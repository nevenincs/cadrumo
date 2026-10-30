import { expect, test } from "@playwright/test";
import { sessionFailedText } from "../src/shell/sessionWords";
import type { Translate } from "../src/shell/strings";

// What a failed terminal session says, read through a translator that names
// the key it is asked for and the values it is given. No page is opened.

const ECHO: Translate = Object.assign(
  (key: string, values?: Record<string, string | number>) =>
    values ? `${key} ${JSON.stringify(values)}` : key,
  { locale: "en" },
);

const said = (reason: string) =>
  `desktop.session.failed ${JSON.stringify({ reason })}`;

test("each code a session fails with is worded as a reason, never shown as the code", () => {
  const reasons: Record<string, string> = {
    spawn_failed: "desktop.session.reason.start",
    environment_failed: "desktop.session.reason.environment",
    package_unavailable: "desktop.session.reason.environment",
    read_failed: "desktop.session.reason.output",
    write_failed: "desktop.session.reason.input",
    queue_full: "desktop.session.reason.input",
    session_unavailable: "desktop.session.reason.gone",
    timed_out: "desktop.session.reason.slow",
    child_failed: "desktop.session.reason.stopped",
    cleanup_failed: "desktop.session.reason.close",
  };

  for (const [code, reason] of Object.entries(reasons)) {
    const text = sessionFailedText(ECHO, code);
    expect(text, code).toBe(said(reason));
    expect(text, code).not.toContain(code);
  }
});

test("a code the window does not word, or none at all, gets the general reason", () => {
  for (const code of [
    "unknown",
    "a_code_from_a_newer_host",
    "",
    "constructor",
    "toString",
  ])
    expect(sessionFailedText(ECHO, code), code).toBe(
      said("desktop.session.reason.other"),
    );
});
