# 기동플랫폼용 지능형 지휘결심지원체계 — 상세설계 문서 데이터화

원본: `C:\working\insung_grapic\titan\documents\260420_UGV에뮬레이터_상세설계_v1.pdf`
(LIG넥스원 C4I연구소, 총 20p, 표지 "기본설계방향" / 자체투자 과제)

이 문서는 **이미지로만 존재해 텍스트 추출이 안 되는 페이지(3, 4, 5, 6, 11, 14, 15, 16, 17)를
직접 렌더링해서 읽고 데이터화한 결과**다. 나머지 페이지(1,2,7~10,12,13,18~20)는 PDF 텍스트
레이어가 정상 추출됨. **핵심 결론: 지금 `titan_example` 언리얼 프로젝트(듀얼 모니터 1대 PC)는
이 설계서가 그리는 시스템 중 "에뮬레이터 SW 두 종류"만 한 프로세스에 합쳐서 구현한 것이고,
실제 설계는 여러 대의 PC/서버가 네트워크로 분산된 멀티 컴퓨터 시스템이다.**

---

## 0. 왜 멀티 컴퓨터인가 — 노드 목록 요약

설계서에 등장하는 물리적으로 구분된 컴퓨팅 노드(문서 근거는 아래 각 절 참조):

| # | 노드 | 역할 | 스펙/연결 | 근거 |
|---|------|------|-----------|------|
| 1 | **UGV 에뮬레이터 구동 PC** | UGV 가상환경 시뮬레이터 (`titan_example`의 UGV 쪽에 대응) | Ryzen 9800X3D / RTX 5070Ti / DDR5 16G / 512G SSD, USB로 UGV 제어 조이스틱(TRUSTMASTER T-1600M FCS) 직결 | p.6 |
| 2 | **자체방호 에뮬레이터 구동 PC** | 자체방호(TitanTruck) 가상환경 시뮬레이터 | 동일 스펙, USB로 UAV/RCWS 조이스틱(제닉스 타이탄 GP5) 직결 | p.6 |
| 3 | **자체방호 콘솔** | 자체방호 PC의 디스플레이+입력 세트(운용자석) | HDMI(영상 in)+USB(조이스틱 out), PC와 로컬 직결로 보임 | p.16 |
| 4 | **MUM-T 통제콘솔 (UGV 원격통제기)** | UGV 원격 조종 콘솔 | **Ethernet**으로 UGV 에뮬레이터 PC와 분리 연결 (자체방호와 달리 네트워크로 떨어져 있을 수 있음) | p.17, p.3 |
| 5 | **운용통제기(넥스원)** | MUM-T 콘솔과 별도로 존재하는 운용 통제 장비 | Ethernet | p.17 |
| 6 | **운용서버** | 지능형지휘통제 SW 구동 | Xeon Silver 4410Y x2, DDR5 32G, 10GbE — 벤더: 모비젠 | p.14~15 |
| 7 | **GPU서버** | 상황인식/타격스케줄링/Object-to-Ontology 모델 추론 | Xeon Silver 4514Y x2, DDR5 64G, Quadro PRO5000 48GB x2 | p.14~15 |
| 8 | **빅데이터서버** | Data Link Processer & Storaging (Raw DB/Fabric 저장) | Xeon Silver 4410Y x2, HDD 8TB Raid5 x3 | p.14~15 |
| 9 | **가시화서버** | 전투통합지휘 SW 구동 | (스펙 표는 GPU/빅데이터/운용서버만 명시, 가시화서버 별도 스펙은 미기재) | p.14~15 |
| 10 | KVM스위치 / 이더넷스위치 / 서버랙 | 위 서버들을 하나의 지휘통제플랫폼 장치(트럭 내부)로 묶는 인프라 | — | p.14 |

즉 **최소 9대 이상의 물리 PC/서버**(에뮬레이터용 2대 + 콘솔/조이스틱 세트 2~3 + 서버 4대)가
네트워크(UDP·RTSP·Ethernet)로 얽혀 하나의 시연 시스템을 구성한다. 지금 프로젝트는 이 중
1번+2번(에뮬레이터 SW 둘)만 한 PC/한 프로세스에 몰아넣은 상태.

