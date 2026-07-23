UGV Chaos Wheeled Vehicle 구동계 프로토타입

Context

교수님이 UGV를 언리얼 기본 Chaos Vehicle 컴포넌트로 교체하는 걸 권장하셔서, 실제 Chaos 기반
탱크 레퍼런스 에셋(외부에서 받아온 M1A2, 이미 Migrate로 titan_example에 이주 완료 —
/Game/EvolveStudio/...)을 MCP로 심층 분석했음. 핵심 발견:

- 구조: AWheeledVehiclePawn 기반, ChaosWheeledVehicleMovementComponent, 좌우 7개씩
14개 로드휠(BP_TankWheel_Chaos_M1A2 : ChaosVehicleWheel), 스켈레탈 메시 필수.
- 엔진/변속기 참고값(확인됨): MaxTorque=8500, MaxRPM=2000, EngineIdleRPM=600, 자동
4단(ForwardGearRatios=[6,3,2,1], FinalRatio=3, 변속 RPM 1950↑/610↓), 서스펜션
SpringRate=3500/FrictionForceMultiplier=5, 차량 질량 30톤.
- 좌우 궤도 차동 조향(스키드 스티어) 로직은 어디에도 없음 — Blueprint 전체(EventGraph,
모든 커스텀 함수, 연결된 컴포넌트, 인터페이스), Config/DefaultInput.ini, 레거시
InputKey/InputAxis 노드까지 전부 훑었지만 SetThrottleInput/SetSteeringInput/
SetDriveTorque 같은 입력 주입 호출이 전혀 없음. SteeringSetup은 존재하지만
bAffectedBySteering=false라 죽어있는 설정. 즉 이 레퍼런스에
엔진/변속기/서스펜션 수치와 뼈대 구조뿐, 조향 알고리즘은 우리가 직접 설계해야 함
(엔진 자체 C++ 베이스 클래스의 기본 입력 처리에 의존하는 것으로 추정되나 소스 코드가
없어 확인 불가).

목표: 기존 UUGVMovementComponent(커스텀 힘 적용 방식)는 그대로 두고, 새 Blueprint로
병행 프로토타입 — 검증되면 나중에 교체, 아니면 폐기해도 기

사용자 확정 사항:
- 디자인팀 UGV 모델 아직 없음 — 마이그레이션된 탱크의 스켈레탈 메시/스켈레톤을 임시로
재활용(차체 본 + 좌우 궤도휠 본), 휠/차체 비주얼만 큐브/실
본 개수는 한쪽당 7→8개로 UE 스켈레톤 에디터의 "Add Bone"으로 확장(실제 UGV 모델
사진 기준 한쪽당 8개). 나중에 디자인팀 모델 오면 같은 뼈대에 메시만 교체.
- 질량 3000kg 고정(현재 UUGVMovementComponent와 동일 스펙 유지, 탱크의 30톤과 무관).
- 기어 변속: Chaos 네이티브 TransmissionSetup(자동 다단) 사
히스테리시스 로직을 새로 이식하지 않고 Chaos가 직접 처리, 대시보드엔 Chaos의
GetCurrentGear() 등을 연결.
- 트랙 비주얼: 탱크 레퍼런스의 UV 스크롤 방식(스플라인+텍스처 UV 스크롤)을 간소화해서
구현.
- 범위 제외: 피격/파괴/잔해, 라이트 기능 — 전부 제외. 이번 작업은 순수 구동계
(엔진/변속/서스펜션/조향/휠 물리)만.

아키텍처

1. 스켈레탈 메시 준비 (에디터 작업, 코드 아님)

1. 마이그레이션된 탱크 스켈레탈 메시/스켈레톤 복제(/Game/EvolveStudio/Tanks/M1A2/...
→ 새 위치, 예: /Game/Vehicles/UGV/Chaos/).
2. 스켈레톤 에디터에서 로드휠 본 한쪽당 7→8개로 확장(Add Bone).
3. 각 휠 본에 붙던 실제 탱크 메시 대신 심플 원기둥(/Engine/
소켓/컴포넌트로 교체. 차체 본엔 기존 SM_UGV_Tank_Temp 또는 심플 박스.
4. Physics Asset도 그에 맞게(휠 본마다 캡슐/구 콜리전, 차체는 박스) 재구성 — 탱크 것을
복제해서 본 개수만큼 콜리전 바디 추가.

2. 새 Pawn/컴포넌트 — AUGVChaosPawn(가칭, AWheeledVehiclePawn 상속)

- 신규 C++ 클래스로 만들지, 순수 BP로 프로토타입할지는 구현
레퍼런스 자체가 100% BP였고 Chaos Vehicle 설정 자체는 프로퍼티 기반이라, 우선 BP로
빠르게 세팅한 뒤 필요한 부분만(조향 로직 등) C++로 뺴는 쪽을 권장.
- ChaosWheeledVehicleMovementComponent: WheelSetups 16개(본
값은 탱크 참고값에서 3톤 스케일에 맞게 축소 조정(엔진 토크/서스펜션 스프링레이트 등 —
30톤 대비 1/10 질량이니 그대로 쓰면 과하게 반응할 가능성,
- WheelClass: UChaosVehicleWheel 상속하는 신규 BP(탱크의 BP_TankWheel_Chaos_M1A2
참고, bAffectedBySteering=false로 시작 — 스티어링은 아래 3절 방식으로 별도 처리).

3. 조향 — 레퍼런스에 없던 부분, 직접 설계

탱크 레퍼런스가 조향 로직을 안 갖고 있어서(위 Context 참고) 이 부분만 새로 만들어야 함.
구현 시작 시 가장 먼저 확인할 것: 로컬 엔진 설치 경로의 Cha
헤더(ChaosWheeledVehicleMovementComponent.h 등, 다운로드한 탱크 프로젝트와 달리 엔진
자체 소스라 로컬에 있음)에서 개별 휠에 토크/브레이크를 직접 지정하는 BlueprintCallable
함수가 있는지 확인 — 있으면 그걸로 좌우 궤도 차동 구동(기존 UUGVMovementComponent가
가상의 두 트랙 지점에 힘을 다르게 주던 것과 개념적으로 동일
매 틱 계산해서 적용. 없으면 대안(좌우 축을 별도 DifferentialSetup으로 분리하거나,
좌/우 휠 그룹에 각각 다른 SetThrottleInput류를 우회 적용하

4. 트랙 비주얼 (간소화)

탱크의 TrackPath_R(스플라인)+TrackStaticMeshes+UV 스크롤 방
속도에 맞춰 트랙 머티리얼 UV를 스크롤시키는 정도로 간소화 구현.

파일 목록

- 신규 스켈레탈 메시/스켈레톤/피직스 애셋 (/Game/Vehicles/U
- 신규 BP 또는 C++ Pawn 클래스(AUGVChaosPawn) + Wheel 클래스 — 기존 AUGVPawn/
UUGVMovementComponent는 수정하지 않음
- 탱크 참고 자료(/Game/EvolveStudio/...)는 계속 참고용으로 남겨둠(삭제 안 함)

검증

- 새 Pawn 스폰 후 WASD로 전진/후진/좌우 회전(제자리 피벗 포
작동하는지
- 기어가 Chaos TransmissionSetup 기준으로 자동 변속되는지,
정상 표시되는지
- 8개씩 16개 휠이 전부 지면에 닿고 서스펜션이 반응하는지(차체가 안 뚫리는지)
- 트랙 UV 스크롤이 실제 이동 속도와 대략 맞아떨어지는지
- 기존 BP_UGV/UUGVMovementComponent 쪽은 전혀 변경 없이 그대로 작동하는지