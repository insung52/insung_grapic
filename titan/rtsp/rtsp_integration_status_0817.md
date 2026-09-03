# RTSP 통합 현황 종합 (2026-08-17)

**[2026-08-19] 이 문서가 지적한 갭은 전부 해소됨 — 기록용으로만 남김.** 카메라 연결은
`rtsp_integration_complete_0817.md`(같은 날 후속 세션)로 끝났고, 이후 지연 최적화
(`rtsp/rtsp_latency_investigation.md`, 441ms→68ms)와 Linux 크로스플랫폼 프레임 폭락 수정
(`linux_wayland_x11_present_bottleneck.md`)까지 마무리됨. 현재 상태 요약은
`protocol_icd.md` §3.3/§4.1/§6 참고.

세 세션(Track1 인코더, UGV축, 자체방호축)이 서로 결과물을 공유 안 하고 각자 진행돼서 생긴
간극을 확인하기 위해 `rtsp_poc_findings.md`(Track1)/`ugv_rc_feature_gap_analysis.md`(UGV축)/
`selfdefense_rc_feature_gap_analysis.md`(자체방호축) 세 문서를 대조.

## 결론 (TL;DR)

**"영상이 잘 오는지 테스트"를 지금 바로 할 수 없는 상태다 — 아직 실제 카메라가 RTSP
파이프라인에 하나도 안 붙어 있음.** 세 세션 다 자기 몫은 끝냈다고 보고했지만, "실제 카메라를
인코더에 연결하는" 접합부(integration)는 셋 다 명시적으로 남의 몫이라고 적어두고 각자
손대지 않은 상태 — 이게 사용자가 느낀 "소통 안 됨"의 정체.

| 축 | 프로토콜/조작 | RTSP 카메라 소스 식별 | RTSP 실제 연결(`URtspStreamComponent` 부착) |
|---|---|---|---|
| Track1(인코더) | 해당없음 | 해당없음(회전 큐브로만 검증) | 파이프라인 자체는 검증 완료, 실 카메라엔 미연결 |
| UGV축 | ✅ 거의 완료+실측 | ❌ 미착수 | ❌ 미착수 |
| 자체방호축 | ✅ 완료+대부분 실측 | ✅ 완료(7종) | ❌ 미착수("남은 유일한 큰 작업"이라 자기 문서에 명시) |

---

## 1. Track1 — RtspEncoder 플러그인 (NVENC+GStreamer)