---

## 1. 시스템 전체 구성도 (p.3, "개발개요 – 구성도")

```
[2판교H 방산전용 클라우드]
        │  상부체계 탐지정보(SAR/EOTS/레이더/SIGINT), 기동플랫폼 탐지정보, 부대자산정보
        ▼
① 지능형 통합 지휘통제체계실  ←──────────────────────┐
   (AIMD 상황도: 위협도, 타격스케줄링, 부대자산 전시)  │ 상부체계 탐지정보 등 (양방향)
        │                                              │
        ▼                                              │
④ 기동형 지휘통제체계실 – 2판교H(야외, 트럭)  ─────────┘
   (다중 모니터 지휘석 + 서버랙)
        │  탐지정보/상태정보/주행정보/무장정보 ↑
        │  주행제어정보/임무정보(자율주행)/타격제어정보 ↓
        ▼
   UGV ← → UAV / 워리어플랫폼(점선=TBD, 미구현/향후 확장 대상)
```

- 클라우드(2판교H)는 **상위 지휘체계**와 **야외 기동형 지휘통제체계실**을 잇는 방산 전용
  클라우드 링크 — 이 프로젝트 범위 밖일 가능성이 높지만, "정보 전시"라는 인터페이스 지점이 있음.
- UAV·워리어플랫폼 박스는 점선 처리 — 현재는 TBD, UGV만 실선(개발 대상 확정).

## 2. SW 요구사항 명세 (p.4~5, "개발개요 – 구성도")

**주의: p.4와 p.5가 같은 요구사항 표(R-UGV-HMR/SFR/ETR)의 서로 다른 버전이다.**
p.4는 빨간 주석이 달린 검토용 마크업(취소선으로 삭제 표시된 항목 있음), p.5는 취소선 없는
표. 그런데 **p.4에서 삭제(취소선) 표시된 항목이 p.5에는 그대로 살아있어 두 버전이 서로
모순된다** — 실제 최신 확정본이 무엇인지는 LIG 측에 재확인 필요.

| 식별자 | 요구성능 | 검증방법 | 비고 |
|---|---|---|---|
| R-UGV-HMR-001 | 무인수색차량 시뮬레이터 제작 (가상환경에서 UGV 모의SW 구동 가능한 하드웨어 제공) | 검사 | |
| R-UGV-HMR-002 | 자기방호시스템 모형 제작 | 검사 | p.4에서 취소선+"TBD" 주석 (삭제 검토 대상), p.5엔 그대로 있음 |
| R-UGV-HMR-003 | 지휘통제 및 임무장비 모의기 하드웨어 제공 | 검사 | 빨간 글씨 강조 (신규/변경 항목으로 추정) |
| R-UGV-SFR-001 | 무인수색차량 가상 모의 SW 구축 (3D 렌더링 물리엔진 기반) | 시연 | |
| R-UGV-SFR-002 | 가상 차량 모델링 (기동형 지휘소 차량 1대 + 무인수색차량 1대 3D 모델링) | 시연 | |
| R-UGV-SFR-003 | 원격 사격 모의 기능 (지휘소 원격 사격명령 → 화염효과 모의) | 시연 | |
| R-UGV-SFR-004 | 주행 경로 설정 기능 (웨이포인트 설정 + 경로 전시) | 시연 | 빨간 글씨. p.4 주석: "시연 시나리오 동작용으로 목표점X(변수)까지 주행이 자동으로 되는 기능" |
| R-UGV-SFR-005 | 원격 제어 기능 (마우스/조이스틱 원격 제어) | 시연 | |
| R-UGV-SFR-006 | 차량 상태 정보 가시화 (속도/위치/자세) | 시연 | |
| R-UGV-SFR-007 | 차량 센서 모의 기능 (센서 구동 + 네트워크로 정보 전달) | 시연 | p.4에서 취소선+"삭제" 주석 |
| R-UGV-SFR-008 | 차량 인터페이스 처리 기능 (운용콘솔과 연동 ICD 반영, 이더넷 기반 제어정보 연동) | 시연 | |
| R-UGV-SFR-009 | 상황 및 환경 모델링 (산지/철책/나무/노지/장애물 3D 모델링, EO/IR 탐지 모의용 가상표적) | 시연 | |
| R-UGV-ETR-001 | 무인수색차량 시뮬레이션 환경 구축 (운용환경 구축/설치 지원) | 분석/검사 | |
| R-UGV-ETR-002 | 통합 테스트 | 분석/검사 | |
| R-UGV-ETR-003 | 소프트웨어 산출물 (SW요구사항명세서/SW상세설계서/통합기능시험결과서) | 분석/검사 | |

