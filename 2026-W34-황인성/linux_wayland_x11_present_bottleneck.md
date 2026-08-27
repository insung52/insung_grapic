# 리눅스 패키지 빌드 프레임 폭락 — 원인과 해결 (2026-08-19)

## 요약

- **증상**: 리눅스 패키지 빌드를 풀스크린(QHD, 2560×1440)으로 띄우면 11fps까지 폭락. 창모드+저해상도는 100~200fps로 정상. 동일 조건 Windows PC에서는 재현 안 됨.
- **원인**: UE Linux 클라이언트(SDL2)가 아무 설정도 안 주면 **Wayland 세션에서도 X11 백엔드를 먼저 고르고**(SDL2의 기본 드라이버 우선순위 자체가 그렇게 생김), GNOME이 X11 호환을 위해 항상 같이 띄워두는 **Xwayland**를 통해 조용히 성공해버림. 이 경로에서 Vulkan Present가 GPU 다이렉트 버퍼 공유(DRI3) 대신 X11 프로토콜 소켓을 통한 **소프트웨어 카피**로 동작해서, 그 복사 비용이 화면 해상도(픽셀 수)에 비례해 커짐.
- **해결**: `Config/Linux/LinuxEngine.ini`에 `[Linux.SDL] VideoDriver=wayland`를 설정해 기본 실행을 네이티브 Wayland로 강제. Wayland가 없는 환경(X11 전용)을 위해 `-sdlvideodriver=x11`로 이 기본값을 뒤집는 별도 실행 스크립트(`titan_example_x11_fallback.sh`)를 같이 배포. (배포 시 수동으로 포함 필요)
- **RTSP와는 무관함**: 처음엔 프로젝트의 `RtspEncoder` 플러그인(다중 카메라 스트리밍)을 의심했으나, RTSP를 통째로 비활성화한 빌드로도 증상이 동일하게 재현되어 배제됨. 아래 "왜 처음에 RTSP를 의심했는가" 참고.

---

## 증상

- 리눅스 패키지 빌드(`titan_example.sh -fullscreen`)에서 풀스크린 QHD 실행 시 **11fps**
- 창모드 + 낮은 해상도로 띄우면 **100~200fps**로 정상
- `kadex_lobby`(거의 빈 레벨)와 `kadex_test`(오브젝트 다수)에서 **동일하게 느림** → 씬 복잡도와 무관한 병목
- 동일 조건 Windows PC(RTX 5060, RAM 32GB)에서는 **재현 안 됨** — 이 플랫폼(Linux+SDL2+X11/Wayland) 고유 이슈

## 배제된 원인들

| 후보 원인 | 확인 방법 | 결과 |
|---|---|---|
| 디스크(HDD) | `lsblk -d -o NAME,ROTA`, `df -h` | 배제 — NVMe SSD에서 실행 중 |
| RAM 부족/스와핑 | `free -h`, GNOME System Monitor | 배제 — Swap 항상 0 bytes |
| GPU 연산 병목 | `nvidia-smi`, `stat gpu` | 배제 — 저프레임 상태에서도 GPU 사용률 10~40%, GPU는 한가함 |
| 씬 렌더링 복잡도 | Unreal Insights (`SceneRenderBuilder_Render` 등) | 배제 — 실제 렌더 패스 시간은 전부 정상 범위(수백 µs~수 ms) |
| Vulkan Present/VSync 자체 | `r.vsync 0`, `__GL_SYNC_TO_VBLANK=0`, exclusive fullscreen | 배제 — 다 테스트했으나 증상 그대로 |
| GPU 전력상태(P-state) | Persistence mode 켜도 P5 유지 확인 | 배제 — P0는 결과일 뿐 원인 아님 |
| **RTSP 네트워크 전송** | RTSP 기능 전체 비활성화 빌드로 재현 테스트 | **배제** — 증상 동일 재현. 네트워크 syscall 시간도 32.5ms로 무시할 수준 |

## 결정적 증거

**1. `perf record -g` 콜스택** (RHIThread, 10초 샘플링, 52508 샘플) — 압도적 1위(68.40%)가 렌더링도 GPU 드라이버도 아니라 소켓 write 경로:

