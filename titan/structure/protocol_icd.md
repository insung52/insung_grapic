# 프로토콜 ICD (Interface Control Document) — 상세 명세

- claude artifacts 시각화 문서

- https://claude.ai/code/artifact/6089715a-aa43-4dbb-9113-207c796d665d?via=auto_preview

---

`architecture_decisions.md`의 Layer A/B를 필드 단위로 formalize한 문서. **UGV 통제기SW가
외주/타사 인계 가능성이 있어서, 구현체(언리얼 여부)와 무관하게 읽을 수 있도록 작성.**
남은 미확정 항목은 §6.

---

## 0. 전송 계층 원칙

**v1: RTSP(영상) 제외 전부 NATS로 통일.** UDP는 도입하지 않음 — 조이스틱/텔레메트리처럼
연속·고빈도인 메시지도 일단 NATS로 보내고, PoC에서 TCP head-of-line blocking으로 인한
체감 끊김이 실측되면 그때 그 메시지들만 UDP로 분리(§7 참고). 메시지 스키마/누가 누구랑
통신하는지는 안 바뀌니 나중에 쪼개는 비용이 작음 — 지금은 타사(UGV 통제기SW 인계 가능성)
온보딩 부담을 줄이는 쪽을 우선.

| 채널 | 전송 | 특성 | 대상 메시지 |
|---|---|---|---|
| NATS-console | NATS(TCP), subject `console.<axis>.cmd` / `console.<axis>.evt` / `console.<axis>.telemetry` | 신뢰성 필요, JetStream 권장 | Layer B 전체(연결/BIT, 조이스틱 입력, 텔레메트리, 이벤트) |
| NATS-hq | NATS(TCP), subject `hq.cmd.<axis>` / `hq.rpt.<axis>` | 신뢰성 필요, JetStream | Layer A(`HQ_*`, `RPT_*`) 전체 |
| RTSP | RTSP | 표준 비디오 스트리밍 | 영상 5~7종 |

`<axis>` = `ugv` 또는 `selfdefense`. (구 UDP 8000/8001 포트 표기는 폐기 — §7 참고)

## 1. 공통 봉투(Envelope) 포맷

모든 메시지(NATS, §7의 향후 UDP 분리 후보 포함)는 아래 봉투로 감싼다:

```json
{
  "cmd": "<MessageName>",
  "seq": 0,          // uint32, 송신측 단조증가 — 수신측이 유실/재정렬 감지용
  "ts": 0,            // uint64, 세션 시작 후 경과 ms
  "payload": { }
}
```

- 수신측이 `seq` 중복이면 무시(NATS at-least-once 재전송 대비 dedup), 역행하면(더 옛날 seq)
  폐기 — 연속형(조이스틱/텔레메트리) 메시지는 "최신값만 반영"이 곧 이 규칙의 자연스러운 결과.
- (§7의 UDP 분리 후보로 전환 시: `seq` 재정렬만 감지, 재전송 없음 — 지금은 해당 없음)

## 2. 공통 타입 · 단위 표준

**좌표는 위경도(WGS84)로 확정** — 에뮬레이터가 "현실을 대체"하는 개념이라, 상위체계/타사
시스템과 주고받는 좌표는 실제로 존재할 GPS 좌표와 동일한 체계여야 함. 언리얼 월드좌표(cm,
레벨 원점 기준)는 에뮬레이터 내부 구현 디테일로만 남고, **와이어 프로토콜엔 절대 안 나옴**.
변환은 이미 있는 `GeoCoordinateUtils.h`(씬 스케일 ↔ 위경도 변환, 나침반/방위각 보정 포함,
`real2world_geo_calibration.md` 참고)를 재사용 — 원칙 4(기존 함수에 올라타기) 그대로 적용.

