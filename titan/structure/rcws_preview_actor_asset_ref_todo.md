# RCWSPreviewActor 하드코딩 에셋 경로 정리 (TODO, 미착수)

- 작성일: 2026-08-11
- 대상: `Source/titan_example/UI/RCWSPreviewActor.h` / `.cpp`
- 상태: **아직 코드 수정 안 함 — 방법만 정리해둔 문서.** 나중에 착수할 때 이 문서 기준으로 진행.
- 계기: VS 로컬 윈도우 디버거로 실행 중 `ConstructorHelpers::FClassFinder<APawn>` 안에서
  `__debugbreak()`가 한 번 걸림(`ARCWSPreviewActor::ARCWSPreviewActor()`). 재현 안 됐고
  `BP_UGV_Vehicle` 블루프린트도 정상 컴파일 — 이번 건 자체는 핫리로드 타이밍 관련 일회성으로
  판단, 별도 조치 안 함. 다만 이 계기로 "하드코딩 경로가 패키징 때 문제되지 않냐"는 질문이
  나와서, 실제 위험도와 정리 방법을 문서로 남김.

## 1. 지금 상태가 실제로 위험한가?

**아니요 — 지금 코드는 이미 한 번 이 문제 때문에 고쳐진 상태다.**
`RCWSPreviewActor.h` 88~93번 줄 주석에 명시:

> "2026-07-29 packaging investigation — a raw string load has no reflected property behind
> it, so it silently dropped from the build)"

즉 예전엔 런타임에 `LoadObject`/`FSoftClassPath::TryLoadClass()`로 문자열 경로를 그냥
로드하는 방식이었고, 그건 **리플렉션 프로퍼티(UPROPERTY)가 뒤에 없어서 쿠커의 정적 의존성
추적이 이 참조 자체를 못 보고 패키징 때 조용히 빠뜨렸음**(에러 없이 그냥 빠짐 — 가장 나쁜
종류의 실패).

지금은 다음과 같이 이미 수정돼 있음:

```cpp
// RCWSPreviewActor.h
UPROPERTY(EditDefaultsOnly, Category = "RCWS Preview")
TSubclassOf<APawn> UGVVehicleClass;

UPROPERTY(EditDefaultsOnly, Category = "RCWS Preview")
TObjectPtr<USkeletalMesh> UGVSkeletalMeshAsset;
```

```cpp
// RCWSPreviewActor.cpp, 생성자 안
static ConstructorHelpers::FClassFinder<APawn> UGVVehicleClassFinder(
    TEXT("/Game/Vehicles/UGV/Blueprint/BP_UGV_Vehicle"));
if (UGVVehicleClassFinder.Succeeded())
{
    UGVVehicleClass = UGVVehicleClassFinder.Class;
}

static ConstructorHelpers::FObjectFinder<USkeletalMesh> UGVSkeletalMeshFinder(
    TEXT("/Game/Vehicles/UGV/SK_UGV.SK_UGV"));
if (UGVSkeletalMeshFinder.Succeeded())
{
    UGVSkeletalMeshAsset = UGVSkeletalMeshFinder.Object;
}
```

**진짜 UPROPERTY(리플렉션 프로퍼티)를 만들어두고, `ConstructorHelpers`는 그 프로퍼티의
"기본값"만 채워주는 용도로 쓰는 것 — 이게 Epic이 권장하는 정석 패턴**이다. 쿠커는 이
UPROPERTY에 실제로 뭐가 들어있는지(ConstructorHelpers가 채운 기본값이든, 블루프린트에서
수동으로 덮어쓴 값이든)를 보고 의존성을 따라가므로, 패키징 시 에셋이 빠질 위험은 없다.

## 2. 그럼 남는 문제는 뭔가?

`ConstructorHelpers::FClassFinder`/`FObjectFinder`에 박혀있는 **하드코딩된 문자열 경로**
자체는 여전히 약점이다:

- `/Game/Vehicles/UGV/Blueprint/BP_UGV_Vehicle`, `/Game/Vehicles/UGV/SK_UGV.SK_UGV` 두
  경로 문자열이 C++ 코드에 그대로 박혀있음.
