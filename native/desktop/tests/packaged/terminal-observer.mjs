// A test-owned interpretation of acknowledged PTY bytes, independent of rendering.
import { createRequire } from "node:module";
import { performance } from "node:perf_hooks";

const require = createRequire(
  new URL("../../frontend/package.json", import.meta.url),
);
const { Terminal } = require("@xterm/xterm");

export const OBSERVATION_LIMITS = Object.freeze({
  bytes: 2 * 1024 * 1024,
  records: 4096,
  batchBytes: 64 * 1024,
  batchRecords: 64,
});
// Both normal and alternate buffers count. Three current kinds share this budget.
export const OBSERVER_CELLS = 120000;
const KINDS = ["console", "python", "tui"];

export class ObservationError extends Error {
  constructor(code) {
    super(code);
    this.name = "ObservationError";
  }
}

export class TerminalObserver {
  constructor({ createTerminal = (options) => new Terminal(options) } = {}) {
    this.createTerminal = createTerminal;
    this.current = new Map();
    this.losses = new Map();
    this.writes = new Map();
    this.document = null;
    this.disposed = false;
    this.epoch = 0;
    this.metrics = {
      dataFrames: 0,
      bytes: 0,
      writes: 0,
      writeCallbackMs: 0,
      peakPendingBytes: 0,
      peakPendingRecords: 0,
      peakCells: 0,
      lossCount: 0,
      lastLoss: null,
    };
  }

  release(state) {
    for (const [done, writing] of this.writes) if (writing === state) done();
    state.term?.dispose();
    state.term = null;
    state.pending.clear();
    state.pendingBytes = 0;
    state.pendingCount = 0;
    state.cells = 0;
  }

  reset(document) {
    this.epoch += 1;
    for (const state of this.current.values()) this.release(state);
    this.current.clear();
    this.losses.clear();
    this.document = document;
  }

  lose(kind, generation, code) {
    if (!KINDS.includes(kind)) return;
    const old = this.losses.get(kind);
    if (!old || old.generation <= generation) {
      if (!old || old.generation !== generation || old.code !== code) {
        this.metrics.lossCount = Math.min(
          Number.MAX_SAFE_INTEGER,
          this.metrics.lossCount + 1,
        );
        this.metrics.lastLoss = { kind, generation, code };
      }
      this.losses.set(kind, { generation, code });
    }
    const state = this.current.get(kind);
    if (state?.generation === generation) this.release(state);
  }

  totals(field) {
    return [...this.current.values()].reduce(
      (sum, state) => sum + state[field],
      0,
    );
  }

  size(state, cols, rows) {
    const cells = cols * rows * 2;
    if (
      !Number.isInteger(cols) ||
      !Number.isInteger(rows) ||
      cols < 2 ||
      rows < 2 ||
      cols > 1000 ||
      rows > 1000 ||
      this.totals("cells") - state.cells + cells > OBSERVER_CELLS
    ) {
      this.lose(
        state.kind,
        state.generation,
        "TerminalObservationGeometryLimit",
      );
      return false;
    }
    state.cells = cells;
    this.metrics.peakCells = Math.max(
      this.metrics.peakCells,
      this.totals("cells"),
    );
    return true;
  }

  async write(state, bytes) {
    for (
      let offset = 0;
      offset < bytes.length && !this.disposed && state.term;
      offset += OBSERVATION_LIMITS.batchBytes
    ) {
      const started = performance.now();
      await new Promise((resolve, reject) => {
        const done = () => {
          this.writes.delete(done);
          resolve();
        };
        this.writes.set(done, state);
        try {
          state.term.write(
            bytes.subarray(offset, offset + OBSERVATION_LIMITS.batchBytes),
            done,
          );
        } catch {
          this.writes.delete(done);
          reject(new ObservationError("TerminalObservationParserFailure"));
        }
      });
      this.metrics.writes += 1;
      this.metrics.writeCallbackMs += performance.now() - started;
    }
  }

