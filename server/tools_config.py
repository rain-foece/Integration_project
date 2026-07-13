"""工具路径配置模块。

外部工具（需要安装 EXE）的路径统一从此配置读取。
默认从应用根目录的 tools/ 文件夹查找，也支持环境变量覆盖。

目录结构规则：
  开发模式:  app/tools_config.py  →  tools/ 在 forensics-platform/tools/
  打包模式:  _internal/app/tools_config.py →  tools/ 在 dist/tools/
"""

import os
import sys
from pathlib import Path


def _resolve_tools_dir() -> Path:
    """解析工具根目录，兼容开发模式与 PyInstaller 打包模式。"""
    # 1. 环境变量优先
    env_dir = os.environ.get("FORENSICS_TOOLS_DIR")
    if env_dir:
        return Path(env_dir)

    # 2. PyInstaller 打包模式：tools/ 与 exe 所在目录同级
    if getattr(sys, "frozen", False):
        # sys.executable = dist/ForensicsPlatform/ForensicsPlatform.exe
        # tools/ = dist/tools/ (exe所在目录的父目录下的tools)
        exe_dir = Path(sys.executable).resolve().parent
        return exe_dir.parent / "tools"

    # 3. 开发模式：app/../tools/
    return Path(__file__).resolve().parent.parent / "tools"


_TOOLS_DIR = _resolve_tools_dir()

# ── 外部工具路径映射 ─────────────────────────────────────────────
# 每个工具支持多个候选路径，按优先级尝试
EXTERNAL_TOOLS = {
    "fiddler": [
        _TOOLS_DIR / "Fiddler" / "Fiddler.exe",
        _TOOLS_DIR / "Fiddler" / "ExecAction.exe",
    ],
    "volatility": [
        _TOOLS_DIR / "Volatility3" / "vol.exe",
        _TOOLS_DIR / "volatility3" / "vol.exe",
        _TOOLS_DIR / "volatility" / "vol.exe",
    ],
    "windbg": [
        _TOOLS_DIR / "WinDbg" / "cdb.exe",
        _TOOLS_DIR / "WinDbg" / "windbg.exe",
    ],
    "john": [
        _TOOLS_DIR / "john" / "run" / "john.exe",
        _TOOLS_DIR / "john" / "john.exe",
    ],
    "networkminer": [
        _TOOLS_DIR / "NetworkMiner" / "NetworkMiner.exe",
    ],
    "testdisk": [
        _TOOLS_DIR / "testdisk" / "testdisk_win.exe",
        _TOOLS_DIR / "testdisk" / "photorec_win.exe",
    ],
    "hashcat_external": [
        _TOOLS_DIR / "hashcat" / "hashcat.exe",
    ],
}


def get_tool_path(tool_name: str) -> str | None:
    """获取工具的可执行文件路径。

    按优先级尝试多个候选路径，返回第一个存在的文件路径。
    如果都不存在，返回 None。

    Args:
        tool_name: 工具名称

    Returns:
        可执行文件绝对路径，或 None
    """
    candidates = EXTERNAL_TOOLS.get(tool_name, [])
    for p in candidates:
        if p.is_file():
            return str(p.resolve())
    return None


def get_tools_dir() -> Path:
    """获取工具根目录。"""
    return _TOOLS_DIR


def list_tool_status() -> dict:
    """列出所有外部工具的状态（已安装/未安装）。"""
    result = {}
    for name, paths in EXTERNAL_TOOLS.items():
        found = None
        for p in paths:
            if p.is_file():
                found = str(p.resolve())
                break
        result[name] = {
            "installed": found is not None,
            "path": found,
            "search_paths": [str(p) for p in paths],
        }
    return result