p.4 상단 라벨: "임무장비 모의기 (슈어소프트테크)" — 이 요구사항 표 전체가 **슈어소프트테크에
발주된 임무장비 모의기(에뮬레이터 SW) 요구사항**임을 시사. 즉 지금 프로젝트(titan_example)는
슈어소프트테크向 계약 요구사항의 사내/자체 구현 버전으로 보임.

## 3. 에뮬레이터 구동 PC 하드웨어 사양 (p.6)

### UGV 모의 SW 운용 장비
- **가상 차량 모델**: 가상환경에서 주행 가능한 기동형 지휘소 모델 + 무인수색차량 모델
- 무인차량에뮬레이터(MUM-T SW(UGV)) 사양: AMD Ryzen 9800X3D / DDR5 16GB / 512GB SSD /
  NVIDIA RTX 5070Ti / **UGV 제어 조이스틱: TRUSTMASTER T-1600M FCS**
- 연결: UGV 에뮬레이터 구동 PC —USB→ UGV 제어 조이스틱

### 자체방어 모의 환경 운용 PC
- **외부 감시 및 자기방호시스템 (예시 이미지 2종)** — 트럭 탑재형 자체방호 시스템
- 자기방호에뮬레이터(MUM-SW(자체방호)) 사양: 동일 CPU/RAM/Storage/GPU 구성,
  **UAV 제어 조이스틱: 제닉스 타이탄 GP5**
- 연결: 자체방어 에뮬레이터 구동 PC —USB→ UAV/RCWS 제어 조이스틱

→ **두 에뮬레이터는 설계상 별개의 PC 2대**로 나뉘어 있고, 각각 별도 조이스틱 모델까지
지정돼 있음. 지금 프로젝트가 한 PC 듀얼 모니터로 합쳐 돌리는 것과 명확히 다른 지점.

## 4. 지휘통제플랫폼 서버랙 구성 (p.14~15, "SW 탑제도")

```
지휘통제플랫폼 장치
├─ 운용서버        ── 지능형지휘통제 SW                     [벤더: 모비젠]
├─ GPU서버         ─┬ 상황인식 모델
│                    ├ 타격스케줄링 모델
│                    └ Object-To-Ontology 모델
├─ 빅데이터서버     ─┴ (위 3개 모델과도 연결) + Data Link Processer & Storaging [벤더: 모비젠]
├─ 무인차량에뮬레이터                                       [벤더: 슈어소프트테크]
├─ 자기방호 에뮬레이터                                      [벤더: 슈어소프트테크]
├─ 가시화 서버      ── 전투 통합지휘 SW
├─ 서버랙 / KVM스위치 / 이더넷스위치  (인프라)
└─ 원격통제장치     ─┬ MUM-T SW (자체방호)
                      └ MUM-T SW (UGV)
```

### 서버 HW 스펙

| 구분 | CPU | RAM | Storage | 기타 |
|---|---|---|---|---|
| 운용서버 | Xeon Silver 4410Y (12C, 3.90GHz/2.00GHz, 30MB, 150W) x2 | DDR5 32GB PC5-4800 ECC/REG x2 | 2.5" SSD SATA3 Samsung EVO 1.92TB(Raid1) x2, **[검토중] 3.5" HDD 8TB(Raid5) x3** | RAID PIKE II 3108-8i, 10GbE(Intel X710-AT2) Onboard |
| GPU서버 | Xeon Silver 4514Y (16C, 2.0GHz/3.4GHz, 30MB) x2 | DDR5 64GB PC5-5600 ECC/REG x4 | 2.5" SSD 1.92TB(Raid1) x2 + 3.84TB(Raid1) x2 | **NVIDIA Quadro PRO5000 48GB x2**, 10GBase-T(Intel X550) x1, 1Gb/s LAN(Intel I350-AM2) Onboard |
| 빅데이터서버 | Xeon Silver 4410Y x2 (동일) | DDR5 32GB x2 | 2.5" SSD 1.92TB(Raid1) x2 + **3.5" HDD 7200rpm 8TB(Raid5) x3** | RAID PIKE II 3108-8i, 10GbE(Intel X710-AT2) Onboard |

