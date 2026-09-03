# UGV 커브 선행 감속 (제동 곡선) — 2026-08-22

> **⚠️ 속도 거버너 부분은 2026-08-31에 교체됨** — 여기 나오는
> `Throttle = 조향컷 × SpeedScale` 배율형 P 제어는 목표 속도를 유지할 수 없다는 구조적 결함이
> 있어서 PI 절대출력으로 바뀌었고, 조향컷도 스로틀이 아니라 목표 속도에 곱하는 쪽으로 옮겨졌다.
> `2026-08-31_ugv-speed-pi-controller.md` 참고. 커브 목표 속도 산출(제동 곡선) 자체는 유효하되,
> 각도→속도 매핑은 2026-08-26에 곡률 반경 기반으로 교체됨
> (`2026-08-26_ugv_obstacle_avoidance.md` 2절).

`AUGVAIController`의 Chaos 추종 주행에 **"꺾이기 전에 미리 감속"** 을 추가한 기록.
`ugv_driving_dev_guide.md` 9절(Pure Pursuit Lookahead)·12절(오프로드 속도 처리)의 후속이고,
계기가 된 레벨 상황은 `2026-08-27_new_kadex_0811_navmesh_autonomous_driving.md` 참고.

---

## 1. 배경

`New_kadex_0811`의 흙길 위에 **나무 장애물을 의도적으로 배치**하기 시작하면서, UGV가 그것들을
회피하는 조향을 **원래 속도 그대로 들어가서 부딪히는** 문제가 생겼다.

### 1.1 기존에 있던 "감속 비슷한 것"

`UpdateChaosPursuit`에 이미 이런 항이 있었다 (`UUGVMovementComponent::RequestDirectMove`에서 포팅):

```cpp
const float Steer    = FMath::Clamp(AngleError / SteerFullLockAngleDeg, -1.f, 1.f);
float       Throttle = FMath::Clamp(1.f - AbsAngleError / ThrottleCutoffAngleDeg, 0.f, 1.f);
```

`AngleError`는 **현재 차체 방향과 lookahead 지점 방향의 각도차**다. 90°(`ThrottleCutoffAngleDeg`)에서
스로틀이 0이 된다. 하지만 세 가지 한계가 있었다:

1. **사후 반응** — `AngleError`는 차체가 이미 틀어진 뒤에야 커진다. 커브 진입 *전에* 줄이는 게 아니다.
2. **감속이 아니라 타력 주행** — 스로틀만 0이 되고 브레이크는 안 밟는다. 질량 3톤이라 실제로는
   거의 안 줄어든다.
3. **실제 브레이크를 밟는 유일한 경로가 커브와 무관** — `bEscortSpeedLimitActive`(아군 동반 기동
   구간 20km/h 제한)일 때뿐이고, 그건 `UScenarioStateSubsystem`이 시나리오 4→7단계에서만 켠다.

### 1.2 검토한 우회책

| 방법 | 판단 |
|---|---|
| `LookaheadDistance` 늘리기 | 커브를 완만하게 돌게는 하지만, 장애물이 여러 개면 부족. 너무 늘리면 커브를 가로질러 잘라먹음 |
| `ThrottleCutoffAngleDeg` 낮추기(90→40) | 재빌드 없이 즉시 가능한 완화책. 여전히 사후 반응 |
| Tank 에이전트 반경 늘리기 | 나무 사이 좁은 틈을 아예 경로로 안 잡아서 근본적이지만, 흙길 자체가 좁아지는 부작용 |
| 최고 속도 제한 | 전 구간이 느려짐 |

근본 해결은 "앞을 보고 미리 줄이는 것"이라 판단하고 구현했다.

---

## 2. ⚠ 먼저 확인해야 할 것 — `RoadCenteringPullStrength`가 회피를 되돌린다

**경로 위에 장애물을 두는 순간, 도로 중심선 당김과 장애물 회피는 서로 상충한다.**

`RefinePathTowardRoadCenterline`은 경로점을 중심선 스플라인 쪽으로 `RoadCenteringPullStrength`
(기본 **0.6**)만큼 당긴다. Recast가 나무를 피해 옆으로 낸 경로점이 중심선에서
`RoadCenteringMaxLateralDistance`(기본 300cm) 이내면, **그 회피분을 다시 나무 쪽으로 되돌린다.**

감속 로직을 손대기 전에 이것부터 확인할 것 — `BP_UGVAIController`에서 `bEnableRoadCentering`을
끄거나 `RoadCenteringPullStrength`를 0.2 정도로 낮추면 된다(재빌드 불필요). 장애물이 경로에 있는
이상 중심선 당김은 약하게 가는 게 맞다.

---

## 3. 1차 구현과 그 실패 (기록용)

처음에는 이렇게 만들었다:

