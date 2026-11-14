// The profile-session keys a window run leaves in the operating system's
// credential store. Every sign-in stores one key under
// "<profile id>:<session id>@cadrumo:profile-session:v2" and only a sign-out
// deletes it, so a run torn down without signing out leaks one key per run;
// enough of them exhaust the Windows per-user credential store and every
// later sign-in on the machine is refused. Only target names are read
// (`cmdkey /list`); no secret is ever read.

import { readdirSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { join } from "node:path";

const SUFFIX = "@cadrumo:profile-session:v2";
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

/** The profile ids of the buckets under a run's storage root. */
export function storageProfileIds(storage) {
  try {
    return readdirSync(join(storage, "buckets")).filter((name) =>
      UUID.test(name),
    );
  } catch {
    return [];
  }
}

/** The profile-session key targets now stored for `profileIds`; null off Windows. */
export function sessionKeyTargets(profileIds) {
  if (process.platform !== "win32") return null;
  const listed = spawnSync("cmdkey", ["/list"], { encoding: "utf8" });
  if (listed.status !== 0)
    throw new Error(`cmdkey /list failed: ${listed.stderr || listed.status}`);
  const wanted = new Set(profileIds);
  const targets = [];
  for (const line of listed.stdout.split(/\r?\n/)) {
    const match = /Target:\s*(?:LegacyGeneric:target=)?(\S+)/.exec(line);
    if (!match || !match[1].endsWith(SUFFIX)) continue;
    if (wanted.has(match[1].split(":", 1)[0])) targets.push(match[1]);
  }
  return targets;
}

/**
 * Compare the keys stored for the run's profiles with those before it
 * started; delete the ones the run added and answer them. A key that was
 * already stored before the run is never touched.
 */
export function removeLeftSessionKeys(profileIds, before) {
  const now = sessionKeyTargets(profileIds);
  if (now === null || before === null) return { left: [], failed: [] };
  const earlier = new Set(before);
  const left = now.filter((target) => !earlier.has(target));
  const failed = [];
  for (const target of left) {
    const removed = spawnSync("cmdkey", [`/delete:${target}`], {
      encoding: "utf8",
    });
    if (removed.status !== 0) failed.push(target);
  }
  return { left, failed };
}

// Page-side helpers (serialised into the window: arguments and document only).

/** Open the titlebar's account menu; the Radix trigger opens on pointerdown. */
export function pageOpenAccountMenu() {
  const trigger = [...document.querySelectorAll("button.profile-trigger")].find(
    (b) => b.getClientRects().length,
  );
  if (!trigger) return false;
  if (trigger.getAttribute("aria-expanded") !== "true")
    trigger.dispatchEvent(
      new PointerEvent("pointerdown", {
        bubbles: true,
        cancelable: true,
        button: 0,
        pointerType: "mouse",
      }),
    );
  return true;
}

/** Choose the account menu's sign-out item, named `words`. */
export function pageChooseSignOut(words) {
  const item = [...document.querySelectorAll('[role="menuitem"]')].find(
    (e) =>
      e.getClientRects().length &&
      (e.textContent ?? "").replace(/\s+/g, " ").trim().startsWith(words),
  );
  if (!item) return false;
  item.click();
  return true;
}

/** Whether the sign-in form is drawn again. */
export function pageSignedOut() {
  return !!document.querySelector("#profile-password");
}
