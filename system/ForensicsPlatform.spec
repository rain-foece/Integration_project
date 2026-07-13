# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置 - 电子数据取证工具集成系统 v3.0。

四层架构: launcher(启动) + server(后端) + web(前端) + system(配置)
入口: launcher/desktop_app.py
构建: cd system && pyinstaller ForensicsPlatform.spec
"""

from pathlib import Path

# SPECPATH 是 spec 文件所在目录 (system/)，PROJECT_ROOT 是项目根目录
PROJECT_ROOT = Path(SPECPATH).parent

# 静态文件: web/
datas = [
    (str(PROJECT_ROOT / "web"), "web"),
]

# 隐藏导入
hiddenimports = [
    "aiosqlite",
    "sqlalchemy.ext.asyncio",
    "pydantic_settings",
    "pydantic",
    "webview",
    "webview.platforms.winforms",
    "webview.platforms.edgechromium",
    "webview.js",
    "webview.util",
    "clr",
    "server",
    "server.main",
    "server.config",
    "server.tools_config",
    "server.models",
    "server.models.database",
    "server.models.case",
    "server.models.evidence",
    "server.models.task",
    "server.models.report",
    "server.models.audit_log",
    "server.adapters",
    "server.adapters.base_adapter",
    "server.adapters.exiftool_adapter",
    "server.adapters.wireshark_adapter",
    "server.adapters.process_explorer_adapter",
    "server.adapters.process_monitor_adapter",
    "server.adapters.ftk_imager_adapter",
    "server.adapters.hashcat_adapter",
    "server.adapters.beyond_compare_adapter",
    "server.adapters.debugview_adapter",
    "server.adapters.ten_editor_adapter",
    "server.adapters.ibackupbot_adapter",
    "server.adapters.fiddler_adapter",
    "server.adapters.volatility_adapter",
    "server.adapters.windbg_adapter",
    "server.adapters.john_adapter",
    "server.adapters.testdisk_adapter",
    "server.adapters.networkminer_adapter",
    "server.routers",
    "server.routers.cases",
    "server.routers.evidences",
    "server.routers.tasks",
    "server.routers.reports",
    "server.routers.tools",
    "server.routers.error_handlers",
    "server.services",
    "server.services.case_service",
    "server.services.task_service",
    "server.services.report_service",
    "server.services.logging",
    "server.utils",
    "server.utils.hash_utils",
]

excluded_modules = [
    "tkinter", "matplotlib", "numpy", "pandas", "PIL",
    "cv2", "tensorflow", "torch", "jupyter", "IPython",
    "PyQt5", "PyQt6", "PySide2", "PySide6", "wx", "gtk",
]

# 自动收集服务端子模块
for pkg in ["server", "server.adapters", "server.models", "server.routers", "server.services", "server.utils"]:
    pkg_path = PROJECT_ROOT / pkg.replace(".", "/")
    if pkg_path.exists():
        for py_file in pkg_path.glob("*.py"):
            if py_file.name != "__init__.py":
                mod = f"{pkg}.{py_file.stem}"
                if mod not in hiddenimports:
                    hiddenimports.append(mod)

a = Analysis(
    [str(PROJECT_ROOT / "launcher" / "desktop_app.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excluded_modules,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="ForensicsPlatform",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="ForensicsPlatform",
)