```
프리뷰 거리 = max(하한, 현재속도 × CornerPreviewSeconds)
   ↓ 그 구간의 진행방향 변화량 누적(도)
   ↓ 0° → 45km/h, 60° 이상 → 10km/h (선형 보간)
   ↓ 속도 거버너 램프
```

**문제**: 프리뷰 창이 사실상 "앞 N m 안에 커브가 있냐/없냐"의 이진 판정이었다. Recast 경로처럼
꺾임이 한 정점에 몰려 있으면, 그 정점이 창에 들어오는 순간 누적 각도가 0 → 90°로 튀고 목표 속도가
45 → 10으로 **계단식으로 떨어진다.** 결과는 **정속으로 달리다 갑자기 풀 브레이크.**

사용자 지적: *"코너가 점점 가까워지는 상황에서 계속 50km로 달리다가, 코너 감지하는 순간 풀
브레이크가 되는 상황인가? 거리가 충분히 멀면 천천히 감속시키는 로직 같은 건 없나?"* — 정확한 지적이라
2차로 갈아엎었다. **거리를 판정 조건으로만 쓰고 출력에는 안 쓴 게 근본 원인이었다.**

---

## 4. 최종 설계 — 제동 곡선

거리를 출력에 직접 넣는다. 앞쪽 커브 각각에 대해:

```
지금 허용속도 = √( 그 커브 통과속도² + 2 × 감속도 × 그 커브까지 거리 )
```

(등가속 운동 `v² = v₀² + 2ad`를 역으로 푼 것. 열차 제동 곡선과 같은 방식.)

`CornerScanDistance` 안의 **모든 커브**에 대해 계산하고 **최솟값**을 목표 속도로 삼는다. 거리가 식에
직접 들어가므로 목표 속도가 매 틱 연속적으로 내려온다 — 계단이 없다. 프리뷰 시간이라는 편법도
필요 없어져서 관련 프로퍼티 2개(`CornerPreviewSeconds`, `CornerPreviewMinDistance`)는 삭제했다.

### 4.1 커브 묶기 (슬라이딩 윈도우)

경로점이 촘촘하면(중심 보정이 켜져 있으면 `RoadCenteringResampleInterval` = 300cm로 리샘플됨)
완만한 커브 하나가 작은 꺾임 여러 개로 쪼개진다. 그래서 `CornerWindowDistance`(기본 10m) 길이의
창을 앞으로 밀면서 **창 안의 꺾임각을 합산**해 하나의 커브로 본다. 이래야 "완만하고 긴 커브"와
"짧고 급한 꺾임"이 같은 기준으로 비교된다. 두 포인터 슬라이딩 윈도우라 경로점 수에 선형.

각도는 **절대값 누적**이라 좌우로 번갈아 꺾이는 S자 구간도 합산된다 — 그런 구간이야말로 줄여야
하므로 의도된 동작이다.

### 4.2 거버너 공유

목표 속도가 정해지면 **`EscortMaxSpeedKmh` 거버너와 똑같은 연속 램프**를 탄다. 그쪽은 2026-08-04에
*"엑셀이 계속 풀로 밟혀있다가 브레이크가 갑자기 턱 걸리듯 세게 걸림"* 리포트를 고치면서 이미
다듬어둔 것이라 그대로 재사용했다. 두 거버너가 동시에 활성이면 **목표 속도가 낮은 쪽**을 따르고,
각자 자기 램프 폭(`CornerSpeedRampBandKmh` / `EscortSpeedRampBandKmh`)을 쓴다.

램프의 의미 (목표 `T`, 폭 `B`):

| 현재 속도 | SpeedScale | 동작 |
|---|---|---|
| `T-B` 이하 | +1 | 조향 스로틀 그대로 |
| `T-B` ~ `T` | +1 → 0 | 스로틀 선형 감소 |
| `T` | 0 | 타력 주행 |
| `T` ~ `T+B` | 0 → -1 | 브레이크 0 → 1 |
| `T+B` 이상 | -1 | 풀 브레이크 |

적용은 `Throttle = (SpeedScale >= 0) ? Throttle * SpeedScale : SpeedScale`. 음수가 그대로 스로틀
자리에 들어가 브레이크가 되는 건 `DispatchSetManualControl`의 음수 처리 규약 덕분이다
(달리는 중 음수는 브레이크로만 작동하고, 실제로 정지한 뒤에야 후진이 된다).

---

## 5. 코드 구조

`Source/titan_example/Vehicles/UGVAIController.{h,cpp}`

