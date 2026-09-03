# 드론 리플리케이션 — 클라이언트 권위 시뮬레이션

2026-09-01 / 완료(2프로세스 실환경 검증 대기) / 새 드론(`ADronePawn`)은 서버가 아니라 자체방호축 클라이언트가 시뮬레이션한다. Chaos Resimulation은 RTSP 지연·UGV 거동 영향 때문에 기각.

구 `AUAVPawn`의 리플리케이션(`replication_audit.md` §8 "UAV, 2026-08-13 구현 완료")은 서버
권위였다. 새 드론은 조종 주체가 달라서 방향을 뒤집었다 — 이 문서는 그 결정 근거와 배선 기록.

드론 자체의 동작은 `vehicle/drone/drone_flight_dev_guide.md` 15절, 작업 경과는
`vehicle/drone/2026-09-01_drone_replaces_bp_uav.md` 참고.

---

## 1. 전제 — 조종 주체와 서버가 다르다

| | 프로세스 | 역할 |
|---|---|---|
| 서버 | UGV축 PC | 리슨서버. UGV/RCWS/AI/시나리오 권위 |
| 클라 | 자체방호축 PC | 트럭 RCWS 빙의. **드론 조종은 여기서 한다** |

2대가 **서로 다른 머신**이다(같은 PC의 2프로세스가 아님). 드론을 서버 권위로 두면 자체방호축
조작자가 누른 입력이 왕복해야 화면에 반영되므로 지연이 그대로 드러난다.

---

## 2. Chaos 네트워크 물리(Resimulation)를 기각한 이유

UE5.8의 `EPhysicsReplicationMode::Resimulation`(클라 예측 + 서버 확인 + 롤백 재시뮬)을 먼저
검토했다. 정공법이지만 이 프로젝트에서는 비용이 크다:

1. **아직 WIP**이다(엔진 문서/코드 기준). 전시 일정에 리스크.
2. **`bTickPhysicsAsync`를 요구한다.** 이걸 켜면:
   - 이 프로젝트가 441~484ms → **68ms**까지 최적화해둔 RTSP 종단 지연이 **+33ms** 늘어난다
     (`rtsp/`, `camera_pipeline/` 참고). 지연 최적화가 이 시스템의 핵심 성과 중 하나라 되돌릴
     수 없다.
   - 튜닝이 끝난 **UGV Chaos 차량 거동이 바뀐다**(`vehicle/ugv/`). 물리 서브스테핑을 끄고
     `t.MaxFPS=60`으로 고정해둔 것과 같은 계열의 문제.

**위협 모델상 클라이언트를 신뢰해도 된다** — 전용 LAN에 놓인 전시 장비 2대뿐이고, 부정 클라이언트
같은 게 존재하지 않는다. 그래서 클라이언트 권위 시뮬레이션을 선택했다.

---

## 3. 배선

```
시뮬 클라(자체방호) ──► 서버 : Server_ReportState(Unreliable, WithValidation) @ 30Hz
                                위치 / 회전 / 속도 / 짐벌 yaw·pitch / 줌
서버 ──► 전원              : 위 값을 Replicated 프로퍼티로 재전파
                                + 시나리오 명령(경로 지시, 탐지 단계, 교전 프레이밍 지점)
```

| 프로퍼티 | 종류 | 방향 |
|---|---|---|
| `RepLocation`(NetQuantize100) / `RepRotation`(FQuat) / `RepVelocity` | Replicated | 서버 → 전원 |
| `RepGimbalYawDeg` / `RepGimbalPitchDeg` / `RepZoomLevel` | Replicated | 서버 → 전원 |
| `CommandedPathId` + `CommandedPathCounter` | ReplicatedUsing `OnRep_CommandedPath` | 서버 → 전원 |
| `RepEngagementFocusLocations` + `EngagementFocusCounter` | ReplicatedUsing `OnRep_EngagementFocus` | 서버 → 전원 |
| `DetectionPhase` | ReplicatedUsing `OnRep_DetectionPhase` | 서버 → 전원 |

설계 포인트:

- **비신뢰 RPC.** 매 프레임 최신값만 의미 있고 유실돼도 다음 패킷이 덮는다. 신뢰 전송의
  재전송·순서보장 비용이 순수 낭비다. 대신 `WithValidation`으로 값 범위는 검증한다.
