# C++ 예외 처리 (Exception Handling)

---

## 1. 예외란?

**예외(exception)** 는 프로그램 실행 중 정상 흐름을 중단시키는 오류 상황.  
C++은 예외를 **객체로 던지고(throw)** → **잡아서(catch)** 처리하는 메커니즘을 제공한다.

```cpp
void divide(int a, int b) {
    if (b == 0) throw std::runtime_error("division by zero");  // 던짐
    return a / b;
}

int main() {
    try {
        divide(10, 0);
    } catch (const std::runtime_error& e) {   // 잡음
        std::cerr << e.what();
    }
}
```

---

## 2. try / catch / throw 기본 구조

```cpp
try {
    // 예외가 발생할 수 있는 코드
    risky_operation();
} catch (const std::runtime_error& e) {
    // runtime_error 또는 그 파생 클래스만 처리
} catch (const std::exception& e) {
    // std::exception 계열 전부 처리
} catch (...) {
    // 모든 예외 처리 (타입 불문)
}
```

- `catch` 블록은 위에서부터 순서대로 매칭. 파생 클래스를 먼저 써야 함.
- `catch (...)` 는 어떤 타입이든 잡음. 마지막에 써야 함.

---

## 3. "예외를 삼킨다" (Swallowing)

**예외를 삼킨다** = `catch`로 예외를 잡은 뒤 **아무것도 안 하고 버리는 것**.

```cpp
try {
    risky();
} catch (...) {
    // 아무것도 안 함 → 예외가 여기서 소멸
}
// 코드는 계속 실행됨
```

예외 객체가 `catch` 블록 안에서 소멸되고, 이후 코드는 마치 아무 일도 없었던 것처럼 계속 실행된다.

### 비교: 삼키기 vs 다시 던지기

```cpp
// 삼키기 — 예외를 여기서 끝냄
catch (...) {}

// 다시 던지기(rethrow) — 상위 호출자에게 전달
catch (...) {
    log_error();   // 로그는 남기고
    throw;         // 동일한 예외를 다시 던짐
}

// 변환해서 던지기
catch (const std::runtime_error& e) {
    throw std::logic_error(e.what());  // 다른 타입으로 포장해서 던짐
}
```

### 언제 삼키는 게 맞나?

| 상황 | 이유 |
|------|------|
| **소멸자** | 소멸자에서 예외가 탈출하면 `std::terminate`. 삼킬 수밖에 없음 |
| **스레드 최상위** | 스레드에서 uncaught 예외 → 프로그램 종료. `catch`로 보호 필요 |
| **콜백/플러그인 경계** | C API 콜백으로 예외를 넘기면 UB. 경계에서 반드시 삼켜야 함 |

**일반 로직에서는 삼키면 안 됨.** 버그를 조용히 숨기게 된다.

---

## 4. noexcept

`noexcept` = "이 함수는 예외를 던지지 않겠다"는 계약.

```cpp
void safe_op() noexcept {
    // 이 안에서 예외가 던져지면 std::terminate() 호출
}
```

### 소멸자와 noexcept

**C++11부터 소멸자는 암묵적으로 `noexcept`.**

```cpp
class Foo {
public:
    ~Foo() {  // noexcept(true) 가 기본
        throw std::runtime_error("oops");  // → std::terminate() 호출!
    }
};
```

소멸자에서 예외가 탈출하면 `terminate`가 불리는 이유가 이것이다.  
`noexcept(false)`로 명시하면 예외를 던질 수 있지만, 그 소멸자는 스택 언와인딩 중 호출되면 여전히 `terminate`를 부른다.

### noexcept 조건부

```cpp
template<typename T>
void swap(T& a, T& b) noexcept(noexcept(T(std::move(a)))) {
    // T의 이동 생성자가 noexcept인 경우에만 이 함수도 noexcept
}
```

---

## 5. std::terminate

예외가 처리되지 못하면 `std::terminate()`가 호출되어 프로그램이 즉시 종료된다.  
기본 핸들러는 `std::abort()`를 호출 (스택 언와인딩 없이 죽음).

### 언제 terminate가 불리나

```
1. noexcept 함수에서 예외 탈출
2. 소멸자에서 예외 탈출 (암묵적 noexcept)
3. main()에서 잡히지 않은 예외
4. 스레드에서 잡히지 않은 예외
5. 두 예외가 동시에 활성화 (스택 언와인딩 중 소멸자가 예외 던짐)
```

### 소멸자 + 스택 언와인딩 이중 예외

