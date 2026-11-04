import assert from "node:assert/strict";
import { EventEmitter } from "node:events";
import { performance } from "node:perf_hooks";
import { test } from "node:test";
import { runInNewContext } from "node:vm";
import { instrument } from "./packaged/browser.mjs";

import {
  OBSERVATION_LIMITS,
  OBSERVER_CELLS,
  ObservationError,
  TerminalObserver,
} from "./packaged/terminal-observer.mjs";
import { OBSERVATION_POLL_MS, Session } from "./packaged/session.mjs";

const open = (kind = "python", generation = 1, cols = 80, rows = 24) => [
  { type: "open", kind, generation, cols, rows },
  { type: "bind", kind, generation, ok: true, session: generation },
];
const frame = (index, bytes, generation = 1, kind = "python") => ({
  type: "frame",
  kind,
  generation,
  index,
  bytes,
});
const data = (index, text, generation = 1, kind = "python") =>
  frame(index, [0, ...Buffer.from(text)], generation, kind);
const ack = (offset, generation = 1, kind = "python") => ({
  type: "ack",
  kind,
  generation,
  session: generation,
  offset,
});
const accept = (observer, records, extra = {}) =>
  observer.accept({ document: "document-a", records, ...extra });
const refused = (observer, code, kind = "python") =>
  assert.throws(
    () => observer.rows(kind),
    (error) => error instanceof ObservationError && error.message === code,
  );

// Execute the actual serialized initialization script without a GUI or product IPC.
async function captureWindow() {
  const window = {
    addEventListener() {},
    __TAURI_INTERNALS__: { callbacks: new Map([[7, () => {}]]) },
    async fetch() {
      return new Response('{"session":1}', {
        headers: { "Tauri-Response": "ok", "Content-Type": "application/json" },
      });
    },
  };
  window.top = window;
  runInNewContext(`(${instrument.toString()})(config)`, {
    window,
    document: { addEventListener() {} },
    location: { origin: "https://shell", href: "https://shell/" },
    config: { shellOrigins: ["https://shell"], ipcPrefix: "https://ipc/" },
    console,
    performance,
    Response,
    TextDecoder,
    Uint8Array,
    ArrayBuffer,
    Map,
  });
  const command = (name, args) =>
    window.fetch(`https://ipc/${name}`, {
      body: JSON.stringify(args),
    });
  const start = (id = 7) => {
    if (!window.__TAURI_INTERNALS__.callbacks.has(id))
      window.__TAURI_INTERNALS__.callbacks.set(id, () => {});
    return command("terminal_open", {
      kind: "python",
      frames: `__CHANNEL__:${id}`,
      cols: 80,
      rows: 24,
    });
  };
  await start();
  return {
    state: window.__s10,
    start,
    command,
    send(index, bytes, end = false, id = 7) {
      window.__TAURI_INTERNALS__.callbacks.get(id)({
        index,
        message: bytes,
        end,
      });
    },
  };
}

test("browser queue survives many-small-frame bursts while the parser consumer is suspended", async (t) => {
  const browser = await captureWindow();
  const received = [];
  let holdWrite = false;
  let releaseWrite;
  let writeStarted;
  const observer = new TerminalObserver({
    createTerminal: () => ({
      write(bytes, done) {
        received.push(Buffer.from(bytes));
        if (holdWrite) {
          releaseWrite = done;
          writeStarted();
        } else done();
      },
      dispose() {},
    }),
  });
  t.after(() => observer.dispose());
  const expected = [];
  let index = 0;
  let offset = 0;
  let captured;
  const produce = () => {
    // Below 1 MB, but more records than the old queue could retain between drains.
    for (let n = 0; n < 6000; n += 1) {
      const payload = Buffer.alloc(127);
      for (let k = 0; k < payload.length; k += 1)
        payload[k] = (index * 17 + k) % 256;
      expected.push(payload);
      browser.send(index++, Uint8Array.from([0, ...payload]));
      offset += payload.length;
    }
  };
  for (let burst = 0; burst < 2; burst += 1) {
    produce();
    captured = browser.state.drainVT();
    assert.equal(
      captured.losses.length,
      0,
      JSON.stringify(captured.captureStats),
    );
    holdWrite = true;
    const writing = new Promise((resolve) => {
      writeStarted = resolve;
    });
    const parsing = observer.accept(captured);
    await writing;
    assert.equal(observer.rows("python"), null);
    // The real browser keeps receiving while Node awaits xterm's callback.
    produce();
    await browser.command("terminal_ack", { session: 1, offset });
    holdWrite = false;
    releaseWrite();
    await parsing;
    do {
      captured = browser.state.drainVT();
      assert.equal(captured.losses.length, 0);
      assert(captured.records.length <= OBSERVATION_LIMITS.batchRecords);
      await observer.accept(captured);
    } while (captured.more);
    assert.equal(observer.current.get("python").next, index);
    assert.equal(observer.current.get("python").acked, offset);
  }
  assert.deepEqual(Buffer.concat(received), Buffer.concat(expected));
  assert.equal(observer.stats().dataFrames, 24000);
  assert.equal(observer.stats().bytes, 3048000);
  assert.equal(observer.stats().lossCount, 0);
  assert.equal(captured.captureStats.bytes, 0);
  assert.equal(captured.captureStats.records, 0);
  t.diagnostic(
    JSON.stringify({
      fixture: "browser-small-frame-bursts",
      capture: captured.captureStats,
      parser: observer.stats(),
    }),
  );
});

