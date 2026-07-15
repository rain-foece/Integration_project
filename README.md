# 电子数据取证工具集成系统

> Forensics Tool Integration Platform v3.0

集成 16 个取证工具的桌面平台，支持案件管理、证据登记、工具调度、任务监控和报告生成。同时支持**桌面版**和**网页版**两种部署模式。

## 两种使用方式

| 方式 | 启动 | 适用场景 |
|------|------|----------|
| 桌面版 | 双击 `launcher/start.vbs` | 个人本地使用，Windows 原生窗口 |
| 网页版 | Docker 部署 | 团队共享，公网访问 |

网页版部署详见 [DEPLOY.md](DEPLOY.md)。

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.14 + FastAPI + SQLAlchemy 2.0 (异步) + SQLite |
| 前端 | 单文件 HTML/CSS/JS，无需 npm |
| 桌面窗口 | pywebview (Edge WebView2) |
| 打包 | PyInstaller |

## 项目结构

```
forensics-platform/
├── launcher/               # 启动程序
│   ├── start.bat           # Windows 一键启动脚本
│   ├── desktop_app.py      # 桌面窗口入口（pywebview 原生窗口）
│   └── web_launcher.py     # 浏览器模式入口（备用）
│
├── server/                 # 后端服务
│   ├── main.py             # FastAPI 应用入口
│   ├── config.py           # 系统配置
│   ├── tools_config.py     # 外部工具路径管理
│   ├── adapters/           # 16 个工具适配器
│   │   ├── base_adapter.py         # 适配器基类
│   │   ├── exiftool_adapter.py     # 元数据提取 (内置)
│   │   ├── wireshark_adapter.py    # 网络流量分析 (内置)
│   │   ├── process_explorer_adapter.py  # 进程分析 (内置)
│   │   ├── process_monitor_adapter.py   # 系统监控 (内置)
│   │   ├── ftk_imager_adapter.py        # 镜像哈希验证 (内置)
│   │   ├── hashcat_adapter.py           # 哈希类型识别 (内置)
│   │   ├── beyond_compare_adapter.py    # 文件对比 (内置)
│   │   ├── debugview_adapter.py         # 调试捕获 (内置)
│   │   ├── ten_editor_adapter.py        # 十六进制查看 (内置)
│   │   ├── ibackupbot_adapter.py        # iOS 备份解析 (内置)
│   │   ├── fiddler_adapter.py           # HTTP 会话分析 (外部)
│   │   ├── volatility_adapter.py        # 内存取证 (外部)
│   │   ├── windbg_adapter.py            # 崩溃转储分析 (外部)
│   │   ├── john_adapter.py              # 密码破解 (外部)
│   │   ├── networkminer_adapter.py      # 网络取证 (外部)
│   │   └── testdisk_adapter.py          # 数据恢复 (外部)
│   ├── models/             # 数据模型
│   │   ├── database.py     # 数据库连接与会话管理
│   │   ├── case.py         # 案件模型
│   │   ├── evidence.py     # 证据模型
│   │   ├── task.py         # 任务模型（含进度追踪）
│   │   ├── report.py       # 报告模型
│   │   └── audit_log.py    # 审计日志模型
│   ├── routers/            # API 路由
│   │   ├── cases.py        # 案件 CRUD
│   │   ├── evidences.py    # 证据注册/删除/哈希校验
│   │   ├── tasks.py        # 任务创建/取消/进度查询
│   │   ├── reports.py      # 报告生成/查看/下载
│   │   ├── tools.py        # 工具列表/详情
│   │   └── error_handlers.py  # 统一异常处理
│   ├── services/           # 业务逻辑
│   │   ├── case_service.py     # 案件管理
│   │   ├── task_service.py     # 异步任务编排
│   │   ├── report_service.py   # 报告模板渲染
│   │   └── logging.py          # 日志配置
│   └── utils/
│       └── hash_utils.py   # SHA-256 哈希计算
│
├── web/                    # 前端界面
│   └── index.html          # 单文件 SPA（仪表盘/案件/工具/任务/报告）
│
├── system/                 # 系统配置
│   ├── requirements.txt    # Python 依赖清单
│   └── ForensicsPlatform.spec  # PyInstaller 打包配置
│
├── tools/                  # 外部工具目录
│   └── README.txt          # 外部工具放置说明
│
├── .gitignore
└── README.md
```

## 快速启动

### 方式一：双击启动（推荐）

```
双击 launcher/start.bat
```

系统会自动检测运行环境，优先使用桌面版，回退到浏览器模式。

### 方式二：命令行启动

```bash
# 安装依赖
pip install -r system/requirements.txt

# 桌面窗口模式
python launcher/desktop_app.py

# 浏览器模式（备用）
python launcher/web_launcher.py
```

### 方式三：打包为 EXE

```bash
cd system
pyinstaller ForensicsPlatform.spec
# 输出: system/dist/ForensicsPlatform/ForensicsPlatform.exe
```

## 内置工具 (10 个)

| 工具 | 说明 |
|------|------|
| ExifTool | 文件元数据提取、哈希计算、PE 信息分析 |
| Wireshark | PCAP 网络流量解析、协议统计 |
| Process Explorer | 进程树、线程、DLL 列表 |
| Process Monitor | 系统活动监控（进程/注册表/文件） |
| FTK Imager | 磁盘镜像哈希验证 |
| Hashcat | 哈希类型识别（30+ 种格式） |
| Beyond Compare | 文件差异对比 |
| DebugView | 调试输出捕获、关键字过滤 |
| 010 Editor | 十六进制查看、magic bytes 分析 |
| iBackupBot | iOS iTunes 备份解析 |

## 外部工具 (6 个)

| 工具 | 需要放入 tools/ 的文件 |
|------|----------------------|
| Fiddler | `tools/Fiddler/Fiddler.exe` |
| Volatility 3 | `tools/Volatility3/vol.exe` |
| WinDbg | `tools/WinDbg/cdb.exe` |
| John the Ripper | `tools/john/run/john.exe` |
| NetworkMiner | `tools/NetworkMiner/NetworkMiner.exe` |
| TestDisk | `tools/testdisk/testdisk_win.exe` |

## 功能特性

- 案件管理：创建/删除案件，状态追踪
- 证据注册：路径引用登记，自动 SHA-256 哈希校验
- 工具调度：异步后台任务，实时进度追踪
- 任务监控：进度条、开始时间、取消操作
- 报告生成：按工具类型自动生成格式化 HTML 报告
- 审计日志：所有操作自动记录、可追溯
- 桌面窗口：pywebview 原生窗口，无需浏览器

## 访问地址

启动后访问 `http://localhost:8000`（桌面窗口会自动打开此地址）。

## 许可证

内部项目，仅供学习和研究使用。