```cpp
struct Dangerous {
    ~Dangerous() {
        throw std::runtime_error("from destructor");  // ← 위험
    }
};

void foo() {
    Dangerous d;
    throw std::logic_error("original");   // ① 첫 번째 예외 발생
    // ② 스택 언와인딩 중 d.~Dangerous() 호출
    // ③ 두 번째 예외 발생 → std::terminate()
}
```

---

## 6. 예외 안전성 보장 수준

함수가 예외 발생 시 객체 상태를 얼마나 보장하는지의 수준.

| 수준 | 설명 |
|------|------|
| **nothrow guarantee** | 절대 예외를 던지지 않음. `noexcept` 함수. |
| **strong guarantee** | 예외 발생 시 상태가 함수 호출 전으로 완전히 복원됨 (커밋/롤백). |
| **basic guarantee** | 예외 발생 시 객체가 유효한 상태를 유지하지만, 어떤 상태인지는 보장 안 함. |
| **no guarantee** | 예외 발생 시 객체가 손상될 수 있음. 피해야 함. |

```cpp
// strong guarantee 예시 — copy-and-swap 패턴
MyClass& operator=(const MyClass& rhs) {
    MyClass tmp(rhs);      // ① 복사 (실패하면 tmp만 손상, this는 안전)
    swap(*this, tmp);      // ② noexcept인 swap으로 교환
    return *this;
}
```

---

## 7. 표준 예외 계층

```
std::exception
├── std::runtime_error     — 런타임 오류
│   ├── std::range_error
│   ├── std::overflow_error
│   └── std::underflow_error
├── std::logic_error       — 프로그램 논리 오류
│   ├── std::invalid_argument
│   ├── std::out_of_range
│   └── std::length_error
└── std::bad_alloc         — 메모리 할당 실패 (new 실패)
```

직접 예외 클래스를 만들 때는 `std::exception`을 상속:
```cpp
class MyError : public std::runtime_error {
public:
    explicit MyError(const std::string& msg) : std::runtime_error(msg) {}
};
```

---

## 8. 실전 패턴

### 소멸자에서 예외 처리

소멸자 밖으로 예외가 나가면 `std::terminate`. 반드시 `catch`로 막아야 함.  
단, catch 블록 안의 로깅 자체가 예외를 던지면 안 됨.

```cpp
Foo::~Foo() {
    try {
        cleanup();
    } catch (const std::exception& e) {
        // utils::slog의 operator<<는 전부 noexcept → 소멸자 안에서 안전
        utils::slog.e << "~Foo cleanup failed: " << e.what() << utils::io::endl;
    } catch (...) {
        utils::slog.e << "~Foo cleanup failed: unknown exception" << utils::io::endl;
    }
}
```

**로깅 방법별 안전도**:

| 방법 | 안전도 | 이유 |
|------|--------|------|
| `utils::slog.e <<` | ✅ 안전 | Filament의 `operator<<`가 전부 `noexcept` 선언 |
| `fprintf(stderr, ...)` | ✅ 안전 | C 함수, 예외 없음 |
| `std::cerr <<` | ⚠️ 보통 안전 | 기본적으로 예외 안 던지지만 설정에 따라 다름 |
| 로그 파일 open/write | ❌ 위험 | 메모리 할당, 파일 IO → 예외 가능 |

### C API 콜백 경계

```cpp
// C 콜백으로 등록되는 함수 — 예외가 C 코드로 넘어가면 UB
extern "C" void my_callback(void* ctx) {
    try {
        static_cast<MyClass*>(ctx)->handle();
    } catch (...) {
        // 반드시 삼켜야 함
    }
}
```

### RAII로 예외 안전 보장

```cpp
// 예외가 어디서 나와도 File이 자동으로 닫힘
void process() {
    std::ifstream file("data.txt");   // RAII — 소멸자에서 close()
    parse(file);                      // 예외가 나와도 file은 정상 종료
}
```

---

## 9. 예외 vs 에러 코드

| | 예외 | 에러 코드 |
|--|------|---------|
| **성능** | 예외 발생 시 비용 큼 (zero-cost는 정상 경로만) | 매 호출마다 소량의 오버헤드 |
| **무시 가능성** | 잡지 않으면 terminate (강제) | 반환값 무시 쉬움 (버그 원인) |
| **중첩 호출** | 여러 계층을 건너 전달 가능 | 모든 계층에서 전달 코드 필요 |
| **C 호환** | C 코드 경계에서 위험 | C와 완전 호환 |
| **사용 권장** | 예외적인 상황 (파일 없음, 네트워크 오류) | 자주 발생하는 흐름 제어 |