test("browser spans preserve ACK, control, resize, end and UTF-8 boundaries", async (t) => {
  const browser = await captureWindow();
  const observer = new TerminalObserver();
  t.after(() => observer.dispose());
  const utf8 = Buffer.from("á漢");
  browser.send(0, [1, ...Buffer.from('{"pid":42}')]);
  browser.send(1, [0, utf8[0]]);
  browser.send(2, [0, ...utf8.subarray(1)]);
  await browser.command("terminal_ack", { session: 1, offset: utf8.length });
  browser.send(3, [0, 65]);
  browser.send(4, [0, 66]);
  browser.send(5, [2, ...Buffer.from('{"code":0}')]);
  await browser.command("terminal_resize", { session: 1, cols: 40, rows: 4 });
  browser.send(6, [0, 67]);
  browser.send(7, [], true);
  const batch = browser.state.drainVT();
  assert.equal(batch.losses.length, 0);
  assert.deepEqual(
    Array.from(batch.records, (r) => [r.type, r.index ?? null, r.count ?? 1]),
    [
      ["open", null, 1],
      ["bind", null, 1],
      ["frame", 0, 1],
      ["frame", 1, 2],
      ["ack", null, 1],
      ["frame", 3, 2],
      ["frame", 5, 1],
      ["resize", null, 1],
      ["frame", 6, 1],
      ["frame", 7, 1],
    ],
  );
  await observer.accept(batch);
  assert.equal(observer.rows("python"), null);
  await browser.command("terminal_ack", {
    session: 1,
    offset: utf8.length + 3,
  });
  await observer.accept(browser.state.drainVT());
  assert.equal(observer.rows("python").split("\n")[0], "á漢ABC");
  assert.equal(observer.stats().dataFrames, 5);
  assert.equal(observer.stats().bytes, utf8.length + 3);
  assert.equal(observer.current.get("python").next, 7);
  assert.equal(observer.current.get("python").ended, true);
});

test("browser true overflow remains sticky and replacement rejects stale channel traffic", async (t) => {
  for (const budget of ["records", "bytes"]) {
    const browser = await captureWindow();
    const observer = new TerminalObserver();
    t.after(() => observer.dispose());
    if (budget === "records") {
      for (let n = 0; n < OBSERVATION_LIMITS.records; n += 1)
        await browser.command("terminal_ack", { session: 1, offset: n });
    } else {
      for (let n = 0; n < 33; n += 1)
        browser.send(n, new Uint8Array(OBSERVATION_LIMITS.batchBytes));
    }
    let batch;
    do {
      batch = browser.state.drainVT();
      assert.equal(batch.losses[0]?.code, "TerminalObservationCaptureLimit");
      await observer.accept(batch);
    } while (batch.more);
    refused(observer, "TerminalObservationCaptureLimit");
    assert(batch.captureStats.peakBytes <= OBSERVATION_LIMITS.bytes);
    assert(batch.captureStats.peakRecords <= OBSERVATION_LIMITS.records);
    if (budget === "records")
      assert.equal(batch.captureStats.peakRecords, 4096);
    browser.send(99, [0, 120]);
    await observer.accept(browser.state.drainVT());
    refused(observer, "TerminalObservationCaptureLimit");
    await browser.start(8);
    browser.send(0, [0, 111], false, 7);
    browser.send(0, [0, 110], false, 8);
    await browser.command("terminal_ack", { session: 1, offset: 1 });
    batch = browser.state.drainVT();
    assert.equal(batch.losses.length, 0);
    await observer.accept(batch);
    assert.equal(observer.rows("python").split("\n")[0], "n");
    assert.equal(observer.stats().lossCount, 1);
    t.diagnostic(
      JSON.stringify({
        fixture: `browser-overflow-${budget}`,
        capture: batch.captureStats,
      }),
    );
  }
});

