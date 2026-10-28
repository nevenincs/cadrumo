import { expect, test } from "@playwright/test";
import {
  FIRST_STATE,
  WAITING_LIMIT,
  clickCount,
  keyPlan,
  modifiersOf,
  pasteSteps,
  pointerButton,
  publishing,
  reduceBrowser,
  takesInput,
  viewPoint,
  wheelDelta,
  type BrowserAction,
  type BrowserState,
  type KeyPress,
} from "../src/components/browser/browserModel";
import {
  sedeViewFailure,
  sedeViewReader,
  sedeViewSize,
  type SedeViewEvent,
} from "../src/shell/sedeView";
import type { SedeViewMessage } from "../src/ipc/contract";

// The Browser page's model: what the view says becomes state, and the
// person's input becomes the host's events. No page is opened.

const press = (over: Partial<KeyPress>): KeyPress => ({
  key: "a",
  code: "KeyA",
  altKey: false,
  ctrlKey: false,
  metaKey: false,
  shiftKey: false,
  isComposing: false,
  altGraph: false,
  ...over,
});

const run = (events: SedeViewEvent[], from = FIRST_STATE): BrowserState =>
  events.reduce(
    (state, event) => reduceBrowser(state, { type: "event", event }),
    from,
  );

const page = (over: Partial<Extract<SedeViewEvent, { kind: "state" }>> = {}) =>
  ({
    kind: "state",
    view: 1,
    security: "secure",
    origin: "https://sede.example.test",
    path: "/inicio",
    title: "",
    can_go_back: false,
    can_go_forward: true,
    loading: false,
    phase: "browsing",
    external: true,
    ...over,
  }) satisfies SedeViewEvent;

test("a page off https replaces the address it left with its marker", () => {
  const sede = run([{ kind: "opened", view: 1 }, page()]);
  expect(sede.page).toMatchObject({ security: "secure", external: true });
  for (const security of ["insecure", "unknown"] as const) {
    const away = run(
      [page({ security, origin: null, path: null, external: false })],
      sede,
    );
    expect(away.page).toMatchObject({
      security,
      origin: null,
      path: null,
      external: false,
    });
  }
});

test("the view opens, shows its page, and publishes before it ends", () => {
  let state = run([{ kind: "opened", view: 1 }, page()]);
  expect(state.phase).toBe("open");
  expect(state.page).toMatchObject({
    origin: "https://sede.example.test",
    path: "/inicio",
    canGoBack: false,
    canGoForward: true,
    mode: "browsing",
  });
  expect(takesInput(state)).toBe(true);
  expect(publishing(state)).toBe(false);

  state = run([{ kind: "closing", view: 1 }], state);
  expect(state.phase).toBe("closing");
  expect(publishing(state)).toBe(true);
  expect(takesInput(state)).toBe(false);

  state = run(
    [
      {
        kind: "ended",
        view: 1,
        reason: "closed",
        code: "operation_unavailable",
        outcome: {
          condition: "succeeded",
          end: "closed",
          publication: "kept-newer",
        },
      },
    ],
    state,
  );
  expect(state.phase).toBe("ended");
  // Only the typed outcome is kept: the raw code never reaches the state.
  expect(state.end).toEqual({ reason: "closed", publication: "kept-newer" });
  expect(JSON.stringify(state)).not.toContain("operation_unavailable");
  expect(state.page).toBeNull();
  // Nothing follows the end.
  expect(run([page({ path: "/otra" })], state)).toBe(state);
});

test("a login that runs takes the person's input; a page that closes does not", () => {
  const acquiring = run([
    { kind: "opened", view: 1 },
    page({ phase: "acquiring" }),
  ]);
  expect(acquiring.page?.mode).toBe("acquiring");
  expect(takesInput(acquiring)).toBe(true);
  const closing = run([page({ phase: "closing" })], acquiring);
  expect(closing.phase).toBe("closing");
  expect(takesInput(closing)).toBe(false);
  expect(publishing(closing)).toBe(true);
});

