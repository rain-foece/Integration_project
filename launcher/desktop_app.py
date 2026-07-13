"""取证平台桌面应用 - 原生窗口 + 内置后端。

使用 pywebview 创建原生 Windows 桌面窗口，
后台自动启动 FastAPI 服务器，无需浏览器。

用法:
    python launcher/desktop_app.py              # 默认端口 8000
    python launcher/desktop_app.py --port 8080  # 自定义端口
"""

import sys
import os
import asyncio
import time
import threading
import socket
import traceback
from pathlib import Path

# 路径: launcher/ 的父目录是项目根目录
if getattr(sys, "frozen", False):
    _ROOT_DIR = Path(sys.executable).resolve().parent
else:
    _ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT_DIR))

APP_TITLE = "电子数据取证工具集成系统"
APP_VERSION = "v3.0"
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 800
WINDOW_MIN_WIDTH = 960
WINDOW_MIN_HEIGHT = 600
ERROR_LOG = _ROOT_DIR / "error.log"


def _log(msg: str):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open(ERROR_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def _find_free_port(start: int = 8000, max_attempts: int = 20) -> int:
    for port in range(start, start + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return start


def _wait_for_server(url: str, timeout: float = 20.0) -> bool:
    import urllib.request
    start = time.time()
    while time.time() - start < timeout:
        try:
            req = urllib.request.Request(url)
            urllib.request.urlopen(req, timeout=1)
            return True
        except Exception:
            time.sleep(0.5)
    return False


def _start_server(port: int):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        import uvicorn
        config = uvicorn.Config(
            "server.main:app",
            host="127.0.0.1",
            port=port,
            log_level="warning",
            loop="asyncio",
        )
        server = uvicorn.Server(config)
        loop.run_until_complete(server.serve())
    except Exception as e:
        _log(f"服务器异常: {e}\n{traceback.format_exc()}")
    finally:
        loop.close()


def main():
    port = _find_free_port(8000)
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--port" and i + 1 < len(args):
            port = int(args[i + 1])
            i += 2
        else:
            i += 1

    url = f"http://127.0.0.1:{port}"

    _log("=" * 60)
    _log(f"  {APP_TITLE} {APP_VERSION}")
    _log("=" * 60)
    _log(f"  服务地址: {url}")

    tools_dir = _ROOT_DIR / "tools"
    _log(f"  工具目录: {tools_dir}")
    if not tools_dir.exists():
        _log(f"  [提示] 外部工具目录不存在，6 个外部工具将不可用")
    _log("=" * 60)

    _log("  正在启动服务...")
    server_thread = threading.Thread(target=_start_server, args=(port,), daemon=True)
    server_thread.start()

    if not _wait_for_server(f"{url}/health", timeout=20.0):
        _log("  [错误] 服务器启动超时！")
        _log("  请检查 error.log 或尝试浏览器模式: python launcher/web_launcher.py")
        return

    _log("  服务已就绪，正在打开桌面窗口...")

    try:
        import webview
        window = webview.create_window(
            title=f"{APP_TITLE} {APP_VERSION}",
            url=url,
            width=WINDOW_WIDTH,
            height=WINDOW_HEIGHT,
            min_size=(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT),
            resizable=True,
            fullscreen=False,
            confirm_close=False,
            text_select=True,
        )
        _log("  桌面窗口已创建")

        def on_closing():
            _log("  窗口关闭")

        window.events.closing += on_closing
        webview.start(debug=False)

    except Exception as e:
        _log(f"  pywebview 启动失败: {e}")
        _log("  回退到浏览器模式...")
        import webbrowser
        def _open_browser():
            time.sleep(1.5)
            webbrowser.open(url)
        threading.Thread(target=_open_browser, daemon=True).start()
        _log(f"  浏览器已打开: {url}")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            _log("  服务已停止")


if __name__ == "__main__":
    main()