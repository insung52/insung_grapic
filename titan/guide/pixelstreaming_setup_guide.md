> ⚠️ [guide/ 이관 시 경고, 2026-08-31] 2026-07-06 기준 작성 — 이후 프로젝트는 RTSP 송출
> (`_archive/structure_README_track_index.md` 트랙1, `RtspEncoder` 플러그인)로 방향이 잡혔음. Pixel Streaming이
> 지금도 실사용 경로인지 확인 필요.

# Pixel Streaming 로컬 테스트 가이드 (2026-07-06)

언리얼 화면을 웹 브라우저로 스트리밍하는 Pixel Streaming을 로컬에서 테스트하는 방법.
`C:\tools\PixelStreamingInfrastructure`에 Epic 공식 인프라 레포([EpicGames/PixelStreamingInfrastructure](https://github.com/EpicGames/PixelStreamingInfrastructure))를
클론해서 사용 중 (LIG 쪽 프로토콜은 아직 미정, 일단 로컬 동작 확인 목적).

## 1. 시그널링 서버 (최초 1회 setup + 매번 start)

```
cd C:\tools\PixelStreamingInfrastructure\SignallingWebServer\platform_scripts\cmd

.\setup.bat   # 최초 1회 — Node.js 다운로드 + npm install + 프론트엔드 빌드 (몇 분 걸림)
.\start.bat   # 매번 — 서버 시작 (계속 떠있는 프로세스, 창 닫으면 서버 종료됨)
```

`start.bat` 실행하면 콘솔에 아래처럼 포트 정보가 찍힘 (기본값):

```
"streamer_port": "8888"   ← 언리얼(스트리머)이 붙는 포트
"player_port": "80"       ← 웹 브라우저(시청자)가 붙는 포트 (http://localhost)
"sfu_port": "8889"
"https_port": 443
```

## 2. 언리얼 쪽 — 스트리머로 붙이기

프로젝트의 `.uproject`에 `PixelStreaming` 플러그인이 활성화되어 있어야 함 (TankSim은 이미 켜져있음).

**에디터에서 Standalone Game으로 실행 (권장)**:
1. 에디터 Play 버튼 옆 드롭다운 화살표 클릭 → **Standalone Game** 모드 선택
2. 같은 드롭다운의 **Advanced Settings...** (또는 Edit > Editor Preferences에서 "Play" 검색)
3. **Additional Launch Parameters**에 아래 추가:
   ```
   -PixelStreamingURL=ws://127.0.0.1:8888
   ```
4. Play 클릭 → 별도 게임 창이 뜨면서 자동으로 시그널링 서버에 스트리머로 연결됨

**커맨드라인으로 직접 실행하는 방법도 있음** (패키징 없이 소스에서 바로 `-game` 모드 실행):
```
"C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe" "<프로젝트>.uproject" -game -PixelStreamingURL=ws://127.0.0.1:8888
```
단, 이 방식은 한 번 "모듈을 리빌드해야 한다"는 다이얼로그가 뜨면서 실패한 적 있음 — 에디터에서
Standalone Game으로 켜는 쪽이 더 안정적으로 됨 (이미 로드된 모듈을 그대로 씀).

## 3. 브라우저로 확인

`http://localhost` 접속 (같은 PC면 이대로, 다른 PC/기기에서 보려면 시그널링 서버 PC의 IP로 접속).

## 4. 참고

- 사용 중인 플러그인은 `PixelStreaming`(레거시, UE 5.8에도 여전히 포함)이고 `PixelStreaming2`(신규)가 아님 —
  둘 다 엔진에 같이 들어있으니 프로젝트가 어느 쪽을 켜놨는지 `.uproject` 확인 필요.
  레거시 플러그인 기준 커맨드라인 인자는 `-PixelStreamingURL=`(전체 URL) 또는
  `-PixelStreamingIP=` + `-PixelStreamingPort=`(분리형) 둘 다 지원함
  (`Engine/Plugins/Media/PixelStreaming/Source/PixelStreaming/Private/Settings.cpp` 참고).
- 시그널링 서버 콘솔 창을 닫으면 스트리밍도 끊김 — 백그라운드로 계속 띄워두고 써야 함.
- `setup.bat`는 최초 1회만 하면 되고, 이후엔 `start.bat`만 실행하면 됨.
