# PhotoRec / TestDisk 适配器，通过 subprocess 调用 PhotoRec 恢复文件。

import asyncio
import os
import time

from server.adapters.base_adapter import BaseToolAdapter, ToolResult


# PhotoRec/TestDisk 文件恢复适配器，支持 recover/analyze/list_files。
class TestDiskAdapter(BaseToolAdapter):

    @property
    def tool_name(self) -> str:
        return "testdisk"

    @property
    def version(self) -> str:
        return "2.0-pure"

    @property
    def description(self) -> str:
        return "PhotoRec/TestDisk 数据恢复工具，支持文件恢复、分区表分析与修复"

    @property
    def capabilities(self) -> list[str]:
        return ["file_recovery", "partition_analysis", "disk_repair", "deleted_file_recovery"]

    def __init__(self, photorec_path: str | None = None, testdisk_path: str | None = None):
        from server.tools_config import get_tool_path
        self._exe_path = get_tool_path("testdisk")
        if self._exe_path:
            base_dir = os.path.dirname(self._exe_path)
            self._photorec_path = photorec_path or os.path.join(base_dir, "photorec_win.exe")
            self._testdisk_path = testdisk_path or os.path.join(base_dir, "testdisk_win.exe")
        else:
            self._photorec_path = None
            self._testdisk_path = None

    def validate_input(self, params: dict) -> bool:
        command = params.get("command", "recover")
        if command == "recover":
            return "image_file" in params and "output_dir" in params
        if command == "analyze":
            return "disk" in params
        if command == "list_files":
            return True
        return False

    def _build_command(self, params: dict) -> list[str]:
        command = params.get("command", "recover")

        if command == "recover":
            image_file = params["image_file"]
            output_dir = params["output_dir"]
            file_types = params.get("file_types", "all")

            cmd = [
                self._photorec_path,
                "/d", output_dir,
                "/cmd", image_file,
                "search",
            ]

            if file_types != "all":
                # PhotoRec 支持的文件类型选项
                cmd.extend(["fileopt", file_types])

            return cmd

        elif command == "analyze":
            disk = params["disk"]
            log_file = params.get("log_file", "")
            cmd = [self._testdisk_path, "/log", "/debug"]
            if log_file:
                cmd.extend(["/log", log_file])
            cmd.extend(["/cmd", disk, "analyse"])
            return cmd

        elif command == "list_files":
            return [self._photorec_path, "/list"]

        return []

    def _parse_output(self, stdout: str, stderr: str, command: str) -> dict:
        result: dict = {
            "command": command,
            "raw_output": stdout,
        }

        if command == "recover":
            lines = stdout.strip().splitlines()
            for line in lines:
                if "files found" in line.lower() or "files saved" in line.lower():
                    result["summary"] = line.strip()
                    break

        if stderr.strip():
            result["warnings"] = stderr.strip()

        return result

    async def run(self, params: dict) -> ToolResult:
        if not self.validate_input(params):
            return ToolResult(
                success=False,
                error="参数验证失败: 请检查 image_file 和 output_dir 参数"
            )

        if not self._exe_path:
            return ToolResult(
                success=False,
                error="TestDisk 未安装，请将 testdisk_win.exe 放入 tools/testdisk/ 目录"
            )

        command = params.get("command", "recover")

        if command == "recover":
            executable = self._photorec_path
            if not os.path.isfile(executable):
                return ToolResult(
                    success=False,
                    error=f"PhotoRec 可执行文件未找到: {executable}"
                )
            image_file = params["image_file"]
            if not os.path.isfile(image_file):
                return ToolResult(
                    success=False,
                    error=f"镜像文件未找到: {image_file}"
                )
            output_dir = params["output_dir"]
            os.makedirs(output_dir, exist_ok=True)
        elif command == "analyze":
            executable = self._testdisk_path
            if not os.path.isfile(executable):
                return ToolResult(
                    success=False,
                    error=f"TestDisk 可执行文件未找到: {executable}"
                )
        else:
            executable = self._photorec_path

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
                    error=f"PhotoRec/TestDisk 执行超时（{params.get('timeout', 600)}秒）"
                )

            stdout_str = stdout.decode("utf-8", errors="replace")
            stderr_str = stderr.decode("utf-8", errors="replace")

            if proc.returncode != 0 and not stdout_str.strip():
                return ToolResult(
                    success=False,
                    error=f"PhotoRec/TestDisk 返回错误码 {proc.returncode}: {stderr_str}",
                    duration=time.perf_counter() - start,
                )

            data = self._parse_output(stdout_str, stderr_str, command)
            duration = time.perf_counter() - start
            return ToolResult(success=True, data=data, duration=duration)

        except FileNotFoundError:
            return ToolResult(
                success=False,
                error=f"PhotoRec/TestDisk 可执行文件未找到: {executable}"
            )
        except Exception as e:
            duration = time.perf_counter() - start
            return ToolResult(
                success=False,
                error=f"PhotoRec/TestDisk 执行异常: {str(e)}",
                duration=duration,
            )