- **명령에는 카운터를 붙인다.** `ReplicatedUsing`은 값이 바뀔 때만 뜨므로, 같은 경로를 다시
  지시하거나 같은 프레이밍 지점을 다시 보내면 OnRep이 안 뜬다. 카운터를 같이 올려서 강제한다.
- **시뮬 주체가 아닌 프로세스는 물리를 아예 안 돌린다** — `CollisionBox->SetSimulatePhysics(false)`,
  `Flight` 컴포넌트 틱 off. 두 프로세스가 각자 물리를 돌리면 미세한 차이가 누적돼 화면이
  어긋난다. 받은 값만 `RemoteInterpSpeed`(12/s)로 보간해 적용한다(`TickRemoteInterpolation`).
- 짐벌 캡쳐도 자체방호축에서만 돈다(`bDisableGimbalCapture`) — 아무도 안 보는 풀퀄리티 캡쳐를
  다른 프로세스에서 돌리지 않는다.

### 3.1 축 판정과 폴백

`FRtspAxisGate::ResolveLocalAxis`로 로컬 축이 확정된 뒤 `ApplySimulationAuthority()`를 부른다.
판정은 `ADronePawn::ResolveShouldSimulateDrone()` 3단계(2026-09-01 개정):

1. **단독 실행(`NM_Standalone`)이면 무조건 이 프로세스** — 넘길 상대가 없다.
2. **`SelfDefense` 또는 `Unspecified`** — 원래 규칙 + 폴백. `Unspecified`는 축 시스템이 없는 레벨
   (`L_DroneTest`는 순정 `APlayerController`를 쓴다)이나 게이트 타임아웃 대비.
3. **데모 실행 모드(`ScenarioConfig::RunMode == Demo`)의 리슨서버면 서버가 시뮬한다.**

