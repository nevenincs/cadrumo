import type {
  SedeViewDialog,
  SedeViewEndReason,
  SedeViewFailureCode,
  SedeViewNoticeCode,
  SedeViewPhase,
  SedeViewPublication,
  SedeViewTransfer,
} from "../../ipc/contract";
import type { SedeViewEvent } from "../../shell/sedeView";

// What the Browser page keeps of its view, and how the person's input becomes
// the host's events. Pure: nothing here touches the host, the document or
// storage, and nothing it holds outlives the page.

/** How many offers, dialogs and prompts wait for the person at once; past
 * it the oldest is let go, as the host lets it go. */
export const WAITING_LIMIT = 16;

export type PageNotice = {
  /** Told apart in the list; not the host's. */
  key: number;
  code: SedeViewNoticeCode;
  /** The host's name for the link the notice offers, if it offers one. */
  offerId: string | null;
};

export type DownloadOffer = { transferId: number; filename: string };
export type ChooserOffer = { chooserId: number; multiple: boolean };

/** How the last transfer ended, said once and then dismissed. */
export type TransferNote = {
  kind: "download" | "upload";
  outcome: SedeViewTransfer;
};

export type PageAddress = {
  origin: string;
  path: string;
  canGoBack: boolean;
  canGoForward: boolean;
  loading: boolean;
  mode: SedeViewPhase;
};

export type BrowserState = {
  /** `opening`: asked for. `waiting`: the previous view still publishes its
   * session. `closing`: the view publishes its session and ends. */
  phase: "opening" | "waiting" | "open" | "closing" | "ended" | "failed";
  page: PageAddress | null;
  /** Oldest first: the person answers them in the order they came. */
  notices: PageNotice[];
  dialogs: SedeViewDialog[];
  downloads: DownloadOffer[];
  choosers: ChooserOffer[];
  note: TransferNote | null;
  /** A call the host refused, said until dismissed. */
  problem: SedeViewFailureCode | null;
  end: {
    reason: SedeViewEndReason;
    publication: SedeViewPublication | null;
  } | null;
  failure: SedeViewFailureCode | null;
  serial: number;
};

export const FIRST_STATE: BrowserState = {
  phase: "opening",
  page: null,
  notices: [],
  dialogs: [],
  downloads: [],
  choosers: [],
  note: null,
  problem: null,
  end: null,
  failure: null,
  serial: 0,
};

export type BrowserAction =
  | { type: "opening" }
  | { type: "waiting" }
  | { type: "failed"; code: SedeViewFailureCode }
  | { type: "event"; event: SedeViewEvent }
  | { type: "problem"; code: SedeViewFailureCode }
  | { type: "problem-dismissed" }
  | { type: "notice-dismissed"; key: number }
  | { type: "dialog-answered"; dialogId: number }
  | { type: "download-answered"; transferId: number }
  | { type: "chooser-answered"; chooserId: number }
  | { type: "note-dismissed" };

/** Appends to a waiting list, letting go of the oldest past the limit. */
function appended<Item>(list: readonly Item[], item: Item): Item[] {
  return [...list, item].slice(-WAITING_LIMIT);
}

export function reduceBrowser(
  state: BrowserState,
  action: BrowserAction,
): BrowserState {
  // Nothing follows a view's end.
  if (state.phase === "ended" && action.type === "event") return state;
  switch (action.type) {
    case "opening":
      return { ...FIRST_STATE, serial: state.serial };
    case "waiting":
      return { ...FIRST_STATE, phase: "waiting", serial: state.serial };
    case "failed":
      return { ...FIRST_STATE, phase: "failed", failure: action.code };
    case "problem":
      return { ...state, problem: action.code };
    case "problem-dismissed":
      return { ...state, problem: null };
    case "notice-dismissed":
      return {
        ...state,
        notices: state.notices.filter((each) => each.key !== action.key),
      };
    case "dialog-answered":
      return {
        ...state,
        dialogs: state.dialogs.filter(
          (each) => each.dialog_id !== action.dialogId,
        ),
      };
    case "download-answered":
      return {
        ...state,
        downloads: state.downloads.filter(
          (each) => each.transferId !== action.transferId,
        ),
      };
    case "chooser-answered":
      return {
        ...state,
        choosers: state.choosers.filter(
          (each) => each.chooserId !== action.chooserId,
        ),
      };
    case "note-dismissed":
      return { ...state, note: null };
    case "event":
      return reduceEvent(state, action.event);
  }
}