위치: `titan_example\Plugins\RtspEncoder\`

- **검증 완료(2026-08-07)**: 단일 스트림 + 7스트림 동시 송출, VLC 연결/재연결/재생 전부
  정상(70+fps, 저부하). §1.9~1.22에 걸친 D3D12 RHI 크래시/재연결 레이스/PTS 문제 전부
  해결됨.
- **크로스플랫폼(Linux) 준비**: Phase 0(WSL2 사전검증)~Phase 2(Vulkan/CUDA 렌더-인코더
  재구현)까지 작성 및 **컴파일 성공** 확인(Windows/Linux 둘 다), 단 **런타임 동작은 실제
  하드웨어에서 전혀 검증 안 됨**(원격 우분투 박스 대기, Phase 4).
- **중요 — 이 세션이 스스로 명시한 스탠딩 룰**: "이 세션은 `titan_example`을 빌드하지
  않는다(사용자가 직접 빌드)" — 즉 **실제 프로젝트에 이 플러그인을 통합하는 작업은 애초에
  이 세션의 범위가 아니었음**, 의도적으로 다음 단계로 남겨둔 것(§8/§9 "실제 UGV/자체방호축
  카메라(QuadCamModule의 SceneCaptureComponent2D들, RCWS 뷰어 등)에
  `URtspStreamComponent`를 붙이는 건 이 PoC가 실제로 동작 확인된 다음 단계").
- 지금까지 붙어있는 액터는 `RtspPocTestActor`(회전 큐브 + 고정 SceneCapture) 하나뿐 — 실제
  게임 카메라는 하나도 안 씀.
- 남겨둔 일(자기 문서 §8): GStreamer DLL 배포 패키징, RTSP URL 스킴/포트 확정(잠정
  `/poc/streamN`), 실제 카메라 연결. **셋 다 아직 아무도 안 함.**

## 2. UGV축 — RTSP 관련 진행 없음

`ugv_rc_feature_gap_analysis.md` 마지막 줄에 명시: *"RTSP 영상 송출(별도 트랙에서 PoC
진행 중, 이 코드베이스엔 아직 한 줄도 없음 — `titan_examplePlayerController.h`에 '아직
미구현'이라고 명시돼 있음)"*.

- 프로토콜(RC_* 커맨드) 쪽은 거의 다 구현+실측 완료(§ 별도 대조표 참고) — RTSP만 완전히
  손 안 댐.
- **자체방호축이 한 "카메라 소스 식별" 작업의 UGV판이 아직 없음** — 필요한 5개 스트림
  (전면/후면/좌측/우측CCTV/RCWS뷰어)이 실제로 UGV 쪽 어느 컴포넌트에서 나오는지
  (`BP_UGV_Vehicle`에 QuadCam류 컴포넌트가 붙어있는지, RCWS 뷰어 카메라를 어떻게 얻는지 등)
  이 세션 문서 어디에도 조사된 흔적이 없음.

## 3. 자체방호축 — 소스는 찾았지만 연결은 안 함

`selfdefense_rc_feature_gap_analysis.md` §1-2, §2:

- RTSP 7종(환경카메라/전면/후면/좌측/우측CCTV/RCWS뷰어/UAV드론뷰)의 **실제 소스 컴포넌트
  식별은 완료**: 환경카메라=`BattlefieldCapture`, CCTV×4=`QuadCam`, RCWS뷰어=
  `GetSightCamera()`, UAV드론뷰=`GetGimbalCamera()`.
- 인코드·송출 파이프라인은 "활성화 확인 + 회전 큐브 테스트로 검증 완료(트랙1)"라고
  **정확히 인지하고 있음** — 즉 Track1의 존재/상태는 알고 있었음.
- 하지만 **"실제 카메라에 `URtspStreamComponent` 연결은 미착수"**라고 §1-2에 명시, §2
  완료기준 대조표에서도 RTSP를 "❌ 미착수, 자체방호축에 남은 유일한 큰 작업"으로 스스로
  분류.
- 조이스틱/RCWS/UAV 짐벌 조작 쪽은 거의 다 실측까지 끝남(2026-08-17 기준 EO/IR, 안전스위치,
  발사, 총열회전 시청각 등) — RTSP만 빠짐.

---

## 4. 그래서 다음 세션이 해야 할 일 — "테스트"가 아니라 먼저 "연결"

셋 다 자기 몫은 끝냈다고 정확히 보고했고 틀린 것도 없음 — 다만 "실제 카메라를 Track1
플러그인에 붙이는" 접합 작업 자체를 아무도 자기 스코프로 잡지 않았을 뿐. 새 세션에게
"영상이 잘 오는지 테스트해줘"라고만 시키면 카메라가 하나도 안 붙어 있어서 테스트할 대상이
없다 — 스코프에 아래 3개를 먼저 넣어야 함:

1. **UGV축 카메라 소스 식별** — 자체방호축이 이미 한 조사(§3)와 같은 성격의 조사를
   UGV축(`BP_UGV_Vehicle`/`BP_TitanTruck`은 아님, UGV 자체)에 대해 먼저 해야 함(5개 스트림).
2. **양쪽 다 `URtspStreamComponent` 연결** — Track1 플러그인의 컴포넌트를 식별된 각
   SceneCapture류 컴포넌트에 붙이는 작업(UGV 5개 + 자체방호 7개, 총 12개 mount). Track1
   문서(`rtsp_poc_findings.md` §1~§4, 특히 §4 D3D12 zero-copy 흐름과 `RtspStreamComponent`
   공개 API)를 참고해서 "SceneCapture 하나당 컴포넌트 하나 붙이기" 패턴 그대로 재사용.
3. **RTSP URL 스킴 확정** — `protocol_icd.md` §3.3/§4.1의 잠정안(`rtsp://<host>:8554/
   <axis>/<stream>`)을 실제로 반영해서 mount 이름 확정, 문서에도 반영.

**이 세 가지가 끝난 뒤에야** `rc_mockup_tools/rtsp_viewer_test/`(Track3 완료분, Python/OpenCV
뷰어)로 실제 영상 수신을 검증하는 게 의미가 있음.

---

## 5. 관련 문서

- `rtsp_poc_findings.md` — Track1 전체 기록(§4 D3D12 zero-copy 흐름, §8 프로덕션 패키징
  남은 일, §10 크로스플랫폼)
- `ugv_rc_feature_gap_analysis.md` §4 종합 우선순위(RTSP 항목)
- `selfdefense_rc_feature_gap_analysis.md` §1-2, §2, §4(다음 액션 2번)
- `protocol_icd.md` §3.3(UGV축 RTSP 5스트림)/§4.1(자체방호축 RTSP 7스트림)
