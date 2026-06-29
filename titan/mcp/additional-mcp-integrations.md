# 추가 MCP 연동 후보 정리

UE + Claude Code 환경에서 연동할 만한 외부 MCP 서버 및 생성형 AI 툴 정리.

---

## 생성형 AI

### 이미지 / 텍스처 생성

| 서비스 | MCP 지원 | 특징 |
|---|---|---|
| **Replicate** | 공식 MCP 서버 있음 | Flux, SDXL 등 다양한 모델. 텍스처·컨셉 이미지 생성 |
| **fal.ai** | 공식 MCP 서버 있음 | 빠른 속도. Flux 계열 이미지 생성 |
| **Stability AI** | API (래핑 필요) | PBR 텍스처 특화 모델 있음 |

**UE 연동 가능 워크플로우:**
```
Claude → Replicate MCP로 이미지 생성
       → 이미지 파일을 Content 폴더에 저장
       → UE TextureTools로 임포트
       → MaterialTools로 머티리얼에 적용
```

### 3D 에셋 생성

| 서비스 | MCP 지원 | 특징 |
|---|---|---|
| **Meshy AI** | API (공식 MCP 없음) | 텍스트/이미지 → 3D 메시 (.fbx, .glb) |
| **Tripo3D** | API (공식 MCP 없음) | 고품질 3D 생성 |
| **Hyper3D** | API | 비슷한 3D 생성 계열 |

> 공식 MCP 서버는 없지만 REST API를 MCP로 래핑하는 커스텀 서버 구현 가능.

### 오디오

| 서비스 | MCP 지원 | 특징 |
|---|---|---|
| **ElevenLabs** | 공식 MCP 서버 있음 | 음성 합성 + SFX 생성. 게임 보이스오버·효과음 |
| **Suno / Udio** | API | 배경 음악 생성 |

---

## 개발 워크플로우

### 버전 관리

| 서비스 | MCP 지원 | 특징 |
|---|---|---|
| **GitHub** | 공식 MCP 서버 있음 | PR, 이슈, 브랜치 관리. Claude가 코드 작업과 씬 편집을 함께 처리 가능 |
| **Perforce** | 없음 | UE 대형 프로젝트 표준이지만 MCP 미지원 |

### 태스크 / 문서

| 서비스 | MCP 지원 | 특징 |
|---|---|---|
| **Notion** | 공식 MCP 있음 (Claude Code에 이미 등록됨, 인증 필요) | 기획 문서·태스크 |
| **Linear** | 공식 MCP 서버 있음 | 이슈 트래킹. 게임 버그·피처 관리 |
| **Jira** | 공식 MCP 서버 있음 | 엔터프라이즈 이슈 트래킹 |

### 웹 검색 / 문서 조회

| 서비스 | MCP 지원 | 특징 |
|---|---|---|
| **Brave Search** | 공식 MCP 서버 있음 | UE 공식 문서, 셰이더 레퍼런스 실시간 검색 |
| **Tavily** | 공식 MCP 서버 있음 | AI 특화 검색. 기술 문서 검색 품질 좋음 |

---

## 우선순위 추천

### 즉시 효과 (UE 내부 툴셋 추가 — `.uproject`만 수정)
1. `SemanticSearchToolset` — 에셋 찾기 편해짐
2. `AutomationTestToolset` — 테스트 자동화
3. `AnimationAssistantToolset` / `NiagaraToolsets` — 작업 영역에 따라

### 단기 (외부 MCP 서버 추가)
1. **GitHub MCP** — 코드·씬 작업 통합 관리
2. **Brave Search MCP** — 문서 검색 워크플로우
3. **Notion MCP** — 기획 문서 연동 (이미 연결 목록에 있으므로 인증만)

### 중장기 (생성형 AI 파이프라인)
1. **Replicate MCP** — 텍스처·컨셉 이미지 생성 → UE 임포트
2. **ElevenLabs MCP** — 보이스오버·SFX 생성 자동화
3. **Meshy/Tripo3D 래핑** — 3D 에셋 생성 파이프라인 (커스텀 구현 필요)

---

## 현황 요약 (2026-06)

MCP 생태계에서 게임 개발 특화 서버는 아직 성숙하지 않음.
공식 MCP 서버를 제공하는 생성형 AI는 Replicate, fal.ai, ElevenLabs 정도.
3D 생성 AI (Meshy, Tripo3D 등)는 MCP 미지원으로 래핑 구현이 필요함.
