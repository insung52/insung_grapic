// titan JetStream 스트림 생성 스크립트 — 재실행해도 안전(멱등, update-or-create).
//
// subject 구조 (protocol_icd.md §0/§5 근거):
//   console.<axis>.cmd / console.<axis>.evt / console.<axis>.telemetry   (Layer B)
//   hq.cmd.<axis> / hq.rpt.<axis>                                        (Layer A)
//   <axis> = ugv | selfdefense
//
// 실행: node setup-streams.js  (기본 서버 nats://127.0.0.1:4222)

const { connect } = require("nats");

const STREAMS = [
  {
    name: "CONSOLE_UGV",
    subjects: ["console.ugv.>"],
    description: "Layer B (console<->에뮬), UGV축 — cmd/evt/telemetry",
  },
  {
    name: "CONSOLE_SELFDEFENSE",
    subjects: ["console.selfdefense.>"],
    description: "Layer B (console<->에뮬), 자체방호축 — cmd/evt/telemetry",
  },
  {
    name: "HQ_UGV",
    subjects: ["hq.cmd.ugv", "hq.rpt.ugv"],
    description: "Layer A (상위체계<->통제기SW), UGV축 — HQ_*/RPT_*",
  },
  {
    name: "HQ_SELFDEFENSE",
    subjects: ["hq.cmd.selfdefense", "hq.rpt.selfdefense"],
    description: "Layer A (상위체계<->통제기SW), 자체방호축 — HQ_*/RPT_*",
  },
];

async function main() {
  const nc = await connect({ servers: "127.0.0.1:4222" });
  const jsm = await nc.jetstreamManager();

  for (const s of STREAMS) {
    const config = {
      name: s.name,
      subjects: s.subjects,
      description: s.description,
      retention: "limits",
      storage: "file",
      max_age: 24 * 60 * 60 * 1e9, // 24h, ns
      max_msgs: 1_000_000,
      discard: "old",
      duplicate_window: 2 * 60 * 1e9, // 2min, ns — seq 기반 dedup은 앱 레벨(§1), 이건 재전송 중복 방지 보조
    };
    try {
      await jsm.streams.info(s.name);
      await jsm.streams.update(s.name, config);
      console.log(`updated: ${s.name} subjects=${JSON.stringify(s.subjects)}`);
    } catch (e) {
      if (e.message.includes("stream not found") || e.api_error?.err_code === 10059) {
        await jsm.streams.add(config);
        console.log(`created: ${s.name} subjects=${JSON.stringify(s.subjects)}`);
      } else {
        throw e;
      }
    }
  }

  console.log("\n현재 스트림 목록:");
  const lister = await jsm.streams.list().next();
  for (const info of lister) {
    console.log(`  - ${info.config.name}: subjects=${JSON.stringify(info.config.subjects)}, messages=${info.state.messages}`);
  }

  await nc.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