test("a dialog is answered as a dialog, and waiting prompts keep their bound", () => {
  const dialog = {
    dialog_id: 7,
    dialog_kind: "confirm",
    message: "Sure?",
    default_prompt: null,
  } as const;
  let state = run([
    {
      kind: "notice",
      view: 1,
      code: "dialog_opened",
      dialog,
    },
  ]);
  expect(state.dialogs).toEqual([dialog]);
  state = reduceBrowser(state, { type: "dialog-answered", dialogId: 7 });
  expect(state.dialogs).toEqual([]);

  const many = run(
    Array.from({ length: WAITING_LIMIT + 4 }, (_, index): SedeViewEvent => ({
      kind: "download",
      view: 1,
      transfer_id: index + 1,
      filename: `f${index}.pdf`,
      size: null,
      mime: null,
    })),
  );
  expect(many.downloads).toHaveLength(WAITING_LIMIT);
  // The oldest is let go, so the first one waiting is the oldest kept.
  expect(many.downloads[0]?.transferId).toBe(5);
});

test("a download or an upload that ends leaves its note, and its prompt goes", () => {
  let state = run([
    {
      kind: "download",
      view: 1,
      transfer_id: 3,
      filename: "a.pdf",
      size: 10,
      mime: "application/pdf",
    },
    {
      kind: "file_chooser",
      view: 1,
      chooser_id: 4,
      accept: [],
      multiple: true,
    },
  ]);
  expect(state.downloads).toEqual([{ transferId: 3, filename: "a.pdf" }]);
  expect(state.choosers).toEqual([{ chooserId: 4, multiple: true }]);
  state = run(
    [
      { kind: "download_ended", view: 1, transfer_id: 3, outcome: "done" },
      { kind: "upload_ended", view: 1, chooser_id: 4, outcome: "cancelled" },
    ],
    state,
  );
  expect(state.downloads).toEqual([]);
  expect(state.choosers).toEqual([]);
  expect(state.note).toEqual({ kind: "upload", outcome: "cancelled" });
  expect(reduceBrowser(state, { type: "note-dismissed" }).note).toBeNull();
});

test("opening again forgets the last view, and a refusal is kept as its code", () => {
  const ended = run([
    {
      kind: "ended",
      view: 1,
      reason: "session_lost",
      code: null,
      outcome: null,
    },
  ]);
  const actions: BrowserAction[] = [{ type: "opening" }, { type: "waiting" }];
  expect(reduceBrowser(ended, actions[0]!).phase).toBe("opening");
  expect(reduceBrowser(ended, actions[0]!).end).toBeNull();
  expect(reduceBrowser(ended, actions[1]!).phase).toBe("waiting");
  const failed = reduceBrowser(FIRST_STATE, {
    type: "failed",
    code: "refused",
  });
  expect(failed).toMatchObject({ phase: "failed", failure: "refused" });
  expect(
    reduceBrowser(failed, { type: "problem", code: "unavailable" }).problem,
  ).toBe("unavailable");
});

test("a key that types sends its text; a shortcut, AltGr and a dead key do not", () => {
  expect(keyPlan(press({}), false)).toEqual({
    key: "a",
    code: "KeyA",
    modifiers: 0,
    text: "a",
  });
  // A shifted character is the character the key typed.
  expect(keyPlan(press({ key: "A", shiftKey: true }), false)).toMatchObject({
    modifiers: 8,
    text: "A",
  });
  // A shortcut is the key alone.
  expect(keyPlan(press({ ctrlKey: true }), false)).toMatchObject({
    modifiers: 2,
    text: null,
  });
  expect(keyPlan(press({ metaKey: true }), true)).toMatchObject({
    modifiers: 4,
    text: null,
  });
  expect(keyPlan(press({ altKey: true }), false)).toMatchObject({
    modifiers: 1,
    text: null,
  });
  // Option types a character on a Mac.
  expect(keyPlan(press({ key: "å", altKey: true }), true)).toMatchObject({
    text: "å",
  });
  // AltGr reports Control and Alt, and types the character.
  expect(
    keyPlan(
      press({
        key: "@",
        code: "Digit2",
        ctrlKey: true,
        altKey: true,
        altGraph: true,
      }),
      false,
    ),
  ).toEqual({ key: "@", code: "Digit2", modifiers: 0, text: "@" });
  // Named keys are keys; the rest of the keyboard is not the page's.
  expect(keyPlan(press({ key: "Enter", code: "Enter" }), false)).toMatchObject({
    key: "Enter",
    text: null,
  });
  expect(keyPlan(press({ key: "F5", code: "F5" }), false)?.key).toBe("F5");
  for (const key of ["Dead", "Process", "Unidentified", "AudioVolumeUp"])
    expect(keyPlan(press({ key }), false), key).toBeNull();
  expect(keyPlan(press({ isComposing: true }), false)).toBeNull();
  // A character outside the basic plane is one character.
  expect(keyPlan(press({ key: "😀", code: "" }), false)?.text).toBe("😀");
});