test("browser malformed arrays fail closed before numeric coercion", async (t) => {
  for (const raw of [
    [0, -1],
    [0, 256],
    [0, 1.5],
    [0, "65"],
    [0, NaN],
    [0, , 1],
  ]) {
    const browser = await captureWindow();
    const observer = new TerminalObserver();
    t.after(() => observer.dispose());
    browser.send(0, raw);
    await observer.accept(browser.state.drainVT());
    refused(observer, "TerminalObservationFrameInvalid");
  }
});

test("coalesced index spans reject overlaps, duplicates and malformed metadata", async (t) => {
  for (const records of [
    [{ ...data(1, "ab"), count: 2 }, data(2, "overlap")],
    [{ ...data(0, "ab"), count: 2 }, data(1, "duplicate")],
    ...[null, 0, -1, 1.5, Number.MAX_SAFE_INTEGER].map((count) => [
      { ...data(1, "x"), count },
    ]),
  ]) {
    const observer = new TerminalObserver();
    t.after(() => observer.dispose());
    await accept(observer, [...open(), ...records]);
    refused(observer, "TerminalObservationFrameOrder");
  }
  const observer = new TerminalObserver();
  t.after(() => observer.dispose());
  await accept(observer, [...open(), { ...data(2, "cd"), count: 2 }, ack(4)]);
  assert.equal(observer.rows("python"), null);
  await accept(observer, [{ ...data(0, "ab"), count: 2 }]);
  assert.equal(observer.rows("python").split("\n")[0], "abcd");
  assert.equal(observer.stats().dataFrames, 4);
  assert.equal(observer.current.get("python").next, 4);
});

test("browser capture keeps gaps and duplicate indices visible to the real parser", async (t) => {
  const browser = await captureWindow();
  const observer = new TerminalObserver();
  t.after(() => observer.dispose());
  browser.send(0, [0, 65]);
  browser.send(2, [0, 67]);
  await browser.command("terminal_ack", { session: 1, offset: 3 });
  await observer.accept(browser.state.drainVT());
  assert.equal(observer.rows("python"), null);
  browser.send(1, [0, 66]);
  await observer.accept(browser.state.drainVT());
  assert.equal(observer.rows("python").split("\n")[0], "ABC");
  assert.equal(observer.current.get("python").next, 3);
  browser.send(1, [0, 88]);
  await observer.accept(browser.state.drainVT());
  refused(observer, "TerminalObservationFrameOrder");
});

test("span counts cannot conceal control or end records", async (t) => {
  for (const record of [
    { ...frame(0, [1, 123, 125]), count: 2 },
    { ...frame(0, []), count: 2, end: true },
  ]) {
    const observer = new TerminalObserver();
    t.after(() => observer.dispose());
    await accept(observer, [...open(), record]);
    refused(observer, "TerminalObservationReorderLimit");
  }
});

test("public VT parser handles reordered frames and split UTF-8, requiring an accepted ACK", async (t) => {
  const observer = new TerminalObserver();
  t.after(() => observer.dispose());
  const bytes = Buffer.from("á漢");
  await accept(observer, [
    ...open(),
    frame(0, [1, ...Buffer.from('{"pid":42}')]),
    frame(2, [0, ...bytes.subarray(1)]),
  ]);
  assert.equal(observer.rows("python"), null);
  await accept(observer, [frame(1, [0, ...bytes.subarray(0, 1)])]);
  assert.equal(observer.rows("python"), null);
  await accept(observer, [ack(bytes.length)]);
  assert.equal(observer.rows("python").split("\n")[0], "á漢");
  assert.equal(observer.stats().bytes, bytes.length);
  assert.equal(observer.stats().pendingRecords, 0);
});

