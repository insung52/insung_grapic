# RTSP 영상 수신 가이드 — 저지연 디코딩 방법

이 문서는 저희 쪽 시뮬레이션 SW가 내보내는 RTSP 스트림을 **낮은 지연으로 수신·디코딩**하는
방법을 정리한 레퍼런스입니다. RTSP를 내보내는 축(axis)이 두 개 있습니다:

- **UGV축** (UGV 시뮬레이션 SW → 원격통제기): RCWS + CCTV 4개, 마운트 접두어 `/ugv/`.
- **자체방호축**(이동형지휘소 통제기 SW → 상위체계): CCTV 4개 + RCWS + UAV 짐벌(+환경 카메라),
  마운트 접두어 `/selfdefense/`.

두 축 다 서로 다른 PC에서 독립적으로 실행되고, 각자 자기 프로세스 안에서 RTSP 서버(포트
8554)를 하나씩 띄웁니다 — 상위체계는 이동형지휘소 PC의 IP로, 원격통제기는 UGV PC의 IP로 각각
접속하면 되고, 두 서버가 물리적으로 다른 머신이라 포트가 같아도 서로 충돌하지 않습니다.
수신 측(통제기/상위체계) 소프트웨어 자체의 개발/유지보수는 이 프로젝트의 범위가 아니지만,
저희 쪽에서 여러 수신 방식을 직접 실측 비교해본 결과를 공유합니다.

**결론부터**: **GStreamer + 하드웨어 디코드(NVIDIA GPU 기준 NVDEC)** 조합을 권장합니다.
같은 스트림을 다른 방식(OpenCV/ffmpeg, libVLC)으로 받았을 때보다 종단 지연이 **5배 이상**
낮게 나왔고(수백 ms → 수십 ms), 그 이유도 아래에 구체적으로 설명되어 있습니다. 아래 §2의
파이프라인/옵션/서버 튜닝은 **두 축 모두 동일하게 적용**됩니다(인코더/스트림 코드가 축 구분
없이 공유되는 구조라서, 마운트 경로만 다를 뿐 인코딩 설정은 완전히 동일함).

---

## 1. 스트림 사양

### 1.1 UGV축 (→ 원격통제기)

| 항목 | 값 |
|---|---|
| 프로토콜 | RTSP, **TCP interleaved만 지원**(UDP 미지원) |
| 비디오 코덱 | H.264, High Profile |
| B프레임 | 없음(`frameIntervalP=1`) — 재정렬(reorder) 불필요 |
| VUI 시그널링 | `bitstream_restriction_flag=1`, `max_num_reorder_frames=0`, `max_dec_frame_buffering=3` — 스트림 자체에 "재정렬 대기 불필요"가 명시되어 있음(아래 §3.2 참고) |
| 스트림 개수 | RCWS(조준경) 1개 + CCTV 4개, 마운트 경로: `/ugv/rcws`, `/ugv/front_cctv`, `/ugv/rear_cctv`, `/ugv/left_cctv`, `/ugv/right_cctv` |
| 해상도/fps | RCWS 1226×928(가변, 최대 60fps까지 설정 가능 — 실제 값은 SDP로 확인), CCTV 4개 240×135 @ 30fps |
| 세션 특성 | Shared media — 여러 클라이언트가 동시에 접속해도 서버 부하는 하나만 발생, `a=range:npt=now-`(라이브, **seek 불가**) |

### 1.2 자체방호축(이동형지휘소) (→ 상위체계)

| 항목 | 값 |
|---|---|
| 프로토콜 | RTSP, **TCP interleaved만 지원**(UDP 미지원) — UGV축과 동일 |
| 비디오 코덱 | H.264, High Profile — 인코더 설정 자체가 UGV축과 완전히 공유되는 코드라 VUI/B프레임 특성도 동일(§1.1 참고) |
| 스트림 개수 | CCTV 4개 + RCWS(조준경) 1개 + UAV 짐벌 1개(+환경 카메라 1개, 상위체계로는 안 보내도 되는 부가 스트림), 마운트 경로: `/selfdefense/front_cctv`, `/selfdefense/rear_cctv`, `/selfdefense/left_cctv`, `/selfdefense/right_cctv`, `/selfdefense/rcws`, `/selfdefense/uav_gimbal` (`/selfdefense/env_camera`는 부가) |
| 해상도/fps | CCTV 4개 240×136 @ 30fps, RCWS 1116×622 @ 30fps, UAV 짐벌 640×360 @ 30fps (전부 SDP로 재확인 가능, 가변) |
| 세션 특성 | UGV축과 동일(Shared media, 라이브·seek 불가) |
| 검증 상태 | 6개 마운트 전부 §2.1 파이프라인으로 접속 성공·`nvh264dec` 하드웨어 디코드까지 확인(2026-08-19). 정밀 지연 재측정(§2.3 방식)은 아직 안 했지만, 인코더/서버 코드가 UGV축과 완전히 동일해서 동등한 수준(§2.3의 68ms대)이 기대됨. |

