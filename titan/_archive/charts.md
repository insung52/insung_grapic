> [보관됨 2026-08-31] 최신 버전: `status_hud_dev_guide.md`. 사유: 이 문서의 UAV 상태 차트 위젯
> 목업(배터리/고도/속도/방향 카드)이 `status_hud_dev_guide.md`(2026-06-25)에서 실제
> `StatusHUDWidget`/`LineGraphWidget`/`RadialGaugeWidget`/`CompassWidget`으로 완전히 구현되고
> 이후 `ui_dev_guide.md`에서 더 발전됨.

![alt text](charts-1.png)

titan truck 등 여러 이동 수단에 여러 상태를 표시하는 차트 위젯을 추가.

레퍼런스 이미지 상
배터리, 고도, 속도, 방향, GPS 상태, 링크 상태, 임무 상태, 신호 세기

각 항목들은 확정이 아니고, 어떤 탈것인지에 따라 변경될 수 있음.

4분할 뷰와 똑같이 m 키를 누르면 위젯이 나타나도록 구현

chart.js ? 를 연동해서 여러 그래프나 원형 그래프 등을 구현

1차 테스트 : 차트가 언리얼 위젯으로 잘 작동하는지, 실시간으로 값과 차트가 변경되는지 테스트 (실제 트럭의 속도나 고도를 가져와서 사용하지 않아도 됨. 차트가 어떻게 작동하는지 확인하는것이 목적)

테스트 후

titan truck 에 간단한 조작 기능 (tanksim 프로젝트의 탱크 코드 참고) 을 적용해서 실제 작동 테스트

또는 tanksim 의 탱크를 titan 프로젝트로 추가시켜서 탱크에도 적용되는지 테스트
```
CanvasPanel (루트, 기본 생성됨)
└ Border  (배경 패널 — 검정 반투명 + 초록 테두리, 크기 약 360x230, 위치 좌상단)
  └ VerticalBox
    ├ TextBlock  "UAV 상태 정보"  (제목, 흰색/초록, Bold)
    ├ HorizontalBox  (1행 — 4칸)
    │  ├ Border "카드"  → VerticalBox: TextBlock("배터리") + Overlay[ RadialGaugeWidget(이름:BatteryGauge) + TextBlock(이름:BatteryPercentText, 중앙정렬) ] + TextBlock(이름:FlightTimeText)
    │  ├ Border "카드"  → VerticalBox: TextBlock("고도(ALT)") + TextBlock(이름:AltitudeText) + LineGraphWidget(이름:AltitudeGraph)
    │  ├ Border "카드"  → VerticalBox: TextBlock("속도(SPD)") + TextBlock(이름:SpeedText) + LineGraphWidget(이름:SpeedGraph)
    │  └ Border "카드"  → VerticalBox: TextBlock("방향(HDG)") + CompassWidget(이름:Compass) + TextBlock(이름:HeadingText)
    └ HorizontalBox  (2행 — 4칸)
       ├ Border "카드" → VerticalBox: TextBlock("GPS 상태") + TextBlock(이름:GpsFixText) + TextBlock(이름:GpsSatText)
       ├ Border "카드" → VerticalBox: TextBlock("링크 상태") + TextBlock(이름:LinkStatusText) + TextBlock(이름:LinkQualityText)
       ├ Border "카드" → VerticalBox: TextBlock("임무 상태") + TextBlock(이름:MissionStatusText) + TextBlock(이름:MissionWaypointText)
       └ Border "카드" → VerticalBox: TextBlock("신호 세기") + HorizontalBox[ Border×5 (이름: SignalBar1, SignalBar2, SignalBar3, SignalBar4, SignalBar5 — 높이를 6/10/14/18/22px로 점점 키워서 막대 느낌) ] + TextBlock(이름:SignalDbmText)
       ```