# GrapiBase 개발환경 설정 및 빌드 가이드

## 필수 도구 및 패키지 설치

운영체제별로 다음 필수 도구 및 패키지를 설치합니다.

### Windows

#### Git 설치
```bat
winget install -e --id Git.Git
```

#### Python 설치
```bat
winget install -e --id Python.Python.3.13
```

---

### Linux

다음 명령어를 통해 빌드에 필요한 패키지를 설치합니다.

#### 필수 공통 패키지 설치
```shell
sudo apt update
sudo apt install git cmake clang ninja-build
```

#### Filament 빌드용 패키지 설치
```shell
sudo apt install libglu1-mesa-dev libc++-dev libc++abi-dev libxi-dev libxcomposite-dev libxxf86vm-dev
```

#### GLFW 빌드용 패키지 설치
```shell
sudo apt install xorg-dev libwayland-dev libxkbcommon-dev wayland-protocols extra-cmake-modules
```

---

## SSH 키 설정 및 소스 코드 가져오기

소스 코드를 가져오기 전에 SSH 키 설정이 필요합니다.

### SSH 키 생성 및 등록

#### Windows

**명령 프롬프트**를 실행한 후, 다음 명령어를 사용하여 SSH 키를 생성합니다.
```bat
ssh-keygen
```

- 기본 경로(`C:\Users\<username>\.ssh\id_ed25519`)에 저장합니다.
- **Passphrase는 비워둔 채로 생성하는 것을 권장**합니다.

다음 명령어로 공개 키를 확인합니다.
```bat
type %USERPROFILE%\.ssh\id_ed25519.pub
```

