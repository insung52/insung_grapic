# 위경도 캘리브레이션 갱신 + 나침반 방향 버그 수정

> `titan_example` 프로젝트. (위성사진 픽셀 좌표 / 실측
> 위경도 / 언리얼 월드 좌표 2개 지점 쌍)를 반영해 `GeoCoordinateUtils.h`의 씬↔실제 캘리브레이션을
> 갱신하고, 미니맵을 씬캡쳐에서 정적 위성사진으로 교체하고, 그 과정에서 발견된 나침반 방향
> 버그(핵심)를 수정한 작업 기록.

---

## 1. 배경

기존 `GeoCoordinateUtils.h`는 두 실측 지점("Cube"/"Cube3")의 위경도 + 언리얼 월드 좌표만으로
씬↔실세계 유사변환(균일 스케일+회전)을 계산하고 있었음. 이번에 같은 두 지점에 대해:

- 언리얼 월드 좌표가 재측정되어 값이 소폭 갱신됨
- 위성사진(`C:\graphics\assets\m_map_1024.png`, 1024×1024, `/Game/widget/m_map`로 이미 임포트됨)
  상의 픽셀 좌표가 새로 추가됨

두 정보가 정리되어 전달됨. 위경도 값 자체는 기존과 동일한 두 지점.

**2점 vs 3점 캘리브레이션**: 유사변환은 자유도 4개(스케일/회전/평행이동 x,y)라 점 2개(좌표 4개)면
수학적으로 정확히 풀린다. 다만 여유 자유도가 0이라 측정 오차가 그대로 보정값에 흡수되고,
X/Y 비균일 스케일이나 반사(거울상) 여부를 검증할 방법이 없다 — 3점 이상이면 최소자승 피팅 +
검증이 가능해진다. 이번엔 2점으로 진행, 3번째 점은 추후 여유 있으면 추가 권장.

---

## 2. GeoCoordinateUtils.h 캘리브레이션 상수 갱신

`PointA_SceneX/Y`, `PointB_SceneX/Y`를 real2world.md의 새 값으로 교체:

| | 위경도 (불변) | 기존 씬 좌표 | 신규 씬 좌표 | 위성사진 픽셀 (신규) |
|---|---|---|---|---|
| Point A | 37°54'44.30"N, 128°10'59.46"E | (8700, 19250) | (8210, 20210) | (527, 632) |
| Point B | 37°55'36.09"N, 128°10'53.53"E | (-1830, -111030) | (-2990, -110670) | (502, 26) |

`GetDistanceScaleFactor()`(UAV/UGV 속도, RCWS 사거리 등에 쓰이는 씬→실거리 배율)는
`GetSceneToRealTransform()`을 매번 재계산하는 구조라 이 상수 갱신만으로 자동 반영됨 — 별도 수정 불필요.

---

## 3. 위성사진 픽셀↔월드 캘리브레이션 추가 (미니맵 교체용)

미니맵을 기존 씬캡쳐(`AMinimapCaptureActor`의 `USceneCaptureComponent2D`) 대신 정적 위성사진으로
교체하기 위해, **위경도와 완전히 독립적인** 별도의 픽셀↔월드 유사변환을 추가:

- `GetPixelToWorldTransform()` — `GetSceneToRealTransform()`과 동일한 복소수 나눗셈 방식,
  단 (픽셀 좌표, 월드 좌표) 쌍으로 직접 피팅. 위경도를 거치지 않음.
- `WorldLocationToMapPixelUV()` / `MapPixelUVToWorldLocation()` — 미니맵 마커 배치, 클릭→월드좌표
  변환에 사용.
- `SceneYawToMapScreenAngleDegrees()` — 미니맵 위 마커 아이콘 회전각(화면 기준, 시계방향).
  나침반 방위각(`SceneYawToBearingDegrees`)과는 **다른 별도 공식** — 아래 4절의 버그와는 무관.

**주의(코드 주석으로도 명시)**: 이 픽셀↔월드 캘리브레이션도 점 2개뿐이라 반사(좌우/상하 뒤집힘)
여부는 검증 불가 — 미니맵 마커가 엉뚱하게 뒤집혀 보이면 이게 원인 후보 1순위.

### 3.1 AMinimapCaptureActor 구조 변경

- 기존: `USceneCaptureComponent2D` + `UTextureRenderTarget2D`로 매틱/주기적 캡쳐.
- 변경 후: 씬캡쳐 완전 제거, `/Game/widget/m_map`(정적 `UTexture2D`)만 `BeginPlay`에 로드.
  액터의 **월드 배치 위치가 더 이상 계산에 안 쓰임**(전부 `GeoCoordinateUtils` 상수 기반) — 레벨에
  액터 인스턴스가 하나 존재하기만 하면 됨, 위치는 아무 데나 둬도 무방.
- 레거시 회귀테스트용 `MissionDashboardWidget`(`WBP_test`)도 같은 `MapTexture`로 재배선해서
  컴파일 안 깨지게 처리.

### 3.2 미니맵 클릭 → 위경도 표시 (신규 기능)

`UMonitor1Widget::NativeOnMouseButtonDown` 오버라이드 — 클릭 좌표가 `MinimapImage` 영역 안이면
UV → `MapPixelUVToWorldLocation` → `WorldLocationToLatLong` → `FormatDMS`로 변환해서
`MinimapClickLatLongText`(TextBlock, WBP에 이름만 맞춰 배치) 에 표시.

---

