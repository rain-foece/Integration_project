外部工具放置说明
==================

此目录用于存放需要手动安装的外部取证工具（6个）。
10个内置工具已纯 Python 实现，无需额外安装。

目录结构要求：
tools/
├── Fiddler/
│   └── Fiddler.exe          ← 网络抓包工具
├── Volatility3/
│   └── vol.exe              ← 内存取证框架
├── WinDbg/
│   └── cdb.exe              ← 微软调试器（或 windbg.exe）
├── john/
│   └── run/
│       └── john.exe         ← 密码破解工具
├── NetworkMiner/
│   └── NetworkMiner.exe     ← 网络取证分析
└── testdisk/
    └── testdisk_win.exe     ← 数据恢复工具

下载链接：
- Fiddler:       https://www.telerik.com/fiddler
- Volatility 3:  https://github.com/volatilityfoundation/volatility3
- WinDbg:        https://aka.ms/windbg/download
- John the Ripper: https://www.openwall.com/john/
- NetworkMiner:  https://www.netresec.com/?page=NetworkMiner
- TestDisk:      https://www.cgsecurity.org/wiki/TestDisk

注意：不需要安装所有工具，系统会自动检测已安装的工具。