# SDL / X11 / ImGui — 역할과 관계

## 각 라이브러리의 위치

```
┌─────────────────────────────────────────────┐
│                  ImGui                      │
│  버튼, 슬라이더, 텍스트박스 등 UI 위젯 그리기 │
│  자체 창 없음 — 아래 레이어에 올라탐          │
└─────────────────────────────────────────────┘
┌─────────────────────────────────────────────┐
│                  SDL                        │
│  OS에서 창 생성, 키보드/마우스 입력 수집      │
│  OpenGL 컨텍스트 생성 및 화면 스왑           │
│  플랫폼 추상화 (Win32 / X11 / Wayland 등)   │
└─────────────────────────────────────────────┘
┌─────────────────────────────────────────────┐
│       OS 창 시스템                          │
│  Windows: Win32 (HWND)                     │
│  Linux:   X11 (Window) / Wayland           │
│  macOS:   Cocoa (NSWindow)                 │
└─────────────────────────────────────────────┘
```

---

## SDL (Simple DirectMedia Layer)

게임/멀티미디어 앱에서 OS별 창 시스템, 입력, 사운드, OpenGL 컨텍스트를 **단일 API**로 다룰 수 있게 해주는 C 라이브러리다.

```cpp
// SDL 없이 Linux에서 창 → X11 API 직접 호출해야 함 (수십 줄)
// SDL 있으면:
SDL_Window* win = SDL_CreateWindow("제목", x, y, w, h, flags);
SDL_GLContext ctx = SDL_GL_CreateContext(win);  // OpenGL 컨텍스트 연결
SDL_GL_SwapWindow(win);                         // 렌더 완료 후 화면 반영
```

SDL은 **창 관리와 이벤트 루프**를 담당한다. 화면에 뭔가를 직접 그리지는 않는다. 그리기는 OpenGL(또는 Vulkan)이 한다.

---

## ImGui (Dear ImGui)

OpenGL 같은 그래픽 컨텍스트 위에 UI 위젯을 그려주는 라이브러리다. **자체 창이 없다** — 창은 SDL이 만들고, ImGui는 그 창 안의 OpenGL 컨텍스트에 픽셀을 채운다.

```cpp
// ImGui 사용 흐름 (ai_studio.cc 기준)

// 1. SDL이 창과 OpenGL 컨텍스트 만들기
g.winUI = SDL_CreateWindow("Panel", ..., SDL_WINDOW_OPENGL);
g.glCtx = SDL_GL_CreateContext(g.winUI);

// 2. ImGui 초기화 — SDL 창과 OpenGL 컨텍스트 연결
ImGui_ImplSDL2_InitForOpenGL(g.winUI, g.glCtx);
ImGui_ImplOpenGL3_Init("#version 130");

// 3. 매 프레임 — SDL이 이벤트 주면 ImGui에 전달
ImGui_ImplSDL2_ProcessEvent(&ev);

// 4. ImGui가 UI 위젯 정의 (실제 그리기는 아직)
ImGui::Button("클릭");
ImGui::SliderFloat("값", &v, 0, 1);

// 5. OpenGL로 실제 출력
ImGui_ImplOpenGL3_RenderDrawData(ImGui::GetDrawData());
SDL_GL_SwapWindow(g.winUI);
```

ai_studio.cc에서 SDL은 창 두 개(3D 뷰 + ImGui 패널)를 모두 관리하고, ImGui는 패널 창 안에 로그/입력 UI를 그린다.

---

## X11

Linux에서 GUI 창을 화면에 표시하는 **디스플레이 서버 프로토콜**이다. Windows의 Win32, macOS의 Cocoa에 해당하는 역할이다.

```
앱이 "창 만들어줘" 요청
  → X11 서버가 받아서
  → 모니터에 실제로 창 표시
  → 키/마우스 입력을 앱에 돌려줌
```

X11은 1984년 MIT에서 만들어진 오래된 프로토콜이다. 네트워크 투명성(원격 디스플레이)이 특징이다. 최근엔 **Wayland**가 더 현대적인 대체재로 등장해서 주요 Linux 데스크탑(GNOME, KDE)이 Wayland로 전환 중이다.

### 네이티브 핸들이 왜 필요한가

filament(Vulkan 백엔드)는 화면에 렌더링하려면 OS가 관리하는 창의 실제 핸들이 필요하다. SDL은 `SDL_SysWMinfo`를 통해 이 네이티브 핸들을 노출한다:

```cpp
SDL_SysWMinfo wmi;
SDL_GetWindowWMInfo(win, &wmi);

// Linux (X11): wmi.info.x11.window → X11 Window 핸들 (정수 ID)
// Windows:    wmi.info.win.window  → HWND
```

filament는 이 핸들을 받아서 Vulkan Surface (`VkSurfaceKHR`)를 생성한다. Surface는 "이 창에 GPU가 직접 그릴 수 있는 연결"이다.

---

## filament 번들 SDL의 특이점 (`SDL_config.h`)

filament는 SDL2를 직접 번들링(`third_party/libsdl2`)하면서 `SDL_config.h`를 커스터마이징했다. Linux에서 어떤 창 시스템을 쓸지를 **빌드 define**으로 선택하게 되어 있다:

```cpp
// filament/third_party/libsdl2/include/SDL_config.h
#elif defined(__LINUX__)
    #if defined(FILAMENT_SUPPORTS_WAYLAND)
        #include "SDL_config_linux_wayland.h"   // Wayland 전체 기능
    #elif defined(FILAMENT_SUPPORTS_X11)
        #include "SDL_config_linux_x11.h"        // X11 전체 기능
    #else
        #include "SDL_config_minimal.h"           // 최소 기능만 (X11 없음)
    #endif
```

`FILAMENT_SUPPORTS_X11`이 없으면 minimal config가 선택되고, 이 경우 `SDL_VIDEO_DRIVER_X11`가 정의되지 않는다. `SDL_syswm.h`의 `SDL_SysWMinfo` 구조체에서 `info.x11` 멤버가 조건부로 제외된다:

```cpp
// SDL_syswm.h
struct SDL_SysWMinfo {
    union {
#if defined(SDL_VIDEO_DRIVER_X11)    // ← 이 define 없으면
        struct { Display* display; Window window; } x11;  // ← 멤버 없음
#endif
    };
};
```

→ `wmi.info.x11.window` 참조 시 컴파일 에러 발생.

이 문제는 `samples/script/CMakeLists.txt`의 ai_studio 타겟에 define을 추가해서 해결한다:

```cmake
if(GRAPI_USE_WAYLAND)
    target_compile_definitions(ai_studio PRIVATE FILAMENT_SUPPORTS_WAYLAND)
else()
    target_compile_definitions(ai_studio PRIVATE FILAMENT_SUPPORTS_X11)
endif()
```

관련 수정 상세 → [`filament_v1.72.0_merge_report.md` 섹션 5-4](..\grapi-base\filament_v1.72.0_merge_report.md)
