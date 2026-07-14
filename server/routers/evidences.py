# 证据上传/下载/哈希校验路由

import os
from pathlib import Path
from fastapi import APIRouter, Depends, UploadFile, File, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from server.models import get_db, Evidence
from server.models.audit_log import AuditLog
from server.config import settings, get_storage_paths
from server.utils.hash_utils import compute_sha256, verify_sha256
from server.routers.error_handlers import AppError
from server.services.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/evidences", tags=["证据管理"])


# 证据响应
class EvidenceResponse(BaseModel):
    id: int
    case_id: int
    name: str
    file_path: str
    file_type: str
    sha256_hash: str
    file_size: int
    created_at: str

    class Config:
        from_attributes = True


# 证据列表响应
class EvidenceListResponse(BaseModel):
    items: list[EvidenceResponse]
    total: int
    skip: int
    limit: int


# 哈希校验请求
class HashVerifyRequest(BaseModel):
    expected_hash: str = Field(..., min_length=64, max_length=64)


# 哈希校验响应
class HashVerifyResponse(BaseModel):
    evidence_id: int
    expected_hash: str
    actual_hash: str
    match: bool


# 通过本地路径注册证据（JSON body 方式，适合大文件取证场景）
class EvidenceCreateRequest(BaseModel):
    case_id: int = Field(...)
    name: str = Field(..., min_length=1)
    file_path: str = Field(..., min_length=1)
    file_type: str = Field(default="raw")