test("VT interpretation follows erase, alternate buffers, resize and replacement without scrollback", async (t) => {
  const observer = new TerminalObserver();
  t.after(() => observer.dispose());
  const normal = "hello\rOK\x1b[K";
  const alternate = "\x1b[?1049h\x1b[2J\x1b[Halt";
  const leave = "\x1b[?1049l";
  await accept(observer, [
    ...open("python", 1, 20, 4),
    data(0, normal),
    ack(Buffer.byteLength(normal)),
  ]);
  assert.equal(observer.rows("python").split("\n")[0], "OK");
  await accept(observer, [
    data(1, alternate),
    ack(Buffer.byteLength(normal + alternate)),
  ]);
  assert.equal(observer.rows("python").split("\n")[0], "alt");
  await accept(observer, [
    data(2, leave),
    ack(Buffer.byteLength(normal + alternate + leave)),
  ]);
  assert.equal(observer.rows("python").split("\n")[0], "OK");
  const resized = "\x1b[2J\x1b[H123456789012";
  await accept(observer, [
    { type: "resize", kind: "python", generation: 1, cols: 10, rows: 3 },
    data(3, resized),
    ack(Buffer.byteLength(normal + alternate + leave + resized)),
  ]);
  assert.deepEqual(observer.rows("python").split("\n"), [
    "1234567890",
    "12",
    "",
  ]);
  await accept(observer, [
    ...open("python", 2, 10, 3),
    data(0, "new", 2),
    ack(3, 2),
    { ...data(4, "old", 1), count: 2 },
    ack(1000, 1),
  ]);
  assert.equal(observer.rows("python").split("\n")[0], "new");
  const scrolling = "\x1b[2J\x1b[Hone\r\ntwo\r\nthree\r\nfour";
  await accept(observer, [
    data(1, scrolling, 2),
    ack(3 + Buffer.byteLength(scrolling), 2),
  ]);
  assert.deepEqual(observer.rows("python").split("\n"), [
    "two",
    "three",
    "four",
  ]);
});

test("geometry is bounded in aggregate across both buffers and all three kinds", async (t) => {
  const observer = new TerminalObserver();
  t.after(() => observer.dispose());
  await accept(observer, [
    ...open("python", 1, 200, 100),
    ...open("console", 2, 200, 100),
    ...open("tui", 3, 200, 100),
  ]);
  assert.equal(observer.stats().cells, OBSERVER_CELLS);
  await accept(observer, [
    { type: "resize", kind: "python", generation: 1, cols: 201, rows: 100 },
  ]);
  refused(observer, "TerminalObservationGeometryLimit");
  assert.equal(observer.stats().cells, 80000);
  assert.equal(observer.stats().peakCells, OBSERVER_CELLS);
  await accept(observer, [...open("python", 4, 1000, 1000)]);
  refused(observer, "TerminalObservationGeometryLimit");
});

test("out-of-order retention has independent byte and record limits, with explicit loss", async (t) => {
  for (const budget of ["bytes", "records"]) {
    const observer = new TerminalObserver();
    t.after(() => observer.dispose());
    await accept(observer, open());
    if (budget === "bytes") {
      const bytes = new Uint8Array(OBSERVATION_LIMITS.bytes / 2);
      await accept(observer, [frame(1, bytes), frame(2, bytes), frame(3, [0])]);
      assert.equal(observer.stats().peakPendingBytes, OBSERVATION_LIMITS.bytes);
    } else {
      await accept(
        observer,
        Array.from({ length: OBSERVATION_LIMITS.records + 1 }, (_, index) =>
          frame(index + 1, [0]),
        ),
      );
      assert.equal(
        observer.stats().peakPendingRecords,
        OBSERVATION_LIMITS.records,
      );
    }
    refused(observer, "TerminalObservationReorderLimit");
    assert.equal(observer.stats().pendingBytes, 0);
    assert.equal(observer.stats().pendingRecords, 0);
  }
});

test("oversized single frames progress through bounded parser writes and expose finite timing", async (t) => {
  const observer = new TerminalObserver();
  t.after(() => observer.dispose());
  const bytes = new Uint8Array(OBSERVATION_LIMITS.bytes).fill(120);
  bytes[0] = 0;
  const started = performance.now();
  await accept(observer, [...open(), frame(0, bytes), ack(bytes.length - 1)]);
  const stats = observer.stats();
  assert.equal(
    stats.writes,
    Math.ceil((bytes.length - 1) / OBSERVATION_LIMITS.batchBytes),
  );
  assert.equal(stats.bytes, bytes.length - 1);
  assert(stats.writeCallbackMs >= 0);
  assert.match(observer.rows("python"), /^x+/);
  assert(stats.peakPendingBytes <= OBSERVATION_LIMITS.bytes);
  t.diagnostic(
    JSON.stringify({
      fixture: "maximum-single-frame",
      elapsedMs: performance.now() - started,
      ...stats,
    }),
  );
});

