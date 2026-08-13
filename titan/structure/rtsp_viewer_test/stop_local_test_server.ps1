<#
.SYNOPSIS
    start_local_test_server.ps1으로 띄운 mediamtx + gst-launch-1.0 프로세스들을 정리한다.
#>
$ErrorActionPreference = "SilentlyContinue"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PidFile = Join-Path $ScriptDir "tools\local_server.pids.json"

if (-not (Test-Path $PidFile)) {
    Write-Host "[INFO] 실행 중인 로컬 테스트 서버 기록(pid file)이 없습니다. 할 일 없음."
    exit 0
}

$procs = Get-Content $PidFile -Raw | ConvertFrom-Json

foreach ($prop in $procs.PSObject.Properties) {
    $name = $prop.Name
    $procId = $prop.Value
    $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
    if ($proc) {
        Write-Host "[INFO] 종료: $name (PID $procId)"
        Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
    } else {
        Write-Host "[INFO] 이미 종료됨: $name (PID $procId)"
    }
}

Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
Write-Host "[OK] 로컬 RTSP 테스트 서버 정리 완료."
