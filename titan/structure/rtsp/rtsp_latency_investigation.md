# RTSP 영상 지연 조사 - 파이프라인 전수 정리 (2026-08-18)

## 0. 증상

UGV RCWS/CCTV RTSP 스트림(UE `RtspEncoder` 플러그인 → GStreamer/gst-rtsp-server → 클라이언트)에서
**입력 반영 시점 대비 영상에 보이는 시점까지 약 0.5초 지연**이 꾸준히 관측됨.

- 로컬호스트, Tailscale, 다른 PC — **환경 무관하게 동일**하게 발생.
- 세션마다 크기가 조금씩 다름(0.5초~3초 리포트됨). **한번 생기면 그 세션 내내 그 크기로 고정**되는
  것처럼 보임(줄어들지 않음).
- UDP+JSON 명령(발사/이동 등)은 별도 경로라 **거의 즉각 반영됨** — 영상 파이프라인만의 문제.
- 측정 방법: 사용자가 입력 → 실제 UGV 반응(별도 채널로 확인) → 영상에 반영되는 시점을 육안으로
  비교 (+ timestamp 를 화면에 띄워서 ms 단위로 비교). ±0.5초 단위 정밀도.

**이 문서의 목적**: 지금까지 조사로 "아니다"라고 확정지은 것과, 아직 확정 못한 것을 구분해서
다음 조사가 헛다리 짚지 않게 하는 것. §3은 조사 순서대로 쌓여있고 중간에 뒤집힌 결론도 많으니(각
절 제목에 "반박됨"/"기각" 표시됨), **지금 실제로 맞는 결론만 보려면 아래 현재 상태 요약과 §2
표를 보고, 그 근거/왜 뒤집혔는지가 궁금할 때만 §3의 해당 절을 찾아가는 걸 권장**.

---

## 현재 상태 요약 (2026-08-19 기준, 가장 최신 — 이 문서에서 가장 먼저 볼 것)

**⚡ 최종 결론(§3.18) — 수신측을 GStreamer+NVDEC로 전환, 목표 달성**: cv2/libVLC(367ms,
튜닝 최대치) 대신 GStreamer+NVDEC 수신 파이프라인(`latency=0`/`drop-on-latency=true`/
`max-display-delay=0`/`sync=false`) + 서버 추가 튜닝(`ULTRA_LOW_LATENCY`+VUI+RCWS 60fps)
조합으로 **총 지연 68ms(30~100ms 변동)** 달성 — 최초 441~484ms 대비 85~90% 개선. 아래
cv2/libVLC 관련 수치와 결론(§3.11~3.17)은 "cv2/libVLC로 갈 경우"의 참고 기록으로 남겨두되,
**실제 채택 경로는 GStreamer+NVDEC**이고 cv2 전환 작업은 보류됨.

**자체방호축(이동형지휘소) 확장(§3.20)**: UGV축과 인코더/서버 코드를 그대로 공유하는 구조라
별도 서버 작업 없이 `selfdefense/*` 6개 마운트 접속·하드웨어 디코드까지 검증 완료(2026-08-19).
정밀 지연 재측정은 미실시 — UGV축과 동등 수준(68ms대) 기대치일 뿐, 확정치 아님.

**총 종단(glass-to-glass) 지연**: `nExtraOutputDelay=1` 적용 전엔 `441~484ms`(§3.9, UE 뷰포트와
rc_gui 화면 동시 스크린샷으로 정밀 실측). 적용 후엔 사용자 육안 확인 기준 **300ms대 중반**으로
줄어듦(§3.15) — 정밀 재실측(§3.9와 같은 스크린샷 방식)은 아직 안 함, 아래 서버/네트워크 구간은
로그로 확정된 값(§3.15에서 재검증 완료)이고 클라이언트 구간은 그 차이로 역산한 값.

```
[서버: 캡처→appsrc push]         ~46.5ms  ← 확정·재검증 완료(§3.14/§3.15). nExtraOutputDelay
                                            =3→1(버퍼 4개→2개, 벤더 SDK 권장 안전 최소값)로
                                            낮춰서 112ms→평균 46.5ms(32.6~52.2ms, 20프레임
                                            로그 실측, fps=30). 우리 코드(render command 큐잉,
                                            EncodeFrame() 호출)는 결백함이 실측으로 증명됨 —
                                            남은 지연은 전부 NVENC 자체 버퍼
        +
[네트워크: push→클라이언트 RTP 도착]  1~12ms  ← 확정, §3.8. 원인 아님
        +
[클라이언트: RTP 도착→화면 표시]     366.7ms (cv2 기준, §3.17에서 정밀 확정 — 원시 소켓 seq
                                            대조, 편차 0) ← VUI bitstream_restriction 수정으로
                                            433.3ms에서 여기까지 줄었으나 아직 미해결. 정확히
                                            고정된 11프레임(367ms) — 지터 아니라 파이프라인
                                            깊이. 아래 "기각된 가설들" 전부 여기 구간에서 나온
                                            것들이고 전부 틀린 것으로 확인됨(cv2/libVLC 둘 다)
```

**서버 쪽(~46.5ms)**: 완료(§3.15) — `nExtraOutputDelay=1` 적용, 안정성 확인됨, 로그로 재검증
완료(100ms 이하 확실), 사용자 육안으로도 개선 확인. RCWS를 60fps로도 올려서 이론상 더 줄이려
했으나 통제기 목업에서 초반 불안정(0.5초/4초 반복) 증상이 나와 일단 fps는 30으로 되돌림 —
나중에 클라이언트 쪽 작업할 때 60fps 대응까지 같이 재시도 예정(§5 0번).

**클라이언트 쪽(~270~310ms, 역산)**: §3.16에서 근본 원인의 정체까지는 찾았으나(연결 초기
해상도 오추측→디코더 재시작→그때 낀 지연이 그대로 고정), **이 프로젝트 코드로 고칠 수 있는
레버가 없다는 결론**(libVLC는 seek 불가 스트림이라 사후 캐치업 자체가 API 레벨에서 막혀있음,
§3.16). 남은 선택지는 cv2로 백엔드 교체(직접 캐치업 로직 구현 가능하지만 렌더링/재연결 구조를
새로 짜야 함) 또는 여기서 서버 개선까지만 마무리 — 사용자 결정 대기 중.

**기각된 가설들**(전부 실측으로 반박됨, 재시도 불필요):
- 프레젠테이션 단계(libVLC `set_hwnd`/Qt 렌더) — §3.10에서 순수 Qt/GDI 페인트 테스트로 반박(20ms 이하)
- "얼어붙은 백로그"(연결 시 느린 오픈으로 쌓인 버퍼가 고정됨) — cv2에선 확정됐지만 libVLC 자체
  연결(`play()`→Playing 이벤트)은 18.7ms로 즉시 됨(§3.11) — 다만 §3.16에서 **다른 메커니즘**
  (해상도 오추측→디코더 재시작)으로 비슷한 현상이 재확인됨, 원인은 다르지만 결과가 비슷함
- libavcodec frame-threading(다른 세션 제안 가설) — `avcodec-threads=1` 직접 적용 후 스크린샷
  재검증했으나 효과 없음(484ms, 그대로) — 기각(§3.12). §3.16에서 이유까지 확인: 이 스트림은
  D3D11VA 하드웨어 디코드를 쓰고 있어서 avcodec의 소프트웨어 스레드 설정 자체가 무관함
