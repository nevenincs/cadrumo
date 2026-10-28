// The scenario host's Sede view: a made-up page drawn on a canvas in the
// browser and sent as JPEG images, over the same events the desktop host's
// channel carries. No page of any site is fetched or shown. It answers input
// by drawing what it received, honours credit as the host does (two images at
// first, one more for each the window credits, the newest replacing the rest),
// keeps one view at a time and publishes its made-up session when closed. A
// person's input while a made-up login runs ends that login, as the host's
// interrupt does. A scenario plays a dialog, a download or a file
// chooser through `window.__scenarioSedeView`, and reads back what the page
// received and how each prompt was answered. Design and test evidence only;
// its call lines name a verb, never a value.

import type {
  SedeViewDialogKind,
  SedeViewEndReason,
  SedeViewInput,
  SedeViewPageSecurity,
  SedeViewPhase,
  SedeViewPublication,
  SedeViewTransfer,
} from "../ipc/contract";
import type {
  SedeViewEvent,
  SedeViewPort,
  SedeViewSession,
  SedeViewSize,
} from "../shell/sedeView";

/** A synthetic origin that belongs to no real site, its start path and a
 * title no part of the window shows. */
export const SEDE_VIEW_ORIGIN = "https://sede.example.test";
export const SEDE_VIEW_HOME = "/inicio";
export const SEDE_VIEW_TITLE = "Titulo sintetico de la pagina";
const START_CREDIT = 2;
/** The most input events the made-up page keeps for a scenario to read. */
const INPUT_KEPT = 400;

/** How the person answered one prompt of the page, in the order answered. */
export type SedeViewAnswer =
  | { kind: "dialog"; id: number; accepted: boolean; text: string | null }
  | { kind: "download"; id: number; accepted: boolean }
  | { kind: "file_chooser"; id: number; accepted: boolean };

/** What a scenario can play into the open view. */
export type SedeViewFixtureControls = {
  dialog(kind: SedeViewDialogKind, message: string, answer?: string): void;
  download(filename: string): void;
  /** AEAT showed the person signed in as another taxpayer. */
  identityMismatch(): void;
  fileChooser(multiple: boolean): void;
  /** Follows a link off https: to a plain `http:` page, or to one whose
   * origin is not known. */
  leave(security: Exclude<SedeViewPageSecurity, "secure">): void;
  phase(phase: SedeViewPhase): void;
  /** Ends the view as the host would, without the window asking. */
  end(reason: SedeViewEndReason, publication?: SedeViewPublication): void;
  /** How many input events of each kind the made-up page has received. */
  received(): Readonly<Record<string, number>>;
  /** The newest input events the made-up page received, oldest first. */
  inputs(): readonly SedeViewInput[];
  /** How many images the made-up page has sent. */
  images(): number;
  /** Every answer to a dialog, a download or a file chooser, in order. */
  answers(): readonly SedeViewAnswer[];
};

declare global {
  interface Window {
    __scenarioSedeView?: SedeViewFixtureControls;
  }
}

export type SedeViewFixtureOptions = {
  say: (call: string) => void;
  /** How long publishing the session takes when the view is closed. */
  publishMs?: number;
  /** The setup action the runtime's recorded verdict names when a component
   * the view needs is not set up: each view then ends refused before its
   * browser opens. */
  needs?: string;
};

type Open = {
  id: number;
  size: SedeViewSize;
  listener: (event: SedeViewEvent) => void;
  ended: boolean;
  credit: number;
  stale: boolean;
  sequence: number;
  history: { path: string; security: SedeViewPageSecurity }[];
  at: number;
  phase: SedeViewPhase;
  received: Record<string, number>;
  inputs: SedeViewInput[];
  answers: SedeViewAnswer[];
  last: string;
  transfers: number;
};

async function draw(open: Open): Promise<ArrayBuffer> {
  const { cssWidth, cssHeight, scale } = open.size;
  const width = Math.max(1, Math.round(cssWidth * scale));
  const height = Math.max(1, Math.round(cssHeight * scale));
  const canvas = new OffscreenCanvas(width, height);
  const context = canvas.getContext("2d");
  if (!context) return new ArrayBuffer(0);
  context.scale(scale, scale);
  context.fillStyle = "#f4f1ea";
  context.fillRect(0, 0, cssWidth, cssHeight);
  context.fillStyle = "#8a1f1f";
  context.fillRect(0, 0, cssWidth, 56);
  context.fillStyle = "#ffffff";
  context.font = "600 20px sans-serif";
  context.fillText("Synthetic page", 24, 35);
  context.fillStyle = "#222222";
  context.font = "16px sans-serif";
  const lines = [
    `Path ${open.history[open.at]?.path ?? SEDE_VIEW_HOME}`,
    open.phase === "acquiring"
      ? "A made-up login is running."
      : "Browsing a made-up page.",
    `Pointer events ${open.received.pointer ?? 0}, keys ${open.received.key ?? 0}`,
    `Text events ${open.received.text ?? 0}, wheel ${open.received.wheel ?? 0}`,
    `Last ${open.last}`,
  ];
  lines.forEach((line, index) => context.fillText(line, 24, 96 + index * 28));
  const blob = await canvas.convertToBlob({
    type: "image/jpeg",
    quality: 0.8,
  });
  return blob.arrayBuffer();
}

