"""报告生成业务逻辑模块 — 支持按工具类型生成格式化 HTML 报告。"""

import json
from typing import Optional
from pathlib import Path
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from server.models.report import Report
from server.models.case import Case
from server.models.audit_log import AuditLog
from server.config import get_storage_paths
from server.services.logging import get_logger

logger = get_logger(__name__)


# ── 工具中文名称映射 ──────────────────────────────────────────────
TOOL_NAMES_ZH = {
    "exiftool": "ExifTool 元数据提取",
    "wireshark": "Wireshark 网络流量分析",
    "fiddler": "Fiddler Web 抓包分析",
    "volatility": "Volatility 内存取证",
    "ftk_imager": "FTK Imager 磁盘镜像",
    "networkminer": "NetworkMiner PCAP 分析",
    "hashcat": "Hashcat 哈希破解",
    "john": "John the Ripper 密码破解",
    "testdisk": "TestDisk 分区恢复",
    "windbg": "WinDbg 崩溃调试",
    "debugview": "DebugView 调试日志",
    "process_explorer": "Process Explorer 进程分析",
    "process_monitor": "Process Monitor 进程监控",
    "010editor": "010 Editor 二进制分析",
    "ibackupbot": "iBackupBot iOS 备份取证",
    "beyond_compare": "Beyond Compare 文件对比",
}

# ── 工具分类映射 ──────────────────────────────────────────────────
TOOL_CATEGORY = {
    "exiftool": "元数据与文件分析",
    "wireshark": "网络流量分析",
    "fiddler": "网络流量分析",
    "networkminer": "网络流量分析",
    "volatility": "内存取证",
    "ftk_imager": "磁盘与镜像取证",
    "testdisk": "磁盘与镜像取证",
    "hashcat": "密码破解",
    "john": "密码破解",
    "windbg": "崩溃与调试分析",
    "debugview": "崩溃与调试分析",
    "process_explorer": "进程监控",
    "process_monitor": "进程监控",
    "010editor": "二进制分析",
    "ibackupbot": "移动设备取证",
    "beyond_compare": "文件对比",
}


async def create_report(
    db: AsyncSession,
    case_id: int,
    title: str,
    content: dict | None = None,
    operator: str | None = None,
    ip_address: str | None = None,
) -> Report:
    """为案件创建一份报告。"""
    case = await db.execute(select(Case).where(Case.id == case_id))
    case = case.scalar_one_or_none()
    if not case:
        raise ValueError(f"案件不存在: case_id={case_id}")

    report = Report(case_id=case_id, title=title, content=content or {})
    db.add(report)
    await db.flush()

    audit = AuditLog(
        case_id=case_id,
        action="report_created",
        detail={"report_id": report.id, "title": title},
        operator=operator,
        ip_address=ip_address,
    )
    db.add(audit)
    await db.flush()

    logger.info(f"报告创建成功 | case_id={case_id}, report_id={report.id}, title={title}")
    return report


async def get_report(db: AsyncSession, report_id: int) -> Report | None:
    result = await db.execute(select(Report).where(Report.id == report_id))
    return result.scalar_one_or_none()