---

## 2. 권장: GStreamer + NVDEC

### 2.1 테스트한 파이프라인

```
# UGV축 (원격통제기)
gst-launch-1.0 rtspsrc location=rtsp://<host>:8554/ugv/rcws latency=0 drop-on-latency=true protocols=tcp ! \
  rtph264depay ! h264parse ! nvh264dec max-display-delay=0 ! d3d11videosink sync=true qos=true

# 자체방호축(이동형지휘소) (상위체계) — 마운트 경로만 바뀜, 나머지 옵션은 동일
gst-launch-1.0 rtspsrc location=rtsp://<host>:8554/selfdefense/rcws latency=0 drop-on-latency=true protocols=tcp ! \
  rtph264depay ! h264parse ! nvh264dec max-display-delay=0 ! d3d11videosink sync=true qos=true
```

(`d3d11videosink`는 Windows+DirectX용 — 다른 플랫폼/렌더러를 쓴다면 그에 맞는 video sink로
교체하되, 아래 프로퍼티들의 의미는 동일하게 적용됩니다.)

### 2.2 각 옵션이 왜 중요한가

| 옵션 | 기본값 | 의미 |
|---|---|---|
| `rtspsrc`의 **`latency`** | **2000ms(!)** | 내부 지터버퍼(`rtpjitterbuffer`)가 목표로 하는 버퍼링 크기. 기본값이 2초라 모르고 쓰면 매우 느려짐 — 로컬/저지터 환경이면 `0`으로 낮춰도 안전 |
| `rtspsrc`의 `drop-on-latency` | false | 지터버퍼가 latency를 넘기면 오래된 패킷을 버림(밀린 채로 계속 쌓이는 것 방지) |
| `nvh264dec`의 **`max-display-delay`** | **-1(auto)** | "디코드와 화면 표시 사이 파이프라이닝"용 내부 버퍼 — `0`으로 명시하면 디코더가 프레임을 붙잡고 있지 않고 바로 내보냄 |
| video sink의 **`sync`** | true | **`true`로 두고 `qos=true`를 같이 켤 것.** 예전엔 "저지연이 중요하면 `false`"라고 안내했으나, 실측 결과 그게 지연 누적 버그의 원인이었음 — 아래 §2.6 참고 |
| video sink의 **`qos`** | false | 늦은 프레임을 버리고 그 사실을 상류(디코더)에 QoS 이벤트로 알려 스킵하게 함. 이게 GStreamer의 유일한 "따라잡기" 수단 |

이 네 가지 모두 **GStreamer 문서에 정식으로 노출된 프로퍼티**입니다 — 즉 "어디서 지연이
생기는지 몰라서 못 고치는" 상황 자체가 잘 안 생깁니다(§3에서 비교하는 다른 방식들과의
핵심적인 차이).

### 2.3 실측 결과

같은 환경(로컬호스트, RCWS 스트림)에서 스크린샷 기반 정밀 실측(양쪽 화면에 UTC 타임스탬프를
같이 띄워서 동시에 캡처, 시각 차이 = 종단 지연):

| 설정 | 종단 지연 |
|---|---|
| `rtspsrc latency=0`만 적용 | 149ms |
| + `sink sync=false` | ~100ms (**이 설정은 쓰지 말 것 — §2.6, 지연 누적 원인**) |
| + `max-display-delay=0`, `drop-on-latency=true`, 서버 쪽 추가 튜닝(§2.4) | **68ms (30~100ms 변동)** |

원래(별도 튜닝 없는 상태) 대비 **85~90% 개선**입니다.

### 2.4 서버 쪽에서 이미 반영된 저지연 설정 (참고용)

