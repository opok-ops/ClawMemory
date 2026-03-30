# ClawMemory GUI 启动器
# 用法: 右键 -> 用 PowerShell 运行
$ErrorActionPreference = "Stop"
Write-Host "=== ClawMemory GUI 启动器 ===" -ForegroundColor Cyan
try {
    pip show PySimpleGUI | Out-Null
} catch {
    Write-Host "[*] 安装 PySimpleGUI..." -ForegroundColor Yellow
    pip install PySimpleGUI --quiet --user
}
python -c "import PySimpleGUI; print('OK')
& python -m PySimpleGUI