- GStreamer 서버 쪽 튜닝(thread-pool/latency/rate-control) — 전부 적용 확인됐지만 효과 없음(§2 #6,7,10)
- VLC `network-caching` — 단일 스트림에선 효과 있었지만 실제 앱(5스트림 동시)에선 왜 효과가
  다른지 미해결(§3.7) — 5개 동시 처리 가설 자체는 §3.8에서 배제됐으므로 원인은 아닐 가능성 높음
- 하드웨어 디코드(D3D11VA) 자체가 원인 — §3.16에서 `avcodec-hw=none`으로 소프트웨어 디코드
  강제 후 재검증, 하드웨어 디코드와 동일한 지연 — 기각

---

**2026-08-18 중요 정정**: 아래 §2 #1의 "UE 내부(제출→appsrc push)는 13ms로 빠름, 원인 아님"이라는
이전 결론이 **측정 방법 결함으로 틀렸음이 확인됨** — §3.6 참고. UE 내부 구간이 다시 용의선상에
올라와 있는 상태. (**2026-08-19 갱신**: §3.13에서 재측정 완료, 216ms로 확정 — 위 현재 상태 요약 참고.)

**2026-08-19**: §3.9(씬 내장 시계로 441ms 직접 실측)와 §3.10(그 원인 분석이 반박됨), §3.11~3.13으로
이어지는 세부 조사 과정은 아래 §3에 순서대로 남아있음 — 결론이 여러 번 뒤집혔으니 최신 결론은
위 "현재 상태 요약"을 기준으로 볼 것.

---

## 1. 전체 파이프라인

### 1.1 구간별 지연 요약

| 구간 | 범위 | 지연 | 상태 | 근거 |
|---|---|---|---|---|
| 서버 인코드 | UE 캡처 → GPU 복사 → NVENC 인코드 → appsrc push | **112ms** | 확정 — NVENC 자체 버퍼 깊이(3프레임), UE 코드는 결백 | §3.14 |
| 네트워크 전송 | appsrc push → 클라이언트 RTP 도착 | **1~12ms** | 확정 — 원인 아님 | §3.8 |
| 클라이언트 | RTP 수신 → 디코드 → 화면 표시 | **~320~360ms** | 미해결(전체에서 역산한 값) | §5 |
| **합계** | **글래스투글래스(체감 지연)** | **441~484ms** | 확정 — 직접 실측 | §3.9 |

### 1.2 서버 인코드(112ms) 내부 분해

| 단계 | 지연 | 근거 |
|---|---|---|
| render command 큐 대기 | 0.7~15ms | 실측, §3.13 |
| `EncodeFrame()` 호출 자체 | 0.2~0.8ms | 실측, §3.13 |
| NVENC 내부 버퍼(비동기 완료 대기, 3프레임) | ≈100ms | 실측·이론치 일치, §3.14 |

NVENC 호출 자체는 비동기라 빠르게 리턴하지만, 그 프레임의 실제 인코드 결과는 3프레임(≈100ms)
뒤에야 나옴(`nExtraOutputDelay=3` 파이프라이닝, NVENC 프리셋 로그로 `lookaheadDepth=0`,
`OutputBufferDelay=3`을 직접 확인) — 이 대기 시간이 112ms의 대부분을 차지함. (처음엔 216ms로
측정됐었는데, 그건 진단 코드 자체의 FIFO 큐 버그로 오염된 값이었음이 밝혀짐 — §3.14.)

**이 100ms가 "CPU 리드백이 느려서"는 아님** — `NvencD3D12Encoder.cpp` 코드로 직접 확인(2026-08-19):
GPU 카피는 펜스만 걸고 CPU는 기다리지 않음("No CPU wait needed on our side — NVENC's hardware
GPU-waits on the fence", 211줄), 결과를 꺼내오는 `Encoder->EncodeFrame(Packets)` 호출 시점엔
이미 그 프레임의 GPU 작업이 한참 전에 끝나있어서 대기가 없음(`encode_call_ms` 실측 0.2~0.8ms가
그 증거). **100ms의 정체는 의도적 설계**: 코드 상단 주석(53~61줄)에 `nExtraOutputDelay=0`으로
버퍼링을 없애려던 과거 시도가 인코더를 동기 모드로 바꿔 렌더 스레드가 매 프레임 하드웨어
완료를 기다리게 만들어 **에디터 전체가 데드락**났던 전례가 적혀있음 — 그래서 지금은 일부러
3프레임을 "제출만 해두고 나중에 꺼내는" 큐에 담아둠. 데드락을 피하려고 지연을 감수하는 트레이드오프.

### 1.3 클라이언트 구간(~320~360ms)에서 기각된 가설

이미 실측으로 반박되어 더 파볼 필요 없는 것들 — 새 가설을 낼 때 이 목록부터 확인할 것.

| 가설 | 결과 |
|---|---|
| 프레젠테이션 단계(libVLC `set_hwnd`/Qt 렌더가 느림) | 반박 — 순수 Qt/GDI 페인트 테스트 20ms 이하 (§3.10) |
| "얼어붙은 백로그"(느린 연결 오픈으로 쌓인 버퍼가 고정) | libVLC엔 해당 없음 — 연결이 18.7ms로 즉시 됨 (§3.11) |
| libavcodec frame-threading | 반박 — `avcodec-threads=1` 적용해도 지연 그대로 (§3.12) |
| 서버 GStreamer 튜닝(thread-pool/latency/rate-control) | 적용 확인됐지만 효과 없음 (§2 #6,7,10) |
| VLC `network-caching` | 단일 스트림엔 효과 있었으나 실제 앱(5스트림)에선 불일치, 원인은 아닌 듯 (§3.7) |

### 1.4 파이프라인 단계 상세 (코드 위치 참고용)

1. **UE 게임스레드** — RCWS/CCTV `SceneCaptureComponent2D` 틱 (TargetFps=30, 5개 스트림), `ENQUEUE_RENDER_COMMAND`
2. **UE 렌더스레드** — `FRHICommandList`: SourceTexture 상태 전이
3. **GPU, D3D12 CopyResource** — SourceTexture → NVENC 입력 리소스로 복사 (GPU-to-GPU, zero-copy)
4. **GPU, NVENC 하드웨어 인코드** — H.264, Preset P3 + TUNING_LOW_LATENCY, CBR, frameIntervalP=1(B프레임 없음), GOP=Fps*2, nExtraOutputDelay=SDK 기본값 3
5. **CPU 리드백** — 압축된 Annex-B 비트스트림만 (수십KB, 픽셀 아님)
6. **GStreamer appsrc** — `PushEncodedFrame()`, PTS/DTS 직접 관리(`State.NextPtsNs`), is-live=true, latency=0,0
7. **h264parse ! rtph264pay** — config-interval=1(매 IDR마다 SPS/PPS 삽입), RTP 패킷화
8. **gst-rtsp-server 내부** — `GstRTSPMedia`/`GstRTSPStream`, RTP 세션 관리, TCP interleave 전송(이 프로젝트 코드 아님, GStreamer 라이브러리 내부)
9. **네트워크** — 로컬호스트/Tailscale/LAN, TCP
10. **클라이언트 수신** — RTSP 세션 파싱, TCP 디인터리브
11. **클라이언트 디코드** — libVLC(python-vlc) 또는 ffmpeg(cv2), H.264 소프트웨어/하드웨어 디코드
12. **클라이언트 화면 표시** — libVLC 자체 렌더 또는 Qt QPixmap

1~6이 §1.1의 "서버 인코드", 7~9가 "네트워크 전송", 10~12가 "클라이언트"에 대응. 1~6 구간(제출
시각 → appsrc push 시각)의 216ms는 `RtspStreamComponent.cpp`/`RtspServerSubsystem.cpp`의 FIFO
큐 기반 타이밍 로그로 확정 실측된 값(처음 시도한 측정은 프레임 정체성을 잘못 짝지어 결함이
있었음 — §3.6 참고). 7 이후는 GStreamer 라이브러리 내부(소스가 이 프로젝트에 없음) + 클라이언트
쪽이라 코드 조사에 한계가 있고, 여기 어딘가에 남은 ~230~260ms가 아직 미해결 상태(§5 참고).

---

## 2. 확정된 것 (증거 있음)

| # | 항목 | 결론 | 근거 |
|---|---|---|---|
| 1 | **서버 인코드 구간(제출→appsrc push) 소요시간** | **확정: 평균 ~112ms, 전부 NVENC 자체 버퍼 깊이(우리 코드 결백)** — §3.14 | FIFO 큐로 프레임 정체성 올바르게 짝지어 실측(`capture_to_push_ms`). 처음 216ms로 나왔던 건 진단 코드의 FIFO 큐 버그(재연결마다 버려지는 프레임의 타임스탬프가 안 빠지고 쌓임)로 오염된 값이었고, 수정 후 112ms — 이론치(3프레임 @ 30fps = 100ms)와 일치 |
| 2 | **이미지가 GPU→CPU로 나오는가** | **아니오.** 픽셀 데이터는 D3D12 `CopyResource`로 GPU 안에서만 이동(zero-copy). CPU로 나오는 건 인코드 완료된 압축 바이트스트림뿐(수십KB) | `NvencD3D12Encoder.cpp::EncodeFrame` 코드 직접 확인 |
| 3 | **네트워크** | 원인 아님 | 로컬호스트/Tailscale/다른 PC 전부 동일한 지연 — 네트워크 왕복 시간이 0에 가까운 로컬호스트에서도 동일하므로 배제 |
| 4 | **에디터 백그라운드 스로틀링**("Use Less CPU when in Background") | 원인 아님 | 꺼놓고 재테스트해도 동일. 다른 PC(창이 포커스된 상태)에서도 동일 |
| 5 | **클라이언트 구현체 종류** | 원인 아님(적어도 단독 원인은 아님) | OpenCV(`cv2.VideoCapture`) / python-vlc(libVLC) / 데스크톱 VLC 앱 — 완전히 다른 3개 구현체가 전부 동일한 지연을 보임 |
| 6 | **GStreamer `GstRTSPMedia` latency 프로퍼티** (`gst_rtsp_media_factory_set_latency(Factory, 0)`) | 적용됨, **효과 없음** | 코드 리뷰로 호출 확인. 재빌드 후 재테스트해도 지연 그대로 |
| 7 | **GStreamer rate control** (`gst_rtsp_stream_set_rate_control(Stream, FALSE)`) | 적용됨, **효과 없음** | UE 로그로 `gst_rtsp_stream_get_rate_control() == 0` 실측 확인(5개 스트림 전부). 재테스트해도 지연 그대로 |
| 8 | **VLC `network-caching`** | **정정됨 — §3.7 참고.** 사용자의 수동 테스트(1000→100→1ms)에서는 바닥이 있었지만, libVLC 자체 verbose 로그로 직접 재측정하니 **100ms→283ms 목표 버퍼링, 10ms→24ms로 거의 비례해서 줄어듦**(단일 스트림 격리 테스트). "캐시로 통제 안 되는 바닥이 있다"는 이전 결론은 최소한 단일 스트림 기준으론 틀렸음 — 두 결과가 왜 다른지는 §3.7에서 재검증 중 | libVLC `--verbose=2` + `--file-logging`로 "Stream buffering done (%d ms in %d ms)" 로그 직접 확인(2026-08-18) |
| 9 | `nExtraOutputDelay=0`(NVENC 출력 버퍼링 완전 제거) | **재시도 불가 — 이미 실패 이력 있음.** 현재 기본값 3이 만드는 실제 지연은 **~100ms(3틱 @ 30fps)로 확정** — §3.6 | `rtsp_poc_findings.md` §1.18: 렌더스레드가 매 프레임 하드웨어 완료를 동기 대기하게 되어 에디터 데드락 유발, 되돌려짐. `NvEncoder.cpp:775` `iEnd = m_iToSend - m_nOutputDelay`(=3)로 코드 레벨 확인 — #1이 이걸 놓치고 있었음 |
| 10 | **서버 쪽 GStreamer 튜닝 3종(latency=0 / rate control=off / thread-pool=8)** | 전부 **적용 확인됨(로그 실측), 체감 지연에 효과 없음** | `LogRtspEncoder`로 3개 전부 반영값 직접 확인. 그런데도 사용자 체감 지연 그대로 — appsrc 이후 구간에서 지금까지 찾은 튜닝 포인트는 소진됐다는 뜻 |
| 11 | **`BP_UGV_Vehicle`의 `CaptureRoundRobinCount`(2→1) 저장 여부** | **저장 확인됨(is_dirty=false)** — 리버트 걱정 없음 | unreal-mcp로 재확인 |

---

## 3. 아직 확정 못한 것 (다음 조사 후보)

전부 **⑦ 이후(appsrc push 이후) 구간**에 있음 — #1(13ms 실측)로 그 이전 구간은 배제됐으므로.

### 3.1. GStreamer `GstRTSPThreadPool` — **소스 레벨로 확인, 수정 적용함(재검증 대기)**

gst-rtsp-server 소스(`rtsp-thread-pool.c`, GitHub 미러로 직접 확인 — 로컬엔 헤더만 있고 .c는 없음)
기준:
- `DEFAULT_MAX_THREADS = 1`.
- 이 제한은 `GST_RTSP_THREAD_TYPE_MEDIA`(인코딩/스트리밍 담당)에는 **적용 안 됨** — 미디어
  요청마다 항상 새 스레드를 만듦(`make_thread`), 공유/재활용 없음. → **5개 스트림의
  인코딩→appsrc push 경로 자체는 스레드 경합이 없다는 뜻**(사용자가 "PIE fps 멀쩡한데 이상하다"고
  지적한 게 맞았음 — 이 경로는 실제로 문제가 아니었음).
- 이 제한은 `GST_RTSP_THREAD_TYPE_CLIENT`(RTSP 연결/세션 처리)에는 적용됨 — `max_threads`에
  도달하면 큐에서 기존 스레드를 재활용(recycle)함.
- **TCP interleaved 전송에서 RTP 데이터가 실제로 나가는 경로는 `GstRTSPClient`의 연결 자체**임
  (`rtsp-client.c`, `do_send_data()` → `send_lock`으로 보호되는 `send_func`). 클라이언트 객체
  자체는 연결마다 별도로 생성되어 공유 안 되지만(→ 데이터 뒤섞임 없음), 그 연결들을 처리하는
  **스레드**는 CLIENT 타입 풀(`max_threads`)에서 배정받음.
- rc_gui(테스트 클라이언트)는 마운트 5개에 각각 별도 RTSP 연결을 열어서(스트림당 1세션) 총
  5개의 `GstRTSPClient`가 뜸 — 기본값 1로는 이 5개 연결의 스케줄링이 스레드 하나에 몰려있었을
  가능성이 있음.

**수정**: `RtspServerSubsystem.cpp::Initialize()`에서 서버 생성 직후
`gst_rtsp_server_get_thread_pool()` → `gst_rtsp_thread_pool_set_max_threads(pool, 8)`로 올림.
실제 반영값은 `LogRtspEncoder`에 로그로 남게 해둠. **재빌드 후 재테스트 필요 — 아직 효과 미검증.**

### 3.2. TCP interleaved 전송 자체의 배치/코얼레싱 동작

§3.1에서 확인한 대로 클라이언트별 `send_lock`이 각자 독립적이라 **클라이언트 간** 경합은 없음이
확인됨(`rtsp-client.c`). 다만 **그 클라이언트를 처리하는 스레드 자체가 §3.1의 풀에서 공유되고
있었다면**, 실제 소켓 flush 타이밍이 그 스레드의 GLib 메인루프 반복 주기에 종속되어 지연될 수
있음 — §3.1 수정으로 같이 해소될 가능성이 있어 별도 항목이라기보다는 §3.1의 하위 증상으로 재분류.

### 3.3. 클라이언트(libVLC) 자체 디코드 파이프라인 내부

`network-caching`을 최소로 낮춰도 안 없어지는 바닥(§2 #8)이 libVLC 자체의 RTP 지터버퍼나 디코더
스레드 큐 어딘가에 있을 가능성. libVLC는 오픈소스라 조사 가능하지만 아직 소스 레벨로 안 들어가봄.

**사용자가 제기한 또 다른 가설과 관련**: **클라이언트가 5개 스트림을 동시에 디코드**하면서(소프트웨어
디코드라면 특히) CPU 경합으로 지연이 생기는 것 아니냐는 가설 — 이것도 미확인. 스트림 1개만 열어놓고
지연을 재보면 이 가설도 §3.1과 같이 검증 가능.

### 3.4. "한번 생긴 지연이 고정되어 유지"되는 메커니즘

사용자 가설: RTSP 세션 시작(PLAY) 시점에 파이프라인 클록 기준점(base-time)이 잡히는데, 그 순간
우연히 낀 지연(키프레임 대기, 시스템 부하 등)이 고정 오프셋으로 남아 이후 계속 적용되는 것 아니냐 —
rate control이 이런 클록 기준점 계산을 담당하는 메커니즘이라 유력한 후보였으나, **rate control을
껐는데도 재현된다면 이 가설은 기각되거나, 다른 곳에도 같은 종류의 클록 고정 로직이 있다는 뜻**.
rate control 끈 뒤의 재현 여부를 아직 명확히 재검증 안 함 — §2 #7의 "효과 없음"이 이 가설까지
포함하는 재검증인지 재확인 필요.

### 3.5. GST_DEBUG=rtpbin:4로 캡처했는데 rtpbin 로그가 전혀 없었음

캡처된 GStreamer 디버그 로그(`gst_debug.log`)에 `rtspstream`(1847줄), `rtspmedia`(636줄)만 있고
`rtpbin` 카테고리 로그가 0줄이었음. 이 파이프라인에 rtpbin이 실제로 안 쓰이는 구성인지(TCP
interleave 전용 경로라 UDP 세션 지터버퍼용 rtpbin을 안 거치는 걸 수도 있음), 아니면 그냥 그
시점에 로그 낼 이벤트가 없었던 것뿐인지 미확인.

### 3.6. NVENC `nExtraOutputDelay` 파이프라이닝 — 측정 결함 발견, 참인 지연 추정치 확정 (2026-08-18)

**문제**: §2 #1의 "13ms" 측정은 `RtspStreamComponent.cpp`에서 매 틱 `FPlatformTime::Seconds()`로
캡처한 `SubmitWallClockSeconds`를, 그 **같은 틱의 `EncodeFrame()` 호출이 반환한 `AccessUnits`**와
짝지어 `PushEncodedFrame`에 넘기는 방식이었음.

**근데 NVENC 벤더 코드(`NvEncoder.cpp`)를 다시 보니** (`GetEncodedPacket`, 774줄):
```cpp
int iEnd = bOutputDelay ? m_iToSend.load() - m_nOutputDelay : m_iToSend.load();
for (; m_iGot < iEnd; m_iGot++) { /* m_iGot번째 프레임의 인코딩 결과를 꺼냄 */ }
```
`m_nOutputDelay = m_nEncoderBuffer - 1 = (frameIntervalP=1 + lookaheadDepth=0 + nExtraOutputDelay=3) - 1 = 3`.
즉 **프레임 N을 제출(`m_iToSend`를 N+1로 증가)해도, 그 호출에서 실제로 돌려받는 데이터는 프레임
(N-3)의 결과**임 — NVENC를 파이프라이닝(제출과 결과 수신을 겹치게)하기 위한 정상 설계.

**결과**: 제가 "프레임 N 제출 시각"과 "그 호출이 반환한 (실제로는 N-3인) 데이터의 push 시각"을
짝지었으니, 계산된 "13ms"는 사실상 무의미한 숫자였음(둘 다 "지금 이 틱" 근처라 작게 나올 수밖에
없는 구조). **진짜 지연은 이보다 최소 3틱(30fps 기준 ~100ms) 더 큼.**

**아직도 다 설명 안 됨**: 보정해도 ~100~125ms 정도라, 전체 0.5초 중 나머지 ~375~400ms는 여전히
appsrc 이후(§3.1~3.5) 구간에 있다는 결론 자체는 안 바뀜. 다만 "UE 내부는 완전히 결백하다"는
과거 결론은 폐기해야 하고, **appsrc 이후 구간의 진짜 크기를 알려면 이 측정부터 프레임 인덱스
기준으로 올바르게 다시 짜야** 다른 구간들과의 정확한 비교가 가능함.

**2026-08-19 구현 완료**: `RtspStreamComponent.h/.cpp`에 `TSharedPtr<TArray<double>>
PendingSubmitWallClockSeconds` FIFO 큐 추가 — 렌더스레드 람다 안에서 `EncodeFrame()` 호출
직전에 제출 시각을 큐에 push, 반환된 `AccessUnits` 개수만큼 큐 앞에서 pop해서 짝지음(렌더스레드
단일 스레드라 레이스 없음). `RtspServerSubsystem.cpp::PushEncodedFrame`은 이제 이 값(같은
프로세스 `FPlatformTime::Seconds()` 기준이라 UTC 변환 불필요)과 push 시각의 차이를
`capture_to_push_ms`로 매 프레임 직접 로그에 찍음. **재빌드 후 재검증 필요 — 아직 미검증.**

### 3.7. libVLC `network-caching` 재검증 — 단일 스트림에선 효과 있음, 실제 앱(5스트림)에선 미검증

PIE가 켜진 김에 `python-vlc`로 UGV RCWS 스트림 하나에 직접 붙어서 libVLC 자체 verbose 로그
(`--verbose=2 --file-logging`)를 떠봤음 — `main debug: Stream buffering done (%d ms in %d ms)`
라인이 실제 목표 버퍼링 시간을 그대로 보여줌:

| `network-caching` 값 | 목표 버퍼링 |
|---|---|
| 100ms (`rc_gui` 기존값) | **283ms** |
| 10ms | **24ms** |

`--clock-jitter=0 --clock-synchro=0`을 같이 줘봤지만 283ms에서 변화 없음(그 컴포넌트가 크게
기여하는 건 아닌 듯). **거의 `network-caching` 값에 비례해서 목표 버퍼링이 줄어듦이 확인됨** —
즉 단일 스트림 기준으론 "캐시를 낮춰도 안 줄어드는 바닥이 있다"는 §2 #8의 기존 결론이 틀렸음.

**그런데 사용자가 이전에 VLC 데스크톱 앱에서 직접 캐시를 1000→100→1ms로 낮춰봤을 때는 이 정도
효과가 안 보였다고 함** — 왜 다른지 아직 설명 안 됨. 가능성:
(a) 데스크톱 VLC GUI의 "네트워크 캐싱" 환경설정이 실제로는 다른 내부 프로퍼티/프로파일에
매핑되어 이 `network-caching` 옵션과 다르게 동작할 수 있음,
(b) 그때는 rc_gui가 5개 스트림을 동시에 열고 있는 상태였을 수 있어서, 단일 스트림 격리
테스트와 다른 결과가 나왔을 수 있음(→ 클라이언트 쪽 "5개 동시 처리" 가설이 다시 유효해짐,
이번엔 서버가 아니라 클라이언트 쪽에서).

**적용한 수정**: `video_panel.py`의 `NETWORK_CACHING_MS`를 100 → **30**으로 낮춤.

### 3.8. Ground-truth 프레임 단위 실측 — 서버 UTC ↔ 클라이언트 UTC 순번 매칭 (2026-08-18, 결정적)

사용자 아이디어("파이프라인 전체에 타임스탬프 찍으면 정확한 ms를 알 수 있지 않냐")로 진행한
가장 정밀한 측정. §3.6에서 지적된 "다른 프로세스 시계는 직접 비교 불가" 문제를 `FDateTime::UtcNow()`
(UE)와 `time.time()`(파이썬)을 둘 다 UTC 기준으로 맞춰서 해결하고, **순번 매칭은 RTP 타임스탬프로
정확히** 함(우리 서버가 프레임마다 결정론적으로 `PTS = seq × frame_duration`을 매기므로, RTP
타임스탬프(90000Hz)를 역산하면 정확히 몇 번째 프레임인지 나옴 — libVLC 콜백 API는 이 정보를
안 줘서, RTSP/RTP를 직접 소켓으로 파싱하는 방식(`latency_probe.py`)으로 우회함).

**수정한 파일**: `RtspServerSubsystem.h`/`.cpp`(`PushEncodedFrame`이 매 프레임 `PUSH seq=N
utc_ms=X`를 UTC로 로그), `latency_probe.py`(RTSP/RTP 소켓 직접 파싱, RTP 타임스탬프로 seq 역산),
`latency_probe_vlc.py`/`latency_probe_vlc5.py`(libVLC raw 비디오 콜백으로 "디코드된 프레임이
실제 표시되는 시각"을 UTC로 기록 — `python-vlc`의 `VideoLockCb` 등이 이 설치본에서 정상 작동 안 해서
libVLC C API 시그니처 그대로 `ctypes.CFUNCTYPE`을 직접 정의해서 우회).

**결과** (전부 PIE 라이브 세션에서 실측, seq 번호로 서버/클라이언트 로그 정확히 대조):

| 구간 | 측정 방법 | 결과 |
|---|---|---|
| 서버 push → RTP 소켓 도착 (네트워크+RTSP/RTP 전송) | raw 소켓, seq 정확히 매칭 | **1~12ms** (180프레임 전부) |
| libVLC 디코드+표시, 안정 상태, 단일 스트림 | display 콜백, 근접 매칭 | **13~31ms** |
| libVLC 디코드+표시, 안정 상태, **5개 동시**(실제 앱과 동일 구조) | display 콜백, 근접 매칭 | **13~25ms** — 5개 동시에도 거의 그대로 |
| libVLC 최초 연결 시 버퍼링(1회성) | display idx=1 vs 서버 seq=1 | **254~283ms** (실행마다 변동 — "가끔 0.5초 가끔 3초"의 정체로 추정) |
| 20초 세션 중 재버퍼링 빈도 | verbose 로그 "Stream buffering done" 카운트 | **2회뿐, 주기적 재발 아님** |

**2026-08-19 재검증**: 서버 개선(nExtraOutputDelay=1, §3.15) 적용 후 이 구간만 다시 raw 소켓
프로브(`latency_probe.py`)로 재확인 — 서버 `PUSH utc_ms` 로그와 프로브 `RECV utc_ms`를 가장
가까운 시각으로 직접 매칭(26개 샘플, 5초 구간): **안정 구간 전부 1.0~2.2ms**로 여전히 무시할
수준. 설정이 바뀌어도 이 구간은 결론 그대로 — 원인 아님 재확인.

**결론**: appsrc 이후 전 구간(네트워크+RTSP+RTP+libVLC 디코드+표시)에서 **안정 상태의 프레임별
지연은 실제로 매우 작다(30ms 이하)**는 게 이제 추측이 아니라 seq 단위 실측으로 확정됨. 지금까지
용의선상에 있던 §3.1(스레드풀)/§3.3(5개 동시 디코드 경합)/§3.4(고정 오프셋)/§3.7(network-caching
바닥) 가설 전부 — 적어도 "안정 상태 지연"의 원인으로서는 — 근거가 사라짐. 유일하게 남은 큰 수치는
**연결 시작 시 1회성 버퍼링(최대 283ms 관측)**뿐이고, 이건 재발하지 않음.

**아직 안 풀린 것 — 사용자 체감과의 불일치**: 사용자는 스트림이 한참 떠있는 상태에서도 지속적으로
~0.5초를 체감한다고 보고함. 이건 "1회성 버퍼링" 설명과 안 맞음(1회성이면 스트림 켜고 한참 뒤엔
없어져야 함). 다음 확인 필요:
- 스트림 켠 지 30초 이상 지난 뒤에도 입력→화면 반응이 여전히 ~0.5초로 느껴지는지 재확인.
- 만약 그렇다면, 이 문서의 모든 실측이 못 잡아낸 무언가가 있다는 뜻 — UE 게임 로직(입력→시뮬레이션
  반영) 쪽이나, 사용자의 "UGV 반응 확인 채널" 자체의 지연일 가능성도 재검토 필요.
- 만약 스트림 켜고 한참 뒤엔 체감이 없어진다면, 이 문서의 결론(1회성 버퍼링)이 맞았다는 뜻이고
  버퍼링 크기를 더 줄이는 쪽(예: network-caching을 30보다 더 낮추거나, 최초 연결 시 강제
  키프레임 타이밍을 더 당기는 등)으로 방향을 잡으면 됨.

### 3.9. 씬 내장 UTC 시계로 직접 종단 지연 실측 — 로그 상관관계 불필요, 결정적 (2026-08-19)

§3.8의 seq 매칭 방식(서버 `PUSH seq=N utc_ms=X` 로그 ↔ 클라이언트 raw 콜백 시각)은 두 가지 근본
한계가 있었음: (a) libVLC의 `video_set_callbacks` raw 콜백 경로는 `set_hwnd` 실제 창 렌더링을
아예 안 거침 — "디코드 끝났다"만 잴 뿐 "실제 화면에 그려졌다"는 못 잼(사용자가 직접 지적).
(b) 로그 기반 seq 매칭은 스크린샷 찍은 시각과 로그 조회 시각 사이에 시간이 몇 분만 지나도
실패함 — 5개 스트림이 끊임없이 PUSH 로그를 찍어서 오래된 항목이 조회 범위 밖으로 밀려남(실측:
목표 시각이 21:14:09였는데 몇 분 뒤 조회 시점엔 로그 끝이 이미 21:20:55 — 6분 이상 차이나
로그로 못 찾음).

**해결책**: 로그 상관관계 자체를 없앰. `ULatencyClockComponent`(신규 액터 컴포넌트,
`Source/titan_example/Vehicles/LatencyClockComponent.h/.cpp`)를 `BP_UGV_Vehicle`에 추가해서
매 틱 `UTextRenderComponent`("LatencyClock", `RCWSSightCineCamera`에 부착, 카메라 정면을 보도록
Yaw180)에 `FDateTime::UtcNow()`를 `HH:MM:SS.mmm`으로 찍음. 이 텍스트가 씬의 일부라서 실제
렌더→인코드→RTSP→디코드→화면표시 전 구간을 그대로 통과함.

**측정 방법**: UE 에디터 PIE 뷰포트(RTSP 안 거치고 직접 렌더 — "지금 진짜 시각")와 rc_gui의
RCWS 패널(RTSP 전체 경로 거침)을 **한 화면에 동시에** 캡처(스크린샷 한 장에 위/아래로 두 창).
두 시계 값의 차이 = 그 순간의 실제 종단(glass-to-glass) 지연. 로그 조회나 seq 계산이 전혀
필요 없음.

**결과** (스트림 켠 지 한참 지난 안정 상태에서 촬영, 2026-08-19):

| 위(UE 뷰포트, RTSP 없음) | 아래(rc_gui, RTSP 전체 경로) | 차이 |
|---|---|---|
| 21:18:21.092 | 21:18:20.651 | **0.441초 (441ms)** |

사용자 체감("0.4초 정도")과 정확히 일치. 첫 시도(21:14:09.960 찍힌 스크린샷)는 로그 상관관계
방식으로 seq를 찾으려다 위 (b) 문제로 실패했고, 이 방법(동시 촬영 직접 비교)으로 전환한 뒤
바로 해결됨.

**§3.8과의 모순, 그리고 그게 알려주는 것**: §3.8은 raw 콜백 기준 "appsrc 이후 전 구간(네트워크+
RTSP+디코드) 안정 상태 <30ms"라는 결론을 냈는데, 이번 441ms 실측(같은 안정 상태 조건)과 정면으로
안 맞음. 두 측정의 유일한 차이는 §3.8이 **디코드 완료 시각**(raw 콜백, 실제 창 렌더링 우회)을
쟀고 이번엔 **실제 화면에 보이는 시각**(스크린샷)을 쟀다는 것뿐 — 그러므로 이 차이(441ms - 30ms
≈ 410ms) 자체가 **"디코드 완료 → libVLC가 실제로 화면에 그리기(set_hwnd 프레젠테이션 경로)"
구간에 지연이 몰려있다는 직접 증거**임. §3.1~3.4/3.7의 appsrc-이후 서버/네트워크/디코드 관련
가설들은 이제 완전히 배제 가능 — 문제는 클라이언트 쪽 "그려진 프레임을 화면에 올리는" 마지막
단계(Qt `QFrame`+`WA_NativeWindow`+`WA_PaintOnScreen` 창에 libVLC가 직접 그리는 경로, GPU
프레젠테이션/컴포지터/vsync 등)로 좁혀짐.

**추가로 풀린 것**: §3.8 말미의 "1회성 버퍼링(283ms)과 사용자의 지속적 체감이 안 맞는다"는
의문도 이걸로 설명됨 — 1회성 버퍼링은 진짜 1회성이 맞지만(§3.8), 사용자가 계속 느끼던 ~0.4~0.5초는
애초에 그것과 무관하게 **매 프레임 지속적으로 존재하는 프레젠테이션 지연**이었음. §3.8이 그
구간을 측정 범위에서 놓치고 있었을 뿐.

**2026-08-19 이 결론 반박됨 — §3.10 참고.** 아래 "다음 조사 방향"은 실행해봤으나(순수 Qt 페인트,
GDI 직접 블릿, cv2 비교) 결과가 예상과 반대로 나와서 "프레젠테이션 단계가 범인"이라는 이 결론
자체가 틀렸음이 확인됨.

~~**다음 조사 방향**: `video_panel.py`의 실제 렌더링 경로(`set_hwnd` + Qt `WA_PaintOnScreen`)를
집중 조사...~~ (아래 §3.10)

### 3.10. §3.9 결론 반박 — 프레젠테이션 단계 아님, 클라이언트 공통 상류 구간으로 재이동 (2026-08-19)

§3.9는 "디코드 완료→화면 표시" 구간(libVLC `set_hwnd` 프레젠테이션)을 범인으로 지목했음. 세
가지 후속 실험으로 이 결론이 틀렸음이 확인됨:

1. **순수 Qt 페인트 지연 측정** (`paint_latency_test.py`, RTSP/VLC 전혀 안 씀): 평범한 Qt
   위젯(컴포지팅) **16.4ms**, `WA_NativeWindow`+`WA_PaintOnScreen`+GDI 직접 블릿(VLC가 쓰는
   것과 같은 종류의 hwnd) **18.7ms** — 둘 다 노이즈 수준. **"창에 그리면 화면에 반영되는" 과정
   자체(Qt 컴포지터/native window/GDI/DWM)는 전혀 안 느림.**
2. **cv2.imshow로 재검증** (`cv2_view_test.py`) — libVLC를 아예 안 쓰는 완전히 다른 렌더 경로
   (OpenCV HighGUI, ffmpeg 디코드)로 같은 스트림을 띄워서 §3.9와 똑같이 동시 스크린샷 비교:
   **462ms** — libVLC의 441ms와 사실상 동일. **독립적인 두 구현체가 같은 크기의 지연을 보인다는
   건, 원인이 렌더러(libVLC/Qt)가 아니라 둘 다 공유하는 무언가라는 뜻.**
3. ffmpeg 쪽 저지연 옵션(`max_delay=0`, `reorder_queue_size=0`, `buffer_size=0`)을 cv2에
   추가해도 **효과 없음(여전히 ~0.5초)** — ffmpeg RTSP 디먹서의 기본 버퍼링(`max_delay` 기본
   500ms)이라는 유력 가설도 배제됨.

**결론**: §3.9의 "①~⑥은 결백, 병목은 프레젠테이션"이라는 판단이 틀렸음. §2 #1(①~⑥ 구간)이
§3.6에서 이미 "측정 결함으로 폐기, 미확인 상태"로 되돌아가 있었다는 걸 상기하면, 지금 유일하게
안 맞는 조각은 그 구간(①~⑥, UE 캡처→인코드→appsrc push)뿐임. 두 클라이언트가 공통으로 겪는
지연이라면 client-side가 받는 데이터 자체가 이미 늦게 도착하는 것 — 즉 서버가 프레임을 실제
캡처한 시점보다 appsrc에 push하는 시점이 한참 늦다는 뜻이 됨.

**조치**: `RtspStreamComponent.h/.cpp` + `RtspServerSubsystem.cpp`에 §3.6에서 미뤄뒀던 "FIFO
큐 기반 올바른 프레임 짝짓기"를 구현함(같은 프로세스 내부 비교라 UTC 변환도 불필요 —
`FPlatformTime::Seconds()` 그대로 diff). `PUSH` 로그 라인에 이제 `capture_to_push_ms`가
프레임마다 직접 찍힘. **재빌드 후 재검증 대기 중** — 이게 크게 나오면(수백 ms) ①~⑥ 구간이
범인으로 확정되고, 여전히 작게 나오면(§3.6 보정치인 ~100~125ms 근처) appsrc 이후~클라이언트
수신 사이의 무언가(§3.1~3.5 중 아직 안 뒤집힌 것, 또는 서버 쪽에 우리가 아직 안 본 다른 큐)를
다시 찾아야 함.

---

### 3.11. "얼어붙은 백로그" 메커니즘 확인 — cv2에선 확정, libVLC엔 그대로 적용 안 됨 (2026-08-19)

**cv2 쪽에서 확정**: `cv2.VideoCapture()` 생성자가 1.9~2.9초 걸림(연결마다 다름). 그동안 서버는
계속 실시간으로 프레임을 밀어넣고, 생성자가 리턴하는 순간 이미 ~25프레임(~650~800ms 분량) 백로그가
쌓여있어서 처음엔 2~4ms 간격으로 몰아서 나오다가(버스트) 33ms 정상 페이스로 안정화됨. 20초짜리
`CAP_PROP_POS_MSEC` vs 벽시계 비율 추적(`cv2_view_test.py`)으로 **버스트 이후 ratio가 0.999~1.000에
정확히 고정되고 전혀 안 줄어든다는 걸 확인** — 즉 연결 시점에 쌓인 백로그가 세션 내내 영구 고정
지연이 됨. 사용자가 처음 냈던 가설("연결할 때 생긴 지연이 계속 고정된다")과 정확히 일치.

**libVLC(rc_gui가 실제 쓰는 것)엔 그대로 적용 안 됨**: `play()` → `MediaPlayerPlaying` 이벤트가
**18.7ms**로 거의 즉시(cv2의 1.9~2.9초와 다름), 그 순간 PTS도 0 — 느린 오픈으로 인한 백로그
메커니즘 자체가 없음. `set_rate()`로 연결 직후 배속 재생해서 혹시 모를 백로그를 밀어내는 방법을
시도했으나 **이 라이브 RTSP 소스에 `set_rate()`를 호출하면 이후 `player.stop()`에서 access
violation 네이티브 크래시가 남**(캐치업 코드를 완전히 뺀 순정 버전은 크래시 없음 — 직접 대조
테스트로 확인, `video_panel.py`는 안전하게 원복함). 라이브 스트림에 대한 트릭플레이(배속)는
이 libVLC 빌드에서 안전하지 않은 것으로 보임 — 이 mechanism 폐기.

PTS 기반으로 12초간 지연을 직접 추적(`vlc_lag_trace.py`)해보니 100~300ms 범위에서 오르내리고
뚜렷한 성장세는 없었으나, 스크린샷 실측(441~462ms)보다 작아서 `get_time()`이 디코드/디먹스
위치까지만 반영하고 그 뒤(vout 큐 등) 구간은 못 잡는 것으로 추정 — 미해결.

### 3.12. frame-threading 가설(다른 세션 분석) — 테스트했으나 효과 없음, 기각 (2026-08-19)

다른 세션에서 제안된 가설: NVENC이 프레임당 슬라이스 1개로 인코딩(코드 확인됨, 슬라이스 설정
안 건드림)하는데, 클라이언트가 avcodec 스레드 수를 auto(이 PC는 논리 코어 10개)에 맡기면
slice-threading이 불가능해서 libavcodec이 자동으로 frame-threading으로 전환하고, 스레드 수만큼
(N프레임) 디코드 지연이 구조적으로 생긴다는 이론 — ffmpeg 공식 문서에 명시된 실제 동작이고,
cv2와 libVLC가 둘 다 내부적으로 libavcodec을 쓰므로 "서로 다른 두 클라이언트가 같은 크기의
지연을 보인 이유"까지 통일되게 설명하는 꽤 설득력 있는 가설이었음.

cv2로 `threads=1` vs 기본값(auto) 비교 시도 — 처음엔 절대 지연 수치가 ~450ms 차이 나서 이론이
맞는 것처럼 보였으나, **이 측정 자체가 결함이 있었음**: rc_gui가 백그라운드에서 계속 같은
스트림에 연결돼 있어서(§3.11) 공유 미디어의 PTS 클록이 테스트 연결 시점과 무관하게 계속
흘러가고 있었고, 그래서 "지연"으로 계산한 값이 스레딩 효과가 아니라 그냥 "테스트를 언제
실행했느냐"는 우연한 오프셋을 재고 있었음(같은 threads=auto 조건을 재측정하니 -1023ms →
-2226ms로 딴 값이 나와서 발각).

**`video_panel.py`(실제 rc_gui, libVLC)에 `--avcodec-threads=1`을 직접 걸고, §3.9와 똑같은
동시 스크린샷 방식(신뢰할 수 있는 방법)으로 재검증** — 결과 **484ms, threads=auto와 동일한
수준(441~462ms)**. **효과 없음 — 이 가설 기각.** 부하 위험(싱글스레드 디코드 강제)만 있고 이득이
없어서 되돌림.

### 3.13. capture_to_push_ms 실측 확정 — 216ms, 우리 코드 결백 확인 (2026-08-19)

§3.10에서 구현한 FIFO 큐 기반 `capture_to_push_ms` 로깅을 재빌드 후 실측:

```
PUSH seq=1385 utc_ms=1787090850416.000 capture_to_push_ms=213.698
PUSH seq=1386 utc_ms=1787090850454.000 capture_to_push_ms=233.191
... (20프레임, 203.8~233.2ms 범위, 평균 ≈216ms)
```

§3.6 보정치(nExtraOutputDelay=3 → ~100~125ms 추정)보다 **거의 2배 큼**. 우리 코드가 원인인지
NVENC 자체가 원인인지 가르기 위해 `RtspStreamComponent.cpp`에 추가 세분화 로그를 넣음:
- `queue_wait_ms` = 게임스레드가 render command를 enqueue한 시각 → 그 람다가 실제로 실행되기
  시작하는 시각(다른 렌더 작업에 밀린 시간 포함)
- `encode_call_ms` = `EncodeFrame()` 호출 자체의 동기 실행 시간(GPU CopyResource 디스패치 +
  NVENC 제출 + 리드백 호출)

재빌드 후 실측 결과 (20프레임):
```
queue_wait_ms:  0.66 ~ 15.08ms
encode_call_ms: 0.21 ~ 0.79ms
```

**결론**: 둘 다 무시할 수준(합쳐도 최대 ~16ms) — `capture_to_push_ms`(216ms)의 **90% 이상이
이 두 구간 어디에도 없음**. `EncodeFrame()` 호출이 0.5ms 만에 리턴한다는 건 GPU 작업이 비동기로
디스패치되고 바로 리턴한다는 뜻이고, 실제 인코드 완료 데이터는 몇 프레임 뒤에야 돌아옴(nExtraOutputDelay
파이프라이닝, §3.6) — 즉 **216ms는 우리 코드(render command 스케줄링, 호출 오버헤드)가 아니라
NVENC 인코더 자체의 내부 버퍼 깊이**임. 3프레임(~100ms)이라는 기존 가정보다 실제로는 그 두 배
가까이 되는 것으로 보임(정확한 프레임 수는 미확인 — GPU 쪽 실제 완료 지연이거나 SDK의 실제
버퍼 깊이가 가정보다 큰 것으로 추정, 더 파려면 NVENC 쪽 GPU 타임스탬프 쿼리가 필요해서 여기서
멈춤).

**의의**: §2 #1(서버 인코드 구간)이 이제 진짜로 확정됨 — 원인은 UE 코드가 아니라 NVENC 자체. 위
"현재 상태 요약"의 서버 쪽 216ms가 이 결과.

**2026-08-19 이 결론도 반박됨 — §3.14 참고.** 216ms 자체가 진단 코드 버그로 오염된 값이었음이
밝혀짐. 아래 §3.14 확인 전까지 216ms는 신뢰하지 말 것.

### 3.14. capture_to_push_ms 재조사 — FIFO 큐 버그 발견, 216ms는 오염된 값이었음 (2026-08-19)

사용자가 "3~4프레임이면 100~130ms인데 어떻게 216ms가 나오냐"고 산수로 지적 — 맞는 지적이었음.
§3.13에서 `lookaheadDepth`가 범인일 거라 추측했으나 NVENC 프리셋 로그로 직접 확인해보니
**`lookaheadDepth=0`, `OutputBufferDelay=3`, 정확히 100.0ms — 처음 가정 그대로**였음(추측 틀림).

그래서 FIFO 큐가 pop되는 순간 실제로 몇 개나 쌓여있는지 직접 로그로 찍어봄
(`queue_depth_at_pop`) — 결과: **3이 아니라 16으로 고정**되어 있었음.

**원인**: 새 RTSP 클라이언트가 붙을 때마다 서버는 강제로 키프레임을 요청하는데
(`bForceKeyframe`), 그 순간 NVENC 파이프라인에 이미 들어가 있던 P프레임들은 `NvencD3D12Encoder.cpp`의
`bWaitingForRequestedKeyframe` 로직이 "요청한 진짜 IDR이 아니다"라며 내부에서 조용히 버림
(`continue`로 스킵, `AccessUnits`에 안 들어감). 근데 그 버려지는 프레임들도 제출될 때 FIFO 큐에
타임스탬프가 하나씩 이미 들어가 있었던 것들이라, **버려진 프레임은 pop이 안 되니 그 타임스탬프가
큐에 영원히 남음**. 오늘 세션 동안 rcws에 테스트 클라이언트를 수십 번 연결했으니(cv2 여러 번,
libVLC 여러 번, rc_gui 등) 재연결마다 몇 개씩 쌓여서 16까지 불어난 것.

**결과적으로 §3.13의 216ms는 "지금 이 프레임의 진짜 지연"이 아니라, 큐 맨 앞에 남아있던 (한참
전에 버려졌어야 할) 오래된 타임스탬프를 잘못 꺼내 쓴 오염된 값이었음.** 실제 서버 쪽 지연은
NVENC 프리셋 로그로 확인된 이론치 **100ms**(3프레임 @ 30fps)에 훨씬 가까울 가능성이 큼 —
사용자의 산수 지적이 정확히 이 버그를 찾아낸 것.

**수정**: `RtspStreamComponent.cpp` — `bForceKeyframe`가 true인 틱(새 연결로 인한 폐기가 막
시작되는 시점)에 `PendingQueue->Empty()`로 큐를 통째로 비움. 그 시점 이후 곧 버려질 프레임들의
타임스탬프를 미리 정리하는 것이므로 실제 데이터 유실은 아님.

**재빌드 후 재검증 완료(2026-08-19)**: `queue_depth_at_pop`이 이제 **4로 고정**(pop 직전 값이라
실제 유지 깊이는 3 — 이론치와 정확히 일치), `capture_to_push_ms`는 **95~128ms, 평균 ≈112ms**로
안정적. 버그 수정 확인됨 — **서버 인코드 구간의 진짜 값은 112ms**(216ms 아님). 위 "현재 상태
요약"/§1.1/§1.2/§2 #1에 전부 반영함.

**부작용**: 서버 쪽이 216→112ms로 줄어든 만큼, 클라이언트 쪽 미해결 구간이 오히려 커짐
(~230~260ms → ~320~360ms) — 지금 이 문서에서 가장 큰 미해결 구간이 됨. 다음 조사는 여기 집중
(§5).

---

### 3.15. 서버 쪽 112ms를 실제로 줄이는 시도 — nExtraOutputDelay 3→1, RCWS fps 30→60 (2026-08-19)

사용자가 클라이언트 조사 전에 서버 쪽부터 안전하게 줄여보자고 요청 — 두 가지 독립적인 레버를
같이 적용함.

**① NVENC `nExtraOutputDelay` 3 → 1**. 추가 조사로 위험한 지점이 정확히 어딘지 좁혀짐:
- `NvEncoder.h:553`에 **벤더(NVIDIA) SDK 헤더 자체의 공식 주석**: "그래픽과 인코드가 병렬로
  동작하려면 `m_nExtraOutputDelay`는 최소 1 이상이어야 한다" — 0만 특별히 위험하고 1은 벤더가
  보증하는 안전한 최소값. 짐작이 아니라 벤더 문서에 적힌 값.
- `m_nEncoderBuffer = frameIntervalP + lookaheadDepth + nExtraOutputDelay`(+temporal filter
  보정) — `=0`이 위험한 이유는 정확히 `frameIntervalP=1, lookaheadDepth=0`(§3.14에서 실측
  확인)일 때 `m_nEncoderBuffer`가 1이 되어, "방금 제출한 프레임"의 GPU 완료를 그 자리에서
  곧바로(`WaitForCompletionEvent`, `NvEncoder.cpp:721`) 기다리기 때문. 근데 그 프레임의
  CopyResource 커맨드는 `RHICmdList.EnqueueLambda`로 "예약"만 된 상태고 아직 UE 렌더러가 GPU
  큐에 flush하기 전이라, 시작도 안 한 작업의 완료를 기다리는 진짜 데드락이 됨. `=1`(버퍼 2개)은
  "1틱 전에 제출한" 프레임을 요청하므로 그 사이 렌더 커맨드 리스트 제출 경계를 최소 한 번은
  지나 있을 게 거의 확실 — 구조적으로 그 데드락 경로 자체를 피함.
- 추가 안전판: `WaitForCompletionEvent`(`NvEncoder.cpp:929`)는 `#ifdef DEBUG`가 아닌 빌드에서
  `INFINITE`가 아니라 **20초 타임아웃**을 씀(946줄). 이 프로젝트 빌드엔 벤더 SDK가 쓰는
  `DEBUG` 매크로가 정의되어 있지 않음(`RtspEncoder.Build.cs` 확인) — 즉 최악의 경우에도 진짜
  영구 데드락이 아니라 20초 뒤 자동 복구됨(그래도 5스트림×매틱 반복되면 체감상 멈춘 것처럼
  보일 수 있어서 재확인은 필요).
- 수정: `NvencD3D12Encoder.cpp`의 `new NvEncoderD3D12(...)` 호출에 `nExtraOutputDelay=1`을
  명시적으로 넘김(벤더 파일은 안 건드림, 우리 쪽 호출부만 수정).

**② RCWS 스트림 fps 30 → 60**. NVENC 버퍼는 "프레임 개수" 단위로 고정이라, 프레임당 시간을
줄이면(fps를 올리면) 버퍼가 차지하는 ms도 비례해서 줄어듦(3프레임 @ 30fps=100ms → 1프레임
@ 60fps 신설정으로는 더 작아짐). `VehicleRtspBridgeComponent.cpp`에서 5개 스트림 전부 fps
지정 없이 만들어져서 `URtspStreamComponent`의 C++ 기본값(30)을 그대로 쓰고 있었음 — RCWS(조준용,
가장 지연에 민감)만 60으로 올림. CCTV 4개는 상황 인지용이라 GPU 부하를 더 늘릴 이유가 적어서
30 유지.

**기대 효과**: 두 변경이 곱으로 작용 — 버퍼 3프레임→1프레임, 프레임 시간 33.3ms→16.7ms.
이론상 서버 인코드 구간이 112ms → ~17ms까지 줄어들 가능성(1프레임 @ 60fps).

**재빌드 후 재검증(2026-08-19)**: `nExtraOutputDelay=1` 쪽은 완전히 성공 — 로그로
`EncoderBufferCount=2 OutputBufferDelay=1`(rcws 16.7ms@60fps, CCTV 33.3ms@30fps) 확인,
데드락/에러 없음, `capture_to_push_ms`가 **24~28ms**로(112ms에서 4배 이상 개선) 안정적으로 나옴.

**근데 fps 쪽에서 부작용 발견**: 사용자가 통제기 목업으로 확인하니 **0.5초 정상 재생 →
~4초 멈춤을 반복**하는 증상이 나타남. 서버 로그(capture_to_push_ms, PUSH 간격, 재연결 횟수)는
전부 깨끗해서 **서버가 멈춘 게 아님** — RCWS를 60fps로 올리면서 대역폭은 그대로(4000kbps)라
프레임당 비트가 절반이 된 것, 또는 fps 2배로 인한 클라이언트(libVLC) 쪽 디코드/버퍼링 부담
증가가 원인으로 추정됨(정확한 원인 미확인). 두 변경을 동시에 넣어서 원인 분리가 안 되므로
**fps는 30으로 되돌리고 `nExtraOutputDelay=1`만 남김** — 이것만으로도 검증된 안전한 개선
(112ms→~33ms 예상, rcws도 CCTV와 같은 30fps 기준). **fps 인상은 별도 항목으로 나중에 재시도할
것(§5) — 이번엔 원인 규명 없이 그냥 되돌림.**

**되돌리기 전 사용자 관찰(단서)**: 재빌드 안 한 상태(60fps+nExtraOutputDelay=1)로 PIE+목업을
몇 분 계속 켜두니 화면이 안정화됨. 근데 PIE를 껐다가 목업을 다시 시작하면 문제가 다시
발생함(초반 몇 분간 0.5초/4초 반복, 그 이후 안정화). **연결 초기에만 나타나고 시간이 지나면
스스로 해소되는 패턴** — §3.11의 "얼어붙은 백로그"류 워밍업 현상과 비슷한 계열일 가능성.
재빌드(fps 30으로 되돌림) 후에는 시작하자마자 바로 안정적이었음(사용자 확인). 60fps 재시도
시(§5 0번) 이 초기 워밍업 패턴부터 재현/조사할 것.

**최종 결과(2026-08-19, 사용자 육안 확인 + 로그 재검증)**: fps 되돌리고 `nExtraOutputDelay=1`만
남긴 빌드로 재검증 — 시작하자마자 안정적, 딜레이 감소가 육안으로도 확인됨. **`capture_to_push_ms`
직접 재확인: 32.6~52.2ms, 평균 ≈46.5ms**(20프레임, fps=30 기준 — 이전 추정치 "~33ms"보다 실측이
조금 더 크지만 100ms 이하는 확실히 검증됨). **현재 총 지연 300ms대 중반**(이전 441~484ms에서
개선). 서버 쪽 작업은 여기서 일단 마무리 — 다음은 클라이언트 쪽(§5 1~3번, §3.16).

---

### 3.16. 클라이언트 쪽(libVLC) 근본 원인 규명 — 해상도 오추측→디코더 재시작, 그리고 막다른 벽 (2026-08-19)

서버 쪽이 46.5ms로 정리된 뒤 클라이언트 쪽(~270~310ms) 조사 재개. §5 1~3번(vout 모듈,
RTSP 전용 캐싱, RTP jitter buffer)을 순서대로 확인.

**① vout 모듈 확인**: `--verbose=2 --file-logging`로 실제 재생 시 로그 확인 —
`main debug: using vout display module "direct3d11"`, 디코드도
`avcodec: Using D3D11VA (NVIDIA GeForce RTX 5060...) for hardware decoding`. 둘 다 GPU
가속 경로라 그 자체는 안 느릴 것으로 예상.

**② `avcodec-hw=none`으로 소프트웨어 디코드 강제 후 비교** — 인스턴스 옵션(`--avcodec-hw=none`)
으로는 안 먹혔고(로그로 여전히 d3d11va 확인), 미디어 옵션(`:avcodec-hw=none`)으로 하니 실제로
소프트웨어 디코드로 전환됨(`no hw decoder modules matched` 로그 확인). 이 상태로 다시 목업/기존
설정(하드웨어 디코드)과 스크린샷 비교 — **완전히 동일한 타임스탬프**가 나옴(사용자가 직접
확인). 즉 **하드웨어냐 소프트웨어냐는 지연에 영향 없음** — 이걸로 §3.12의 "avcodec-threads=1이
효과 없었다"는 결과의 진짜 이유도 설명됨: 이 스트림은 D3D11VA 하드웨어 디코드를 쓰고 있어서
avcodec의 소프트웨어 스레드 설정(frame-threading 포함) 자체가 애초에 무관했던 것.

**③ 결정적 로그 발견 — 연결 초기 디코더 재시작 히컵**: 10초짜리 verbose 로그 전체를 훑어보니
연결 직후 이런 시퀀스가 나옴:
```
d3d11va debug: Detected size change 634x480          ← 처음엔 잘못된 해상도로 추측
...
main error: buffer deadlock prevented
main debug: Decoder wait done in 209 ms               ← 209ms 대기
main warning: picture is too late to be displayed (missing 132 ms)
main warning: picture is too late to be displayed (missing 98 ms)
main warning: picture is too late to be displayed (missing 65 ms)
main warning: picture is too late to be displayed (missing 32 ms)  ← 33ms씩 줄며 4개 폐기
...
main error: ES_OUT_SET_(GROUP_)PCR is called too late (pts_delay increased to 35 ms)
main debug: ES_OUT_RESET_PCR called
main debug: Buffering 0%→95%, Stream buffering done (66 ms in 67 ms)
```
libVLC가 연결 초기 해상도를 잘못 추측(634x480)했다가 실제 데이터로 뒤늦게 정정(1232x928)하면서
**디코더를 통째로 재시작** — 그 과정에서 209ms 대기 + 재버퍼링(66~99ms대) + PCR 리셋까지
연쇄로 발생. 총 비용이 어림잡아 200~400ms대로, 지금 우리가 쫓는 미해결 구간(~270~310ms)과
크기가 맞아떨어짐. §3.11의 "얼어붙은 백로그"와 결과는 비슷하지만(연결 초기에 낀 지연이 그대로
고정) **원인 메커니즘은 다름**(cv2는 "연결 자체가 느림", libVLC는 "해상도 오추측→재시작").

**"picture is too late to be displayed"의 의미**: VLC 자체에 이미 "너무 늦은 프레임은 화면에
안 그리고 버리는" 로직이 있음(사용자 질문에 대한 답 — 이 4개 프레임이 실제로 그 사례). 근데
이 판정은 **VLC 자신의 내부 클록(PCR) 기준**이라, 저 재시작 히컵으로 클록 자체가 이미 200~300ms
밀린 채로 세팅되고 나면, 그 이후 도착하는 프레임들은 그 클록 기준으론 정시라 버려질 이유가
없음 — "한 번 밀린 시각을 새 기준점으로 고정하고 그 뒤로는 정상 재생"하는 패턴이 되어, 지속적인
재동기화(라이브 엣지로 계속 따라붙기)는 안 하는 것으로 보임(주기적 재동기화 관찰은 안 됨, 10초
캡처 한정 — 더 긴 로그로 검증은 안 함).

**서버 SPS 자체는 결백 확인**: SDP의 `sprop-parameter-sets`를 직접 파싱해봄 — 정확히 1226x928
(크롭 반영), 1232x928(코딩 크기)로 올바르게 인코딩되어 있음. VLC가 SDP의 SPS를 활용 안 하고
왜 처음에 634x480으로 잘못 짚는지는 libVLC/live555 내부 동작이라 이 프로젝트 코드로는 원인
규명도 수정도 불가능해 보임.

**사후 캐치업(재시작 이후 강제로 라이브 엣지로 점프)도 막혀있음**: `player.is_seekable()`을
직접 확인 — **`False`**. SDP가 `a=range:npt=now-`(라이브, 논시커블)로 선언돼 있어서 VLC가
seek 자체를 거부함. `set_rate()`(§3.11, 크래시남)에 이어 `set_time()`도 시도할 것도 없이
API 레벨에서 막혀있음이 확인됨 — **이 프로젝트 코드로 사후 캐치업을 구현할 방법이 libVLC
공식 API로는 없음.**

**결론 — 막다른 벽**: 클라이언트 쪽 ~270~310ms는 근본 원인(해상도 오추측→디코더 재시작)까지는
찾았지만, 그 원인도 결과(seek 불가)도 전부 libVLC/live555 내부 동작이라 이 프로젝트 코드에서
손댈 레버가 없음. 남은 선택지 두 가지:
1. **video_panel.py의 백엔드를 libVLC → cv2로 교체** — cv2는 §3.11에서 "연결 시 몰아오는
   백로그"를 명확히 관측했고, 그건 애플리케이션 코드로 직접 감지·스킵하는 로직을 안전하게
   구현할 수 있음(VLC 내부 API를 안 건드리니 크래시 위험 없음). 단점: `set_hwnd` 네이티브
   렌더링을 못 쓰게 되어 캡처스레드/프레임큐/디스플레이타이머 구조가 되돌아옴(과거에 없앤 이유
   그대로 다시 생김), `cv2.VideoCapture()`가 블로킹 호출이라 별도 스레드 필요(1.9~2.9초 동안
   GUI 프리징 방지), 하드웨어 디코드가 기본 보장 안 됨(5스트림 CPU 부하 우려), 재연결 로직
   새로 작성 필요.
2. **여기서 서버 개선까지만 마무리하고 클라이언트는 보류** — 이미 441~484ms → 300ms대 중반으로
   상당한 개선을 이뤘고, 나머지는 libVLC/RTSP+live555 조합 자체의 구조적 한계일 가능성이 높음.

**사용자 결정 대기 중** — 다음 세션/작업에서 방향 정할 것. → **2026-08-19 결정: cv2로 전환
진행**(§3.17).

---

### 3.17. cv2 전환 착수 — 정밀 측정 방법 확보, 고정 13프레임 지연 발견, VUI 원인 일부 규명 (2026-08-19)

`video_panel_cv2.py`(신규 파일) — cv2 전환 1단계, RCWS 뷰만 표시(조이스틱/재연결 등 다른 기능
없음). `cv2.VideoCapture()`가 블로킹이라 별도 스레드에서 돌리고 `pyqtSignal`로 메인 스레드에
프레임 전달.

**연결 직후 캐치업(백로그 스킵) 로직 추가** — read() 간격이 정상 프레임 간격의 절반 이상이 될
때까지(=백로그 다 소진하고 실시간 페이스 따라잡을 때까지) 화면에 안 그리고 버림. 실측: 21프레임
건너뜀. **근데 육안 확인 결과 지연 그대로(~400ms)** — §3.11의 "연결 시 쌓인 백로그가 그대로
고정" 이론이 **불완전했음**이 드러남(버스트 자체는 실재하지만, 그걸 스킵해도 밑에 깔린 진짜
지연은 안 없어짐).

