"""Volatility 3 适配器。

通过 subprocess 调用 Volatility 3 进行内存取证分析，支持进程列表、网络连接、
注册表分析等插件。
"""

import asyncio
import json
import os
import re
import time

from server.adapters.base_adapter import BaseToolAdapter, ToolResult

# 支持的 Volatility 3 插件
_SUPPORTED_PLUGINS = {
    "windows.pslist": "进程列表",
    "windows.psscan": "进程扫描",
    "windows.pstree": "进程树",
    "windows.cmdline": "命令行参数",
    "windows.netscan": "网络连接扫描",
    "windows.netstat": "网络连接",
    "windows.dlllist": "DLL 列表",
    "windows.handles": "句柄列表",
    "windows.malfind": "恶意代码检测",
    "windows.modules": "内核模块",
    "windows.registry.hivelist": "注册表蜂巢列表",
    "windows.registry.printkey": "注册表键值",
    "windows.filescan": "文件扫描",
    "windows.mftscan": "MFT 扫描",
    "windows.dumpfiles": "文件提取",
    "windows.svcscan": "服务扫描",
    "windows.driverscan": "驱动扫描",
    "windows.symlinkscan": "符号链接扫描",
    "windows.vadinfo": "VAD 信息",
    "windows.info": "系统信息",
    "linux.pslist": "Linux 进程列表",
    "linux.netscan": "Linux 网络扫描",
    "mac.pslist": "macOS 进程列表",
}


class VolatilityAdapter(BaseToolAdapter):
    """Volatility 3 内存取证分析适配器。

    支持的命令:
        - run: 运行指定插件
        - list: 列出可用插件
        - info: 获取内存镜像信息
    """

    @property
    def tool_name(self) -> str:
        return "volatility"

    @property
    def version(self) -> str:
        return "2.0-pure"

    @property
    def description(self) -> str:
        return "Volatility 3 内存取证分析框架，支持进程、网络、注册表等内存分析"

    @property
    def capabilities(self) -> list[str]:
        return [
            "memory_analysis",
            "process_analysis",
            "network_forensics",
            "registry_analysis",
            "malware_detection",
        ]

    def __init__(self, vol_path: str | None = None):
        from server.tools_config import get_tool_path
        self._exe_path = vol_path or get_tool_path("volatility")
        self._python_cmd = "python"

    def validate_input(self, params: dict) -> bool:
        command = params.get("command", "run")
        if command == "list":
            return True
        if command == "info":
            return "memory_dump" in params
        if command == "run":
            if "memory_dump" not in params:
                return False
            plugin = params.get("plugin", "")
            return plugin in _SUPPORTED_PLUGINS
        return False

    def _build_command(self, params: dict) -> list[str]:
        memory_dump = params.get("memory_dump", "")
        command = params.get("command", "run")

        if self._exe_path and os.path.isfile(self._exe_path):
            cmd = [self._exe_path]
        else:
            cmd = [self._python_cmd, "-m", "volatility3"]

        if command == "list":
            cmd.extend(["-h"])
        elif command == "info":
            cmd.extend(["-f", memory_dump, "windows.info"])
        elif command == "run":
            plugin = params["plugin"]
            cmd.extend(["-f", memory_dump, plugin])
            # 添加额外参数
            extra_args = params.get("extra_args", [])
            if extra_args:
                cmd.extend(extra_args)
            # JSON 输出
            if params.get("json_output", True):
                cmd.extend(["--output", "json"])

        return cmd

    def _parse_output(self, stdout: str, stderr: str, command: str) -> dict:
        result: dict = {
            "command": command,
            "raw_output": stdout,
        }

        if command == "run":
            try:
                parsed = json.loads(stdout) if stdout.strip() else []
                result["data"] = parsed
                result["count"] = len(parsed) if isinstance(parsed, list) else 0
            except json.JSONDecodeError:
                result["data"] = stdout
                result["count"] = 0

        if stderr.strip():
            result["warnings"] = stderr.strip()

        return result

    async def run(self, params: dict) -> ToolResult:
        if not self.validate_input(params):
            return ToolResult(
                success=False,
                error="参数验证失败: 请检查 memory_dump 和 plugin 参数"
            )

        if not self._exe_path:
            return ToolResult(
                success=False,
                error="Volatility 未安装，请将 vol.exe 放入 tools/Volatility3/ 目录"
            )

        command = params.get("command", "run")
        memory_dump = params.get("memory_dump", "")
        if memory_dump and not os.path.isfile(memory_dump):
            return ToolResult(
                success=False,
                error=f"内存镜像文件未找到: {memory_dump}"
            )

        start = time.perf_counter()

        try:
            cmd = self._build_command(params)
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=params.get("timeout", 600)
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return ToolResult(
                    success=False,
                    error=f"Volatility 执行超时（{params.get('timeout', 600)}秒）"
                )

            stdout_str = stdout.decode("utf-8", errors="replace")
            stderr_str = stderr.decode("utf-8", errors="replace")

            if proc.returncode != 0 and not stdout_str.strip():
                return ToolResult(
                    success=False,
                    error=f"Volatility 返回错误码 {proc.returncode}: {stderr_str}",
                    duration=time.perf_counter() - start,
                )

            data = self._parse_output(stdout_str, stderr_str, command)
            duration = time.perf_counter() - start
            return ToolResult(success=True, data=data, duration=duration)

        except FileNotFoundError:
            return ToolResult(
                success=False,
                error="Volatility 未安装，请将 vol.exe 放入 tools/Volatility3/ 目录"
            )
        except Exception as e:
            duration = time.perf_counter() - start
            return ToolResult(
                success=False,
                error=f"Volatility 执行异常: {str(e)}",
                duration=duration,
            )