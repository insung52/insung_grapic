# TankSim 작업 내역

> 기간: 2026-06-13 ~ 2026-06-19
> 담당: 000

---

## a) 낮/밤 시간 흐름 시뮬레이션

> 목표: 약 240초(4분) 주기로 낮과 밤이 자연스럽게 전환되는 시뮬레이션 구현

### 1차 시도 — DirectionalLight 방향 회전 ❌

태양 고도각을 실제처럼 회전시키는 방식 시도.
아티스트가 비주얼 품질 기준으로 고정해 둔 광원 각도가 있어 방향 변경 시 그래픽 퀄리티 저하 발생 → 폐기.

### 2차 시도 — 광원 방향 유지 + Intensity 조절 ⚠️

광원 방향은 아티스트 설정 그대로 유지한 채, `DirectionalLight`의 `Intensity` 값만 시간에 따라 변화시켜 낮/밤을 표현 → 일반 메시 기준 성공.

**문제**: Gaussian Splatting(LCC) 오브젝트는 `DirectionalLight`의 영향을 받지 않아 밤에도 밝은 상태 유지.

### 3차 시도 — Intensity + LCCActor Tint 동기화 ✅

`LCCActor`의 `Tint` 값을 `DirectionalLight Intensity`와 연동하여 함께 조절.

- **결과**: 일반 메시와 Gaussian Splatting 모두 낮/밤 전환 표현 성공
- **주기**: 10초 = 1시간 경과 → 240초(4분) = 24시간(하루) 순환

---

## b) VDB 이펙트 랙 최적화