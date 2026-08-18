# RTSP 송출 PoC — 진행 현황 (1단계)

**상태: 1단계 목표 달성 — 단일 스트림 + 7-스트림 동시 송출 모두 성공 확인(사용자 확인,
2026-08-07). §1.22의 프레임 타임스탬프 수정(`FRtspStreamState::NextPtsNs` 기반 명시적
PTS/DTS/DURATION)까지 반영한 뒤 VLC에서 연결·재연결·재생(큐브 회전 포함) 전부 정상
동작. 이어서 §6.1의 7-스트림 동시 재생 테스트도 통과 — VLC 7개 전부 끊김 없이 재생,
UE 프레임레이트 70+ 유지, 체감 부하 거의 없음. §1.9~§1.22에 걸쳐 다뤘던 컴파일 이슈,
D3D12/NVENC RHI 크래시, RTSP 재연결 레이스, 키프레임 타이밍, 프레임 페이싱, RTP
타임스탬프 문제가 모두 해결된 상태.

**다음 단계**: §9 참고 — 이 PoC의 남은 일은 §8(프로덕션 패키징: GStreamer DLL 배포,
RTSP URL 스킴/포트 확정, 실제 UGV/자체방호축 카메라 연결)로, 우선순위는 사용자와 상의
후 진행.

**추가 트랙(2026-08-14~): 크로스플랫폼(Windows+Linux) 지원 — §10 참고.** WSL2로 NVENC/
GStreamer 레이어는 Phase 0에서 검증 완료. **Phase 1(빌드 시스템 크로스플랫폼화)도 완료
및 검증됨** — Build.cs/uplugin/모듈 크로스컴파일 지원을 작성한 뒤, 실제 컴파일 에러
2라운드(D3D12 전용 파일이 Linux 빌드에도 끼어들던 문제, 벤더 코드의 초기화 순서 버그,
파일 이동 후 self-include 경로 누락)를 거쳐 **Windows 빌드 + Linux 패키징(플러그인
포함 확인됨) 둘 다 성공**(2026-08-14, §10.2.1). **Phase 2(렌더-인코더 Vulkan/CUDA
재구현)도 작성 완료**(2026-08-14, §10.3) — `IRtspFrameEncoder` 인터페이스 도입,
`FNvencVulkanEncoder`(NvEncoderCuda + Vulkan `VK_KHR_external_memory` 브릿지) 신규 구현,
`RtspFrameEncoderFactory`로 런타임 RHI 분기. **컴파일은 두 플랫폼 다 통과 확인됨**
(2026-08-15, §10.3.1 — Windows 빌드/Linux 패키징 둘 다 성공, 몇 라운드의 실제
컴파일 에러 수정 거침: Build.cs 스코프 실수, **UE의 Vulkan 헤더가 `VK_NO_PROTOTYPES`라
core 함수를 정적 링크로 못 씀**을 뒤늦게 발견해서 전부 동적 로드로 교체, CUDA 13.3의
`cuCtxCreate_v4` 시그니처 변경 등). **런타임 동작은 여전히 전혀 검증 안 됨** — 확장
등록 타이밍, SceneCapture의 실제 Vulkan 레이아웃 등 실제 하드웨어 없이는 확인
불가능한 가정들이 여러 개 그대로 남아있음(§10.3에 나열, 컴파일 성공이 이걸 검증해주진
않음). Vulkan RHI 렌더링 자체의 검증도 WSL2에서 불가능해서(Phase 0) 원격 우분투 박스
몫으로 남음(Phase 4) — 다음 단계는 원격 박스에서 실제 스트리밍 확인.

이 세션은 `titan_example`을 빌드하지 않는다는 스탠딩 룰(사용자가 직접 빌드) 때문에
UBT/Build.bat를 실행하지 않았습니다. 아래는 실제로 작성된 플러그인 코드와, 그동안 겪고
해결한 이슈들의 기록입니다.

작업 위치: `C:\working\works\kadex\titan_example\Plugins\RtspEncoder\` (새 플러그인, 기존
QuadCamModule/GenesisOSCBridge/JoystickPlugin 등 다른 트랙은 건드리지 않음).

---

## 0. §7 대비 바뀐 점 — CUDA 안 씀

`protocol_icd.md` §7엔 "CUDA-D3D11 interop"라고 적혀 있는데, 실제로는 **CUDA를 전혀 쓰지
않습니다.** 이유:

- `titan_example`의 `DefaultEngine.ini`가 `DefaultGraphicsRHI_DX12`로 설정되어 있어서, UE가
  실제로 렌더링하는 텍스처는 `ID3D12Resource`입니다 (D3D11 아님).
- NVIDIA Video Codec SDK 13.1.15엔 `NvEncoderD3D12` (D3D12 텍스처를 NVENC에 직접 먹이는
  공식 래퍼)가 이미 있어서, D3D12 → D3D11 브리지나 CUDA interop 없이 **D3D12 리소스를 그대로
  NVENC에 넘기는 경로**로 갔습니다. UE의 `ID3D12DynamicRHI` 인터페이스(엔진이 정확히 이런
  외부 인코더 연동을 위해 제공하는 API — `RHIGetResource`, `RHIGetGraphicsCommandList`,
  `RHISignalManualFence`)를 그대로 활용.
- 그 결과 CUDA Toolkit은 **설치는 했지만 실제 코드에서 링크도 include도 안 함** —
  Build.cs를 보면 `d3d12.lib`/`dxgi.lib`/`nvencodeapi.lib`/GStreamer 라이브러리만 링크하고
  CUDA 관련 lib는 없습니다. 미리 알았으면 설치 안 시켜도 됐을 항목인데, SDK 실제 내용
  확인은 이 세션에서 설치 끝난 뒤에야 했습니다 — 죄송합니다. 지워도 무방하지만 굳이 지울
  필요도 없음(다른 용도로 쓸 수도 있고).
- `protocol_icd.md` §7의 "CUDA-D3D11 interop" 문구는 실제 구현과 달라졌으니, 문서를
  업데이트할 거면 "UE NVENC D3D12 네이티브 인코드(NvEncoderD3D12, zero GPU-copy 아님이지만
  zero CPU-copy) → gst-rtsp-server appsrc"로 고치는 게 맞습니다.

"Zero-copy"의 정확한 의미: **CPU/PCIe 왕복이 없다**는 뜻이지, GPU 내부 복사가 아예 없다는
뜻은 아닙니다. `NvEncoderD3D12`가 자기 전용 입력 버퍼(`ID3D12Resource`)를 따로 할당해서
쓰는 구조라, SceneCapture 렌더타겟 → 그 입력 버퍼로 **GPU-로컬 `CopyResource` 한 번**은
거칩니다(VRAM 대역폭 안에서 일어나는 복사라 수 마이크로초 수준, CPU 스톨 없음). §4 참고.

---

## 1. 만들어진 파일

```
Plugins/RtspEncoder/
  RtspEncoder.uplugin
  Source/RtspEncoder/
    RtspEncoder.Build.cs
    Public/
      RtspEncoderModule.h        — GStreamer 프로세스 전역 초기화(gst_init)
      RtspServerSubsystem.h      — GstRTSPServer + appsrc 브리지 (GameInstanceSubsystem)
      NvencD3D12Encoder.h        — NvEncoderD3D12 래퍼 (zero-copy 인코드)
      RtspStreamComponent.h      — SceneCapture 1개 ↔ 인코더 1개 ↔ RTSP mount 1개
      RtspPocTestActor.h         — 회전 큐브 + Capture + Stream, 최소 검증용 액터
    Private/
      (위 5개의 .cpp) + RtspPocCommands.cpp (콘솔 커맨드)
    ThirdParty/NvCodec/          — NVIDIA SDK 샘플 코드 vendored (아래 §2)
```

---

## 1.10. §1.9 크래시 진짜 원인 + 조용한 fence 버그 하나 더 발견

§1.9의 `FRHICommandListScopedPipeline`만 추가하는 조치로는 **크래시가 그대로 재현**됐습니다
(같은 assert, 줄 번호만 밀림). 엔진 소스(`RHICommandList.cpp`, `D3D12RHI.cpp`,
`D3D12CommandContext.h`)를 직접 따라가서 원인을 다시 찾았습니다.

**진짜 원인**: `RHICmdList.SwitchPipeline(...)`은 즉시 효과가 나는 게 아니라 **커맨드
스트림에 "파이프라인 전환" 명령을 하나 enqueue만** 합니다(`FRHICommandListBase::
ActivatePipelines`가 `EnqueueLambda`로 구현돼 있음) — 이게 실제로 적용되는 건 나중에 그
커맨드 리스트가 "실행"될 때입니다. 그런데 `RHIGetGraphicsCommandList()`는 제가
**즉시/동기적으로** 호출하고 있었습니다 — SwitchPipeline이 큐에 들어가기만 하고 아직
실행 전인 시점에 상태를 읽으려 든 것. 그래서 파이프라인 전환 자체는 (아마) 맞게
enqueue됐는데도 크래시가 똑같이 재현된 것.

거기다 `RHIGetGraphicsCommandList`의 실제 구현(`D3D12RHI.cpp`)을 보면, 이름은
"Graphics"인데 내부적으로 `RHICmdList.GetComputeContext()`를 요구합니다(D3D12에서는
Graphics/Compute 컨텍스트 획득 경로가 이렇게 얽혀있음) — 그래서 어서트 메시지가
"ComputeContext"를 얘기했던 것.

**해결**: `RHIGetGraphicsCommandList` + 배리어 + `CopyResource` + `RHISignalManualFence`를
전부 `RHICmdList.EnqueueLambda(...)` **안으로** 옮겼습니다 — 이러면 SwitchPipeline 명령
다음으로 우리 커맨드가 큐에 순서대로 들어가고, 나중에 그 스트림이 실제 실행될 때 SwitchPipeline
효과가 이미 적용된 뒤에 우리 코드가 돌아갑니다(엔진 자체의 D3D12RHI 구현도 전부 이 패턴 —
`D3D12Texture.cpp`/`D3D12RenderTarget.cpp` 등 수십 군데가 똑같이 `EnqueueLambda` 안에서
`ExecutingCmdList`를 받아 씀).

**덤으로 발견한 조용한 버그**: 이 코드를 파다가, fence 카운터를 **우리 자신의 별도 멤버
변수**(`InputFenceValue`)로 증가/시그널하고 있었는데, NVIDIA SDK의 `MapResources()`
(NVENC가 GPU-wait할 값을 정하는 곳)는 **자기 자신의 내부 카운터**(`m_nInputFenceVal`,
`Encoder->GetInpFenceValPtr()`로 얻는 그 포인터)를 읽는다는 걸 확인했습니다. 서로 다른
카운터라, NVENC는 우리가 실제로 시그널하는 값과 무관하게 "0(fence 생성 시 초기값)"만
기다리고 있었던 셈 — 즉 **복사가 끝나기도 전에 NVENC가 입력 버퍼를 읽어갔을 수 있는
레이스 컨디션**이었습니다(크래시는 안 났겠지만 화면이 찢기거나 이전 프레임 잔상이 섞이는
식으로 나타났을 가능성). `Encoder->GetInpFenceValPtr()`가 가리키는 진짜 카운터를 직접
증가시키도록 고쳤고, 이제 안 쓰는 `InputFenceValue` 멤버는 지웠습니다.

---

## 1.11. §1.10 수정 후 — 크래시 지점이 더 안쪽으로 이동 (RHIGetGraphicsCommandList는 이제 통과)

§1.10 수정(EnqueueLambda로 감싸기) 후 스택트레이스가 `TRHILambdaCommand::ExecuteAndDestruct`
안쪽까지 들어간 걸 확인 — 즉 우리 람다가 정확한 지점에서 실제로 실행되기 시작했다는 뜻이고,
`RHIGetGraphicsCommandList(ExecutingCmdList, ...)` 호출도 이번엔 통과했습니다(더 이상
그 줄에서 안 죽음). 그런데 바로 다음 줄 `RHISignalManualFence(RHICmdList, ...)`에서 다시
같은 계열 어서트("Exactly one pipeline must be active... mask is 0x00") — 이번엔 "컨텍스트가
없다"가 아니라 "파이프라인이 아예 하나도 활성화 안 된 상태".

원인: 그 줄에서 **바깥쪽 `RHICmdList`(레코딩용 원본 참조)를 그대로 썼는데**,
`RHIGetGraphicsCommandList`에 넘긴 `ExecutingCmdList`(람다 파라미터, 실행 시점의 진짜
커맨드리스트)와 `ActivePipelines` 상태가 동기화돼 있지 않았습니다 — "같은 오브젝트를
시점만 다르게 참조하는 것"이라는 제 가정이 틀렸던 것. **해결**: `RHISignalManualFence`도
`ExecutingCmdList`를 쓰도록 바꿨습니다(타입만 `FRHICommandList&`를 요구해서
`static_cast` 필요 — 실제 런타임 객체는 항상 `FRHICommandListImmediate`라 안전).
**교훈**: 이 람다 안에서는 예외 없이 `ExecutingCmdList`만 쓰고 바깥 `RHICmdList`는
절대 참조하지 말 것.

---

## 1.12. PIE 종료 시 크래시 (use-after-free) + "영상 안 나옴" 진단 체크리스트

인코딩 루프는 안정적으로 돌기 시작했지만(§1.9~1.11 크래시 재발 없음), VLC로 접속했는데
영상이 안 나왔고, PIE 종료하다가 별개의 크래시가 나서 로그를 확인 못 함:

```
EXCEPTION_ACCESS_VIOLATION reading address 0xffffffffffffffff
RtspEncoderPrivate::OnMediaUnprepared() [RtspServerSubsystem.cpp:61]
```

**원인**: `OnMediaConfigure`에서 `GstRTSPMedia`의 `"unprepared"` 시그널에 **factory qdata의
포인터를 그대로** 넘기고 있었습니다. `gst_rtsp_media_factory_set_shared`로 공유되는 미디어는
그걸 만든 factory보다 더 오래 살 수 있어서(PIE 종료 시 `UnregisterStream`/`Deinitialize`가
factory를 정리하는 도중에 media/세션이 아직 마무리 중인 경우 등), factory의 qdata
destroy-notify가 먼저 그 포인터를 `delete`해버린 뒤에 `unprepared`가 나중에 발화하면
이미 해제된 메모리를 읽는 use-after-free가 됩니다 — 정확히 이 크래시.

**해결**: media 쪽에 `TSharedPtr` **독립 사본**을 새로 힙 할당해서 media 자신의 qdata로
붙였습니다(참조 카운트 방식이라 안전 — media가 살아있는 한 `FRtspStreamState`도 같이
살아있음, factory 수명과 무관).

**"영상 안 나옴" 다음 진단 순서** (이 크래시 없이 로그를 볼 수 있게 됐으니):
1. `LogRtspEncoder: ... prepared for a client` 로그가 떴는지 — 안 떴으면 VLC가 appsrc까지
   도달을 못 한 것(SDP/미디어 팩토리 문제).
2. `LogRtspEncoder: ... media-configure couldn't find appsrc` 에러가 떴는지 — 떴으면 launch
   문자열의 `appsrc name=videosrc` 이름 매칭 문제.
3. `LogRtspEncoderNvenc` 쪽에 `EncodeFrame`/`NVENC EncodeFrame threw` 에러가 반복되는지 —
   있으면 인코딩 자체가 실패해서 프레임이 아예 안 만들어지는 것.
4. 위 셋 다 정상인데 화면만 안 나오면: `appsrc`의 caps 문자열(`width=%d,height=%d,
   framerate=%d/1`)과 실제 프레임 크기가 일치하는지, 또는 VLC 쪽 캐싱/지연시간 설정 문제일
   수 있음 — `ffplay -rtsp_transport tcp rtsp://127.0.0.1:8554/poc/stream0`로 다시 시도해서
   VLC 특정 문제인지 구분해보는 것도 방법.

---

## 1.13. VLC "입력을 열 수 없습니다" — DESCRIBE가 통째로 걸려있었음

PIE가 켜진 채로 있길래 이 컴퓨터에서 직접 실시간 진단했습니다(사용자 재현 없이):

- `netstat`: 8554 포트 정상 리슨 중, VLC로 추정되는 ESTABLISHED 연결도 여러 개 있음 (TCP 연결
  자체는 됨).
- `curl -v rtsp://127.0.0.1:8554/`(OPTIONS): 즉시 `200 OK` 정상 응답 — RTSP 서버 자체는
  살아있고 응답도 함.
