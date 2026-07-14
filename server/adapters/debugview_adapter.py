# DebugView 适配器（纯 Python 实现），通过 ctypes 调用 kernel32.dll 使用 DBWIN 共享内存机制捕获 OutputDebugString 输出。

import asyncio
import ctypes
import ctypes.wintypes
import os
import time
import threading
from concurrent.futures import ThreadPoolExecutor

from server.adapters.base_adapter import BaseToolAdapter, ToolResult

# Win32 常量与类型定义
DBWIN_BUFFER_SIZE = 4096
DBWIN_MUTEX = "DBWinMutex"
DBWIN_BUFFER = "DBWIN_BUFFER"
DBWIN_BUFFER_READY = "DBWIN_BUFFER_READY"
DBWIN_DATA_READY = "DBWIN_DATA_READY"

# 从 kernel32.dll 获取所需函数
_kernel32 = ctypes.windll.kernel32

OpenMutexW = _kernel32.OpenMutexW
OpenMutexW.restype = ctypes.wintypes.HANDLE
OpenMutexW.argtypes = [ctypes.wintypes.DWORD, ctypes.wintypes.BOOL, ctypes.wintypes.LPCWSTR]

CreateMutexW = _kernel32.CreateMutexW
CreateMutexW.restype = ctypes.wintypes.HANDLE
CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.wintypes.BOOL, ctypes.wintypes.LPCWSTR]

WaitForSingleObject = _kernel32.WaitForSingleObject
WaitForSingleObject.restype = ctypes.wintypes.DWORD
WaitForSingleObject.argtypes = [ctypes.wintypes.HANDLE, ctypes.wintypes.DWORD]

ReleaseMutex = _kernel32.ReleaseMutex
ReleaseMutex.restype = ctypes.wintypes.BOOL
ReleaseMutex.argtypes = [ctypes.wintypes.HANDLE]

CloseHandle = _kernel32.CloseHandle
CloseHandle.restype = ctypes.wintypes.BOOL
CloseHandle.argtypes = [ctypes.wintypes.HANDLE]

OpenEventW = _kernel32.OpenEventW
OpenEventW.restype = ctypes.wintypes.HANDLE
OpenEventW.argtypes = [ctypes.wintypes.DWORD, ctypes.wintypes.BOOL, ctypes.wintypes.LPCWSTR]

CreateEventW = _kernel32.CreateEventW
CreateEventW.restype = ctypes.wintypes.HANDLE
CreateEventW.argtypes = [ctypes.c_void_p, ctypes.wintypes.BOOL, ctypes.wintypes.BOOL, ctypes.wintypes.LPCWSTR]

SetEvent = _kernel32.SetEvent
SetEvent.restype = ctypes.wintypes.BOOL
SetEvent.argtypes = [ctypes.wintypes.HANDLE]

CreateFileMappingW = _kernel32.CreateFileMappingW
CreateFileMappingW.restype = ctypes.wintypes.HANDLE
CreateFileMappingW.argtypes = [
    ctypes.wintypes.HANDLE, ctypes.c_void_p, ctypes.wintypes.DWORD,
    ctypes.wintypes.DWORD, ctypes.wintypes.DWORD, ctypes.wintypes.LPCWSTR,
]

OpenFileMappingW = _kernel32.OpenFileMappingW
OpenFileMappingW.restype = ctypes.wintypes.HANDLE
OpenFileMappingW.argtypes = [ctypes.wintypes.DWORD, ctypes.wintypes.BOOL, ctypes.wintypes.LPCWSTR]

MapViewOfFile = _kernel32.MapViewOfFile
MapViewOfFile.restype = ctypes.c_void_p
MapViewOfFile.argtypes = [
    ctypes.wintypes.HANDLE, ctypes.wintypes.DWORD, ctypes.wintypes.DWORD,
    ctypes.wintypes.DWORD, ctypes.c_size_t,
]

UnmapViewOfFile = _kernel32.UnmapViewOfFile
UnmapViewOfFile.restype = ctypes.wintypes.BOOL
UnmapViewOfFile.argtypes = [ctypes.c_void_p]

OutputDebugStringW = _kernel32.OutputDebugStringW
OutputDebugStringW.argtypes = [ctypes.wintypes.LPCWSTR]

# 常量
SYNCHRONIZE = 0x00100000
STANDARD_RIGHTS_REQUIRED = 0x000F0000
MUTEX_ALL_ACCESS = 0x1F0001
EVENT_MODIFY_STATE = 0x0002
FILE_MAP_READ = 0x0004
PAGE_READWRITE = 0x04
WAIT_OBJECT_0 = 0x00000000
WAIT_TIMEOUT = 0x00000102
INFINITE = 0xFFFFFFFF
ERROR_FILE_NOT_FOUND = 2
ERROR_ALREADY_EXISTS = 183


