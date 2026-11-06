import { expect, type Frame, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { seedLayout } from "./layout";
import { label } from "./strings";
import { ABOUT_FIXTURE } from "../../src/dev/fixtures/about";
import { FIXTURE_CALENDAR } from "../../src/dev/fixtures/calendar";

export const local = (path: string) =>
  fileURLToPath(new URL(path, import.meta.url));

// A transport boundary fixture for presentation tests, never a live sign-in
// acceptance claim. The actual Tauri adapter and React shell run unchanged.
export async function signInHost(
  target: Page,
  supported = true,
  deferInitial = false,
  deferInitialList = false,
  bundled = true,
  logLevel = "INFO",
  profiles = [{ name: "Test profile", active: true }],
) {
  await target.addInitScript(
    ({
      supported,
      docs,
      deferInitial,
      deferInitialList,
      logLevel,
      about,
      calendar,
      profiles,
    }) => {
      const state = {
        presence: "absent",
        supported,
        runtimeAvailable: true,
        refusal: null as null | {
          code: string;
          retryAfterSeconds: number | null;
        },
        submitCode: "CREDENTIAL_REJECTED",
        retryAfterSeconds: null as number | null,
        submissions: 0,
        statusReads: 0,
        statusError: "",
        activeStatusReads: 0,
        activeListReads: 0,
        signOuts: 0,
        savedClearCalls: 0,
        savedClearRawPassword: false,
        savedClearToken: false,
        savedClearProfile: null as string | null,
        savedClearFieldEmpty: false,
        savedClearSecretWiped: false,
        savedClearError: "",
        deferSavedClear: false,
        releaseSavedClear: null as (() => void) | null,
        // What the product reports a sign-out leaves standing: the saved
        // setting is on, and whether an issued key can still admit is a
        // separate answer.
        automationAccessRemains: false as boolean | null,
        tuiStarts: 0,
        tuiCloses: 0,
        terminalStarts: [] as string[],
        terminalWrites: [] as string[],
        deferTui: false,
        releaseTui: null as (() => void) | null,
        terminalCloses: 0,
        rawPassword: false,
        tokenHeader: false,
        secretCleared: false,
        profiles,
        listReads: 0,
        profileHeader: null as string | null,
        creations: 0,
        createdHeader: null as string | null,
        createdRawPassword: false,
        createdTokenHeader: false,
        createdSecretCleared: false,
        deferStatus: deferInitial,
        releaseStatus: null as (() => void) | null,
        deferList: deferInitialList,
        releaseList: null as (() => void) | null,
        exitTui: null as (() => void) | null,
        signInUpdate: null as ((signal: unknown) => void) | null,
        viewReads: [] as unknown[],
      };
      let id = 0;
      Object.assign(window, {
        isTauri: true,
        __signInTest: state,
        __CADRUMO_SHELL__: { token: "a".repeat(64) },
        __TAURI_INTERNALS__: {
          transformCallback: () => ++id,
          unregisterCallback: () => undefined,
          async invoke(
            command: string,
            args: Record<string, unknown> | Uint8Array,
            options?: { headers?: Record<string, string> },
          ) {
            switch (command) {
              case "about_info":
                return about;
              case "manager_status":
                return { state: "ready", failure: null };
              case "manager_subscribe":
                if (!(args instanceof Uint8Array))
                  (
                    args.updates as { onmessage: (signal: unknown) => void }
                  ).onmessage({
                    kind: "manager-state",
                    revision: 1,
                    status: { state: "ready", failure: null },
                  });
                return ++id;
              case "manager_unsubscribe":
                return null;
              case "sign_in_subscribe":
                if (!(args instanceof Uint8Array))
                  state.signInUpdate = (signal) =>
                    (
                      args.updates as { onmessage: (signal: unknown) => void }
                    ).onmessage(signal);
                return ++id;
              case "sign_in_unsubscribe":
                state.signInUpdate = null;
                return null;
              case "desktop_environment":
                return {
                  outputLanguage: "en",
                  logLevel,
                  docs: docs
                    ? {
                        state: "bundled",
                        origin: docs,
                        languages: [
                          { code: "en", entry: `${docs}/index.html` },
                        ],
                      }
                    : { state: "notBundled" },
                };
              case "sign_in_status": {
                ++state.statusReads;
                if (state.activeStatusReads + state.activeListReads > 0)
                  throw { code: "queue_full" };
                ++state.activeStatusReads;
                const snapshot = {
                  supported: state.supported,
                  state: state.presence,
                  active_profile:
                    state.profiles.find((profile) => profile.active)?.name ??
                    null,
                  runtimeAvailable: state.runtimeAvailable,
                  refusal: state.refusal,
                };
                if (state.deferStatus) {
                  state.deferStatus = false;
                  await new Promise<void>((resolve) => {
                    state.releaseStatus = resolve;
                  });
                }
                --state.activeStatusReads;
                if (state.statusError) throw { code: state.statusError };
                return snapshot;
              }
              case "sign_in_submit": {
                ++state.submissions;
                state.rawPassword =
                  args instanceof Uint8Array &&
                  new TextDecoder().decode(args) === "secret á漢";
                state.tokenHeader =
                  options?.headers?.["x-cadrumo-token"] === "a".repeat(64);
                state.profileHeader =
                  options?.headers?.["x-cadrumo-profile"] ?? null;
                setTimeout(() => {
                  state.secretCleared =
                    args instanceof Uint8Array &&
                    args.every((byte) => byte === 0);
                }, 0);
                if (state.submitCode)
                  return {
                    kind: "refused",
                    code: state.submitCode,
                    retryAfterSeconds: state.retryAfterSeconds,
                  };
                state.presence = "present";
                if (state.profileHeader !== null) {
                  const selected = decodeURIComponent(state.profileHeader);
                  state.profiles = state.profiles.map((profile) => ({
                    ...profile,
                    active: profile.name === selected,
                  }));
                }
                return {
                  kind: "signed-in",
                  status: {
                    supported: state.supported,
                    state: "present",
                    active_profile:
                      state.profiles.find((profile) => profile.active)?.name ??
                      null,
                    runtimeAvailable: true,
                    refusal: null,
                  },
                };
              }
              case "profile_list": {
                ++state.listReads;
                if (state.activeStatusReads + state.activeListReads > 0)
                  throw { code: "queue_full" };
                ++state.activeListReads;
                const snapshot = {
                  profiles: state.profiles.map((profile) => ({ ...profile })),
                  complete: true,
                };
                if (state.deferList) {
                  state.deferList = false;
                  await new Promise<void>((resolve) => {
                    state.releaseList = resolve;
                  });
                }
                --state.activeListReads;
                return snapshot;
              }
              case "profile_create": {
                ++state.creations;
                state.createdHeader =
                  options?.headers?.["x-cadrumo-profile"] ?? null;
                state.createdRawPassword =
                  args instanceof Uint8Array &&
                  new TextDecoder().decode(args) === "secret á漢";
                state.createdTokenHeader =
                  options?.headers?.["x-cadrumo-token"] === "a".repeat(64);
                setTimeout(() => {
                  state.createdSecretCleared =
                    args instanceof Uint8Array &&
                    args.every((byte) => byte === 0);
                }, 0);
                const name = decodeURIComponent(state.createdHeader ?? "");
                state.profiles = [
                  ...state.profiles.map((held) => ({ ...held, active: false })),
                  { name, active: true },
                ];
                return { kind: "created", name };
              }
              case "profile_views_notifications":
                state.viewReads.push({ command, ...args });
                return {
                  captured_at: "2026-10-20T09:00:00Z",
                  row_count: 4,
                  unread: 2,
                };
              case "profile_views_calendar":
                state.viewReads.push({ command, ...args });
                return calendar;
              case "sign_out_with_password": {
                ++state.savedClearCalls;
                state.savedClearRawPassword =
                  args instanceof Uint8Array &&
                  new TextDecoder().decode(args) === "secret á漢";
                state.savedClearToken =
                  options?.headers?.["x-cadrumo-token"] === "a".repeat(64);
                state.savedClearProfile =
                  options?.headers?.["x-cadrumo-profile"] ?? null;
                state.savedClearFieldEmpty =
                  document.querySelector<HTMLInputElement>("#profile-password")
                    ?.value === "";
                try {
                  if (state.deferSavedClear)
                    await new Promise<void>((resolve) => {
                      state.releaseSavedClear = resolve;
                    });
                  if (state.savedClearError)
                    throw { code: state.savedClearError };
                  state.presence = "absent";
                  return {
                    remainingAccess: {
                      automationEnabled: true,
                      automationAccessRemains: state.automationAccessRemains,
                      automationRevoked: false,
                    },
                  };
                } finally {
                  setTimeout(() => {
                    state.savedClearSecretWiped =
                      args instanceof Uint8Array &&
                      args.every((byte) => byte === 0);
                  }, 0);
                }
              }
              case "sign_out":
                ++state.signOuts;
                state.presence = "absent";
                return {
                  remainingAccess: {
                    automationEnabled: true,
                    automationAccessRemains: state.automationAccessRemains,
                    automationRevoked: false,
                  },
                };
              case "terminal_open":
                if (!(args instanceof Uint8Array))
                  state.terminalStarts.push(String(args.kind));
                if (!(args instanceof Uint8Array) && args.kind === "tui") {
                  ++state.tuiStarts;
                  const frames = args.frames as {
                    onmessage: (data: ArrayBuffer) => void;
                  };
                  frames.onmessage(Uint8Array.from([1]).buffer);
                  if (state.deferTui) {
                    (
                      args.frames as { onmessage: (data: ArrayBuffer) => void }
                    ).onmessage(Uint8Array.from([0, 27, 91, 54, 110]).buffer);
                    await new Promise<void>((resolve) => {
                      state.releaseTui = resolve;
                    });
                  }
                  state.exitTui = () =>
                    (
                      args.frames as { onmessage: (data: ArrayBuffer) => void }
                    ).onmessage(
                      Uint8Array.from([
                        2,
                        ...new TextEncoder().encode('{"code":0}'),
                      ]).buffer,
                    );
                }
                return {
                  session:
                    !(args instanceof Uint8Array) && args.kind === "tui"
                      ? 99
                      : ++id,
                };
              case "terminal_close":
                ++state.terminalCloses;
                if (!(args instanceof Uint8Array) && args.session === 99)
                  ++state.tuiCloses;
                return {};
              case "terminal_write":
                if (args instanceof Uint8Array)
                  state.terminalWrites.push(new TextDecoder().decode(args));
                return null;
              case "logs_subscribe":
                return {
                  subscription: 1,
                  state: { kind: "missing", detail: "" },
                };
              default:
                return null;
            }
          },
        },
      });
    },
    {
      supported,
      docs: bundled ? DOCS : null,
      deferInitial,
      deferInitialList,
      logLevel,
      about: ABOUT_FIXTURE,
      calendar: FIXTURE_CALENDAR,
      profiles,
    },
  );
  await target.addInitScript(() => {
    if (localStorage.getItem("cadrumo-shell-layout")) return;
    localStorage.setItem(
      "cadrumo-shell-layout",
      // The TUI starts closed, so a test opens it as a person does.
      JSON.stringify({ layout: { page: "docs", tuiShown: false } }),
    );
  });
  await serveDocs(target);
  await target.goto("/");
}

export const signInState = (target: Page) =>
  target.evaluate(
    () =>
      (window as unknown as { __signInTest: Record<string, unknown> })
        .__signInTest,
  );

export async function revealTui(target: Page) {
  await target
    .locator(".rail")
    .getByRole("button", { name: label("desktop.rail.tui") })
    .click();
}

/** How the documentation's pane and the TUI's stand: side by side, or one
 * above the other. */
export async function arrangement(target: Page): Promise<"row" | "column"> {
  const docs = await target.locator('[data-dock-pane="docs"]').boundingBox();
  const tui = await target.locator('[data-dock-pane="tui"]').boundingBox();
  if (!docs || !tui)
    throw new Error("The documentation and TUI are not both shown.");
  const [first, second] =
    docs.x <= tui.x && docs.y <= tui.y ? [docs, tui] : [tui, docs];
  if (second.x >= first.x + first.width - 1) return "row";
  if (second.y >= first.y + first.height - 1) return "column";
  throw new Error("The documentation and TUI overlap.");
}

// A stand-in documentation origin. It is a different origin from the shell,
// and its pages load the real desktop bridge script.
export const DOCS = "http://docs.cadrumo.test";
export const bridge = readFileSync(
  local("../../../../docs/_static/cadrumo-desktop-bridge.js"),
  "utf8",
);
export const page = (title: string, body: string) =>
  `<!doctype html><html lang="en"><head><meta charset="utf-8"><title>${title}</title>` +
  `<script src="/bridge.js"></script></head><body data-theme="light">${body}</body></html>`;
export const PAGES: Record<string, string> = {
  "/index.html": page(
    "Stand-in documentation",
    '<h1>Stand-in documentation</h1><p id="text">Casilla 01 total</p>' +
      '<a id="internal" href="/second.html">Second page</a> <a id="external" href="https://example.org/">External</a>',
  ),
  "/second.html": page("Second page", "<h1>Second page</h1>"),
};

export async function serveDocs(
  target: Page,
  indexHtml = PAGES["/index.html"],
) {
  await target.route(`${DOCS}/**`, (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/bridge.js")
      return route.fulfill({ contentType: "text/javascript", body: bridge });
    const html = path === "/index.html" ? indexHtml : PAGES[path];
    return html
      ? route.fulfill({ contentType: "text/html", body: html })
      : route.fulfill({ status: 404, body: "" });
  });
}

export async function openWithDocs(target: Page, indexHtml?: string) {
  await seedLayout(target);
  await serveDocs(target, indexHtml);
  await target.goto(`/?docs=${encodeURIComponent(`${DOCS}/index.html`)}`);
  await expect(target.frameLocator(".docs-frame").locator("h1")).toHaveText(
    "Stand-in documentation",
  );
}

/** The documentation frame's own execution context, on the stand-in origin. */
export function docsFrame(target: Page): Frame {
  const frame = target.frames().find((f) => f.url().startsWith(DOCS));
  if (!frame) throw new Error("The documentation frame is not loaded.");
  return frame;
}