```
Coord      { "lat": double, "lon": double, "alt": float }
             // lat/lon: WGS84 십진수 도(°), double(float64) — 소수점 7자리는 있어야 cm급 정밀도
             // alt: 미터, AGL(지면 기준 고도) — UAV 고도 등에 재사용, 지상 유닛은 0 고정
BBox       { "x": float, "y": float, "w": float, "h": float }  // 화면 UV 0~1 (카메라 뷰 로컬 개념이라 위경도 아님)
Detection  { "id": string, "type": "Person"|"Vehicle", "bbox": BBox, "coord": Coord|null, "confidence": float }
             // coord: 지도 마킹용 실좌표 추정치(가능하면), 계산 안 되면 null
```

**단위 표준**: 거리/반경/고도 = 미터(m), 속도 = m/s, 각도(pan/tilt/gimbal/방위각) = 도(°),
배터리 = 0~1 소수, 시간 = ms. 필드별 예외는 표에 개별 표기.

---

## 3. Layer B — UGV축

### 3.1 연결/BIT (`console.ugv.cmd`)

| 메시지 | 방향 | payload |
|---|---|---|
| `RC_Connetion` | SW→에뮬 | `{}` |
| `RC_Connetion_ADU` | SW→에뮬 | `{}` |
| `UGV_Response_Connection` | 에뮬→SW | `{ "source": "UGV"\|"ADU" }` |
| `RC_Request_BIT` | SW→에뮬 | `{}` |
| `RC_Request_BIT_ADU` | SW→에뮬 | `{}` |
| `UGV_Response_BIT` | 에뮬→SW | `{ "source": "UGV"\|"ADU", "ok": bool, "detail": string }` |

### 3.2 조이스틱 입력 / 텔레메트리 (`console.ugv.cmd` / `console.ugv.telemetry`)

| 메시지 | 방향 | payload | 매핑 |
|---|---|---|---|
| `RC_ManualDrive` | SW→에뮬 | `{ "forward": float[-1,1], "turn": float[-1,1] }` | `SetManualControl()`, Manual 모드 아니면 무시 |
| `RC_Movement` | SW→에뮬 | `{ "pan": float, "tilt": float }` | RCWS 조준, Remote 모드에서만 반영 |
| `UGV_Period_BasicInfo` | 에뮬→SW | `{ "pos": Coord, "speed": float(m/s), "battery": float(0~1), "driveMode": "Idle"\|"Manual"\|"Auto", "odometer": float(m) }` | 10Hz |
| `UGV_Period_ObjectDetectionResult` | 에뮬→SW | `{ "targets": Detection[] }` | 10Hz |
| `UGV_Period_NavigationInformation` | 에뮬→SW | `{ "waypoint": Coord, "distanceRemaining": float }` | 10Hz |
| `UGV_Period_RCWSStatus` | 에뮬→SW | `{ "mode": "Remote"\|"AutoSurveillance"\|"AutoAim"\|"AutoFire", "aimPan": float, "aimTilt": float, "loaded": bool, "fireReady": bool, "zoom": int(1~16) }` | 10Hz |

### 3.3 단발성 명령/이벤트 (`console.ugv.cmd` / `console.ugv.evt`)

| 메시지 | 방향 | payload | 매핑 |
|---|---|---|---|
| `RC_SetUGVMode` | SW→에뮬 | `{ "mode": "Idle"\|"Manual"\|"Auto" }` | `SetUGVMode` |
| `RC_MissionWaypoint` | SW→에뮬 | `{ "target": Coord, "radius": float(m) }` | Auto 모드 목적지 |
| `RC_SetRCWSMode` | SW→에뮬 | `{ "mode": "Remote"\|"AutoSurveillance"\|"AutoAim"\|"AutoFire" }` | `SetRCWSMode` |
| `RC_ManualFire` | SW→에뮬 | `{}` | `ManualFireAction`, `bLoaded`/`bFireReady`/`bEngagementAuthorized` 게이트 |
| `RC_ZoomIn` / `RC_ZoomOut` | SW→에뮬 | `{}` | `AddManualZoomStep` |
| `RC_SetEngagementAuthorized` | SW→에뮬 | `{ "authorized": bool }` | `bEngagementAuthorized` (§Layer A 연동, 기본 off) |
| `TRK_Event_MissionStarted` | 에뮬→SW | `{ "missionId": string }` | |
| `TRK_Event_ObjectiveReached` | 에뮬→SW | `{ "radius": float }` | |
| `TRK_Event_ContactDetected` | 에뮬→SW | `{ "targets": Detection[] }` | |
| `TRK_Event_EngagementInitiated` | 에뮬→SW | `{}` | |
| `TRK_Event_EngagementResult` | 에뮬→SW | `{ "kia": int, "fleeing": int }` | |
| `TRK_Event_MissionComplete` | 에뮬→SW | `{ "missionId": string, "result": string }` | |