가시화서버는 다이어그램에만 존재, 별도 스펙표 없음(문서 내 미기재).

**모비젠 / 슈어소프트테크**: p.15 좌측 다이어그램에 "모비젠2"(운용서버·지능형지휘통제SW),
"모비젠1"(빅데이터서버·Data Link Processor&Storaging), "슈어1"(무인차량에뮬레이터),
"슈어2"(자기방호에뮬레이터) 라벨이 붙어 있음 — **모비젠이 지휘통제/데이터링크 SW,
슈어소프트테크가 UGV/자체방호 에뮬레이터 SW를 각각 외주/협력 개발**하는 구조로 추정.

## 5. UGV 원격통제기 프로토콜 (p.11, "체계구성품 – MUM-T 무인체계SW / UGV 원격통제기")

RemoteControl(원격통제기) ↔ UGV에뮬레이터 간 UDP 기반 시퀀스. **한 페이지에 다이어그램 3개**가
있음: (A) 연결 시퀀스 초안, (B) 연결 시퀀스(명명 규칙이 다른 버전), (C) 연결 완료 후 주기 통신.

### (A) 연결 시퀀스 — 좌측 다이어그램
```
Boot 완료
par
 ├─ loop [모든 연결될 때까지, 각 5s 타임아웃]
 │    RemoteControl --RTSP(5) 연결시도--> UGV에뮬레이터
 │    RemoteControl <--frame-- UGV에뮬레이터         (RTSP 스트림 5개: 카메라 영상)
 ├─ par [UDP binding]  (port: 8000, port: 8001)
 │    loop [성공할 때까지] bind port
 │    alt [bind 실패] → close socket → realolocate socket → [성공] ready
 └─ par [UGV Connection]  (port: 8001)
      loop [1Hz, 재부팅까지]
      alt [connect==false]
        RC --cmd:CMD_Connetion--> UGV
        RC --cmd:Request_Connetion--> UGV
        RC <--cmd:Response_Connection/UGV-- UGV
        RC <--cmd:Response_Connection/ADU-- UGV
      RC --cmd:CMD_Request_Bit--> UGV
      RC --cmd:Request_BIT--> UGV
      RC <--cmd:Response_BIT-- UGV
      RC <--cmd:Response_BIT_ADU-- UGV
```

### (B) 연결 시퀀스 — 중앙 다이어그램 (RC_/UGV_ 접두사 버전)
구조는 (A)와 동일(UDP binding: port 8000/8001, UGV Connection: port 8001)이나 **명령어 이름이
다름**:
```
alt [connect==false]
  RC --cmd:RC_Connetion--> UGV
  RC --cmd:RC_Connetion_ADU--> UGV
  RC <--cmd:UGV_Response_Connection/UGV-- UGV
  RC <--cmd:UGV_Response_Connection/ADU-- UGV
RC --cmd:RC_Request_BIT--> UGV
RC --cmd:RC_Request_BIT_ADU--> UGV
RC <--cmd:UGV_Response_BIT-- UGV
RC <--cmd:UGV_Response_BIT_ADU-- UGV
```

> ⚠️ **불일치 메모**: (A)는 `CMD_Connetion`/`Request_Connetion`, (B)는 `RC_Connetion`/
> `RC_Connetion_ADU` 식으로 명명 규칙이 다르다. (C)의 주기 통신은 `RC_`/`UGV_` 접두사를
> 쓰므로 (B) 쪽이 최종 명명 규칙에 더 가까워 보이지만, 문서 안에 확정판이 따로 없다.
> 실제 ICD(인터페이스 정의서)가 별도로 있는지 LIG 측에 확인 필요.

