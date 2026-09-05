# 보병 재장전음 어테뉴에이션 분리 (아군/적군 라이플)

2026-09-03 / 완료 / 아군·적군 재장전 폴리 3종이 총성용 `SA_Weapon`(폴오프 1.5km)을 그대로 공유하던 것을 `SA_WeaponHandling_att`(폴오프 50m)로 분리.

## 증상 / 배경

"아군·적군 총 재장전 소리에 어테뉴에이션이 적용돼 있는지" 확인 요청에서 출발. 확인 결과
**적용은 되어 있었지만**, 재장전 폴리(탄창 빼기·끼우기·노리쇠)가 **총성과 완전히 동일한
감쇠 설정**을 쓰고 있어 1.5km 밖에서도 들리는 상태였음.

2026-09-01 배럴 회전음 건(`2026-09-01_barrel_spin_audio_attenuation.md`)과 **똑같은 패턴** —
"같은 무기에서 나는 소리"라는 이유로 발사음 감쇠를 그대로 물려받았지만, 총성이 멀리 가는 건
의도된 것이고 기계음/폴리는 그 기준을 따를 이유가 없음.

## 배선 구조 (조사 결과)

| 축 | 캐릭터 BP | 무기 BP |
|---|---|---|
| 아군 | `BP_Ally_kadex` ← `BP_ThirdPersonCharacter` | `BP_AR4Rifle` |
| 적군 | `BP_Enemy_kadex` ← `BP_Enemy_Base` | `BP_EnemyRifle` |

두 라이플 BP의 `StartReload` 커스텀 이벤트가 `SpawnSoundAttached`로 폴리 3종을
0.6s / 0.7s / 0.7s 간격으로 순차 재생함(그래프 내용 동일):

- `01_assault_rifle_reload_1_drop_the_mag`
- `02_assault_rifle_reload_1_insert_the_mag`
- `03_assault_rifle_reload_1_bolt`

**`SpawnSoundAttached`의 `AttenuationSettings` 핀은 양쪽 BP 모두 None**(두 `.uasset`에
SoundAttenuation 에셋 임포트가 0개). 따라서 감쇠는 **사운드 웨이브 애셋 자신의
`USoundBase::AttenuationSettings`**에서 오고, 그게 `SA_Weapon`이었음.

`SA_Weapon`(`/Game/Soldiers/Weapons/`)의 참조자는 정확히 4개였음 — 재장전 폴리 3종 + 발사음
`assault_rifle_gunshot_01`.

## 수정

새 에셋은 만들지 않고, **이미 있으나 아무 데서도 참조되지 않던**
`/Game/Gun_effect/Audio/Attenuation/SA_WeaponHandling_att`를 재장전 폴리용으로 재활용함
(이름·용도가 그대로 맞음). 웨이브 3종의 `AttenuationSettings`만 그쪽으로 재지정.

### 감쇠 값 비교

| | `SA_Weapon` (발사음, 변경 없음) | `SA_WeaponHandling_att` (재장전, 수정 후) |
|---|---|---|
| Distance Algorithm | NaturalSound | NaturalSound *(Logarithmic에서 변경)* |
| Shape / Radius (full volume) | Sphere / 3,000cm (30m) | Sphere / 400cm (4m) |
| Falloff Distance | 150,000cm (**1,500m**) | 5,000cm (**50m**) *(1,500cm에서 변경)* |
| dB Attenuation At Max | -60 | -60 |
| 실질 소멸 거리 | 약 1,530m | 약 **54m** |

재장전음 도달 거리 **약 1,530m → 54m (약 1/28)**.

### `SA_WeaponHandling_att` 원본값 (되돌릴 때 참고)

이 애셋은 원래 Gun_effect 팩에 딸려 온 미사용 애셋(headRev 1, 참조자 0)이었고, **딱 두 필드만**
고쳤음. 나머지(`attenuationShapeExtents` 400 / `stereoSpread` 200 / LPF 1000·3000·20000→20000 /
reverb 400·4000 등)는 그대로 둠.

| 필드 | 원본 | 변경 후 | 이유 |
|---|---|---|---|
| `falloffDistance` | 1500 | **5000** | 원본 15m(→소멸 19m)는 FPS에서 *플레이어 본인 총*을 위한 값. 이 프로젝트는 3인칭/차량 관측 시점이라 분대를 수십 m 밖에서 보는 경우가 많아, 그 거리에서 재장전음이 아예 안 들리면 "소리가 사라졌다"로 읽힘. 배럴 회전음 선례(약 50m)와 맞춤. |
| `distanceAlgorithm` | Logarithmic | **NaturalSound** | `SA_Weapon`과 감쇠 곡선 성격을 통일 |

## 왜 웨이브 내부 오버라이드가 아니라 애셋 교체인가

`USoundBase`의 `bOverrideAttenuation` / `AttenuationOverrides`는 **unreal-mcp 리플렉션으로
읽기·쓰기가 안 됨**(`get_properties`가 "could not be read"로 거절). 따라서 웨이브별 인라인
오버라이드는 불가능했고, 애셋 참조를 바꾸는 방식만 가능했음.

새 `SA_...` 애셋을 MCP로 만들지 않은 이유는 세션 규칙(`새 에셋은 MCP로 만들지 말 것`) —
기존 애셋의 프로퍼티 수정은 허용 범위라 그 안에서 해결함.

## 검증

- MCP `get_properties`: 웨이브 3종 모두 `AttenuationSettings = SA_WeaponHandling_att`.
- 디스크 `.uasset` 임포트 테이블: 3종 모두 `/Game/Gun_effect/Audio/Attenuation/SA_WeaponHandling_att`,
  발사음은 `/Game/Soldiers/Weapons/SA_Weapon` 유지.
- `get_referencers("/Game/Soldiers/Weapons/SA_Weapon")` → 이제 발사음 1개만.
- P4: 4개 파일 체크아웃 후 저장(`SA_WeaponHandling_att` + 폴리 3종). **커밋(submit)은 안 함.**
- 인게임 실청취 검증은 **안 했음** — 50m 안팎에서 재장전음이 자연스럽게 사라지는지 확인 필요.

## 남은 것 / 참고

- `SA_WeaponHandling_att`의 LPF가 사실상 무효(`LPFFrequencyAtMin/Max` 둘 다 20000)라 거리에
  따른 muffling이 없음. `SA_Weapon`은 50m 지점에서 이미 상당히 muffle됨. 재장전음이 원거리에서
  너무 또렷하게 느껴지면 `LPFFrequencyAtMax`를 4000 정도로 낮추면 됨.
- 애셋 위치가 흩어져 있음 — 발사음 감쇠는 `Soldiers/Weapons/`, 재장전 감쇠는 `Gun_effect/Audio/`.
  나중에 정리 세션에서 한쪽으로 모으면 좋음.
- `Content/Gun_effect/Audio/Cue/CUE_Shotgun_Reload_Cue`는 여전히 어떤 BP도 참조하지 않는
  미사용 애셋(이번 작업과 무관).
- 관련 문서: `sfx_vfx/2026-09-01_barrel_spin_audio_attenuation.md`,
  `guide/rcws_fire_control_dev_guide.md` §12.1(RCWS 발사음 — 별개 시스템, 이번에 변경 없음).
