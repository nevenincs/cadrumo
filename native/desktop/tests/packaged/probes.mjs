// Probe sequences shared by the packaged run and the harness's own tests.
import { randomBytes } from "node:crypto";
import { readFileSync, watch } from "node:fs";
import { isAbsolute, relative } from "node:path";

import { docsProbe } from "./browser.mjs";
import { refusalVerdict, tokenVerdict } from "./verdicts.mjs";
import { sleep } from "./session.mjs";

export function sedeMissingVerdict({
  absent,
  sentence,
  offer,
  panel,
  records,
  warning,
  expectedSentence,
}) {
  const record = records?.[0];
  const valid =
    absent === true &&
    (expectedSentence
      ? sentence?.includes(expectedSentence)
      : /(?:not|isn't) installed/i.test(sentence ?? "")) &&
    offer === true &&
    panel === true &&
    records?.length === 1 &&
    record.service?.event === "feature_refused" &&
    record.service?.feature === "sede_view" &&
    record.service?.refusal === "component_not_ready" &&
    record.service?.item === "browser" &&
    warning === true;
  return {
    verdict: valid ? "PASS" : "FAIL",
    detail: valid
      ? "Sede names the missing browser, opens its provisioning panel and records a local warning"
      : "Sede's missing-browser offer or persisted warning is missing",
    data: { absent, sentence, offer, panel, records, warning },
  };
}

/** The existing native log is watched before navigation, so no delay stands for a write. */
export async function runSedeMissingAcceptance({
  session,
  driver,
  expectedSentence,
}) {
  const read = await driver.read();
  const absent =
    read.snapshot?.rows.find((row) => row.item === "browser")?.state ===
    "absent";
  const diagnostics = await session.call("diagnostics_snapshot", { after: 0 });
  if (!diagnostics.ok || !diagnostics.value.paths?.current)
    throw new Error("the local diagnostics log is unavailable");
  const path = diagnostics.value.paths.current;
  const inside = relative(driver.layout.root, path);
  if (!inside || inside.startsWith("..") || isAbsolute(inside))
    throw new Error("the native log escaped the throwaway root");
  const prior = new Set(
    diagnostics.value.events.map(
      (event) => `${event.hostPid}:${event.sequence}`,
    ),
  );
  const records = () =>
    readFileSync(path, "utf8")
      .split("\n")
      .slice(0, -1)
      .filter(Boolean)
      .map((line) => JSON.parse(line))
      .filter(
        (event) =>
          !prior.has(`${event.hostPid}:${event.sequence}`) &&
          event.service?.event === "feature_refused" &&
          event.service?.feature === "sede_view",
      );
  let watcher;
  let timer;
  const persisted = new Promise((resolve, reject) => {
    const inspect = () => {
      try {
        const found = records();
        if (found.length) resolve(found);
      } catch (error) {
        reject(error);
      }
    };
    watcher = watch(path, inspect);
    watcher.on("error", reject);
    timer = setTimeout(
      () => reject(new Error("Sede refusal did not reach the local log")),
      30000,
    );
    inspect();
  });
  persisted.catch(() => undefined);
  try {
    await driver.closeDialog();
    await session.page.locator('[data-rail="browser"]').click();
    const offer = session.page.locator('[data-setup-offer="browser"]');
    await offer.waitFor({ state: "visible", timeout: 30000 });
    const sentence = await offer.locator("xpath=..").innerText();
    await offer.getByRole("button").click();
    await session.page
      .locator('.setup-dialog [data-setup-row="browser"]')
      .waitFor({ state: "visible" });
    const local = await persisted;
    await driver.closeDialog();
    await session.showTab("logs");
    const warning = await session.page.evaluate(
      () =>
        new Promise((resolve, reject) => {
          const inspect = () => {
            const records = window.__s10.logs.records;
            if (
              records.some(
                (entry) =>
                  entry.level === "WARNING" &&
                  entry.message.includes("feature_refused"),
              )
            ) {
              observer.disconnect();
              clearTimeout(timer);
              resolve(true);
            }
          };
          const observer = new MutationObserver(inspect);
          observer.observe(document, {
            subtree: true,
            childList: true,
            characterData: true,
          });
          const timer = setTimeout(() => {
            observer.disconnect();
            reject(new Error("Sede warning was not projected locally"));
          }, 30000);
          inspect();
        }),
    );
    return sedeMissingVerdict({
      absent,
      sentence,
      offer: true,
      panel: true,
      records: local,
      warning,
      expectedSentence,
    });
  } finally {
    watcher?.close();
    clearTimeout(timer);
  }
}

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