```
__x64_sys_writev (68.40%)
 └─ do_writev → vfs_writev → do_iter_readv_writev
     └─ sock_write_iter
         └─ unix_stream_sendmsg          ← AF_UNIX 소켓 (네트워크 아닌 로컬 IPC)
             └─ skb_copy_datagram_from_iter (64.81%)
                 └─ copy_page_from_iter (60.45%)
                     └─ _copy_from_iter (60.39%)
```

**2. 유저스페이스 호출 체인** (`perf report --stdio`):

```
68.40%  RHIThread  libc.so.6      [.] __GI___writev
        RHIThread  libxcb.so.1.1.0  [.] (X11 프로토콜 클라이언트 라이브러리 심볼)
```

→ RHIThread가 `libxcb`(X11 프로토콜 클라이언트 라이브러리)를 거쳐 X 서버와 직접 통신 중이었음이 콜스택으로 확정됨. 렌더러 자체 코드와 NVIDIA 드라이버 코드는 합쳐서 5% 미만.

**3. 실증 테스트**: `SDL_VIDEODRIVER=wayland`로 강제 전환 → 풀스크린 QHD에서 **200fps 이상 회복 확인**.

## 원인 분석

이 시스템은 GNOME(Wayland) 데스크톱이지만, X11 전용 앱도 그냥 돌아가게 해주는 호환 레이어인 **Xwayland**가 백그라운드에서 항상 같이 실행되고 있다. UE Linux 클라이언트(SDL2 기반)는 아무 오버라이드도 없으면 SDL2 자체의 기본 드라이버 우선순위를 그대로 따르는데, **SDL2는 역사적으로 X11을 Wayland보다 먼저 시도한다**(Wayland 백엔드가 X11보다 한참 늦게 추가돼서 오랫동안 "차선책" 취급이었던 게 이유). Xwayland가 항상 떠있으니 SDL이 X11을 골라도 창은 문제없이 뜨고 — **에러 없이 조용히 "느리게" 성공**해버려서, 프로파일링 전엔 아무도 눈치채지 못했다.

이 Xwayland 경유 경로에서는 Vulkan WSI Present가 GPU 다이렉트 버퍼 공유(DRI3) 대신 X11 프로토콜 소켓을 통한 소프트웨어 카피로 동작한 것으로 보이며, 그 복사 비용이 프레임 해상도(픽셀 수)에 정비례해서 커진다. 이는 관찰된 모든 증상과 정확히 일치한다:

- 해상도에 비례해서 느려짐 (풀스크린 QHD ↔ 축소 창모드)
- 씬 복잡도와 무관 (복사량은 화면 픽셀 수로만 결정됨)
- GPU는 한가하고 CPU(RHIThread) 한 코어만 100% (병목이 렌더링이 아니라 Present 단계의 데이터 카피이므로)
- RTSP/네트워크/GPU전력과 무관 (Xwayland 관련 로컬 IPC 문제였으므로)

**중요**: 이건 UE 패키징이나 이 프로젝트 코드의 버그가 아니다 — UE는 오버라이드가 없을 때 SDL2한테 선택을 통째로 맡기고, SDL2의 기본 우선순위가 원래 이렇게 생겨먹었다. 아래 해결책은 그 기본값을 명시적으로 뒤집어주는, UE가 정식으로 제공하는 메커니즘을 쓴다.

## 왜 처음에 RTSP를 의심했는가

이 조사는 원래 `RtspEncoder` 플러그인(UGV/자체방호축 다중 카메라 RTSP 스트리밍)의 지연 최적화 작업 도중 발견됐다. `RtspStreamComponent`의 Vulkan 인코더 경로(`FNvencVulkanEncoder`)가 렌더스레드를 매 프레임 블로킹하는 별개의 실제 버그(`SubmitAndBlockUntilGPUIdle()` 과다 사용, 스코프 펜스로 수정됨)를 갖고 있었던 데다, `kadex_lobby`(RTSP 스트림이 실제로는 하나도 등록 안 되는 레벨)에서도 저프레임이 재현되면서 "RTSP 서버 서브시스템 자체가 원인 아닐까"라는 작업 가설이 한동안 유력하게 다뤄졌다. `RtspEncoder` 플러그인을 통째로 비활성화(모듈 의존성 제거 + `TITAN_RTSP_ENABLED=0`)한 빌드로도 동일 증상이 재현되면서 이 가설은 배제됐고, 곧이어 위 `perf`/`strace` 분석으로 진짜 원인(Xwayland Present 경로)이 확정됐다.