async def list_reports(
    db: AsyncSession,
    case_id: int | None = None,
    skip: int = 0,
    limit: int = 20,
) -> tuple[list[Report], int]:
    query = select(Report)
    count_query = select(func.count(Report.id))
    if case_id:
        query = query.where(Report.case_id == case_id)
        count_query = count_query.where(Report.case_id == case_id)
    query = query.order_by(Report.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    reports = result.scalars().all()
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    return list(reports), total


async def generate_report_html(
    db: AsyncSession,
    report_id: int,
) -> Report | None:
    """为报告生成格式化 HTML 文件。"""
    report = await get_report(db, report_id)
    if not report:
        return None

    storage_paths = get_storage_paths()
    report_dir = storage_paths["report"] / str(report.case_id)
    report_dir.mkdir(parents=True, exist_ok=True)

    html_content = _build_html_report(report)
    html_path = report_dir / f"report_{report.id}.html"
    html_path.write_text(html_content, encoding="utf-8")

    report.html_path = str(html_path)
    await db.flush()

    logger.info(f"HTML 报告生成成功 | case_id={report.case_id}, report_id={report.id}")
    return report


async def generate_report_pdf(
    db: AsyncSession,
    report_id: int,
) -> Report | None:
    report = await get_report(db, report_id)
    if not report:
        return None
    if not report.html_path:
        report = await generate_report_html(db, report_id)
        if not report:
            return None
    storage_paths = get_storage_paths()
    report_dir = storage_paths["report"] / str(report.case_id)
    pdf_path = report_dir / f"report_{report.id}.pdf"
    report.pdf_path = str(pdf_path)
    await db.flush()
    return report


# ===================================================================
#  HTML 报告模板构建
# ===================================================================

def _build_html_report(report: Report) -> str:
    """构建格式化的 HTML 取证报告。

    根据报告内容中的 tool_name 自动选择对应的格式化模板。
    对于 exiftool 等元数据工具，以表格形式展示；对于其他工具，以结构化面板展示。
    """
    content = report.content or {}
    tool_name = content.get("tool_name", "unknown")
    result = content.get("result", {})
    task_id = content.get("task_id", "-")
    generated_at = content.get("generated_at", str(report.created_at))

    tool_zh = TOOL_NAMES_ZH.get(tool_name, tool_name)
    category = TOOL_CATEGORY.get(tool_name, "通用取证")

    sections_html = _build_result_sections(tool_name, result)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{report.title}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
  font-family: -apple-system, BlinkMacSystemFont, 'Microsoft YaHei', 'Segoe UI', sans-serif;
  background: #0a0e17; color: #e2e8f0; line-height: 1.7;
  padding: 40px 60px;
}}
.header {{
  border-bottom: 2px solid #06b6d4; padding-bottom: 20px; margin-bottom: 30px;
}}
.header h1 {{ font-size: 1.6rem; color: #06b6d4; margin-bottom: 6px; }}
.header .meta {{ color: #8899aa; font-size: 0.85rem; }}
.header .meta span {{ margin-right: 24px; }}
.header .badge {{
  display: inline-block; background: rgba(6,182,212,0.15); color: #06b6d4;
  padding: 2px 10px; border-radius: 4px; font-size: 0.8rem; font-weight: 600;
}}
.section {{
  background: #111827; border: 1px solid #1e293b; border-radius: 8px;
  padding: 20px; margin-bottom: 20px;
}}
.section h2 {{
  font-size: 1rem; color: #06b6d4; margin-bottom: 14px;
  padding-bottom: 8px; border-bottom: 1px solid #1e293b;
}}
.section h3 {{ font-size: 0.9rem; color: #8b5cf6; margin: 16px 0 8px; }}
table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
th {{
  text-align: left; padding: 8px 12px; background: #1a2332;
  color: #06b6d4; font-weight: 600; font-size: 0.78rem;
  text-transform: uppercase; letter-spacing: 0.04em;
  border-bottom: 2px solid #1e293b;
}}
td {{ padding: 6px 12px; border-bottom: 1px solid #1e293b; }}
td.key {{ color: #8899aa; font-weight: 600; width: 180px; }}
td.val {{ word-break: break-all; font-family: 'Consolas', 'Courier New', monospace; font-size: 0.82rem; }}
.hash {{ color: #f59e0b; }}
.success {{ color: #10b981; }}
.danger {{ color: #ef4444; }}
.muted {{ color: #8899aa; }}
.card-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px; }}
.info-card {{
  background: #1a2332; border: 1px solid #1e293b; border-radius: 6px; padding: 12px;
}}
.info-card .label {{ font-size: 0.72rem; color: #8899aa; text-transform: uppercase; }}
.info-card .value {{ font-size: 0.95rem; font-weight: 600; margin-top: 4px; word-break: break-all; }}
.footer {{
  margin-top: 40px; padding-top: 16px; border-top: 1px solid #1e293b;
  color: #556677; font-size: 0.75rem; text-align: center;
}}
</style>
</head>
<body>
<div class="header">
  <h1>📋 {report.title}</h1>
  <div class="meta">
    <span>案件 ID: <strong>#{report.case_id}</strong></span>
    <span>任务 ID: <strong>#{task_id}</strong></span>
    <span>工具: <span class="badge">{tool_zh}</span></span>
    <span>分类: {category}</span>
  </div>
  <div class="meta" style="margin-top:6px">
    <span>生成时间: {generated_at}</span>
  </div>
</div>
{sections_html}
<div class="footer">
  由电子数据取证工具集成系统自动生成 · Forensics Tool Integration Platform v1.0
</div>
</body>
</html>"""


def _build_result_sections(tool_name: str, result: dict) -> str:
    """根据工具类型构建不同的结果展示区域。"""
    if not result:
        return '<div class="section"><h2>分析结果</h2><p class="muted">无结果数据</p></div>'

    # 如果是纯字符串结果，直接展示
    if isinstance(result, str):
        return f'<div class="section"><h2>分析结果</h2><pre style="background:#1a2332;padding:16px;border-radius:6px;white-space:pre-wrap;font-family:Consolas,monospace;font-size:0.82rem;">{result}</pre></div>'

    if not isinstance(result, dict):
        return f'<div class="section"><h2>分析结果</h2><pre style="background:#1a2332;padding:16px;border-radius:6px;white-space:pre-wrap;font-family:Consolas,monospace;font-size:0.82rem;">{str(result)}</pre></div>'

    # exiftool 元数据 — 核心格式化
    if tool_name == "exiftool":
        return _build_exiftool_sections(result)

    # 通用格式化
    return _build_generic_sections(result)


def _build_exiftool_sections(result: dict) -> str:
    """为 exiftool 构建格式化的元数据报告区域。"""
    md = result.get("metadata", result)
    file_info = result.get("file", "")

    html = ""

    # 文件基本信息卡片
    if file_info:
        html += _make_info_cards([
            ("文件路径", file_info),
            ("提取字段数", str(result.get("fields_extracted", len(md)))),
            ("分析状态", '<span class="success">✅ 提取成功</span>'),
        ])

    # 基本信息表
    basic_keys = ["FileName", "FileSize", "FileSizeHR", "FileTypeExtension", "MIMEType"]
    basic_rows = [(k, str(md.get(k, "-"))) for k in basic_keys if k in md]
    if basic_rows:
        html += _make_section("📁 文件基本信息", _make_table(basic_rows))

    # 哈希值表
    hash_keys = ["SHA256", "MD5"]
    hash_rows = []
    for k in hash_keys:
        if k in md:
            hash_rows.append((k, f'<span class="hash">{md[k]}</span>'))
    if hash_rows:
        html += _make_section("🔐 哈希校验", _make_table(hash_rows))

    # 时间戳表
    time_keys = ["FileModifyDate", "FileAccessDate", "FileCreateDate"]
    time_rows = [(k, str(md.get(k, "-"))) for k in time_keys if k in md]
    if time_rows:
        html += _make_section("🕐 时间戳信息", _make_table(time_rows))

    # PE 分析
    pe_keys = ["FileFormat", "MachineType", "PEMagic", "NumberOfSections", "EntryPoint", "ImageBase", "PETimestamp"]
    pe_rows = [(k, str(md.get(k, "-"))) for k in pe_keys if k in md]
    if pe_rows:
        html += _make_section("⚙️ PE 文件分析", _make_table(pe_rows))

    # 图片信息
    img_keys = ["ImageFormat", "ImageWidth", "ImageHeight"]
    img_rows = [(k, str(md.get(k, "-"))) for k in img_keys if k in md]
    if img_rows:
        html += _make_section("🖼️ 图片属性", _make_table(img_rows))

    # 文件头信息
    header_keys = ["MagicBytes", "MagicString", "FileHeader"]
    header_rows = [(k, f'<span style="font-family:Consolas,monospace;font-size:0.78rem">{md.get(k, "-")}</span>') for k in header_keys if k in md]
    if header_rows:
        html += _make_section("🔍 文件头与魔数", _make_table(header_rows))

    # 其余未知字段
    shown = set(basic_keys + hash_keys + time_keys + pe_keys + img_keys + header_keys)
    other_rows = [(k, str(v)) for k, v in md.items() if k not in shown]
    if other_rows:
        html += _make_section("📎 其他元数据", _make_table(other_rows))

    return html


def _build_generic_sections(result: dict) -> str:
    """通用结果格式化。"""
    html = ""

    # 如果 result 有明确的结构，尝试格式化
    for section_key, section_value in result.items():
        if isinstance(section_value, dict):
            rows = [(k, str(v)) for k, v in section_value.items()]
            html += _make_section(f"📊 {section_key}", _make_table(rows))
        elif isinstance(section_value, list):
            items = "".join(f'<li style="padding:4px 0;border-bottom:1px solid #1e293b">{str(item)}</li>' for item in section_value)
            html += _make_section(f"📋 {section_key}", f'<ul style="list-style:none;padding:0">{items}</ul>')
        else:
            html += _make_section(f"📄 {section_key}", f'<pre style="background:#1a2332;padding:12px;border-radius:6px;white-space:pre-wrap;font-family:Consolas,monospace;font-size:0.82rem;">{str(section_value)}</pre>')

    return html


# ── HTML 构建辅助函数 ─────────────────────────────────────────────

def _make_section(title: str, body: str) -> str:
    return f'<div class="section"><h2>{title}</h2>{body}</div>'


def _make_table(rows: list[tuple[str, str]]) -> str:
    tbody = "".join(
        f'<tr><td class="key">{k}</td><td class="val">{v}</td></tr>'
        for k, v in rows
    )
    return f'<table><tbody>{tbody}</tbody></table>'


def _make_info_cards(items: list[tuple[str, str]]) -> str:
    cards = "".join(
        f'<div class="info-card"><div class="label">{label}</div><div class="value">{value}</div></div>'
        for label, value in items
    )
    return f'<div class="section"><div class="card-grid">{cards}</div></div>'

