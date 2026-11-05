// The native record a refused WebView2-override launch leaves behind. The host
// refuses before it creates a window, so its record is a short, fixed
// sequence that ends in one `environment_failed` failure and exit code 1.

export const REFUSAL_CODE = "environment_failed";
export const REFUSAL_OPERATION = "webview";

/** The kinds a host that refuses before any window may write. */
const ALLOWED_KINDS = new Set([
  "host_started",
  "stage_started",
  "stage_completed",
  "failure",
  "host_stopped",
]);

/**
 * Judges one refused launch's native diagnostics text. Returns the deviations
 * (empty when the record is exactly a refusal) and the host pid it names.
 */
export function overrideRefusalProblems(text, { excludedPids = [] } = {}) {
  const problems = [];
  const records = [];
  if (typeof text !== "string" || !text.trim()) {
    return { problems: ["the native record is empty or missing"], pid: null };
  }
  for (const [index, line] of text.split("\n").entries()) {
    if (!line.trim()) continue;
    try {
      const record = JSON.parse(line);
      if (record === null || typeof record !== "object")
        throw new Error("not an object");
      records.push(record);
    } catch {
      problems.push(`line ${index + 1} is not a JSON object`);
    }
  }
  if (!records.length) return { problems, pid: null };

  const pids = new Set(records.map((record) => record.hostPid));
  const pid = pids.size === 1 ? [...pids][0] : null;
  if (pids.size !== 1)
    problems.push(`records name ${pids.size} host pids, not one`);
  else if (!Number.isInteger(pid)) problems.push("hostPid is not an integer");
  else if (excludedPids.includes(pid))
    problems.push(`hostPid ${pid} belongs to another host`);

  for (const record of records) {
    if (!ALLOWED_KINDS.has(record.kind))
      problems.push(`unexpected record kind ${JSON.stringify(record.kind)}`);
    if (record.webviewFailure != null)
      problems.push("a webview failure is recorded");
  }

  const kinds = records.map((record) => record.kind);
  if (kinds.includes("gui_selected"))
    problems.push("gui_selected is recorded, so a window was selected");

  const failures = records.filter((record) => record.kind === "failure");
  if (failures.length !== 1)
    problems.push(`${failures.length} failure records, expected exactly one`);
  else {
    const failure = failures[0].failure;
    if (failure?.code !== REFUSAL_CODE)
      problems.push(
        `failure code is ${JSON.stringify(failure?.code)}, expected ${REFUSAL_CODE}`,
      );
    if (failure?.operation !== REFUSAL_OPERATION)
      problems.push(
        `failure operation is ${JSON.stringify(failure?.operation)}, expected ${REFUSAL_OPERATION}`,
      );
  }

  const started = kinds.indexOf("host_started");
  const failed = kinds.indexOf("failure");
  const stops = records.filter((record) => record.kind === "host_stopped");
  const stopped = kinds.indexOf("host_stopped");
  if (kinds.filter((kind) => kind === "host_started").length !== 1)
    problems.push("host_started is not recorded exactly once");
  else if (failed >= 0 && started > failed)
    problems.push("host_started is not before the failure");
  if (stops.length !== 1) problems.push("host_stopped is not recorded once");
  else {
    if (failed >= 0 && stopped < failed)
      problems.push("host_stopped is not after the failure");
    if (stops[0].hostExitCode !== 1)
      problems.push(
        `host_stopped hostExitCode is ${JSON.stringify(stops[0].hostExitCode)}, expected 1`,
      );
  }
  return { problems, pid };
}
