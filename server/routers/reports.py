# 报告生成/查看路由

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from pathlib import Path

from server.models import get_db
from server.services import report_service
from server.routers.error_handlers import AppError

router = APIRouter(prefix="/reports", tags=["报告管理"])


# 创建报告请求
class ReportCreateRequest(BaseModel):
    case_id: int = Field(...)
    title: str = Field(..., min_length=1, max_length=512)
    content: dict | None = Field(None)


# 报告响应
class ReportResponse(BaseModel):
    id: int
    case_id: int
    title: str
    content: dict | None
    html_path: str | None
    pdf_path: str | None
    created_at: str

    class Config:
        from_attributes = True


# 报告列表响应
class ReportListResponse(BaseModel):
    items: list[ReportResponse]
    total: int
    skip: int
    limit: int


# 创建报告
@router.post("", response_model=ReportResponse, status_code=201)
async def create_report(
    body: ReportCreateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    try:
        report = await report_service.create_report(
            db=db,
            case_id=body.case_id,
            title=body.title,
            content=body.content,
            operator=_get_client_ip(request),
            ip_address=_get_client_ip(request),
        )
        return _report_to_response(report)
    except ValueError as e:
        raise AppError(code="REPORT_CREATE_ERROR", message=str(e), status_code=400)


# 获取报告列表（分页）
@router.get("", response_model=ReportListResponse)
async def list_reports(
    case_id: int | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    reports, total = await report_service.list_reports(
        db=db, case_id=case_id, skip=skip, limit=limit
    )
    return ReportListResponse(
        items=[_report_to_response(r) for r in reports],
        total=total,
        skip=skip,
        limit=limit,
    )


# 获取单个报告详情
@router.get("/{report_id}", response_model=ReportResponse)
async def get_report(
    report_id: int,
    db: AsyncSession = Depends(get_db),
):
    report = await report_service.get_report(db=db, report_id=report_id)
    if not report:
        raise AppError(code="REPORT_NOT_FOUND", message=f"报告不存在: report_id={report_id}", status_code=404)
    return _report_to_response(report)


# 为报告生成 HTML 文件
@router.post("/{report_id}/generate-html")
async def generate_html_report(
    report_id: int,
    db: AsyncSession = Depends(get_db),
):
    report = await report_service.generate_report_html(db=db, report_id=report_id)
    if not report:
        raise AppError(code="REPORT_NOT_FOUND", message=f"报告不存在: report_id={report_id}", status_code=404)
    return {"message": "HTML 报告已生成", "html_path": report.html_path}


# 为报告生成 PDF 文件
@router.post("/{report_id}/generate-pdf")
async def generate_pdf_report(
    report_id: int,
    db: AsyncSession = Depends(get_db),
):
    report = await report_service.generate_report_pdf(db=db, report_id=report_id)
    if not report:
        raise AppError(code="REPORT_NOT_FOUND", message=f"报告不存在: report_id={report_id}", status_code=404)
    return {"message": "PDF 报告路径已设置", "pdf_path": report.pdf_path}


# 在线查看报告 HTML
@router.get("/{report_id}/view")
async def view_report_html(
    report_id: int,
    db: AsyncSession = Depends(get_db),
):
    report = await report_service.get_report(db=db, report_id=report_id)
    if not report:
        raise AppError(code="REPORT_NOT_FOUND", message=f"报告不存在: report_id={report_id}", status_code=404)

    if not report.html_path:
        # 自动生成 HTML
        report = await report_service.generate_report_html(db=db, report_id=report_id)
        if not report or not report.html_path:
            raise AppError(code="REPORT_GENERATE_ERROR", message="无法生成 HTML 报告", status_code=500)

    html_path = Path(report.html_path)
    if not html_path.exists():
        raise AppError(code="HTML_FILE_NOT_FOUND", message=f"HTML 文件不存在: {report.html_path}", status_code=404)

    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


# 下载 HTML 报告文件
@router.get("/{report_id}/download-html")
async def download_report_html(
    report_id: int,
    db: AsyncSession = Depends(get_db),
):
    report = await report_service.get_report(db=db, report_id=report_id)
    if not report:
        raise AppError(code="REPORT_NOT_FOUND", message=f"报告不存在: report_id={report_id}", status_code=404)

    if not report.html_path:
        report = await report_service.generate_report_html(db=db, report_id=report_id)
        if not report or not report.html_path:
            raise AppError(code="REPORT_GENERATE_ERROR", message="无法生成 HTML 报告", status_code=500)

    html_path = Path(report.html_path)
    if not html_path.exists():
        raise AppError(code="HTML_FILE_NOT_FOUND", message=f"HTML 文件不存在: {report.html_path}", status_code=404)

    return FileResponse(
        path=str(html_path),
        filename=f"report_{report.id}.html",
        media_type="text/html",
    )


def _report_to_response(report) -> ReportResponse:
    return ReportResponse(
        id=report.id,
        case_id=report.case_id,
        title=report.title,
        content=report.content,
        html_path=report.html_path,
        pdf_path=report.pdf_path,
        created_at=report.created_at.isoformat() if report.created_at else "",
    )


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
