# ExifTool 适配器（纯 Python 实现），使用内置模块提取文件元数据、哈希、PE 信息等。

import hashlib
import mimetypes
import os
import struct
import time
from datetime import datetime, timezone, timedelta

from server.adapters.base_adapter import BaseToolAdapter, ToolResult


# 元数据提取适配器，支持通用文件/图片/PE 元数据提取。
class ExifToolAdapter(BaseToolAdapter):

    @property
    def tool_name(self) -> str:
        return "exiftool"

    @property
    def version(self) -> str:
        return "1.0-pure"

    @property
    def description(self) -> str:
        return "ExifTool 元数据提取与分析 — 纯 Python 实现，支持 PE/图片/文件通用元数据提取"

    @property
    def capabilities(self) -> list[str]:
        return ["metadata_extraction", "file_analysis", "hash_computation", "pe_analysis"]

    def validate_input(self, params: dict) -> bool:
        return "file" in params

    async def run(self, params: dict) -> ToolResult:
        if not self.validate_input(params):
            return ToolResult(success=False, error="参数验证失败: 请提供 file 参数")

        file_path = params["file"]
        if not os.path.isfile(file_path):
            return ToolResult(success=False, error=f"文件未找到: {file_path}")

        start = time.perf_counter()
        try:
            metadata = self._extract_all(file_path)
            duration = time.perf_counter() - start
            return ToolResult(
                success=True,
                data={
                    "file": file_path,
                    "metadata": metadata,
                    "fields_extracted": len(metadata),
                },
                duration=duration,
            )
        except Exception as e:
            duration = time.perf_counter() - start
            return ToolResult(success=False, error=str(e), duration=duration)

    def _extract_all(self, file_path: str) -> dict:
        """提取文件的所有元数据。"""
        stat = os.stat(file_path)
        meta = {}

        # 通用文件信息
        meta["FileName"] = os.path.basename(file_path)
        meta["FileSize"] = stat.st_size
        meta["FileSizeHR"] = self._format_size(stat.st_size)
        meta["FileModifyDate"] = datetime.fromtimestamp(stat.st_mtime, tz=timezone(timedelta(hours=8))).isoformat()
        meta["FileAccessDate"] = datetime.fromtimestamp(stat.st_atime, tz=timezone(timedelta(hours=8))).isoformat()
        meta["FileCreateDate"] = datetime.fromtimestamp(stat.st_ctime, tz=timezone(timedelta(hours=8))).isoformat()

        # MIME 类型
        mime_type, _ = mimetypes.guess_type(file_path)
        meta["MIMEType"] = mime_type or "application/octet-stream"

        # 扩展名
        _, ext = os.path.splitext(file_path)
        meta["FileTypeExtension"] = ext.lower() if ext else ""

        # 哈希值
        with open(file_path, "rb") as f:
            # SHA-256
            sha256 = hashlib.sha256()
            buf = f.read(65536)
            while buf:
                sha256.update(buf)
                buf = f.read(65536)
            meta["SHA256"] = sha256.hexdigest()

            # MD5
            f.seek(0)
            md5 = hashlib.md5()
            buf = f.read(65536)
            while buf:
                md5.update(buf)
                buf = f.read(65536)
            meta["MD5"] = md5.hexdigest()

            # 读取文件头（前 256 字节）
            f.seek(0)
            header = f.read(256)
            meta["FileHeader"] = header[:64].hex()
            magic = header[:16]
            meta["MagicBytes"] = magic.hex()
            meta["MagicString"] = "".join(chr(b) if 32 <= b < 127 else "." for b in magic[:8])

        # 根据文件类型提取特定元数据
        if mime_type:
            if mime_type.startswith("image/"):
                self._extract_image_meta(file_path, meta)
            elif ext and ext.lower() in (".exe", ".dll", ".sys", ".ocx", ".scr"):
                self._extract_pe_meta(file_path, meta)

        return meta

    def _extract_image_meta(self, file_path: str, meta: dict):
        """提取图片尺寸等元数据。"""
        try:
            with open(file_path, "rb") as f:
                header = f.read(32)
                # PNG
                if header[:8] == b"\x89PNG\r\n\x1a\n":
                    meta["ImageFormat"] = "PNG"
                    width, height = struct.unpack(">II", f.read(8))
                    meta["ImageWidth"] = width
                    meta["ImageHeight"] = height
                # JPEG
                elif header[:2] == b"\xff\xd8":
                    meta["ImageFormat"] = "JPEG"
                    self._parse_jpeg(file_path, meta)
                # GIF
                elif header[:6] in (b"GIF87a", b"GIF89a"):
                    meta["ImageFormat"] = "GIF"
                    width, height = struct.unpack("<HH", header[6:10])
                    meta["ImageWidth"] = width
                    meta["ImageHeight"] = height
                # BMP
                elif header[:2] == b"BM":
                    meta["ImageFormat"] = "BMP"
                    width, height = struct.unpack("<II", header[18:26])
                    meta["ImageWidth"] = width
                    meta["ImageHeight"] = abs(height)
        except Exception:
            pass

    def _parse_jpeg(self, file_path: str, meta: dict):
        """解析 JPEG 尺寸。"""
        try:
            with open(file_path, "rb") as f:
                f.seek(2)
                while True:
                    marker = f.read(2)
                    if len(marker) < 2 or marker[0] != 0xFF:
                        break
                    if marker[1] in (0xD8, 0xD9):
                        continue
                    length_data = f.read(2)
                    if len(length_data) < 2:
                        break
                    length = struct.unpack(">H", length_data)[0]
                    if marker[1] >= 0xC0 and marker[1] <= 0xC2:
                        sof = f.read(7)
                        if len(sof) >= 7:
                            height, width = struct.unpack(">HH", sof[1:5])
                            meta["ImageWidth"] = width
                            meta["ImageHeight"] = height
                            return
                    f.seek(length - 2, 1)
        except Exception:
            pass

    def _extract_pe_meta(self, file_path: str, meta: dict):
        """提取 PE 文件元数据。"""
        try:
            with open(file_path, "rb") as f:
                # DOS header
                dos_header = f.read(64)
                if dos_header[:2] != b"MZ":
                    return
                meta["FileFormat"] = "PE"
                pe_offset = struct.unpack("<I", dos_header[60:64])[0]

                # PE signature
                f.seek(pe_offset)
                pe_sig = f.read(4)
                if pe_sig != b"PE\0\0":
                    return

                # COFF header
                coff = f.read(20)
                machine = struct.unpack("<H", coff[0:2])[0]
                num_sections = struct.unpack("<H", coff[2:4])[0]
                timestamp = struct.unpack("<I", coff[4:8])[0]
                opt_header_size = struct.unpack("<H", coff[16:18])[0]

                machine_types = {
                    0x014C: "x86", 0x8664: "x64", 0x0200: "IA64",
                    0x01C4: "ARM", 0xAA64: "ARM64",
                }
                meta["MachineType"] = machine_types.get(machine, f"0x{machine:04X}")
                meta["NumberOfSections"] = num_sections
                if timestamp:
                    meta["PETimestamp"] = datetime.fromtimestamp(timestamp, tz=timezone(timedelta(hours=8))).isoformat()

                # Optional header
                opt = f.read(opt_header_size)
                if len(opt) >= 68:
                    magic = struct.unpack("<H", opt[0:2])[0]
                    meta["PEMagic"] = "PE32" if magic == 0x10B else "PE32+" if magic == 0x20B else f"0x{magic:04X}"
                    meta["EntryPoint"] = struct.unpack("<I", opt[16:20])[0]
                    if magic == 0x20B:  # PE32+
                        meta["ImageBase"] = struct.unpack("<Q", opt[24:32])[0]
                    else:
                        meta["ImageBase"] = struct.unpack("<I", opt[28:32])[0]
        except Exception:
            pass

    @staticmethod
    def _format_size(size: int) -> str:
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"
