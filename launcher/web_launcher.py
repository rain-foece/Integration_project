"""取证平台 - 浏览器模式启动器。

后台启动 FastAPI 服务器，自动打开默认浏览器。

用法:
    python launcher/web_launcher.py              # 默认端口 8000
    python launcher/web_launcher.py --port 8080  # 自定义端口
    python launcher/web_launcher.py --no-browser # 不自动打开浏览器
"""

import sys
import time
import webbrowser
import threading
import asyncio
from pathlib import Path

# 路径: launcher/ 的父目录是项目根目录
if getattr(sys, "frozen", False):
    _ROOT_DIR = Path(sys.executable).resolve().parent
else:
    _ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT_DIR))


def main():
    import socket

    port = 8000
    no_browser = False
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--port" and i + 1 < len(args):
            port = int(args[i + 1])
            i += 2
        elif args[i] == "--no-browser":
            no_browser = True
            i += 1
        else:
            i += 1

    for p in range(port, port + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", p))
                port = p
                break
            except OSError:
                continue

    url = f"http://127.0.0.1:{port}"

    print("=" * 60)
    print(f"  电子数据取证工具集成系统 v3.0")
    print(f"  服务地址: {url}")
    print("=" * 60)

    def _serve():
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
        finally:
            loop.close()

    server_thread = threading.Thread(target=_serve, daemon=True)
    server_thread.start()

    import urllib.request
    for _ in range(30):
        try:
            urllib.request.urlopen(f"{url}/health", timeout=1)
            break
        except Exception:
            time.sleep(0.5)

    print("  服务已就绪")

    if not no_browser:
        def _open():
            time.sleep(0.5)
            webbrowser.open(url)
        threading.Thread(target=_open, daemon=True).start()
        print(f"  浏览器已打开: {url}")

    print("  按 Ctrl+C 停止服务")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("  服务已停止")


if __name__ == "__main__":
    main()