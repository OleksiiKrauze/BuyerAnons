# Запуск Telegram-бота BuyerAnons напрямую в Windows (не в Docker - иначе не работает New Balance).
# Используется автозагрузкой (Планировщик заданий, задача "BuyerAnons Bot"), можно запускать и вручную:
#   powershell -ExecutionPolicy Bypass -File start_bot.ps1
# Если бот упал - перезапускается через 30 секунд. Логи: bot_error.log (предыдущий запуск - bot_error.prev.log).

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
Set-Location $root

function Get-BotProcess {
    Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" |
        Where-Object { $_.CommandLine -like '*run_bot.py*' }
}

# Второй экземпляр нельзя: Telegram отдаёт обновления только одному (Conflict на getUpdates)
if (Get-BotProcess) {
    Write-Output "BuyerAnons bot is already running - exit"
    exit 0
}

$python = (Get-Command python -ErrorAction Stop).Source
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'

while ($true) {
    foreach ($name in 'bot_error', 'bot_output') {
        $log = Join-Path $root "$name.log"
        if (Test-Path $log) { Move-Item $log (Join-Path $root "$name.prev.log") -Force }
    }

    $proc = Start-Process -FilePath $python -ArgumentList '-W', 'ignore', 'run_bot.py' `
        -WorkingDirectory $root -WindowStyle Hidden -PassThru -Wait `
        -RedirectStandardOutput (Join-Path $root 'bot_output.log') `
        -RedirectStandardError (Join-Path $root 'bot_error.log')

    Add-Content (Join-Path $root 'bot_restarts.log') "$(Get-Date -Format s) bot exited with code $($proc.ExitCode), restarting in 30s"
    Start-Sleep -Seconds 30
}
