"""Process Monitor 适配器（纯 Python 实现）。

使用 psutil 监控进程创建/退出，配合 watchdog 监控文件系统变化。
不需要外部 Process Monitor exe。

说明：需要安装 watchdog 库 `pip install watchdog`。
psutil 和 watchdog 均为纯 Python 跨平台库，不依赖外部可执行文件。
"""

import asyncio
import csv
import os
import time
import threading

import psutil

from server.adapters.base_adapter import BaseToolAdapter, ToolResult


class ProcessMonitorAdapter(BaseToolAdapter):
    """Process Monitor 系统活动监控适配器（纯 Python 实现）。

    使用 psutil 监控进程创建/退出，配合 watchdog 监控文件系统变化。
    不需要外部 Process Monitor exe。

    说明：需要安装 watchdog 库 `pip install watchdog`。

    支持的动作:
        - monitor_processes: 定期轮询，记录进程变化
        - monitor_files: 监控目录下文件创建/修改/删除
        - watch_directory: 监控目录并实时输出变更事件
    """

    @property
    def tool_name(self) -> str:
        return "process_monitor"

    @property
    def version(self) -> str:
        return "2.0-pure"

    @property
    def description(self) -> str:
        return (
            "Process Monitor 系统活动监控工具（纯 Python 实现），"
            "使用 psutil 监控进程创建/退出，watchdog 监控文件系统变化，"
            "不需要外部 Process Monitor exe"
        )

    @property
    def capabilities(self) -> list[str]:
        return ["monitor_processes", "monitor_files", "watch_directory"]

    def __init__(self):
        self._stop_event = threading.Event()
        self._monitor_thread: threading.Thread | None = None

    def validate_input(self, params: dict) -> bool:
        """验证输入参数。

        Args:
            params: 必须包含 "action" 键（默认 "monitor_processes"）。
                    monitor_files / watch_directory 动作时还需要 "directory" 键。

        Returns:
            参数是否合法。
        """
        action = params.get("action", "monitor_processes")
        if action not in ("monitor_processes", "monitor_files", "watch_directory"):
            return False
        if action in ("monitor_files", "watch_directory"):
            return "directory" in params
        return True

    # ------------------------------------------------------------------
    # 动作：monitor_processes
    # ------------------------------------------------------------------
    def _action_monitor_processes(self, params: dict) -> ToolResult:
        """定期轮询进程列表，记录进程创建和退出事件。

        参数:
            duration: 监控持续时间（秒），默认 30。
            output_file: 输出文件路径，写入 CSV 格式的进程变化日志。
            include_details: 是否包含进程详细信息（路径、内存等），默认 True。
        """
        duration = float(params.get("duration", 30))
        output_file = params.get("output_file", "process_changes.csv")
        include_details = params.get("include_details", True)
        interval = float(params.get("interval", 1.0))

        start = time.perf_counter()

        # 确保输出目录存在
        out_dir = os.path.dirname(os.path.abspath(output_file))
        if out_dir and not os.path.isdir(out_dir):
            os.makedirs(out_dir, exist_ok=True)

        # 获取初始进程快照
        previous_pids = set(psutil.pids())
        previous_procs: dict[int, dict] = {}
        if include_details:
            for pid in previous_pids:
                try:
                    p = psutil.Process(pid)
                    previous_procs[pid] = {
                        "name": p.name(),
                        "exe": p.exe() or "",
                        "cmdline": " ".join(p.cmdline() or []),
                        "create_time": p.create_time(),
                    }
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

        events: list[dict] = []
        self._stop_event.clear()

        try:
            end_time = time.monotonic() + duration

            while time.monotonic() < end_time and not self._stop_event.is_set():
                current_pids = set(psutil.pids())
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

                # 新进程
                new_pids = current_pids - previous_pids
                for pid in new_pids:
                    event = {
                        "timestamp": timestamp,
                        "event_type": "process_start",
                        "pid": pid,
                        "name": "",
                        "exe": "",
                        "cmdline": "",
                    }
                    try:
                        p = psutil.Process(pid)
                        event["name"] = p.name()
                        if include_details:
                            event["exe"] = p.exe() or ""
                            event["cmdline"] = " ".join(p.cmdline() or [])
                            event["create_time"] = p.create_time()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                    events.append(event)

                # 退出进程
                exited_pids = previous_pids - current_pids
                for pid in exited_pids:
                    event = {
                        "timestamp": timestamp,
                        "event_type": "process_exit",
                        "pid": pid,
                    }
                    if pid in previous_procs:
                        event["name"] = previous_procs[pid]["name"]
                        event["exe"] = previous_procs[pid]["exe"]
                    events.append(event)

                # 更新快照
                previous_pids = current_pids
                if include_details:
                    previous_procs = {}
                    for pid in current_pids:
                        try:
                            p = psutil.Process(pid)
                            previous_procs[pid] = {
                                "name": p.name(),
                                "exe": p.exe() or "",
                                "cmdline": " ".join(p.cmdline() or []),
                                "create_time": p.create_time(),
                            }
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass

                time.sleep(interval)

        finally:
            self._stop_event.clear()

        # 写入 CSV 文件
        csv_path = self._write_events_csv(events, output_file)

        running_count = len(psutil.pids())
        duration_sec = time.perf_counter() - start

        return ToolResult(
            success=True,
            data={
                "action": "monitor_processes",
                "duration_seconds": duration_sec,
                "total_events": len(events),
                "process_starts": sum(1 for e in events if e["event_type"] == "process_start"),
                "process_exits": sum(1 for e in events if e["event_type"] == "process_exit"),
                "current_running_processes": running_count,
                "events": events,
                "output_file": csv_path,
            },
            duration=duration_sec,
        )

    # ------------------------------------------------------------------
    # 动作：monitor_files
    # ------------------------------------------------------------------
    def _action_monitor_files(self, params: dict) -> ToolResult:
        """监控目录下文件创建/修改/删除事件。

        使用 watchdog 库进行文件系统事件监控。

        参数:
            directory: 要监控的目录路径。
            duration: 监控持续时间（秒），默认 30。
            output_file: 输出文件路径，写入 CSV 格式的文件变更日志。
            recursive: 是否递归监控子目录，默认 True。
            patterns: 过滤的文件模式列表，如 ["*.txt", "*.log"]，默认监控所有文件。
        """
        directory = params["directory"]
        duration = float(params.get("duration", 30))
        output_file = params.get("output_file", "file_changes.csv")
        recursive = params.get("recursive", True)
        patterns = params.get("patterns", None)

        if not os.path.isdir(directory):
            return ToolResult(success=False, error=f"目录不存在: {directory}")

        # 确保输出目录存在
        out_dir = os.path.dirname(os.path.abspath(output_file))
        if out_dir and not os.path.isdir(out_dir):
            os.makedirs(out_dir, exist_ok=True)

        start = time.perf_counter()

        events: list[dict] = []

        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler
        except ImportError:
            return ToolResult(
                success=False,
                error="watchdog 库未安装，请执行: pip install watchdog",
            )

        class FileEventHandler(FileSystemEventHandler):
            def __init__(self, event_list: list[dict]):
                self._events = event_list

            def on_created(self, event):
                self._events.append({
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "event_type": "file_created",
                    "path": event.src_path,
                    "is_directory": event.is_directory,
                })

            def on_modified(self, event):
                self._events.append({
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "event_type": "file_modified",
                    "path": event.src_path,
                    "is_directory": event.is_directory,
                })

            def on_deleted(self, event):
                self._events.append({
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "event_type": "file_deleted",
                    "path": event.src_path,
                    "is_directory": event.is_directory,
                })

            def on_moved(self, event):
                self._events.append({
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "event_type": "file_moved",
                    "path": event.src_path,
                    "dest_path": event.dest_path,
                    "is_directory": event.is_directory,
                })

        observer = Observer()
        handler = FileEventHandler(events)

        try:
            observer.schedule(handler, directory, recursive=recursive)
            observer.start()

            self._stop_event.clear()
            end_time = time.monotonic() + duration
            while time.monotonic() < end_time and not self._stop_event.is_set():
                time.sleep(0.5)

            observer.stop()
            observer.join(timeout=5)
        finally:
            self._stop_event.clear()
            if observer.is_alive():
                observer.stop()
                observer.join(timeout=2)

        # 写入 CSV 文件
        csv_path = self._write_events_csv(events, output_file)

        duration_sec = time.perf_counter() - start

        return ToolResult(
            success=True,
            data={
                "action": "monitor_files",
                "directory": os.path.abspath(directory),
                "duration_seconds": duration_sec,
                "total_events": len(events),
                "file_created": sum(1 for e in events if e["event_type"] == "file_created"),
                "file_modified": sum(1 for e in events if e["event_type"] == "file_modified"),
                "file_deleted": sum(1 for e in events if e["event_type"] == "file_deleted"),
                "file_moved": sum(1 for e in events if e["event_type"] == "file_moved"),
                "events": events,
                "output_file": csv_path,
            },
            duration=duration_sec,
        )

    # ------------------------------------------------------------------
    # 动作：watch_directory
    # ------------------------------------------------------------------
    def _action_watch_directory(self, params: dict) -> ToolResult:
        """监控目录并实时输出变更事件。

        与 monitor_files 类似，但更侧重于实时输出，
        并支持指定文件模式过滤。

        参数:
            directory: 要监控的目录路径。
            duration: 监控持续时间（秒），默认 30。
            output_file: 输出文件路径。
            recursive: 是否递归监控子目录，默认 True。
            patterns: 过滤的文件模式列表，如 ["*.txt", "*.log"]，默认监控所有文件。
        """
        # 复用 monitor_files 的实现，两者逻辑相同
        return self._action_monitor_files(params)

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------
    @staticmethod
    def _write_events_csv(events: list[dict], output_file: str) -> str:
        """将事件列表写入 CSV 文件。

        Args:
            events: 事件字典列表。
            output_file: 输出文件路径。

        Returns:
            输出文件的绝对路径。
        """
        if not events:
            return ""

        fieldnames = list(events[0].keys())

        with open(output_file, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for event in events:
                writer.writerow(event)

        return os.path.abspath(output_file)

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------
    async def run(self, params: dict) -> ToolResult:
        """异步执行工具。

        Args:
            params: 参数字典，必须包含 "action" 键。

        Returns:
            ToolResult 执行结果。
        """
        if not self.validate_input(params):
            return ToolResult(
                success=False,
                error=(
                    "参数验证失败: action 必须为 'monitor_processes', 'monitor_files' 或 "
                    "'watch_directory'；monitor_files/watch_directory 动作还需要 "
                    "'directory' 参数"
                ),
            )

        action = params.get("action", "monitor_processes")

        try:
            # 所有监控动作都是阻塞的，使用默认线程池异步执行
            loop = asyncio.get_event_loop()

            if action == "monitor_processes":
                result = await loop.run_in_executor(
                    None, self._action_monitor_processes, params
                )
            elif action == "monitor_files":
                result = await loop.run_in_executor(
                    None, self._action_monitor_files, params
                )
            elif action == "watch_directory":
                result = await loop.run_in_executor(
                    None, self._action_watch_directory, params
                )
            else:
                return ToolResult(success=False, error=f"未知动作: {action}")

            return result

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Process Monitor 执行异常: {str(e)}",
            )