### 3.4 RTSP — UGV축 (5)

`전면CCTV`, `후면CCTV`, `좌측CCTV`, `우측CCTV`, `RCWS뷰어` — URL 규칙은 §6 참고(잠정
`rtsp://ugv-console:8554/ugv/<stream>`).

---

## 4. Layer B — 자체방호축

### 4.1 연결/BIT (`console.selfdefense.cmd`) — 3.1과 동일 패턴, `_ADU` → `_UAV`, 응답 프리픽스 `UGV_`→`TRK_`

### 4.2 조이스틱 입력 / 텔레메트리 (`console.selfdefense.cmd` / `console.selfdefense.telemetry`)

| 메시지 | 방향 | payload | 매핑 |
|---|---|---|---|
| `RC_UAVGimbal` | SW→에뮬 | `{ "pan": float, "tilt": float, "zoom": float }` | UAV 짐벌만, 비행 자체는 항상 Auto |
| `RC_Movement` | SW→에뮬 | `{ "pan": float, "tilt": float }` | 트럭 RCWS 조준 (3.2와 동일 컴포넌트) |
| `TRK_Period_BasicInfo` | 에뮬→SW | `{ "status": "OK"\|"Fault" }` | 트럭은 이동 없어 최소 필드만 |
| `TRK_Period_UAVInfo` | 에뮬→SW | `{ "pos": Coord, "speed": float(m/s), "battery": float(0~1), "gimbalPan": float(°), "gimbalTilt": float(°) }` | 10Hz — 고도는 `pos.alt`로 통합, 별도 필드 없음 |
| `TRK_Period_ObjectDetectionResult` | 에뮬→SW | `{ "source": "UAV"\|"RCWS", "targets": Detection[] }` | 10Hz |
| `TRK_Period_RCWSStatus` | 에뮬→SW | 3.2의 `UGV_Period_RCWSStatus`와 동일 스키마 | 10Hz |

### 4.3 단발성 명령/이벤트 (`console.selfdefense.cmd` / `console.selfdefense.evt`)

| 메시지 | 방향 | payload | 매핑 |
|---|---|---|---|
| `RC_MissionUAVRecon` | SW→에뮬 | `{ "target": Coord }` | UAV 자동이륙+비행 트리거 |
| `RC_SetRCWSMode` / `RC_ManualFire` / `RC_ZoomIn` / `RC_ZoomOut` / `RC_SetEngagementAuthorized` | SW→에뮬 | 3.3과 동일 스키마 | 트럭 RCWS |
| `TRK_Event_MissionComplete` | 에뮬→SW | `{ "missionId": string, "result": string }` | UAV 임무완료 / 최종섬멸 공용 |
| `TRK_Event_TargetsIdentified` | 에뮬→SW | `{ "targets": Detection[] }` | |
| `TRK_Event_EngagementInitiated` / `TRK_Event_EngagementResult` | 에뮬→SW | 3.3과 동일 | 트럭 RCWS |

### 4.4 RTSP — 자체방호축 (7)

`환경카메라`, `전면CCTV`, `후면CCTV`, `좌측CCTV`, `우측CCTV`, `RCWS뷰어`, `UAV드론뷰` — URL
규칙은 §6 참고(잠정 `rtsp://selfdefense-console:8554/selfdefense/<stream>`).

---

## 5. Layer A — 상위체계 ↔ 통제기SW

NATS subject: `hq.cmd.selfdefense`, `hq.cmd.ugv`(하달) / `hq.rpt.selfdefense`, `hq.rpt.ugv`(보고).
봉투/payload 포맷은 §1~2와 동일.