test("the modifier mask is Alt 1, Control 2, Meta 4 and Shift 8", () => {
  expect(
    modifiersOf({ altKey: true, ctrlKey: true, metaKey: true, shiftKey: true }),
  ).toBe(15);
  expect(
    modifiersOf(
      { altKey: true, ctrlKey: true, metaKey: false, shiftKey: false },
      true,
    ),
  ).toBe(0);
});

test("a paste becomes bounded text with a line break as Enter", () => {
  expect(pasteSteps("")).toEqual([]);
  expect(pasteSteps("hola")).toEqual([{ type: "text", text: "hola" }]);
  expect(pasteSteps("a\r\nb\nc\rd")).toEqual([
    { type: "text", text: "a" },
    { type: "enter" },
    { type: "text", text: "b" },
    { type: "enter" },
    { type: "text", text: "c" },
    { type: "enter" },
    { type: "text", text: "d" },
  ]);
  // No control character reaches the host.
  expect(pasteSteps("a\tb\u0000c")).toEqual([{ type: "text", text: "a b c" }]);
  const long = pasteSteps("x".repeat(600));
  expect(
    long.map((step) => (step.type === "text" ? step.text.length : 0)),
  ).toEqual([256, 256, 88]);
  // Never splits a character in two.
  const emoji = pasteSteps("😀".repeat(257));
  expect(emoji).toHaveLength(2);
  expect(emoji[0]).toEqual({ type: "text", text: "😀".repeat(256) });
});

test("a point of the panel is a CSS pixel of the page, inside it", () => {
  const box = { left: 100, top: 50, width: 400, height: 200 };
  const page = { width: 800, height: 400 };
  expect(viewPoint({ x: 100, y: 50 }, box, page)).toEqual({ x: 0, y: 0 });
  expect(viewPoint({ x: 300, y: 150 }, box, page)).toEqual({ x: 400, y: 200 });
  // Outside the panel, as in a drag, the point is held at the page's edge.
  expect(viewPoint({ x: 9999, y: -50 }, box, page)).toEqual({ x: 799, y: 0 });
  expect(viewPoint({ x: 1, y: 1 }, { ...box, width: 0 }, page)).toBeNull();
  expect(viewPoint({ x: 1, y: 1 }, box, { width: 0, height: 5 })).toBeNull();
});

test("a wheel turn is whole CSS pixels within the host's bound", () => {
  const sized = { height: 600 };
  expect(wheelDelta({ deltaX: 0, deltaY: 100, deltaMode: 0 }, sized)).toEqual({
    x: 0,
    y: 100,
  });
  expect(wheelDelta({ deltaX: 0, deltaY: 3, deltaMode: 1 }, sized)).toEqual({
    x: 0,
    y: 120,
  });
  expect(wheelDelta({ deltaX: 0, deltaY: -1, deltaMode: 2 }, sized)).toEqual({
    x: 0,
    y: -600,
  });
  expect(
    wheelDelta({ deltaX: 99999, deltaY: -99999, deltaMode: 0 }, sized),
  ).toEqual({ x: 10000, y: -10000 });
});

test("buttons and click counts are the host's", () => {
  expect([0, 1, 2, 3, 4].map(pointerButton)).toEqual([
    "left",
    "middle",
    "right",
    null,
    null,
  ]);
  expect([0, 1, 2, 3, 7].map(clickCount)).toEqual([1, 1, 2, 3, 3]);
});