수신 측에서 뭘 더 하지 않아도, 서버가 보내는 스트림 자체가 이미 다음과 같이 저지연 지향으로
구성되어 있습니다(**UGV축/자체방호축 공통** — 인코더·스트림 코드가 축 구분 없이 공유됨):
- NVENC 인코더 버퍼 최소화(`nExtraOutputDelay=1`, 안전하게 확인된 최소값)
- NVENC 튜닝 프리셋 `ULTRA_LOW_LATENCY`
- VUI에 재정렬 불필요(`max_num_reorder_frames=0`) 명시 — **디코더가 이 스펙을 신뢰하고 불필요한
  보수적 버퍼링을 하지 않아야 함**(§3.2에서 이걸 안 지키는 디코더의 문제를 다룸)
- GStreamer 서버(gst-rtsp-server) 쪽 미디어 latency=0, rate-control 비활성화

### 2.5 하드웨어 요구사항

`nvh264dec`은 **NVIDIA GPU(NVDEC 지원)가 있어야** 동작합니다. 수신 측 하드웨어에 NVIDIA GPU가
없다면:
- Intel GPU: `qsvh264dec`(Quick Sync Video) 또는 `vah264dec`(VA-API)
- AMD GPU: `vah264dec`(VA-API, 드라이버 지원 시)
- 하드웨어 디코드가 아예 없는 환경: 소프트웨어 디코더(`avdec_h264`)로도 GStreamer의 지터버퍼
  제어(`rtspsrc latency`, `drop-on-latency`)만으로 cv2/libVLC보다는 나은 결과를 기대할 수
  있음(단, §3에서 다루는 것처럼 소프트웨어 디코더 자체의 내부 버퍼링 여부는 별도 확인 필요)

어떤 디코더를 쓰든 **`rtspsrc`의 `latency`/`drop-on-latency`와 sink의 `sync=true qos=true`는
동일하게 적용 가능**합니다 — 이게 가장 효과가 컸던 설정입니다.

### 2.6 ⚠ sink의 `sync=false`는 쓰지 말 것 (2026-08-21 실측으로 확인)

저지연을 노리고 sink에 `sync=false`를 주면 **처음엔 지연이 낮지만, 시간이 지나거나 창을 드래그해
클라이언트가 잠깐 멈추면 그 지연이 계속 누적되기만 하고 영원히 복구되지 않습니다**(실측에서
0.5초대까지 쌓였고, 프로세스를 재시작해야만 초기화됐습니다).

원인은 `sync=false`가 단순히 "클럭 동기화를 끄는" 게 아니라 실질적으로 **QoS를 통째로 끄는**
설정이기 때문입니다. 늦음(lateness)이라는 개념 자체가 없어지므로:
- sink가 늦은 프레임을 **버릴 수 없고**,
- 상류(디코더)로 QoS 이벤트도 안 나가서 디코더도 **프레임을 스킵할 수 없습니다**.

즉 파이프라인 전체에 "따라잡기" 수단이 하나도 없어져서, 한 번 밀리면 밀린 만큼 계속 과거
프레임을 보여주게 됩니다.

**해결: `sync=true qos=true`.** 서버 appsrc가 `is-live=true`이고 `rtspsrc latency=0` + 서버
rtsp-media latency도 0이라 파이프라인 지연 예산이 사실상 0이므로, `sync=true`로 바꿔도 지연이
늘지 않습니다. 오히려 늦은 프레임을 버리고 최신 프레임을 따라가므로 원래 목표에 더 부합합니다.

참고로 이 문제는 **수신 측 단일 스트림(bare `gst-launch`)에서도 그대로 재현**됩니다 — 애플리케이션
프레임워크나 다중 스트림 동시 재생과는 무관한, 파이프라인 구성 자체의 문제입니다.

---

## 3. (참고) 다른 방식 시도 기록 — 방법과 한계

아래는 GStreamer로 정착하기 전에 시도했던 다른 수신 방식들의 요약입니다. 결론적으로 둘 다
**"어디서 지연이 생기는지 통제 불가능한 내부 버퍼링"**이 발목을 잡았습니다.

### 3.1 OpenCV(cv2) — ffmpeg 백엔드

**방법**: `cv2.VideoCapture(url, cv2.CAP_FFMPEG)` + `OPENCV_FFMPEG_CAPTURE_OPTIONS` 환경변수로
`rtsp_transport=tcp`, `fflags=nobuffer`, `flags=low_delay`, `max_delay=0`,
`reorder_queue_size=0`, `buffer_size=0`, `threads=1` 등 알려진 저지연 옵션을 전부 시도.

**한계**:
- `cv2.VideoCapture()` 자체가 스트림을 여는 데 약 1~3초 걸림(내부 포맷 프로빙) — 그동안 서버가
  보낸 프레임들이 쌓였다가 연결 직후 몰아서 나옴.
