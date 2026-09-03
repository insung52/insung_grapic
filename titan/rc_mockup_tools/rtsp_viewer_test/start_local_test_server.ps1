<#
.SYNOPSIS
    로컬 RTSP 테스트 서버를 띄운다 (실제 UGV RTSP 서버가 아직 없을 때, 뷰어/클라이언트
    개발·검증용).

.DESCRIPTION
    1) mediamtx(경량 RTSP 서버, tools\mediamtx.exe)를 백그라운드로 실행 (rtsp://127.0.0.1:8564)
    2) GStreamer(videotestsrc, 이미 시스템에 설치돼 있음: gst-launch-1.0)로 5개의 UGV축
       스트림(front_cctv/rear_cctv/left_cctv/right_cctv/rcws_viewer, protocol_icd.md §3.3)
       이름에 맞는 테스트 패턴 영상을 생성해서 mediamtx로 RTSP RECORD(publish)한다.
       스트림마다 다른 testsrc 패턴 + 스트림 이름 텍스트 오버레이를 넣어서 rtsp_test_client.py로
       각 스트림이 실제로 구분되는지 눈으로도 확인 가능.

    이 스크립트가 만드는 것은 어디까지나 "테스트용 가짜 RTSP 서버"다. 실제 UGV 시뮬레이션
    SW가 RTSP 서버(NVENC+GStreamer로 인코딩)를 완성하면 이 스크립트는 더 이상 필요 없고,
    rtsp_test_client.py의 URL(--base 또는 streams_config.json)만 실제 서버 주소로 바꾸면 된다.

.PARAMETER Port
    mediamtx가 리슨할 RTSP 포트. 기본 8564 — protocol_icd.md §3.3의 잠정 포트(8554)와는
    "일부러" 다르게 둠 (이유는 스크립트 본문 주석/README.md §4 참고: 이 컴퓨터에서 병행
    진행 중인 다른 세션의 UE RTSP PoC가 로컬 8554를 쓰고 있어서 충돌 방지).

.PARAMETER Width / Height / Fps
    테스트 패턴 해상도/프레임레이트. 기본 1280x720 @ 30fps.

.EXAMPLE
    .\start_local_test_server.ps1
    .\start_local_test_server.ps1 -Port 8564 -Width 640 -Height 480 -Fps 15
#>
param(
    [int]$Port = 8564,
    [int]$Width = 1280,
    [int]$Height = 720,
    [int]$Fps = 30
)
# 주의: 기본 포트를 protocol_icd.md 잠정 포트(8554)가 아니라 8564로 둠 - 이 컴퓨터에서
# 다른 세션이 titan_example UE 프로젝트의 실제 RTSP PoC(rtsp_poc_findings.md, VLC로
# rtsp://127.0.0.1:8554/poc/stream0 테스트 중)를 같은 127.0.0.1:8554에서 병행 작업 중이라,
# 이 로컬 가짜 서버가 그 포트를 점유하면 그쪽 클라이언트(VLC 등)가 실수로 이 가짜 서버에
# 붙어버리는 충돌이 생김(실제로 테스트 중 관측됨). 로컬 검증용 포트는 8564로 분리해서 절대
# 겹치지 않게 함 - 실제 UGV 서버(§3.3, IP 확정 192.168.10.10, 포트는 8554로 잠정)에 붙일 때는
# --base로 그쪽 실제 주소/포트를 지정하면 되므로 이 분리는 클라이언트 사용에 영향 없음.

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ToolsDir = Join-Path $ScriptDir "tools"
$LogsDir = Join-Path $ScriptDir "logs"
$PidFile = Join-Path $ToolsDir "local_server.pids.json"

New-Item -ItemType Directory -Force -Path $LogsDir | Out-Null

# --- GStreamer 위치 확인 (RtspEncoder PoC 트랙에서 이미 설치해둔 것을 재사용, env var 우선) ---
$GstRoot = $env:GSTREAMER_1_0_ROOT_MSVC_X86_64
if (-not $GstRoot) {
    $GstRoot = "C:\Program Files\gstreamer\1.0\msvc_x86_64"
}
$GstLaunch = Join-Path $GstRoot "bin\gst-launch-1.0.exe"
if (-not (Test-Path $GstLaunch)) {
    Write-Error "gst-launch-1.0.exe를 찾을 수 없습니다: $GstLaunch`n환경변수 GSTREAMER_1_0_ROOT_MSVC_X86_64를 GStreamer 설치 경로로 설정하거나, 직접 설치하세요 (https://gstreamer.freedesktop.org/download/ , MSVC 64-bit, 'Complete' 옵션)."
}

# --- mediamtx 확인 ---
$MediaMtxExe = Join-Path $ToolsDir "mediamtx.exe"
$MediaMtxYml = Join-Path $ToolsDir "mediamtx.yml"
if (-not (Test-Path $MediaMtxExe)) {
    Write-Error "mediamtx.exe가 없습니다: $MediaMtxExe`n다운로드: https://github.com/bluenviron/mediamtx/releases (windows_amd64.zip) 후 tools\ 안에 압축 해제하세요."
}

# 이미 떠 있는 이전 세션 정리
if (Test-Path $PidFile) {
    Write-Host "[INFO] 이전 로컬 테스트 서버가 남아있는 것 같습니다 - 먼저 stop_local_test_server.ps1을 실행합니다."
    & (Join-Path $ScriptDir "stop_local_test_server.ps1")
    Start-Sleep -Seconds 1
}

$procs = @{}

