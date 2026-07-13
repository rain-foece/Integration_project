"""Fiddler 适配器。

通过 Fiddler CLI 或 ExecAction.exe 自动化分析 SAZ 会话存档和 HTTP 流量数据。
"""

import asyncio
import json
import os
import time

from server.adapters.base_adapter import BaseToolAdapter, ToolResult


class FiddlerAdapter(BaseToolAdapter):
    """Fiddler SAZ 会话分析适配器。

    支持的命令:
        - export: 导出 SAZ 文件中的会话信息
        - extract: 从 SAZ 中提取文件/资源
        - analyze: 分析 HTTP 流量模式
    """

    @property
    def tool_name(self) -> str:
        return "fiddler"

    @property
    def version(self) -> str:
        return "2.0-pure"

    @property
    def description(self) -> str:
        return "Fiddler HTTP 流量分析工具，支持 SAZ 会话解析与流量导出"

    @property
    def capabilities(self) -> list[str]:
        return ["saz_parse", "http_export", "traffic_analysis", "file_extraction"]

    def __init__(self, fiddler_path: str | None = None, execaction_path: str | None = None):
        from server.tools_config import get_tool_path
        self._exe_path = fiddler_path or get_tool_path("fiddler")
        if self._exe_path:
            self._execaction_path = execaction_path or os.path.join(
                os.path.dirname(self._exe_path), "ExecAction.exe"
            )
        else:
            self._execaction_path = None

    def validate_input(self, params: dict) -> bool:
        if "saz_file" not in params:
            return False
        command = params.get("command", "export")
        return command in ("export", "extract", "analyze")

    def _build_command(self, params: dict) -> list[str]:
        command = params.get("command", "export")
        saz_file = params["saz_file"]
        output_dir = params.get("output_dir", os.path.dirname(saz_file))

        if command == "export":
            return [
                self._execaction_path,
                "exec",
                f'import fiddler; '
                f'sessions = fiddler.Utilities.ReadSessionArchive(r"{saz_file}"); '
                f'print(len(sessions))'
            ]
        elif command == "extract":
            return [
                self._exe_path,
                "/quiet",
                "/load:" + saz_file,
                "/export:" + output_dir,
            ]
        elif command == "analyze":
            return [
                self._execaction_path,
                "analyze",
                saz_file,
                "--output", output_dir,
            ]
        return []

    def _parse_output(self, stdout: str, stderr: str, command: str) -> dict:
        result: dict = {
            "command": command,
            "raw_output": stdout,
        }

        if command == "export":
            try:
                session_count = int(stdout.strip())
                result["session_count"] = session_count
            except ValueError:
                result["session_count"] = 0
                result["raw_output"] = stdout

        if stderr.strip():
            result["warnings"] = stderr.strip()

        return result

    async def run(self, params: dict) -> ToolResult:
        if not self.validate_input(params):
            return ToolResult(
                success=False,
                error="参数验证失败: 缺少 saz_file 或 command 不支持"
            )

        if not self._exe_path:
            return ToolResult(
                success=False,
                error="Fiddler 未安装，请将 Fiddler.exe 放入 tools/Fiddler/ 目录"
            )

        executable = self._execaction_path if params.get("command") == "export" else self._exe_path
        if not os.path.isfile(executable):
            return ToolResult(
                success=False,
                error=f"Fiddler 可执行文件未找到: {executable}"
            )

        saz_file = params["saz_file"]
        if not os.path.isfile(saz_file):
            return ToolResult(
                success=False,
                error=f"SAZ 文件未找到: {saz_file}"
            )

        start = time.perf_counter()
        command = params.get("command", "export")

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
                    error=f"Fiddler 执行超时（{params.get('timeout', 600)}秒）"
                )

            stdout_str = stdout.decode("utf-8", errors="replace")
            stderr_str = stderr.decode("utf-8", errors="replace")

            if proc.returncode != 0 and not stdout_str.strip():
                return ToolResult(
                    success=False,
                    error=f"Fiddler 返回错误码 {proc.returncode}: {stderr_str}",
                    duration=time.perf_counter() - start,
                )

            data = self._parse_output(stdout_str, stderr_str, command)
            duration = time.perf_counter() - start
            return ToolResult(success=True, data=data, duration=duration)

        except FileNotFoundError:
            return ToolResult(
                success=False,
                error=f"Fiddler 可执行文件未找到: {executable}"
            )
        except Exception as e:
            duration = time.perf_counter() - start
            return ToolResult(
                success=False,
                error=f"Fiddler 执行异常: {str(e)}",
                duration=duration,
            )