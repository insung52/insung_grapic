# 총열 회전음 어테뉴에이션 축소 (BP_UGV_Vehicle_new)

2026-09-01 / 완료 / 배럴 회전음이 RCWS 발사음 기준을 그대로 물려받아 엔진음보다 10배 멀리(1.5km) 퍼지던 것을 50m로 축소하고, 노출돼 있으나 실제로는 동작하지 않던 감쇠 노브를 동작하게 고침.

## 증상

`BP_UGV_Vehicle_new`에서 총열(배럴) 회전 사운드가 UGV 엔진 사운드보다 훨씬 멀리까지
들림. 차량이 시야에서 사라질 만큼 먼 거리에서도 모터 회전음만 계속 들리는 상태.

## 원인

두 사운드 모두 `UAudioComponent`를 상속한 C++ 컴포넌트가 생성자에서
`bOverrideAttenuation` + `AttenuationOverrides`를 직접 세팅한다(별도 `USoundAttenuation`
애셋 없음). MCP로 `BP_UGV_Vehicle_new` CDO의 두 컴포넌트를 읽어서 실측한 값:

| 컴포넌트 | Sound | 반경(full volume) | FalloffDistance | 소멸 거리 |
|---|---|---|---|---|
| `VehicleEngineAudio` (`UVehicleEngineAudioComponent`) | `MS_UGVEngine` | 500cm (5m) | 15,000cm (150m) | **약 155m** |
| `BarrelSpinAudio` (`UBarrelSpinAudioComponent`) | `MS_barrel_spin` | 1,000cm (10m) | **150,000cm (1,500m)** | **약 1,510m** |

즉 회전음이 엔진음보다 **약 10배** 멀리 퍼지고 있었음.

원인은 `BarrelSpinAudioComponent.h`의 원래 주석에 그대로 적혀 있었음 — "같은 무기에서
나는 소리라 들리는 범위가 비슷해야 자연스러움"이라는 이유로
`URCWSFireControlComponent::FireSoundAttenuationRadiusCm`/`FireSoundFalloffDistanceCm`
(발사음)의 기본값 1000/150000을 그대로 복사해 온 것. 하지만 **총성**은 1.5km 밖에서도
들리는 게 자연스러운 반면 **배럴 회전**은 그냥 모터 기계음이라 같은 기준을 쓸 이유가 없음.
실제로 발사음 쪽은 BP에서 오히려 3,000cm / 250,000cm(2.5km)로 더 키워 놨음 — 발사음이
멀리 가는 건 의도된 것이고, 회전음이 그 기준을 따라간 게 잘못이었다는 뜻.

### 부수 원인 — 감쇠 노브가 실제로는 동작하지 않았음

`AttenuationRadiusCm`/`AttenuationFalloffDistanceCm`는 `EditAnywhere`로 노출돼 있지만
**생성자에서 한 번만** `AttenuationOverrides`로 옮겨 담고 있었음. 즉 BP나 인스턴스
Details 패널에서 이 값을 고쳐도 실제 감쇠는 전혀 바뀌지 않았고, 감쇠를 조정하려면 매번
C++ 값을 고치고 리빌드해야 했음. (`UVehicleEngineAudioComponent`도 동일한 구조 —
이번엔 건드리지 않음.)

## 수정 (`Source/titan_example/Vehicles/BarrelSpinAudioComponent.{h,cpp}`)

1. 기본값 축소: `AttenuationRadiusCm` 1000 → **300**(3m까지 full volume),
   `AttenuationFalloffDistanceCm` 150000 → **4700** → 소멸 거리 **약 50m**.
   1,510m → 50m로 **약 1/30**, 엔진음(155m)의 **약 1/3** 범위.
2. 생성자 인라인 세팅을 `ApplyAttenuationSettings()`로 분리하고, 생성자·`BeginPlay`·
   (에디터에서) `PostEditChangeProperty` 세 곳에서 호출. `BeginPlay`에서는
   `AdjustAttenuation()`으로 이미 재생 중인 사운드에도 반영(`bAutoActivate`라 `Super::BeginPlay`가
   먼저 `Play()`한 상태일 수 있음). 이제 BP/인스턴스에서 반경·폴오프를 고치면 리빌드 없이
   실제로 적용됨.

NaturalSound 곡선 + 거리별 LPF(20kHz→1kHz) 구성 자체는 그대로 유지 — 거리 값만 줄었음.

## `.uasset`은 건드리지 않았음 (중요)

`BP_UGV_Vehicle_new.uasset`을 바이너리로 확인한 결과 `AttenuationOverrides` /
`AttenuationShapeExtents` / `AttenuationRadiusCm` 델타가 **하나도 직렬화돼 있지 않음**
(이름 테이블에 걸린 `FireSoundAttenuationRadiusCm`/`FireSoundFalloffDistanceCm`는 RCWS
발사음 쪽 오버라이드라 별개). 즉 BP는 감쇠 값을 전적으로 C++ CDO에서 상속받고 있으므로,
C++만 고치고 리빌드하면 BP에 자동 반영됨.

MCP로 BP 컴포넌트에 값을 직접 써 넣지 **않은** 이유: 그러면 BP에 델타 오버라이드가 생겨
이후 C++ 기본값 변경을 영구히 가려버림. P4 체크아웃도 불필요해짐(.uasset은 read-only 유지).

## 적용/확인 방법

C++ 변경이라 **리빌드 필요**. 리빌드 후 확인:

- 에디터에서 `BP_UGV_Vehicle_new` → `BarrelSpinAudio` → Attenuation 카테고리가
  300 / 4700인지, Attenuation Overrides의 `FalloffDistance`가 4700인지.
- 인게임에서 UGV로부터 50m 이상 떨어졌을 때 회전음이 들리지 않고, 엔진음은 계속 들리는지.

값이 여전히 과하거나 부족하면 이제는 BP Details 패널에서 바로 조정 가능(리빌드 불필요).

## 참고

- 관련 코드: `Vehicles/BarrelSpinAudioComponent.{h,cpp}`,
  `Vehicles/VehicleEngineAudioComponent.{h,cpp}`, `Vehicles/RCWSFireControlComponent.h`
- 사운드 애셋: `/Game/SFX/MetaSounds/MS_barrel_spin`, `/Game/Vehicles/UGV/sounds/MS_UGVEngine`
- 발사음 감쇠 설계 배경: `guide/rcws_fire_control_dev_guide.md` §12.1