test("duplicate indices, invalid bytes and failed opens refuse interpretation", async (t) => {
  const cases = [
    ["TerminalObservationFrameOrder", [frame(1, [0]), frame(1, [0])]],
    ["TerminalObservationFrameInvalid", [frame(0, [0, -1])]],
    [
      "TerminalObservationOpenFailed",
      [
        {
          type: "bind",
          kind: "python",
          generation: 1,
          ok: false,
          session: null,
        },
      ],
    ],
  ];
  for (const [code, records] of cases) {
    const observer = new TerminalObserver();
    t.after(() => observer.dispose());
    await accept(observer, [...open(), ...records]);
    refused(observer, code);
  }
});

test("capture loss is sticky within a generation and cleared only by a newer open or document", async (t) => {
  const observer = new TerminalObserver();
  t.after(() => observer.dispose());
  await accept(observer, open(), {
    losses: [
      {
        kind: "python",
        generation: 1,
        code: "TerminalObservationCaptureLimit",
      },
    ],
  });
  refused(observer, "TerminalObservationCaptureLimit");
  await accept(observer, [], {
    losses: [
      {
        kind: "python",
        generation: 1,
        code: "TerminalObservationCaptureLimit",
      },
    ],
  });
  assert.equal(observer.stats().lossCount, 1);
  await accept(observer, [
    ...open("python", 2),
    data(0, "replacement", 2),
    ack(11, 2),
  ]);
  assert.match(observer.rows("python"), /^replacement/);
  await observer.accept({ document: "document-b", records: open() });
  assert.equal(observer.rows("python"), null);
  assert.equal(observer.stats().losses.length, 0);
  observer.dispose();
  assert.equal(observer.stats().lossCount, 1);
  assert.equal(
    observer.stats().lastLoss.code,
    "TerminalObservationCaptureLimit",
  );
});

test("end markers participate in channel reordering and reject later frames", async (t) => {
  const observer = new TerminalObserver();
  t.after(() => observer.dispose());
  await accept(observer, [
    ...open(),
    { ...frame(1, []), end: true },
    data(0, "ended"),
    ack(5),
  ]);
  assert.match(observer.rows("python"), /^ended/);
  await accept(observer, [data(2, "late")]);
  refused(observer, "TerminalObservationFrameOrder");
});

test("reset and disposal settle a pending parser callback without leaving retained resources", async () => {
  for (const action of ["reset", "dispose"]) {
    let writing;
    let started;
    const writeStarted = new Promise((resolve) => {
      started = resolve;
    });
    let disposed = 0;
    const observer = new TerminalObserver({
      createTerminal: () => ({
        write: (_bytes, callback) => {
          writing = callback;
          started();
        },
        dispose: () => disposed++,
      }),
    });
    const pending = accept(observer, [
      ...open(),
      data(0, "pending"),
      ...open("console", 2),
      data(0, "stale", 2, "console"),
    ]);
    await writeStarted;
    assert.equal(typeof writing, "function");
    action === "reset" ? observer.reset("document-b") : observer.dispose();
    await pending;
    writing();
    assert.equal(disposed, 1);
    assert.equal(observer.writes.size, 0);
    assert.equal(observer.stats().cells, 0);
    assert.equal(observer.stats().pendingRecords, 0);
    assert.equal(observer.stats().activeKinds, 0);
    observer.dispose();
  }
});

test("rows stay ineligible while a parser has mutated its buffer before the write callback", async () => {
  let callback;
  let started;
  let writeStarted = new Promise((resolve) => {
    started = resolve;
  });
  let visible = "";
  const observer = new TerminalObserver({
    createTerminal: () => ({
      rows: 2,
      buffer: {
        active: {
          baseY: 0,
          getLine: () => ({ translateToString: () => visible }),
        },
      },
      write: (bytes, done) => {
        visible += Buffer.from(bytes).toString();
        callback = done;
        started();
      },
      dispose: () => {},
    }),
  });
  try {
    let pending = accept(observer, [...open(), data(0, "old"), ack(3)]);
    await writeStarted;
    callback();
    await pending;
    assert.match(observer.rows("python"), /^old/);
    writeStarted = new Promise((resolve) => {
      started = resolve;
    });
    pending = accept(observer, [data(1, "unacknowledged")]);
    await writeStarted;
    assert.equal(visible, "oldunacknowledged");
    assert.equal(observer.rows("python"), null);
    callback();
    await pending;
    assert.equal(observer.rows("python"), null);
    await accept(observer, [ack(Buffer.byteLength(visible))]);
    assert.match(observer.rows("python"), /^oldunacknowledged/);
  } finally {
    observer.dispose();
  }
});