- 나중에 이 에셋들을 다른 폴더로 옮기거나 이름을 바꾸면, 이 문자열은 **자동으로 안 따라감**
  (리다이렉터가 남아있는 동안은 `LoadObject`가 리다이렉터를 타고 찾아가긴 하지만, "Fix Up
  Redirects"로 리다이렉터를 정리하고 나면 이 하드코딩 문자열은 완전히 끊어짐).
- 끊어져도 **컴파일 에러가 안 남** — `.Succeeded()` 체크가 실패를 조용히 흡수하도록 짜여
  있어서, `UGVVehicleClass`/`UGVSkeletalMeshAsset`가 그냥 `None`이 된 채로 넘어감. 이 프리뷰
  액터가 조용히 아무것도 안 그리는 것 말고는 티가 안 남 — 발견이 늦어질 수 있음.

즉 "패키징에서 빠지는" 문제는 이미 해결됐고, 남은 건 "리소스 리네임/이동에 대한 내구성"
문제다.

## 3. 정리 방법 (착수 시 이 순서로)

**핵심 아이디어: C++ 생성자의 `ConstructorHelpers` 하드코딩 문자열을 완전히 제거하고, 그
대신 블루프린트 에디터의 "클래스 디폴트(Class Defaults)" 패널에서 직접 드래그&드롭으로
할당해둔다.** UPROPERTY 자체는 그대로 유지(이미 안전한 패턴이므로 안 건드림) — 값을
채우는 주체만 "C++ 생성자"에서 "에디터에서 사람이 한 번 지정"으로 옮기는 것.

1. **먼저 확인**: `ARCWSPreviewActor`를 상속한 블루프린트 서브클래스가 프로젝트에 이미
   있는지 콘텐츠 브라우저에서 검색(`search_subclasses` MCP 툴 또는 직접 검색). 레벨에
   배치된 인스턴스가 어느 클래스인지도 확인.
   - 있으면: 그 블루프린트를 열어서 클래스 디폴트에 `UGVVehicleClass`/
     `UGVSkeletalMeshAsset`를 `BP_UGV_Vehicle`/`SK_UGV`로 직접 할당.
   - 없으면(네이티브 `ARCWSPreviewActor`를 직접 레벨에 배치해서 쓰고 있다면): 새
     블루프린트(`BP_RCWSPreviewActor` 등)를 만들어 그 안에서 할당하고, 레벨의 기존
     인스턴스를 그 블루프린트로 교체하거나, 네이티브 클래스를 계속 쓸 거면 별도 방법 필요
     (아래 "대안" 참고).
2. `RCWSPreviewActor.cpp` 생성자에서 두 `ConstructorHelpers` 블록(`UGVVehicleClassFinder`/
   `UGVSkeletalMeshFinder`, `#include "UObject/ConstructorHelpers.h"`도 다른 용도로 안 쓰이면
   같이) 삭제.
3. 재빌드 후, 위 1번에서 값을 할당해둔 블루프린트(또는 네이티브 클래스 디폴트)로 프리뷰가
   여전히 정상 작동하는지 확인(RCWS 대시보드에 미니 터렛 프리뷰가 뜨는지).
4. `UGVVehicleClass`/`UGVSkeletalMeshAsset`가 `None`인 상태로 `BeginPlay`가 진행되는
   경우(할당을 깜빡한 경우) 조용히 넘어가지 않도록, `BeginPlay`나 `SyncTurretMesh` 진입부에
   `UE_LOG(Warning, ...)` 한 줄 추가 권장 — 지금은 실패가 완전히 무음이라 나중에 똑같은
   종류의 "왜 프리뷰가 안 나오지" 디버깅을 반복하게 됨.

**대안(1번에서 마땅한 블루프린트가 없고 새로 안 만들고 싶은 경우)**: 네이티브 C++ 클래스도
`UCLASS(Blueprintable)`이면 별도 애셋 없이 클래스 자체의 CDO를 코드로 건드릴 순 없지만,
언리얼 에디터의 "Class Defaults" 보기는 보통 블루프린트 애셋을 통해서만 노출된다 — 따라서
네이티브 클래스를 그대로 쓸 거면 결국 최소 한 개의 얇은 블루프린트 래퍼(로직 없이 디폴트값만
설정)를 만드는 게 제일 간단하다.

## 4. 하지 않기로 한 대안 (참고용)

`TSoftClassPtr<APawn>`/`TSoftObjectPtr<USkeletalMesh>`로 바꿔서 `BeginPlay`에서
비동기 로드하는 방법도 있지만, 이건 **일부러 안 씀** — 헤더 주석에 이미 그 이유가 적혀있음
("Hard reference ... rather than a runtime FSoftClassPath::TryLoadClass() string load").
소프트 레퍼런스는 로드 시점을 늦출 수 있는 대신, 쿠커가 "이 에셋이 반드시 필요하다"고
확신을 못 해서 Asset Manager 룰을 별도로 안 만들면 여전히 패키징에서 빠질 수 있는 유형의
문제라, 이번 프리뷰 액터처럼 "항상 켜져 있어야 하는 UI 요소"엔 안 맞음. 하드 레퍼런스 +
UPROPERTY 방식을 유지하고, 그 값을 채우는 주체만 C++에서 에디터로 옮기는 게 맞는 방향.