**`threads=1`로 재시도** — 버스트 자체가 사라짐(0프레임 건너뜀, 처음부터 정상 페이스로 들어옴).
**그런데도 지연 그대로**(사용자 육안 확인, 스크린샷 정밀 실측 426ms). 이걸로 "지연 = 쌓인
백로그" 가설 자체가 완전히 틀렸음이 확정됨 — 큐에 아무것도 안 쌓여있는데도(0프레임 스킵) 지연이
그대로라는 건, 문제가 "쌓인 걸 못 비워서"가 아니라 **매 프레임이 개별적으로 일정하게 밀려서
나온다**는 뜻.

**정밀 측정 방법 확보 — 스크린샷 불필요, 자동화**: `cv2_precise_lag.py`(신규) — 원시 RTP 소켓
프로브(`latency_probe.py`와 동일 원리, ground truth)와 cv2를 거의 동시에 같은 URL에 연결.
RTP 타임스탬프는 서버가 결정론적으로 매기는 값이라 두 연결의 로컬 seq 번호가 거의 같은 실제
프레임을 가리키게 됨 — "지금 막 도착한 최신 seq"(원시 프로브) vs "cv2가 지금 내놓는 seq"
(POS_MSEC 기반)를 실시간으로 비교, seq 차이 × frame_duration = 정확한 지연(ms). UTC 시각
변환도 스크린샷도 전혀 필요 없음.

