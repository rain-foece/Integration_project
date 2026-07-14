# John the Ripper 适配器，通过 subprocess 调用 John 进行密码哈希破解。

import asyncio
import os
import time

from server.adapters.base_adapter import BaseToolAdapter, ToolResult

# 常用格式映射
_FORMATS = {
    "raw-md5": "Raw-MD5",
    "raw-sha1": "Raw-SHA1",
    "raw-sha256": "Raw-SHA256",
    "raw-sha512": "Raw-SHA512",
    "nt": "NT",
    "ntlm": "NT",
    "lm": "LM",
    "descrypt": "descrypt",
    "bsdicrypt": "bsdicrypt",
    "md5crypt": "md5crypt",
    "bcrypt": "bcrypt",
    "sha512crypt": "sha512crypt",
    "sha256crypt": "sha256crypt",
    "wpapsk": "wpapsk",
    "wpa-psk": "wpapsk",
    "krb5": "krb5",
    "krb5tgs": "krb5tgs",
    "mysql": "mysql",
    "oracle": "oracle",
    "zip": "zip",
    "rar": "rar",
    "rar5": "rar5",
    "pdf": "pdf",
    "office": "office",
    "bitcoin": "bitcoin",
    "ethereum": "ethereum",
}


# John the Ripper 密码破解适配器，支持 crack/show/test/list_formats。
class JohnAdapter(BaseToolAdapter):

    @property
    def tool_name(self) -> str:
        return "john"

    @property
    def version(self) -> str:
        return "2.0-pure"

    @property
    def description(self) -> str:
        return "John the Ripper 密码破解工具，支持多种哈希格式和攻击模式"

    @property
    def capabilities(self) -> list[str]:
        return ["hash_cracking", "hash_identification", "format_detection", "benchmark"]

    def __init__(self, john_path: str | None = None):
        from server.tools_config import get_tool_path
        self._exe_path = john_path or get_tool_path("john")

    def validate_input(self, params: dict) -> bool:
        command = params.get("command", "crack")
        if command == "crack":
            return "hash_file" in params
        if command == "show":
            return "hash_file" in params
        if command == "test":
            return True
        if command == "list_formats":
            return True
        return False

    def _resolve_format(self, fmt: str) -> str:
        """解析格式名称。"""
        return _FORMATS.get(fmt.lower(), fmt)

    def _build_command(self, params: dict) -> list[str]:
        command = params.get("command", "crack")
        cmd = [self._exe_path]

        if command == "crack":
            hash_file = params["hash_file"]
            hash_format = params.get("hash_format", "")

            if hash_format:
                fmt = self._resolve_format(hash_format)
                cmd.extend(["--format=" + fmt])

            wordlist = params.get("wordlist", "")
            if wordlist:
                cmd.extend(["--wordlist=" + wordlist])

            rules = params.get("rules", "")
            if rules:
                cmd.extend(["--rules=" + rules])

            incremental = params.get("incremental", "")
            if incremental:
                cmd.extend(["--incremental=" + incremental])

            session = params.get("session", "")
            if session:
                cmd.extend(["--session=" + session])

            restore = params.get("restore", "")
            if restore:
                cmd.extend(["--restore=" + restore])

            cmd.append(hash_file)

        elif command == "show":
            hash_file = params["hash_file"]
            hash_format = params.get("hash_format", "")
            if hash_format:
                cmd.extend(["--format=" + self._resolve_format(hash_format)])
            cmd.extend(["--show", hash_file])

        elif command == "test":
            hash_format = params.get("hash_format", "")
            if hash_format:
                cmd.extend(["--test", "--format=" + self._resolve_format(hash_format)])
            else:
                cmd.append("--test")

        elif command == "list_formats":
            cmd.append("--list=formats")

        return cmd

    def _parse_output(self, stdout: str, stderr: str, command: str) -> dict:
        result: dict = {
            "command": command,
            "raw_output": stdout,
        }

        if command == "crack":
            lines = stdout.strip().splitlines()
            cracked = []
            for line in lines:
                if ":" in line and "password" not in line.lower() and not line.startswith(("Loaded", "Using", "Will", "Press", "Proceeding", "Warning", "Note:", "guesses:")):
                    cracked.append(line.strip())
            result["cracked_count"] = len(cracked)
            result["cracked_passwords"] = cracked

            for line in lines:
                if "guesses:" in line.lower():
                    result["stats"] = line.strip()
                    break

        elif command == "show":
            lines = stdout.strip().splitlines()
            result["results"] = [l for l in lines if ":" in l]
            result["count"] = len(result["results"])

        elif command == "list_formats":
            result["formats"] = [l.strip() for l in stdout.strip().splitlines() if l.strip()]

        if stderr.strip():
            result["warnings"] = stderr.strip()

        return result

    async def run(self, params: dict) -> ToolResult:
        if not self.validate_input(params):
            return ToolResult(
                success=False,
                error="参数验证失败: 请检查 hash_file 参数"
            )

        if not self._exe_path:
            return ToolResult(
                success=False,
                error="John the Ripper 未安装，请将 john.exe 放入 tools/john/run/ 目录"
            )

        if not os.path.isfile(self._exe_path):
            return ToolResult(
                success=False,
                error=f"John the Ripper 可执行文件未找到: {self._exe_path}"
            )

        command = params.get("command", "crack")
        if command in ("crack", "show"):
            hash_file = params["hash_file"]
            if not os.path.isfile(hash_file):
                return ToolResult(
                    success=False,
                    error=f"哈希文件未找到: {hash_file}"
                )
            wordlist = params.get("wordlist", "")
            if wordlist and not os.path.isfile(wordlist):
                return ToolResult(
                    success=False,
                    error=f"字典文件未找到: {wordlist}"
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
                    error=f"John the Ripper 执行超时（{params.get('timeout', 600)}秒）"
                )

            stdout_str = stdout.decode("utf-8", errors="replace")
            stderr_str = stderr.decode("utf-8", errors="replace")

            if proc.returncode != 0 and not stdout_str.strip():
                return ToolResult(
                    success=False,
                    error=f"John the Ripper 返回错误码 {proc.returncode}: {stderr_str}",
                    duration=time.perf_counter() - start,
                )

            data = self._parse_output(stdout_str, stderr_str, command)
            duration = time.perf_counter() - start
            return ToolResult(success=True, data=data, duration=duration)

        except FileNotFoundError:
            return ToolResult(
                success=False,
                error=f"John the Ripper 可执行文件未找到: {self._exe_path}"
            )
        except Exception as e:
            duration = time.perf_counter() - start
            return ToolResult(
                success=False,
                error=f"John the Ripper 执行异常: {str(e)}",
                duration=duration,
            )