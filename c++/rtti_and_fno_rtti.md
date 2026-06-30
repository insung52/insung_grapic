# C++ RTTI와 `-fno-rtti`

## RTTI란?

**RTTI (Runtime Type Information)** — 프로그램 실행 중에 객체의 실제 타입을 알 수 있게 해주는 C++ 언어 기능이다.

### 왜 필요한가

C++에서는 기반 클래스 포인터에 파생 클래스 객체를 담을 수 있다:

```cpp
Animal* a = new Dog();
```

컴파일러는 `a`를 `Animal*`로만 알고 있다. 런타임에 "이게 진짜 `Dog`야, `Cat`이야?"를 알아야 할 때가 있다:

```cpp
std::vector<Animal*> animals = { new Dog(), new Cat(), new Dog() };

for (Animal* a : animals) {
    // a가 Dog인지 Cat인지 컴파일 시점엔 모름 → 실행 중에 확인 필요 → RTTI
}
```

### 두 가지 언어 구문

C++ 표준에서 RTTI는 두 가지 언어 구문으로 표현된다:
- `dynamic_cast<T*>(ptr)` — 기반 클래스 포인터를 파생 클래스 포인터로 안전하게 변환. 실패 시 `nullptr` 반환
- `typeid(expr)` — 표현식의 런타임 타입을 나타내는 `std::type_info` 객체 반환

```cpp
class Animal { virtual ~Animal() {} };
class Dog : public Animal {};

Animal* a = new Dog();
Dog* d = dynamic_cast<Dog*>(a);  // RTTI 사용: 성공, d != nullptr
typeid(*a).name();               // RTTI 사용: "Dog" (구현체에 따라 다름)
```

### `dynamic_cast`를 안 쓰면 RTTI를 안 쓰는 건가?

**반만 맞다.**

`dynamic_cast`와 `typeid` 둘 다 쓰지 않으면 RTTI 기능을 직접 사용하지는 않는 것이다.

그러나 직접 사용 여부와 별개로, 컴파일러는 **virtual 함수가 있는 클래스마다 typeinfo 심볼을 자동으로 생성한다**:

```cpp
class Animal { virtual ~Animal() {} };
// → 컴파일러가 "typeinfo for Animal" 심볼을 바이너리에 자동 삽입
//   dynamic_cast를 쓰든 안 쓰든
```

`-fno-rtti`는 이 자동 생성을 막는 옵션이다.

따라서 **`dynamic_cast`를 한 번도 쓰지 않아도**, `-fno-rtti`로 컴파일된 클래스를 상속하면 typeinfo 심볼 참조가 발생해 링크 에러가 날 수 있다. 문서 하단의 실제 사례(`VulkanPlatformLinux`)가 정확히 이 케이스다.

### `dynamic`의 의미 — 동적 할당과의 혼동 주의

`dynamic_cast`의 "dynamic"과 동적 할당(`new`/`delete`)의 "dynamic"은 다른 개념이다:

| 용어 | 의미 | 시점 |
|---|---|---|
| **동적 할당** (`new Foo()`) | 힙에 메모리 공간 확보 | 런타임 |
| **`dynamic_cast`** | 타입 변환의 유효성을 검사하며 변환 | 런타임 |

둘 다 런타임에 일어나는 일이라 "dynamic"이라는 단어를 공유하지만, RTTI는 메모리 할당과 관계없다.

---

## 내부 동작: typeinfo 심볼

RTTI를 지원하기 위해 컴파일러는 각 클래스에 대한 **typeinfo 심볼**을 바이너리에 생성한다.

```
typeinfo for Animal    ← VTable과 함께 존재
typeinfo for Dog       ← typeinfo for Animal 을 참조
```

**키 함수(key function)** 규칙 (Itanium C++ ABI, Linux/macOS 기준):
- typeinfo 심볼은 해당 클래스의 **첫 번째 non-inline 가상 함수가 정의된 `.cpp` 파일**에서 생성된다
- 클래스에 non-inline 가상 함수가 없으면 typeinfo는 weak symbol로 여러 TU에 분산된다

```cpp
// Animal.h
class Animal {
    virtual void speak();  // 선언만 (non-inline)
};

// Animal.cpp  ← speak()의 첫 정의 → typeinfo for Animal이 여기 생성됨
void Animal::speak() { ... }
```

---

## `-fno-rtti` 플래그

`-fno-rtti`를 컴파일 옵션에 추가하면:
- typeinfo 심볼 **생성 안 함**
- typeinfo 심볼 **참조도 안 함**
- `dynamic_cast`, `typeid` 사용 시 **컴파일 에러** 발생
- 바이너리 크기 소폭 감소 (typeinfo 테이블 제거)

