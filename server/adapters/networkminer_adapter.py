# NetworkMiner 适配器，通过 subprocess 调用 NetworkMiner 解析 PCAP 文件。

import asyncio
import os
import time

from server.adapters.base_adapter import BaseToolAdapter, ToolResult


# NetworkMiner 网络取证分析适配器，支持 extract/analyze/live。
class NetworkMinerAdapter(BaseToolAdapter):

    @property
    def tool_name(self) -> str:
        return "networkminer"

    @property
    def version(self) -> str:
        return "2.0-pure"

    @property
    def description(self) -> str:
        return "NetworkMiner 网络取证工具，支持 PCAP 文件解析、文件提取与凭证分析"

    @property
    def capabilities(self) -> list[str]:
        return ["pcap_parsing", "file_extraction", "credential_analysis", "certificate_analysis"]

    def __init__(self, networkminer_path: str | None = None):
        from server.tools_config import get_tool_path
        self._exe_path = networkminer_path or get_tool_path("networkminer")

    def validate_input(self, params: dict) -> bool:
        command = params.get("command", "extract")
        if command == "extract":
            return "pcap_dir" in params
        if command == "analyze":
            return "pcap_file" in params
        if command == "live":
            return "interface" in params
        return False

    def _build_command(self, params: dict) -> list[str]:
        command = params.get("command", "extract")
        cmd = [self._exe_path]

        if command == "extract":
            pcap_dir = params["pcap_dir"]
            cmd.extend(["/directory", pcap_dir])
            output_dir = params.get("output_dir", "")
            if output_dir:
                cmd.extend(["/output", output_dir])
        elif command == "analyze":
            pcap_file = params["pcap_file"]
            cmd.extend(["/open", pcap_file])
        elif command == "live":
            interface = params["interface"]
            cmd.extend(["/capture", interface])

        return cmd

    def _parse_output(self, stdout: str, stderr: str, command: str) -> dict:
        result: dict = {
            "command": command,
            "raw_output": stdout,
        }

        if "files_extracted" in stdout.lower():
            for line in stdout.splitlines():
                if "files" in line.lower() and "extracted" in line.lower():
                    result["summary"] = line.strip()
                    break

        if stderr.strip():
            result["warnings"] = stderr.strip()

        return result

    async def run(self, params: dict) -> ToolResult:
        if not self.validate_input(params):
            return ToolResult(
                success=False,
                error="参数验证失败: 请检查 pcap_dir/pcap_file/interface 参数"
            )

        if not self._exe_path:
            return ToolResult(
                success=False,
                error="NetworkMiner 未安装，请将 NetworkMiner.exe 放入 tools/NetworkMiner/ 目录"
            )

        if not os.path.isfile(self._exe_path):
            return ToolResult(
                success=False,
                error=f"NetworkMiner 可执行文件未找到: {self._exe_path}"
            )

        command = params.get("command", "extract")
        if command == "extract":
            pcap_dir = params["pcap_dir"]
            if not os.path.isdir(pcap_dir):
                return ToolResult(
                    success=False,
                    error=f"PCAP 目录未找到: {pcap_dir}"
                )
        elif command == "analyze":
            pcap_file = params["pcap_file"]
            if not os.path.isfile(pcap_file):
                return ToolResult(
                    success=False,
                    error=f"PCAP 文件未找到: {pcap_file}"
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
                    error=f"NetworkMiner 执行超时（{params.get('timeout', 600)}秒）"
                )

            stdout_str = stdout.decode("utf-8", errors="replace")
            stderr_str = stderr.decode("utf-8", errors="replace")

            if proc.returncode != 0 and not stdout_str.strip():
                return ToolResult(
                    success=False,
                    error=f"NetworkMiner 返回错误码 {proc.returncode}: {stderr_str}",
                    duration=time.perf_counter() - start,
                )

            data = self._parse_output(stdout_str, stderr_str, command)
            duration = time.perf_counter() - start
            return ToolResult(success=True, data=data, duration=duration)

        except FileNotFoundError:
            return ToolResult(
                success=False,
                error=f"NetworkMiner 可执行文件未找到: {self._exe_path}"
            )
        except Exception as e:
            duration = time.perf_counter() - start
            return ToolResult(
                success=False,
                error=f"NetworkMiner 执行异常: {str(e)}",
                duration=duration,
            )