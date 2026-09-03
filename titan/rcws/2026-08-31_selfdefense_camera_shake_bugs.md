# 자체방호축 카메라 떨림 / UGV 발사 셰이크 누출 (버그 2건)

2026-08-31 / 코드수정 완료·2PC 실환경 검증 대기 / 두 버그 모두 원인은 "셰이크 경로" 한 줄기 —
씬 캡쳐에 얹는 셰이크 오프셋이 한 프레임 어긋나 조향분을 셰이크로 오인(버그1), 명중 셰이크가
발사 주체와 무관하게 모든 로컬 카메라에 걸림(버그2).

관련 파일:
`Plugins/QuadCamModule/Source/QuadCamModule/{Public,Private}/SceneCaptureViewParity.{h,cpp}`,
`Source/titan_example/Vehicles/RCWSProjectile.cpp`.
선행 문서: `camera_pipeline/rtsp_postprocess_parity_0820.md` §2~3(이번에 고친 그 기능의 도입 문서),
`replication/replication_audit.md` §8.

---

## 0. 요약 — 두 버그는 같은 지점에서 만난다

리포트는 별개로 들어왔지만, 자체방호 PC의 **환경카메라(`BattlefieldCapture`)·CCTV 4분할
(`QuadCam`)·RCWS 조준경 캡쳐**는 전부 `FSceneCaptureViewParity::GetLocalViewShakeOffset()` 하나를
거쳐 "로컬 플레이어 카메라에 걸린 셰이크"를 자기 캡쳐 트랜스폼에 얹는다(2026-08-20 도입,
RTSP 화면에 피격 흔들림이 안 나오던 문제의 해결책).

- **버그 1**은 그 함수가 셰이크가 **아닌** 것(마운트 조향분)을 셰이크로 잘못 계산한 것.
- **버그 2**는 애초에 걸리면 안 되는 셰이크(UGV가 쏜 탄의 명중 셰이크)가 자체방호 PC의
  `PlayerCameraManager`에 걸린 것 → 메인 뷰(RCWS)가 흔들리고, 그게 위 함수를 타고 나머지 두
  화면에도 번짐.

사용자 최초 가설(공유 상위 컴포넌트 트랜스폼의 리플리케이션 노이즈 전파)은 **틀렸다**.
`ATitanTruck`의 컴포넌트 계층은 정상이고, `RCWSMount`/`BattlefieldCineCamera`/QuadCam
CineCamera들은 전부 `TruckRoot` 바로 아래 형제라 마운트 회전이 다른 카메라에 전파될 경로가
구조적으로 없다(`TitanTruck.cpp` 생성자 — `RCWSMount->SetupAttachment(TruckRoot)`,
`SetupBattlefieldCamera()`는 CineCamera의 `GetAttachParent()`에 캡쳐를 시블링으로 붙임).

---

## 1. 버그 1 — RCWS 조향 시 환경카메라/CCTV가 "회전은 안 하는데 떨림"

### 원인 (확정, 엔진 소스로 확인)

`GetLocalViewShakeOffset()`은 셰이크분을 이렇게 역산하고 있었다:

```cpp
// (수정 전)
FMinimalViewInfo Unshaken;
const_cast<AActor*>(ViewOwner)->CalcCamera(0.f, Unshaken);   // ← 이번 프레임 트랜스폼
... CamMgr->GetCameraLocation() - Unshaken.Location ...      // ← 직전 프레임 POV 캐시
```

두 값의 **샘플 시각이 항상 한 프레임 어긋난다**. 근거는 엔진의 `UWorld::Tick`
(`LevelTick.cpp:1835`):

```
// Update cameras last. This needs to be done before NetUpdates, and after all actors have been ticked.
for (...) PlayerController->UpdateCameraManager(DeltaSeconds);
```

즉 `APlayerCameraManager`의 POV 캐시 갱신은 **모든 액터 틱이 끝난 뒤**에 돈다. 씬 캡쳐를
돌리는 코드는 액터 틱 안(`ATitanTruck::Tick`, `URCWSComponent::TickComponent`,
`UQuadCamComponent::TickComponent`)이므로, 거기서 읽는 `GetCameraLocation()/GetCameraRotation()`은
**언제나 직전 프레임 값**인데 `CalcCamera()`는 **이번 프레임** 트랜스폼으로 즉석 계산된다.

⇒ 셰이크가 하나도 없어도 "카메라가 지난 한 프레임 동안 움직인 양"이 통째로 셰이크 오프셋으로
둔갑해서 캡쳐 트랜스폼에 실린다.

### 왜 2-PC에서만 보이는가

`ReplicatedMountRelativeRotation`은 `OnRep_MountRelativeRotation`에서 보간 없이 마운트에
바로 꽂힌다(`RCWSComponent.cpp:453`). 클라이언트(자체방호 PC)에서는 마운트 회전이
**리플리케이션 패킷이 도착한 프레임에만 계단식으로** 바뀌므로,