대형 엔진(Unreal Engine, filament 등)이 이 옵션을 사용하는 이유:
- 사용하지 않는 기능의 오버헤드 제거
- 자체 reflection 시스템을 구현해서 표준 RTTI 불필요

---

## RTTI 혼재 문제: 서로 다른 TU가 섞일 때

문제는 **RTTI on으로 컴파일된 코드**가 **RTTI off로 컴파일된 클래스를 상속**할 때 발생한다.

### 시나리오

```
ParentLib.cpp  (−fno-rtti로 컴파일)
  class Parent {
      virtual void foo();  // non-inline 가상 → typeinfo for Parent가 여기 생성되어야 함
  };                       // 그러나 -fno-rtti라 생성 안 됨
```

```
MyCode.cpp  (RTTI on으로 컴파일)
  class Child : public Parent { };
  // Child의 typeinfo가 Parent의 typeinfo를 참조 → 심볼 없음 → 링크 에러
```

링커 에러 메시지:
```
undefined reference to `typeinfo for Parent`
```

---

## grapi-base + filament에서 발생한 사례

상세 내용 → [`filament_v1.72.0_merge_report.md` 섹션 5-3](..\grapi-base\filament_v1.72.0_merge_report.md)

### 발생 배경

filament v1.72.0에서 Vulkan 플랫폼 코드가 리팩터링되었다 (커밋 `d52fb1f4f`).

**v1.71.x 이전**: Linux Vulkan 구현이 `VulkanPlatform` 하나 안에 static 메서드로 내장됨. `VulkanPlatformLinux`라는 별도 클래스가 없었다.

**v1.72.0 이후**: polymorphism 리팩터링으로 `VulkanPlatformLinux`가 독립 클래스로 분리됨.

```cpp
// 새로 생긴 VulkanPlatformLinux.h
class VulkanPlatformLinux : public VulkanPlatform {
    virtual ExtensionSet getSwapchainInstanceExtensions() const override;  // 선언만
    virtual SurfaceBundle createVkSurfaceKHR(...) const noexcept override; // 선언만
};

// VulkanPlatformLinux.cpp (새 파일, -fno-rtti로 컴파일됨)
// → getSwapchainInstanceExtensions()의 첫 정의 → typeinfo가 여기 생성되어야 함
// → 그러나 -fno-rtti → typeinfo for VulkanPlatformLinux 없음
```

### grapi-base context.cc의 영향

```cpp
// context.cc (RTTI on)
class BaseVulkanPlatform : public filament::backend::VulkanPlatformLinux {
    ...
};
// BaseVulkanPlatform의 typeinfo → VulkanPlatformLinux의 typeinfo 참조
// → undefined reference to typeinfo for VulkanPlatformLinux
```

**v1.71.x에서 문제가 없었던 이유**: `VulkanPlatformLinux` 클래스 자체가 없었고 `VulkanPlatform`만 있었다. `VulkanPlatform`은 헤더에서 정의되는 부분이 많아 typeinfo가 분산(weak) 처리되거나 링커가 암묵적으로 처리했던 것으로 보인다.

---

## 해결 방법 비교

### 방법 A: 문제 파일만 -fno-rtti (현재 적용)

```cmake
set_source_files_properties(src/grapi/base/context.cc
                            PROPERTIES COMPILE_FLAGS -fno-rtti)
```

- **장점**: 수정 범위 최소, 즉시 검증 완료
- **단점**: 향후 다른 파일에서 같은 패턴이 생기면 또 개별 처리 필요

### 방법 B: grapi-base 전체에 -fno-rtti

```cmake
# base/CMakeLists.txt
target_compile_options(grapi-base PRIVATE -fno-rtti)
```

**사전 확인 필요 사항**:

| 항목 | 상태 | 비고 |
|---|---|---|
| grapi-base 자체 코드의 `dynamic_cast` / `typeid` | **없음** | grep 확인 완료 |
| grapi-base 자체 TypeInfo 시스템 | **RTTI 무관** | DJB2 해시 + 포인터 체인으로 직접 구현 |
| JoltPhysics | **없음** | C 스타일 |
| sol2 | **지원** | `SOL_NO_RTTI` / `__GXX_RTTI` 자동 감지로 RTTI-free 경로 선택 |
| harfbuzz / freetype | **없음** | C 라이브러리 |
| thorvg | **없음** | |

기술적으로 grapi-base 전체에 `-fno-rtti`를 걸어도 현재 코드 기준으로는 문제가 없을 것으로 예상된다. 단, 적용 후 전체 리빌드 및 샘플 실행 테스트로 검증이 필요하다.

> 권고: 이번 v1.72.0 머지 MR과 분리하여 별도 클린업 커밋으로 진행할 것.
