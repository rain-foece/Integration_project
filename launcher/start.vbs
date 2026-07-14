' 电子数据取证工具集成系统 - 无声启动脚本
' 双击此文件即可启动，不会弹出任何命令行窗口
Set WshShell = CreateObject("WScript.Shell")
scriptDir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = scriptDir
WshShell.Run "cmd /c start.bat", 0, False