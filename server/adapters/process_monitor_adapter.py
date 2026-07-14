# Process Monitor 适配器（纯 Python 实现），使用 psutil 监控进程变化，配合 watchdog 监控文件系统。

import asyncio
import csv
import os
import time
import threading

import psutil

from server.adapters.base_adapter import BaseToolAdapter, ToolResult


# Process Monitor 系统活动监控适配器，使用 psutil + watchdog 监控进程创建/退出和文件系统变化，支持 monitor_processes / monitor_files / watch_directory。
class ProcessMonitorAdapter(BaseToolAdapter):

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
        """验证 action 参数。monitor_files/watch_directory 时需要 directory。"""
        action = params.get("action", "monitor_processes")
        if action not in ("monitor_processes", "monitor_files", "watch_directory"):
            return False
        if action in ("monitor_files", "watch_directory"):
            return "directory" in params
        return True

    def _action_monitor_processes(self, params: dict) -> ToolResult:
        """监控进程创建和退出事件。duration: 监控时长(秒)，output_file: CSV 输出路径。"""
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

    def _action_monitor_files(self, params: dict) -> ToolResult:
        """监控文件创建/修改/删除事件。directory: 监控目录，duration: 监控时长(秒)。"""
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

    def _action_watch_directory(self, params: dict) -> ToolResult:
        """监控目录变更事件，与 monitor_files 行为一致。"""
        return self._action_monitor_files(params)

    @staticmethod
    def _write_events_csv(events: list[dict], output_file: str) -> str:
        """将事件列表写入 CSV 文件，返回绝对路径。"""
        if not events:
            return ""

        fieldnames = list(events[0].keys())

        with open(output_file, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for event in events:
                writer.writerow(event)

        return os.path.abspath(output_file)

    async def run(self, params: dict) -> ToolResult:
        """异步执行监控。action: monitor_processes/monitor_files/watch_directory。"""
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