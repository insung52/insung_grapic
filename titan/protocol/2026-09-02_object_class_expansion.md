# UGV 탐지 `ObjectClass` 6분류 확장

2026-09-02 / 완료(빌드·실측 검증 대기) / ICD 원문 `Human`/`Car` 2값을 플랫 6값(Ally/Enemy/UGV/MobileCommandPost/Drone/Parachute)으로 확장, 낙하산이 "Car"로 나가던 버그 해소.

## 1. 배경

`UGV_Period_ObjectDetectionResult.Objects[].ObjectClass`는 ICD 원문상 `Human`/`Car` 두 값뿐인데,
LIG 1차 답변(`documents/response_0828.md` Q10)에서 **"트럭/UGV/민간 차량 구분이 가능하시면
구분해서 보내주셔도 되고, `Car`로만 구분해서 보내주셔도 됩니다"**로 우리 재량 항목이 됐다.
실측 중 **낙하산이 `Car`로 표시되는** 게 발견돼서 이번에 최종 형식을 확정하고 구현했다.

LIG가 이미 재량이라고 답한 사안이라 추가 답변을 기다리지 않고 구현했다 — LIG에는 질문이 아니라
**결정 통보**만 하면 된다(`lig_questions_0816.md` §5-2, 아직 미발송).

## 2. 조사 — 왜 낙하산이 `Car`로 나갔나

확장 전 판정 로직은 `UGVRemoteControlSubsystem.cpp`의 한 줄이 전부였다:

```cpp
ObjJson->SetStringField(TEXT("ObjectClass"), Cast<ACharacter>(Target.Target) ? TEXT("Human") : TEXT("Car"));
```

낙하산 구현을 실제로 확인한 결과(추정 아님):

- `Content/Parachute/BP_Parachute` — **부모 클래스가 `/Script/Engine.Actor`**(대응 C++ 클래스
  없음). `StaticMeshComponent` + `GeometryCacheComponent`(펼쳐지는 애니메이션) +
  `UDetectableTargetComponent` 조합의 소품 액터.
- 그 `UDetectableTargetComponent`의 `Faction`이 **`EMilitaryFaction::EnemyEvidence`**
  (2026-08-03에 "전투원이 아닌 적의 흔적"용으로 추가된 값 — `Faction == Enemy` 엄격 비교를
  쓰는 RCWS 자동조준/드론 정찰 대상 계산에서 자동으로 빠지도록 만든 값).
- 즉 낙하산은 **강하 중인 적 캐릭터가 아니라 캐릭터와 완전히 분리된 별도 액터**다. 드론의
  "낙하산 관측"(`ADronePawn::ParachuteActor`, `UAVParachuteObserved` 트리거)도 이 액터를 직접
  가리키는 인스턴스 포인터로 동작한다.

`ACharacter`가 아니므로 위 삼항연산자의 else 가지로 떨어져 `Car`가 나갔던 것 — 버그가 아니라
2분류 로직의 필연적 결과였다.

**`EnemyEvidence`를 쓰는 에셋은 프로젝트 전체에서 `BP_Parachute` 하나뿐**(Content 전수 검색으로
확인) — 낙하산 BP에 대응하는 C++ 클래스가 없어 클래스 캐스팅으로는 집을 수 없으므로, 이 Faction
값이 낙하산의 유일한 안정적 식별자다. 낙하산 외의 "흔적" 액터가 생기면 이 분기부터 다시 봐야 한다.

## 3. 확정 형식 — 2단계 계층이 아니라 플랫 6값

| 값 | 대상 |
|---|---|
| `Ally` | 아군 보병(`BP_Ally_kadex`) |
| `Enemy` | 적군 보병(`BP_Enemy_kadex`) |
| `UGV` | 무인차량(`BP_UGV_Vehicle*`) |
| `MobileCommandPost` | 이동형지휘소(`ATitanTruck`) |
| `Drone` | 정찰 드론(`ADronePawn`, 구형 `AUAVPawn` 포함) |
| `Parachute` | 적 강하 흔적(`BP_Parachute`) |

2단계 계층(`Human` → Ally/Enemy, `Car` → UGV/MobileCommandPost/Drone)은 **드론이 어떻게 봐도
"Car"에 안 들어간다**는 문제로 기각. 이 시나리오엔 적 차량·적 드론이 없어서 장비 3종은 항상 아군
자산이라, 플랫으로 펴도 피아식별 정보가 사라지지 않는다.

## 4. 구현

### 4.1 `Network/UGVRemoteControlTypes.h`

`UGVRC::ObjectClass` 네임스페이스에 6개 문자열 상수 추가(`Cmd::` 상수들과 같은 스타일).

