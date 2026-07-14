# 适配器注册表模块。

from server.adapters.base_adapter import BaseToolAdapter, ToolResult

from server.adapters.wireshark_adapter import WiresharkAdapter
from server.adapters.fiddler_adapter import FiddlerAdapter
from server.adapters.volatility_adapter import VolatilityAdapter
from server.adapters.ftk_imager_adapter import FTKImagerAdapter
from server.adapters.networkminer_adapter import NetworkMinerAdapter
from server.adapters.hashcat_adapter import HashcatAdapter
from server.adapters.john_adapter import JohnAdapter
from server.adapters.testdisk_adapter import TestDiskAdapter
from server.adapters.windbg_adapter import WinDbgAdapter
from server.adapters.process_explorer_adapter import ProcessExplorerAdapter
from server.adapters.process_monitor_adapter import ProcessMonitorAdapter
from server.adapters.exiftool_adapter import ExifToolAdapter
from server.adapters.ten_editor_adapter import TenEditorAdapter
from server.adapters.ibackupbot_adapter import IBackupBotAdapter
from server.adapters.beyond_compare_adapter import BeyondCompareAdapter
from server.adapters.debugview_adapter import DebugViewAdapter

# 适配器注册表：tool_name -> AdapterClass
_adapter_registry: dict[str, type[BaseToolAdapter]] = {}

# 网络流量分析
_adapter_registry["wireshark"] = WiresharkAdapter
_adapter_registry["fiddler"] = FiddlerAdapter
_adapter_registry["networkminer"] = NetworkMinerAdapter

# 内存取证
_adapter_registry["volatility"] = VolatilityAdapter

# 磁盘与镜像取证
_adapter_registry["ftk_imager"] = FTKImagerAdapter
_adapter_registry["testdisk"] = TestDiskAdapter

# 密码破解
_adapter_registry["hashcat"] = HashcatAdapter
_adapter_registry["john"] = JohnAdapter

# 崩溃与调试分析
_adapter_registry["windbg"] = WinDbgAdapter
_adapter_registry["debugview"] = DebugViewAdapter

# 进程监控
_adapter_registry["process_explorer"] = ProcessExplorerAdapter
_adapter_registry["process_monitor"] = ProcessMonitorAdapter

# 元数据与二进制分析
_adapter_registry["exiftool"] = ExifToolAdapter
_adapter_registry["010editor"] = TenEditorAdapter

# 移动设备取证
_adapter_registry["ibackupbot"] = IBackupBotAdapter

# 文件对比
_adapter_registry["beyond_compare"] = BeyondCompareAdapter


def register_adapter(tool_name: str, adapter_cls: type[BaseToolAdapter]) -> None:
    """注册工具适配器。"""
    _adapter_registry[tool_name] = adapter_cls


def get_adapter(tool_name: str) -> type[BaseToolAdapter] | None:
    """获取已注册的适配器类。"""
    return _adapter_registry.get(tool_name)


def list_registered_adapters() -> dict[str, dict]:
    """列出所有已注册的适配器及元信息。"""
    result = {}
    for name, cls in _adapter_registry.items():
        instance = cls()
        result[name] = instance.get_info()
    return result


__all__ = [
    "BaseToolAdapter",
    "ToolResult",
    "register_adapter",
    "get_adapter",
    "list_registered_adapters",
    "WiresharkAdapter",
    "FiddlerAdapter",
    "VolatilityAdapter",
    "FTKImagerAdapter",
    "NetworkMinerAdapter",
    "HashcatAdapter",
    "JohnAdapter",
    "TestDiskAdapter",
    "WinDbgAdapter",
    "ProcessExplorerAdapter",
    "ProcessMonitorAdapter",
    "ExifToolAdapter",
    "TenEditorAdapter",
    "IBackupBotAdapter",
    "BeyondCompareAdapter",
    "DebugViewAdapter",
]