**결과: 정확히 13프레임(433.3ms), 편차 0(130개 샘플 전부 동일)**. 지터/네트워크 변동이 아니라
**완전히 고정된 파이프라인 깊이**라는 뜻 — `max_delay`/`reorder_queue_size`/`buffer_size`/
`threads` 전부 안 먹혔던 이유(애플리케이션 옵션이 아니라 더 구조적인 무언가).

**웹 검색 + FFmpeg 소스 확인으로 원인 일부 규명**: H.264 VUI의 `num_reorder_frames`(디코더가
프레임을 몇 개나 재정렬 대기시켜야 하는지)는 선택 필드 — 인코더가 안 채우면 디코더는
`h264_ps.c`의 로직대로 **레벨(3.2) 기준 보수적인 기본값**을 씀(`level_max_dpb_mbs[level] /
(mb_width*mb_height)` 공식, GitHub `FFmpeg/FFmpeg/libavcodec/h264_ps.c` 직접 확인). 우리
SPS엔 `bitstream_restriction_flag`가 꺼져있어서(NVENC 기본값) 디코더가 이 스트림이
`frameIntervalP=1`(재정렬 불필요)이란 걸 몰랐던 것.

**수정**: `NvencD3D12Encoder.cpp`에 `EncodeConfig.encodeCodecConfig.h264Config
.h264VUIParameters.bitstreamRestrictionFlag = 1;` 추가(NVENC SDK, `nvEncodeAPI.h`의
`NV_ENC_CONFIG_H264_VUI_PARAMETERS` 구조체 — 개별 숫자 필드는 없고 플래그만 있음, NVENC이
실제 인코드 설정 기준으로 알아서 채워줌). 순수 SPS 메타데이터 변경이라 인코딩/GPU 작업엔
영향 없음, 안전.

