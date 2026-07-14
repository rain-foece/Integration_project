# 工具列表/能力查询路由

from fastapi import APIRouter
from server.adapters import list_registered_adapters

router = APIRouter(prefix="/tools", tags=["工具管理"])


# 获取所有已注册的工具适配器列表及其元信息
@router.get("")
async def list_tools():
    tools = list_registered_adapters()
    return {"tools": tools, "total": len(tools)}


# 获取指定工具的详细信息
@router.get("/{tool_name}")
async def get_tool_info(tool_name: str):
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