# 通过本地路径注册证据（适合大文件取证场景，无需HTTP上传），系统会自动计算文件的 SHA-256 哈希值并记录文件大小
@router.post("", response_model=EvidenceResponse, status_code=201)
async def register_evidence_by_path(
    body: EvidenceCreateRequest,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    file_path = Path(body.file_path)
    if not file_path.exists():
        raise AppError(code="FILE_NOT_FOUND", message=f"文件不存在: {body.file_path}", status_code=400)
    if not file_path.is_file():
        raise AppError(code="NOT_A_FILE", message=f"路径不是文件: {body.file_path}", status_code=400)

    file_size = file_path.stat().st_size

    # 计算 SHA-256
    sha256_hash = await compute_sha256(str(file_path))

    evidence = Evidence(
        case_id=body.case_id,
        name=body.name,
        file_path=str(file_path.resolve()),
        file_type=body.file_type,
        sha256_hash=sha256_hash,
        file_size=file_size,
    )
    db.add(evidence)
    await db.flush()

    # 审计日志
    audit = AuditLog(
        case_id=body.case_id,
        action="evidence_registered",
        detail={
            "evidence_id": evidence.id,
            "name": body.name,
            "file_path": str(file_path.resolve()),
            "sha256": sha256_hash,
            "file_size": file_size,
        },
        operator=_get_client_ip(request),
        ip_address=_get_client_ip(request),
    )
    db.add(audit)
    await db.flush()

    logger.info(
        f"证据注册成功 case_id={body.case_id} evidence_id={evidence.id} name={body.name} sha256={sha256_hash}"
    )

    return _evidence_to_response(evidence)


# 上传证据文件并自动计算 SHA-256 哈希值，文件将保存到配置的存储目录中
@router.post("/upload", response_model=EvidenceResponse, status_code=201)
async def upload_evidence(
    case_id: int = Query(...),
    file: UploadFile = File(...),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    # 验证文件扩展名
    if file.filename is None:
        raise AppError(code="INVALID_FILE", message="文件名不能为空", status_code=400)

    ext = Path(file.filename).suffix.lower()
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise AppError(
            code="UNSUPPORTED_FILE_TYPE",
            message=f"不支持的文件类型: {ext}",
            status_code=400,
        )

    # 检查文件大小
    if file.size is not None and file.size > settings.MAX_UPLOAD_SIZE:
        raise AppError(
            code="FILE_TOO_LARGE",
            message=f"文件大小超过限制: {settings.MAX_UPLOAD_SIZE} bytes",
            status_code=413,
        )

    # 保存文件到存储目录
    storage_paths = get_storage_paths()
    evidence_dir = storage_paths["evidence"] / str(case_id)
    evidence_dir.mkdir(parents=True, exist_ok=True)

    # 生成唯一文件名（防止覆盖）
    original_name = file.filename
    safe_name = f"{os.urandom(8).hex()}_{original_name}"
    file_path = evidence_dir / safe_name

    # 写入文件
    content = await file.read()
    file_path.write_bytes(content)
    file_size = len(content)

    # 计算 SHA-256
    sha256_hash = await compute_sha256(str(file_path))

    # 创建证据记录
    evidence = Evidence(
        case_id=case_id,
        name=original_name,
        file_path=str(file_path),
        file_type=ext,
        sha256_hash=sha256_hash,
        file_size=file_size,
    )
    db.add(evidence)
    await db.flush()

    # 审计日志
    audit = AuditLog(
        case_id=case_id,
        action="evidence_uploaded",
        detail={
            "evidence_id": evidence.id,
            "name": original_name,
            "sha256": sha256_hash,
            "file_size": file_size,
        },
        operator=_get_client_ip(request),
        ip_address=_get_client_ip(request),
    )
    db.add(audit)
    await db.flush()

    logger.info(
        f"证据上传成功 case_id={case_id} evidence_id={evidence.id} name={original_name} sha256={sha256_hash}"
    )

    return _evidence_to_response(evidence)


# 获取证据列表（分页）
@router.get("", response_model=EvidenceListResponse)
async def list_evidences(
    case_id: int | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select, func

    query = select(Evidence)
    count_query = select(func.count(Evidence.id))

    if case_id:
        query = query.where(Evidence.case_id == case_id)
        count_query = count_query.where(Evidence.case_id == case_id)

    query = query.order_by(Evidence.created_at.desc()).offset(skip).limit(limit)

    result = await db.execute(query)
    evidences = result.scalars().all()

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    return EvidenceListResponse(
        items=[_evidence_to_response(e) for e in evidences],
        total=total,
        skip=skip,
        limit=limit,
    )


# 获取单个证据详情
@router.get("/{evidence_id}", response_model=EvidenceResponse)
async def get_evidence(
    evidence_id: int,
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select
    result = await db.execute(select(Evidence).where(Evidence.id == evidence_id))
    evidence = result.scalar_one_or_none()
    if not evidence:
        raise AppError(code="EVIDENCE_NOT_FOUND", message=f"证据不存在: evidence_id={evidence_id}", status_code=404)
    return _evidence_to_response(evidence)


# 下载证据文件
@router.get("/{evidence_id}/download")
async def download_evidence(
    evidence_id: int,
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select
    result = await db.execute(select(Evidence).where(Evidence.id == evidence_id))
    evidence = result.scalar_one_or_none()
    if not evidence:
        raise AppError(code="EVIDENCE_NOT_FOUND", message=f"证据不存在: evidence_id={evidence_id}", status_code=404)

    file_path = Path(evidence.file_path)
    if not file_path.exists():
        raise AppError(code="FILE_NOT_FOUND", message=f"文件不存在: {evidence.file_path}", status_code=404)

    return FileResponse(
        path=str(file_path),
        filename=evidence.name,
        media_type="application/octet-stream",
    )


# 验证证据文件的 SHA-256 哈希值
@router.post("/{evidence_id}/verify", response_model=HashVerifyResponse)
async def verify_evidence_hash(
    evidence_id: int,
    body: HashVerifyRequest,
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select
    result = await db.execute(select(Evidence).where(Evidence.id == evidence_id))
    evidence = result.scalar_one_or_none()
    if not evidence:
        raise AppError(code="EVIDENCE_NOT_FOUND", message=f"证据不存在: evidence_id={evidence_id}", status_code=404)

    match = verify_sha256(evidence.file_path, body.expected_hash)

    return HashVerifyResponse(
        evidence_id=evidence_id,
        expected_hash=body.expected_hash,
        actual_hash=evidence.sha256_hash,
        match=match,
    )


# 删除证据记录及其文件
@router.delete("/{evidence_id}")
async def delete_evidence(
    evidence_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select
    result = await db.execute(select(Evidence).where(Evidence.id == evidence_id))
    evidence = result.scalar_one_or_none()
    if not evidence:
        raise AppError(code="EVIDENCE_NOT_FOUND", message=f"证据不存在: evidence_id={evidence_id}", status_code=404)

    # 删除物理文件
    file_path = Path(evidence.file_path)
    if file_path.exists():
        file_path.unlink()

    # 审计日志
    audit = AuditLog(
        case_id=evidence.case_id,
        action="evidence_deleted",
        detail={"evidence_id": evidence_id, "name": evidence.name},
        operator=_get_client_ip(request),
        ip_address=_get_client_ip(request),
    )
    db.add(audit)

    await db.delete(evidence)
    await db.flush()

    logger.info(f"证据已删除 evidence_id={evidence_id} case_id={evidence.case_id}")
    return {"message": "证据已删除"}


def _evidence_to_response(evidence: Evidence) -> EvidenceResponse:
    return EvidenceResponse(
        id=evidence.id,
        case_id=evidence.case_id,
        name=evidence.name,
        file_path=evidence.file_path,
        file_type=evidence.file_type,
        sha256_hash=evidence.sha256_hash,
        file_size=evidence.file_size,
        created_at=evidence.created_at.isoformat() if evidence.created_at else "",
    )


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