**재검증 결과 — 부분 성공**: **13프레임(433.3ms) → 11프레임(366.7ms)**, 2프레임(66.7ms) 개선.
여전히 완전히 고정값(130개 샘플 전부 366.7ms, 편차 0). **VUI 이론은 방향은 맞았지만 전체를
설명 못 함** — 남은 11프레임(367ms)의 정체는 아직 미해결. 다음 조사 후보: (a) VUI 신호가
디코더에 실제로 온전히 반영되는지 재확인(SPS 다시 파싱해서 bitstream_restriction 필드값 직접
검증), (b) 이 11프레임이 데드 코드 상 RTSP 데먹서(demux) 레이어의 별도 버퍼링인지, (c) 서버
쪽에 아직 못 찾은 다른 고정 지연원이 있는지.

---

### 3.18. 수신측을 cv2/libVLC에서 GStreamer+NVDEC로 — 결정적 개선 (2026-08-19)

사용자가 "GPT한테 물어보니 cv2/libVLC는 원래 느리고, 수신측도 송신측처럼 GStreamer+NVDEC 쓰는 게
저지연에 정석"이라는 의견을 제시 — 실제로 이 프로젝트가 통제기(LIG) 소프트웨어 개발 주체는
아니지만, LIG에 "이런 식으로 디코딩해달라"는 레퍼런스 파이프라인을 제공하고 싶어함. 검증 없이
권하지 않고 먼저 직접 테스트.

