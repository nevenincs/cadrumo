// The profile page at rest, in the packaged native window. A page a person has
// opened and left alone draws its sections and then asks the host for nothing:
// an effect that reads the profile again after every answer is a loop that
// keeps the page loading (it never draws a section) and floods the host. One
// window serves the whole file.
//
// PIR-01 opens the profile page from the rail and waits for a section.
// PIR-01b switches between the calendar and the profile page from the rail
// five times and asserts that the switching makes no more than
// MAX_PROFILE_READS profile reads in the whole run and that the profile page
// still draws a section within SECTION_MS of the last switch: showing or
// hiding a page alone is no reason to read the profile again.
// PIR-02 times every host call from the moment the window's calls are timed
// (before the page opens), lets the page settle, then records a window of no
// input. It asserts that no profile read is made in that window, that no more
// than MAX_PROFILE_READS profile reads were made in the whole run, and that
// the profile observers are not subscribed and unsubscribed again and again. A
// failure names the loop: the calls per command, split before and after the
// rail press, and the first calls of each part with their start and end.
//
// Environment: as ./window-ux-audit.test.mjs (CADRUMO_PERSONA_WORLD,
// CADRUMO_PERSONA_HOST, CADRUMO_CMAKE_BINARY_DIR, CADRUMO_BUILD_CONFIG,
// CADRUMO_UX_RUN; CADRUMO_UX_STAGED_SHA256 is compared with the executable
// the run drove when it is set), plus
//   CADRUMO_PROFILE_IDLE_MS  (optional) the idle window to record; default 20000
//
// The profile commands are read from the host adapter's source, not restated
// here. Results are appended, one JSON object per line, to
// <run>/profile-idle-reads.jsonl.
import assert from "node:assert/strict";
import { appendFileSync, mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { after, before, test } from "node:test";
import {
  exec,
  runIdentity,
  sleep,
  start,
  teardown,
  waitFor,
  win,
} from "./ux-driver.mjs";
import { callsSince, pageTimeInvokes } from "./ux-calls.mjs";
import { dismissSetup, openRailPage } from "./ux-nav.mjs";

const STAGED_SHA256 = (process.env.CADRUMO_UX_STAGED_SHA256 ?? "")
  .trim()
  .toLowerCase();
const IDLE_MS = Number(process.env.CADRUMO_PROFILE_IDLE_MS ?? 20_000);
const SETTLE_MS = 3_000;
const SECTION_MS = 15_000;
const FIRST_CALLS = 40;
/** The most `user_profile_read` calls the whole run may make: the page's own
 * read and what the window's readers add while it opens. */
const MAX_PROFILE_READS = 3;

/** The profile page and what it draws once it has read the profile. */
const PROFILE_PAGE = ".user-profile-page";
const SECTION = `${PROFILE_PAGE} [data-section]`;
/** The filing calendar, the window's other reader of the profile. */
const CALENDAR_PAGE = ".calendar-page";
/** How many times the rail switches calendar -> profile in PIR-01b. */
const SWITCHES = 5;
/** Readers that may subscribe to profile changes while the page is open: the
 * window's own profile read, the profile page and its household. */
const MOUNTED_READERS = 3;

// ---------------------------------------------------------------------------
// The profile commands the host adapter issues, read from its source.
// ---------------------------------------------------------------------------

const ADAPTER = readFileSync(
  new URL("../../frontend/src/shell/tauriHost.ts", import.meta.url),
  "utf8",
);
const PROFILE_COMMANDS = [
  ...new Set(
    [...ADAPTER.matchAll(/\b(?:bound|call|submit)\(\s*"([a-z_]+)"/g)]
      .map((match) => match[1])
      .filter((cmd) => /^(user_profile|profile_censo)_/.test(cmd)),
  ),
];
const isObserve = (cmd) => /_observe$/.test(cmd);
const isUnobserve = (cmd) => /_unobserve$/.test(cmd);
const isWrite = (cmd) => /_(change|start|answer)$/.test(cmd);
/** Commands that read the profile: neither a subscription nor a write. */
const PROFILE_READS = PROFILE_COMMANDS.filter(
  (cmd) => !isObserve(cmd) && !isUnobserve(cmd) && !isWrite(cmd),
);
const PROFILE_OBSERVES = PROFILE_COMMANDS.filter(isObserve);
const PROFILE_UNOBSERVES = PROFILE_COMMANDS.filter(isUnobserve);

// ---------------------------------------------------------------------------
// Readers and the breakdown a failure carries
// ---------------------------------------------------------------------------

/** What the profile page draws now (serialised into the window). */
function pageProfileState(root, section) {
  const shown = (el) => el.getClientRects().length > 0;
  const page = [...document.querySelectorAll(root)].find(shown) ?? null;
  return {
    page: !!page,
    sections: document.querySelectorAll(section).length,
    sectionsShown: [...document.querySelectorAll(section)].filter(shown).length,
    busy: !!page?.querySelector('[aria-busy="true"]'),
    text: (page?.textContent ?? "").replace(/\s+/g, " ").trim().slice(0, 160),
  };
}

const countBy = (calls) => {
  const counts = {};
  for (const call of calls) counts[call.cmd] = (counts[call.cmd] ?? 0) + 1;
  return counts;
};
const countText = (counts) =>
  Object.entries(counts)
    .sort((left, right) => right[1] - left[1])
    .map(([cmd, n]) => `${cmd}=${n}`)
    .join(", ") || "none";
const callText = (call) =>
  `  ${call.startMs}-${call.endMs ?? "unanswered"} ms ${call.cmd}${
    call.definition ? ` (${call.definition})` : ""
  }${call.ok === false ? " FAILED" : ""}`;

/** The breakdown every failing assertion of PIR-02 repeats, so the failure
 * names the loop. Times are ms after the window's calls were first timed. */
function breakdown(measure) {
  const {
    calls,
    idle,
    idleFrom,
    idleTo,
    pressAt,
    rendered_ms: rendered,
  } = measure;
  const pre = calls.filter((call) => call.startMs < pressAt);
  const post = calls.filter((call) => call.startMs >= pressAt);
  const first = (list) => list.slice(0, FIRST_CALLS).map(callText);
  return [
    `rail pressed at ${pressAt} ms; section rendered: ${rendered === null ? "never" : `${rendered} ms after the press`}`,
    `idle window ${idleFrom}-${idleTo} ms, ${idle.length} of ${calls.length} calls`,
    `calls per command, whole run: ${countText(countBy(calls))}`,
    `calls per command, before the press (${pre.length}): ${countText(countBy(pre))}`,
    `calls per command, after the press (${post.length}): ${countText(countBy(post))}`,
    `calls per command, idle window: ${countText(countBy(idle))}`,
    `first ${Math.min(FIRST_CALLS, pre.length)} of ${pre.length} calls before the press:`,
    ...first(pre),
    `first ${Math.min(FIRST_CALLS, post.length)} of ${post.length} calls after the press:`,
    ...first(post),
  ].join("\n");
}

// ---------------------------------------------------------------------------
// Run
// ---------------------------------------------------------------------------

let runDir;
let results;
/** What PIR-01 learned and PIR-02 measures from. */
const opening = {
  installedAt: null,
  pressedAt: null,
  renderedMs: null,
  reached: null,
};

function record(line) {
  appendFileSync(results, `${JSON.stringify(line)}\n`);
  console.info(JSON.stringify(line));
}

before(async () => {
  runDir =
    process.env.CADRUMO_UX_RUN ??
    join(mkdtempSync(join(tmpdir(), "cadrumo-e2e-profile-idle-")), "run");
  results = join(runDir, "profile-idle-reads.jsonl");
  await start(runDir);
  await dismissSetup();
  // Timed before the page opens, so the reads of opening it are recorded too;
  // every later call is counted from this instant.
  opening.installedAt = Date.now();
  assert(await exec(pageTimeInvokes), "the window's host calls are not timed");
});
after(async () => {
  if (!win.closed) await teardown();
});

test("PIR-00 the run records the host it drove and the profile commands it watches", () => {
  const line = {
    case: "PIR-00",
    exe_sha256: runIdentity.exeSha256,
    reads: PROFILE_READS,
    observes: PROFILE_OBSERVES,
    unobserves: PROFILE_UNOBSERVES,
  };
  try {
    assert.equal(runIdentity.error, null, runIdentity.error ?? "");
    if (STAGED_SHA256)
      assert.equal(runIdentity.exeSha256?.toLowerCase(), STAGED_SHA256);
    assert.ok(PROFILE_READS.length > 0, "no profile read in the host adapter");
    assert.ok(
      PROFILE_OBSERVES.length > 0,
      "no profile observer in the host adapter",
    );
    line.verdict = "pass";
  } finally {
    line.verdict ??= "fail";
    record(line);
  }
});

test(
  "PIR-01 the profile page opened from the rail draws a section",
  { timeout: 180_000 },
  async () => {
    const line = { case: "PIR-01", section_budget_ms: SECTION_MS };
    try {
      opening.pressedAt = Date.now();
      const got = await openRailPage("profile", PROFILE_PAGE);
      opening.reached = got;
      line.reached = got.reached;
      line.reason = got.reason ?? null;
      assert(got.reached, `the profile page did not open: ${got.reason}`);
      const rootAt = Date.now();
      line.root_ms = rootAt - opening.pressedAt;
      const section = await waitFor(
        async () =>
          (await exec(pageProfileState, PROFILE_PAGE, SECTION)).sectionsShown >
          0,
        {
          timeout: SECTION_MS,
          what: `${SECTION} to be shown`,
          soft: true,
          interval: 250,
        },
      );
      line.page = await exec(pageProfileState, PROFILE_PAGE, SECTION);
      if (section) {
        opening.renderedMs = Date.now() - opening.pressedAt;
        line.rendered_ms = opening.renderedMs;
      }
      assert(
        section,
        `${SECTION} was not shown within ${SECTION_MS} ms of the page root (${JSON.stringify(line.page)})`,
      );
      line.verdict = "pass";
    } finally {
      line.verdict ??= "fail";
      record(line);
    }
  },
);

test(
  "PIR-01b switching between the calendar and the profile page does not read the profile again",
  { timeout: 180_000 },
  async () => {
    const line = {
      case: "PIR-01b",
      switches: SWITCHES,
      section_budget_ms: SECTION_MS,
    };
    try {
      assert(
        opening.reached?.reached,
        "PIR-01 did not open the profile page, so there is nothing to switch from",
      );
      for (let round = 1; round <= SWITCHES; round += 1) {
        const calendar = await openRailPage("calendar", CALENDAR_PAGE);
        assert(
          calendar.reached,
          `round ${round}: the calendar did not open: ${calendar.reason}`,
        );
        const profile = await openRailPage("profile", PROFILE_PAGE);
        assert(
          profile.reached,
          `round ${round}: the profile page did not open: ${profile.reason}`,
        );
      }
      const lastSwitchAt = Date.now();
      const section = await waitFor(
        async () =>
          (await exec(pageProfileState, PROFILE_PAGE, SECTION)).sectionsShown >
          0,
        {
          timeout: SECTION_MS,
          what: `${SECTION} to be shown after the last switch`,
          soft: true,
          interval: 250,
        },
      );
      line.page = await exec(pageProfileState, PROFILE_PAGE, SECTION);
      line.section_after_ms = Date.now() - lastSwitchAt;
      const calls = await callsSince(opening.installedAt);
      const reads = calls.filter((call) => call.cmd === "user_profile_read");
      line.user_profile_reads = reads.length;
      line.counts = countBy(calls);
      assert(
        reads.length <= MAX_PROFILE_READS,
        `${reads.length} user_profile_read calls after ${SWITCHES} switches between the calendar and the profile page, more than the ${MAX_PROFILE_READS} allowed: showing a page reads the profile again: ${reads.map(callText).join(" |")}`,
      );
      assert(
        section,
        `${SECTION} was not shown within ${SECTION_MS} ms of the last switch (${JSON.stringify(line.page)})`,
      );
      line.verdict = "pass";
    } finally {
      line.verdict ??= "fail";
      record(line);
    }
  },
);

test(
  "PIR-02 the idle profile page makes no profile read and does not re-subscribe",
  { timeout: IDLE_MS + 180_000 },
  async () => {
    const line = {
      case: "PIR-02",
      settle_ms: SETTLE_MS,
      idle_ms: IDLE_MS,
      rendered_ms: opening.renderedMs,
    };
    try {
      assert(
        opening.pressedAt !== null,
        "PIR-01 did not open the page, so there is no run to measure",
      );
      // No input and no window command between here and the read below.
      await sleep(SETTLE_MS);
      const idleStart = Date.now();
      await sleep(IDLE_MS);
      const idleEnd = Date.now();
      const calls = await callsSince(opening.installedAt);
      const pressAt = opening.pressedAt - opening.installedAt;
      const idleFrom = idleStart - opening.installedAt;
      const idleTo = idleEnd - opening.installedAt;
      const idle = calls.filter(
        (call) => call.startMs >= idleFrom && call.startMs < idleTo,
      );
      const measure = {
        calls,
        idle,
        idleFrom,
        idleTo,
        pressAt,
        rendered_ms: opening.renderedMs,
      };
      Object.assign(line, {
        calls_total: calls.length,
        press_at_ms: pressAt,
        counts: countBy(calls),
        counts_before_press: countBy(
          calls.filter((call) => call.startMs < pressAt),
        ),
        counts_after_press: countBy(
          calls.filter((call) => call.startMs >= pressAt),
        ),
        idle_counts: countBy(idle),
        first_calls: calls.slice(0, FIRST_CALLS),
      });
      const why = (claim) => `${claim}\n${breakdown(measure)}`;
      assert(
        calls.length > 0,
        why("no host call was recorded: the calls are not timed"),
      );

      const idleReads = idle.filter((call) => PROFILE_READS.includes(call.cmd));
      assert.equal(
        idleReads.length,
        0,
        why(
          `${idleReads.length} profile read(s) in ${IDLE_MS} ms with no input (${countText(countBy(idleReads))}): the page re-reads the profile at rest`,
        ),
      );

      const totalReads = calls.filter(
        (call) => call.cmd === "user_profile_read",
      ).length;
      line.user_profile_reads_total = totalReads;
      assert(
        totalReads <= MAX_PROFILE_READS,
        why(
          `${totalReads} user_profile_read calls in the whole run, more than the ${MAX_PROFILE_READS} allowed: the profile is read again and again`,
        ),
      );

      const idleChurn = idle.filter(
        (call) => isObserve(call.cmd) || isUnobserve(call.cmd),
      );
      assert.equal(
        idleChurn.length,
        0,
        why(
          `${idleChurn.length} subscribe/unsubscribe call(s) in ${IDLE_MS} ms with no input (${countText(countBy(idleChurn))})`,
        ),
      );

      const counts = countBy(calls);
      for (const cmd of PROFILE_OBSERVES)
        assert(
          (counts[cmd] ?? 0) <= MOUNTED_READERS,
          why(
            `${cmd} was called ${counts[cmd]} times for at most ${MOUNTED_READERS} mounted readers`,
          ),
        );
      for (const cmd of PROFILE_UNOBSERVES)
        assert(
          (counts[cmd] ?? 0) <= MOUNTED_READERS,
          why(
            `${cmd} was called ${counts[cmd]} times for at most ${MOUNTED_READERS} mounted readers`,
          ),
        );

      assert(
        opening.renderedMs !== null,
        why("no profile read in the idle window, but the page drew no section"),
      );
      line.verdict = "pass";
    } finally {
      line.verdict ??= "fail";
      record(line);
    }
  },
);

test("PIR-99 the run signs out and leaves no profile-session key", async () => {
  let teardownError = null;
  try {
    await teardown();
  } catch (error) {
    teardownError = error.message;
  }
  record({ case: "PIR-99", teardown_error: teardownError });
  assert.equal(teardownError, null, `teardown: ${teardownError}`);
});
