// What a frontend record may say of a console call, an uncaught error or a
// rejected promise: the authored shape of its message with every value taken
// out, and the script and position its first stack frame names. The host
// applies the same rule again (`redact_template` and `module_name` in
// native/application/src/diagnostics/desktop.rs), so this copy only keeps
// values from leaving the document in the first place.

/** Words a message may keep although they start with a capital. */
const KEPT_CAPITALISED = new Set([
  "A",
  "AbortError",
  "An",
  "Cannot",
  "Could",
  "DOMException",
  "Defaulting",
  "Each",
  "Encountered",
  "Error",
  "EvalError",
  "Expected",
  "Failed",
  "Function",
  "Functions",
  "If",
  "Invalid",
  "It",
  "Maximum",
  "NetworkError",
  "NotAllowedError",
  "NotFoundError",
  "Objects",
  "RangeError",
  "React",
  "ReferenceError",
  "Rendered",
  "ResizeObserver",
  "Script",
  "SecurityError",
  "SyntaxError",
  "The",
  "This",
  "Too",
  "TypeError",
  "URIError",
  "Uncaught",
  "Unexpected",
  "Warning",
  "When",
]);

const TEMPLATE_LIMIT = 240;
const EDGE = new Set(".,:;()[]{}!?-=");

function trimEdges(token: string): [number, number] {
  let start = 0;
  let end = token.length;
  while (start < end && EDGE.has(token[start]!)) start += 1;
  while (end > start && EDGE.has(token[end - 1]!)) end -= 1;
  return [start, end];
}

function kept(core: string): boolean {
  return (
    core === "" ||
    core === "…" ||
    core === "`…`" ||
    core === '"…"' ||
    KEPT_CAPITALISED.has(core) ||
    /^%[sdifoOc]$/.test(core) ||
    (/^[a-z][A-Za-z']*$/.test(core) && !core.includes("''"))
  );
}

/** The authored shape of `text`: quoted and backticked spans, numbers,
 * capitalised words outside a closed list, and every word with a digit, a
 * non-ASCII letter or a symbol become `…`. Null when no word is left. */
export function redactTemplate(text: string): string | null {
  let spans = "";
  let quote: string | null = null;
  for (const c of text) {
    if (quote !== null) {
      if (c === quote) {
        spans += `…${c}`;
        quote = null;
      }
    } else if (c === "`" || c === '"') {
      spans += c;
      quote = c;
    } else spans += c;
  }
  if (quote !== null) spans += "…";
  const words: string[] = [];
  for (const token of spans.split(/\s+/).filter(Boolean)) {
    const [start, end] = trimEdges(token);
    const core = token.slice(start, end);
    const word = kept(core)
      ? token
      : `${token.slice(0, start)}…${token.slice(end)}`;
    if (word === "…" && words.at(-1) === "…") continue;
    words.push(word);
  }
  let template = "";
  for (const word of words) {
    const next = [...template].length + (template ? 1 : 0) + [...word].length;
    if (next > TEMPLATE_LIMIT) {
      template += " …";
      break;
    }
    template += (template ? " " : "") + word;
  }
  return /[A-Za-z]/.test(template) ? template : null;
}

/** A script's file name, never its origin, folders or query. */
export function moduleName(location: string): string | null {
  const path = location.split(/[?#]/)[0] ?? "";
  const name = path.split(/[/\\]/).at(-1) ?? "";
  return /\.(m?js|jsx|tsx?|html)$/.test(name) &&
    name.length <= 96 &&
    !name.startsWith(".") &&
    /^[A-Za-z0-9._-]+$/.test(name)
    ? name
    : null;
}

export type Frame = { module: string; line: number; column: number };

/** The frames of a V8 stack, outermost last; frames with no script are left
 * out. */
export function frames(stack: string | undefined): Frame[] {
  if (!stack) return [];
  const found: Frame[] = [];
  for (const line of stack.split("\n")) {
    const match = /\(?([^\s()]+):(\d+):(\d+)\)?\s*$/.exec(line.trim());
    if (!match || !/^\s*at\s/.test(line)) continue;
    const module = moduleName(match[1]!);
    if (module)
      found.push({ module, line: Number(match[2]), column: Number(match[3]) });
  }
  return found;
}

/** What a report says of what happened, beside its closed fields. */
export type Summary = {
  template?: string;
  module?: string;
  line?: number;
  column?: number;
};

function summary(
  template: string | null,
  frame: Partial<Frame> | null | undefined,
): Summary {
  return {
    ...(template ? { template } : {}),
    ...(frame?.module ? { module: frame.module } : {}),
    ...(frame?.line !== undefined && frame.column !== undefined
      ? { line: frame.line, column: frame.column }
      : {}),
  };
}

/** What a thrown or rejected value was. A host failure is a plain object
 * with a closed `code`; any other value says only its kind. */
function describe(value: unknown): string {
  if (value instanceof Error) return `${value.name}: ${value.message}`;
  if (value === null) return "null value thrown";
  if (typeof value === "string")
    return redactTemplate(value) ?? "string thrown";
  if (
    typeof value === "object" &&
    "code" in value &&
    typeof value.code === "string"
  )
    return `host failure ${value.code}`;
  return `${typeof value} thrown`;
}

/** A console call: the first argument is the message or its format string;
 * the rest are values and never read. `stack` is taken inside the console
 * wrapper, whose own frame comes first and is skipped. */
export function consoleSummary(args: unknown[], stack: string | undefined) {
  const [first] = args;
  const text =
    typeof first === "string"
      ? first
      : first instanceof Error
        ? `${first.name}: ${first.message}`
        : null;
  return summary(text === null ? null : redactTemplate(text), frames(stack)[1]);
}

/** An uncaught error event. Without an error object and at line 0 the
 * browser withheld the detail (a script of another origin) or raised a
 * notice of its own, such as a ResizeObserver loop; its message still says
 * which. */
export function errorEventSummary(event: {
  message?: string;
  filename?: string;
  lineno?: number;
  colno?: number;
  error?: unknown;
}): Summary {
  const error = event.error;
  const thrown =
    error instanceof Error
      ? redactTemplate(`${error.name}: ${error.message}`)
      : null;
  const template =
    thrown ??
    redactTemplate(event.message ?? "") ??
    (error === undefined || error === null
      ? "uncaught error event without message or error object"
      : redactTemplate(describe(error)));
  const frame = error instanceof Error ? frames(error.stack)[0] : undefined;
  const module = event.filename ? moduleName(event.filename) : null;
  return summary(
    template,
    frame ??
      (module
        ? { module, line: event.lineno ?? 0, column: event.colno ?? 0 }
        : null),
  );
}

/** A rejected promise: an Error says its name and message; any other value
 * says only what kind of value it was. */
export function rejectionSummary(reason: unknown): Summary {
  const template = redactTemplate(describe(reason));
  return summary(
    template,
    reason instanceof Error ? frames(reason.stack)[0] : null,
  );
}

/** Whether an uncaught error event is the browser's own notice that a
 * ResizeObserver could not deliver every resize in one frame: nothing
 * failed, and the next frame delivers the rest. */
export function isResizeObserverNotice(event: {
  message?: string;
  error?: unknown;
}): boolean {
  return (
    (event.error === undefined || event.error === null) &&
    /^ResizeObserver loop/.test(event.message ?? "")
  );
}