function reduceEvent(state: BrowserState, event: SedeViewEvent): BrowserState {
  switch (event.kind) {
    case "opened":
      return state.phase === "closing" ? state : { ...state, phase: "open" };
    case "image":
      return state;
    case "state":
      return {
        ...state,
        phase:
          event.phase === "closing" && state.phase === "open"
            ? "closing"
            : state.phase,
        page: {
          origin: event.origin,
          path: event.path,
          canGoBack: event.can_go_back,
          canGoForward: event.can_go_forward,
          loading: event.loading,
          mode: event.phase,
        },
      };
    case "notice": {
      // A dialog is answered as a dialog, not read as a notice as well.
      if (event.dialog)
        return { ...state, dialogs: appended(state.dialogs, event.dialog) };
      return {
        ...state,
        notices: appended(state.notices, {
          key: state.serial,
          code: event.code,
          offerId: event.offer_id,
        }),
        serial: state.serial + 1,
      };
    }
    case "download":
      return {
        ...state,
        downloads: appended(state.downloads, {
          transferId: event.transfer_id,
          filename: event.filename,
        }),
      };
    case "download_ended":
      return {
        ...state,
        downloads: state.downloads.filter(
          (each) => each.transferId !== event.transfer_id,
        ),
        note: { kind: "download", outcome: event.outcome },
      };
    case "file_chooser":
      return {
        ...state,
        choosers: appended(state.choosers, {
          chooserId: event.chooser_id,
          multiple: event.multiple,
        }),
      };
    case "upload_ended":
      return {
        ...state,
        choosers: state.choosers.filter(
          (each) => each.chooserId !== event.chooser_id,
        ),
        note: { kind: "upload", outcome: event.outcome },
      };
    case "closing":
      return { ...state, phase: "closing" };
    case "ended":
      return {
        ...FIRST_STATE,
        phase: "ended",
        serial: state.serial,
        end: {
          reason: event.reason,
          publication: event.outcome?.publication ?? null,
        },
      };
  }
}

/** Whether the view is publishing its session, so a navigation must wait. */
export function publishing(state: BrowserState): boolean {
  return state.phase === "closing" || state.page?.mode === "closing";
}

/** Whether the person's input reaches the page: while a login runs it does
 * too, and takes the login over. */
export function takesInput(state: BrowserState): boolean {
  return state.phase === "open" && state.page?.mode !== "closing";
}

// ---------------------------------------------------------------------------
// Input
// ---------------------------------------------------------------------------

/** The modifier mask the host takes: Alt 1, Control 2, Meta 4, Shift 8. */
export function modifiersOf(
  press: Pick<KeyboardEvent, "altKey" | "ctrlKey" | "metaKey" | "shiftKey">,
  altGraph = false,
): number {
  // AltGr reports Control and Alt together; it types a character instead.
  return (
    (press.altKey && !altGraph ? 1 : 0) |
    (press.ctrlKey && !altGraph ? 2 : 0) |
    (press.metaKey ? 4 : 0) |
    (press.shiftKey ? 8 : 0)
  );
}

const clamp = (value: number, low: number, high: number) =>
  Math.min(high, Math.max(low, value));

/** The CSS pixel of the view's page under a point of the panel, or null while
 * either has no size. */
export function viewPoint(
  point: { x: number; y: number },
  box: { left: number; top: number; width: number; height: number },
  page: { width: number; height: number },
): { x: number; y: number } | null {
  if (box.width <= 0 || box.height <= 0 || page.width < 1 || page.height < 1)
    return null;
  return {
    x: clamp(
      Math.floor(((point.x - box.left) / box.width) * page.width),
      0,
      page.width - 1,
    ),
    y: clamp(
      Math.floor(((point.y - box.top) / box.height) * page.height),
      0,
      page.height - 1,
    ),
  };
}

