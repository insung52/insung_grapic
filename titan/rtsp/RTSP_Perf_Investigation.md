# 리눅스 성능 저하 조사 보고서 — 원인 확정 (2026-08-19)

## 결론 요약

**원인: UE Linux 클라이언트(SDL2)가 기본적으로 X11 백엔드(Xwayland 경유)로 창을 띄우고, RHIThread의 프레젠트(Present) 경로가 `libxcb`(X11 프로토콜 클라이언트 라이브러리)를 통해 매 프레임 대량의 데이터를 Unix 도메인 소켓으로 X 서버에 동기 전송하고 있었음. 이 전송 비용이 해상도에 비례해서 폭증하며 풀스크린(QHD)에서 CPU(RHIThread) 병목으로 프레임이 폭락함.**

**해결책: 환경변수로 네이티브 Wayland 백엔드 강제**
```bash
SDL_VIDEODRIVER=wayland ./titan_example.sh -fullscreen
```
적용 후 kadex_lobby 풀스크린(QHD) 기준 **200fps 이상 회복 확인됨.**

## 증상 (해결 전)

- 리눅스 패키지 빌드에서 풀스크린(QHD, 2560x1440) 실행 시 **11fps**까지 프레임 폭락
- 창모드 + 저해상도는 **100~200fps**로 정상
- `kadex_lobby`(거의 빈 레벨)와 `kadex_test`(오브젝트 다수)에서 동일하게 느림 → 씬 복잡도와 무관
- 동일 조건 Windows PC(RTX 5060/32GB)에서는 재현 안 됨 (Windows는애초에 이 문제 자체가 존재하지 않는 플랫폼별 이슈)

## 조사 과정 요약 (배제된 가설들)

| 후보 원인 | 결과 |
|---|---|
| 디스크 (HDD) | 배제 — 프로젝트는 NVMe SSD에서 실행 중 |
| RAM 부족 / 스와핑 | 배제 — Swap 항상 0 bytes |
| GPU 연산 병목 | 배제 — 저프레임 상태에서도 GPU 사용률 10~40%, 전력 20W대/220W (GPU는 한가했음) |
| 씬 렌더링 복잡도 | 배제 — Unreal Insights로 확인한 실제 렌더 패스 시간은 전부 정상 범위 |
| Vulkan Present / VSync 자체 | 배제 — `r.vsync 0`, `__GL_SYNC_TO_VBLANK=0`, exclusive fullscreen 다 테스트했으나 무효 |
| RTSP 네트워크 전송 | 배제 — RTSP 기능 전체 비활성화 빌드로도 문제 동일 재현. 네트워크(TCP/UDP) syscall 시간은 32.5ms로 무시할 수준 |
| GPU 전력상태(P-state)/Persistence mode | 배제 — Persistence mode 켜도 P5 유지. P0는 결과일 뿐 원인 아니었음 |
| Unreal Insights 트레이스 옵션 오염 | 배제 — 확인 결과 최종 테스트 시 `-trace` 옵션 없었음 |

## 결정적 증거

**1. `perf record -g` 콜스택** (RHIThread, 10초 샘플링, 52508 샘플):
```
__x64_sys_writev (68.40%)
 └─ do_writev → vfs_writev → do_iter_readv_writev
     └─ sock_write_iter
         └─ unix_stream_sendmsg          ← AF_UNIX 소켓 (네트워크 아닌 로컬 IPC)
             └─ skb_copy_datagram_from_iter (64.81%)
                 └─ copy_page_from_iter (60.45%)
                     └─ _copy_from_iter (60.39%)
```

**2. 유저스페이스 호출 체인 확인** (`perf report --stdio`):
```
68.40%  RHIThread  libc.so.6      [.] __GI___writev
        RHIThread  libxcb.so.1.1.0  [.] (X11 프로토콜 클라이언트 라이브러리 심볼)
```
→ RHIThread가 `libxcb`를 거쳐 X 서버와 직접 통신 중이었음이 콜스택으로 확정.

**3. 실증 테스트**: `SDL_VIDEODRIVER=wayland`로 강제 전환 → 풀스크린 QHD에서 200fps+ 회복.

## 원인 분석