- 패킷 도착 프레임: 프레임 델타가 큼 → 큰 오프셋
- 나머지 프레임: 델타 0 → 오프셋 0

이 번갈아 실려서 **떨림**이 된다. 방향이 한쪽으로 누적되지 않으니 "회전은 안 하는데 떨린다"는
증상과 정확히 일치. 호스트(서버)에서는 조향이 매 프레임 조금씩 적용돼 델타가 작고 매끄러워서
거의 안 보인다 — **PIE/로컬 단일 프로세스로 재현이 안 됐던 이유**.

오프셋은 각 캡쳐의 **로컬 공간**에 얹히므로(`FScopedCaptureViewShake`), 방향이 전혀 다른
CCTV 4방/환경카메라에도 똑같이 실린다. 반면 RCWS 메인 뷰는 `PlayerCameraManager`의 POV를
그대로 쓰므로 이 오프셋이 안 걸린다 → "RCWS만 정상, 나머지가 떨림".

### 수정

`UViewShakeProbeCameraModifier`(신규, `SceneCaptureViewParity.h`)를 카메라 매니저의 모디파이어
체인 **맨 앞(`Priority=0`)** 에 꽂아, `ApplyCameraModifiers`가 도는 바로 그 자리에서
"아직 아무 모디파이어도 안 걸린 POV"를 기록한다. `GetLocalViewShakeOffset()`은 그 값과
카메라 매니저의 최종 POV 차이를 쓴다 — **둘 다 같은 프레임·같은 갱신에서 나온 값**이라
카메라 자체의 이동/조향은 정확히 상쇄되고 모디파이어(셰이크)분만 남는다.

- `Priority=0`이면 `APlayerCameraManager::AddCameraModifierToList`의
  `NewModifier->Priority <= M->Priority` 조건에 첫 원소부터 걸려 항상 리스트 맨 앞에 삽입 →
  엔진 `UCameraModifier_CameraShake`보다 먼저 불리는 게 보장된다.
- `ModifyCamera`는 POV를 건드리지 않고 `Super`(알파 보간 등 기본 살림)를 그대로 태워 `false`
  리턴 → 뒤의 셰이크 모디파이어가 정상적으로 이어서 돈다.
- **설치는 `GetLocalViewShakeOffset()`이 필요할 때 자동으로 한다**(`AddNewCameraModifier`).
  PlayerController/PlayerCameraManager 클래스를 갈아끼울 필요가 없어서 BP 쪽 설정과 무관하게
  동작한다. 설치 직후 1프레임만 Identity가 나가고 그다음부터 정상.
- `FMinimalViewInfo` 통째로 안 들고 위치/회전만 복사 — `PostProcessSettings` 안의 UObject
  포인터를 `UPROPERTY` 아닌 멤버로 붙들면 GC와 어긋나기 때문.

셰이크가 없을 때 오프셋은 **정확히 Identity**가 되고(`FillCameraCache(NewPOV)`가
`ApplyCameraModifiers` 결과를 그대로 캐시하므로 차이가 비트 단위로 0),
`FScopedCaptureViewShake`가 Identity면 트랜스폼을 아예 안 건드리므로 캡쳐는 완전 정지한다.

기존 방어선(`MaxShakeOffsetCm=200` / `MaxShakeOffsetDegrees=30`)은 이제 실질적으로 걸릴 일이
없지만 그대로 남겨뒀다.

---

## 2. 버그 2 — UGV 발사가 자체방호축 3화면을 전부 흔듦

### 원인 (확정)

프로젝트 전체 C++에서 카메라를 흔드는 코드는 **딱 하나**다(전수 확인): `ARCWSProjectile::
PlayImpactEffect`의 명중 셰이크.

```cpp
// (수정 전)
UGameplayStatics::PlayWorldCameraShake(World, ImpactCameraShakeClass, Location,
    ImpactCameraShakeInnerRadius /*100cm*/, ImpactCameraShakeOuterRadius /*3500cm*/, 1.f, false);
```

`APlayerCameraManager::PlayWorldCameraShake`는 **"누가 쐈는지"를 전혀 안 본다**. 월드의 모든
`PlayerController`를 훑어 착탄점과 카메라 위치의 거리만으로 셰이크를 건다. 리슨서버
2프로세스 구성에서 이게 두 갈래로 샜다:

- **(a) 각 프로세스 로컬 경로** — `Multicast_PlayImpactEffect`가 모든 프로세스에서 이 함수를
  부르므로, 자체방호 PC에서도 "UGV가 쏜 탄의 착탄"이 트럭 카메라 반경 35m 안이기만 하면
  셰이크가 걸렸다(UGV와 트럭은 같은 전개지에 나란히 있으므로 사실상 항상 걸림).
