// Probe sequences shared by the packaged run and the harness's own tests.
import { randomBytes } from "node:crypto";

import { docsProbe } from "./browser.mjs";
import { refusalVerdict, tokenVerdict } from "./verdicts.mjs";
import { sleep } from "./session.mjs";

/** Host refusals of a missing or wrong token recorded in host diagnostics. */
export async function hostRefusals(session) {
  const snapshot = await session.call("diagnostics_snapshot", { after: 0 });
  return snapshot.ok
    ? snapshot.value.events.filter(
        (event) =>
          event.kind === "failure" &&
          event.failure?.code === "invalid_arguments" &&
          event.failure?.operation === "webview",
      ).length
    : -1;
}

/** Host answers the shell received for IPC callbacks it never registered. */
export function unknownCallbacks(session) {
  return session.console.filter((entry) =>
    /Couldn't find callback id/.test(entry.text),
  ).length;
}

/**
 * One adversarial probe from the docs frame. The command it tries writes a
 * fresh nonce to the clipboard, so a command that ran shows up there; the
 * clipboard must still hold `baseline` afterwards.
 */
export async function refusalProbe(session, kind, { ipcOrigin, baseline }) {
  const nonce = `S10-NONCE-${randomBytes(6).toString("hex")}`;
  const refusalsBefore = await hostRefusals(session);
  const callbacksBefore = unknownCallbacks(session);
  const outcome = await session.docs(docsProbe, {
    kind,
    nonce,
    timeoutMs: 4000,
    ipcOrigin,
  });
  await sleep(1000);
  const clipboard = await session.call("shell_clipboard_read");
  const effect =
    clipboard.ok && clipboard.value.text.includes(nonce)
      ? "the clipboard holds the probe's text"
      : clipboard.ok && clipboard.value.text !== baseline
        ? "the clipboard changed"
        : !clipboard.ok
          ? `the clipboard could not be read (${clipboard.error.code})`
          : null;
  const result = {
    ...outcome,
    refusals: (await hostRefusals(session)) - refusalsBefore,
    hostAnswersToUnknownCallbacks: unknownCallbacks(session) - callbacksBefore,
  };
  return { result, ...refusalVerdict({ ...result, effect }) };
}

/** The shell's token getter state and the docs frame's reach, for tokenVerdict. */
export async function tokenCheck(session) {
  const docs = await session.docs(docsProbe, { kind: "token" });
  const shell = await session.shell(() => {
    const object = window.__CADRUMO_SHELL__;
    const descriptor =
      object && Object.getOwnPropertyDescriptor(object, "token");
    const value = object ? object.token : undefined;
    return {
      getterAtStart: !!window.__s10.tokenGetter?.getter,
      getterNow: !!descriptor?.get,
      valueNow: value === undefined ? "undefined" : typeof value,
      authorized: window.__s10.tokenSeen,
    };
  });
  return { observed: { docs, shell }, ...tokenVerdict({ docs, shell }) };
}
