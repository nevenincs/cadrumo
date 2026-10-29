import type {
  AeatSyncPrepared,
  AeatSyncPreparePort,
} from "../shell/aeatSyncPrepare";

/** What the scenario's pre-update check finds. */
export type AeatSyncPrepareMode =
  /** Everything is in place and the sign-in is immediate. */
  | "ready"
  /** The secure browser is not installed. */
  | "browser_missing"
  /** The browser's row needs its own recovery. */
  | "browser_attention"
  /** The profile has no AEAT access yet. */
  | "access_missing"
  /** Sign-in waits for approval on the phone. */
  | "phone"
  /** The sign-in is refused. */
  | "refused";

const MB = 1024 * 1024;

/** A synthetic pre-update check. `browserReady` lets a story that stages the
 * setup report the browser as installed once its setup has finished. */
export function aeatSyncPrepareFixture(
  mode: AeatSyncPrepareMode,
  options: { browserReady?: () => boolean; waitMs?: number } = {},
): AeatSyncPreparePort {
  let cancel: (() => void) | null = null;
  return {
    prepare: (): Promise<AeatSyncPrepared> => {
      const installed =
        (mode !== "browser_missing" && mode !== "browser_attention") ||
        options.browserReady?.() === true;
      return Promise.resolve({
        browser: installed
          ? { state: "ready" }
          : mode === "browser_attention"
            ? { state: "attention" }
            : { state: "missing", bytes: 180 * MB },
        access: mode === "access_missing" ? "needs_access" : "ready",
      });
    },
    signIn: (stage) =>
      new Promise<void>((resolve, reject) => {
        if (mode === "refused") return reject({ code: "refused" });
        if (mode !== "phone") return resolve();
        stage("waiting_for_phone");
        const timer = setTimeout(resolve, options.waitMs ?? 60_000);
        cancel = () => {
          clearTimeout(timer);
          reject({ code: "cancelled" });
        };
      }),
    cancelSignIn: () => {
      cancel?.();
      cancel = null;
      return Promise.resolve();
    },
  };
}
