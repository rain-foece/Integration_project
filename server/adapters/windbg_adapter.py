"""WinDbg / CDB 适配器。

通过 subprocess 调用 CDB（命令行调试器）进行 Windows 崩溃转储分析。
"""

import asyncio
import os
import time

from server.adapters.base_adapter import BaseToolAdapter, ToolResult


class WinDbgAdapter(BaseToolAdapter):
    """WinDbg/CDB 崩溃转储分析适配器。

    支持的命令:
        - analyze: 运行 !analyze -v 自动分析
        - stack: 获取调用栈
        - modules: 列出加载模块
        - memory: 读取内存区域
        - custom: 运行自定义命令
    """

    @property
    def tool_name(self) -> str:
        return "windbg"

    @property
    def version(self) -> str:
        return "2.0-pure"

    @property
    def description(self) -> str:
        return "WinDbg/CDB Windows 调试工具，支持崩溃转储分析、调用栈与内存检查"

    @property
    def capabilities(self) -> list[str]:
        return ["crash_analysis", "stack_trace", "memory_analysis", "module_analysis"]

    def __init__(self, cdb_path: str | None = None):
        from server.tools_config import get_tool_path
        self._exe_path = cdb_path or get_tool_path("windbg")

    def validate_input(self, params: dict) -> bool:
        if "dump_file" not in params:
            return False
        command = params.get("command", "analyze")
        return command in ("analyze", "stack", "modules", "memory", "custom")

    def _build_command(self, params: dict) -> list[str]:
        command = params.get("command", "analyze")
        dump_file = params["dump_file"]
        cmd = [self._exe_path, "-z", dump_file]

        if command == "analyze":
            cmds = "!analyze -v;q"
        elif command == "stack":
            thread_id = params.get("thread_id", "")
            if thread_id:
                cmds = f"~{thread_id}k;q"
            else:
                cmds = "~*k;q"
        elif command == "modules":
            cmds = "lm;q"
        elif command == "memory":
            address = params.get("address", "0")
            length = params.get("length", "256")
            cmds = f"db {address} L{length};q"
        elif command == "custom":
            cmds = params.get("commands", "!analyze -v;q")
        else:
            cmds = "q"

        cmd.extend(["-c", cmds])
        return cmd

    def _parse_output(self, stdout: str, stderr: str, command: str) -> dict:
        result: dict = {
            "command": command,
            "raw_output": stdout,
        }

        if command == "analyze":
            lines = stdout.strip().splitlines()
            for i, line in enumerate(lines):
                if "BUGCHECK" in line or "EXCEPTION" in line:
                    result["bugcheck"] = line.strip()
                    # 捕获后续分析行
                    analysis_lines = []
                    for j in range(i, min(i + 50, len(lines))):
                        l = lines[j].strip()
                        if l and not l.startswith("{"):
                            analysis_lines.append(l)
                    result["analysis"] = "\n".join(analysis_lines[:30])
                    break

        if stderr.strip():
            result["warnings"] = stderr.strip()

        return result

    async def run(self, params: dict) -> ToolResult:
        if not self.validate_input(params):
            return ToolResult(
                success=False,
                error="参数验证失败: 缺少 dump_file 或 command 不支持"
            )

        if not self._exe_path:
            return ToolResult(
                success=False,
                error="WinDbg 未安装，请将 cdb.exe 放入 tools/WinDbg/ 目录"
            )

        if not os.path.isfile(self._exe_path):
            return ToolResult(
                success=False,
                error=f"CDB 可执行文件未找到: {self._exe_path}"
            )

        dump_file = params["dump_file"]
        if not os.path.isfile(dump_file):
            return ToolResult(
                success=False,
                error=f"转储文件未找到: {dump_file}"
            )

        start = time.perf_counter()
        command = params.get("command", "analyze")

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
                    error=f"CDB 执行超时（{params.get('timeout', 600)}秒）"
                )

            stdout_str = stdout.decode("utf-8", errors="replace")
            stderr_str = stderr.decode("utf-8", errors="replace")

            if proc.returncode != 0 and not stdout_str.strip():
                return ToolResult(
                    success=False,
                    error=f"CDB 返回错误码 {proc.returncode}: {stderr_str}",
                    duration=time.perf_counter() - start,
                )

            data = self._parse_output(stdout_str, stderr_str, command)
            duration = time.perf_counter() - start
            return ToolResult(success=True, data=data, duration=duration)

        except FileNotFoundError:
            return ToolResult(
                success=False,
                error=f"CDB 可执行文件未找到: {self._exe_path}"
            )
        except Exception as e:
            duration = time.perf_counter() - start
            return ToolResult(
                success=False,
                error=f"CDB 执行异常: {str(e)}",
                duration=duration,
            )