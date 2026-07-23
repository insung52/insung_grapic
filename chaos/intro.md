kadex 전시회에 제출할 언리얼 기반 시나리오 씬 제작 프로젝트의 일부를 진행하려함.

먼저 UGV가 무엇인지 알아야 한다.

C:\private\titan\all.md 기능 명세서?(참고만) 및 시나리오 정리

C:\working\kadex\titan_example\Content\Vehicles\UGV\BP_UGV.uasset

기존 무료 탱크 로우폴리 메시를 이용한 테스트용 UGV (무인 자동 주행/사격 탱크형 포탑)

C:\private\titan\path\ugv_driving_dev_guide.md

UGV의 주행 기능을 간단하게 구현했던 과정 정리

C:\private\titan\path\joystick_camera_control_dev_guide.md

조이스틱 기반 카메라 조작 기능 과정 정리

C:\private\titan\path\detection_dev_guide.md

객체 감지 기능 구현 정리

C:\private\titan\rcws_fire_control_dev_guide.md

자동 조준/발사 기능 정리

C:\private\titan\status_hud_dev_guide.md

WBP 와 실제 액터들 연결 과정 정리. 최신화가 안되어있으므로 주의.

---

본격적인 내용들

C:\working\kadex\titan_example\Content\Vehicles\UGV\ChaosFromTank\BP_UGVFromTank.uasset

이전에 회사에서 유료로 구매한 chaos wheeled vehicle 을 이용한 탱크 에셋에 위의 우리가 구현한 UGV 관련 기능들을 이식한 에셋. 우리에게 필요없는 기능들이 많고 chaos vehicle 관련 부분에서 상당히 헤매고 아직도 어려운 부분이 많다.

- 해당 과정 정리 C:\private\titan\M1A2_UGV_Conversion.md

C:\graphics\assets

디자인팀에서 받은 blend 에셋 모델 및 텍스쳐 파일들. 최종적으로 이 에셋을 사용하여 UGV 를 구현해야 한다.

Chaos wheeled vehicle 관련해서 나도 모르는 부분이 많고 claude code 와의 협업으로도 해결하지 못한 문제들이 많다. 때문에 chaos wheeled vehicle 관련해서 충분한 조사가 필요할거같다.

1차 목표는 디자인팀에서 받은 blend 에셋 모델을 확인하고, 내가 blender를 잘하는 편이 아니라, 어떤 구조로 되어있는지 blender mcp 로 확인 후 알려주는것. 언리얼에서 작업할때 움직이는 부분은 차체가 몸통이고, 궤도가 m1a2 탱크처럼 자연스러운 회전, 가속에 따른 물리적인 움직임(출렁임 등)이 가능하도록 해야하고(instanced mesh + spline 등 이용) 차체 위에서 포탑이 360도로 좌우 회전, 총열 등 실제 발사가 되는 부분은 상하 특정 범위 내에서 회전 가능해야한다.

결정해야할 사항이 있는데, 이전처럼 m1a2 블루프린트 액터를 복제해서 거기에 우리 에셋을 적용하는 방식으로 할지, 아니면 m1a2 구조는 참고만 하고 깔끔하게 처음부터 구현하는 방식으로 할지 정해야 한다. 이전에 다른 세션에서 블렌더 mcp 활용해서 간단한 탱크모양 스켈레탈 메시를 만들고 거기에 chaos 를 적용시켜보았을때는 여러 문제가 발생했다. (blender - unreal 축 정렬 시켜야함, 콜리전 기준 위치와 시각적 위치가 불일치, 휠 서스펜션 적용 위치가 실제 탱크 휠들의 bone 위치가 아니고 root 에 몰려있다던지 등.)
해당 문제들을 격은 뒤 도저히 해결 방법을 찾지 못해서 결국 교수님의 조언대로 m1a2 탱크를 복제해서 사용했다. 이 때에도 사소한 문제가 있었다. 스케일을 우리 ugv에 맞게 0.5로 했는데 chaos wheel 의 바퀴 서스펜션 적용 기준은 스케일이 적용이 안되는것같이 탱크가 공중에 떠서 이동하는 버그. 임시방편으로 휠에 z 방향 오프셋을 적용하였다.

나는 가능하다면 chaos wheeled vehicle 의 모든 작동 원리를 파악하고 작업하고싶음. 그래야 나중에 내가 원하는대로 커스텀 하기도 쉽고, 건드릴 수 있는 부분들이 많아질거 같아. 또 m1a2 탱크는 블루프린트만으로 구현되어있는것 같아서, 범용성이 c++에 비해서 조금 부족해보이고 claude 로 작업하기에도 mcp 가 있긴하지만 번거로움.
단점은 처음부터 구현하는건 시간이 얼마나 걸릴지 모른다는것.
때문에, 우리의 작업 방향은 m1a2 유료 에셋을 뜯어보면서 구조를 파악해보고, 언리얼 chaos wheeled vehicle 관련해서 웹에서 공식 문서들에서 상세한 사용방법들과, 사용자들의 후기 같은걸 찾아서과 알려진 버그들 및 사용자들의 경험들을 찾아보아야 할 것 같다. 특히 각 wheel 들의 서스펜션 작동 원리 및 배치 방법 등. 이 조사 내용들을 C:\private\chaos 해당 폴더에 문서로 정리하는것을 0차 목표로 한다.