> **3번이 2026-09-01에 추가된 이유 (버그 수정)**: 데모는 자체방호 클라이언트가 안 붙는 구성이
> 정상 시나리오다(전시용 1 PC, UGV축 호스트 단독). 그런데 예전 규칙으로는 **2번의 시뮬 주체가
> 세상에 존재하지 않아** 드론이 영영 안 날았고, 그러면 `HasObservedParachute()`가 계속 false라
> `UAVParachuteObserved` 트리거 → `MoveUGVToZone1Destination` 체인이 통째로 멈췄다(증상: "UGV가
> 1차 목적지로 출발을 안 한다". 2차 이동은 다른 트리거를 쓰므로 멀쩡해서 더 헷갈렸다).
> 데모에선 아무도 드론을 수동 조종하지 않으므로(전 구간 자율비행) 클라 권위를 유지할 이유도 없다.
> 실행 모드는 `GameState::bDemoRunMode`로 리플리케이트되므로 나중에 클라가 붙어도 판정이 갈리지 않는다.
> **FullSystem 구성의 클라이언트 권위는 그대로다** — 조종 지연 문제 때문에 내린 결정이므로.

> 같이 고친 것: 이 축 판정 블록 전체가 예전엔 `#if TITAN_RTSP_ENABLED` 안에 있었다. RTSP를 끄고
> 빌드하면 `ApplySimulationAuthority`가 아예 안 불려 `bAxisResolved=false`로 남고, 드론 `Tick`이
> 통째로 조기 리턴해서 **드론이 아무것도 안 한다**. 축 판정은 순수 게임플레이 관심사이므로 밖으로
> 빼고 `#if`는 스트림 생성에만 남겼다.

### 3.2 시뮬 주체가 아직 안 붙었을 때 (2026-09-02 수정)

시뮬 주체가 아닌 프로세스의 `Tick`은 곧바로 `TickRemoteInterpolation()`을 돌면서
`RepLocation`으로 수렴한다. 문제는 **시뮬 주체가 아직 접속하지 않았으면 `RepLocation`이
초기값 `(0, 0, 0)` 그대로**라는 것 — 드론이 배치 위치에서 **월드 원점으로 빨려 들어가
지형 아래로 사라진다**(`RemoteInterpSpeed = 12`라 0.3초면 도착).

증상은 **로비 → Host(UGV, `Demo=0`)로 들어갔을 때만** 나온다. 이 조합만 리슨서버라
`ResolveShouldSimulateDrone`이 false를 주기 때문이고, 나머지 진입 경로는 전부
`NM_Standalone`이라 §3.1의 1번에서 걸러진다:

| 진입 경로 | NetMode | 축 | 시뮬 주체 | 드론 |
|---|---|---|---|---|
| 로비 → Host | `ListenServer` | UGV | **원격(미접속)** | **사라짐 → 수정됨** |
| 로비 → Client solo | `Standalone` | SelfDefense | 이 프로세스 | 정상 |
| New_kadex_0811 직접 PIE | `Standalone` | UGV | 이 프로세스 | 정상 |
| 〃 후 `open ...?Axis=SelfDefense` | `Standalone` | SelfDefense | 이 프로세스 | 정상 |

**수정**: `ApplySimulationAuthority()`에서 시뮬 주체가 아닐 때, `RepLocation`/`RepRotation`이
아직 초기값이면 **배치된 트랜스폼을 초기값으로 심는다.** 그러면 Lerp가 제자리 보간이 돼서
실제 상태가 도착할 때까지 시작 지점에 그대로 떠 있는다.

```cpp
if (!bAuthority && RepLocation.IsZero() && RepRotation.Equals(FQuat::Identity))
{
    RepLocation = GetActorLocation();
    RepRotation = GetActorQuat();
    RepVelocity = FVector::ZeroVector;
}
```

> 참고: FullSystem(`Demo=0`) 구성에서 호스트만 켜고 자체방호 PC를 안 붙이면 **드론은 원래
> 안 난다**(설계상 자체방호 PC가 시뮬 주체). 이 수정은 "사라지는" 것만 막을 뿐이고, 드론이
> 날아야 하는 상황이면 자체방호 PC를 붙이거나 `Demo=1`로 실행해야 한다 — 안 그러면
> `UAVParachuteObserved` → `MoveUGVToZone1Destination` 체인이 §3.1의 예전 버그와 똑같이 멈춘다.

---

---

## 4. 소유권 함정 (중요)

**클라이언트가 Server RPC를 보내려면 그 PC가 대상 액터의 Owner여야 한다.** 엔진이 RPC 호출
권한을 소유권으로 판정하기 때문이다. 드론은 레벨에 직접 배치된 액터라 기본적으로 Owner가 없다.

`Atitan_exampleGameMode::PostLogin`에서 축이 `SelfDefense`인 PC에게 넘겨준다:

```cpp
if (TitanPC->PlayerAxis == EPlayerAxis::SelfDefense)
{
    if (AActor* Drone = UGameplayStatics::GetActorOfClass(GetWorld(), ADronePawn::StaticClass()))
    {
        Drone->SetOwner(TitanPC);
    }
}
```

**빙의(`Possess`)는 하지 않는다** — 자체방호축은 트럭 RCWS를 빙의 중이고, 드론 조종은 빙의 없이
컨트롤러 라우팅(`titan_examplePlayerController`)으로 한다.

소유권을 못 넘기면 증상이 "조용히 상태만 안 올라감"이라 원인 추적이 어렵다. 경고 로그를
넣어뒀다:

```
PostLogin: 레벨에서 ADronePawn을 못 찾아 소유권을 못 넘겼습니다 — 드론 상태가 서버로 전달되지 않습니다.
```

---

## 5. 검증 상태

| 항목 | 상태 |
|---|---|
| 단일 프로세스 시나리오 전체 흐름 | ✅ 확인 |
| PIE 2클라이언트 | ✅ 확인 |
| **2대 PC 실환경** | ❌ **미검증** |

2대 PC에서 확인할 것:
- 트랜스폼 동기화 품질(`RemoteInterpSpeed` 튜닝 필요 여부)
- `SetOwner` 타이밍 — 드론이 `PostLogin` 시점에 레벨에 이미 있는지
- `OnRep_CommandedPath` / `OnRep_EngagementFocus` / `OnRep_DetectionPhase` 실제 전달
- UGV축 화면에서 본 드론의 움직임이 자체방호축과 어긋나지 않는지