- 직접 소켓 열어서 `DESCRIBE rtsp://.../poc/stream0` 전송: **5초 타임아웃까지 응답 0바이트**
  — 완전히 걸려있음.
- `gst-launch-1.0`으로 우리가 만드는 것과 **똑같은 launch 문자열**(appsrc caps 포함)을
  standalone으로 돌려봄 — PAUSED→PLAYING 정상 진입, 문제없음. → 파이프라인 자체는 결백,
  우리 C++ 통합 코드 쪽 문제로 좁혀짐.
- `titan_example.log`를 직접 열어서 확인: `RTSP server listening`/`Registered RTSP mount`/
  `NVENC ready`까지는 찍히는데, **`"... prepared for a client"` 로그(= `OnMediaConfigure`
  완료 시점)가 여러 번의 DESCRIBE 시도에도 단 한 번도 안 찍힘** — `media-configure` 콜백
  진입 자체가 안 됨(또는 그 안에서 영원히 멈춤).

**원인**: RTSP 서버 전용 스레드(`FRtspLoopRunnable`)에서 `g_main_loop_run()`을 돌리기 전에
**`g_main_context_push_thread_default()`를 호출 안 함.** OPTIONS 같은 단순 요청은 서버를
attach한 컨텍스트에 직접 붙는 이벤트라 문제없이 처리되지만, gst-rtsp-server는 각 클라이언트의
미디어 준비를 **자체 워커 스레드 풀**에서 처리하고 그 완료를 "스레드 기본 컨텍스트" 메커니즘으로
알리는데, 이게 하나도 안 잡혀있으면 완료 신호가 갈 곳이 없어서 영원히 대기 — GLib 공식 문서의
"전용 스레드에서 커스텀 컨텍스트로 메인루프 돌리기" 레시피에 있는 필수 단계를 빼먹었던 것.

**해결**: `FRtspLoopRunnable::Run()`에서 `g_main_loop_run()` 앞뒤로
`g_main_context_push_thread_default()` / `g_main_context_pop_thread_default()` 추가.

---

## 1.14. 성공 — 그리고 "느림"의 진짜 원인은 PIE 백그라운드 프레임 제한이었음