이 시스템은 GNOME(Wayland) 데스크톱이지만 `Xwayland`(X11 호환 레이어)가 백그라운드에서 함께 실행되고 있었고, UE Linux 클라이언트(SDL2 기반)는 기본값으로 X11 백엔드를 선택해 Xwayland를 통해 창을 띄우고 있었다. 이 경로에서는 Vulkan WSI 프레젠트가 GPU 다이렉트 버퍼 공유(DRI3) 대신, X11 프로토콜 소켓을 통한 소프트웨어 카피 경로로 동작한 것으로 보이며, 그 복사 비용이 프레임 해상도(픽셀 수)에 정비례해서 커졌다. 이는 지금까지 관찰된 모든 증상과 정확히 일치한다:

- 해상도에 비례해서 느려짐 (풀스크린 QHD ↔ 축소 창모드)
- 씬 복잡도와 무관 (복사량은 화면 픽셀 수로만 결정)
- GPU는 한가하고 CPU(RHIThread) 한 코어만 100% (병목이 렌더링이 아니라 프레젠트 단계의 데이터 카피이므로)
- RTSP/네트워크/GPU전력과 무관 (Xwayland 관련 로컬 IPC 문제였으므로)

## 권장 조치 (2026-08-19 갱신 — 실제 적용된 방식)

애초 아이디어였던 "실행 스크립트에서 `WAYLAND_DISPLAY` 조건부 분기"는 채택 안 함 — UE 패키징이
`titan_example.sh`를 매번 새로 생성해서 덮어쓰므로, 그 파일을 직접 고치는 방식은 패키징할 때마다
다시 손봐야 하는 문제가 있었음. 대신 UE 엔진이 이미 제공하는 정식 오버라이드 메커니즘을 씀
(`LinuxPlatformApplicationMisc.cpp`의 SDL 비디오 드라이버 우선순위: 커맨드라인 > env var >
**INI** > SDL 기본값):

1. **기본값(생 `.sh` 실행 시) — `Config/Linux/LinuxEngine.ini`**:
   ```ini
   [Linux.SDL]
   VideoDriver=wayland
   ```
   프로젝트 Config라 패키징할 때마다 자동으로 쿡됨 — 생성된 `.sh`를 손댈 필요 없음. 다만 이건
   무조건 wayland를 강제하는 정적 설정이라, Wayland가 없는 순수 X11 머신에서 그대로 실행하면
   SDL 초기화가 실패함(폴백 없음).
2. **X11 전용 환경 대비 — `titan_example_x11_fallback.sh`(프로젝트 루트)**: `-sdlvideodriver=x11`
   커맨드라인 오버라이드로 위 INI 기본값을 명시적으로 뒤집어서 안전하게 X11로 뜸(LIG처럼 Wayland
   없는 구형 환경 배포용). **UE 패키징이 자동으로 포함해주는 파일이 아니므로, 패키지 결과물
   폴더에 매번 수동으로 같이 복사해서 배포해야 함.**
3. **순수 X11(Xorg) 세션에서도 테스트 권장**(아직 안 함): Wayland 없이 완전히 X11로만 붙는
   세션(로그인 화면에서 "Ubuntu on Xorg")에서도 정상 속도가 나오는지 확인해서, 문제가 "Xwayland
   번역 계층" 자체인지 "X11 백엔드 자체"인지 한 번 더 구분해두면 좋음(현재는 Xwayland 케이스만
   확인됨) — `titan_example_x11_fallback.sh`로 재현/확인 가능.
4. **근본 원인(선택사항, 낮은 우선순위)**: 왜 이 NVIDIA 드라이버+Xwayland 조합에서 DRI3 다이렉트
   버퍼 공유가 안 되고 소프트웨어 카피로 폴백되는지는 추가로 팔 수 있으나, 위 우회책으로 실사용에는
   문제없음.

## 참고 — 사용한 진단 도구

- `htop`, GNOME System Monitor: CPU 코어별/스레드별, 메모리/스왑, 네트워크 실시간 확인
- `nvidia-smi`, `nvtop`: GPU 사용률/전력/P-state/VRAM
- Unreal Insights: GPU/CPU 타임라인 상세 분석
- `perf top -p <PID>`, `perf record -g` + `perf report --stdio -g graph,0.5,caller`: 함수/콜스택 레벨 CPU 프로파일링 (최종 원인 특정에 결정적)
- `strace -p <PID> -c` / `-e trace=...` / `-k`: syscall 레벨 분석
- `ss -tnp`, `lsof -p <PID> -a -i` (인터넷 소켓) / `-a -U` (Unix 소켓): 프로세스별 열린 소켓 확인
