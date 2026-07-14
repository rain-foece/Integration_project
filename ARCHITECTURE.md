# 电子数据取证工具集成系统 v3.0 — 架构文档

## 项目概览

一个面向电子数据取证的桌面工具集成平台，将 16 个取证工具统一在一个原生 Windows 窗口中运行。后端使用 FastAPI + SQLite，前端为单文件 SPA，桌面窗口通过 pywebview（Edge WebView2）实现。

## 目录结构

```
forensics-platform/
│
├── launcher/                  # 启动层：程序入口
│   ├── start.vbs              # 双击零弹窗启动（推荐）
│   ├── start.bat              # 一键启动（自动检测桌面版/浏览器模式）
│   ├── desktop_app.py         # 桌面窗口入口（pywebview + 内嵌后端）
│   └── web_launcher.py        # 浏览器模式入口（备用）
│
├── server/                    # 后端服务层
│   ├── main.py                # FastAPI 应用入口（路由注册/CORS/静态文件）
│   ├── config.py              # 全局配置（数据库/存储/日志/上传限制）
│   ├── tools_config.py        # 外部工具路径管理
│   │
│   ├── adapters/              # 16 个工具适配器
│   │   ├── base_adapter.py    # 抽象基类（ToolResult + BaseToolAdapter）
│   │   ├── __init__.py        # 适配器注册表
│   │   └── *_adapter.py       # 各工具适配器（见下方工具列表）
│   │
│   ├── models/                # 数据模型（SQLAlchemy 异步 ORM）
│   │   ├── database.py        # 引擎/会话/get_db 依赖注入
│   │   ├── case.py            # 案件模型
│   │   ├── evidence.py        # 证据模型
│   │   ├── task.py            # 任务模型
│   │   ├── report.py          # 报告模型
│   │   └── audit_log.py       # 审计日志
│   │
│   ├── routers/               # API 路由（FastAPI APIRouter）
│   │   ├── cases.py           # 案件 CRUD
│   │   ├── evidences.py       # 证据注册/上传/哈希校验
│   │   ├── tasks.py           # 任务创建/查询/取消
│   │   ├── reports.py         # 报告生成/查看/下载
│   │   ├── tools.py           # 工具列表/详情
│   │   └── error_handlers.py  # 统一异常处理
│   │
│   ├── services/              # 业务逻辑层
│   │   ├── case_service.py    # 案件 CRUD + 审计日志
│   │   ├── task_service.py    # asyncio 后台任务执行引擎
│   │   ├── report_service.py  # HTML 报告模板渲染
│   │   └── logging.py         # 日志配置
│   │
│   └── utils/                 # 工具函数
│       └── hash_utils.py      # SHA-256 异步/同步计算
│
├── web/                       # 前端层
│   └── index.html             # 单文件 SPA（内嵌 CSS + JS）
│
├── system/                    # 系统配置
│   ├── requirements.txt       # Python 依赖
│   └── ForensicsPlatform.spec # PyInstaller 打包配置
│
├── tools/                     # 外部工具目录（用户自行放置 EXE）
│   └── README.txt
│
└── README.md                  # 项目说明
```

## 启动流程

```
用户双击 start.vbs
  │
  └─ start.vbs 调用 start.bat（隐藏控制台窗口）
       │
       ├─ [方式1] 检测到 dist/ForensicsPlatform.exe
       │    └─ 直接启动打包好的 EXE
       │
       ├─ [方式2] 检测到 launcher/desktop_app.py
       │    ├─ 检查依赖 → 缺失则 pip install
       │    └─ pythonw.exe launcher/desktop_app.py
       │         ├─ 后台线程启动 uvicorn（server.main:app）
       │         ├─ 等待 /health 就绪
       │         └─ pywebview 创建原生窗口（Edge WebView2）
       │
       └─ [方式3] 检测到 launcher/web_launcher.py
            └─ python.exe launcher/web_launcher.py
                 ├─ 后台启动 uvicorn
                 └─ 自动打开浏览器
```

## 16 个取证工具

### 内置工具（10 个，纯 Python 实现，零外部依赖）

| 工具 | 适配器文件 | 取证领域 | 核心能力 |
|------|-----------|----------|----------|
| ExifTool | `exiftool_adapter.py` | 元数据分析 | 文件元数据提取、PE 头分析、哈希计算 |
| Wireshark | `wireshark_adapter.py` | 网络流量 | PCAP 解析、协议统计、HTTP 提取（scapy） |
| Hashcat | `hashcat_adapter.py` | 密码破解 | 30+ 种哈希类型识别与验证 |
| Process Explorer | `process_explorer_adapter.py` | 进程监控 | 进程列表、进程树、DLL 分析（psutil） |
| Process Monitor | `process_monitor_adapter.py` | 进程监控 | 进程/文件实时监控（psutil + watchdog） |
| 010 Editor | `ten_editor_adapter.py` | 二进制分析 | 十六进制查看、60+ 魔数签名识别 |
| iBackupBot | `ibackupbot_adapter.py` | 移动取证 | iOS 备份解析、短信/联系人提取 |
| Beyond Compare | `beyond_compare_adapter.py` | 文件对比 | 文件差异对比、相似度分析（difflib） |
| DebugView | `debugview_adapter.py` | 调试分析 | DBWIN 共享内存调试消息捕获 |
| FTK Imager | `ftk_imager_adapter.py` | 磁盘镜像 | 磁盘镜像校验、哈希验证 |

