"""工具适配器抽象基类模块。

定义所有电子数据取证工具的适配器接口规范。
每个具体工具适配器需要继承 BaseToolAdapter 并实现 run() 和 validate_input() 方法。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolResult:
    """工具执行结果数据类。

    Attributes:
        success: 执行是否成功
        data: 返回的数据（JSON 可序列化）
        error: 错误信息（仅失败时）
        duration: 执行耗时（秒）
    """
    success: bool
    data: Any = None
    error: str | None = None
    duration: float = 0.0


class BaseToolAdapter(ABC):
    """电子数据取证工具适配器抽象基类。

    所有工具适配器必须实现此基类中定义的抽象方法。

    使用示例:
        class MyToolAdapter(BaseToolAdapter):
            @property
            def tool_name(self) -> str:
                return "my_tool"

            @property
            def version(self) -> str:
                return "1.0.0"

            def validate_input(self, params: dict) -> bool:
                return "input_file" in params

            async def run(self, params: dict) -> ToolResult:
                # 实现工具调用逻辑
                ...
    """

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
        """验证输入参数是否合法。

        Args:
            params: 工具参数字典

        Returns:
            参数是否合法
        """
        ...

    @abstractmethod
    async def run(self, params: dict) -> ToolResult:
        """异步执行工具。

        Args:
            params: 工具参数字典

        Returns:
            ToolResult 执行结果
        """
        ...

    def get_info(self) -> dict:
        """获取工具元信息（非抽象，子类可覆盖）。"""
        return {
            "tool_name": self.tool_name,
            "version": self.version,
            "description": self.description,
            "capabilities": self.capabilities,
        }