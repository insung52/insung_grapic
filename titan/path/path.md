unreal 엔진의 moteToLocation 함수를 활용하여 이동 경로 생성 및 경로 추종 자동화

운전 모드 2개

1. 수동 주행

2. 목적지 입력 시 자동 주행

입력 : 목적지 좌표 수신

경로 주행
- MoteToLocation 호출 (AIController 모듈 사용)
- 목적지를 지형 3D 모델에 반영하여 위치 보정 수행
- PathFollowingComponent 가 경로 추종 수행
- OnMoveCompleted 함수로 도착 완료/실패 처리

1차적으로 가속, 조향 같은 운전 물리는 무시하고 길만 따라가게 구현