### 外部工具（6 个，需安装对应 EXE 到 tools/ 目录）

| 工具 | 适配器文件 | 取证领域 | 调用的 EXE |
|------|-----------|----------|-----------|
| Volatility | `volatility_adapter.py` | 内存取证 | `vol.exe` |
| NetworkMiner | `networkminer_adapter.py` | 网络流量 | `NetworkMiner.exe` |
| John the Ripper | `john_adapter.py` | 密码破解 | `john.exe` |
| TestDisk | `testdisk_adapter.py` | 磁盘恢复 | `photorec_win.exe` / `testdisk_win.exe` |
| WinDbg | `windbg_adapter.py` | 调试分析 | `cdb.exe` |
| Fiddler | `fiddler_adapter.py` | 网络流量 | `Fiddler.exe` |

## 数据模型关系

```
Case (案件)
  ├── 1:N → Evidence (证据) —— case_id 外键，级联删除
  ├── 1:N → Task (任务)    —— case_id 外键，级联删除
  └── 1:N → Report (报告)  —— case_id 外键，级联删除

Evidence (证据)
  └── 1:N → Task (任务)    —— evidence_id 外键，删除证据时置 NULL

AuditLog (审计日志，独立表，记录所有操作)
```

**状态流转**：
- 案件：`open` → `analyzing`（创建任务自动触发）→ `closed`（手动）
- 任务：`pending` → `running` → `completed` / `failed`

## API 接口一览

前缀：`/api/v1`

### 案件 `/cases`
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/cases` | 创建案件 |
| GET | `/cases` | 案件列表（分页，支持 status 过滤） |
| GET | `/cases/{id}` | 案件详情 |
| PATCH | `/cases/{id}` | 更新案件 |
| DELETE | `/cases/{id}` | 删除案件（级联删除关联数据） |

### 证据 `/evidences`
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/evidences` | 通过本地路径注册证据（自动计算 SHA-256） |
| POST | `/evidences/upload` | 上传证据文件 |
| GET | `/evidences` | 证据列表（分页，支持 case_id 过滤） |
| GET | `/evidences/{id}` | 证据详情 |
| GET | `/evidences/{id}/download` | 下载证据文件 |
| POST | `/evidences/{id}/verify` | 验证 SHA-256 哈希 |
| DELETE | `/evidences/{id}` | 删除证据及文件 |

### 任务 `/tasks`
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/tasks` | 创建取证任务（异步后台执行） |
| GET | `/tasks` | 任务列表（分页，支持 case_id/status/tool_name 过滤） |
| GET | `/tasks/{id}` | 任务详情 |
| POST | `/tasks/{id}/cancel` | 取消任务 |

### 报告 `/reports`
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/reports` | 创建报告 |
| GET | `/reports` | 报告列表（分页，支持 case_id 过滤） |
| GET | `/reports/{id}` | 报告详情 |
| POST | `/reports/{id}/generate-html` | 生成 HTML 报告 |
| GET | `/reports/{id}/view` | 在线查看报告 |
| GET | `/reports/{id}/download-html` | 下载报告文件 |

### 工具 `/tools`
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/tools` | 工具列表及元信息 |
| GET | `/tools/{name}` | 工具详情 |

### 其他
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 前端页面 |
| GET | `/health` | 健康检查 |

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端框架 | FastAPI |
| ASGI 服务器 | uvicorn |
| ORM | SQLAlchemy 2.0（异步模式） |
| 数据库 | SQLite（aiosqlite 驱动） |
| 数据验证 | Pydantic v2 |
| 配置管理 | pydantic-settings |
| 前端 | 单文件 HTML/CSS/JS（零框架依赖） |
| 桌面窗口 | pywebview（Edge WebView2） |
| 打包 | PyInstaller |
| 进程监控 | psutil |
| 网络分析 | scapy |
| 文件监控 | watchdog |

## 适配器开发指南

如需添加新工具，在 `server/adapters/` 下创建新文件，继承 `BaseToolAdapter`：

```python
from server.adapters.base_adapter import BaseToolAdapter, ToolResult

class MyToolAdapter(BaseToolAdapter):
    tool_name = "my_tool"
    version = "1.0.0"
    description = "工具描述"
    capabilities = ["capability_a", "capability_b"]

    def validate_input(self, params: dict) -> bool:
        return True

    async def run(self, params: dict) -> ToolResult:
        # 实现取证逻辑
        return ToolResult(
            success=True,
            result={"key": "value"},
            message="分析完成",
        )
```

然后在 `server/adapters/__init__.py` 中注册即可。