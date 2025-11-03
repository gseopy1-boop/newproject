# 프로젝트 루트 기준
$Root = (Get-Location).Path
$TaskName = "StartDesk-AutoRunLoop"
$PsExe = (Get-Command powershell.exe).Source
$Script = Join-Path $Root "run_loop.ps1"

# 작업 인자: -ExecutionPolicy Bypass -File .\run_loop.ps1  (루프 모드)
$Args = "-ExecutionPolicy Bypass -File `"$Script`""

# 기존 있으면 제거
schtasks /Delete /TN $TaskName /F 2>$null | Out-Null

# 현재 사용자 로그온 시 자동 실행
schtasks /Create /TN $TaskName /SC ONLOGON /RL LIMITED /TR "`"$PsExe`" $Args" /F

Write-Host "✅ 작업 생성: $TaskName (로그온 시 자동 실행)"