## 4. 핵심 버그 — 나침반 방향이 거울상으로 뒤집혀 있었음

### 4.1 증상

RCWS 방위각 리본에서 북쪽 기준점은 정확한데, 오른쪽(동쪽)으로 90도 돌리면 방위각이 90(E)이
아니라 270(W)으로 표시됨. `AzimuthText`(숫자 텍스트) 자체가 틀린 값이라 리본 렌더링 문제가
아니라 데이터 문제. UGV RCWS, UAV `UAVCameraHeadingText`, 트럭 4분할캠 리본까지 전부 동일하게
반대 방향으로 나타남 — 전부 같은 공용 함수(`SceneVectorToBearingDegrees`)를 쓰기 때문.

### 4.2 원인

언리얼 월드가 **왼손 좌표계**인데, 씬 좌표(SceneX, SceneY)를 일반적인(오른손) 복소수 평면으로
다루면서 `Zs = SceneX + i·SceneY`로 취급 → 회전 합성 자체는 내부적으로 일관되지만, 실제
물리적 회전 방향(오른쪽으로 돎 = 시계방향)과는 거울상으로 어긋남. 기준점(북쪽) 하나만 맞으면
겉보기엔 정상처럼 보여서 지금까지 발견 안 됐던, `GeoCoordinateUtils.h`가 처음 작성될 때부터
있던 버그.

### 4.3 검증

real2world.md의 실측 두 지점 간 **진짜 방위각**을 표준 항법 공식(forward azimuth)으로
독립적으로 계산 —

```
bearing = atan2( sin(Δlon)·cos(lat2), cos(lat1)·sin(lat2) − sin(lat1)·cos(lat2)·cos(Δlon) )
```

— 하고, 코드가 예측하는 값과 대조:

| | 기존 코드 | 씬 Y부호 반전 후 |
|---|---|---|
| A→B 방위각 재계산 | (회전 자체가 다른 값, 절대값 불일치) | **정확히 일치** (354.839° = 354.839°) |
| Yaw 0→90 회전 시 방위각 변화 | **-90**(반대 방향) | **+90**(정상) |
| 두 캘리브레이션 지점 위경도 왕복 | 정확 | 정확 (변화 없음) |
| `GetDistanceScaleFactor()` (스케일) | 1.2241 | 1.2241 (변화 없음) |

씬 Y 델타 부호를 하나 반전하는 것만으로 두 검증이 동시에 통과함을 확인 — 사용자의 실제
인게임 테스트(오른쪽 90도 회전 시 W가 아니라 E가 나와야 함)로 최종 재확인.

### 4.4 수정

`GeoCoordinateUtils.h`의 `GetSceneToRealTransform`, `WorldLocationToLatLong`,
`SceneVectorToBearingDegrees` 세 곳에서 `SceneDY`를 부호 반전. 전부 공용 함수라 이 수정 하나로:

- `RCWSComponent::RefreshAzimuthElevation`의 `AzimuthDegrees`
- `AUAVPawn`의 `HeadingDegrees`(`UpdateStatusHUDFlightData`) / `GetGimbalWorldHeadingDegrees`
- `Monitor1Widget`의 트럭 4분할캠 리본(`TruckFrontRibbon` 등)

가 전부 한 번에 고쳐짐 — 각 파일은 이 공용 함수를 그대로 호출만 하고 있어서 별도 수정
불필요했음.

**영향받지 않는 것**: 미니맵 마커 회전(`SceneYawToMapScreenAngleDegrees`, 3절)은 이 버그와
완전히 별개의 독립 계산이라 안 건드림. `GetDistanceScaleFactor()`(속도/사거리 스케일)도 회전이
아니라 스케일(크기)만 쓰므로 값 불변 확인됨.

**부수 효과**: 회전값이 대폭 바뀌었으므로(약 -170° → +0.27°), 캘리브레이션 지점이 아닌 다른
위치의 위경도 표시(UAV 위경도, 미니맵 클릭 위경도)도 이제 다른(더 정확한) 값이 나옴 — 회귀가
아니라 원래도 부정확했던 부분이 같이 고쳐진 것.

---

## 5. 미니맵 UGV 마커 방향 — 별개의 간단한 수정

`Monitor1Widget::RefreshMinimap()`의 UGV 마커 회전 계산이 예전 UGV 메시(-X가 정면이던
네이티브 `AUGVPawn`/`BP_UGVFromTank`, 둘 다 폐기됨) 기준으로 `GetActorForwardVector()`를
negate하고 있었음. 현재 유일하게 남은 UGV(`BP_UGV_Vehicle`, 디자인팀 실제 모델)는 표준
+X-전방 컨벤션이라 이 negate가 오히려 틀린 상태였음 — 제거하고 `GetActorRotation().Yaw`를
그대로 사용하도록 수정.

---

## 6. 남은 이슈 / 참고사항

- 위경도 캘리브레이션, 픽셀↔월드 캘리브레이션 둘 다 점 2개 기준 — 3번째 지점이 생기면 최소자승
  피팅 + 반사 여부 검증으로 업그레이드 권장.
- Titan Truck 자체 RCWS 화면에는 아직 azimuth 관련 ruler 위젯이 안 붙어있어서(UGV RCWS만 확인)
  별도 확인 필요.
- UAV 카메라도 이번 수정으로 같이 고쳐졌는지 최종 재확인 필요(사용자가 UGV/트럭까지는 확인,
  UAV는 코드 공유 구조상 같이 고쳐졌을 것으로 예상되나 직접 테스트는 아직).