```
UpdateChaosPursuit()
  ├─ Steer / Throttle  (기존 AngleError 기반 — 그대로 유지)
  └─ 속도 거버너
       ├─ ComputeCornerTargetSpeedKmh(CurrentLocation, DistanceScale)   ← 신규
       │    1) 경로에서 현재 위치와 가장 가까운 구간 + 그 위의 투영점 찾기
       │    2) 앞쪽 정점들의 (거리, 꺾임각) 수집 (CornerScanDistance까지)
       │    3) 슬라이딩 윈도우로 커브 묶고 제동 곡선 역산 → 최솟값
       ├─ EscortMaxSpeedKmh 와 비교해 더 낮은 쪽 채택
       └─ ComputeSpeedGovernorScale(현재속도, 목표속도, 램프폭)          ← 신규(기존 로직 추출)
```

**단위 주의**: 제동 곡선은 **실제 세계 단위(m, m/s, m/s²)** 로 푼다. 씬 거리에
`GeoCoordinateUtils::GetDistanceScaleFactor()`(씬 1cm당 실제 ~1.2135cm)를 곱해서 변환한다.
안 그러면 `CornerDecelMetersPerSecSq`가 물리적으로 말이 안 되는 값이 된다. 이 프로젝트의 다른 모든
km/h 표시도 같은 보정을 쓴다 — 2026-08-04에 아군 동반 거버너만 이 보정을 빠뜨려서
`EscortMaxSpeedKmh=20`이 실제로는 24.3km/h였던 버그가 있었다.

**두 감속 축은 분리되어 있다**: `ThrottleCutoffAngleDeg`는 "지금 차체가 틀어진 만큼",
커브 감속은 "앞으로 틀어질 만큼"을 담당한다. 커브 계산에 차체의 현재 방향 오차를 넣으면 이중으로
깎이므로 일부러 뺐다.

---

## 6. 파라미터 (`BP_UGVAIController` → `UGV AI|Chaos Pursuit`)

| 프로퍼티 | 기본값 | 의미 |
|---|---|---|
| `bEnableCornerBraking` | true | 전체 on/off |
| `CornerScanDistance` | 8000cm (80m) | 얼마나 먼 커브까지 고려할지. 넉넉해도 무해 — 먼 커브는 허용 속도가 높게 나와 저절로 무시됨 |
| `CornerWindowDistance` | 1000cm (10m) | 하나의 커브로 묶어 각도를 합산할 구간 |
| **`CornerDecelMetersPerSecSq`** | **2.0** | **제동 곡선 감속도 — 감속 성격을 결정하는 핵심 노브** |
| `CornerFullSlowAngleDeg` | 60° | 창 누적 각도가 이 값 이상이면 그 커브 통과 속도 = `CornerMinSpeedKmh` |
| `CornerStraightSpeedKmh` | 45 | 직선 목표 속도 = **사실상 자율주행 최고속도 상한** |
| `CornerMinSpeedKmh` | 10 | 급커브 통과 속도 |
| `CornerSpeedRampBandKmh` | 6 | 스로틀↔브레이크 전환 폭 (4절 표) |

### 감속도 2m/s², 커브 통과속도 10km/h일 때 허용 속도 곡선

| 커브까지 거리 | 허용 속도 |
|---|---|
| 80m | 51 km/h |
| 50m | 41 km/h |
| 30m | 32 km/h |
| 15m | 24 km/h |
| 5m | 16 km/h |
| 0m | 10 km/h |

45km/h로 달리면 커브 **약 60m 전부터** 스로틀이 서서히 빠지기 시작한다.

### 튜닝 감각

- **부딪힌다 / 너무 늦게 줄인다** → `CornerDecelMetersPerSecSq`를 1.5로 낮춤(더 일찍 살살),
  또는 `CornerFullSlowAngleDeg`를 40으로 낮춤(작은 굴곡에도 예민)
- **너무 굼뜨다** → `CornerDecelMetersPerSecSq`를 3~4로(늦게까지 달리다 세게 제동)
- **전체적으로 느리게/빠르게** → `CornerStraightSpeedKmh`
- **커브 진입이 늦은 게 문제면 `CornerSpeedRampBandKmh`가 아니라 감속도를 만질 것** —
  램프 폭은 "속도 축"의 부드러움이고, 커브 반응 시점은 "거리 축" 문제다

---

## 7. 결과

사용자 확인: **"아주 깔끔하게 주행된다"** (2026-08-22). 기본값 그대로 나무 장애물 구간을 통과.

## 8. 남은 것

- [ ] 장애물이 아주 촘촘한 구간에서는 여전히 에이전트 반경 조정이 필요할 수 있음
      (현재 Tank 반경 200cm = 통과에 4m 필요)
- [ ] 커브 감속은 **경로 형상만** 본다 — 경로 옆의 장애물까지 거리는 안 본다. 좁은 틈을 직선으로
      통과하는 구간에서는 감속이 안 걸린다. 필요해지면 경로점 주변 클리어런스를 별도 항으로 추가하는
      방향
- [ ] 후진 시에는 이 거버너가 의미 없음(현재 자율주행이 전진만 쓰므로 문제 없음)