### (C) 연결 완료 후 주기 통신 — 우측 다이어그램 (port: 8000)
```
Connection Done
par
 ├─ loop [10Hz, connection false까지]
 │    RC <--cmd:UGV_Period_BasicInfo/UGV-- UGV
 │    RC <--cmd:UGV_Period_ObjectDetectionResult/ADU-- UGV
 │    RC <--cmd:UGV_Period_NavigationInformation/ADU-- UGV
 │    RC <--cmd:UGV_Period_ObjectDetectionResult/RCWS-- UGV
 └─ loop [20Hz, connection false까지]
      alt [Joystick DR(주행) mode]
        RC --cmd:RC_RemoteDriving--> UGV
        RC <--cmd:UGV_Period_BasicInfo/UGV-- UGV
      alt [Joystick RCWS mode]
        alt [Joystick 이벤트 발생]
          RC --cmd:RC_Movement--> UGV
          RC <--cmd:ACK_Movement/RCWS-- UGV
      RC <--cmd:Period_RCWS_Status/RCWS-- UGV
```

### RC_RemoteDriving 내부 로직 (p.11 좌측 상태도)
```
주행명령 (cmd: RC_RemoteDriving)
 └─ 제어권 설정? ─0→ 종료
     └─1→ 주행모드? ─STAY/EMERGENCY→ 종료
           └─REMOTE→ 기어상태? ─BACK→ 후진주행 (Acc=후진가속, Brake=감속)
                            └─FRONT→ 전진주행 (Acc=전진가속, Brake=감속)
```

### 포트/전송 요약
- **RTSP 스트림 x5**: 카메라 영상 (전/후/좌/우 + α), 별도 표준 포트
- **UDP 8000**: 실시간 제어(RC_RemoteDriving, RC_Movement) + 10~20Hz 주기 상태/탐지/항법정보
- **UDP 8001**: 연결(Connection)/BIT(Built-In Test) 핸드셰이크, 1Hz
- 세션마다 **UGV 본체(UGV)/자율주행유닛(ADU)/RCWS** 세 개의 응답 주체가 태그로 구분됨
  (`/UGV`, `/ADU`, `/RCWS`) — 즉 UGV 에뮬레이터 하나가 내부적으로도 UGV 본체, ADU(자율주행),
  RCWS 세 서브시스템을 시뮬레이션해서 각각 응답해야 함을 시사.

## 6. 데이터 흐름도 (DFD) — 두 플랫폼의 연결 방식 차이 (p.16~17)

### 자체방호 플랫폼 DFD (p.16)
```
자체방호 에뮬레이터 (PC: 센서모의SW / GUI SW / 지휘차량모의SW / 환경모의SW)
   --HDMI(영상)--> 자체방호 콘솔     [①모의시작 ②~⑧ 영상/데이터 전시]
   <--USB(조이스틱)-- 자체방호 콘솔  [⑤RCWS제어 ⑥RCWS화력제어 ⑦자체방호드론제어]
   --Ethernet--> Raw DB / Fabric --> 지능형지휘통제, 가시화 CSCI (기동 지휘통제 플랫폼)
```
→ 에뮬레이터 PC와 콘솔이 **HDMI/USB로 로컬 직결** (물리적으로 같은 위치, 케이블 거리 수준).

### MUM-T 지휘통제 플랫폼 DFD (p.17, UGV용)
```
MUM-T 에뮬레이터 (PC: 센서모의SW / 무인차량모의SW / 환경모의SW)
   --Ethernet--> MUM-T 통제콘솔        [전장정보/탐지/EO-IR/격발/타격효과 전시]
   <--Ethernet-- MUM-T 통제콘솔        [RCWS제어/화력제어/임무계획(way point)/원격주행제어]
   --Ethernet--> Raw DB / Fabric --> 지능형지휘통제, 가시화 CSCI (기동 지휘통제 플랫폼)
운용통제기(넥스원)  ← 별도 박스, MUM-T 통제콘솔과 나란히 존재
```
→ UGV 쪽은 에뮬레이터와 콘솔이 **Ethernet으로 네트워크 분리** — 자체방호(로컬 HDMI/USB)와
아키텍처가 다르다. 즉 **UGV 쪽만 진짜 "여러 컴퓨터가 네트워크로 통신"하는 시나리오**이고,
자체방호 쪽은 "한 PC + 로컬 콘솔"에 더 가까울 수 있음 — 다만 p.6에서는 두 에뮬레이터가 동일하게
별도 PC로 취급되므로, 최종적으로 자체방호도 원격 콘솔(Ethernet)로 갈 가능성을 열어두고
LIG 측에 확인이 필요.