test("the panel's size is whole pixels the host accepts", () => {
  expect(sedeViewSize({ width: 800.9, height: 600.2 }, 1.5)).toEqual({
    cssWidth: 800,
    cssHeight: 600,
    scale: 1.5,
  });
  expect(sedeViewSize({ width: 0, height: 600 }, 1)).toBeNull();
  expect(sedeViewSize({ width: 0.4, height: 600 }, 1)).toBeNull();
  expect(sedeViewSize({ width: 9000, height: 9000 }, 9)).toEqual({
    cssWidth: 4096,
    cssHeight: 4096,
    scale: 4,
  });
  expect(sedeViewSize({ width: 10, height: 10 }, Number.NaN)?.scale).toBe(1);
  expect(sedeViewSize({ width: 10, height: 10 }, 0.1)?.scale).toBe(0.5);
});

test("a refusal is its code, and anything else never reached the host", () => {
  expect(sedeViewFailure({ code: "conflict", operation_id: "op-1" })).toEqual({
    code: "conflict",
    operation_id: null,
  });
  for (const code of [
    "invalid",
    "not_admitted",
    "unavailable",
    "file_unavailable",
    "refused",
    "unknown",
    "not_signed_in",
  ])
    expect(sedeViewFailure({ code }).code).toBe(code);
  expect(sedeViewFailure({ code: "invalid_arguments" }).code).toBe(
    "unavailable",
  );
  expect(sedeViewFailure(new Error("boom")).code).toBe("unavailable");
  expect(sedeViewFailure(null).code).toBe("unavailable");
});

const announce = (
  view: number,
  byteLength: number,
): Extract<SedeViewMessage, { kind: "image" }> => ({
  kind: "image",
  view,
  sequence: 1,
  byte_length: byteLength,
  pixel_width: 10,
  pixel_height: 10,
  css_width: 10,
  css_height: 10,
  scale: 1,
});

const reading = () => {
  const events: SedeViewEvent[] = [];
  return { events, reader: sedeViewReader((event) => events.push(event)) };
};

test("what the host sends before its answer waits for the view it belongs to", () => {
  const { events, reader } = reading();
  reader.accept({ kind: "opened", view: 4 });
  reader.accept(announce(4, 3));
  reader.accept(new Uint8Array([1, 2, 3]).buffer);
  reader.accept({ kind: "opened", view: 3 });
  expect(events).toEqual([]);
  reader.open(4);
  expect(events.map((event) => event.kind)).toEqual(["opened", "image"]);
  const image = events[1];
  expect(image?.kind === "image" && image.bytes?.byteLength).toBe(3);
  // A message of another view is never an event.
  reader.accept({ kind: "closing", view: 3 });
  reader.accept({ kind: "closing", view: 4 });
  expect(events.map((event) => event.kind)).toEqual([
    "opened",
    "image",
    "closing",
  ]);
});

test("an image is its announcement with its bytes, or with none when they fall short", () => {
  const { events, reader } = reading();
  reader.open(1);
  // Whole: raw bytes as a buffer, a typed array and the JSON fallback.
  reader.accept(announce(1, 3));
  reader.accept(new Uint8Array([9, 8, 7]).buffer);
  reader.accept(announce(1, 3));
  reader.accept(new Uint8Array([9, 8, 7]));
  reader.accept(announce(1, 3));
  reader.accept([9, 8, 7]);
  // The wrong length is not an image to draw, but is still one to credit.
  reader.accept(announce(1, 5));
  reader.accept(new Uint8Array([1]).buffer);
  // Announced and never followed by its bytes: the next message shows it.
  reader.accept(announce(1, 3));
  reader.accept({ kind: "closing", view: 1 });
  // Bytes nothing announced are dropped.
  reader.accept(new Uint8Array([1, 2]).buffer);
  const summary = events.map((event) =>
    event.kind === "image"
      ? event.bytes
        ? event.bytes.byteLength
        : null
      : event.kind,
  );
  expect(summary).toEqual([3, 3, 3, null, null, "closing"]);
});