| 메시지 | 방향 | payload |
|---|---|---|
| `HQ_EnemyContactReport` | 상위체계→자체방호SW | `{ "contactId": string, "coord": Coord }` |
| `RPT_TargetsIdentified` | 자체방호SW→상위체계 | `{ "targets": Detection[] }` |
| `HQ_MissionMoveToEngage` | 상위체계→UGV SW | `{ "target": Coord, "radius": float(m) }` |
| `RPT_ObjectiveReached` | UGV SW→상위체계 | `{ "radius": float }` (FYI) |
| `RPT_ContactDetected` | UGV SW→상위체계 | `{ "targets": Detection[] }` |
| `HQ_EngagementAuthorization` | 상위체계→UGV SW | `{ "approved": bool, "contactId": string }` |
| `RPT_EngagementInitiated` | UGV SW→상위체계 | `{}` (FYI) |
| `RPT_EngagementResult` | UGV SW→상위체계 | `{ "kia": int, "fleeing": int }` |
| `HQ_MissionEngageFleeing` | 상위체계→자체방호SW | `{ "coord": Coord }` |
| `RPT_ScenarioComplete` | 자체방호SW→상위체계 | `{ "result": string }` |

---

## 6. 결정된 것 / 남은 미확정

**결정됨**:
- **좌표계**: 위경도(WGS84) — §2에서 확정, `GeoCoordinateUtils.h` 변환 유틸 재사용.
- **`bEngagementAuthorized`는 축마다 별도 승인** — 시나리오상 UGV축(#4-6)과 자체방호축(#4-8)이
  서로 다른 시점에 서로 다른 대상(1차 적군 vs 도주한 잔적)을 교전하므로 동시에 하나로 묶일
  이유가 없음. `RC_SetEngagementAuthorized`가 축별 NATS subject(`console.<axis>.cmd`)로 개별
  전달되는 걸로 확정.
- **JSON 페이로드** — 가독성/이식성(타사 인계 가능성) 우선. 대역폭이 실측에서 문제되면 그때
  바이너리 재검토(원칙 5).

**아직 미확정 (구현 착수 전 확인 필요)**:
- **RTSP URL 규칙/포트 번호** — §3.4/4.4. 인코딩 방식(UE NVENC + `gst-rtsp-server`)은 확정,
  구체적 URL 스킴은 PoC 이후 확정. 잠정 제안: `rtsp://<console-host>:8554/<axis>/<stream>`
  (8554 = RTSP 비특권 관용 포트, 554는 피함), 예:
  `rtsp://ugv-console:8554/ugv/rcws`, `rtsp://selfdefense-console:8554/selfdefense/uav`.

## 7. RTSP 구현 방식 + 향후 UDP 분리 후보 (참고용, 결정 아님)

- **RTSP 송출**: UE에서 NVENC로 직접 인코딩(zero-copy, CUDA-D3D11 interop) → 인코딩된 H.264
  비트스트림만 GStreamer `gst-rtsp-server`의 `appsrc`에 공급 → RTSP 세션 협상/SDP/RTP 패킷화는
  GStreamer가 담당. live555는 대안(예제 프로젝트 유지보수 불확실), 완전 자체구현은 비추천
  (RFC 6184 등 표준 준수 부담). GStreamer/gst-rtsp-server는 LGPL — 내부 데모 용도라 실무상
  문제 소지는 낮으나 최종 납품 형태에 따라 법무 확인 권장. 일정 리스크: PoC 1~2일, 프로덕션
  안정화까지 1~2주로 예상.
- **UDP 분리 후보**: §0에서 결정한 대로 v1은 전부 NATS. 만약 PoC에서 `RC_ManualDrive`/
  `RC_Movement`/`RC_UAVGimbal`(연속 조이스틱 입력)이나 `*_Period_*`(텔레메트리)에서 TCP
  head-of-line blocking으로 인한 체감 끊김이 확인되면, 그 메시지들만 UDP(예: port 8000,
  "최신값이 이전값을 덮어씀" 시맨틱)로 분리 — 메시지 스키마/통신 상대는 안 바뀌므로 나중에
  쪼개는 비용은 작음.
