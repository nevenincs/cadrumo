// Page-dependent evidence of a failed check. The page can be legitimately gone
// when a check fails (cleanup checks run after the window or host closed), so a
// read that finds it closed records a `page_closed` status under the usual
// evidence name instead of surfacing a raw error. Collecting evidence never
// throws, so it cannot change a check verdict or the cleanup outcome.

export const PAGE_CLOSED = "page_closed";
export const CAPTURE_FAILED = "capture_failed";
export const CAPTURED = "captured";

const GONE =
  /Target (page, context or browser )?(has been )?closed|(Page|Context|Browser|Session) (has been )?closed|Connection closed/i;

/** True when the error says the page, context or browser no longer exists. */
export function pageGone(error) {
  return GONE.test(String(error?.message ?? error));
}

/**
 * Reads one piece of page evidence and writes it as `name`. Returns the status:
 * `captured`, `page_closed` or `capture_failed`; never throws.
 */
export async function capturePageEvidence(results, name, read) {
  let value;
  let status = CAPTURED;
  let reason;
  try {
    value = await read();
  } catch (error) {
    status = pageGone(error) ? PAGE_CLOSED : CAPTURE_FAILED;
    reason = String(error?.message ?? error).split("\n")[0];
  }
  try {
    results.evidence(name, status === CAPTURED ? value : { status, reason });
  } catch {
    return CAPTURE_FAILED;
  }
  return status;
}

/** Captures the shell and host evidence of a failed provisioning check. */
export async function captureProvisioningFailure(session, results, id) {
  if (!session) return {};
  const statuses = {};
  const take = async (name, read) => {
    statuses[name] = await capturePageEvidence(results, name, read);
  };
  await take(`${id}-ui.json`, () =>
    session.shell(() => ({
      language: document.documentElement.lang,
      surfaces: [
        ...document.querySelectorAll(
          '.setup-dialog, .pane-tui, [data-slot="local-models"], [data-slot="local-models-signed-out"], .profile-status',
        ),
      ].map((node) => ({
        slot: node.getAttribute("data-slot"),
        className: node.className,
        text: node.textContent.trim().slice(0, 12000),
      })),
      setup: window.__s10.setupLatest,
      documentation: window.__s14DocsFailure ?? null,
      commands: window.__s10.ipc
        .slice(-80)
        .map(({ cmd, ok, code }) => ({ cmd, ok, code })),
    })),
  );
  await take(`${id}-diagnostics.json`, () =>
    session.call("diagnostics_snapshot", { after: 0 }),
  );
  if (/^(palette|localized|settings-docs)/.test(id))
    await take(`${id}-docs.json`, () =>
      session.docs(() => ({
        href: location.href,
        language: document.documentElement.lang,
        messages: window.__s10.messages.slice(-30),
        keys: window.__s10.keys.slice(-10),
      })),
    );
  if (id.startsWith("provisioning-3"))
    await take(`${id}-models.json`, () => session.call("agent_local_models"));
  return statuses;
}