**환경**: 이 PC에 GStreamer가 이미 설치돼 있고(서버 쪽 플러그인이 씀) `nvcodec` 플러그인의
`nvh264dec`(NVDEC 하드웨어 디코더)도 확인됨. `gst-launch-1.0.exe`로 최소 수신 파이프라인
직접 테스트:

```
gst-launch-1.0 rtspsrc location=rtsp://.../ugv/rcws latency=0 protocols=tcp ! \
  rtph264depay ! h264parse ! nvh264dec ! d3d11videosink
```

**결과 — 첫 시도부터 극적으로 빠름**:

| 설정 | 지연(스크린샷 실측) |
|---|---|
| cv2 (VUI 수정 후, 튜닝 다 적용) | 367ms (§3.17, 정밀 seq 대조) |
| GStreamer+NVDEC, `rtspsrc latency=0`만 | **149ms** |
| + `sink sync=false` | **~100ms** |

`latency=0` 프로퍼티 하나 명시한 것만으로 cv2/libVLC 대비 2.5배 이상 빠름 — **GStreamer의
지터버퍼(`rtpjitterbuffer`)는 `rtspsrc`의 `latency` 프로퍼티로 명시적으로 노출·문서화되어 있고
기본값이 2000ms**(`gst-inspect-1.0 rtspsrc`로 확인)라, 모르고 쓰면 오히려 매우 느릴 수 있지만
반대로 알고 쓰면 바로 낮출 수 있음 — cv2/libVLC에서 우리가 몇 시간을 들여 파헤쳐야 했던 "정체불명
고정 지연"이 GStreamer에서는 그냥 문서화된 프로퍼티 하나였다는 뜻.

