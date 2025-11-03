param(
  [int]$MinMinutes = 15,   # 최소 간격(분)
  [int]$MaxMinutes = 40,   # 최대 간격(분)
  [switch]$Once            # -Once 주면 1회만 실행
)

try {
  chcp 65001 | Out-Null
  [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
  $env:PYTHONIOENCODING = "utf-8"
} catch {}


# --- 0) 작업 디렉터리/로그 경로 ---
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
$newline = [Environment]::NewLine
$logsDir = Join-Path $Root "output\logs"
New-Item -ItemType Directory -Force -Path $logsDir | Out-Null

# --- 1) .venv 활성화(있으면) ---
$activate = Join-Path $Root ".venv\Scripts\Activate.ps1"
if (Test-Path $activate) { . $activate }

# --- 2) 환경 변수(단일 계정 고정) ---
$env:PROFILE = "main"
$env:DRY_RUN = "1"    # 실업로드 방지(메타 연결될 때까지 유지)

# --- 3) 한 번 실행 ---
function Run-Once {
  $stamp = (Get-Date).ToString("yyyyMMdd_HHmmss")
  $logFile = Join-Path $logsDir "run_$stamp`_main.log"

  Write-Host "[$stamp] PROFILE=main 실행" -ForegroundColor Cyan
  try {
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = "python"
    $psi.Arguments = ".\main.py"
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError  = $true
    $psi.UseShellExecute = $false

    $p = [System.Diagnostics.Process]::Start($psi)
    $stdout = $p.StandardOutput.ReadToEnd()
    $stderr = $p.StandardError.ReadToEnd()
    $p.WaitForExit()

    $content = "=== PROFILE=main ===$newline$stdout$newline--- STDERR ---$newline$stderr"
    $content | Out-File -FilePath $logFile -Encoding UTF8

    if ($p.ExitCode -eq 0) {
      Write-Host "완료: $logFile" -ForegroundColor Green
    } else {
      Write-Warning "오류 종료 코드: $($p.ExitCode) (로그: $logFile)"
    }
  } catch {
    $_ | Out-String | Out-File -FilePath $logFile -Encoding UTF8
    Write-Warning "예외 발생 (로그: $logFile)"
  }
}

# --- 4) 루프 ---
if ($Once) { Run-Once; exit 0 }

while ($true) {
  Run-Once
  $delay = Get-Random -Minimum ($MinMinutes*60) -Maximum ($MaxMinutes*60)
  $hhmm = "{0:00}:{1:00}" -f ([math]::Floor($delay/3600)), (([math]::Floor($delay/60)) % 60)
  Write-Host "다음 실행까지 대기: 약 $hhmm (총 $([math]::Round($delay/60))분)" -ForegroundColor Yellow
  Start-Sleep -Seconds $delay
}