브라우저에서 다음 주소로 접속하여 로그인한 뒤 키를 등록합니다.  
[https://code.grapicar.com/-/user_settings/ssh_keys](https://code.grapicar.com/-/user_settings/ssh_keys)

- **Add new key** → 복사한 키 붙여넣기 → **Add key**

### 소스 코드 가져오기

SSH 설정이 완료되면 다음 명령어를 사용하여 소스 코드를 가져옵니다.
```shell
git clone --recursive git@code.grapicar.com:engine-dev/grapi-base.git
```

---

## IDE 설정

### Visual Studio Code

#### Visual Studio Code 설치
```bat
winget install -e --id Microsoft.VisualStudioCode
```

#### MSBuild Tools 설치
```bat
winget install -e --id Microsoft.VisualStudio.2022.BuildTools
```

#### MSBuild Tools 구성
1. **Visual Studio Installer**를 실행합니다.
2. **Visual Studio BuildTools 2022** 옆의 **Modify** 버튼 클릭
3. **Desktop development with C++** 항목 선택 후 하단의 **Modify** 버튼 클릭

#### 프로젝트 열기 및 빌드
1. Visual Studio Code 실행
2. **File > Open Folder**로 `grapi-base` 폴더 열기
3. `Ctrl+Shift+X` → **C++** 확장 설치
4. 같은 방식으로 **CMake Tools** 확장 설치
5. `Ctrl+Shift+P` → **CMake: Select Configure Preset** 실행 후 원하는 Preset 선택
6. 하단의 **Build** 버튼 클릭

---

### Visual Studio 2022

1. Visual Studio 2022 실행
2. **Open a local folder**로 `grapi-base` 폴더 열기
3. 상단 툴바 Preset 드롭다운에서 원하는 Preset 선택
4. **Build > Build All** 클릭

---

## 빌드 스크립트 사용법

### Windows

`x64 Native Tools Command Prompt for VS 2022`를 실행한 후, 다음 명령어를 입력합니다.
```bat
build.bat [options] <build_type1> [<build_type2> ...]
```

### Linux

다음 명령어를 입력하여 빌드를 실행합니다.
```shell
./build.sh [options] <build_type1> [<build_type2> ...] [target]
```

### 빌드 스크립트 옵션

| 옵션 | 설명 |
|:-----|:-----|
| `-h` | 도움말 출력 |
| `-a` | 빌드 결과 압축 |
| `-c` | 빌드 디렉터리 정리 후 빌드 |
| `-f` | CMake 강제 재실행 |
| `-i` | 빌드 결과 설치 |
| `-p` | 빌드 플랫폼 지정 (`desktop`, `android`, `embedded`, `webgl`, `all`) |
| `-q` | Android ABI 지정 (`armeabi-v7a`, `arm64-v8a`, `x86`, `x86_64`, `all`) |

> `-p`, `-q` 옵션은 Linux 환경에서만 사용할 수 있습니다.

---

## 플랫폼별 빌드 방법 (Linux)

### Desktop

Desktop 빌드는 별도의 추가 설정 없이 다음 명령어로 바로 실행할 수 있습니다.
```shell
./build.sh release
```

---

### Android

Android 빌드를 하려면 Java , Android SDK, NDK 설치가 필요합니다. 다음 명령어를 순서대로 실행합니다.

```shell
sudo apt install openjdk-17-jdk
```

```shell
cd <your chosen parent folder for the Android SDK>
curl -OL https://dl.google.com/android/repository/commandlinetools-linux-14742923_latest.zip
unzip -q commandlinetools-linux-14742923_latest.zip -d android_sdk
cd android_sdk/cmdline-tools
mkdir latest
mv lib bin NOTICE.txt source.properties latest/
cd latest/bin
./sdkmanager --install "ndk;28.2.13676358"
```

NDK 설치가 완료되면 프로젝트 루트 디렉터리로 이동합니다.
```shell
cd <your GrapiBase project root>
```

Android SDK 경로를 환경 변수로 설정합니다.
```shell
export ANDROID_HOME=<your chosen home for the Android SDK>
```

설정 후 다음 명령어로 빌드를 실행합니다.
```shell
./build.sh -p android release
```

---

### WebGL

WebGL 빌드를 하려면 Emscripten SDK가 필요합니다. 다음 명령어를 순서대로 실행합니다.
```shell
cd <your chosen parent folder for the Emscripten SDK>
git clone https://github.com/emscripten-core/emsdk.git
cd emsdk
./emsdk install latest
./emsdk activate latest
source ./emsdk_env.sh
```

환경 설정 후 프로젝트 디렉터리로 이동하여 빌드를 실행합니다.
```shell
cd <your GrapiBase project root>
./build.sh -p webgl release
```

---

### Embedded

#### Renesas R-Car H3ULCB

첨부된 툴체인 설치 스크립트를 실행합니다.
**RCar:**
```shell
./poky-glibc-x86_64-core-image-weston-sdk-aarch64-h3ulcb-toolchain-3.1.11.sh
```
**TeleChips Dolpin:**
```shell
./TCC803x_Linux_IVI_YP3.1_1.0.0-tcc803x-toolchain-aarch64-opengl-wayland-ivi-x86_64-gcc-arm-9.2.sh
```

> 설치 중 경로 지정 프롬프트가 표시되며, 본 문서는 RCar 및 TeleChips Dolpin 보드 기준으로 작성되었습니다.

SDK에 포함된 CMake는 버전 3.16.5로, 본 프로젝트 최소 요구 버전(CMake 3.19)에 미달합니다. 다음 명령어로 비활성화합니다.
**RCar:**
```shell
sudo mv /opt/poky/3.1.11/sysroots/x86_64-pokysdk-linux/usr/bin/cmake /opt/poky/3.1.11/sysroots/x86_64-pokysdk-linux/usr/bin/cmake.bak
```
**TeleChips Dolpin:**
```shell
sudo mv /opt/poky-telechips-systemd/nodistro.0/sysroots/x86_64-oesdk-linux/usr/bin/cmake /opt/poky-telechips-systemd/nodistro.0/sysroots/x86_64-oesdk-linux/usr/bin/cmake.bak
```

환경 설정을 적용합니다.
**RCar:**
```shell
source /opt/poky/3.1.11/environment-setup-aarch64-poky-linux
```
**TeleChips Dolpin:**
```shell
source /opt/poky-telechips-systemd/nodistro.0/environment-setup-aarch64-telechips-linux
```

Embedded 빌드를 실행합니다.
```shell
./build.sh -p embedded release
```

빌드 도중 타겟 보드 선택 메뉴가 표시되며, 선택에 따라 빌드가 진행됩니다.