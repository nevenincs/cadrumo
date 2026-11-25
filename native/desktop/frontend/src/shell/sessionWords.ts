import type { Translate } from "./strings";

// Why a terminal session failed, in the person's language. The host reports a
// closed code and never its own text; the window words each code it knows and
// gives every other one, or a failure that carried no code, the general reason.

const REASONS: ReadonlyMap<string, string> = new Map([
  ["spawn_failed", "desktop.session.reason.start"],
  ["environment_failed", "desktop.session.reason.environment"],
  ["package_unavailable", "desktop.session.reason.environment"],
  ["read_failed", "desktop.session.reason.output"],
  ["write_failed", "desktop.session.reason.input"],
  ["queue_full", "desktop.session.reason.input"],
  ["session_unavailable", "desktop.session.reason.gone"],
  ["timed_out", "desktop.session.reason.slow"],
  ["child_failed", "desktop.session.reason.stopped"],
  ["cleanup_failed", "desktop.session.reason.close"],
]);

/** The sentence that says a session failed, with its reason in words. */
export function sessionFailedText(t: Translate, code: string): string {
  return t("desktop.session.failed", {
    reason: t(REASONS.get(code) ?? "desktop.session.reason.other"),
  });
}
