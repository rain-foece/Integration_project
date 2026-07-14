# FTK Imager 适配器（纯 Python），使用 hashlib 计算磁盘镜像哈希值。

import hashlib
import mimetypes
import os
import time
from datetime import datetime

from server.adapters.base_adapter import BaseToolAdapter, ToolResult

# 大文件分块读取大小: 64KB
_CHUNK_SIZE = 64 * 1024

# 进度报告间隔: 每处理 10MB 报告一次
_PROGRESS_INTERVAL = 10 * 1024 * 1024


def _format_size(size_bytes: int) -> str:
    """将字节数格式化为人类可读的大小字符串。"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.2f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def _guess_mime_type(file_path: str) -> str:
    """根据文件扩展名猜测 MIME 类型。"""
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type is None:
        # 检查常见磁盘镜像扩展名
        ext = os.path.splitext(file_path)[1].lower()
        disk_image_extensions = {
            ".e01": "application/x-ewf",
            ".ex01": "application/x-ewf",
            ".aff": "application/x-aff",
            ".dd": "application/octet-stream",
            ".raw": "application/octet-stream",
            ".img": "application/octet-stream",
            ".iso": "application/x-iso9660-image",
            ".vmdk": "application/x-vmdk",
            ".vhd": "application/x-vhd",
            ".vhdx": "application/x-vhdx",
            ".ad1": "application/x-ftk-image",
        }
        mime_type = disk_image_extensions.get(ext, "application/octet-stream")
    return mime_type


# 磁盘镜像哈希验证适配器，支持 verify（SHA-256/MD5/SHA-1）和 quick_hash（仅 SHA-256）。
class FTKImagerAdapter(BaseToolAdapter):

    @property
    def tool_name(self) -> str:
        return "ftk_imager"

    @property
    def version(self) -> str:
        return "2.0-pure"

    @property
    def description(self) -> str:
        return (
            "FTK Imager 磁盘镜像哈希验证工具（纯 Python 实现），"
            "支持 SHA-256/MD5/SHA-1 哈希计算、文件元信息提取，"
            "大文件分块读取（64KB 块）并显示进度"
        )

    @property
    def capabilities(self) -> list[str]:
        return ["hash_verification", "file_metadata", "disk_image_analysis", "progress_tracking"]

    def validate_input(self, params: dict) -> bool:
        """需要 file 或 file_path 参数。"""
        return "file" in params or "file_path" in params

    def _get_file_path(self, params: dict) -> str:
        """从参数中提取文件路径。"""
        return params.get("file", params.get("file_path", ""))

    def _compute_hashes(self, file_path: str, algorithms: list[str],
                        report_progress: bool = False) -> dict:
        """分块读取文件并计算哈希值。report_progress 为 True 时生成进度报告。"""
        # 初始化所有哈希对象
        hashers = {}
        for algo in algorithms:
            hashers[algo] = hashlib.new(algo)

        file_size = os.path.getsize(file_path)
        bytes_read = 0
        progress_reports = []

        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(_CHUNK_SIZE)
                if not chunk:
                    break

                for hasher in hashers.values():
                    hasher.update(chunk)

                bytes_read += len(chunk)

                if report_progress:
                    last_report = bytes_read - len(chunk)
                    current_milestone = (bytes_read // _PROGRESS_INTERVAL) * _PROGRESS_INTERVAL
                    last_milestone = (last_report // _PROGRESS_INTERVAL) * _PROGRESS_INTERVAL

                    if current_milestone > last_milestone or bytes_read == file_size:
                        percent = round(bytes_read / file_size * 100, 2)
                        progress_reports.append({
                            "bytes_read": bytes_read,
                            "size_readable": _format_size(bytes_read),
                            "total_size": file_size,
                            "total_readable": _format_size(file_size),
                            "percent": percent,
                        })

        result = {
            "file_size_bytes": file_size,
            "file_size_readable": _format_size(file_size),
            "chunk_size": _CHUNK_SIZE,
            "chunks_processed": (file_size + _CHUNK_SIZE - 1) // _CHUNK_SIZE if file_size > 0 else 0,
        }

        for algo, hasher in hashers.items():
            result[algo] = hasher.hexdigest()

        if report_progress:
            result["progress_reports"] = progress_reports

        return result

    def _get_file_metadata(self, file_path: str) -> dict:
        """获取文件的修改时间、MIME 类型等元信息。"""
        stat = os.stat(file_path)

        mtime = datetime.fromtimestamp(stat.st_mtime)
        ctime = datetime.fromtimestamp(stat.st_ctime)

        mime_type = _guess_mime_type(file_path)

        return {
            "file_name": os.path.basename(file_path),
            "file_path": os.path.abspath(file_path),
            "file_extension": os.path.splitext(file_path)[1].lower(),
            "mime_type": mime_type,
            "size_bytes": stat.st_size,
            "size_readable": _format_size(stat.st_size),
            "last_modified": mtime.isoformat(),
            "last_modified_timestamp": stat.st_mtime,
            "created": ctime.isoformat(),
            "created_timestamp": stat.st_ctime,
            "is_file": os.path.isfile(file_path),
            "is_directory": os.path.isdir(file_path),
        }

    async def run(self, params: dict) -> ToolResult:
        """执行哈希验证。需 file/file_path，可选 action: verify/quick_hash。"""
        if not self.validate_input(params):
            return ToolResult(
                success=False,
                error="参数验证失败: 需要提供 file 或 file_path 参数"
            )

        file_path = self._get_file_path(params)
        action = params.get("action", "verify")
        show_progress = params.get("show_progress", True)

        # 验证文件存在
        if not os.path.exists(file_path):
            return ToolResult(
                success=False,
                error=f"文件未找到: {file_path}"
            )

        if not os.path.isfile(file_path):
            return ToolResult(
                success=False,
                error=f"路径不是文件: {file_path}"
            )

        start = time.perf_counter()

        try:
            file_size = os.path.getsize(file_path)

            if action == "quick_hash":
                # 仅计算 SHA-256
                hash_results = self._compute_hashes(
                    file_path,
                    algorithms=["sha256"],
                    report_progress=show_progress,
                )

                data = {
                    "action": "quick_hash",
                    "sha256": hash_results["sha256"],
                    "file_size_bytes": hash_results["file_size_bytes"],
                    "file_size_readable": hash_results["file_size_readable"],
                    "chunk_size": hash_results["chunk_size"],
                    "chunks_processed": hash_results["chunks_processed"],
                }
            else:
                # action == "verify" (默认): 计算所有哈希
                hash_results = self._compute_hashes(
                    file_path,
                    algorithms=["sha256", "md5", "sha1"],
                    report_progress=show_progress,
                )
                metadata = self._get_file_metadata(file_path)

                data = {
                    "action": "verify",
                    "sha256": hash_results["sha256"],
                    "md5": hash_results["md5"],
                    "sha1": hash_results["sha1"],
                    "file_size_bytes": hash_results["file_size_bytes"],
                    "file_size_readable": hash_results["file_size_readable"],
                    "chunk_size": hash_results["chunk_size"],
                    "chunks_processed": hash_results["chunks_processed"],
                    "metadata": metadata,
                }

            if show_progress and "progress_reports" in hash_results:
                data["progress_reports"] = hash_results["progress_reports"]

            duration = time.perf_counter() - start
            throughput = file_size / duration / (1024 * 1024) if duration > 0 else 0
            data["duration_seconds"] = round(duration, 3)
            data["throughput_mbps"] = round(throughput, 2)

            return ToolResult(success=True, data=data, duration=duration)

        except PermissionError as e:
            return ToolResult(
                success=False,
                error=f"文件读取权限不足: {str(e)}",
                duration=time.perf_counter() - start,
            )
        except OSError as e:
            return ToolResult(
                success=False,
                error=f"文件 I/O 错误: {str(e)}",
                duration=time.perf_counter() - start,
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"哈希验证执行异常: {str(e)}",
                duration=time.perf_counter() - start,
            )