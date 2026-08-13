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