**추가로 확인된 저지연 프로퍼티** (`gst-inspect-1.0`로 직접 확인):
- `nvh264dec`의 **`max-display-delay`**(기본값 -1=auto, "디코드와 화면 표시 사이 파이프라이닝
  개선" — 우리가 cv2/libVLC에서 쫓던 것과 같은 부류의 디코더 내부 고정 지연으로 추정, 여기선
  `=0`으로 명시 가능) — cv2/ffmpeg에선 이런 게 아예 노출이 안 돼서 못 건드렸던 것과 대조적.
- `rtspsrc`의 **`drop-on-latency`**(기본 false → true 권장, 레이턴시 넘는 패킷 버림).
- `sink`의 `sync=false`(파이프라인 클록 동기화 대기 생략).

**최종 테스트 파이프라인**(사용자 재검증 대기 중, PIE 재빌드 때문에 중단됨):
```
gst-launch-1.0 rtspsrc location=rtsp://.../ugv/rcws latency=0 drop-on-latency=true protocols=tcp ! \
  rtph264depay ! h264parse ! nvh264dec max-display-delay=0 ! d3d11videosink sync=false
```

**서버 쪽도 동시에 한 단계 더 튜닝**: NVENC `tuningInfo`를 `NV_ENC_TUNING_INFO_LOW_LATENCY`
(저지연용)에서 `NV_ENC_TUNING_INFO_ULTRA_LOW_LATENCY`(초저지연용, SDK에 값=3으로 존재,
`nvEncodeAPI.h` 확인)로 상향(`NvencD3D12Encoder.cpp`). RCWS fps도 60으로 재적용 —
`VehicleRtspBridgeComponent`에 `RcwsTargetFps`(기본 60, `EditAnywhere`) 프로퍼티를 신설해서
**재빌드 없이 에디터에서 바로 조절 가능**하게 함(§3.15에서 구형 libVLC 목업 조합과 같이 썼을 때
불안정했던 전례가 있어서 — GStreamer+NVDEC 조합에서는 재현되는지 아직 미확인, 재현되면 여기서
그냥 값만 낮추면 됨).

**최종 재검증 완료(2026-08-19, 서버 재빌드 후)**: VUI + `nExtraOutputDelay=1` +
`ULTRA_LOW_LATENCY` + RCWS 60fps 전부 반영된 서버 + 위 최종 GStreamer 파이프라인(모든 저지연
옵션 적용) 조합으로 스크린샷 실측 — **68ms**(02:02:23.993 − 02:02:23.925), 사용자 관찰로는
**~30~100ms 범위에서 변동, 순간적으로 30ms대까지도 나옴**. 최초 측정값(441~484ms) 대비
**약 85~90% 개선**. 사용자가 목표로 했던 "수십ms대"가 실제로 달성됨.

**정리 — 전체 개선 경로**:
| 단계 | 총 지연 | 무엇을 바꿨나 |
|---|---|---|
| 최초 실측(§3.9) | 441~484ms | — |
| 서버 버그 수정 후(§3.14/§3.15) | 300ms대 중반 | FIFO 큐 버그 수정, `nExtraOutputDelay` 3→1 |
| 수신측 GStreamer+NVDEC 전환(§3.18) | 68ms(30~100ms 변동) | `latency=0`/`drop-on-latency`/`max-display-delay=0`/`sync=false` + 서버 `ULTRA_LOW_LATENCY`+VUI+60fps |

