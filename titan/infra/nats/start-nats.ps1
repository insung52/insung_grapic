# titan NATS/JetStream 로컬 개발 서버 기동 스크립트
# 재사용법: 그냥 이 스크립트를 실행하면 됨. `& .\start-nats.ps1`
#
# 바이너리는 기본적으로 사용자 Downloads 폴더에 이미 받아둔 v2.14.4를 그대로 사용.
# 다른 컴퓨터에서 돌리는 거라 그 경로에 바이너리가 없으면, 같은 버전(v2.14.4)을
# https://github.com/nats-io/nats-server/releases/tag/v2.14.4 에서 받아 압축 풀고
# -NatsServerPath 로 경로를 넘기면 됨.

param(
    [string]$NatsServerPath = "C:\Users\user\Downloads\nats-server-v2.14.4-windows-amd64\nats-server-v2.14.4-windows-amd64\nats-server.exe"
)

$ConfigPath = Join-Path $PSScriptRoot "nats-server.conf"

if (-not (Test-Path $NatsServerPath)) {
    Write-Error "nats-server.exe not found at $NatsServerPath. Pass -NatsServerPath, or download nats-server v2.14.4 for windows-amd64."
    exit 1
}

if (-not (Test-Path $ConfigPath)) {
    Write-Error "Config not found at $ConfigPath"
    exit 1
}

Write-Host "Starting titan NATS/JetStream server..."
Write-Host "  binary: $NatsServerPath"
Write-Host "  config: $ConfigPath"
Write-Host "  client port: 4222, monitoring: http://localhost:8222"

& $NatsServerPath -c $ConfigPath
