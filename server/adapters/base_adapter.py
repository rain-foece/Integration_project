# 工具适配器抽象基类模块。

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


# 工具执行结果数据类。
@dataclass
class ToolResult:
    success: bool
    data: Any = None
    error: str | None = None
    duration: float = 0.0


# 工具适配器抽象基类，所有适配器需继承并实现抽象方法。
class BaseToolAdapter(ABC):

    @property
    @abstractmethod
    def tool_name(self) -> str:
        """工具唯一标识名称。"""
        ...

    @property
    @abstractmethod
    def version(self) -> str:
        """工具版本号。"""
        ...

    @property
    def description(self) -> str:
        """工具描述。子类可覆盖。"""
        return ""

    @property
    def capabilities(self) -> list[str]:
        """工具能力列表。子类可覆盖。"""
        return []

    @abstractmethod
    def validate_input(self, params: dict) -> bool:
        """验证输入参数是否合法。"""
        ...

    @abstractmethod
    async def run(self, params: dict) -> ToolResult:
        """异步执行工具。"""
        ...

    def get_info(self) -> dict:
        """获取工具元信息（非抽象，子类可覆盖）。"""
        return {
            "tool_name": self.tool_name,
            "version": self.version,
            "description": self.description,
            "capabilities": self.capabilities,
        }