  async frame(state, record) {
    if (
      !Number.isSafeInteger(record.index) ||
      record.index < state.next ||
      state.pending.has(record.index) ||
      state.ended
    ) {
      this.lose(state.kind, state.generation, "TerminalObservationFrameOrder");
      return;
    }
    const raw = record.bytes ?? [];
    if (
      (!Array.isArray(raw) && !(raw instanceof Uint8Array)) ||
      (!record.end && (!raw.length || raw[0] > 3)) ||
      raw.length > OBSERVATION_LIMITS.bytes ||
      this.totals("pendingBytes") + raw.length > OBSERVATION_LIMITS.bytes ||
      this.totals("pendingCount") >= OBSERVATION_LIMITS.records
    ) {
      this.lose(
        state.kind,
        state.generation,
        "TerminalObservationReorderLimit",
      );
      return;
    }
    for (const byte of raw)
      if (!Number.isInteger(byte) || byte < 0 || byte > 255) {
        this.lose(
          state.kind,
          state.generation,
          "TerminalObservationFrameInvalid",
        );
        return;
      }
    const bytes = Uint8Array.from(raw);
    state.pending.set(record.index, { bytes, end: record.end });
    state.pendingBytes += bytes.length;
    state.pendingCount = state.pending.size;
    this.metrics.peakPendingBytes = Math.max(
      this.metrics.peakPendingBytes,
      this.totals("pendingBytes"),
    );
    this.metrics.peakPendingRecords = Math.max(
      this.metrics.peakPendingRecords,
      this.totals("pendingCount"),
    );
    while (state.pending.has(state.next) && !this.disposed) {
      const next = state.pending.get(state.next);
      state.pending.delete(state.next);
      state.pendingCount = state.pending.size;
      state.pendingBytes -= next.bytes.length;
      if (next.end) {
        state.ended = true;
        break;
      }
      state.next += 1;
      if (next.bytes[0] === 0) {
        state.parsing = true;
        try {
          await this.write(state, next.bytes.subarray(1));
        } finally {
          state.parsing = false;
        }
        if (this.disposed || !state.term) return;
        state.interpreted += next.bytes.length - 1;
        this.metrics.dataFrames += 1;
        this.metrics.bytes += next.bytes.length - 1;
      }
    }
  }

  async accept(batch) {
    if (!batch || this.disposed) return;
    if (batch.document !== this.document) this.reset(batch.document);
    const epoch = this.epoch;
    for (const loss of batch.losses ?? [])
      this.lose(loss.kind, loss.generation, loss.code);
    for (const record of batch.records) {
      if (this.disposed || this.epoch !== epoch) break;
      if (!KINDS.includes(record.kind)) continue;
      let state = this.current.get(record.kind);
      if (record.type === "open") {
        if (state && state.generation >= record.generation) continue;
        if (state) this.release(state);
        state = {
          kind: record.kind,
          generation: record.generation,
          term: null,
          cells: 0,
          session: null,
          pendingAck: null,
          next: 0,
          interpreted: 0,
          acked: 0,
          ended: false,
          parsing: false,
          pending: new Map(),
          pendingBytes: 0,
          pendingCount: 0,
        };
        this.current.set(record.kind, state);
        if (this.losses.get(record.kind)?.generation >= record.generation)
          continue;
        if (this.size(state, record.cols, record.rows))
          state.term = this.createTerminal({
            cols: record.cols,
            rows: record.rows,
            scrollback: 0,
          });
      }
      if (!state || state.generation !== record.generation || !state.term)
        continue;
      if (record.type === "frame") await this.frame(state, record);
      else if (
        record.type === "resize" &&
        this.size(state, record.cols, record.rows)
      )
        state.term.resize(record.cols, record.rows);
      else if (record.type === "bind") {
        if (
          !record.ok ||
          !Number.isSafeInteger(record.session) ||
          record.session < 0
        )
          this.lose(
            record.kind,
            record.generation,
            "TerminalObservationOpenFailed",
          );
        else if (
          state.pendingAck &&
          state.pendingAck.session !== record.session
        )
          this.lose(
            record.kind,
            record.generation,
            "TerminalObservationAckInvalid",
          );
        else {
          state.session = record.session;
          state.acked = Math.max(state.acked, state.pendingAck?.offset ?? 0);
          state.pendingAck = null;
        }
      } else if (record.type === "ack") {
        if (
          !Number.isSafeInteger(record.offset) ||
          record.offset < 0 ||
          !Number.isSafeInteger(record.session) ||
          record.session < 0 ||
          (state.pendingAck && state.pendingAck.session !== record.session)
        )
          this.lose(
            record.kind,
            record.generation,
            "TerminalObservationAckInvalid",
          );
        else if (state.session === null)
          state.pendingAck = {
            session: record.session,
            offset: Math.max(state.pendingAck?.offset ?? 0, record.offset),
          };
        else if (record.session === state.session)
          state.acked = Math.max(state.acked, record.offset);
      }
    }
  }

  rows(kind) {
    if (this.disposed)
      throw new ObservationError("TerminalObservationDisposed");
    const state = this.current.get(kind);
    const loss = this.losses.get(kind);
    if (loss && (!state || loss.generation >= state.generation))
      throw new ObservationError(loss.code);
    if (
      !state?.term ||
      state.parsing ||
      state.session === null ||
      !state.interpreted ||
      state.pending.size ||
      state.acked < state.interpreted
    )
      return null;
    const buffer = state.term.buffer.active;
    return Array.from(
      { length: state.term.rows },
      (_, index) =>
        buffer.getLine(buffer.baseY + index)?.translateToString(true) ?? "",
    ).join("\n");
  }

  stats() {
    return {
      ...this.metrics,
      cells: this.totals("cells"),
      pendingBytes: this.totals("pendingBytes"),
      pendingRecords: this.totals("pendingCount"),
      activeKinds: this.current.size,
      losses: [...this.losses.entries()].map(([kind, loss]) => ({
        kind,
        ...loss,
      })),
    };
  }

  dispose() {
    if (this.disposed) return;
    this.disposed = true;
    for (const done of this.writes.keys()) done();
    this.reset(null);
  }
}
