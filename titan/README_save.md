# titan_example — 조작 가이드

카덱스 전시회 시나리오 시뮬레이터. 이 문서는 **시나리오를 실행/조작하는 사람**을 위한 명령어·조작
정리입니다(내부 구현 문서는 `C:\private\titan\README.md` 참고).

레벨 시작 시 기본 상태: 3D 월드 렌더링 켜짐, 조이스틱 시점은 **UGV RCWS**를 조작 중.

---

## 1. 콘솔 명령 (PIE/패키지 빌드에서 `~` 키로 콘솔 열고 입력)

### UGV(`BP_UGV_Vehicle`) 주행
> 명령 이름이 `UGVFromTank`로 되어있는데, 예전에 M1A2 탱크 Blueprint를 복제해서 만들었던
> 시절 이름이 그대로 남은 것 — 현재 실제 UGV(`BP_UGV_Vehicle`)를 제어하는 명령이 맞음.
> **추후 이름 정리 예정.**

| 명령 | 동작 |
|---|---|
| `SetUGVFromTankMode Idle\|Manual\|Auto` | UGV 주행 모드 전환 (빙의 없이 가능) |
| `MoveUGVFromTankTo (X=...,Y=...,Z=...)` | UGV를 지정 좌표로 자율 이동시킴 (괄호 필수, 예: `MoveUGVFromTankTo (X=13692,Y=-70187,Z=-4703)`) |

### UAV
| 명령 | 동작 |
|---|---|
| `BeginUAVMissionToTarget (X=13692,Y=-70187,Z=-4703)` | UAV 임무 시작 — 5초간 20m 상승 후 지정 좌표로 순항 비행 (UAV는 빙의 대상이 아니라서 이 콘솔 명령이 유일한 시작 방법) |

### RCWS / 카메라 시점
| 명령 | 동작 |
|---|---|
| `SetCameraControlTarget Idle\|TruckRCWS\|UGVRCWS\|UAV` | 조이스틱 시점을 어느 차량으로 보낼지 전환 |
| `SetRCWSMode Remote\|AutoSurveillance\|AutoAim\|AutoFire` | 현재 카메라 대상 RCWS의 교전 모드 설정 |
| `SetRCWSStabilization true\|false` | 현재 카메라 대상 RCWS의 2축 안정화 on/off (기본 켜짐) |

### 시나리오 연출
| 명령 | 동작 |
|---|---|
| `SetWorldRenderingEnabled true\|false` | 3D 월드 렌더링 자체를 껐다 켰다 (기본 켜짐) |
| `BeginScenarioEnemyContact` | "적 접촉" 신호 발생 대체용 — 레벨에 `EnemyCube` 태그가 붙은 액터 위치를 적 신호로 사용, 미니맵에 반영 |

---

## 2. 조이스틱/키보드 조작 (Enhanced Input — 실제 키 배정은 IMC 에셋에서 설정)

| 조작 | 동작 |
|---|---|
| 시점 Pan/Tilt (Vector2D 축) | `SetCameraControlTarget`으로 지정된 차량의 RCWS/짐벌을 조준 이동. **RCWS가 Remote 모드일 때만** 작동 — Auto 계열 모드에서는 자동 조준이 우선이라 입력이 무시됨 |
| UGV 이동/조향 (Vector2D 축) | 빙의 없이 작동 — UGV가 Manual 모드일 때만 반응 |
| UGV 브레이크(Space) | 위와 동일하게 빙의 무관하게 작동 |
| 수동 발사(홀드) | 현재 카메라 대상 RCWS를 시야 방향 그대로 연사 (자동 조준 보정 없음) |
| RCWS 모드 다음/이전 | `Remote → AutoSurveillance → AutoAim → AutoFire` 순환 (양방향) |
| RCWS 줌 인/아웃 | Remote 모드에서만 작동, 6단계(`0.5/1/2/4/8/16`)로 전환, 단계당 약 0.4초 |
| **M 키** | TitanTruck/UGV의 4분할 CCTV(QuadCam) 화면 토글 — 현재 빙의 중인 차량 기준 |

---

## 3. 알려진 제약 / 미구현 사항

- **장전/비장전, 사격대기/사격, EO/IR(주간/야간) 전환**: 내부 함수(`SetLoaded`/`SetFireReady`/`SetCameraMode`)는 존재하지만, **콘솔 명령·조이스틱 입력·UI 버튼 어디에도 연결되어 있지 않습니다.** 현재는 항상 "장전됨/사격대기됨" 상태로 고정되어 있고, 이 세 가지는 실질적으로 조작 불가능한 상태입니다. 실제 데모에 필요하면 추가 연결 작업이 필요합니다.
- **UGV 비상정지**: 기획 문서(`memo.md`)에 언급만 있고 코드에는 별도 구현이 없습니다 — 대신 `SetUGVFromTankMode Idle`(급제동)로 대체됩니다.
- **UAV 수동 비행/줌 조이스틱 축**: UAV는 이착륙·이동이 전부 스크립트(자동)이고, 조이스틱로 조작 가능한 건 짐벌 카메라 시점뿐입니다. 줌은 조이스틱 축이 아니라 WBP의 2단계(1.0x/2.5x) 버튼 토글입니다.

---

참고: `C:\private\titan\path\joystick_camera_control_dev_guide.md`/`ugv_driving_dev_guide.md` 등 기존 개발 문서 일부는 최신화가 안 되어 위 목록과 다를 수 있습니다(예: RCWS 탄약 수, UAV 짐벌 최대 피치각, 월드 렌더링 기본값 등) — 실제 동작은 이 문서와 C++ 소스 기준이 최신입니다.