§1.13 수정(스레드 기본 컨텍스트) 이후에도 DESCRIBE가 느렸던 것(반복할수록 더 느려짐)의
진짜 원인을 사용자가 직접 찾아냈습니다: **PIE 창이 백그라운드로 가면 에디터가 프레임레이트를
크게 낮추는 설정**(Editor Preferences → General → Performance → "Use Less CPU when in
Background") 때문에, `RtspStreamComponent::TickComponent`(매 틱마다 인코드+push)가 거의
안 돌아서 appsrc에 실제 데이터가 안 들어갔고, gst-rtsp-server가 SDP에 넣을 실제 SPS/PPS를
뽑을 데이터가 없어 DESCRIBE가 하염없이 느려진 것이었습니다(§1.13의 스레드 컨텍스트 수정도
필요하긴 했음 — 그거 없인 영원히 걸렸을 것). 이 설정을 끄니 VLC 접속·재생 정상 확인됨.

**프로덕션 관련 참고**: 실제 통제기SW 연동 시 에뮬레이터 창이 항상 포커스돼 있으리라는 보장이
없다면, 이 백그라운드 스로틀링이 실서비스에서도 문제가 될 수 있음 — 패키지 빌드(에디터가
아닌 실행 파일)에서는 이 특정 설정이 적용 안 되지만, 유사한 백그라운드 절전 로직이 있는지는
확인 필요.

**추가로 확인된 사소한 것들** (파이프라인 검증엔 무관, 나중에 다듬을 것):
- 회전 큐브가 다소 어둡게 보임 — 씬 조명/노출 설정 이슈로 추정, 인코딩/스트리밍 자체와는 무관.
- VLC에 보이는 화면은 PIE 뷰포트(플레이어 시점)가 아니라 `RtspPocTestActor`가 큐브 옆에 만든
  **고정 SceneCapture**임 — 의도된 설계(PoC 목표가 "SceneCapture 하나로 배관이 되는지"였지
  플레이어 시점 미러링이 아니었음). 실제 UGV/자체방호축 연동 시엔 QuadCamModule/RCWS의 진짜
  SceneCaptureComponent에 `RtspStreamComponent`를 붙이면 됨.

---

## 1.15. "새로 시작하면 되는데 반복 연결하면 불안정" — 레이스 컨디션 찾아서 고침

§1.14 성공 이후, 7스트림 부하 테스트→VLC 여러 개 연결 테스트 과정에서 재연결이 점점
불안정해지는 걸 발견. VLC뿐 아니라 **GStreamer 자체 클라이언트(`gst-launch-1.0`의
`rtspsrc`)로도 똑같이 재현**돼서 VLC 탓이 아니라 서버 쪽 문제로 확정. ffplay 설치해서
추가 테스트했지만 그쪽은 별도로 창 생성 관련 이슈가 있어 보여 판단 보류(SDL 창이 아예
안 뜸 — 연결 자체는 되는데, 이건 ffplay/실행 환경 쪽일 가능성이 있어 더 안 팠음).

**리서치**: "gst-rtsp-server + appsrc, 재연결하면 불안정/실패"는 알려진 문제 계열이었음
([NVIDIA 포럼](https://forums.developer.nvidia.com/t/rtsp-server-reconnection-failure/161171),
[GStreamer Discourse](https://discourse.gstreamer.org/t/rtsp-disconnect-and-reconnect-on-error-during-play/395)) —
"마지막 클라이언트가 끊기면 GstRTSPMedia가 파이프라인을 완전히 GST_STATE_NULL로 내리고,
다음 연결 때 media-configure부터 처음부터 다시 돈다"는 게 핵심 배경 지식. 이걸 바탕으로
저희 코드를 다시 리뷰해서 구체적 버그를 찾음.

**버그**: `OnMediaUnprepared`가 "이 unprepared 신호가 지금 활성 상태인 그 미디어의 것이
맞는지" 확인 없이 `State.AppSrc`를 무조건 null로 지움. gst-rtsp-server는
`media-configure`/`unprepared`를 미디어 인스턴스별로 **다른 스레드 풀 워커**에서 실행할 수
있어서, "클라이언트 A 끊김(media1 unprepared, 처리 지연)" 도중에 "클라이언트 B 재연결
(media2 configure, AppSrc를 새 값으로 교체)"이 끼어들면, **뒤늦게 처리된 media1의
unprepared가 media2의 새 AppSrc까지 지워버림** — 재연결을 많이 반복할수록 이 타이밍이
어긋날 확률이 올라가는 구조라 "새로 시작하면 되고 반복하면 불안정해지는" 증상과 정확히
일치.

**해결**: 각 미디어 인스턴스가 "내가 설정한 AppSrc가 이거였다"를 자기 것으로 따로
들고 있다가(`FMediaUserData::OwnAppSrc`), unprepared 시점에 `State.AppSrc`가 **여전히
자기 것과 같을 때만** null로 지우도록 수정 — 이미 더 새로운 미디어로 교체된 상태라면
자기 참조만 정리하고 `State.AppSrc`는 안 건드림.

**디버깅 로그 보강** (사용자 요청): `prepared`/`unprepared` 로그에 media/appsrc 포인터 값
추가, `PushEncodedFrame`이 연결마다 첫 성공 push 시점을 로그로 남기도록 추가, push
성공/실패 누적 카운트 추가 — 다음에 비슷한 문제가 또 나오면 로그만으로 "재연결 타이밍
문제인지 아닌지"를 바로 알 수 있음.

---

## 1.16. 레이스 컨디션 고친 후에도 "연결은 유지되는데 화면 안 뜸" — 진짜 원인은 키프레임

§1.15 수정 후 로그 재확인(스트림 1개, 반복 재연결) — 이번엔 "already superseded" 경고
없이 깨끗했고, `prepared` → `first encoded frame pushed`가 **밀리초 단위**로 거의
즉시 찍힘(예전의 수 초 지연은 사라짐). 그런데 연결이 10~20초씩 유지되다가 끊기는 게
반복됐고, 사용자 확인으로는 그 10~20초 동안 화면이 한 번도 제대로 뜬 적이 없었음.

**데이터는 전송되는데 화면이 안 뜨는 이유**: NVENC의 GOP 길이를 `Fps*2`(2초)로 설정해뒀는데,
**새로 붙는 RTSP 클라이언트가 정확히 그 순간의 프레임(대개 P-프레임)부터 받기 시작**함.
P-프레임은 이전 프레임을 참조해야 디코딩되는데, 새 클라이언트는 그 "이전 프레임"을 받은
적이 없어서 디코딩이 안 됨 — 다음 키프레임(최대 2초 후)이 올 때까지는 이론상 검은
화면/디코딩 실패 상태. 서버 쪽에서 보면 "정상 push 계속 성공"으로 보여서
(`bLoggedFirstPushThisConnection`는 실제로 데이터가 나갔다는 것만 확인하지 그게
디코딩 가능한 프레임인지는 모름) 로그만 봐서는 이 문제를 못 잡음 — 사용자가 화면을 직접
보고서야 드러난 문제.

**해결**: 새 클라이언트가 붙는 시점(`OnMediaConfigure`가 `AppSrc`를 새로 설정하는 순간)을
`FRtspStreamState::bNewConnectionPending` 플래그로 표시 →
`URtspServerSubsystem::ConsumeNewConnectionFlag()`로 노출 → `RtspStreamComponent::
TickComponent`가 매 틱 이 플래그를 확인해서, 있으면 그 프레임 인코딩 시
`NV_ENC_PIC_FLAG_FORCEIDR`을 넘겨 강제로 키프레임을 만들도록 함
(`FNvencD3D12Encoder::EncodeFrame`의 새 `bForceKeyframe` 파라미터). NVIDIA SDK의
`NvEncoder::DoEncode()`가 넘겨받은 `NV_ENC_PIC_PARAMS`의 `encodePicFlags`만 그대로 통과시키고
나머지 필드는 자체적으로 채워주는 구조라, 이 플래그 하나만 세팅하면 됨.

---

## 1.17. §1.16 강제 키프레임이 "가끔만" 먹히던 진짜 이유 — NVENC 출력 버퍼링

§1.16 수정 후에도 재연결이 여전히 불안정. 이번엔 `ffplay`/`ffprobe`를 직접 스크립트로
돌려서(로그인 세션 이슈로 SDL 창은 안 떴지만 `-show_frames`로 헤더리스 디코딩 검증은
가능) 확인 — **어떤 연결은 첫 push가 9800~40000바이트대(키프레임 크기), 어떤 연결은
1500~2100바이트대(일반 P-프레임 크기)**로 들쭉날쭉했음. 강제 키프레임 요청 자체는
매번 나가고 있는데, 실제로 반영이 안 되는 경우가 있다는 뜻.

**원인**: `NvEncoderD3D12` 생성 시 `nExtraOutputDelay` 기본값이 3 — 이건 "지금 인코딩
요청한 프레임의 출력 결과가 실제로 나오기까지 최대 3번의 `EncodeFrame()` 호출만큼 지연될
수 있다"는 뜻(GPU/CPU 파이프라이닝 오버랩용 버퍼링). 새 클라이언트 연결 시점에 강제
키프레임을 "요청"해도, **그 요청 이전에 이미 파이프라인에 들어가 있던 P-프레임 최대 3개의
출력이 먼저 나와서 새 클라이언트에게 먼저 push됨** — 새 클라이언트는 자기가 요청한
키프레임이 나오기 전에 디코딩 불가능한 P-프레임부터 받는 구조. 로그의 `first encoded
frame pushed` 크기가 들쭉날쭉했던 게 정확히 이걸 반영한 것(운 좋게 버퍼가 비어있던
타이밍이면 키프레임이 바로 나오고, 아니면 몇 프레임 밀림).

**해결**: `FNvencD3D12Encoder::Initialize()`에서 `NvEncoderD3D12` 생성 시
`nExtraOutputDelay=0`으로 설정(기본값 3 → 0) — 인코딩 요청한 프레임의 출력이 지연 없이
바로 나오도록. 트레이드오프: SDK 주석은 "GPU/CPU 병렬 처리를 위해 최소 1은 권장"이라고
돼 있어 약간의 파이프라이닝 이득을 포기하는 것이지만, 실측한 NVENC 하드웨어 사용률이
7스트림에서도 평균 10%로 여유가 커서(§1.9 이전, 부하 실측 참고) 이 정도 트레이드오프는
감당 가능하다고 판단.

---

## 1.18. `nExtraOutputDelay=0`이 에디터 데드락 유발 → 되돌리고 다른 방식으로 해결

§1.17에서 `nExtraOutputDelay`를 3→0으로 줄였는데, 그 직후 `RtspPoc.SpawnTestActors 1`
(스트림 딱 1개) 실행하자마자 **에디터가 멈춤**(크래시는 아님, `Get-Process`로 확인해보니
`Responding: True`인데 화면은 정지 — 렌더 스레드가 뭔가를 무한 대기하는 전형적인 증상).

**원인**: `NvEncoder.cpp`의 `m_nEncoderBuffer = frameIntervalP + lookaheadDepth +
nExtraOutputDelay + ...` 계산식에서, 저희 설정(`frameIntervalP=1`, `lookaheadDepth=0`)에
`nExtraOutputDelay=0`을 더하면 `m_nEncoderBuffer=1`이 되고, 이러면 `NvEncoder`가
`IsZeroDelay()` 동기 모드로 들어갑니다 — `EncodeFrame()` 호출이 **렌더 스레드에서 GPU
하드웨어 완료를 블로킹 대기**하게 됨(원래는 비동기 파이프라이닝). SDK 헤더 주석에도
"GPU/CPU 병렬 처리를 위해 최소 1은 되게 하라"고 적혀 있었는데 무시하고 0으로 갔던 게
문제. **되돌림** — `nExtraOutputDelay`는 SDK 기본값(3)을 그대로 둠.

**대신 이렇게 해결**: 새 클라이언트를 위해 요청한 강제 키프레임이 버퍼링 때문에 즉시 안
나올 수 있다는 사실 자체는 그대로 두고, **그 사이에 나오는 패킷들을 실제로 push하지 않고
버리도록** `FNvencD3D12Encoder::EncodeFrame()`에 로직 추가 — `bForceKeyframe`을 요청한
직후부터 `bWaitingForRequestedKeyframe` 플래그를 세우고, `NvEncOutputFrame::pictureType`이
`NV_ENC_PIC_TYPE_IDR`인 패킷이 실제로 나올 때까지 그 사이의(이미 파이프라인에 있던 오래된
P-프레임) 패킷들은 그냥 버림(`OutAccessUnits`에 안 넣음, push 자체가 안 됨). 버퍼링/스레딩
동작은 전혀 안 건드리고, "새 클라이언트가 받는 첫 프레임이 항상 디코딩 가능해야 한다"는
요구사항만 정확히 만족시키는 방식.

**교훈**: NVENC SDK 파라미터를 바꿀 땐 헤더 주석의 경고를 가볍게 넘기지 말 것 — 이번 건
"성능 트레이드오프려니" 하고 넘어갔다가 실제로는 스레딩 모델 자체가 바뀌는 위험한
변경이었음.

---

## 1.19. §1.18 이후에도 재연결 시 화면 안 뜸 — 근데 서버 로그는 정상 (진단 로그 강화)

에디터가 2개 떠 있어서 로그를 잘못 보고 있었던 걸 사용자가 지적 — 하나만 남기고 정리한
뒤 다시 확인. **재연결(두 번째 연결)도 서버 쪽 로그로는 10초 넘게 1254개 프레임이 문제없이
계속 push됨**(끊길 때도 FLUSHING→unprepared로 깔끔하게 종료, 크래시/에러 없음) — 그런데도
VLC엔 화면이 안 뜸. → 결론: 여전히 "연결/전송 문제"가 아니라 "받은 데이터를 디코딩 못
하는" 문제.

같은 세션에서 `ffprobe -show_frames`로도 확인해봤는데, **841개 프레임이 정상 push된
연결에서도 ffprobe가 프레임을 단 하나도 디코딩 못 함**(SDP 파싱까진 성공, 그 이후
`-show_frames` 출력이 완전히 빔). VLC뿐 아니라 ffprobe도 안 되는 걸 보면, 클라이언트
쪽 문제라기보다 저희가 만드는 비트스트림 자체에 남은 결함이 있을 가능성이 있음.

**의심되는 지점**: 강제 키프레임(`NV_ENC_PIC_FLAG_FORCEIDR`)으로 만든 프레임이 실제로
`NvEncOutputFrame::pictureType == NV_ENC_PIC_TYPE_IDR`로 보고되는지 확신할 근거가
없었음(로그로 실측한 적이 없었음) — `NV_ENC_PIC_TYPE_I`(일반 인트라 프레임, IDR과는
구분되는 별개 타입)로 보고될 가능성을 배제 못 해서, 방어적으로 `_I`도 함께 허용하도록
수정. 동시에 `bWaitingForRequestedKeyframe` 대기 중 만나는 모든 패킷의 실제
`pictureType` 값을 Log 레벨로 남기도록 진단 로그 추가 — 다음 재현 시 이 값을 보면
가설이 맞았는지 바로 확인 가능.

---

## 1.20. pictureType 로그로 키프레임 가설은 기각 — 진짜 원인은 PTS가 재연결마다 리셋 안 되는 것

§1.19에서 추가한 `pictureType` 진단 로그로 재현해보니, **재연결할 때마다 매번
`pictureType=0`(P프레임) 패킷들이 정상적으로 discard되고, 그 다음 정확히
`pictureType=3`(IDR)이 accept되는 패턴이 재현성 있게 확인됨** — 즉 강제 키프레임 로직
자체는 완전히 맞게 동작하고 있었음. `_I` 방어 코드는 실제로는 한 번도 안 탔음(항상
`_IDR`로 정확히 보고됨). 이걸로 "키프레임 타이밍" 가설은 기각.

다음으로 `ffprobe -v debug -show_frames`로 더 깊이 파봄. 로그를 보면:
- SDP는 정상 파싱, `video codec set to: h264`, `RTP Packetization Mode: 1`
- `sprop-parameter-sets`에서 뽑은 SPS/PPS(대역외 extradata, 아직 RTP로 프레임 하나도
  안 온 시점)를 ffmpeg의 H264 파서가 파싱 — `nal_unit_type: 7(SPS)`,
  `nal_unit_type: 8(PPS)` 로그 다음 `Decoding VUI`를 마지막으로 **그 이후로 8초
  타임아웃까지 로그가 완전히 끊김**(추가 NAL 로그도, 프레임 출력도 전혀 없음).

`sprop-parameter-sets=Z2QAH6wrIAoAt2AiAAAH0AAB1MEI,aOuPLA==`의 SPS를 직접
exp-golomb으로 파싱해본 결과(Python으로 직접 비트리더 작성): `profile_idc=100(High)`,
`1280x720`, `aspect_ratio_idc=1`, `timing_info(1000/60000, 30fps)`, HRD 파라미터 없음,
`bitstream_restriction` 없음, 트레일링 비트까지 완전히 정상 — **VUI 데이터 자체는 전혀
손상되지 않음**. 즉 `Decoding VUI` 로그는 SPS 파싱이 실패해서 멈춘 게 아니라, 그
extradata 1회성 파싱이 끝난 마지막 로그 줄이고, **그 이후 실제 RTP로 오는 슬라이스/IDR
NAL 자체를 못 받고(또는 재조립 못 하고) 있다는 뜻**으로 재해석.

서버 로그로는 `gst_app_src_push_buffer`가 연결당 수백~천 회 이상 계속 `GST_FLOW_OK`로
성공 — appsrc 큐가 꽉 차서 막힌 흔적도 없음(막혔다면 appsrc의 `max-bytes`
기본값 200KB가 30fps에서 1초 내로 다 차서 곧 push 실패가 났을 것). 즉 appsrc →
`h264parse` → `rtph264pay`까지는 데이터가 계속 흐르고 있다는 뜻이라, 병목은 그보다 더
아래(RTSP 세션의 실제 클라이언트 전송 경로) 쪽으로 좁혀짐.

**진짜 원인으로 특정**: `gst_rtsp_media_factory_set_shared(Factory, TRUE)`라서, 마지막
클라이언트가 끊기고 새 클라이언트가 붙을 때마다 `OnMediaConfigure`가 다시 불리며
**파이프라인이 통째로 새로 만들어짐**(그때마다 GStreamer 파이프라인 clock의 base-time도
새로 잡힘, running-time은 항상 0부터 다시 시작). 그런데 `PushEncodedFrame`에 넘기는
PTS(`RtspStreamComponent::TickComponent`의 `SubmitPtsNs`)는 **액터
`BeginPlay` 시점에 딱 한 번 잡히는 `StreamStartSeconds` 기준 경과 시간**이라서, 재연결
때마다 리셋되지 않고 계속 누적됨. 그 결과:
- PIE를 막 켠 직후 첫 연결: 누적 경과 시간이 거의 0이라 새 파이프라인의 running-time(0)과
  거의 맞아떨어짐 → 재생 성공.
- 그 이후의 모든 재연결: 우리가 찍는 PTS가 이미 (PIE 시작 후 흐른 시간만큼) 커져 있는데,
  새로 만들어진 파이프라인의 running-time은 다시 0부터 시작 → 버퍼가 "미래" 시각으로
  타임스탬프 찍혀서 들어오는 꼴이 됨. `format=time`인 live appsrc 뒤에서 sync를 신경 쓰는
  구간이 이 시각까지 기다리려고 하면서 사실상 영상이 하나도 안 나가는 것으로 보임(정확히
  어느 구성요소가 대기시키는지까지는 확인 안 했지만, 증상·재현 조건과 정확히 일치).
- "PIE 껐다 켜니 잘 나옴"도 같은 설명: `StreamStartSeconds` 자체가 리셋되어 경과 시간이
  다시 0에 가까워졌기 때문.

**수정**: `RtspServerSubsystem.cpp`의 launch 문자열에서 appsrc에 `do-timestamp=true` 추가
(파이프라인 자신의 클록으로, push되는 시점의 running-time을 기준으로 매번 새로
타임스탬프를 찍음 — 재연결마다 파이프라인이 새로 생기면 그 클록도 같이 새로 생기니까
자동으로 맞음). `PushEncodedFrame`에서 수동으로 하던 `GST_BUFFER_PTS`/`GST_BUFFER_DTS`
설정은 제거(`do-timestamp=true`가 어차피 덮어씀). `PtsNanoseconds` 파라미터는 시그니처만
남기고 실제로는 안 씀 — 나중에 완전히 정리해도 됨.

**검증 결과(추후 갱신)**: 재연결 안정성 자체(연결이 빠르고 재연결도 끊김 없이 됨)는
사용자가 확인함 — 이 섹션의 진단(파이프라인 재생성마다 클록이 리셋된다는 것)은 맞았음.
다만 여기서 적용한 수정 방식(`do-timestamp=true`)은 실제로는 효과가 없었던 것으로 나중에
밝혀짐(`OnMediaConfigure`가 매번 다시 꺼버리고 있었음) — 자세한 내용과 최종 수정은
§1.22 참고. 최종적으로는 프레임 인덱스 기반 수동 PTS(`NextPtsNs`)로 대체됨.

---

## 1.21. §1.20 이후 — 연결/재연결은 완전히 안정화, 그런데 VLC 화면이 멈춰있음(회전 안 함)

`do-timestamp=true` 수정 이후 사용자 확인: **VLC 연결이 훨씬 빨라졌고, 재연결도 이제
문제없이 됨** — §1.20의 진단/수정이 맞았던 것으로 보임. 그런데 새 증상: VLC 화면에
큐브는 보이는데 회전하지 않고 정지 화면처럼 멈춰 있음.

로그부터 확인(`titan_example.log`, `LogRtspEncoder`의 30개마다 찍는 push 로그) —
**초당 push 빈도가 예상(30fps)보다 훨씬 높음**:

```
push ok #601 04:22:56.449
push ok #631 04:22:56.700   (30번에 251ms = 초당 약 119.5회)
push ok #661 04:22:56.953   (253ms)
push ok #691 04:22:57.204   (251ms)
```

즉 **초당 약 120회 push되고 있었음** — `URtspStreamComponent::TickComponent`가 UE 틱마다
(레벨이 작아서 PIE가 120fps 가까이 도는 상태) 아무 제한 없이 매번 `EncodeFrame`을 호출해서
그대로 인코딩/전송하고 있었던 것. 반면 SDP/caps는 `TargetFps=30`으로 선언돼 있고,
`ffprobe`/`ffmpeg`가 감지한 스트림 정보도 `30 fps, 60 tbr`로 선언값과 실측값이 어긋나 있음.

직접 검증: `ffmpeg -rtsp_transport tcp -i ... -frames:v 90 raw_%03d.png`를 돌려보면
`frame=0 ... drop=NNN`으로 **디코딩된 프레임을 출력에 하나도 못 쓰고 계속 drop만 함**
(15초에 570프레임 이상 드랍) — 선언된 30fps 기준으로 출력 타이밍을 맞추려는 쪽이 실제
4배 빠른 입력 페이스를 따라가지 못해 거의 다 버려지는 것으로 보임. VLC 쪽도 같은 이유로
(SDP가 30fps라고 알려주는데 실제로는 4배 빠르게 프레임이 밀려들어오니) 디코드/렌더가
못 따라가서 첫 프레임에 멈춘 것으로 추정.

**주의**: `pict_type,pkt_size`만 보는 `ffprobe -show_frames`(§1.20에서 썼던 명령)로는 이
문제가 안 드러남 — 프레임 자체는 각각 정상적으로 디코딩되고 크기도 매번 다르게 나와서
"비트스트림은 멀쩡하다"고 착각하기 쉬움. 실제 프레임 페이싱(초당 개수)을 봐야 드러나는
문제였음 — 앞으로 이런 종류 증상(연결/디코딩은 되는데 재생이 이상함)은 pict_type 로그
말고 **push 로그 타임스탬프 간격**이나 `ffmpeg`의 `drop=`/`dup=` 카운터도 같이 봐야 함.

**수정**: `RtspStreamComponent`에 프레임 페이싱 누적기(`SecondsSinceLastSubmittedFrame`)
추가 — `TickComponent`가 매 틱 호출되더라도, `TargetFps`가 요구하는 간격(`1/TargetFps`)이
지나기 전에는 그냥 리턴하고 인코드/push를 스킵함. 드리프트 누적을 막기 위해 다음 프레임
때 누적값을 0으로 리셋하지 않고 간격만큼 빼는 방식(`-=`)으로 처리. `RtspStreamComponent.h`/
`.cpp` 수정.

**검증 결과**: 이 프레임 페이싱 수정 자체(30fps로 정확히 제한됨)는 §1.22에서 로그로
재확인됨. 다만 이것만으로는 "첫 프레임 멈춤" 증상이 해결되지 않았음 — 진짜 원인은 별개로
§1.22에서 찾음(RTP 타임스탬프가 아예 증가하지 않던 문제). 최종적으로 §1.22 수정까지
합쳐진 뒤 사용자가 정상 재생(큐브 회전 포함)을 확인함.

---

## 1.22. §1.21 이후에도 여전히 첫 프레임에서 멈춤 — 진짜 원인은 do-timestamp가 실제로는 꺼져 있었던 것

사용자 확인: §1.21(프레임 페이싱 제한)을 적용/재빌드한 뒤에도 VLC가 여전히 첫 프레임에서
멈춤. "제대로 원인 파악 작업 시작해줘" 요청에 따라 처음부터 다시 체계적으로 확인.

먼저 로그로 §1.21 수정이 실제로 반영됐는지부터 검증: push 로그 간격이 `#1`→`#31`
0.994초로 정확히 30fps에 맞게 나오는 것 확인(이전엔 251ms/30개였음) — 페이싱 수정
자체는 제대로 동작 중. 그런데도 증상은 동일 → 프레임 레이트 문제가 아니라 여전히 다른
원인이 있다는 뜻.

`ffprobe -show_entries frame=pts,pts_time,pkt_pts,pkt_pts_time,pkt_dts,pkt_dts_time,best_effort_timestamp_time,key_frame,pict_type`로
실제 RTP 타임스탬프를 직접 찍어봄 — **결정적 증거**: 첫 IDR 프레임(`key_frame=1`)만
제외하고, 그 뒤로 받은 P프레임 220개 이상이 전부 예외 없이 `pts=0, pts_time=0.000000,
dts=0, dts_time=0.000000, best_effort_timestamp_time=0.000000`. 즉 **서버가 실제로
내보내는 RTP 타임스탬프가 두 번째 프레임부터 아예 증가하지 않고 있었음** — VLC와
ffprobe 둘 다 "새 프레임이 도착했다"는 신호(타임스탬프 진행)를 못 받으니 첫 프레임에서
멈춘 것으로 정확히 설명됨. (§1.21에서 썼던 `ffmpeg -frames:v N out_%03d.png` 캡처가
매번 `frame=0 ... drop=NNN`으로 프레임을 하나도 못 쓴 것도 같은 원인 — 모든 프레임이
동일한 타임스탬프라 CFR 출력 슬롯에 전혀 안 맞아떨어짐.)

원인 추적: §1.20에서 launch 문자열에 `do-timestamp=true`를 추가했지만, **`OnMediaConfigure`
안에 원래부터 있던 코드**(`RtspServerSubsystem.cpp`, 클라이언트 연결마다 appsrc를 찾아
설정하는 부분)에 이미 다음 줄이 있었음:

```cpp
g_object_set(G_OBJECT(Src), "format", GST_FORMAT_TIME, "is-live", TRUE, "do-timestamp", FALSE, nullptr);
```

이게 **매 연결마다 appsrc의 `do-timestamp`를 강제로 `FALSE`로 되돌리고 있었음** —
launch 문자열의 `do-timestamp=true`는 파이프라인 최초 생성 시점의 초기값일 뿐이고, 이
`g_object_set` 호출이 그 값을 곧바로 덮어썼던 것. §1.20에서 `do-timestamp=true`를 추가한
게 아무 효과가 없었던 진짜 이유. 게다가 §1.20에서 `PushEncodedFrame`의 수동
`GST_BUFFER_PTS`/`DTS` 설정도 같이 제거했기 때문에, 결과적으로 **아무도 타임스탬프를
설정하지 않는 상태**가 되어 버퍼가 무효한 타임스탬프(`GST_CLOCK_TIME_NONE`)로 들어가고,
그게 `rtph264pay`를 거치며 0으로 처리된 것으로 보임.

**수정**: GStreamer의 파이프라인 클록/`do-timestamp` 메커니즘에 다시 의존하지 않고,
직접 타임스탬프를 관리하는 방식으로 변경.
- `FRtspStreamState`에 `uint64 NextPtsNs` 추가 — 연결마다 리셋되는 이 스트림 전용 PTS
  클록(나노초 단위, 프레임마다 `GST_SECOND / Fps`만큼 증가).
- `OnMediaConfigure`에서 push 카운터 리셋하는 곳과 같은 자리에서 `State.NextPtsNs = 0`으로
  리셋(재연결마다 새 파이프라인과 함께 새로 시작).
- `PushEncodedFrame`에서 `GST_BUFFER_PTS`/`GST_BUFFER_DTS`를 `State.NextPtsNs`로,
  `GST_BUFFER_DURATION`을 `GST_SECOND / Fps`로 명시적으로 설정한 뒤 `NextPtsNs`를
  프레임 하나만큼 증가.
- launch 문자열의 `do-timestamp=true`는 제거(`OnMediaConfigure`가 어차피 `FALSE`로
  되돌리므로 있으나 없으나 차이 없고, 혼란만 유발) — `do-timestamp=FALSE`로 남겨두고
  대신 우리가 직접 타임스탬프를 채워 넣는 것으로 역할을 명확히 함.

이제 프레임 인덱스 기반이라 GStreamer 파이프라인 클록/베이스타임의 어떤 미묘한 동작에도
영향받지 않고, §1.21의 프레임 페이싱(정확히 `1/TargetFps` 간격으로 push)과도 자연스럽게
맞아떨어짐.

**교훈**: `do-timestamp=true`를 launch 문자열에 넣었다고 해서 실제로 적용된다고 가정하면
안 됨 — 같은 element를 나중에 코드에서 `g_object_set`으로 다시 만지는 곳이 있는지
반드시 확인해야 함(이번 경우 `OnMediaConfigure`). 다음번에 GStreamer 프로퍼티를 바꿀
때는 launch 문자열뿐 아니라 `OnMediaConfigure`의 `g_object_set` 호출도 같이 확인할 것.

**검증 결과**: 사용자가 재빌드 후 재현 확인 — "성공했다, 완벽함." VLC에서 연결·재연결·
회전하는 큐브 재생까지 전부 정상 동작함(2026-08-07). §1.13~§1.22에 걸쳐 진행된 "연결은
되는데 재생이 안 됨/불안정함" 계열 이슈들이 이 수정으로 최종 해결된 것으로 판단.

---

## 1.9. 드라이버 업데이트 후 — 큰 레벨에서 RHI 파이프라인 크래시

드라이버 업데이트로 NVENC 세션 오픈까지는 성공(§1.8까지의 조치가 유효했다는 뜻). 그런데
복잡한(더 무거운) 레벨에서 `RtspPoc.SpawnTestActors`를 돌리니 크래시:

```
Assertion failed: ComputeContext [RHICommandList.h:706]
There is no active compute context on this command list. There may be a missing call to SwitchPipeline().
FNvencD3D12Encoder::EncodeFrame() [NvencD3D12Encoder.cpp:148]
```

148번째 줄은 `ID3D12DynamicRHI::RHIGetGraphicsCommandList()` 호출 지점. 원인: 단순한
씬에서는 우리 렌더 커맨드가 실행되는 시점에 `RHICmdList`가 우연히 Graphics 파이프가 활성화된
상태였는데, 무거운 레벨(Lumen/Nanite 등이 AsyncCompute 패스를 스케줄링하는 경우)에서는 우리
커맨드가 AsyncCompute 전용 스코프 중간에 실행될 수 있고, 그 상태에서
`RHIGetGraphicsCommandList()`가 내부적으로 `GetComputeContext()`를 요구하면서 걸림 —
어서트 메시지가 그대로 알려주는 대로 `SwitchPipeline()` 호출이 빠져있던 게 원인.

**해결**: `FNvencD3D12Encoder::EncodeFrame()` 맨 앞에서
`FRHICommandListScopedPipeline PipelineScope(RHICmdList, ERHIPipeline::Graphics);`
(엔진이 제공하는 RAII 헬퍼, `RHICommandList.h`)로 Graphics 파이프를 강제 활성화하고 함수
끝나면(스코프 벗어나면) 자동으로 이전 파이프로 복원되도록 함.

---

## 1.8. 컴파일 성공 후 — 플러그인 로드 실패 → delay-load로 전환 → 또 크래시 → 진짜 해결

**1차**: "Plugin 'RtspEncoder' failed to load because module 'RtspEncoder' could not be
loaded" 발생. 원인: GStreamer DLL들을 **implicit link**로 붙여놔서, Windows가
`UnrealEditor-RtspEncoder.dll` 자체를 로드하는 순간(우리 코드가 한 줄도 실행되기 전)
import 테이블의 GStreamer DLL들을 바로 찾으려 듦 — GStreamer `bin/`이 시스템 기본 검색
경로 어디에도 없어서 로드 자체가 실패. **1차 조치**: GStreamer DLL들을 implicit link
대신 **delay-load**로 전환(`RtspEncoder.Build.cs`의 `PublicDelayLoadDLLs`) — DLL resolve
시점을 "모듈 로드 시점"에서 "그 DLL 함수를 실제로 처음 호출하는 시점"으로 미룸.

**2차**: 그래도 `gst_is_initialized()` 호출 시점에 `0xc06d007e`(delay-load
`ERROR_MOD_NOT_FOUND`) 크래시. 원인: `FPlatformProcess::AddDllDirectory()`가 **진짜 Win32
`AddDllDirectory` API가 아니라 UE 자체 내부 캐시**였음(`FPlatformProcess::GetDllHandle()`
전용, delay-load 헬퍼가 쓰는 raw `LoadLibrary` 호출엔 전혀 영향 없음) — 완전히 헛다리였던
호출. **진짜 해결**: `FPlatformProcess::PushDllDirectory()`로 교체 — 이건 실제 Win32
`::SetDllDirectory()`를 호출해서 이후 모든 `LoadLibrary` 호출(딜레이로드 헬퍼가 내부적으로
쓰는 것 포함)에 영향을 줌. `ShutdownModule()`에 대응하는 `PopDllDirectory()`도 추가.

NVENC(`nvencodeapi64.dll`)나 D3D12/DXGI는 시스템 기본 경로(System32)에 있어서 이 문제
자체가 없음 — GStreamer만 해당.

---

## 1.7. 5라운드 — 진짜 원인 찾음 (RTSPENCODER_GST_ROOT_DIR 이론은 틀렸음)

4라운드에서 슬래시로 바꿔도 `RtspEncoderModule.cpp`의 "식별자 'RtspEncoder'" + EOF 에러가
**한 글자도 안 바뀌고** 그대로 나서, 매크로 이스케이핑 이론은 폐기. 대신 실제
`Intermediate/.../RtspEncoder.Shared.rsp` + `Definitions.h`를 직접 열어서 컴파일러가 진짜
보는 내용을 확인했고, 최종적으로 **cl.exe를 이 세션에서 직접 `/P`(전처리만) 옵션으로
돌려서 실제 전처리 결과를 봤습니다**(컴파일/링크는 안 함, 순수 읽기 진단).

결과: 파일 맨 끝의 `IMPLEMENT_MODULE(FRtspEncoderModule, RtspEncoder)`가 **매크로 확장이
전혀 안 된 채로 그대로** 출력에 남아있었습니다 — `IMPLEMENT_MODULE`이 매크로로 인식조차
안 됐다는 뜻. 원인은 아주 단순했습니다: `RtspEncoderModule.h`가
`#include "Modules/ModuleInterface.h"`(``IModuleInterface`` 베이스 클래스만 있음)만
넣고, **`IMPLEMENT_MODULE` 매크로가 실제로 정의된 `Modules/ModuleManager.h`를 빼먹었습니다.**
정의 안 된 `IMPLEMENT_MODULE(...)`가 파일 스코프에서 함수 호출처럼 보이는 구문으로
남으면서 `RtspEncoder`에서 파서가 막히고 EOF까지 회복을 못 한 것 — GError/매크로
이스케이핑/`/Zc:preprocessor` 등 그동안의 정황 추리는 다 헛다리였고 그냥 헤더 하나
빠뜨린 실수였습니다. `#include "Modules/ModuleManager.h"` 추가로 해결.

**교훈**: 애매한 컴파일러 증상이 계속 재현되는데 정황 추리로 못 찾겠으면, 다음번엔 바로
`cl.exe /P`로 실제 전처리 결과를 까봐야 한다 — 훨씬 빠르게 찾았을 것.

---

## 1.6. 4라운드 컴파일 수정 (3차 에러 로그 기반)

3라운드 수정 후 다시 빌드하니 앞선 에러들(wrl.h, HAL/Runnable.h, 삼항연산자, ConstructorHelpers)은
전부 없어졌고, 남은 건 두 가지:

1. **glib 헤더의 `#if defined(__GNUC__)` / `__clang_major__` / `__SUNPRO_C` 이식성 체크가
   전부 C4668("정의 안 된 매크로, 0으로 취급")로 잡힘** — MSVC에서는 당연히 저것들이
   안 잡히는 게 정상인데, UE 기본 경고 레벨이 이걸 에러로 승격시킴. glib 잘못도 우리 코드
   잘못도 아니고 순전히 "GLib를 MSVC에 물릴 때 항상 나는" 종류라, `RtspEncoder.Build.cs`에
   `CppCompileWarningSettings.UndefinedIdentifierWarningLevel = WarningLevel.Off;` 추가해서
   이 모듈에서만 꺼둠(UE5.6+ API, 예전엔 `bEnableUndefinedIdentifierWarnings`였음).
2. **`RtspEncoderModule.cpp:88`(`IMPLEMENT_MODULE` 줄)에서 계속 나던 "식별자 'RtspEncoder'"
   구문 에러 + 파일 끝 EOF 에러** — 3라운드까지 원인을 못 찾았는데, 유력한 범인을 찾은 것
   같습니다: `RTSPENCODER_GST_ROOT_DIR` 매크로 값이 `C:\Program Files\gstreamer\...`처럼
   **공백 + 백슬래시가 같이 있는 경로**라, C# → UBT 응답 파일 → cl.exe `/D`로 넘어가는
   여러 겹 이스케이핑을 거치면서 깨졌을 가능성이 높습니다(문자열 리터럴이 안 닫힌 채로
   이후 줄들을 계속 집어삼키면 딱 이런 "한참 뒤에서 EOF" 증상이 남). `Build.cs`에서 이
   매크로 값을 백슬래시 대신 **슬래시**(`C:/Program Files/...`)로 바꿨습니다 — Windows API는
   슬래시도 그대로 받아들이고, 이스케이핑 겹이 훨씬 단순해집니다. 100% 확신은 아니지만
   가장 유력.

---

## 1.5. 3라운드 컴파일 수정 (2차 에러 로그 기반)

`bUseUnity = false` + 2라운드 수정(§2.1) 후 다시 빌드하니 GError/nesting 계열은 없어졌지만,
새로운(가려져 있던) 에러 4종류가 나왔습니다:

1. **`<wrl.h>`의 `implements.h`/`module.h`/`corewrappers.h`에서 여전히
   `TRUE`/`FALSE`/`InterlockedCompareExchange` 못 찾음** — `<windows.h>`를 명시적으로 앞에
   추가해도 여전히 발생. 원인: UE가 프로젝트 전체에 `WIN32_LEAN_AND_MEAN`을 컴파일러 플래그로
   강제하기 때문에, "평범하게 `<windows.h>`를 include"해도 NVIDIA 샘플이 기대하는 "완전한"
   windows.h가 아님. **해결**: `NvEncoderD3D12.h`는 사실 `Microsoft::WRL::ComPtr`만 쓰는데,
   무거운 `<wrl.h>`(WinRT COM 서버 활성화 기능 전체 포함, `implements.h`/`module.h` 포함)
   대신 **`<wrl/client.h>`**(ComPtr만 제공, 그 두 개 헤더 안 끌어옴)로 교체. NVIDIA 샘플이
   원래 무겁게 `<wrl.h>`를 쓴 것뿐이라 기능 손실 없음.
2. **`RtspServerSubsystem.cpp`: `FRunnable` 기본 클래스 미정의** — 제가 단순히
   `#include "HAL/RunnableThread.h"`만 넣고 `#include "HAL/Runnable.h"`(FRunnable 클래스
   본체)를 빼먹었습니다. 추가함.
3. **`NvEncoderD3D12.cpp:400`: 삼항연산자 공통 타입 모호** —
   `bOutputDelay ? m_iToSend - m_nOutputDelay : m_iToSend` 에서 `m_iToSend`가
   `std::atomic<int32_t>`라, 두 분기 타입(`int32_t` vs `atomic<int32_t>`)이 UE5.8의 더 엄격한
   conformance 모드에서 모호하다고 판단됨(NVIDIA 원본 개발 환경에선 통과했을 것). `else` 분기를
   `m_iToSend.load()`로 명시 — 값은 동일, 타입만 명확화.
4. **`RtspPocTestActor.cpp`: `ConstructorHelpers::FObjectFinder<UStaticMesh>`가
   `TObjectPtr<UStaticMesh>`를 `UObject*`로 변환 못 함** — `Components/StaticMeshComponent.h`는
   `UStaticMesh`를 전방선언만 하는데, `TObjectPtr`의 상위 클래스(UObject) 캐스팅은 완전한
   타입 정의가 있어야 컴파일러가 상속 관계를 확인할 수 있습니다. `#include "Engine/StaticMesh.h"`
   추가로 완전한 정의를 가져옴.

추가로 `RtspEncoderModule.cpp`에서 `#undef GError`를 파일 맨 끝(`IMPLEMENT_MODULE` 이후)이
아니라 **마지막으로 실제 쓰는 지점 직후**로 당겨왔습니다 — `IMPLEMENT_MODULE(FRtspEncoderModule,
RtspEncoder)` 줄에서 "식별자 'RtspEncoder'" 구문 에러가 났는데 정확한 인과관계를 100%
확신하진 못했지만(제 매크로 치환 로직상 `RtspEncoder` 토큰 자체와는 안 부딪혀야 정상), 범위를
좁혀두는 게 안전해서 방어적으로 조치. **이 특정 에러는 재현/원인이 애매하니, 다시 떠도 알려주시면
좋겠습니다.**

---

## 2. Third-party 코드 (vendored, 수정함)

`C:\SDK\Video_Codec_SDK_13.1.15\Samples\`에서 아래 4개 + 지원 헤더 2개를 복사해왔습니다:
`NvEncoder.h/.cpp`, `NvEncoderD3D12.h/.cpp`, `NvCodecUtils.h`, `Logger.h`, `nvEncodeAPI.h`.

**수정한 부분** (원본 로직은 안 건드림, UE에 넣기 위한 배선만):
- `NvEncoder.cpp`/`NvEncoderD3D12.cpp`의 self-include 경로를 `"NvEncoder/NvEncoder.h"` →
  `"NvEncoder.h"`로 수정 (SDK의 `Samples/NvCodec/` 트리 밖으로 파일을 옮겼으므로).
- `Logger.h`/`nvEncodeAPI.h`/`NvEncoderD3D12.h`의 `<windows.h>`/`<d3d12.h>`/`<wrl.h>`
  include는 **의도적으로 UE의 Allow/HideMicrosoftPlatformTypes.h로 안 감쌌습니다** — 아래
  1차 컴파일에서 이걸로 한 번 크게 데었습니다 (§2.1).

### 2.1 실제 컴파일해보고 고친 것 (2 라운드)

**1라운드 — "Nesting AllowWindowsPlatformTypes.h is not allowed!"**: `NvEncoderD3D12.h`에서
`#include "NvEncoder.h"`를 우리 자신의 Allow/Hide 블록 **안쪽**에 넣어놨었는데,
`NvEncoder.h`가 `Logger.h`를 거치면서 **자기 자신의** Allow/Hide를 또 열어서 중첩 위반.
`NvEncoder.h`를 Allow 블록 바깥으로 뺐음.

**2라운드 — 위 수정 후에도 `FALSE`/`InterlockedIncrement` 미선언, `GError` 재정의 폭발**:
1라운드 수정으로 nesting은 없어졌는데, 실제로 빌드해보니 훨씬 근본적인 문제가 있었습니다.
**`Microsoft/AllowMicrosoftPlatformTypes.h` → `HideMicrosoftPlatformTypes.h` 패턴은 "UE
코드가 짧게 Windows 타입을 빌려쓰고 바로 반납"하는 용도로 설계된 거지, 벤더/서드파티 코드가
파일 전체에서 `TRUE`/`FALSE`/`InterlockedIncrement`를 자유롭게 쓰는 상황엔 안 맞습니다.**
`HideWindowsPlatformTypes.h`가 `#undef TRUE` / `#undef FALSE`를 실제로 하는데(직접 확인함),
NVIDIA 샘플 코드(`NvEncoder.cpp`, `NvEncoderD3D12.cpp`)는 자기 파일 전체에서 `TRUE`/`FALSE`가
계속 살아있다고 가정하고 짜여 있어서, Hide가 끝난 뒤 나오는 코드에서 "식별자를 찾을 수
없습니다" 에러가 쏟아졌습니다. `<wrl.h>`(ComPtr)의 `InterlockedIncrement` 관련 에러도 같은
계열 — `<d3d12.h>`/`<wrl.h>`만 Allow 블록에 넣고 `<windows.h>`는 안 넣어서, `implements.h`가
필요로 하는 `InterlockedIncrement` 선언이 애초에 없었던 것도 겹쳤음(NVIDIA 원본
`AppEncD3D12.cpp`는 `<d3d12.h>` 앞에 `<windows.h>`를 명시적으로 따로 include 해둠 — 그대로
따라감).

거기에 별개로 **`GError` 이름 충돌**: UE는 `CoreGlobals.h`에 `extern FOutputDeviceError*
GError;`라는 전역 변수(치명적 에러 출력 담당)가 있는데, GLib도 정확히 같은 이름
`GError`로 **타입**(struct)을 선언합니다. 매크로 문제가 아니라 진짜 변수 vs 타입 이름
충돌이라 Allow/Hide로는 못 막고, `#define GError GstGError` ~ `#undef GError`로 그 파일
안에서만 이름을 바꿔치기했습니다.

**최종 정리된 원칙**:
- `ThirdParty/NvCodec` 안의 벤더 헤더들은 Allow/Hide로 감싸지 않고 **완전히 원본 그대로**
  (`<windows.h>`/`<d3d12.h>`/`<wrl.h>`를 평범하게 include) — 이 파일들은 `CoreMinimal.h`를
  전혀 안 쓰니 UE 매크로와 부딪힐 일이 없고, NVIDIA가 테스트한 형태 그대로 두는 게 제일
  안전.
- UE 코드와 벤더/GLib 코드가 실제로 한 파일에서 섞이는 지점(`NvencD3D12Encoder.cpp`,
  `RtspEncoderModule.cpp`, `RtspServerSubsystem.cpp`)에서는, Allow/Hide로 통째로 감싸는 대신
  **진짜 충돌나는 식별자만** `#pragma push_macro`/`pop_macro`로 국소적으로 처리:
  `check`(NVENC 쪽), `TEXT`(양쪽 다 — `<windows.h>`가 재정의하는 걸 이 파일의 이후
  `UE_LOG`/`TEXT()` 호출이 UE 버전으로 계속 쓰도록), `GError`(위 설명).
- `RtspEncoder.Build.cs`에 `bUseUnity = false` 추가 — 벤더 파일들이 `TRUE`/`FALSE`/`TEXT`를
  Hide 없이 그대로 남겨두는 설계라, Unity Build가 그 파일을 관계없는 다른 파일과 같은
  translation unit으로 합쳐버리면 그 잔여 매크로가 엉뚱한 파일로 새어나갈 수 있어서 원천
  차단.

이걸로 원래 에러 목록(GError 연쇄, FALSE/Interlocked, nesting)은 다 설명되고 고쳤는데,
**`RtspPocTestActor.cpp`의 `ConstructorHelpers::ValidateObject` 관련 에러 하나는 원인이
명확하지 않습니다** — 같은 Unity 블록에서 GError 충돌 때문에 파서가 깨지면서 생긴 연쇄
에러였을 가능성이 높다고 보고(그렇다면 위 수정으로 같이 없어질 것), `bUseUnity = false`로
분리됐으니 다시 빌드해서 이 에러가 여전히 남아있는지 확인 필요.

라이선스: NVIDIA Video Codec SDK 샘플 코드는 SDK 자체 라이선스(SDK 루트의
`License.pdf`, 여기 `ThirdParty/NvCodec/NVIDIA_License.pdf`로 같이 복사해둠) 하에 배포되는
샘플 코드입니다 — 재배포/파생 조건 최종 확인은 법무 검토 시 같이.

---

## 3. GStreamer 쪽 설계

- `RtspServerSubsystem`은 `UGameInstanceSubsystem`이라 **PIE 세션 시작/종료에 맞춰
  RTSP 서버가 뜨고 내려갑니다** (에디터 프로세스 전체 수명이 아님). PIE로 Play 누르면
  자동으로 8554 포트에서 리슨 시작.
- 각 스트림은 `gst_rtsp_media_factory_set_shared(..., TRUE)`로 등록 — 여러 RTSP 클라이언트가
  같은 mount에 붙어도 NVENC 세션은 하나만 돕니다 (클라이언트마다 별도 인코드 세션이 뜨는
  게 아님).
- appsrc 파이프라인: `appsrc name=videosrc ! h264parse config-interval=1 ! rtph264pay
  name=pay0 pt=96 config-interval=1` — `EncodeFrame()`이 이미 뱉는 Annex-B 비트스트림을
  그대로 `gst_app_src_push_buffer`에 넣습니다, 별도 리패키징 없음.
- 콘솔 커맨드 `RtspPoc.SpawnTestActors [count]` 로만 액터가 생성됩니다 — 플러그인이
  로드된다고 자동으로 뭔가 스폰하지 않음(다른 트랙 안 건드리는 원칙 지키려고 opt-in으로
  설계).

---

## 4. D3D12 zero-copy 흐름 (`NvencD3D12Encoder::EncodeFrame`)

렌더 스레드에서, `RHICmdList`(UE가 관리하는 커맨드 리스트) 위에:
1. SceneCapture 렌더타겟(`FRHITexture`)을 `ERHIAccess::CopySrc`로 전이
2. `ID3D12DynamicRHI::RHIGetGraphicsCommandList()`로 UE의 **네이티브 D3D12 커맨드 리스트**를
   얻어서, 거기에 직접 `CopyResource(NVENC 입력버퍼, SceneCapture 텍스처)` 삽입 — 우리
   전용 커맨드 큐를 따로 안 만들고 UE 큐에 얹으므로, "SceneCapture 렌더가 끝난 다음에
   복사해야 한다"는 순서 보장이 자동으로 됩니다 (수동 큐간 동기화 불필요).
3. 렌더타겟을 다시 `ERHIAccess::RTV`로 전이 (다음 틱 재캡처 대비)
4. `ID3D12DynamicRHI::RHISignalManualFence()`로 NVENC 전용 fence를 UE 커맨드 스트림
   안에서 시그널 — `NvEncoderD3D12`가 내부적으로 이 fence를 GPU-wait 조건으로 걸어두므로
   (`NvEncoderD3D12.cpp`의 `MapResources()`), NVENC 하드웨어가 복사 완료를 GPU에서
   기다립니다. **CPU 스톨 없음.**
5. `NvEncoderD3D12::EncodeFrame()` 호출 → Annex-B 패킷 0개 이상 받음(파이프라인 채워지는
   중이면 처음 몇 프레임은 0개가 정상).

**픽셀 포맷 가정**: `NV_ENC_BUFFER_FORMAT_ARGB`(메모리상 B,G,R,A 순서, `nvEncodeAPI.h`
주석으로 확인함)가 `DXGI_FORMAT_B8G8R8A8_UNORM` = UE의 기본 렌더타겟 포맷(`PF_B8G8R8A8`)과
바이트 순서가 정확히 일치합니다. `RtspPocTestActor`는 `RTF_RGBA8`(=PF_B8G8R8A8)로 렌더타겟을
만들어서 이 가정에 맞춰뒀는데, **다른 포맷(HDR float 등)의 렌더타겟을 넣으면 색이 깨지거나
`NvEncoderD3D12` 등록 단계에서 예외가 날 것**입니다.

---

## 5. 빌드 전 필요한 것 (설치 확인됨)

| 항목 | 경로 | 용도 |
|---|---|---|
| CUDA Toolkit v13.3 | `C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.3` | **실제로 안 씀** (§0) |
| NVIDIA Video Codec SDK 13.1.15 | `C:\SDK\Video_Codec_SDK_13.1.15` | 헤더+샘플 소스 (vendored 완료), `nvencodeapi.lib` 링크 |
| GStreamer (MSVC x86_64, Complete) | `C:\Program Files\gstreamer\1.0\msvc_x86_64` | gst-rtsp-server 등 링크 + 런타임 DLL |
| VLC | 기본 설치 경로 | RTSP 재생 테스트 |

Build.cs는 이 경로들을 하드코딩 기본값으로 두되, 환경변수(`NVIDIA_VIDEO_CODEC_SDK_DIR`,
`GSTREAMER_1_0_ROOT_MSVC_X86_64`)로 오버라이드 가능하고, 없으면 `BuildException`으로 바로
에러 메시지를 냅니다(조용히 실패하지 않음).

---

## 6. 테스트 절차

1. UE 에디터에서 `titan_example` 컴파일 (Live Coding 또는 에디터 재시작으로 새 플러그인
   반영).
2. 아무 레벨이나 PIE로 Play.
3. 콘솔 열고(`~`) `RtspPoc.SpawnTestActors 1` 입력 — 회전 큐브 액터 하나 스폰,
   `rtsp://127.0.0.1:8554/poc/stream0`로 송출 시작.
4. VLC → 미디어 → 네트워크 스트림 열기 → 위 URL 입력 → 재생 확인.
5. 되면 로그(`LogRtspEncoder`)에서 해상도/비트레이트 로그 확인, VLC 쪽 지연시간/프레임
   드랍 체감 확인.
6. **5/7 스트림 스케일 테스트**: PIE 중지하고 다시 Play, `RtspPoc.SpawnTestActors 7` 로
   7개 동시 스폰 (`poc/stream0`~`poc/stream6`), 태스크 관리자로 GPU 인코더 사용률
   (NVENC는 GPU 사용률 그래프에 별도 "Video Encode" 엔진으로 보임)/CPU, PIE의 프레임레이트
   변화 관찰. VLC를 여러 창 띄워서 몇 개까지 동시 재생해도 끊기지 않는지 확인.

### 6.1. 7-스트림 동시 재생 테스트 — 결과 (2026-08-07)

§1.22까지 반영된 코드로, PIE에서 `RtspPoc.SpawnTestActors 7`로 7개 스트림을 띄운 뒤
VLC 7개를 각각 `poc/stream0`~`poc/stream6`에 연결(VLC는 명령줄로 일괄 실행). 결과:

- **7개 전부 정상 재생**(연결 끊김 없음, 각자 다른 큐브가 정상적으로 회전) — 사용자 확인.
- **UE 프레임레이트 70+ 유지**, 체감상 부하 거의 없음(사용자 표현: "부하가 거의 없어보여서
  일단 껐음"). §5에서 이전에 측정했던 수치 부하 테스트(NVENC avg 10%/peak 24%, CPU
  ~38.6%)와도 일치하는 결과 — 이번엔 그 수치가 재생이 실제로 안정적인 상태에서 나온
  결과라는 점이 다름(§1.19 이전엔 재생 자체가 불안정해서 수치만 측정하고 시각 확인은
  못 했었음).
- 이 작은 테스트 레벨(회전 큐브) 기준으로는 5~7 스트림 동시 송출에 여유가 있는 것으로
  보임. 실제 UGV/자체방호축 씬(더 무거운 레벨)에서도 같은 수준일지는 별개로 확인 필요 —
  이 PoC는 인코드/전송 파이프라인 자체의 건전성 확인이 목적이라, 씬 렌더링 부하 자체는
  스코프 밖.

---

## 7. 컴파일 시 걸릴 가능성이 높은 지점 (우선순위순, 2라운드 수정 반영) — [해결됨, 기록용]

**이 섹션은 최초 컴파일 성공 이전(1~2라운드 빌드 수정 단계)에 작성된 예상 목록입니다.
플러그인은 이후 여러 차례 정상 컴파일/실행되었고, 단일 스트림 RTSP PoC(연결·재연결·재생)도
2026-08-07에 성공 확인됐습니다 — 아래 항목들은 실제로 다 지나간 이슈들의 기록이며,
당시 예상했던 순서대로 전부 해결된 건 아니고 §1.x의 실제 크래시/버그 기록(특히 §1.7~
§1.22)이 진짜 있었던 문제들의 정확한 순서/원인입니다. §1.x 쪽을 우선 참고하세요.**

1차 빌드에서 실제로 걸렸던 nesting/`GError`/`FALSE`/`InterlockedIncrement` 계열은 §2.1
수정으로 해결됐다고 보고 있습니다(다음 빌드로 확인 필요). 남은 건 전부 **아직 한 번도
컴파일 성공을 못 봐서 진짜 검증이 안 된** 지점들 — 순서대로 의심해보면 좋습니다:

1. **`RtspPocTestActor.cpp`의 `ConstructorHelpers::ValidateObject` 에러 재발 여부** — 1차
   빌드 로그에 있었는데, 같은 Unity 블록에서 `GError` 충돌로 파서가 깨지면서 생긴 연쇄
   에러였을 가능성이 높습니다(§2.1 끝부분). `bUseUnity = false`로 파일이 분리됐으니, 이게
   여전히 남아있으면 진짜 별개 원인 — `FObjectFinder<UStaticMesh> CubeMeshAsset(TEXT("/Engine/BasicShapes/Cube.Cube"))`
   자체는 UE5 표준 패턴이라 의심스러우면 알려주세요.
2. **D3D12 리소스 상태 전이 가정** (§4) — SceneCapture 렌더타겟의 "캡처 직후 상태"를
   `ERHIAccess::Unknown`(이전 상태 모름, RHI가 알아서 처리)으로 가정하고
   `ERHIAccess::CopySrc`로 전이 요청했습니다. RHI 검증 레이어(Debug 빌드)가 assert를
   던지면, 캡처 직후 실제 트래킹된 access 상태를 확인해서 `ERHIAccess::Unknown` 대신
   정확한 이전 상태(예: `ERHIAccess::SRVMask`)로 바꿔야 할 수 있습니다.
3. **GStreamer 헤더/링크 경로** — `RtspEncoder.Build.cs`가 `Directory.Exists`/`File.Exists`로
   미리 체크해서 없으면 명확한 `BuildException` 메시지를 내도록 해뒀으니, 이 종류 에러는
   메시지 읽으면 바로 원인 알 수 있을 것.
4. **`D3D12RHI` 모듈 의존성** — 엔진 내부 모듈이라 플러그인에서 끌어다 쓰는 게 버전마다
   미묘하게 다를 수 있음. 링크 에러(`RHIGetResource` 등 미해결 심볼) 나면 이 모듈 관련.
5. **`TEXT`/`check`/`GError` push_macro 처리가 실제로 다른 파일까지 안전한지** — §2.1에서
   설명한 방식이 이론적으로는 맞지만, 이 조합(UE + 벤더 NVENC + GLib를 한 모듈에서, Unity
   Build 끄고 push_macro만으로) 자체가 흔한 패턴이 아니라 다른 조합의 에러가 또 나올
   가능성 있음. 나오면 어느 파일/어느 줄인지, 어떤 식별자인지 보고 같은 방식(진짜 충돌하는
   식별자만 push_macro)으로 대응.
6. **appsrc/media-configure 스레드 레이스** — 클라이언트가 붙었다 끊기는 타이밍에 따라
   `RtspServerSubsystem.cpp`의 `AppSrc` 포인터 처리가 이론상 레이스 가능성 있음(문서화는
   해뒀지만 완전히 막지는 않음, PoC 스코프). 컴파일은 되는데 특정 상황(클라이언트 재연결
   반복 등)에서 크래시하면 여기부터 볼 것.

---

## 8. 프로덕션 패키징 시 남는 일 (지금은 안 함)

- GStreamer DLL들이 이 PC의 `C:\Program Files\gstreamer\...`를 직접 가리키게 되어 있음
  (`RtspEncoder.Build.cs`/`RtspEncoderModule.cpp`) — 다른 PC에 배포하려면 필요한 DLL/플러그인
  세트를 패키징된 빌드의 `Binaries\` 옆에 실제로 복사해 넣는 작업 필요 (LGPL 조건과도
  맞물림, `protocol_icd.md` §7 참고).
- RTSP URL 스킴/포트(`/poc/streamN` 임시) — 실제 UGV 5개/자체방호 7개 축 이름 매핑은
  `protocol_icd.md` §3.4/4.4의 잠정안(`rtsp://<console-host>:8554/<axis>/<stream>`)대로
  갈지 §6 미확정 항목 확정되는 대로 반영.
- 지금은 `RtspPocTestActor`(회전 큐브)만 연결돼 있음 — 실제 UGV/자체방호축 카메라
  (QuadCamModule의 SceneCaptureComponent2D들, RCWS 뷰어 등)에 `URtspStreamComponent`를
  붙이는 건 이 PoC가 실제로 동작 확인된 다음 단계.

---

## 9. 다음 액션

**1단계(PoC) 완료**: 단일 스트림(연결/재연결/재생, 2026-08-07) + 7-스트림 동시 송출
(§6.1, 2026-08-07, VLC 7개 전부 정상 재생·UE 70+fps·저부하) 둘 다 사용자 확인 완료.

남은 건 §8(프로덕션 패키징 시 남는 일)에 정리된 항목들 — GStreamer DLL 배포 패키징,
RTSP URL 스킴/포트 확정, 실제 UGV/자체방호축 카메라(QuadCamModule 등)에
`URtspStreamComponent` 연결 — 로, 이건 사용자와 우선순위 상의 후 진행.

이후 회사 쪽 요청으로 **크로스플랫폼(Windows+Linux) 지원**이 새 트랙으로 결정됨 — §10 참고.

---

## 10. 크로스플랫폼(Linux) 지원 — 진행 현황

### 10.1. Phase 0 — WSL2로 로컬 사전검증 (2026-08-14)

리눅스 테스트 컴퓨터가 회사 다른 곳에 있어서 자주 테스트를 못 하는 제약 때문에, 원격
접속 없이 이 Windows 개발 머신의 WSL2(Ubuntu 24.04, 타겟 우분투 버전과 일치)로 최대한
사전검증부터 함. 결과:

| 레이어 | 결과 |
|---|---|
| NVENC 하드웨어 (SDK `NvEncoder` 직접 호출, P1-P7 프리셋 — 우리가 실제 쓰는 방식) | ✅ WSL2 GPU 패스스루로 정상 동작 확인 |
| GStreamer + gst-rtsp-server 서빙 (appsrc→h264parse→rtph264pay, 우리 파이프라인과 동일 구조) | ✅ Windows↔WSL2 네트워크 경계 넘어 정상 스트리밍 확인 |
| UE Vulkan RHI 렌더링 | ❌ WSL2 불가 확정 — Vulkan ICD가 `dzn`(Mesa의 D3D12 변환 레이어, 스스로 "non-conformant, testing use only"라고 명시)뿐이고, 네이티브 NVIDIA Vulkan ICD(`nvidia_icd.json`은 파일상 존재)로 강제해봐도 "Failed to detect any valid GPUs"로 실패. 원격 우분투 박스(진짜 드라이버) 몫으로 확정. |

검증 방법 메모:
- 처음에 GStreamer 자체의 `nvh264enc`(gst-plugins-bad의 `nvcodec`) 엘리먼트로 NVENC를
  찔러봤다가 "Selected preset not supported"로 실패 — 이건 NVIDIA가 R550+ 드라이버부터
  구형 프리셋 GUID 지원을 끊은 것과 관련된, **GStreamer의 그 엘리먼트 자체에 국한된
  별개 버그**([GStreamer Discourse](https://discourse.gstreamer.org/t/nvcodec-nvenc-nvidia-deprecates-support-for-old-videocodec-sdk-h-264-hevc-encoder-presets-with-driver-r550-in-q124/182))로
  확인됨 — 우리 플러그인은 이 엘리먼트를 안 쓰므로 무관. 깨끗한 새 WSL 배포판에서도
  재현되어(환경 오염 아님) 이 결론을 재확인.
- 진짜 판단 기준은 NVIDIA Video Codec SDK의 `AppEncCuda` 샘플을 WSL 안에 CUDA 툴킷 설치
  후 직접 빌드해서, 우리 Windows 코드와 동일한 옵션(`-preset p3 -tuninginfo lowlatency
  -rc cbr`, `NV_ENC_PRESET_P3_GUID`+`NV_ENC_TUNING_INFO_LOW_LATENCY`와 동일)으로 돌려본
  것 — 30프레임 전부 정상 인코딩, ffprobe로 디코딩까지 확인.
- RTSP 서빙은 그 결과물을 실제 우리 launch 문자열 그대로 쓰는 작은 C 테스트 서버
  (`test_rtsp_appsrc.c`)를 WSL 안에서 컴파일+실행해서, Windows의 ffprobe로
  `rtsp://127.0.0.1:8555/...`에 접속해 확인(WSL2 localhost 포워딩으로 접속 잘 됨).

### 10.2. Phase 1 — 빌드 시스템 크로스플랫폼화 (2026-08-14)

**중요한 발견**: 이 프로젝트의 리눅스 패키징은 실제 우분투 머신에서 빌드하는 게
아니라, 이 Windows 컴퓨터에서 UE가 번들 제공하는 크로스컴파일 툴체인
(`LINUX_MULTIARCH_ROOT=C:\UnrealToolchains\v26_clang-20.1.8-rockylinux8\`, RockyLinux8
기반 sysroot, glibc 2.28)으로 빌드한 뒤 옮겨서 테스트하는 방식임(사용자 확인). 이
sysroot엔 당연히 GStreamer가 없고, **Build.cs가 실행되는 시점(=이 Windows 컴퓨터)엔
진짜 리눅스 `pkg-config`를 실행할 방법이 없음** — Phase 0에서 WSL로 검증했던
`pkg-config` 방식은 이 크로스컴파일 워크플로우엔 그대로 못 씀.

**해결 방식**: Windows가 이미 쓰고 있는 패턴(로컬에 GStreamer를 설치해두고 Build.cs가
그 경로의 헤더/lib를 직접 참조, env var로 오버라이드 가능)을 리눅스에도 그대로 적용 —
pkg-config 라이브 조회 대신 **로컬에 vendoring된 GStreamer Linux 헤더+`.so` 번들**을
씀. 이 번들은 Phase 0에서 쓴 WSL Ubuntu 24.04(GStreamer 1.24.2, 실제 타겟 우분투
버전과 일치)에서 뽑아냄:

- 번들 위치: `C:\SDK\gstreamer-1.24.2-linux-x86_64\`(env var
  `GSTREAMER_1_0_ROOT_LINUX_X86_64`로 오버라이드 가능 — Windows의
  `GSTREAMER_1_0_ROOT_MSVC_X86_64`와 같은 패턴).
- 내용: `include/{gstreamer-1.0, glib-2.0, glib-2.0-arch, gio-unix-2.0}` +
  `lib/libgst{reamer,base,app,rtsp,rtspserver,sdp,net}-1.0.so` +
  `lib/lib{glib,gobject,gio,gmodule}-2.0.so`(전부 심볼릭 링크 체인을 `cp -L`로
  dereference해서 실제 파일로 뽑음 — NTFS/WSL↔Windows tar 전송 경계에서 다단계
  symlink가 깨지는 문제가 있었음).
- 재현 스크립트: `C:\SDK\gstreamer-1.24.2-linux-x86_64\make_bundle.sh` (WSL Ubuntu
  안에서 실행하면 같은 번들을 다시 만들 수 있음 — 버전 올릴 때나 다른 배포판 기준으로
  다시 뽑을 때 참고).
- **주의**: 이 번들은 **크로스컴파일 시점의 링커를 만족시키기 위한 것**이지, 실제
  타겟 리눅스 머신에 배포되는 게 아님. 최종 바이너리는 `libgstreamer-1.0.so.0` 같은
  SONAME으로 링크되고, 실제 실행 시점엔 타겟 머신에 진짜 설치된(apt 등) GStreamer가
  그걸 채워줌 — 그래서 타겟 머신의 GStreamer가 이 번들과 호환되는 버전이어야 함(지금은
  둘 다 Ubuntu 24.04/GStreamer 1.24.2 기준으로 맞춰둠).

**수정한 파일**:
- `RtspEncoder.uplugin`: `PlatformAllowList`에 `"Linux"` 추가.
- `RtspEncoder.Build.cs`: `Target.Platform == UnrealTargetPlatform.Linux` 분기 추가 —
  위 번들 경로 확인 후 헤더/lib 연결, `RTSPENCODER_HAS_GSTREAMER=1` /
  `RTSPENCODER_HAS_NVENC=0`(NVENC는 아직 — 아래 Phase 2 참고). Windows처럼
  `PublicDelayLoadDLLs`를 쓰지 않고 그냥 일반 링크(`PublicAdditionalLibraries`)로
  처리 — delay-load는 PE(Windows) 전용 개념이라 리눅스에선 필요도 없고 해당도 안 됨.
- `RtspEncoderModule.cpp`: `StartupModule()`의 Windows 전용 DLL 검색 경로/GST_PLUGIN_PATH
  설정 로직을 `#if PLATFORM_WINDOWS`/`#elif PLATFORM_LINUX`로 분리. 리눅스 쪽은 **아무
  것도 안 함**(진짜 타겟 머신에 정상 설치된 GStreamer라면 `gst_init_check()`가 시스템
  기본 플러그인 스캔 경로에서 알아서 다 찾음 — Phase 0에서 WSL로 이미 확인된 사실).
  빌드 시점 번들 경로(`RTSPENCODER_GST_ROOT_DIR`)를 런타임 플러그인 경로로 착각해서
  쓰면 안 됨 — 그 경로는 "이 바이너리를 빌드한 Windows 머신"의 경로지 "이 바이너리가
  실행되는 리눅스 머신"의 경로가 아니므로 완전히 의미 없는 값이 됨(코드 주석으로 남겨둠).
- `RtspStreamComponent.cpp`/`NvencD3D12Encoder.*`는 이미 `#if RTSPENCODER_HAS_NVENC`로
  깔끔하게 게이팅돼 있어서 수정 불필요 — 리눅스에선 자동으로 "이 플랫폼에서 NVENC 지원
  안 함" 에러 로그 경로를 탐(기존에 있던 else 분기 그대로 재사용).

**아직 안 한 것 / 검증 안 된 것**:
- 이 세션은 UBT/Build.bat를 실행하지 않는다는 스탠딩 룰 때문에 **실제 크로스컴파일을
  돌려보지 않았음** — 사용자가 평소 하던 "Linux로 패키징" 절차로 직접 컴파일해서 에러
  나오면 알려줘야 함.
- NVIDIA SDK 쪽 헤더(`ThirdParty/NvCodec/Interface`, `Utils`)가 이 크로스컴파일
  툴체인(clang, glibc 2.28)에서 별문제 없이 파싱되는지도 미검증 — Windows 전용으로
  작성된 부분(`NvEncoderD3D12.h` 등)은 `RTSPENCODER_HAS_NVENC=0`이라 애초에 컴파일
  대상에서 빠지므로 문제 없어야 하지만, 확인은 필요.

### 10.2.1. 첫 실제 크로스컴파일 시도 — `RTSPENCODER_HAS_NVENC=0`만으로는 부족했음 (2026-08-14)

사용자가 `titan_example.uproject`에서 `RtspEncoder`를 `Enabled: true`로 켜고(잠깐
`false`였던 걸 되돌림) 실제 "Linux로 패키징"을 돌려봄 — 결과: GStreamer 쪽 파일들
(`RtspEncoderModule.cpp`, `RtspServerSubsystem.cpp`, `RtspStreamComponent.cpp`,
`RtspPocTestActor.cpp`, `RtspPocCommands.cpp`)은 **전부 정상 컴파일** — Phase 1의
GStreamer 번들/Build.cs 분기가 실제로 동작함을 처음으로 확인. 하지만 두 가지 에러로
전체 빌드는 실패:

1. **`NvEncoderD3D12.cpp`가 리눅스에서도 컴파일 시도됨** → `fatal error: 'windows.h'
   file not found`. 원인: `RTSPENCODER_HAS_NVENC=0`은 **매크로**라서 코드 안에서
   `#if`로 걸러내는 것만 되지, UBT 자체는 이 매크로를 모르고 `Source/` 밑의 `.cpp`
   파일을 전부 무조건 컴파일 시도함 — `NvencD3D12Encoder.cpp`도 `RtspStreamComponent.h`가
   무조건(`#if` 없이) `#include "NvencD3D12Encoder.h"` 하고 있어서 같이 걸림.
2. **`NvEncoder.cpp`(플랫폼 무관 베이스 클래스)의 실제 버그** — 생성자 초기화 리스트
   순서가 멤버 선언 순서와 안 맞아서 `-Werror=reorder` 에러. MSVC는 기본적으로 이걸
   경고조차 안 띄워서 지금까지 Windows에서는 드러난 적이 없었음 — clang(리눅스
   툴체인)이 더 엄격해서 처음 걸림.

**수정**:
- UBT의 "경로에 `Windows`/`Linux`/`Mac` 같은 세그먼트가 있으면 해당 플랫폼 아닌 빌드는
  자동으로 그 파일을 제외" 규칙을 이용 — `p4 move`로 다음 파일들을 `Windows/`
  서브폴더로 이동:
  - `Private/NvencD3D12Encoder.cpp` → `Private/Windows/NvencD3D12Encoder.cpp`
  - `Public/NvencD3D12Encoder.h` → `Public/Windows/NvencD3D12Encoder.h`
  - `ThirdParty/NvCodec/NvEncoder/NvEncoderD3D12.{cpp,h}` →
    `ThirdParty/NvCodec/NvEncoder/Windows/NvEncoderD3D12.{cpp,h}`
  - `RtspEncoder.Build.cs`의 Win64 분기에 `PrivateIncludePaths.Add(...NvEncoder/Windows)`
    추가(이동한 `NvEncoderD3D12.h`를 `NvencD3D12Encoder.cpp`가 계속 찾을 수 있도록).
- `RtspStreamComponent.h`의 `#include "NvencD3D12Encoder.h"`와
  `TSharedPtr<FNvencD3D12Encoder> Encoder;` 멤버를 `#if RTSPENCODER_HAS_NVENC`로 감쌈
  (이동한 헤더 경로도 `"Windows/NvencD3D12Encoder.h"`로 갱신). `RtspStreamComponent.cpp`의
  `EndPlay()`에서 그때까지 게이팅 안 돼 있던 `Encoder` 참조 4줄도 같이 감쌈(다른
  두 군데, `SetupEncoderAndStream()`/`TickComponent()`는 이미 게이팅돼 있었음).
- `NvEncoder.cpp`의 생성자 초기화 리스트를 `NvEncoder.h`의 실제 멤버 선언 순서와
  똑같이 재배열 — 텍스트 순서만 바뀌는 거라(멤버는 항상 선언 순서대로 초기화되므로)
  동작은 그대로, MSVC/clang 둘 다에서 경고/에러 없이 컴파일되게 함.

**교훈**: UE 플러그인에서 `RTSPENCODER_HAS_NVENC` 같은 자체 매크로로 플랫폼별 코드를
껐다고 해서 그 파일이 다른 플랫폼에서 컴파일 자체가 안 되는 건 아님 — UBT는 매크로를
모르고 `Source/` 전체를 훑어서 발견되는 `.cpp`를 전부 컴파일 시도함. 진짜로 파일을
빼려면 `Windows/`류 이름의 서브폴더에 넣는 자동 제외 규칙을 써야 함. 헤더 쪽도
"매크로로 감싼 `#include`"가 아니라 "무조건 `#include`"로 돼 있으면 같은 문제가
전파되니, 플랫폼 전용 타입을 멤버로 쓰는 헤더는 그 멤버 선언 자체도 매크로로 감싸야 함.

**검증 결과**: 재시도에서 `NvencD3D12Encoder.cpp`(이동한 파일 자신)의
`#include "NvencD3D12Encoder.h"`가 새 경로로 안 고쳐진 채 남아있던 실수 하나가 더
있었음(`Windows/NvencD3D12Encoder.h`로 수정) — 그 외 이동한 파일들의 include는 전부
재확인해서 문제없음 확인. 이후 **Windows 빌드 성공 확인 → Linux 패키징도 성공 확인**
(`kadex_new_0814_2`, 2026-08-14 23:32) — 매니페스트에 `RtspEncoder.uplugin`이 실제로
포함되어 있고 바이너리 안에도 `RtspEncoder` 문자열이 존재함을 확인, §10.2 초반의
"Enabled: false라서 사실은 테스트 안 됐던" 가짜 성공과 달리 이번엔 플러그인이 진짜
포함된 채로 성공. **Phase 1(빌드 시스템 크로스플랫폼화) 완료.**

### 10.3. Phase 2 — 렌더-인코더 연동 재구현 (2026-08-14 작성, 2026-08-15 컴파일 성공 — §10.3.1)

**출발점에서 바뀐 것**: SDK에 `NvEncoderVulkan`은 없음(확인 완료) — 있는 건
`NvEncoderCuda`뿐이라, 실제 아키텍처는 "Vulkan 렌더 → CUDA 인코드"를 잇는 브릿지.
SDK의 `Samples/AppEncode/AppMotionEstimationVkCuda` 샘플이 정확히 이 패턴(Vulkan
`VK_KHR_external_memory`로 이미지를 export → CUDA가 `cuImportExternalMemory`로
import)을 보여줘서 그대로 참고함.

**UE 쪽 연동점**: `IVulkanDynamicRHI.h`(D3D12 때 `ID3D12DynamicRHI.h`에 대응)에 필요한
게 다 있음 — `RHIGetVkImage(Texture)`(=`RHIGetResource`), `RHIGetVkDevice()`/
`RHIGetVkPhysicalDevice()`, `RHIGetVkCommandBuffer(ExecutingCmdList)`(=
`RHIGetGraphicsCommandList`). **단, `RHISignalManualFence`에 대응하는 게 없음** — 대신
`RHIRunOnQueue(QueueType, TFunction<void(VkQueue)>, bWaitForSubmission)`이라는, 플러그인이
자기 커맨드버퍼를 직접 만들어 큐에 제출하는 훅이 있어서 이걸로 동기화 설계를 다시 함.

**아키텍처(매 프레임)**:
1. UE SceneCapture 렌더타겟(평범한 VkImage, export 불가) → **우리가 직접 만든 export
   가능 VkImage**로 `vkCmdCopyImage` — `RHIRunOnQueue(..., bWaitForSubmission=true)`로
   완전히 별도의, 우리가 직접 submit/fence-wait까지 하는 자체 커맨드버퍼를 씀. UE의
   공유 커맨드버퍼(EnqueueLambda 방식)에 얹지 않은 이유: 거기 얹으면 D3D12의
   `RHISignalManualFence` 같은 "이 지점에서 GPU가 신호를 보낸다"에 대응하는 게 없어서
   "언제 다 됐는지" 알 방법이 없음. `RHIRunOnQueue`+블로킹 대기로 크로스 API 세마포어
   없이 단순하고 확실하게 처리 — 렌더 스레드가 매 프레임 잠깐 멈추는 대가.
2. 그 export 이미지의 메모리를 CUDA가 `CUarray`로 매핑해서 보고 있음(Initialize
   시점에 1회 import).
3. `cuMemcpy2D`로 그 `CUarray` → `NvEncoderCuda`가 자체 할당한 선형 버퍼(`GetNextInputFrame()`).
4. 이후는 D3D12 코드와 100% 동일(`Encoder->EncodeFrame(...)`, 강제 키프레임 discard 로직 등).

**진짜 미검증/리스크가 큰 지점 (실제 리눅스 박스에서 확인 전까지는 추측)**:
- **확장 등록 타이밍**: `VK_KHR_external_memory_win32`/`_fd`는 VkDevice가 만들어지기
  *전에* `IVulkanDynamicRHI::AddEnabledDeviceExtensionsAndLayers()`로 요청해둬야 함.
  플러그인의 `LoadingPhase`를 기존 `Default`에서 `PostConfigInit`("매우 low-level
  hook용"이라고 엔진 주석에 명시)으로 바꾸고 `RtspEncoderModule::StartupModule()`에서
  호출하도록 했는데, 이게 실제로 VulkanRHI의 디바이스 생성보다 먼저 실행되는지는
  검증 못 함 — 안 되면 더 이른 phase(`EarliestPossible`)가 필요할 수 있음.
- **SceneCapture 렌더타겟의 실제 Vulkan 레이아웃**: `RHIRunOnQueue`로 UE의 커맨드
  추적을 벗어난 별도 커맨드버퍼에서 직접 다루기 때문에, D3D12 때처럼 `ERHIAccess::Unknown`
  같은 "UE가 알아서 처리" 옵션이 없음. `VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL`을
  직전 레이아웃으로 가정하고 배리어를 짬 — 틀렸으면 validation layer 에러나 색/화면
  깨짐으로 나타날 가능성이 높은, 가장 먼저 의심해볼 지점.
- **VkFormat 가정**: `PF_B8G8R8A8`가 실제로 `VK_FORMAT_B8G8R8A8_UNORM`으로 만들어지는지
  (SRGB 변형이나 다른 스위즐이 아닌지) 미확인.
- CUDA 디바이스 선택은 D3D12 때(`RHIGetDevice(0)`)와 같은 수준으로 단순화 — 멀티 GPU
  환경에서 Vulkan physical device와 CUDA device가 다를 수 있는 상황은 처리 안 함(UUID
  매칭 필요, 지금은 항상 디바이스 0).

**만든/수정한 파일**:
- `Public/IRtspFrameEncoder.h` (신규) — `Initialize()`는 인터페이스에 없음(각 구현체가
  다른 네이티브 디바이스 핸들을 받으므로) — 대신 `RtspFrameEncoderFactory`가 활성 RHI를
  보고 알맞은 구현체를 만들어서 이미 초기화된 채로 반환.
- `Public/RtspFrameEncoderFactory.h` / `Private/RtspFrameEncoderFactory.cpp` (신규) —
  `IsRHID3D12()`면 `FNvencD3D12Encoder`, Vulkan이면 `FNvencVulkanEncoder`. D3D12 분기는
  `#if PLATFORM_WINDOWS`로 감쌈(그 심볼 자체가 리눅스엔 없음).
- `Public/FNvencVulkanEncoder.h` / `Private/FNvencVulkanEncoder.cpp` (신규) — 위 아키텍처
  구현. Windows/Linux 둘 다에서 컴파일됨(D3D12와 달리 `Windows/` 서브폴더에 안 넣음 —
  Linux도 이 인코더를 씀).
- `ThirdParty/NvCodec/NvEncoder/Cuda/NvEncoderCuda.{h,cpp}` (신규, SDK에서 vendoring).
- `Windows/NvencD3D12Encoder.{h,cpp}`: `IRtspFrameEncoder` 구현하도록 최소 수정
  (virtual/override 추가, 로직은 그대로).
- `RtspStreamComponent.{h,cpp}`: `TSharedPtr<FNvencD3D12Encoder>` →
  `TSharedPtr<IRtspFrameEncoder>`로 교체, D3D12 관련 include/분기 전부 제거 — 이제 이
  파일은 어느 인코더를 쓰는지 전혀 모름(Factory가 알아서 함). `#if RTSPENCODER_HAS_NVENC`
  게이팅도 다 제거됨(인터페이스 자체가 플랫폼 무관이라 필요 없어짐).
- `RtspEncoderModule.h/.cpp`: `LoadingPhase: PostConfigInit`으로 변경, `StartupModule()`에
  Vulkan 확장 등록 추가.
- `RtspEncoder.Build.cs`: CUDA 헤더/lib 연결(Windows는 로컬 CUDA Toolkit 13.3 설치 경로,
  Linux는 WSL에서 뽑은 `C:\SDK\cuda-13.3-linux-x86_64\` 번들 — GStreamer 때와 동일한
  패턴, env var `CUDA_LINUX_X86_64_DIR`로 오버라이드), `VulkanRHI` 모듈 의존성 추가
  (양쪽 플랫폼 다), 리눅스 쪽 `libnvidia-encode.so` 스텁 링크 추가. 리눅스
  `RTSPENCODER_HAS_NVENC`를 `1`로 전환.

**아직 안 한 것**: 실제 컴파일도, 리눅스/원격 박스 실행도 전혀 안 해봄 — 다음은
사용자가 Windows 빌드부터 돌려서(D3D12 경로는 코드가 안 바뀌었으니 회귀 없어야 함,
`IRtspFrameEncoder`/Factory 리팩터만 제대로 컴파일되는지가 관건) 확인, 그 다음 Linux
패키징으로 최소 컴파일 확인, 최종적으로는 원격 우분투 박스에서 실제 스트리밍까지
확인 필요.

### 10.3.1. 첫 컴파일 시도 — 실제 에러들 (2026-08-15)

Windows 빌드(`-projectfiles`)를 실행해보니 예상대로 여러 라운드의 에러가 남:

1. **Build.cs C# 컴파일 에러**: `VideoCodecSdkDir`가 Win64 `if` 블록 안에서만 선언된
   지역 변수인데 Linux 블록에서도 참조하고 있었음(스코프 실수) — Linux 블록에도 같은
   env var 기반 선언을 추가해서 해결.
2. **`vkCreateImage`/`vkCmdCopyImage` 등 전부 "식별자를 찾을 수 없음" (C3861)**: 진짜
   중요한 발견 — UE의 `VulkanThirdParty.h`가 `#define VK_NO_PROTOTYPES` 후
   `<vulkan.h>`를 include함. 즉 **UE는 core Vulkan 함수를 정적 심볼로 전혀 노출 안
   하고, 전부 동적 로드**하는 구조(내부 로더는 `VulkanRHI/Private/VulkanLoader.h` —
   플러그인에서 접근 불가). `vkCreateImage` 같은 함수를 직접 호출하는 코드는 애초에
   컴파일이 안 됨. **수정**: 필요한 core Vulkan 함수 19개를 전부
   `IVulkanDynamicRHI::RHIGetVkInstanceProcAddr`/`RHIGetVkDeviceProcAddr`로 `Initialize()`
   시점에 한 번 로드해서 멤버 함수 포인터(`Fp` 접두사)로 저장해두고, 모든 호출부를 그
   포인터를 통하도록 교체. (기존에 win32/fd 핸들 export 확장 함수 두 개만 이 방식으로
   로드했었는데, 사실 **core 함수도 전부 똑같이 해야 했음** — 처음엔 몰랐던 부분.)
3. **`cuCtxCreate_v4`: 인자 개수 안 맞음**: 벤더링한 CUDA 13.3의 `cuda.h`가
   `cuCtxCreate`를 `cuCtxCreate_v4`(4-인자, `CUctxCreateParams*` 추가됨)로 매크로
   치환 — 이전 3-인자 시그니처는 구버전 API. `nullptr`을 그 자리에 넘겨서 해결(기본
   동작 요청).
4. **`RtspFrameEncoderFactory.cpp`의 `TEXT("none")` 삼항연산자 타입 에러**:
   `FDynamicRHI::GetName()`이 이미 `const TCHAR*`를 반환하는데 `*`로 역참조해서 단일
   문자 타입이 돼버린 실수 — `*` 제거.

**교훈**: UE의 Vulkan 헤더가 `VK_NO_PROTOTYPES`라는 걸 미리 확인하지 않고 D3D12(정적
링크되는 COM 인터페이스라 그냥 호출 가능)와 같은 방식으로 코드를 짰던 게 이번 라운드
에러의 대부분을 차지함 — 다음에 비슷한 크로스 API 작업할 때는 헤더의 매크로 전제부터
먼저 확인할 것.

**검증 결과**: 재컴파일 결과 **Windows 빌드 + Linux 패키징 둘 다 성공**(2026-08-15).
Windows `UnrealEditor-RtspEncoder.dll` 재빌드 확인, Linux 바이너리는 매니페스트에
`RtspEncoder.uplugin` 포함 + 바이너리 안에 `FNvencVulkanEncoder` 심볼 존재까지 확인
(§10.2 앞부분에서 "Enabled: false라 사실 테스트 안 됐던" 가짜 성공 사례가 있었어서
이번엔 심볼까지 직접 확인). **Phase 2 코드가 두 플랫폼 모두에서 컴파일 자체는 통과.**

**중요— "컴파일된다"과 "동작한다"는 다른 얘기**: 이건 어디까지나 컴파일 통과일 뿐,
런타임 동작(특히 Vulkan/CUDA 인터롭 자체가 실제로 되는지)은 전혀 검증 안 됨.
- Windows는 `DefaultGraphicsRHI_DX12`가 기본이라 평소 플레이로는 `FNvencD3D12Encoder`
  경로만 타고, `FNvencVulkanEncoder`는 `-vulkan` 옵션으로 강제하지 않는 이상 실행 자체가
  안 됨(그래도 컴파일이 깨지지 않는다는 건 확인됨).
- §10.3에 나열해둔 미검증 리스크들(Vulkan 확장 등록 타이밍, SceneCapture 렌더타겟의
  실제 레이아웃 가정, VkFormat 가정 등)은 전부 그대로 남아있음 — 컴파일 성공은 이런
  런타임 가정들을 전혀 검증해주지 않음.
- 진짜 검증은 Phase 4(원격 우분투 박스, 진짜 Vulkan 드라이버)에서 실제로 스트리밍이
  되는지 확인해야 끝남.

### 10.3.2. SDK 없는 PC에서 빌드가 통째로 막히는 문제 → soft-fail로 전환 (2026-08-18)

다른 PC(NVIDIA Video Codec SDK 미설치)에서 titan_example을 빌드하니 `RtspEncoder.Build.cs`의
`BuildException`이 떠서 **RTSP랑 전혀 상관없는 작업을 하려는 사람의 빌드까지 프로젝트
전체가 막히는** 문제가 드러남. 플러그인을 `Enabled: false`로 꺼도 재현됐다고 함(원격
PC라 직접 디버깅은 못 했음 — P4 동기화 안 됐거나 다른 원인일 수 있음, 확인 필요하면
그 PC에서 정확히 어떤 에러가 뜨는지 다시 받아볼 것).

**근본 수정**: SDK/CUDA/GStreamer가 없어도 `BuildException`으로 전체 빌드를 막는 대신,
`Log.TraceWarning`만 찍고 그 기능만 꺼진 채(`RTSPENCODER_HAS_NVENC=0` /
`RTSPENCODER_HAS_GSTREAMER=0`) 나머지는 정상 컴파일되도록 `RtspEncoder.Build.cs`를
전면 재구성:
- 각 외부 의존성(Windows NVENC+Vulkan/CUDA, Linux NVENC+Vulkan/CUDA, Windows GStreamer,
  Linux GStreamer) 셋업을 `TrySetupXxx()` 형태의 private 메서드로 분리 — 못 찾으면 경고
  찍고 `false` 리턴, 찾으면 실제로 헤더/lib 연결하고 `true` 리턴.
- **벤더 파일들이 원래 매크로 게이팅이 전혀 안 돼 있었다는 게 진짜 문제였음** —
  `RTSPENCODER_HAS_NVENC=0`으로 lib만 안 붙이면 컴파일은 되지만 **링크 에러**
  (`NvEncodeAPICreateInstance` 등 unresolved external symbol)로 바뀔 뿐이었음.
  `NvEncoder.h/.cpp`, `NvEncoderD3D12.h/.cpp`, `NvEncoderCuda.h/.cpp` 6개 벤더 파일
  전체를 `#if RTSPENCODER_HAS_NVENC ... #endif`로 감싸서, SDK 없으면 이 파일들이
  전부 빈 translation unit으로 컴파일되게 함(우리 자신의 wrapper 파일들은 이미
  Phase 2에서 이렇게 돼 있었음 — 벤더 파일만 빠져있었던 것).
- `RtspServerSubsystem.cpp`(GStreamer)는 이미 전체가 `#if RTSPENCODER_HAS_GSTREAMER`로
  게이팅돼 있어서 추가 수정 불필요했음.

**결과**: 이제 어떤 PC든 SDK가 있든 없든 titan_example 빌드 자체는 항상 성공. RTSP
기능만 그 SDK 유무에 따라 켜지거나 꺼짐 — 런타임 쪽은 이미 Phase 1부터
`RtspStreamComponent::SetupEncoderAndStream()`이 인코더 생성 실패 시 로그만 남기고
조용히 스트리밍을 끄는 방식이었으므로(에디터 크래시나 게임 진행 방해 없음) 그대로 잘
맞아떨어짐. **아직 재컴파일로 검증 안 됨** — 다음에 Windows/Linux 양쪽 다시 빌드해서
확인 필요.

### 10.3.3. `LoadingPhase: PostConfigInit`이 모듈 로드 자체를 깨뜨림 → `Default`로 되돌림 (2026-08-18)

빌드는 성공했는데 에디터 실행 시 `"The game module 'titan_example' could not be loaded"`
에러 발생. 원인으로 가장 유력한 건 §10.3(Phase 2)에서 Vulkan 확장(`VK_KHR_external_memory_win32`/
`_fd`) 등록 타이밍을 맞추려고 `RtspEncoder.uplugin`의 `LoadingPhase`를 `Default`에서
`PostConfigInit`(엔진 초기화 극초반)으로 앞당겼던 것 — 이 시점엔 우리 모듈이 의존하는
`D3D12RHI`/`VulkanRHI` 같은 다른 모듈들 자체가 아직 로드될 준비가 안 됐을 가능성이 높음.

**수정**: `LoadingPhase`를 `Default`로 되돌림. 이건 **원래 문제(확장 등록 타이밍)를 고친
게 아니라 그냥 되돌린 것** — `IVulkanDynamicRHI::AddEnabledDeviceExtensionsAndLayers()`
호출 자체는 코드에 남아있지만, 이제 다시 `Default` 페이즈(Vulkan 디바이스가 이미 만들어진
한참 뒤)에서 실행되므로 **사실상 아무 효과 없는 코드**가 됨 — VK_KHR_external_memory
계열 확장이 실제로 활성화되는지는 여전히 미해결 상태. `FNvencVulkanEncoder`를 실제
Vulkan RHI에서 테스트하다가 "확장을 못 찾음" 에러가 나면 바로 이 부분임 — 그때는
LoadingPhase가 아니라 진짜 엔진 프리인잇 훅(플러그인 모듈의 StartupModule 말고, 예를
들어 커스텀 `IEngineLoop` 훅이나 `FCoreDelegates` 계열의 아주 이른 델리게이트) 같은
다른 메커니즘을 찾아봐야 함.

**교훈**: 이번 것도 그렇고 아까 Build.cs 스코프 에러도 그렇고, Phase 2 이후로는 매
수정마다 실제로 사용자 PC에서 재현/재검증을 거치고 있음 — 이 기능(Vulkan/CUDA 인터롭
전체)은 여전히 실제 하드웨어 검증이 하나도 안 끝난 상태라, 당분간 이런 라운드가 더
나올 걸로 예상.

### 10.3.4. `LoadingPhase`를 `Default`로 되돌려도 여전히 크래시 → 진짜 원인은 `checkf` (2026-08-18)

§10.3.3에서 `LoadingPhase`를 `Default`로 되돌렸는데도 사용자 PC에서 똑같이
`"The game module 'titan_example' could not be loaded"` 재현됨 — 진단이 틀렸던 것.

`IVulkanDynamicRHI::AddEnabledDeviceExtensionsAndLayers()`의 실제 구현
(`VulkanLayers.cpp`)을 열어보니:
```cpp
checkf(!GVulkanRHI, TEXT("AddEnabledDeviceExtensionsAndLayers should be called before the VulkanRHI has been created"));
```
`checkf`는 조건이 거짓이면 **즉시 fatal 크래시**임 — 조용히 무시되는 게 아니었음. 이
프로젝트는 `DefaultGraphicsRHI_DX12`라 Vulkan이 활성 RHI는 아니지만, `LoadingPhase`가
`Default`든 `PostConfigInit`이든 우리 모듈의 `StartupModule()`이 실행되는 시점엔 이미
`GVulkanRHI`가 어떤 형태로든 설정돼 있어서(정확한 메커니즘까지는 추적 안 함) 이
`checkf`가 매번 걸렸던 것으로 보임 — 즉 `LoadingPhase`를 아무리 조정해도 이 접근 자체가
성립할 수 없는 방식이었음.

**수정**: `RtspEncoderModule.cpp`의 `StartupModule()`에서 이 호출을 **완전히 제거**.
`LoadingPhase`도 `Default`로 유지(이제 이 값을 바꿀 이유 자체가 없어짐). Vulkan
`VK_KHR_external_memory` 확장 등록은 여전히 미해결 상태로 남겨둠 — `FNvencVulkanEncoder`의
`LoadVulkanFunctionPointers()`가 이미 관련 함수를 못 찾으면 크래시 없이 로그만 남기고
안전하게 실패하도록 돼 있어서(Phase 2에서 이미 그렇게 설계함), 최소한 "동작 안 함"이
"에디터 전체가 안 뜸"으로 번지는 일은 없어짐.

**교훈**: `checkf`/`check`류 UE 매크로를 쓰는 엔진 API를 호출할 때는, "실패하면 그냥
아무 효과 없겠지"라고 넘겨짚지 말고 실제 구현을 먼저 열어봐야 함 — 이번에 그 가정이
완전히 틀렸었고, 그것 때문에 원인 파악에 한 라운드를 더 씀.

### 10.3.5. "game module could not be loaded"의 진짜 원인 — checkf도 LoadingPhase도 아니었음

§10.3.3/10.3.4에서 두 번 수정(LoadingPhase 되돌리기, checkf 유발 호출 제거)했는데도 동일한
"The game module 'titan_example' could not be loaded" 에러가 그대로 재현됐음. 급하게 P4
제출해야 하는 상황이라 일단 `titan_example.Build.cs`에서 `"RtspEncoder"` 의존성 자체를
빼고(`TITAN_RTSP_ENABLED=0`, Vehicles/*.cpp 3개 파일의 `URtspStreamComponent` 사용부를
`#if TITAN_RTSP_ENABLED`로 감싸서 스텁 처리) 플러그인을 코드 레벨에서 완전히 분리했는데도
**같은 에러가 또 재현**됨 — 이때 처음으로 `Saved/Logs/titan_example.log`를 직접 열어서
"could not be loaded" 다이얼로그 줄(1759) 근처가 아니라 그 훨씬 앞, 실제
`InternalLoadLibrary` 시퀀스 부분을 봤음:

```
LogModuleManager: InternalLoadLibrary: 'titan_example' ('.../UnrealEditor-titan_example.dll')
LogWindows: Failed to load '.../UnrealEditor-titan_example.dll' (GetLastError=126)
LogWindows:   Missing import: UnrealEditor-RtspEncoder.dll
```

`GetLastError=126` = `ERROR_MOD_NOT_FOUND` — DLL 자체가 아니라 **그 DLL이 임포트하는
다른 DLL**을 못 찾았다는 뜻. `Build.cs`에서 의존성을 뺐는데도 `titan_example.dll`의 PE
임포트 테이블엔 여전히 `UnrealEditor-RtspEncoder.dll`이 박혀 있었음 — 즉 소스 수정은
맞았는데 **그 수정을 반영해서 다시 링크된 바이너리가 아니었음**. 원인은 Live Coding:
Binaries 폴더에 `.patch_0.exe`/`.patch_1.exe`가 있었던 걸로 봐서 Live Coding을 쓰고
있었는데, Live Coding은 함수 본문 핫패치만 하지 "이 DLL 의존성을 더 이상 안 쓴다" 같은
**링크 구조 변경은 절대 반영 못 함**.

**수정**: Binaries/Intermediate(titan_example + RtspEncoder 양쪽) 삭제 → 프로젝트 파일
재생성 → Live Coding이 아닌 일반 빌드(Rebuild)로 다시 링크 → 정상 로드 확인됨.

**교훈**:
- "빌드는 되는데 실행이 안 됨" 계열 에러를 다이얼로그 텍스트만 보고 재현/추측으로 접근하지
  말고, **`Saved/Logs/*.log`에서 `InternalLoadLibrary`/`GetLastError` 주변을 직접 읽는 게
  가장 빠름** — 이번에도 그렇게 하자마자 한 번에 진짜 원인이 나왔음. `checkf`/`LoadingPhase`
  두 라운드는 로그를 안 보고 소스 코드만 보고 추측한 결과였고, 둘 다 틀렸음.
- **Build.cs의 모듈 의존성 목록을 바꿨을 때는 Live Coding으로 확인하면 안 됨** — 반드시
  풀 빌드(또는 최소한 일반 링크가 도는 빌드)로 확인해야 함. 이 프로젝트는 평소 Live
  Coding을 습관적으로 쓰는 듯하니, 앞으로 플러그인 의존성/`.uplugin`/Build.cs를 건드린
  뒤에는 매번 "이거 Live Coding 아니라 진짜 재빌드했나?"부터 확인할 것.

### 10.3.6. SDK 미설치 시 소프트-페일 체인 전수 감사 (2026-08-18)

RTSP 재활성화하면서 "SDK 없어도 경고만 뜨고 빌드/실행은 되게" 요구사항이 실제로 전
구간에서 지켜지는지 코드 레벨로 재확인함 (이전 세션에서 구현한 걸 다시 검증):

- **`RtspEncoder.Build.cs`**: `TrySetupNvencWindows`/`TrySetupNvencLinux`/
  `TrySetupGStreamerWindows`/`TrySetupGStreamerLinux` 전부 SDK/디렉토리/라이브러리 파일
  하나라도 없으면 `Log.TraceWarning` + `return false`만 하고 `BuildException`은 절대 안
  던짐. 결과는 `RTSPENCODER_HAS_NVENC`/`RTSPENCODER_HAS_GSTREAMER` 매크로(0/1)로 전달.
- **벤더 NVENC 파일 6개** (`ThirdParty/NvCodec/**`): 전체가 `#if RTSPENCODER_HAS_NVENC`로
  감싸져 있어서 0일 때 빈 파일처럼 컴파일됨 — 링크 에러 없음.
- **`NvencD3D12Encoder.cpp`**: 전체 구현이 `#if RTSPENCODER_HAS_NVENC`로 감싸짐. 헤더
  (`NvencD3D12Encoder.h`)는 가드 없이 항상 컴파일되지만 멤버 함수 선언만 있고 정의가
  없어도 문제없음 — 실제로 그 함수들을 호출하는 코드(Factory)도 똑같이 매크로로 가려져
  있어서 참조 자체가 안 생김.
- **`RtspFrameEncoderFactory.cpp`**: `#if RTSPENCODER_HAS_NVENC`로 `CreateRtspFrameEncoder`
  전체가 두 가지 버전으로 나뉨 — 0일 때는 그냥 에러 로그 찍고 `nullptr` 리턴하는 버전으로
  컴파일됨.
- **`RtspStreamComponent.cpp::SetupEncoderAndStream()`**: `CreateRtspFrameEncoder`가
  `nullptr`이면 에러 로그 찍고 `false` 리턴 — 스트리밍만 조용히 안 됨, 크래시 없음.
  `URtspServerSubsystem`이 안 돌고 있어도(GStreamer 없음) 마찬가지로 그냥 에러 로그 +
  `false`.
- **`RtspServerSubsystem.cpp`**: 전체가 `#if RTSPENCODER_HAS_GSTREAMER`로 감싸져 있고,
  `FRtspEncoderModule::IsGStreamerReady()`도 체크함.
- **`RtspEncoderModule.cpp::StartupModule()`**: GStreamer bin 디렉토리가 없으면(런타임
  체크, 빌드 타임과 별개) 에러 로그 찍고 그냥 `return` — 모듈 자체는 정상 로드됨.

**결론**: 이 체인은 감사 당시엔 전 구간 soft-fail로 보였으나, 실제로 SDK 없는 팀원 PC에서
빌드해보니 구멍이 하나 있었음(아래 §10.3.7) — 정적 감사만으로는 못 잡았고, 실제 그 환경에서
빌드해봐야 확실히 검증된다는 교훈.

### 10.3.7. `FNvencVulkanEncoder.h` — SDK 없는 PC에서 C1083

팀원 PC(NVIDIA Video Codec SDK 미설치, `RTSPENCODER_HAS_NVENC=0`)에서 실제 빌드 시:

```
C1083: 포함 파일을 열 수 없습니다. 'IVulkanDynamicRHI.h'
  FNvencVulkanEncoder.h(41)
```

원인: `FNvencVulkanEncoder.h`가 `#include "IVulkanDynamicRHI.h"`/`<cuda.h>`를 **아무 매크로
가드 없이** 최상단에서 include하고 있었음. 이 헤더는 `FNvencVulkanEncoder.cpp`가
(`#include "FNvencVulkanEncoder.h"`를 자기 자신의 `#if RTSPENCODER_HAS_NVENC` 가드보다
**앞에서** — 즉 가드 밖에서 — include) 매번 무조건 include하는데, `IVulkanDynamicRHI.h`가
실제로 include 경로에 잡히는 건 `RtspEncoder.Build.cs`가 `"VulkanRHI"` 모듈 의존성을 추가한
경우뿐이고, 그건 NVENC SDK + CUDA Toolkit이 둘 다 있어야만(`TrySetupNvencWindows`/
`TrySetupNvencLinux`가 `true`를 리턴해야만) 일어남. 벤더 NVENC 파일 6개나
`NvencD3D12Encoder.cpp`/`RtspFrameEncoderFactory.cpp`는 전부 이 패턴을 정확히 지켰는데
이 파일 하나만 헤더 자체가 안 가려져 있었음.

**수정**: `FNvencVulkanEncoder.h`의 `#include "IVulkanDynamicRHI.h"` / `<cuda.h>` 및
클래스 선언 전체를 `#if RTSPENCODER_HAS_NVENC ... #endif`로 감쌈 (`CoreMinimal.h`/
`IRtspFrameEncoder.h`만 가드 밖에 남김 — 둘 다 항상 안전). `.cpp` 쪽은 안 건드림 — 헤더
자체가 이제 SDK 없을 때 빈 파일처럼 컴파일되므로, `.cpp`의 무가드 include가 안전해짐.

**교훈**: §10.3.6 감사는 "매크로로 감싸져 있는지" 코드를 눈으로 훑는 정적 점검이었는데, 이
파일 하나를 놓쳤음 — 실제로 SDK 없는 머신에서 빌드해보기 전까진 100% 확신할 수 없었음.
비슷한 소프트-페일 가드를 또 추가할 일이 있으면, **`.h`/`.cpp` 양쪽 다 최상단부터 확인** —
특히 "이 .cpp는 가드돼 있으니 안전하다"고 넘겨짚지 말고 그 .cpp가 include하는 헤더 자체도
가드돼 있는지 따로 확인할 것.

### 10.3.8. `NvencD3D12Encoder.h` — 클린 리빌드로도 안 없어지는 LNK2001/2019

§10.3.7 고치고 다시 그 PC에서 폴더 싹 지우고 클린 리빌드까지 했는데도 **같은 계열의 또
다른 에러**가 남:

```
LNK2001: FNvencD3D12Encoder::Shutdown, FNvencD3D12Encoder::EncodeFrame
LNK2019: FNvencD3D12Encoder 소멸자 + vector deleting destructor
(전부 NvencD3D12Encoder.cpp.obj 자기 자신이 참조하는 것으로 표시됨)
```

C1083(못 찾는 헤더)가 아니라 LNK라서 처음엔 스테일 빌드 의심했는데, 클린 리빌드로도
재현되는 걸 보고 진짜 코드 문제라고 판단. 원인은 `FNvencVulkanEncoder.h`(§10.3.7)와
근본적으로 같은 "가드 안 된 헤더" 계열이지만 증상이 다르게 나타난 케이스:

`NvencD3D12Encoder.h`는 클래스 선언 자체엔 매크로 가드가 없었고, 그 안에
`IsInitialized()` 하나가 **인라인**으로 정의돼 있었음(`{ return Encoder != nullptr; }`).
클래스가 `RTSPENCODER_API`(dllexport)라서, `RTSPENCODER_HAS_NVENC=0`인 머신에서
`NvencD3D12Encoder.cpp`을 컴파일하면 생성자/소멸자/`Shutdown`/`EncodeFrame`(전부 .cpp에서
`#if RTSPENCODER_HAS_NVENC`로 가드된 아웃오브라인 정의)은 빠지는데, 헤더의 인라인
`IsInitialized()`는 매크로와 무관하게 이 TU에서 그대로 컴파일됨. dllexport 클래스가 어떤
TU에서든 가상함수 정의(인라인 포함)를 하나라도 가지면 MSVC는 그 TU에서 vtable 전체를
export해야 하고, vtable을 채우려면 나머지 가상함수(Shutdown/EncodeFrame/소멸자) 주소도
필요한데 이 TU엔 없음 — 그래서 정확히 이 세 개만(인라인이 아닌 것들만) unresolved
external로 뜬 것. `GetWidth`/`GetHeight`도 인라인이라 문제없었던 것도 이 설명과 일치.

**수정**: `NvencD3D12Encoder.h`도 `FNvencVulkanEncoder.h`와 동일하게 클래스 선언 전체를
`#if RTSPENCODER_HAS_NVENC ... #endif`로 감쌈 (`CoreMinimal.h`/`IRtspFrameEncoder.h`만
가드 밖).

**교훈**: dllexport(`XXX_API`) 클래스에 인라인 가상함수가 하나라도 있으면, 그 클래스
선언 전체가 매크로로 가드 안 돼 있는 한 "이 .cpp의 나머지 정의만 가드하면 충분하다"는
가정이 깨짐 — 헤더에 인라인 정의가 하나라도 있으면 .cpp가 아무리 잘 가드돼 있어도
소용없음. `FNvencVulkanEncoder.h`는 애초에 인라인 가상함수가 없어서 이 문제가 없었고
(그래서 그쪽은 C1083, 이쪽은 LNK로 다르게 터짐) — SDK-optional 가드가 필요한
`XXX_API` 클래스는 앞으로 **무조건 클래스 선언 전체를 매크로로 감싸는 걸 기본값**으로
할 것, 인라인 함수 유무를 개별 판단하지 말고.

### 10.4. 남은 Phase

- **Phase 3 — Windows 전용 접착 코드 정리**: Phase 1~2에서 이미 대부분 진행됨.
- **Phase 4 — 리눅스 실빌드/실테스트**: 사용자가 실제 "Linux로 패키징" 절차 실행 →
  옮겨서 실제 우분투 박스에서 컴파일 에러/런타임 확인. Vulkan RHI 렌더링 자체가 되는지,
  §10.3에서 나열한 미검증 리스크들이 실제로 문제가 되는지가 여기서 처음 검증됨.