- 위 옵션들을 다 적용해도 **정확히 11프레임(약 367ms) 고정 지연**이 없어지지 않음(원시 소켓
  기준 seq 단위로 정밀 측정, 편차 0 — 지터가 아니라 고정된 파이프라인 깊이임을 확인).
- 원인 일부 규명: 저희 SPS에 애초에 VUI `bitstream_restriction` 정보가 없어서(현재는 수정됨,
  §2.4) 디코더가 H.264 레벨 기준 보수적인 기본 버퍼링을 적용하고 있었음 — 수정 후 13→11프레임으로
  일부 개선됐지만 전부 설명되지는 않음.
- **cv2/ffmpeg에는 이 잔여 지연을 직접 제어할 수 있는 노출된 옵션이 없었음** — GStreamer의
  `max-display-delay` 같은 명시적 프로퍼티에 대응하는 게 없어서 더 파고들려면 ffmpeg 소스
  레벨 분석이 필요한 상황이었음.

### 3.2 libVLC (VLC 미디어 플레이어 라이브러리)

**방법**: `python-vlc`로 `network-caching=30`, `rtsp-tcp` 등 저지연 옵션 적용.

**한계**:
- libVLC의 RTSP 처리는 ffmpeg가 아니라 **live555**라는 별도 라이브러리를 씀 — 내부 동작이
  더 불투명함.
- 연결 초기에 **해상도를 잘못 추측(예: 634×480)했다가 실제 데이터를 보고 디코더를 통째로
  재시작**하는 현상을 확인 — 그 과정에서 200ms 이상의 지연이 발생하고, 한번 재시작 시점의
  지연이 "새 기준점"으로 고정되어 그 뒤로는 안 줄어듦.
- **사후에 강제로 따라잡기(예: 배속 재생, 최신 위치로 점프)도 불가능함**을 확인:
  - `set_rate()`(배속) 호출 시 이 종류의 라이브 스트림에서 네이티브 크래시(access violation) 발생.
  - `player.is_seekable()`이 `False` — 스트림이 `a=range:npt=now-`(라이브, 논시커블)로
    선언되어 있어서 seek 자체가 API 레벨에서 거부됨.
- 최종적으로 소프트웨어/하드웨어 디코드 전환, 스레드 수 조정 등 여러 시도를 했지만 **~400ms대
  지연이 거의 그대로** 유지됨.

### 3.3 왜 GStreamer가 더 나았는가 (핵심 차이)

cv2/libVLC 둘 다 "어딘가에 고정된 버퍼링이 있는 건 확실한데, 그걸 제어할 수 있는 옵션이
노출되어 있지 않다"는 공통된 벽에 부딪혔습니다. GStreamer는 `rtpjitterbuffer`의 `latency`,
디코더의 `max-display-delay`, sink의 `sync` 같은 **핵심 지연 요소들이 전부 정식 프로퍼티로
문서화되어 있어서**, 삽질 없이 바로 낮출 수 있었습니다. 이게 5배 이상의 지연 차이로 이어진
근본적인 이유입니다.

---

## 4. 요약 권장사항

1. 가능하면 **GStreamer + 하드웨어 디코드**로 수신 파이프라인을 구성할 것.
2. `rtspsrc`의 `latency`를 기본값(2000ms)에서 낮출 것 — 이게 가장 큰 영향을 줌.
3. 디코더의 프레임 지연 관련 프로퍼티(`max-display-delay` 등, 사용하는 디코더 문서 참고)를
   확인하고 최소화할 것.
4. Sink는 **`sync=true qos=true`**로 둘 것. 저지연을 노려 `sync=false`로 끄면 지연이 누적되기만
   하고 복구가 안 됩니다 — §2.6 참고(실측으로 확인된 함정).
5. 서버 SDP의 VUI에 `bitstream_restriction_flag=1`, `max_num_reorder_frames=0`이 명시되어
   있으니, 디코더가 이를 신뢰하고 불필요한 재정렬 버퍼링을 하지 않는지 확인할 것(일부 디코더는
   레벨 기준 보수적 기본값을 여전히 쓸 수 있음 — §3.1 참고).
6. cv2/libVLC 기반으로 구현해야 하는 불가피한 사정이 있다면, §3의 한계를 미리 인지하고
   수백 ms대 지연을 감안할 것 — 현재까지 조사로는 이 두 방식에서 그 이상 줄이는 명확한 방법을
   찾지 못했음.