# DebugView 调试输出捕获适配器，通过 ctypes + DBWIN 共享内存捕获 OutputDebugString 输出，支持 capture_python / list_messages / filter_keyword 动作。
class DebugViewAdapter(BaseToolAdapter):

    @property
    def tool_name(self) -> str:
        return "debugview"

    @property
    def version(self) -> str:
        return "2.0-pure"

    @property
    def description(self) -> str:
        return (
            "DebugView 调试输出捕获工具（纯 Python 实现），"
            "通过 ctypes 调用 kernel32.dll 使用 DBWIN 共享内存捕获 OutputDebugString 输出，"
            "支持 Python 进程调试消息的实时捕获与关键字过滤"
        )

    @property
    def capabilities(self) -> list[str]:
        return ["capture_python", "list_messages", "filter_keyword"]

    def __init__(self):
        self._captured_messages: list[dict] = []
        self._stop_event = threading.Event()
        self._capture_thread: threading.Thread | None = None

    def validate_input(self, params: dict) -> bool:
        """验证 action 参数。filter_keyword 时需要 keyword。"""
        action = params.get("action", "capture_python")
        if action not in ("capture_python", "list_messages", "filter_keyword"):
            return False
        if action == "filter_keyword":
            return "keyword" in params
        return True

    # 通过 DBWIN 共享内存捕获调试输出。duration: 捕获时长（秒），0 表示无限；output_file: 可选输出文件路径。
    def _capture_dbwin(self, duration: float, output_file: str | None) -> list[dict]:
        messages: list[dict] = []
        handle_mutex = None
        handle_mapping = None
        handle_buffer_ready = None
        handle_data_ready = None
        p_buffer = None
        file_handle = None

        try:
            handle_mutex = OpenMutexW(SYNCHRONIZE, False, DBWIN_MUTEX)
            if not handle_mutex:
                handle_mutex = CreateMutexW(None, False, DBWIN_MUTEX)
            if not handle_mutex:
                return messages

            handle_mapping = OpenFileMappingW(FILE_MAP_READ, False, DBWIN_BUFFER)
            if not handle_mapping:
                handle_mapping = CreateFileMappingW(
                    ctypes.wintypes.HANDLE(-1), None, PAGE_READWRITE,
                    0, DBWIN_BUFFER_SIZE, DBWIN_BUFFER,
                )
            if not handle_mapping:
                return messages

            p_buffer = MapViewOfFile(handle_mapping, FILE_MAP_READ, 0, 0, DBWIN_BUFFER_SIZE)
            if not p_buffer:
                return messages

            handle_buffer_ready = OpenEventW(SYNCHRONIZE, False, DBWIN_BUFFER_READY)
            if not handle_buffer_ready:
                handle_buffer_ready = CreateEventW(None, False, True, DBWIN_BUFFER_READY)
            handle_data_ready = OpenEventW(SYNCHRONIZE, False, DBWIN_DATA_READY)
            if not handle_data_ready:
                handle_data_ready = CreateEventW(None, False, False, DBWIN_DATA_READY)
            if not handle_buffer_ready or not handle_data_ready:
                return messages

            if output_file:
                file_handle = open(output_file, "w", encoding="utf-8")

            start_time = time.monotonic()
            wait_timeout = 1000  # 毫秒

            while not self._stop_event.is_set():
                if duration > 0 and (time.monotonic() - start_time) >= duration:
                    break

                # 等待数据就绪
                ret = WaitForSingleObject(handle_data_ready, wait_timeout)
                if ret != WAIT_OBJECT_0:
                    continue

                # 获取锁
                ret = WaitForSingleObject(handle_mutex, 1000)
                if ret != WAIT_OBJECT_0:
                    continue

                try:
                    # 读取缓冲区: 前 4 字节 = PID（DWORD），后 4092 字节 = 消息文本
                    pid = ctypes.cast(p_buffer, ctypes.POINTER(ctypes.wintypes.DWORD))[0]
                    msg_bytes = ctypes.cast(
                        ctypes.c_void_p(p_buffer + 4),
                        ctypes.POINTER(ctypes.c_char * (DBWIN_BUFFER_SIZE - 4)),
                    )[0]
                    # 查找 null 终止符
                    null_pos = msg_bytes.find(b"\x00")
                    if null_pos >= 0:
                        msg_text = msg_bytes[:null_pos].decode("utf-8", errors="replace")
                    else:
                        msg_text = msg_bytes.decode("utf-8", errors="replace")

                    msg_entry = {"pid": pid, "content": msg_text}
                    messages.append(msg_entry)

                    if file_handle:
                        file_handle.write(f"[PID:{pid}] {msg_text}\n")
                        file_handle.flush()
                finally:
                    ReleaseMutex(handle_mutex)

                # 通知缓冲区已就绪
                SetEvent(handle_buffer_ready)

        finally:
            self._stop_event.clear()
            if file_handle:
                file_handle.close()
            if p_buffer:
                UnmapViewOfFile(p_buffer)
            if handle_mapping:
                CloseHandle(handle_mapping)
            if handle_mutex:
                CloseHandle(handle_mutex)
            if handle_buffer_ready:
                CloseHandle(handle_buffer_ready)
            if handle_data_ready:
                CloseHandle(handle_data_ready)

        return messages

    def _action_capture_python(self, params: dict) -> ToolResult:
        """捕获 Python 进程的 OutputDebugString 输出。duration: 捕获时长(秒)，output_file: 输出文件路径。"""
        duration = float(params.get("duration", 30))
        output_file = params.get("output_file", "captured_messages.txt")

        # 确保输出目录存在
        out_dir = os.path.dirname(os.path.abspath(output_file))
        if out_dir and not os.path.isdir(out_dir):
            os.makedirs(out_dir, exist_ok=True)

        start = time.perf_counter()

        # 发送测试消息以确认缓冲区正常工作
        test_msg = f"[DebugViewAdapter] 捕获开始 - PID={os.getpid()}"
        OutputDebugStringW(test_msg)

        self._captured_messages = []
        self._stop_event.clear()

        captured = self._capture_dbwin(duration=duration, output_file=output_file)

        # 过滤出 Python 进程（通过进程名）
        python_messages = []
        for msg in captured:
            try:
                import psutil
                proc = psutil.Process(msg["pid"])
                proc_name = proc.name().lower()
                if "python" in proc_name or "python" in proc.exe().lower():
                    msg["process_name"] = proc.name()
                    python_messages.append(msg)
            except Exception:
                # 如果 psutil 不可用或进程已退出，仍保留消息
                python_messages.append(msg)

        self._captured_messages = python_messages

        duration_sec = time.perf_counter() - start
        return ToolResult(
            success=True,
            data={
                "action": "capture_python",
                "total_captured": len(captured),
                "python_messages": len(python_messages),
                "messages": python_messages,
                "output_file": os.path.abspath(output_file),
                "duration_seconds": duration_sec,
            },
            duration=duration_sec,
        )

    def _action_list_messages(self, params: dict) -> ToolResult:
        """列出已捕获的消息。limit: 返回数量上限。"""
        limit = int(params.get("limit", 0))
        messages = self._captured_messages
        if limit > 0:
            messages = messages[:limit]

        return ToolResult(
            success=True,
            data={
                "action": "list_messages",
                "total": len(self._captured_messages),
                "returned": len(messages),
                "messages": messages,
            },
        )

    def _action_filter_keyword(self, params: dict) -> ToolResult:
        """按关键字过滤已捕获的消息。keyword: 过滤关键字(不区分大小写)，output_file: 可选输出文件。"""
        keyword = params.get("keyword", "")
        output_file = params.get("output_file", "")

        filtered = [
            msg for msg in self._captured_messages
            if keyword.lower() in msg.get("content", "").lower()
        ]

        if output_file:
            out_dir = os.path.dirname(os.path.abspath(output_file))
            if out_dir and not os.path.isdir(out_dir):
                os.makedirs(out_dir, exist_ok=True)
            with open(output_file, "w", encoding="utf-8") as f:
                for msg in filtered:
                    f.write(f"[PID:{msg['pid']}] {msg['content']}\n")

        return ToolResult(
            success=True,
            data={
                "action": "filter_keyword",
                "keyword": keyword,
                "total_messages": len(self._captured_messages),
                "matched": len(filtered),
                "messages": filtered,
                "output_file": os.path.abspath(output_file) if output_file else None,
            },
        )

    async def run(self, params: dict) -> ToolResult:
        """异步执行工具。action: capture_python/list_messages/filter_keyword。"""
        if not self.validate_input(params):
            return ToolResult(
                success=False,
                error=(
                    "参数验证失败: action 必须为 'capture_python', 'list_messages' 或 "
                    "'filter_keyword'；filter_keyword 动作还需要 'keyword' 参数"
                ),
            )

        action = params.get("action", "capture_python")

        try:
            if action == "capture_python":
                # capture_python 是阻塞操作，使用线程池异步执行
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(self._action_capture_python, params)
                    result = await asyncio.get_event_loop().run_in_executor(
                        None, future.result
                    )
                    return result
            elif action == "list_messages":
                return self._action_list_messages(params)
            elif action == "filter_keyword":
                return self._action_filter_keyword(params)
            else:
                return ToolResult(success=False, error=f"未知动作: {action}")
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"DebugView 执行异常: {str(e)}",
            )