### 4.2 `Network/UGVRemoteControlSubsystem.cpp`

익명 네임스페이스에 `ClassifyDetectedObject(const FDetectedTarget&)` 추가,
`BuildDetectionObjectJson`이 이걸 호출하도록 교체. **판정 순서에 의미가 있다** — 위에서부터 더
구체적인 것 먼저:

1. `Faction == EnemyEvidence` → `Parachute` (2절 근거)
2. `ACharacter` → Faction으로 `Ally`/`Enemy` (보병만 캐릭터다)
3. `ATitanTruck` → `MobileCommandPost`
4. `ADronePawn` / `AUAVPawn` → `Drone` (`AUAVPawn`은 `ADronePawn`으로 대체 진행 중인 구형
   `BP_UAV` — 레벨에 남아 있을 수 있어 같이 처리)
5. `AWheeledVehiclePawn` → `UGV`. 실사용 `BP_UGV_Vehicle`/`BP_UGV_Vehicle_new`가 프로젝트 C++
   클래스가 아니라 **엔진 `AWheeledVehiclePawn` 직속 BP**라 이게 유일한 공통 조상이다. 이
   레벨에서 Chaos 휠드 폰은 UGV 계열뿐(트럭 `ATitanTruck`은 `APawn`이라 안 걸림).
6. 그 외 → **Faction만 보고 `Ally`/`Enemy`** + 액터/클래스명을 담은 경고 로그.

6번 기본값 선택 근거: 6값 중 "장비 3종"을 지어내면 오퍼레이터에게 거짓 정보가 되지만,
피아식별(가장 중요한 비트)은 `FDetectedTarget::Faction`으로 항상 알 수 있다. 탐지 자체를 빼는
것(객체를 아예 안 보냄)보다 낫고, 새 탐지 대상 에셋이 추가됐다는 신호를 로그로 남긴다.

### 4.3 `ugv_rc_gui`(원격통제기 목업, 별도 저장소)

`detection_overlay.py`가 `Human`/`Car` 문자열에 의존하는 로직은 원래 없었고(라벨에 값을 그대로
찍기만 함, 박스는 전부 초록 고정), 6값이 피아식별까지 담게 됐으므로 **`ObjectClass`별 박스 색**을
추가했다 — 아군=초록, 적군=빨강, 낙하산=주황, 아군 장비 3종=하늘색. 모르는 값(예전 빌드의
`Human`/`Car`, 앞으로 늘어날 값)은 **회색**으로 떨어뜨린다. 조용히 초록으로 그리면 아군으로
오독되기 때문.

## 5. 검증

`New_kadex_0811` 레벨에서 `UDetectableTargetComponent`를 가진 액터 전수 확인(에디터 MCP):

| 액터 | 개수 | `Faction` | → `ObjectClass` |
|---|---|---|---|
| `BP_Ally_kadex_C_*` | 25 | 전부 `Friendly` | `Ally` |
| `BP_Enemy_kadex_C_*` | 15 | 전부 `Enemy` | `Enemy` |
| `BP_TitanTruck_C_4` | 1 | `Friendly` | `MobileCommandPost` |
| `BP_Drone_C_2` | 1 | `Friendly` | `Drone` |
| `BP_UGV_Vehicle_new_C_3` | 1 | `Friendly` | `UGV` |
| `BP_Parachute_C_3` | 1 | `EnemyEvidence` | `Parachute` |

`AUAVPawn`(구형 `BP_UAV`) 인스턴스는 이 레벨에 없음. **6번(fallback)으로 떨어지는 액터는 없다.**

**남은 것**: 빌드 후 `ugv_rc_gui`로 실제 수신 확인(이 세션은 프로젝트를 빌드하지 않음).

## 6. 함께 갱신한 문서

- `protocol/protocol_icd.md` §2 — `Detection` 타입의 `objectClass`를 `ObjectClass` 타입으로
  분리하고 6값 정의 + 변경 사유/날짜 명시. §6 미확정 목록의 해당 항목도 완료 처리.
- `protocol/ugv_rc_feature_gap_analysis.md` — `ObjectClass` 행 ⚠️ 근사 → ✅ 실동작, 판정 순서 기록.
- `protocol/lig_questions_0816.md` §5-2 — "어떤 형태를 원하시나요" 질문 → **결정 통보**로 재작성.
- `CURRENT_STATE.md` §12 — 답변 대기가 아니라 "통보 발송 대기"로 상태 갱신.
- `guide/detection_dev_guide.md` — 상단 경고 배너에 이 문서 포인터 추가.