/** The scenario host's Sede view port. */
export function sedeViewFixture({
  say,
  publishMs = 600,
  needs,
}: SedeViewFixtureOptions): SedeViewPort {
  let issued = 0;
  let current: Open | null = null;

  // A page off https states only its marker, and has no address to open.
  const secure = (open: Open) =>
    (open.history[open.at]?.security ?? "secure") === "secure";
  const state = (open: Open) => {
    const shown = secure(open);
    open.listener({
      kind: "state",
      view: open.id,
      security: open.history[open.at]?.security ?? "secure",
      origin: shown ? SEDE_VIEW_ORIGIN : null,
      path: shown ? (open.history[open.at]?.path ?? SEDE_VIEW_HOME) : null,
      title: SEDE_VIEW_TITLE,
      can_go_back: open.at > 0,
      can_go_forward: open.at < open.history.length - 1,
      loading: false,
      phase: open.phase,
      external: shown,
    });
  };

  // A change is drawn at once when the window has credit, and otherwise
  // waits as the newest image until it credits one.
  const frame = async (open: Open) => {
    if (open.ended) return;
    if (open.credit < 1) {
      open.stale = true;
      return;
    }
    open.credit -= 1;
    open.stale = false;
    const bytes = await draw(open);
    if (open.ended) return;
    open.sequence += 1;
    open.listener({
      kind: "image",
      view: open.id,
      sequence: open.sequence,
      byte_length: bytes.byteLength,
      pixel_width: Math.round(open.size.cssWidth * open.size.scale),
      pixel_height: Math.round(open.size.cssHeight * open.size.scale),
      css_width: open.size.cssWidth,
      css_height: open.size.cssHeight,
      scale: open.size.scale,
      bytes,
    });
  };

  const finish = (
    open: Open,
    reason: SedeViewEndReason,
    publication: SedeViewPublication | null,
  ) => {
    if (open.ended) return;
    open.ended = true;
    open.listener({
      kind: "ended",
      view: open.id,
      reason,
      code: null,
      outcome: {
        condition: "succeeded",
        end: reason === "closed" ? "closed" : "stopped",
        publication,
      },
      recovery_action_id: null,
    });
    if (window.__scenarioSedeView && current === open)
      delete window.__scenarioSedeView;
  };

  const controls = (open: Open): SedeViewFixtureControls => ({
    dialog(kind, message, answer) {
      open.transfers += 1;
      open.listener({
        kind: "notice",
        view: open.id,
        code: "dialog_opened",
        dialog: {
          dialog_id: open.transfers,
          dialog_kind: kind,
          message,
          default_prompt: answer ?? null,
        },
      });
    },
    identityMismatch() {
      open.listener({
        kind: "notice",
        view: open.id,
        code: "identity_mismatch",
        dialog: null,
      });
    },
    download(filename) {
      open.transfers += 1;
      open.listener({
        kind: "download",
        view: open.id,
        transfer_id: open.transfers,
        filename,
        size: null,
        mime: null,
      });
    },
    fileChooser(multiple) {
      open.transfers += 1;
      open.listener({
        kind: "file_chooser",
        view: open.id,
        chooser_id: open.transfers,
        accept: [],
        multiple,
      });
    },
    leave(security) {
      open.history = [
        ...open.history.slice(0, open.at + 1),
        { path: "/fuera", security },
      ];
      open.at = open.history.length - 1;
      state(open);
      void frame(open);
    },
    phase(phase) {
      open.phase = phase;
      state(open);
      void frame(open);
    },
    end: (reason, publication) => finish(open, reason, publication ?? null),
    received: () => ({ ...open.received }),
    inputs: () => [...open.inputs],
    images: () => open.sequence,
    answers: () => [...open.answers],
  });

  const session = (open: Open): SedeViewSession => {
    const live = (): Promise<void> =>
      open.ended
        ? Promise.reject({ code: "not_admitted", operation_id: null })
        : Promise.resolve();
    const navigated = (verb: string, step: () => void) => {
      say(`sedeViewNavigate ${verb}`);
      step();
      state(open);
      void frame(open);
    };
    return {
      async input(event: SedeViewInput) {
        await live();
        say(`sedeViewInput ${event.type}`);
        open.received[event.type] = (open.received[event.type] ?? 0) + 1;
        open.inputs.push(event);
        if (open.inputs.length > INPUT_KEPT) open.inputs.shift();
        // The person takes a login that runs over, and the page goes on.
        if (open.phase === "acquiring") {
          open.phase = "browsing";
          state(open);
        }
        open.last =
          event.type === "pointer"
            ? `${event.action} at ${event.x}, ${event.y}`
            : event.type === "key"
              ? `${event.action} ${event.key}`
              : event.type === "text"
                ? `text ${event.text}`
                : `wheel ${event.delta_y}`;
        void frame(open);
      },
      async navigate(verb) {
        await live();
        navigated(verb, () => {
          if (verb === "back") open.at = Math.max(0, open.at - 1);
          else if (verb === "forward")
            open.at = Math.min(open.history.length - 1, open.at + 1);
          else if (verb === "home") {
            open.history = [
              ...open.history.slice(0, open.at + 1),
              { path: SEDE_VIEW_HOME, security: "secure" },
            ];
            open.at = open.history.length - 1;
          }
        });
      },
      async resize(size) {
        await live();
        say("sedeViewResize");
        open.size = size;
        void frame(open);
      },
      async credit() {
        await live();
        say("sedeViewCredit");
        open.credit = Math.min(START_CREDIT, open.credit + 1);
        if (open.stale) void frame(open);
      },
      async dialog(dialogId, accept, promptText) {
        await live();
        say(`sedeViewDialog ${accept ? "accept" : "dismiss"}`);
        open.answers.push({
          kind: "dialog",
          id: dialogId,
          accepted: accept,
          text: promptText ?? null,
        });
      },
      async downloadAnswer(transferId, save) {
        await live();
        say(`sedeViewDownload ${save ? "save" : "decline"}`);
        open.answers.push({ kind: "download", id: transferId, accepted: save });
        if (save)
          window.setTimeout(() => {
            if (open.ended) return;
            open.listener({
              kind: "download_ended",
              view: open.id,
              transfer_id: transferId,
              outcome: "done" satisfies SedeViewTransfer,
            });
          }, 100);
        return { saving: save };
      },
      async fileChooserAnswer(chooserId, choose) {
        await live();
        say(`sedeViewUpload ${choose ? "choose" : "cancel"}`);
        open.answers.push({
          kind: "file_chooser",
          id: chooserId,
          accepted: choose,
        });
        window.setTimeout(() => {
          if (open.ended) return;
          open.listener({
            kind: "upload_ended",
            view: open.id,
            chooser_id: chooserId,
            outcome: choose ? "done" : "cancelled",
          });
        }, 100);
        return { supplied: choose ? 1 : 0 };
      },
      async openExternal() {
        await live();
        if (!secure(open))
          return Promise.reject({ code: "unavailable", operation_id: null });
        say("sedeViewOpenExternal page");
      },
      async close() {
        if (open.ended) return Promise.reject({ code: "not_admitted" });
        say("sedeViewClose");
        open.phase = "closing";
        open.listener({ kind: "closing", view: open.id });
        window.setTimeout(() => finish(open, "closed", "published"), publishMs);
        return undefined;
      },
    };
  };

  return {
    async open(size, listener) {
      if (current && !current.ended)
        throw { code: "conflict", operation_id: null };
      say("sedeViewOpen");
      issued += 1;
      const open: Open = {
        id: issued,
        size,
        listener,
        ended: false,
        credit: START_CREDIT,
        stale: false,
        sequence: 0,
        history: [{ path: SEDE_VIEW_HOME, security: "secure" }],
        at: 0,
        phase: "browsing",
        received: {},
        inputs: [],
        answers: [],
        last: "nothing yet",
        transfers: 0,
      };
      current = open;
      if (needs !== undefined) {
        window.setTimeout(() => {
          open.ended = true;
          listener({
            kind: "ended",
            view: open.id,
            reason: "component_not_ready",
            code: null,
            outcome: { condition: "refused", end: null, publication: null },
            recovery_action_id: needs,
          });
        }, 0);
        return session(open);
      }
      window.__scenarioSedeView = controls(open);
      // The host answers first; the browser opens after.
      window.setTimeout(() => {
        if (open.ended) return;
        listener({ kind: "opened", view: open.id });
        state(open);
        void frame(open);
      }, 0);
      return session(open);
    },
  };
}
