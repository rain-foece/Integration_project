# 010 Editor 纯 Python 十六进制查看适配器，零外部依赖。

from __future__ import annotations

import hashlib
import os
import struct
import time
from datetime import datetime, timezone

from server.adapters.base_adapter import BaseToolAdapter, ToolResult

# 常见文件类型头字节签名: (偏移量, 十六进制字节序列, 描述)
_MAGIC_SIGNATURES: list[tuple[int, bytes, str]] = [
    # 图片
    (0, b"\xFF\xD8\xFF", "JPEG image"),
    (0, b"\x89PNG\r\n\x1A\n", "PNG image"),
    (0, b"GIF87a", "GIF image (87a)"),
    (0, b"GIF89a", "GIF image (89a)"),
    (0, b"BM", "BMP image"),
    (0, b"II*\x00", "TIFF image (little-endian)"),
    (0, b"MM\x00*", "TIFF image (big-endian)"),
    (0, b"\x00\x00\x01\x00", "ICO icon"),
    (0, b"RIFF", "RIFF container (possible AVI/WAV/WEBP)"),
    (8, b"WEBP", "WEBP image"),

    # 音频 / 视频
    (0, b"ID3", "MP3 audio (ID3 tag)"),
    (0, b"\xFF\xFB", "MP3 audio"),
    (0, b"\xFF\xF3", "MP3 audio"),
    (0, b"\xFF\xF2", "MP3 audio"),
    (0, b"fLaC", "FLAC audio"),
    (0, b"OggS", "OGG container"),
    (0, b"\x1A\x45\xDF\xA3", "Matroska (MKV/MKA/MKS)"),
    (0, b"\x00\x00\x01\xBA", "MPEG-PS video"),
    (0, b"\x00\x00\x01\xB3", "MPEG video"),

    # 文档
    (0, b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1", "OLE2 compound document (DOC/XLS/PPT/MSI)"),
    (0, b"PK\x03\x04", "ZIP archive (DOCX/XLSX/PPTX/JAR/APK)"),
    (0, b"PK\x05\x06", "ZIP archive (empty)"),
    (0, b"PK\x07\x08", "ZIP archive (spanned)"),
    (0, b"%PDF", "PDF document"),
    (0, b"\x7FELF", "ELF executable"),
    (0, b"MZ", "DOS/PE executable (EXE/DLL)"),
    (0, b"\xFE\xED\xFA\xCE", "Mach-O 32-bit"),
    (0, b"\xFE\xED\xFA\xCF", "Mach-O 64-bit"),
    (0, b"\xCE\xFA\xED\xFE", "Mach-O 32-bit (reverse)"),
    (0, b"\xCF\xFA\xED\xFE", "Mach-O 64-bit (reverse)"),
    (0, b"\xCA\xFE\xBA\xBE", "Mach-O universal binary"),

    # 压缩 / 归档
    (0, b"\x1F\x8B", "GZIP archive"),
    (0, b"BZh", "BZIP2 archive"),
    (0, b"\xFD7zXZ\x00", "XZ archive"),
    (0, b"Rar!\x1A\x07\x00", "RAR archive (v1.5)"),
    (0, b"Rar!\x1A\x07\x01\x00", "RAR archive (v5.0)"),
    (0, b"7z\xBC\xAF\x27\x1C", "7-Zip archive"),

    # 数据库
    (0, b"SQLite format 3\x00", "SQLite database"),

    # 其他
    (0, b"\x25\x50\x44\x46", "PDF document (ASCII)"),
    (0, b"\x1B\x4C\x4A", "LJ (HP) printer file"),
    (0, b"\x00\x00\x00\x0C\x6A\x50\x20\x20", "JPEG 2000"),
    (0, b"\xFF\x4F\xFF\x51", "JPEG 2000 (codestream)"),
]


# 根据文件头字节识别文件类型。
def _identify_magic(file_bytes: bytes) -> list[dict]:
    matches: list[dict] = []
    for offset, signature, description in _MAGIC_SIGNATURES:
        end = offset + len(signature)
        if len(file_bytes) >= end and file_bytes[offset:end] == signature:
            matches.append({
                "offset": offset,
                "hex": signature.hex(" ").upper(),
                "description": description,
            })
    return matches


def _format_hex_line(offset: int, chunk: bytes) -> dict:
    """格式化单行十六进制输出。"""
    hex_str = " ".join(f"{b:02X}" for b in chunk)
    ascii_str = "".join(chr(b) if 32 <= b <= 126 else "." for b in chunk)
    return {
        "offset": f"0x{offset:08X}",
        "hex": hex_str,
        "ascii": ascii_str,
    }


def _compute_hashes(file_path: str) -> dict[str, str]:
    """计算文件的 MD5、SHA1、SHA256 哈希值。"""
    md5 = hashlib.md5()
    sha1 = hashlib.sha1()
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            md5.update(chunk)
            sha1.update(chunk)
            sha256.update(chunk)
    return {
        "md5": md5.hexdigest(),
        "sha1": sha1.hexdigest(),
        "sha256": sha256.hexdigest(),
    }


# 纯 Python 十六进制查看器，支持 hex_view / file_stats / magic_analysis。
class TenEditorAdapter(BaseToolAdapter):

    # 元属性

    @property
    def tool_name(self) -> str:
        return "010editor"

    @property
    def version(self) -> str:
        return "2.0-pure"

    @property
    def description(self) -> str:
        return "纯 Python 十六进制查看器，零依赖，支持十六进制预览、文件统计与魔数分析"

    @property
    def capabilities(self) -> list[str]:
        return ["hex_view", "file_stats", "magic_analysis"]

    def validate_input(self, params: dict) -> bool:
        """验证 command 和 file_path/file 参数。"""
        command = params.get("command", "hex_view")
        file_path = params.get("file_path") or params.get("file")
        if not file_path:
            return False
        if command not in ("hex_view", "file_stats", "magic_analysis"):
            return False
        return True

    def _resolve_path(self, params: dict) -> str:
        """从 params 中解析文件路径，优先使用 file_path。"""
        return params.get("file_path") or params.get("file", "")

    def _do_hex_view(self, file_path: str, params: dict) -> dict:
        """分块显示十六进制 + ASCII 预览。"""
        file_size = os.path.getsize(file_path)
        offset = int(params.get("offset", 0))
        max_bytes = int(params.get("max_bytes", min(4096, file_size - offset)))

        lines: list[dict] = []
        bytes_read = 0
        with open(file_path, "rb") as f:
            f.seek(offset)
            while bytes_read < max_bytes:
                remaining = max_bytes - bytes_read
                chunk_size = min(16, remaining)
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                lines.append(_format_hex_line(offset + bytes_read, chunk))
                bytes_read += len(chunk)

        return {
            "command": "hex_view",
            "file_path": file_path,
            "file_size": file_size,
            "offset": offset,
            "max_bytes": max_bytes,
            "bytes_read": bytes_read,
            "lines": lines,
        }

    def _do_file_stats(self, file_path: str, params: dict) -> dict:
        """输出文件大小、修改时间、哈希、魔数。"""
        stat = os.stat(file_path)
        mtime_dt = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)

        hashes = _compute_hashes(file_path)

        with open(file_path, "rb") as f:
            header = f.read(64)

        magic_matches = _identify_magic(header)
        magic_hex = header[:16].hex(" ").upper()

        return {
            "command": "file_stats",
            "file_path": file_path,
            "file_size": stat.st_size,
            "modified_time": mtime_dt.isoformat(),
            "modified_timestamp": stat.st_mtime,
            "hashes": hashes,
            "magic_header": magic_hex,
            "magic_matches": magic_matches,
        }

    # 根据文件头魔数识别文件类型。
    def _do_magic_analysis(self, file_path: str, params: dict) -> dict:
        with open(file_path, "rb") as f:
            header = f.read(64)

        matches = _identify_magic(header)
        identified = matches[0]["description"] if matches else "Unknown"

        return {
            "command": "magic_analysis",
            "file_path": file_path,
            "header_hex": header[:64].hex(" ").upper(),
            "identified_type": identified,
            "all_matches": matches,
        }

    async def run(self, params: dict) -> ToolResult:
        """异步执行。command: hex_view/file_stats/magic_analysis，需 file_path/file。"""
        if not self.validate_input(params):
            return ToolResult(
                success=False,
                error="参数验证失败: 请提供 command 和 file_path (或 file) 参数",
            )

        file_path = self._resolve_path(params)
        if not os.path.isfile(file_path):
            return ToolResult(
                success=False,
                error=f"文件未找到: {file_path}",
            )

        command = params.get("command", "hex_view")
        start = time.perf_counter()

        try:
            if command == "hex_view":
                data = self._do_hex_view(file_path, params)
            elif command == "file_stats":
                data = self._do_file_stats(file_path, params)
            elif command == "magic_analysis":
                data = self._do_magic_analysis(file_path, params)
            else:
                return ToolResult(
                    success=False,
                    error=f"不支持的命令: {command}",
                )

            duration = time.perf_counter() - start
            return ToolResult(success=True, data=data, duration=duration)

        except PermissionError:
            return ToolResult(
                success=False,
                error=f"权限不足，无法读取文件: {file_path}",
            )
        except OSError as e:
            return ToolResult(
                success=False,
                error=f"文件读取错误: {e}",
            )
        except Exception as e:
            duration = time.perf_counter() - start
            return ToolResult(
                success=False,
                error=f"执行异常: {e}",
                duration=duration,
            )