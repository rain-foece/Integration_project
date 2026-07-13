"""Process Explorer 适配器（纯 Python 实现）。

基于 psutil 库，无需外部 exe，直接通过 Python 接口获取进程信息。
"""

import time
from datetime import datetime
from typing import Any

from server.adapters.base_adapter import BaseToolAdapter, ToolResult

try:
    import psutil
    _PSUTIL_AVAILABLE = True
except ImportError:
    _PSUTIL_AVAILABLE = False


class ProcessExplorerAdapter(BaseToolAdapter):
    """Process Explorer 进程分析适配器（纯 Python 实现）。

    支持的命令:
        - process_list: 列出所有进程
        - process_tree: 构建进程树
        - dll_list: 列出指定进程加载的 DLL
        - network: 列出所有网络连接
    """

    @property
    def tool_name(self) -> str:
        return "process_explorer"

    @property
    def version(self) -> str:
        return "2.0-pure"

    @property
    def description(self) -> str:
        return "Process Explorer 进程分析工具（纯 Python/psutil 实现），支持进程列表、进程树、DLL 列表与网络连接分析"

    @property
    def capabilities(self) -> list[str]:
        return ["process_list", "process_tree", "dll_analysis", "network_analysis"]

    def validate_input(self, params: dict) -> bool:
        """验证输入参数。

        Args:
            params: 包含 "action"（可选）和 "pid"（可选）参数的字典。

        Returns:
            参数是否合法。
        """
        action = params.get("action", "process_list")
        valid_actions = {"process_list", "process_tree", "dll_list", "network"}
        if action not in valid_actions:
            return False
        if action == "dll_list":
            return "pid" in params
        return True

    # ------------------------------------------------------------------
    # 内部辅助方法
    # ------------------------------------------------------------------

    @staticmethod
    def _format_process_info(proc: Any) -> dict:
        """格式化单个进程信息为字典。"""
        try:
            with proc.oneshot():
                pid = proc.pid
                name = proc.name() or ""
                cpu_percent = proc.cpu_percent()
                mem_info = proc.memory_info() if hasattr(proc, "memory_info") else None
                mem_rss = mem_info.rss if mem_info else 0
                mem_percent = proc.memory_percent()
                status = proc.status()
                try:
                    create_time = datetime.fromtimestamp(proc.create_time()).isoformat()
                except (OSError, psutil.NoSuchProcess):
                    create_time = ""
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return {}

        return {
            "pid": pid,
            "name": name,
            "cpu_percent": cpu_percent,
            "memory_rss": mem_rss,
            "memory_percent": round(mem_percent, 2),
            "status": status,
            "create_time": create_time,
        }

    @staticmethod
    def _format_connection(conn: Any) -> dict:
        """格式化单个网络连接信息为字典。"""
        local_addr = f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else ""
        remote_addr = f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else ""
        return {
            "fd": conn.fd,
            "family": str(conn.family),
            "type": str(conn.type),
            "local_addr": local_addr,
            "remote_addr": remote_addr,
            "status": conn.status,
            "pid": conn.pid or 0,
        }

    # ------------------------------------------------------------------
    # action 处理
    # ------------------------------------------------------------------

    def _process_list(self) -> dict:
        """列出所有进程。"""
        processes = []
        for proc in psutil.process_iter():
            info = self._format_process_info(proc)
            if info:
                processes.append(info)

        return {
            "action": "process_list",
            "total_count": len(processes),
            "processes": processes,
        }

    def _process_tree(self) -> dict:
        """构建进程树（父子关系）。"""
        proc_map: dict[int, dict] = {}
        for proc in psutil.process_iter():
            try:
                with proc.oneshot():
                    pid = proc.pid
                    name = proc.name() or ""
                    ppid = proc.ppid() or 0
                    status = proc.status()
                    try:
                        create_time = datetime.fromtimestamp(proc.create_time()).isoformat()
                    except (OSError, psutil.NoSuchProcess):
                        create_time = ""
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

            proc_map[pid] = {
                "pid": pid,
                "name": name,
                "ppid": ppid,
                "status": status,
                "create_time": create_time,
                "children": [],
            }

        # 构建父子关系
        roots: list[dict] = []
        for pid, node in proc_map.items():
            ppid = node["ppid"]
            if ppid in proc_map:
                proc_map[ppid]["children"].append(node)
            else:
                roots.append(node)

        return {
            "action": "process_tree",
            "total_count": len(proc_map),
            "tree": roots,
        }

    def _dll_list(self, pid: int) -> dict:
        """列出指定进程加载的 DLL。"""
        try:
            proc = psutil.Process(pid)
            proc_name = proc.name()
            dlls = []
            for mmap in proc.memory_maps():
                if mmap.path and (mmap.path.lower().endswith(".dll") or mmap.path.lower().endswith(".exe")):
                    dlls.append({
                        "path": mmap.path,
                        "rss": mmap.rss,
                    })
        except psutil.NoSuchProcess:
            return {
                "action": "dll_list",
                "pid": pid,
                "error": f"进程 PID={pid} 不存在",
                "dlls": [],
            }
        except psutil.AccessDenied:
            return {
                "action": "dll_list",
                "pid": pid,
                "error": f"权限不足，无法访问进程 PID={pid}",
                "dlls": [],
            }

        return {
            "action": "dll_list",
            "pid": pid,
            "process_name": proc_name,
            "dll_count": len(dlls),
            "dlls": dlls,
        }

    def _network(self) -> dict:
        """列出所有网络连接。"""
        connections = []
        try:
            for conn in psutil.net_connections(kind="all"):
                connections.append(self._format_connection(conn))
        except psutil.AccessDenied:
            return {
                "action": "network",
                "error": "权限不足，无法获取网络连接信息",
                "connections": [],
            }

        return {
            "action": "network",
            "total_count": len(connections),
            "connections": connections,
        }

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------

    async def run(self, params: dict) -> ToolResult:
        """异步执行进程分析。

        Args:
            params: 参数字典，支持:
                - action: "process_list" | "process_tree" | "dll_list" | "network"
                - pid: 进程 PID（dll_list 必需）

        Returns:
            ToolResult 执行结果。
        """
        if not _PSUTIL_AVAILABLE:
            return ToolResult(
                success=False,
                error="psutil 库未安装，请运行: pip install psutil",
            )

        if not self.validate_input(params):
            return ToolResult(
                success=False,
                error="参数验证失败: action 必须是 process_list / process_tree / dll_list / network 之一，dll_list 需要提供 pid",
            )

        action = params.get("action", "process_list")
        start = time.perf_counter()

        try:
            if action == "process_list":
                data = self._process_list()
            elif action == "process_tree":
                data = self._process_tree()
            elif action == "dll_list":
                pid = params["pid"]
                data = self._dll_list(int(pid))
            elif action == "network":
                data = self._network()
            else:
                return ToolResult(
                    success=False,
                    error=f"未知的 action: {action}",
                )
        except Exception as e:
            duration = time.perf_counter() - start
            return ToolResult(
                success=False,
                error=f"执行异常: {type(e).__name__}: {str(e)}",
                duration=duration,
            )

        duration = time.perf_counter() - start
        return ToolResult(success=True, data=data, duration=duration)