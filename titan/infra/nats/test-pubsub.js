// pub/sub + JetStream 재연결 유실 없음 검증 스크립트.
// protocol_icd.md §1 봉투 포맷 { cmd, seq, ts, payload } 그대로 사용.
//
// 시나리오:
//   1) core NATS 구독자가 살아있는 상태에서 발행 -> 즉시 수신 확인
//   2) JetStream durable consumer 구독자를 끊고, 끊긴 동안 메시지를 발행한 뒤,
//      같은 durable 이름으로 재연결 -> 끊긴 동안의 메시지를 놓치지 않고 받는지 확인
//
// 실행: node test-pubsub.js

const { connect, StringCodec } = require("nats");

const sc = StringCodec();

function envelope(cmd, seq, payload) {
  return JSON.stringify({ cmd, seq, ts: Date.now(), payload });
}

function assert(cond, msg) {
  if (!cond) throw new Error("FAIL: " + msg);
  console.log("  OK: " + msg);
}

async function testCoreLiveSubscriber() {
  console.log("\n[1] core NATS: 구독자 살아있는 상태에서 pub -> sub 즉시 수신");
  const pub = await connect({ servers: "127.0.0.1:4222" });
  const sub = await connect({ servers: "127.0.0.1:4222" });

  const subject = "console.ugv.telemetry";
  const sscb = sub.subscribe(subject);

  const received = [];
  const consumeTask = (async () => {
    for await (const m of sscb) {
      received.push(JSON.parse(sc.decode(m.data)));
      if (received.length >= 3) break;
    }
  })();

  // 구독이 서버에 반영될 시간을 잠깐 준다
  await new Promise((r) => setTimeout(r, 200));

  for (let seq = 1; seq <= 3; seq++) {
    const msg = envelope("UGV_Period_BasicInfo", seq, {
      pos: { lat: 37.5665, lon: 126.978, alt: 0 },
      speed: 1.2,
      battery: 0.87,
      driveMode: "Auto",
      odometer: 123.4,
    });
    pub.publish(subject, sc.encode(msg));
  }

  await consumeTask;
  assert(received.length === 3, `3개 메시지 수신 (실제 ${received.length})`);
  assert(received[0].cmd === "UGV_Period_BasicInfo", "cmd 필드가 봉투 포맷대로 옴");
  assert(
    received.every((m, i) => m.seq === i + 1),
    "seq가 순서대로 옴 (1,2,3)"
  );
  assert(
    received.every((m) => typeof m.ts === "number" && m.payload && typeof m.payload === "object"),
    "ts/payload 필드 존재"
  );

  await sub.close();
  await pub.close();
}

async function testJetStreamCatchUpAfterDisconnect() {
  console.log("\n[2] JetStream: 구독자가 끊긴 동안 발행된 메시지도 재연결 시 놓치지 않고 수신");

  const durableName = "test_hq_ugv_watcher";
  const subject = "hq.rpt.ugv";

  // --- 구독자 1차 연결: durable consumer 생성만 하고 바로 끊는다 (아직 아무것도 안 옴) ---
  let nc = await connect({ servers: "127.0.0.1:4222" });
  let js = nc.jetstream();
  let jsm = await nc.jetstreamManager();

  try {
    await jsm.consumers.info("HQ_UGV", durableName);
    await jsm.consumers.delete("HQ_UGV", durableName); // 이전 테스트 잔재 제거, 깨끗하게 시작
  } catch (_) {
    /* 없으면 무시 */
  }

  const psub = await js.pullSubscribe(subject, { config: { durable_name: durableName, ack_policy: "explicit" } });
  await psub.unsubscribe(); // 로컬 구독만 정리, durable consumer 자체는 서버에 남음
  await nc.close(); // 구독자 연결 끊음 (durable consumer는 서버에 남아있음)
  console.log("  구독자 연결 끊음 (durable consumer 'test_hq_ugv_watcher'는 서버에 유지됨)");

  // --- 구독자가 없는 동안 3개 메시지 발행 ---
  const pub = await connect({ servers: "127.0.0.1:4222" });
  const publishedSeqs = [101, 102, 103];
  for (const seq of publishedSeqs) {
    const msg = envelope("RPT_ContactDetected", seq, {
      targets: [{ id: `t${seq}`, type: "Person", bbox: { x: 0.1, y: 0.1, w: 0.05, h: 0.1 }, coord: null, confidence: 0.9 }],
    });
    await pub.publish(subject, sc.encode(msg));
  }
  await pub.flush();
  await pub.close();
  console.log(`  구독자 없는 동안 seq=${publishedSeqs.join(",")} 발행 완료`);

  // --- 구독자 재연결: 같은 durable 이름으로 재구독 -> 그 사이 메시지를 받아야 함 ---
  nc = await connect({ servers: "127.0.0.1:4222" });
  js = nc.jetstream();
  const psub2 = await js.pullSubscribe(subject, { config: { durable_name: durableName, ack_policy: "explicit" } });
  psub2.pull({ batch: 10, expires: 2000 });

  const caughtUp = [];
  for await (const m of psub2) {
    caughtUp.push(JSON.parse(sc.decode(m.data)));
    m.ack();
    if (caughtUp.length >= publishedSeqs.length) break;
  }

  assert(caughtUp.length === publishedSeqs.length, `재연결 후 ${publishedSeqs.length}개 전부 수신 (실제 ${caughtUp.length})`);
  assert(
    JSON.stringify(caughtUp.map((m) => m.seq)) === JSON.stringify(publishedSeqs),
    `순서/내용 일치: 받은 seq=[${caughtUp.map((m) => m.seq)}]`
  );

  // 정리
  const jsm2 = await nc.jetstreamManager();
  await jsm2.consumers.delete("HQ_UGV", durableName);
  await nc.close();
}

async function main() {
  const watchdog = setTimeout(() => {
    console.error("\nTIMEOUT: 검증이 15초 안에 끝나지 않음");
    process.exit(1);
  }, 15000);
  watchdog.unref();

  await testCoreLiveSubscriber();
  await testJetStreamCatchUpAfterDisconnect();
  console.log("\n모든 검증 통과.");
  clearTimeout(watchdog);
}

main().catch((err) => {
  console.error("\n검증 실패:", err.message);
  process.exit(1);
});