const LINE_PIXELS = 40;
const WHEEL_LIMIT = 10_000;

/** A wheel turn in CSS pixels, whatever unit the system reports it in. */
export function wheelDelta(
  turn: Pick<WheelEvent, "deltaX" | "deltaY" | "deltaMode">,
  page: { height: number },
): { x: number; y: number } {
  const unit =
    turn.deltaMode === 1 ? LINE_PIXELS : turn.deltaMode === 2 ? page.height : 1;
  const whole = (value: number) =>
    clamp(Math.round(value * unit), -WHEEL_LIMIT, WHEEL_LIMIT);
  return { x: whole(turn.deltaX), y: whole(turn.deltaY) };
}

export function pointerButton(
  index: number,
): "left" | "middle" | "right" | null {
  return index === 0
    ? "left"
    : index === 1
      ? "middle"
      : index === 2
        ? "right"
        : null;
}

/** The keys the page can be given by name; any one character is a key too. */
const NAMED_KEYS: ReadonlySet<string> = new Set([
  "Backspace",
  "Tab",
  "Enter",
  "Shift",
  "Control",
  "Alt",
  "Pause",
  "CapsLock",
  "Escape",
  "PageUp",
  "PageDown",
  "End",
  "Home",
  "ArrowLeft",
  "ArrowUp",
  "ArrowRight",
  "ArrowDown",
  "PrintScreen",
  "Insert",
  "Delete",
  "Meta",
  "ContextMenu",
  "NumLock",
  "ScrollLock",
  ...Array.from({ length: 12 }, (_, index) => `F${index + 1}`),
]);

const KEY_TEXT_LIMIT = 32;
const characters = (text: string) => Array.from(text).length;
const HAS_CONTROL = /\p{Cc}/u;

export type KeyPress = Pick<
  KeyboardEvent,
  "key" | "code" | "altKey" | "ctrlKey" | "metaKey" | "shiftKey" | "isComposing"
> & { altGraph: boolean };

/** What one key press sends: the key itself and, for a key that types a
 * character, the text it types. */
export type KeyPlan = {
  key: string;
  code: string;
  modifiers: number;
  text: string | null;
};

/** The events a key press becomes, or null for a key the page cannot be
 * given: a dead key, a composition in progress, a media key. */
export function keyPlan(press: KeyPress, mac: boolean): KeyPlan | null {
  if (press.isComposing) return null;
  const single = characters(press.key) === 1;
  if (!single && !NAMED_KEYS.has(press.key)) return null;
  if (single && HAS_CONTROL.test(press.key)) return null;
  const shortcut =
    !press.altGraph &&
    (press.ctrlKey || press.metaKey || (press.altKey && !mac));
  return {
    key: press.key,
    code: press.code.length <= KEY_TEXT_LIMIT ? press.code : "",
    modifiers: modifiersOf(press, press.altGraph),
    text: single && !shortcut ? press.key : null,
  };
}

const TEXT_LIMIT = 256;

export type PasteStep = { type: "text"; text: string } | { type: "enter" };

/** A paste as the events that carry it: the host takes at most 256 characters
 * of text with no control character at a time, and a line break is Enter. */
export function pasteSteps(text: string): PasteStep[] {
  const steps: PasteStep[] = [];
  text.split(/\r\n|\r|\n/).forEach((line, index) => {
    if (index > 0) steps.push({ type: "enter" });
    const letters = Array.from(line.replace(/\p{Cc}/gu, " "));
    for (let start = 0; start < letters.length; start += TEXT_LIMIT)
      steps.push({
        type: "text",
        text: letters.slice(start, start + TEXT_LIMIT).join(""),
      });
  });
  return steps;
}

/** The highest click count the host takes. */
export function clickCount(detail: number): number {
  return clamp(Math.trunc(detail) || 1, 1, 3);
}
