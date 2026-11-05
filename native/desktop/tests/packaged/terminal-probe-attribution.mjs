// Causal attribution of the one authored terminal fault probe: the
// `flood-every-byte` check acknowledges one byte past what the shell received,
// and the window host refuses it with a native terminal failure record. That
// record is excused only when it is provably the refusal of that exact call:
// same host, same terminal session, the byte count the call overshot, an
// accepted acknowledgement of that count before it, and the call inside the
// check's window with the record inside the call's. Timing is necessary and
// never sufficient. Nothing here reads files; the gate passes the records and
// the harness's IPC trace in.

/** The check whose authored overshooting acknowledgement this attributes. */
export const TERMINAL_PROBE_CHECK = "flood-every-byte";
/** At most this many native records are excused in a run. */
export const TERMINAL_PROBE_MAX_ATTRIBUTED = 1;
/** Clock tolerance between the page's call stamp and the host's record. */
export const TERMINAL_PROBE_SKEW_MS = 1;

const integer = (value) => Number.isInteger(value);

/** The check's recorded span, or null when it did not run. */
function probeWindow(checks) {
  const check = (checks ?? []).find((c) => c.id === TERMINAL_PROBE_CHECK);
  if (!check) return null;
  const start = Date.parse(check.startedAt);
  if (!Number.isFinite(start) || !Number.isFinite(check.elapsedMs)) return null;
  return [start, start + check.elapsedMs];
}

/** (a) A native record of a refused terminal call's arguments. */
export function isTerminalRefusal(record) {
  return (
    record?.kind === "failure" &&
    record.failure?.code === "invalid_arguments" &&
    record.failure?.operation === "terminal"
  );
}

/** A well-formed harness `terminal_ack` row of the IPC trace. */
function harnessAck(call) {
  return (
    call?.by === "harness" &&
    call.cmd === "terminal_ack" &&
    integer(call.seq) &&
    Number.isFinite(call.at) &&
    Number.isFinite(call.ms) &&
    call.ms >= 0 &&
    integer(call.args?.session) &&
    integer(call.args?.offset)
  );
}

/** (e) The harness's refused acknowledgement, never a shell call. */
export function isProbeCall(call) {
  return (
    harnessAck(call) && call.ok === false && call.code === "invalid_arguments"
  );
}

const inside = (from, to, [start, end]) => from >= start && to <= end;

/**
 * The record and call are one causal pair, (b) to (d) and (f): the window
 * host, the call's session, the count one below the overshooting offset with
 * an accepted harness acknowledgement of exactly that count earlier in the
 * check, the call inside the check and the record inside the call.
 */
function causalPair(record, call, { trace, window, windowHostPid }) {
  if (!integer(record.sequence) || record.hostPid !== windowHostPid)
    return false;
  if (!integer(record.terminalSession)) return false;
  if (record.terminalSession !== call.args.session) return false;
  const bytes = record.status?.terminalBytes;
  if (!integer(bytes) || bytes !== call.args.offset - 1) return false;
  if (!inside(call.at, call.at + call.ms, window)) return false;
  if (
    !Number.isFinite(record.timestampMs) ||
    record.timestampMs < call.at - TERMINAL_PROBE_SKEW_MS ||
    record.timestampMs > call.at + call.ms + TERMINAL_PROBE_SKEW_MS
  )
    return false;
  return trace.some(
    (prior) =>
      harnessAck(prior) &&
      prior.ok === true &&
      prior.seq < call.seq &&
      prior.args.session === call.args.session &&
      prior.args.offset === bytes &&
      inside(prior.at, prior.at + prior.ms, window),
  );
}

/**
 * The native records the authored probe explains, as a Map from each excused
 * record object to its attribution. `records` are the parsed native lines,
 * `trace` the harness's IPC trace rows, `checks` the run's recorded checks and
 * `windowHostPid` the pid of the host the window run launched. Each call
 * excuses at most one record and the run at most
 * TERMINAL_PROBE_MAX_ATTRIBUTED; every other record stays as it was.
 */
export function attributeTerminalProbe({
  records,
  trace,
  checks,
  windowHostPid,
}) {
  const attributed = new Map();
  const window = probeWindow(checks);
  if (!window || !integer(windowHostPid) || windowHostPid <= 0)
    return attributed;
  if (!Array.isArray(trace) || !Array.isArray(records)) return attributed;
  const calls = trace.filter(isProbeCall).sort((a, b) => a.seq - b.seq);
  const candidates = records
    .filter(isTerminalRefusal)
    .sort((a, b) => (a.sequence ?? 0) - (b.sequence ?? 0));
  for (const call of calls) {
    if (attributed.size >= TERMINAL_PROBE_MAX_ATTRIBUTED) break;
    const record = candidates.find(
      (candidate) =>
        !attributed.has(candidate) &&
        causalPair(candidate, call, { trace, window, windowHostPid }),
    );
    if (record)
      attributed.set(record, {
        check: TERMINAL_PROBE_CHECK,
        call: call.seq,
        record: record.sequence,
        hostPid: record.hostPid,
        terminalSession: record.terminalSession,
        offset: call.args.offset,
      });
  }
  return attributed;
}
