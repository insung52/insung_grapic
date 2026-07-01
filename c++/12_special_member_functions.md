# C++ 특수 멤버 함수 (Special Member Functions)

---

## 1. 특수 멤버 함수 6가지

컴파일러가 자동으로 생성할 수 있는 함수들:

```cpp
class T {
public:
    T();                            // 기본 생성자
    ~T();                           // 소멸자
    T(const T&);                    // 복사 생성자
    T& operator=(const T&);         // 복사 대입 연산자
    T(T&&) noexcept;                // 이동 생성자       (C++11)
    T& operator=(T&&) noexcept;     // 이동 대입 연산자  (C++11)
};
```

아무것도 선언하지 않으면 컴파일러가 6개 모두 자동 생성.  
하나라도 직접 선언하면 나머지 일부의 자동 생성이 억제됨.

---

## 2. `= default` vs `{}`

### 동작은 같지만 의미가 다름

```cpp
// 빈 소멸자 — 사용자가 "직접 정의"한 것으로 간주
T::~T() {}

// = default — "컴파일러 기본 동작을 명시적으로 요청"
T::~T() = default;
```

### `{}` 사용 시 부작용

C++11부터 소멸자를 **직접 정의**(`{}`)하면 이동 연산자 자동 생성이 억제됨:

```cpp
class Foo {
public:
    ~Foo() {}   // 직접 정의
    // 이동 생성자, 이동 대입 → 자동 생성 안 됨
    // 복사 생성자, 복사 대입 → deprecated 방식으로 자동 생성
};

std::vector<Foo> v;
v.push_back(Foo{});  // 이동 대신 복사 발생 → 성능 손해
```

### `= default` 사용 시

```cpp
class Foo {
public:
    ~Foo() = default;  // 기본 동작 명시
    // 이동 생성자, 이동 대입 → 자동 생성 유지됨
};
```

### 인라인 최적화 차이

| | `~T() {}` | `~T() = default` |
|--|-----------|-----------------|
| 이동 연산 자동 생성 | ❌ 억제 | ✅ 유지 |
| 인라인 최적화 | ❌ 어려움 | ✅ 가능 |
| 의도 전달 | 불분명 | "기본 동작" 명시 |

---

## 3. `= delete`

함수 사용을 컴파일 타임에 금지:

```cpp
class Singleton {
public:
    Singleton(const Singleton&) = delete;            // 복사 금지
    Singleton& operator=(const Singleton&) = delete; // 복사 대입 금지
    Singleton(Singleton&&) = delete;                 // 이동 금지
    Singleton& operator=(Singleton&&) = delete;      // 이동 대입 금지
};

Singleton a;
Singleton b = a;  // 컴파일 에러
```

`= delete`는 `private`으로 숨기는 것보다 낫다 — 에러 메시지가 명확함.

---

## 4. Rule of Zero / Three / Five

### Rule of Zero (권장)

raw pointer를 직접 소유하지 말고 RAII 래퍼(`std::unique_ptr`, `std::vector` 등)를 사용하면 특수 멤버 함수를 하나도 정의할 필요가 없음.

```cpp
class Good {
    std::unique_ptr<Resource> res_;  // RAII — 소멸자/복사/이동 자동 처리
    std::vector<int> data_;
    // 특수 멤버 함수 전혀 불필요
};
```

### Rule of Three (C++03)

소멸자 / 복사 생성자 / 복사 대입 중 하나를 정의하면 나머지 둘도 정의해야 함.  
셋 중 하나가 필요하다는 건 raw pointer 직접 소유 등 비자명한 리소스 관리를 뜻하기 때문.

```cpp
class Buffer {
    char* data_;
    size_t size_;
public:
    ~Buffer() { delete[] data_; }                // 소멸자 정의
    Buffer(const Buffer& o);                     // 복사 생성자도 정의 필수
    Buffer& operator=(const Buffer& o);          // 복사 대입도 정의 필수
    // 안 하면 기본 복사(얕은 복사) → 이중 해제 발생
};
```

### Rule of Five (C++11)

Rule of Three + 이동 생성자 + 이동 대입까지 5개 모두 명시.

```cpp
class Buffer {
public:
    ~Buffer();
    Buffer(const Buffer&);
    Buffer& operator=(const Buffer&);
    Buffer(Buffer&&) noexcept;
    Buffer& operator=(Buffer&&) noexcept;
};
```

복사를 금지하고 이동만 허용하는 패턴 (소유권 이전 의미):

```cpp
class UniqueResource {
public:
    ~UniqueResource();
    UniqueResource(const UniqueResource&) = delete;
    UniqueResource& operator=(const UniqueResource&) = delete;
    UniqueResource(UniqueResource&&) = default;
    UniqueResource& operator=(UniqueResource&&) = default;
};
```

---

## 5. 이동 연산 자동 생성 억제 규칙

컴파일러가 이동 생성자/이동 대입을 자동 생성하지 **않는** 조건:

| 직접 선언한 것 | 이동 생성자 | 이동 대입 |
|--------------|------------|----------|
| 소멸자 `~T()` | ❌ 억제 | ❌ 억제 |
| 복사 생성자 | ❌ 억제 | ❌ 억제 |
| 복사 대입 | ❌ 억제 | ❌ 억제 |
| 이동 생성자 | (본인) | ❌ 억제 |
| 이동 대입 | ❌ 억제 | (본인) |

→ **소멸자를 `{}`로 정의하는 것만으로도 이동 연산이 없는 클래스가 됨.**  
→ `= default`로 명시하면 이동 연산 자동 생성 유지.

---

## 6. 실전 패턴

### 복사/이동 전부 막기 (싱글톤, 시스템 클래스)

```cpp
class Context {
public:
    Context(const Context&) = delete;
    Context& operator=(const Context&) = delete;
    Context(Context&&) = delete;
    Context& operator=(Context&&) = delete;
};
```

### 복사만 막고 이동 허용 (소유권 이전 가능 리소스)

```cpp
class PhysicsBody {
public:
    ~PhysicsBody();  // 리소스 해제
    PhysicsBody(const PhysicsBody&) = delete;
    PhysicsBody& operator=(const PhysicsBody&) = delete;
    PhysicsBody(PhysicsBody&&) = default;
    PhysicsBody& operator=(PhysicsBody&&) = default;
};
```

### 헤더/소스 분리 시 `= default` 위치

```cpp
// foo.h — 선언만
class Foo {
public:
    ~Foo();  // 정의는 .cc에
};

// foo.cc — = default 로 정의
Foo::~Foo() = default;
// → Foo의 멤버 타입 전체 정의가 .cc에서 보이므로
//   unique_ptr 등 불완전 타입 문제 없이 소멸자 생성 가능
```
