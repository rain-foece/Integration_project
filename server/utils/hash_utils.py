"""SHA-256 哈希计算工具模块。"""

import hashlib
import asyncio
from pathlib import Path
from typing import Optional

import aiofiles


async def compute_sha256(file_path: str | Path, chunk_size: int = 8192) -> str:
    """异步计算文件的 SHA-256 哈希值。

    Args:
        file_path: 文件路径
        chunk_size: 每次读取的块大小（字节），默认 8KB

    Returns:
        SHA-256 哈希值的十六进制字符串

    Raises:
        FileNotFoundError: 文件不存在
        IOError: 读取文件时发生错误
    """
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


def compute_sha256_sync(file_path: str | Path, chunk_size: int = 8192) -> str:
    """同步计算文件的 SHA-256 哈希值。

    Args:
        file_path: 文件路径
        chunk_size: 每次读取的块大小（字节），默认 8KB

    Returns:
        SHA-256 哈希值的十六进制字符串
    """
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


def verify_sha256(file_path: str | Path, expected_hash: str) -> bool:
    """同步验证文件的 SHA-256 哈希值是否匹配。

    Args:
        file_path: 文件路径
        expected_hash: 预期的哈希值

    Returns:
        哈希值是否匹配
    """
    actual = compute_sha256_sync(file_path)
    return actual.lower() == expected_hash.lower()


def compute_sha256_from_bytes(data: bytes) -> str:
    """计算字节数据的 SHA-256 哈希值。

    Args:
        data: 字节数据

    Returns:
        SHA-256 哈希值的十六进制字符串
    """
    return hashlib.sha256(data).hexdigest()