## 7. 원격통제기 UI 상세설계 (p.7~10, p.12~13 — 텍스트 추출 정상, 요약만)

**UGV 원격통제기 – CSC1 원격운용통제 상세설계**
- CSC2 주행장비정보처리: UGV 주행영상(전/후/좌/우), UGV 상태정보(위치/속도/고도/배터리/
  총주행거리/운용모드), 원격주행제어신호처리(조향각/가감속), UGV 장비상태정보(카메라/주행제어/
  주행센서/RCWS 연결상태), 임무상황도시(경로), UGV 식별객체정보(bounding box: 사람/차량)
- CSC2 임무장비정보처리: 임무장비상태정보(RCWS), EO/IR·RCWS 영상정보(**RTSP**),
  임무장비제어명령(모션제어/발사제어/발사모드/조준제어/영상제어)

**자체방호통제기 (슈어소프트테크 솔루션 활용)**
1. 자유시점(항공뷰) 모드로 드론 영상 모사
2. 전/후/좌/우 CCD 카메라 모사
3. 조향 및 기타 원격제어 기능
4. 실시간 주행데이터 전시
5. RCWS 조작기능 모사
6. RCWS EO/IR 카메라 모사
7. RCWS 상태정보 모사 및 전시

## 8. 시나리오/일정 (p.18~20)

사용자 요청에 따라 18페이지 이후는 상세 데이터화 생략(이미 별도로 시나리오 정보 보유 중).
p.19에 전체 업무일정(개념설계→상세설계→체계통합→자체시연)이 워크스트림별로 정리돼 있다는
것만 참고용으로 기록.

---

## 9. 현재 프로젝트(titan_example)와의 갭 정리

| 설계서 요구 | 현재 구현 상태 |
|---|---|
| UGV 에뮬레이터 PC / 자체방호 에뮬레이터 PC — **물리적으로 별도 PC 2대**, 각자 조이스틱 | 한 PC의 듀얼 모니터로 통합 구현 |
| UGV 콘솔은 **Ethernet**으로 에뮬레이터 PC와 네트워크 분리, 자체방호 콘솔은 HDMI/USB 로컬 | 네트워크 분리 없음, 전부 인메모리 |
| UDP 8000/8001 프로토콜, RTSP x5 영상 스트리밍, RC_/UGV_/ADU/RCWS 태그 기반 메시지 체계 | 미구현 (프로토콜 레이어 없음) |
| 운용서버(지능형지휘통제 SW)/GPU서버(AI 모델 3종)/빅데이터서버(Raw DB·Fabric)/가시화서버(전투통합지휘) — **서버 4대** | 미구현 (해당 SW 자체가 LIG/모비젠 담당 영역일 가능성) |
| 지능형 통합 지휘통제체계실 ↔ 기동형 지휘통제체계실(2판교H, 야외 트럭) ↔ UGV/UAV/워리어플랫폼 3단 계층 | 미구현 |

다음 계획 수립 시 참고할 핵심 질문:
1. 서버랙 4종(운용/GPU/빅데이터/가시화 서버)의 SW는 우리 팀 범위인가, 모비젠 협력사 범위인가?
2. 프로토콜(p.11) 최종 확정본(ICD)이 이 PPT 밖에 별도로 존재하는가 — (A)/(B) 명명 불일치 해소 필요.
3. UGV·자체방호 두 에뮬레이터를 물리적으로 분리(PC 2대 + 네트워크)할지, 현재처럼 한 프로세스로
   유지하되 "네트워크 분리처럼 보이게" 만 시연할지 — 카덱스 전시회 시연 목적상 후자로도 충분할
   가능성 있음(확인 필요).
