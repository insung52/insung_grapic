# Unreal Engine MCP × Claude Code 연동 가이드

## 개요

Unreal Engine의 MCP 플러그인이 **MCP 서버** 역할을 하고,
Claude Code가 **MCP 클라이언트**로 접속하는 구조.

```
Claude Code (MCP 클라이언트)
        ↕ HTTP  http://127.0.0.1:8000/mcp
UE 에디터 (MCP 서버 — ModelContextProtocol 플러그인)
```

---

## 세팅 방법

### 1. `.uproject`에 플러그인 추가

```json
{
  "Plugins": [
    {
      "Name": "ModelContextProtocol",
      "Enabled": true
    },
    {
      "Name": "EditorToolset",
      "Enabled": true
    }
  ]
}
```

- `ModelContextProtocol` — MCP 서버 본체 (필수)
- `EditorToolset` — 액터/씬/머티리얼 등 에디터 툴셋 (실질적인 작업 도구)

### 2. 에디터 환경설정

**Edit → Editor Preferences → Model Context Protocol**
- `Auto Start Server` 토글 ON

### 3. `.mcp.json` 생성

UE 에디터 콘솔(`~`)에서 실행:

```
ModelContextProtocol.GenerateClientConfig ClaudeCode
```

프로젝트 루트에 `.mcp.json` 자동 생성됨:

```json
{
  "mcpServers": {
    "unreal-mcp": {
      "type": "http",
      "url": "http://127.0.0.1:8000/mcp"
    }
  }
}
```

### 4. Claude Code 연결 확인

프로젝트 루트에서 Claude Code 실행 후:

```
/mcp
```

`unreal-mcp: ✔ Connected` 확인

---

## 주의사항

- `claude mcp add`로 수동 추가하면 **안 됨** — `.mcp.json`이 올바른 방법
- 서버 타입은 `http` (SSE 아님)
- 에디터가 실행 중이어야 서버가 동작함

---

## 활성화된 툴셋 목록 (EditorToolset 기준)

| 툴셋 | 기능 |
|---|---|
| `SceneTools` | 레벨 로드, 액터 배치/삭제, 아웃라이너 폴더 관리 |
| `ActorTools` | 액터 트랜스폼, 라벨, 컴포넌트 편집 |
| `BlueprintTools` | 블루프린트 생성·편집 |
| `MaterialTools` | 머티리얼·머티리얼 함수 생성·편집 |
| `MaterialInstanceTools` | 머티리얼 인스턴스 생성·파라미터 편집 |
| `AssetTools` | 프로젝트 에셋 조회·관리 |
| `ObjectTools` | UObject 프로퍼티 조회·수정 |
| `PrimitiveTools` | 프리미티브 지오메트리 컴포넌트 추가 |
| `StaticMeshTools` | 스태틱 메시 에셋 조회·편집 |
| `SkeletalMeshTools` | 스켈레탈 메시·본·소켓 편집 |
| `TextureTools` | 텍스처 에셋 작업 |
| `DataTableTools` | 데이터 테이블 생성·편집 |
| `CurveTableTools` | 커브 테이블 생성·편집 |
| `DataAssetTools` | 데이터 에셋 작업 |
| `StringTableTools` | 스트링 테이블 생성·편집 |
| `ProgrammaticToolset` | 여러 툴을 Python 스크립트로 묶어서 일괄 처리 |
| `EditorAppToolset` | 콘솔 변수, 뷰포트 카메라, PIE 제어 |
| `LogsToolset` | 출력 로그 읽기·로그 카테고리 상세도 제어 |
| `AgentSkillToolset` | AgentSkill 에셋 목록·읽기·생성·수정 |

---

## 엔진 내 추가 활성화 가능한 툴셋

`C:\Program Files\Epic Games\UE_5.8\Engine\Plugins\Experimental\Toolsets\` 아래에 있으며
`.uproject`에 플러그인 이름만 추가하면 바로 사용 가능.

| 플러그인 이름 | 용도 |
|---|---|
| `AutomationTestToolset` | 자동화 테스트 실행·결과 확인 |
| `AnimationAssistantToolset` | 애니메이션 편집 지원 |
| `NiagaraToolsets` | 나이아가라 파티클 시스템 |
| `PCGToolset` | 절차적 콘텐츠 생성 (PCG) |
| `SemanticSearchToolset` | 프로젝트 에셋 시맨틱 검색 |
| `StateTreeToolset` | AI 상태 트리 편집 |
| `AIModuleToolset` | AI 모듈 (비헤이비어 트리 등) |
| `GASToolsets` | Gameplay Ability System 관련 |
| `ConversationToolset` | 대화 시스템 |
| `AllToolsets` | 위 전부 한번에 활성화 |

---

## 참고 문서

- 공식 문서: https://dev.epicgames.com/documentation/unreal-engine/unreal-mcp-in-unreal-editor