- **(b) 서버→원격 클라 RPC 경로** — 서버(UGV 호스트)에서 부른 것도 원격 클라이언트의
  `PlayerController`까지 훑어 `ClientStartCameraShake`(Client RPC)를 쏜다. 게다가 서버가 들고
  있는 원격 클라 `PlayerCameraManager`의 위치는 클라가 간헐적으로 보고하는
  (`ServerUpdateCamera`) 값이라 거리 판정 근거 자체가 부정확하다. 엔진 주석도
  `CalcRadialShakeScale`에 "need to ensure server has reasonably accurate camera position"이라고
  달아놨다.

그 셰이크가 자체방호 PC의 `PlayerCameraManager`에 걸리면 **RCWS 메인 뷰가 직접 흔들리고**,
같은 셰이크가 §1의 `GetLocalViewShakeOffset()`을 타고 **환경카메라/CCTV 캡쳐에도 번진다** —
리포트대로 3화면 전부.

참고: "UGV 자기 화면 반동"에는 이 명중 셰이크 말고 `URCWSFireControlComponent`의 마운트 반동
킥(`RecoilMountKick*` → `AddPanTiltInput`)도 있는데, 그건 UGV 액터 자기 마운트만 돌리므로
애초에 트럭과 무관하다(이번 버그의 원인 아님).

### 수정

`PlayWorldCameraShake`를 버리고 파일 스코프 헬퍼 `PlayImpactCameraShakeForShooterView()`로 교체
(`RCWSProjectile.cpp`):

1. **로컬 플레이어만** 훑는다(`FLocalPlayerIterator`) → 서버가 원격 클라에 RPC를 쏘는 (b) 경로
   자체가 사라진다. 각 프로세스는 이미 멀티캐스트로 같은 이벤트를 받으므로 정보 손실 없음.
2. `CameraManager->GetViewTarget() != ShooterActor`면 스킵 → **발사 주체를 지금 보고 있는
   화면에만** 셰이크. 발사 주체는 `WorldContextObject`(항상 발사자의
   `Multicast_PlayImpactEffect` 컴포넌트)의 `GetOwner()`로 얻는다.
3. 거리 감쇠는 엔진 `CalcRadialShakeScale`과 동일한 식으로 그대로 유지(그 함수가 `protected`라
   직접 못 불러 4줄 재구현) → **발사 주체 본인 화면의 기존 느낌은 안 바뀐다**.

### 의도된 부수효과 (사용자 확인 필요)

발사 주체를 안 보고 있는 화면은 착탄이 아무리 가까워도 안 흔들린다. 즉 **적 병사가 내 차량
근처를 쏴서 나던 피격 흔들림도 같이 사라진다**(`UEnemyCombatComponent`/`UAllyFormationComponent`
소유자는 어떤 로컬 플레이어의 뷰타겟도 아니므로).

"자체방호축은 UGV 발사에 전혀 영향받지 않아야 한다"는 요구를 만족시키려면 거리 기반 규칙
자체를 버려야 해서 이렇게 했다. 만약 "내가 피격당할 때는 흔들려야 한다"를 살리고 싶으면,
`Multicast_PlayImpactEffect` 3개 시그니처에 **피격 대상 액터**를 추가해서
"쏜 사람이 나 || 맞은 게 내 뷰타겟"으로 게이트를 넓히는 게 다음 단계다(이번엔 스코프 밖이라
안 함).

---

## 3. 검증 상태 — 아직 2-PC 실환경 확인 안 됨

**코드 수정만 완료. 실제 2대(UGV PC=호스트 / 자체방호 PC=클라) 확인은 미실시.**
빌드도 안 함(이 프로젝트는 사용자가 직접 빌드).

확인 절차:

1. UE 에디터에서 C++ 리컴파일(`UViewShakeProbeCameraModifier`가 새 UCLASS라 UHT가 돌아야 함 —
   에디터 Live Coding이 아니라 **에디터 닫고 빌드** 권장).
2. UGV PC 호스트 / 자체방호 PC `?Axis=SelfDefense`로 접속.
3. **버그 1** — 자체방호 PC에서 조이스틱으로 RCWS를 좌우/상하로 크게 훑는다.
   → 환경카메라 인셋과 CCTV 4분할이 **완전히 정지**해야 함(RCWS 메인 뷰만 움직임).
4. **버그 2** — UGV PC에서 연사.
   → 자체방호 PC의 RCWS 메인 뷰 / 환경카메라 / CCTV 전부 **무반응**이어야 함.
   → 동시에 UGV PC 자기 화면에서는 기존과 동일하게 마운트 반동 + (착탄이 35m 안이면) 명중
     셰이크가 나야 함(회귀 아님을 같이 확인).
5. **회귀 확인** — 자체방호 PC에서 트럭 RCWS로 근거리(35m 안) 사격.
   → 자기 3화면에 명중 셰이크가 예전처럼 실려야 함(§1 프로브가 정상 동작한다는 증거).

RTSP 쪽(`ugv_rc_gui`)도 같은 캡쳐를 보므로 3~5가 그대로 적용된다.