# --- 1) mediamtx 실행 ---
Write-Host "[INFO] mediamtx 실행 중 (RTSP :$Port) ..."
$mediamtxLog = Join-Path $LogsDir "mediamtx.log"
$mtxProc = Start-Process -FilePath $MediaMtxExe -ArgumentList @($MediaMtxYml) `
    -WorkingDirectory $ToolsDir `
    -RedirectStandardOutput $mediamtxLog -RedirectStandardError (Join-Path $LogsDir "mediamtx.err.log") `
    -WindowStyle Hidden -PassThru
$procs["mediamtx"] = $mtxProc.Id
Start-Sleep -Seconds 2

if ($mtxProc.HasExited) {
    Write-Error "mediamtx가 바로 종료됐습니다. 로그 확인: $mediamtxLog"
}

# --- 2) 5개 UGV축 스트림용 테스트 패턴을 GStreamer로 publish ---
# protocol_icd.md §3.3: 전면CCTV/후면CCTV/좌측CCTV/우측CCTV/RCWS뷰어
# testsrc pattern 번호는 스트림마다 다르게 줘서(시각적으로) 구분되게 함.
# textoverlay 표시용 라벨은 ASCII로만 둔다 (한글은 gst-launch 인자 인코딩/폰트 렌더링
# 경로에서 깨질 수 있어서 - 실제 한글 이름은 streams_config.json의 "label"에만 둠).
$streams = @(
    @{ Name = "front_cctv";  Label = "FRONT CCTV";  Pattern = 0 },  # smpte
    @{ Name = "rear_cctv";   Label = "REAR CCTV";    Pattern = 1 },  # snow
    @{ Name = "left_cctv";   Label = "LEFT CCTV";    Pattern = 18 }, # ball
    @{ Name = "right_cctv";  Label = "RIGHT CCTV";   Pattern = 11 }, # circular
    @{ Name = "rcws_viewer"; Label = "RCWS VIEWER";  Pattern = 19 }  # smpte100
)

# mediamtx가 RECORD 요청을 처리할 준비가 완전히 끝나기 전에 여러 publisher가 거의 동시에
# 붙으면 간헐적으로 "Resource not found"로 즉시 죽는 경우가 관찰됨(로컬 테스트 서버 특유의
# 레이스로 보임, 실제 UGV RTSP 서버와는 무관). 스트림 하나씩 순차로 붙이고, 붙인 직후
# 프로세스가 바로 죽었으면(=publish 실패) 최대 2회까지 재시도해서 흡수한다.
$MaxRetriesPerStream = 3

foreach ($s in $streams) {
    $name = $s.Name
    $label = $s.Label
    $pattern = $s.Pattern
    $url = "rtsp://127.0.0.1:$Port/$name"
    $log = Join-Path $LogsDir "gst_$name.log"
    $errLog = Join-Path $LogsDir "gst_$name.err.log"

    # videotestsrc(패턴) -> timeoverlay(시계, 프레임 도착을 눈으로도 확인) -> textoverlay(스트림 이름)
    # -> x264enc(zerolatency) -> h264parse -> rtspclientsink(RECORD로 mediamtx에 publish)
    $pipeline = @(
        "videotestsrc", "pattern=$pattern", "is-live=true", "!",
        "video/x-raw,width=$Width,height=$Height,framerate=$Fps/1", "!",
        "timeoverlay", "halignment=left", "valignment=top", "!",
        "textoverlay", "text=`"$label`"", "halignment=center", "valignment=bottom", "font-desc=`"Sans 24`"", "!",
        "videoconvert", "!",
        "x264enc", "tune=zerolatency", "bitrate=2000", "speed-preset=ultrafast", "key-int-max=$Fps", "!",
        "h264parse", "!",
        "rtspclientsink", "location=$url", "protocols=tcp"
    )

    $started = $false
    for ($attempt = 1; $attempt -le $MaxRetriesPerStream; $attempt++) {
        Write-Host "[INFO] publish 시작: $name -> $url (pattern=$pattern, 시도 $attempt/$MaxRetriesPerStream)"
        $p = Start-Process -FilePath $GstLaunch -ArgumentList $pipeline `
            -RedirectStandardOutput $log -RedirectStandardError $errLog `
            -WindowStyle Hidden -PassThru
        # 즉시 죽는 경우(예: publish 거부)뿐 아니라 잠깐 붙었다가 1~2초 뒤 끊기는 경우도
        # 있어서(로컬 소프트웨어 인코딩 5개 동시 구동 특유의 과도기적 부하) 두 단계로 확인.
        Start-Sleep -Milliseconds 800
        if ($p.HasExited) {
            Write-Host "[WARN] $name publish가 바로 종료됨 (재시도) - 로그: $errLog"
            Start-Sleep -Milliseconds 500
            continue
        }
        Start-Sleep -Milliseconds 1800
        if (-not $p.HasExited) {
            $procs[$name] = $p.Id
            $started = $true
            break
        }
        Write-Host "[WARN] $name publish가 시작 직후 끊김 (재시도) - 로그: $errLog"
        Start-Sleep -Milliseconds 500
    }
    if (-not $started) {
        Write-Warning "$name : $MaxRetriesPerStream 회 재시도에도 publish 실패. $errLog 확인 필요."
    }
}

$procs | ConvertTo-Json | Set-Content -Path $PidFile -Encoding UTF8

Start-Sleep -Seconds 2
Write-Host ""
Write-Host "[OK] 로컬 RTSP 테스트 서버 준비 완료. 아래 URL로 테스트하세요:"
foreach ($s in $streams) {
    Write-Host ("   rtsp://127.0.0.1:{0}/{1}   ({2})" -f $Port, $s.Name, $s.Label)
}
Write-Host ""
Write-Host "예:  python rtsp_test_client.py --config streams_config.json --duration 10 --snapshot"
Write-Host "중지: .\stop_local_test_server.ps1"
Write-Host "로그: $LogsDir"