**향후 방향**: 이 파이프라인이 충분히 검증됐다고 보고, rc_gui는 여기서 더 안 건드림(테스트용
목업이므로 — cv2 전환 작업은 이 결과로 보류/불필요해짐). **LIG에 이 GStreamer+NVDEC 기반
레퍼런스 파이프라인(gst-launch 커맨드 + 각 프로퍼티 의미 설명)을 전달**하는 방향으로 — 실제
통제기 소프트웨어 구현은 LIG 담당이므로 우리는 "이렇게 디코딩하면 저지연 나온다"는 검증된
참고 자료를 제공하는 역할. 남은 ~30~100ms의 변동 폭(왜 흔들리는지)은 필요하면 추가 조사
가능하지만, 이미 실용적으로 충분한 수준.

**레퍼런스 문서**: `rtsp_client_reception_guide.md`(같은 폴더) — LIG에 전달 가능한 형태로
정리, GStreamer+NVDEC를 메인으로 하고 cv2/libVLC는 "방법과 한계" 요약만 간단히 포함.

### 3.19. D3D11 vs D3D12, GStreamer 기반 rc_gui 목업 착수 (2026-08-19)

**D3D11 vs D3D12 비교**: `d3d11h264dec`(DXVA)와 `d3d12h264dec`(DXVA) 둘 다 테스트 —
**둘 다 50~80ms로 유의미한 차이 없음**. 참고로 D3D12 경로도 로그에 "NVIDIA GeForce RTX 5060"이
찍히는 걸 보면 **물리적으로는 같은 NVDEC 하드웨어**를 쓰는 것(NVIDIA 자체 API(CUVID,
`nvh264dec`)로 접근하냐 MS 표준 API(DXVA, `d3d11h264dec`/`d3d12h264dec`)로 접근하냐 차이일 뿐).
`d3d1x` 계열 sink/decoder 둘 다 `processing-deadline`(기본 15ms), `max-lateness`(기본 5ms),
`compliance`(H.264 스펙 준수 강도) 같은 추가 프로퍼티가 있음 — 다 낮춰봐도 유의미한 추가 개선은
없었음. **최종 선택: D3D11 + `nvh264dec`**(GStreamer D3D11 지원이 더 성숙하고, `nvh264dec`가
`max-display-delay` 같은 가장 명시적인 저지연 옵션을 제공해서).

**GStreamer 기반 rc_gui 비디오 패널 1단계 완료**: `video_panel_gstreamer.py`(신규) — libVLC
대신 GStreamer+NVDEC로 RCWS만 표시(다른 기능 없음, cv2 전환 때와 같은 "일단 창부터" 원칙).
PyGObject(공식 파이썬 바인딩)는 Windows에 pip 설치 안 됨(meson 빌드가 `girepository-2.0`
요구, 직접 확인) — **ctypes로 GStreamer C API 직접 호출**하는 방식으로 우회:
- `gst_parse_launch()`에 파이프라인 문자열 전체(gst-launch-1.0과 같은 문법)를 넘겨서 개별
  프로퍼티마다 `g_object_set` 호출할 필요 없앰 — ctypes 바인딩이 최소한으로 줄어듦.
- `gst_video_overlay_set_window_handle()`(`gstvideo-1.0-0.dll`)로 libVLC의 `set_hwnd`와
  같은 방식으로 Qt 위젯에 임베딩.
- 시행착오 2가지: (1) Windows GStreamer DLL엔 `lib` 접두사가 없음(`gstreamer-1.0-0.dll`,
  `libgstreamer-1.0-0.dll` 아님). (2) `os.add_dll_directory()`만으론 부족 — GStreamer 내부
  플러그인 로더(각 `.dll` 플러그인의 의존성 해석)는 `PATH` 환경변수 자체를 봐야 해서
  `os.environ["PATH"]`에 GStreamer bin 경로를 직접 추가해야 플러그인 로딩이 됨.

**결과**: 사용자 확인 — 정상 동작(영상 표시됨). cv2 때처럼 블로킹 연결 문제도 없음(GStreamer
파이프라인 생성/재생 시작 자체가 비블로킹이라 별도 스레드 불필요 — cv2보다 구조가 단순함).

---

### 3.20. 자체방호축(이동형지휘소) RTSP 스트림 연결성 검증 (2026-08-19)

자체방호축(`TitanTruck::SetupRtspStreams()` + `UAVPawn`)이 UGV축과 완전히 동일한
`RtspStreamComponent`/`FNvencD3D12Encoder` 코드를 공유해서 등록하는 마운트라, 인코더 설정
(`ULTRA_LOW_LATENCY`, `nExtraOutputDelay=1`, VUI `bitstreamRestrictionFlag=1`)은 이미 자동
적용된 상태 — 별도 서버 코드 작업 없이, §2.1의 GStreamer 저지연 파이프라인으로 실제 접속만
검증함(PIE, SelfDefense 축):

```
gst-launch-1.0 rtspsrc location=rtsp://127.0.0.1:8554/selfdefense/<mount> latency=0 \
  drop-on-latency=true protocols=tcp ! rtph264depay ! h264parse ! nvh264dec max-display-delay=0 \
  ! fakesink sync=false
```

`front_cctv`/`rear_cctv`/`left_cctv`/`right_cctv`(240×136)/`rcws`(1116×622)/`uav_gimbal`
(640×360) 6개 전부 ERROR/WARN 없이 `nvh264dec`까지 캡스 협상 성공(CUDA 메모리로 하드웨어
디코드 확인). `env_camera`는 상위체계로는 안 보내도 되는 부가 스트림이라 이번 검증에서 제외 —
계속 등록은 돼 있음(제거 안 함, 2026-08-19 사용자 확인).

**정밀 지연(§3.9/§3.18 방식의 스크린샷 동시 캡처 실측)은 아직 안 함** — 인코더/서버 코드가
UGV축과 축 구분 없이 완전히 동일해서 이론상 §3.18의 68ms대와 동등한 수준이 기대되지만, 이건
아직 "기대"지 실측 확정 아님. 정밀 재측정하려면 UGV축 §3.9와 같은 방식(양쪽 화면에 UTC
타임스탬프 동시 표시 후 스크린샷 비교, 또는 `LatencyClockComponent`를 TitanTruck의 RCWS/CCTV
쪽에도 붙여서 활용)이 필요함.

배포 토폴로지 확인: UGV축/자체방호축은 서로 다른 물리 PC에서 각자 독립된
`URtspServerSubsystem`(GameInstance당 1개, 포트 8554 고정)을 띄우므로 두 축이 같은 포트를
써도 충돌 없음 — 상위체계는 자체방호축 PC의 IP로, 원격통제기는 UGV축 PC의 IP로 각각 접속.
단, **같은 PC에서 두 축을 동시에 띄워서 로컬 테스트**하려면 실제로 포트 충돌이 남(`Port`가
`RtspServerSubsystem.h`에 `8554`로 하드코딩, 인스턴스별 오버라이드 불가) — 필요해지면 Config
프로퍼티로 빼는 작업 필요(2026-08-19 기준 미착수).

이 내용은 `rtsp_client_reception_guide.md`(LIG 공유용, §1.2/§2 참고)에도 반영함.

---

## 4. 참고 — 실측에 쓴 방법

- **UE 내부 타이밍**: `RtspStreamComponent.cpp`(제출 시각 캡처, `SubmitWallClockSeconds`) +
  `RtspServerSubsystem.cpp`(`PushEncodedFrame`에서 diff 계산, `LogRtspEncoder` 카테고리로 30프레임에
  1번 로그) — unreal-mcp `EditorToolset.LogsToolset.GetLogEntries`로 직접 조회하거나, 에디터 종료
  후 `Saved/Logs/titan_example.log`(또는 `-backup-*.log`, 세션이 새로 시작되면 이전 로그가 여기로
  이름이 바뀜)를 직접 읽어서 확인 가능.
- **GStreamer 내부 트레이스**: 에디터 실행 전 환경변수로 GStreamer 자체 디버그 로그를 파일로 뽑음:
  ```powershell
  $env:GST_DEBUG = "rtspmedia:5,rtspstream:5,rtpbin:4"
  $env:GST_DEBUG_FILE = "C:\working\mine\ugv_rc_gui\gst_debug.log"
  Start-Process "C:\working\works\kadex\titan_example\titan_example.uproject"
  ```
  (다음 조사 때 `rtsp-thread-pool:5`도 추가해서 §3.1을 직접 로그로 확인해볼 것.)

---

## 5. 다음 조사 우선순위 제안 (§3.15 이후 갱신, 2026-08-19)

서버 쪽은 §3.14/§3.15로 대부분 확정됨 — `nExtraOutputDelay=3→1` 적용 완료(안정성 확인됨,
112ms→~33ms 예상). fps 인상(rcws 30→60)은 통제기 목업에서 0.5초 정상+~4초 멈춤 반복 증상이
나와서 일단 되돌림(§3.15) — 원인 미규명 상태로 남음, 아래 0번으로 재분류. 클라이언트 쪽
~320~360ms(이제 서버가 더 줄었으니 실제로는 이보다 조금 더 클 수 있음)가 여전히 가장 큰
미해결 구간이고, 그동안 나온 가설들(프레젠테이션/얼어붙은백로그/frame-threading/서버 GStreamer
튜닝/network-caching)은 전부 실측으로 기각됨(위 "현재 상태 요약" 참고) — 아래는 아직 안 해본 것들:

0. **RCWS fps 인상 재시도(원인 규명 포함)** — §3.15에서 60fps 단독 효과를 못 밝히고 그냥
   되돌림. 재시도할 때는 (a) `nExtraOutputDelay=1`과 동시에 넣지 말고 **fps만 단독으로** 바꿔서
   테스트, (b) 4초 멈춤이 재현되면 GStreamer 쪽 로그(`GST_DEBUG=rtspmedia:5,rtspstream:5`)와
   libVLC verbose 로그를 같이 떠서 어느 쪽(서버 SDP/캡스 변경, 클라이언트 디코드 부담, 대역폭)
   문제인지 좁힐 것. 성공하면 이론상 33ms(1프레임@30fps)→17ms(1프레임@60fps)까지 추가 개선 가능.
1. **libVLC의 실제 vout(비디오 출력) 모듈 확인** — `--vout` 나열, 현재 뭐가 자동 선택되는지.
   §3.10에서 "그려지는 것 자체는 안 느림"을 GDI 직접 블릿으로 확인했지만, 그건 우리가 자체
   제작한 테스트고 libVLC의 실제 vout 파이프라인(내부 프레임 큐 등)은 여전히 안 들여다봄.
2. **libVLC의 RTSP 전용 캐싱 옵션이 `network-caching`과 별개로 있는지** — §3.7에서 단일
   스트림 테스트와 실제 앱(5스트림) 결과가 다르게 나왔던 이유가 아직 미해결(`--rtsp-caching`
   류 프로토콜 전용 옵션이 `network-caching`을 무시하고 따로 동작할 가능성).
3. **RTP jitter buffer**(디코더 앞단, network-caching과 다른 계층) 존재 여부 확인 — GStreamer의
   `rtpjitterbuffer` 같은 개념이 libVLC/ffmpeg의 RTP 수신 경로에도 있는지, 있다면 기본 target
   latency가 얼마인지.
   비중이라 우선순위는 1~3보다 낮음.
