"""工具列表/能力查询路由。"""

from fastapi import APIRouter
from server.adapters import list_registered_adapters

router = APIRouter(prefix="/tools", tags=["工具管理"])


@router.get("")
async def list_tools():
    """获取所有已注册的工具适配器列表及其元信息。

    Returns:
        {tool_name: tool_info} 字典，tool_info 包含 tool_name, version, description, capabilities
    """
    tools = list_registered_adapters()
    return {"tools": tools, "total": len(tools)}


@router.get("/{tool_name}")
async def get_tool_info(tool_name: str):
    """获取指定工具的详细信息。

    Args:
        tool_name: 工具名称

    Returns:
        工具元信息字典
    """
    from server.adapters import get_adapter

    adapter_cls = get_adapter(tool_name)
    if not adapter_cls:
        from server.routers.error_handlers import AppError
        raise AppError(
            code="TOOL_NOT_FOUND",
            message=f"工具未注册: {tool_name}",
            status_code=404,
        )

    instance = adapter_cls()
    return instance.get_info()