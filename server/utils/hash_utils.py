# SHA-256 哈希计算工具模块

import hashlib
import asyncio
from pathlib import Path
from typing import Optional

import aiofiles


# 异步计算文件的 SHA-256 哈希值
async def compute_sha256(file_path: str | Path, chunk_size: int = 8192) -> str:
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")
    if not file_path.is_file():
        raise ValueError(f"路径不是文件: {file_path}")

    sha256 = hashlib.sha256()
    async with aiofiles.open(file_path, "rb") as f:
        while True:
            chunk = await f.read(chunk_size)
            if not chunk:
                break
            sha256.update(chunk)
    return sha256.hexdigest()


# 同步计算文件的 SHA-256 哈希值
def compute_sha256_sync(file_path: str | Path, chunk_size: int = 8192) -> str:
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")
    if not file_path.is_file():
        raise ValueError(f"路径不是文件: {file_path}")

    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            sha256.update(chunk)
    return sha256.hexdigest()


# 同步验证文件的 SHA-256 哈希值是否匹配
def verify_sha256(file_path: str | Path, expected_hash: str) -> bool:
    actual = compute_sha256_sync(file_path)
    return actual.lower() == expected_hash.lower()


# 计算字节数据的 SHA-256 哈希值
def compute_sha256_from_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