test("a pre-bind ACK retains only one exact session and never acknowledges another session", async (t) => {
  const observer = new TerminalObserver();
  t.after(() => observer.dispose());
  const [opening, binding] = open();
  await accept(observer, [opening, data(0, "early"), ack(5)]);
  assert.equal(observer.rows("python"), null);
  await accept(observer, [binding]);
  assert.match(observer.rows("python"), /^early/);
  await accept(observer, [
    ...open("python", 2).slice(0, 1),
    data(0, "new", 2),
    ack(3, 2),
    { ...open("python", 2)[1], session: 99 },
  ]);
  refused(observer, "TerminalObservationAckInvalid");
});

test("Session discards a drain response from a navigated document and keeps bounded cached evidence", async () => {
  const browser = new EventEmitter();
  const page = new EventEmitter();
  const main = {};
  page.mainFrame = () => main;
  let complete;
  let requested;
  const request = new Promise((resolve) => {
    requested = resolve;
  });
  page.evaluate = () => {
    requested();
    return new Promise((resolve) => {
      complete = resolve;
    });
  };
  const session = new Session({ browser, page });
  for (let index = 0; index < 2003; index++)
    page.emit("console", {
      type: () => "warning",
      text: () => "x".repeat(500),
      location: () => ({ url: "fixture" }),
    });
  assert.equal(session.console[0].text.length, 400);
  assert.deepEqual(session.observationStats().console, {
    records: 2000,
    dropped: 3,
    limit: 2000,
  });
  session.startObservation();
  await request;
  page.emit("framenavigated", main);
  complete({
    document: "stale",
    records: [...open(), data(0, "stale"), ack(5)],
  });
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(session.observer.stats().activeKinds, 0);
  page.emit("crash");
  await session.observationPump;
  const stats = session.observationStats();
  assert.equal(stats.stopped, true);
  assert.equal(stats.drains, 0);
  assert.equal(stats.parser.cells, 0);
  assert.equal(stats.console.dropped, 3);
});

test("Session drains queued batches immediately and uses cancellable idle/active poll intervals", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const page = new EventEmitter();
  const browser = new EventEmitter();
  const main = {};
  page.mainFrame = () => main;
  let drains = 0;
  page.evaluate = async () => {
    drains += 1;
    return {
      document: "fixture",
      captureStats: { records: 0, bytes: 0 },
      records: drains === 4 ? open() : [],
      more: drains < 3,
    };
  };
  const session = new Session({ browser, page });
  const flush = () => new Promise((resolve) => setImmediate(resolve));
  try {
    session.startObservation();
    await flush();
    assert.equal(drains, 3, "queued batches must not wait on a poll timer");
    assert.equal(session.observationStats().immediateDrains, 2);
    t.mock.timers.tick(OBSERVATION_POLL_MS.idle - 1);
    await flush();
    assert.equal(drains, 3);
    t.mock.timers.tick(1);
    await flush();
    assert.equal(drains, 4);
    assert(session.observationStats().parser.cells > 0);
    t.mock.timers.tick(OBSERVATION_POLL_MS.active - 1);
    await flush();
    assert.equal(drains, 4);
    t.mock.timers.tick(1);
    await flush();
    assert.equal(drains, 5);
    page.emit("framenavigated", main);
    assert.equal(session.observationStats().parser.cells, 0);
    assert.equal(session.rows("python"), null);
    t.mock.timers.tick(OBSERVATION_POLL_MS.active);
    await flush();
    assert.equal(drains, 6);
    t.mock.timers.tick(OBSERVATION_POLL_MS.idle - 1);
    await flush();
    assert.equal(drains, 6, "navigation/reset returns to the idle cadence");
    session.stopObservation();
    await session.observationPump;
    t.mock.timers.tick(10000);
    await flush();
    assert.equal(drains, 6, "stop cancels waits and drain deadlines");
    assert.equal(session.cancelObservationWait, null);
    assert.deepEqual(session.observationStats().polling, {
      active: 100,
      idle: 250,
    });
  } finally {
    session.stopObservation();
    await session.observationPump;
  }
});