## 해결 방법 (구현됨)

UE 엔진이 이미 제공하는 SDL 비디오 드라이버 오버라이드 우선순위(`Engine/Source/Runtime/ApplicationCore/Private/Linux/LinuxPlatformApplicationMisc.cpp`: 커맨드라인 > env var > **INI** > SDL 기본값)를 그대로 활용 — 실행 스크립트(`titan_example.sh`)는 패키징할 때마다 새로 생성돼서 덮어써지므로, 그 파일을 직접 고치는 방식은 채택하지 않았다.

**1. 기본값 — `Config/Linux/LinuxEngine.ini`** (프로젝트에 커밋, 패키징 시 자동으로 쿡됨):
```ini
[Linux.SDL]
VideoDriver=wayland
```
`./titan_example.sh`를 그냥 실행해도 기본으로 네이티브 Wayland로 뜬다. 다만 이건 무조건 wayland를 강제하는 정적 설정이라, Wayland 컴포지터가 없는 순수 X11 머신에서 그대로 실행하면 SDL 초기화가 실패한다(폴백 없음).

**2. X11 전용 환경 대비 — `titan_example_x11_fallback.sh`** (프로젝트 루트에 커밋):
```bash
#!/bin/bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$SCRIPT_DIR/titan_example.sh" -sdlvideodriver=x11 "$@"
```
`-sdlvideodriver=x11` 커맨드라인 오버라이드(env var/INI보다 항상 우선)로 위 INI의 wayland 강제를 명시적으로 뒤집는다. LIG처럼 Wayland 없는 구형 환경에 배포할 때 이 스크립트를 씀.

**주의**: `titan_example_x11_fallback.sh`는 UE 패키징이 자동으로 포함해주는 파일이 아니다 — 패키지 결과물(`titan_example.sh`가 있는 폴더)에 매번 수동으로 같이 복사해서 배포해야 한다.

## 아직 안 한 것 / 남은 확인 사항

- **순수 X11(Xorg) 세션 테스트**: 지금까지는 "Xwayland 경유 X11"이 느리다는 것만 확인됨. Wayland 없이 완전히 X11로만 붙는 세션(로그인 화면에서 "Ubuntu on Xorg")에서도 정상 속도가 나오는지 확인해서, 문제가 "Xwayland 번역 계층" 자체인지 "X11 백엔드 자체"인지 한 번 더 구분해두면 좋음. `titan_example_x11_fallback.sh`로 재현/확인 가능.
- **근본 원인(선택사항, 낮은 우선순위)**: 왜 이 NVIDIA 드라이버+Xwayland 조합에서 DRI3 다이렉트 버퍼 공유가 안 되고 소프트웨어 카피로 폴백되는지는 추가로 팔 수 있으나, 위 우회책으로 실사용에는 문제없음.

## 참고 — 사용한 진단 도구

- `htop`, GNOME System Monitor: CPU 코어별/스레드별, 메모리/스왑, 네트워크 실시간 확인
- `nvidia-smi`, `nvtop`: GPU 사용률/전력/P-state/VRAM
- Unreal Insights (`-trace=cpu,gpu,frame,bookmark,rendercommands -statnamedevents`): GPU/CPU 타임라인 상세 분석
- `perf top -p <PID>`, `perf record -g` + `perf report --stdio -g graph,0.5,caller`: 함수/콜스택 레벨 CPU 프로파일링 (최종 원인 특정에 결정적)
- `strace -p <PID> -c` / `-e trace=...` / `-k`: syscall 레벨 분석
- `ss -tnp`, `lsof -p <PID> -a -i`(인터넷 소켓) / `-a -U`(Unix 소켓): 프로세스별 열린 소켓 확인

## 관련 파일

- `titan_example/Config/Linux/LinuxEngine.ini` — Wayland 기본값 설정
- `titan_example/titan_example_x11_fallback.sh` — X11 강제 대체 실행 스크립트
- `titan_example/RTSP_Perf_Investigation.md` — 이 조사의 원본 진행 로그(조사 과정 그대로, 시행착오 포함)
- `rtsp/rtsp_latency_investigation.md`, `rtsp/rtsp_client_reception_guide.md` — 별개 주제(RTSP 자체의 종단 지연 최적화, GStreamer 수신 가이드)
