import type {
  AeatSyncItemState,
  AeatSyncRunArea,
  AeatSyncRunPort,
  AeatSyncRunSnapshot,
  AeatSyncRunState,
} from "../shell/aeatSyncRun";
import type { AeatSyncAreaId } from "../shell/aeatSync";
import type { AeatSyncReason } from "../shell/aeatSyncResults";

/** What the scenario's update from AEAT is in the middle of. */
export type AeatSyncRunMode =
  /** No update has started. */
  | "idle"
  /** Going on: two areas done, one running, two waiting. */
  | "running"
  /** Done, with a failed year and a failed area beside parts that worked. */
  | "partial_failure"
  /** Done, with a part whose outcome could not be confirmed. */
  | "unknown"
  /** Done, and AEAT had nothing new. */
  | "nothing_found"
  /** A stop is waiting for the step in progress. */
  | "stopping"
  /** Stopped before every area was reached. */
  | "stopped"
  /** The AEAT session ended partway. */
  | "paused"
  /** Done, and everything was brought. */
  | "done";

let next = 1;
function part(
  state: AeatSyncItemState,
  year: number | null = null,
  reason: AeatSyncReason | null = null,
) {
  return { item: next++, year, state, reason };
}

function area(
  id: AeatSyncAreaId,
  state: AeatSyncRunArea["state"],
  items: ReturnType<typeof part>[],
): AeatSyncRunArea {
  return { area: id, state, items };
}

function years(...states: AeatSyncItemState[]) {
  return states.map((state, i) => part(state, 2024 - i));
}

function snapshot(mode: AeatSyncRunMode): AeatSyncRunSnapshot | null {
  next = 1;
  const settled = (state: AeatSyncRunState, areas: AeatSyncRunArea[]) => ({
    state,
    areas,
  });
  switch (mode) {
    case "idle":
      return null;
    case "running":
      return settled("running", [
        area("census", "finished", [part("brought")]),
        area("identity", "finished", [part("nothing_found")]),
        area("notifications", "running", [part("running")]),
        area("vat", "waiting", [part("waiting")]),
        area("filed", "waiting", []),
      ]);
    case "partial_failure":
      return settled("done", [
        area("census", "finished", [part("brought")]),
        area("identity", "finished", [part("failed", null, "unavailable")]),
        area("notifications", "finished", [part("brought")]),
        area("vat", "finished", [part("nothing_found")]),
        area("filed", "finished", [
          part("brought", 2024),
          part("failed", 2023, "refused"),
          part("brought", 2022),
        ]),
      ]);
    case "unknown":
      return settled("done", [
        area("census", "finished", [part("brought")]),
        area("identity", "finished", [part("brought")]),
        area("notifications", "finished", [part("unknown")]),
        area("vat", "finished", [part("brought")]),
        area("filed", "finished", [
          part("brought", 2024),
          part("unknown", 2023),
        ]),
      ]);
    case "nothing_found":
      return settled("done", [
        area("census", "finished", [part("nothing_found")]),
        area("identity", "finished", [part("nothing_found")]),
        area("notifications", "finished", [part("nothing_found")]),
        area("vat", "finished", [part("nothing_found")]),
        area("filed", "finished", [
          part("nothing_found", 2024),
          part("nothing_found", 2023),
        ]),
      ]);
    case "stopping":
      return settled("stopping", [
        area("census", "finished", [part("brought")]),
        area("identity", "finished", [part("brought")]),
        area("notifications", "running", [part("running")]),
        area("vat", "waiting", [part("waiting")]),
        area("filed", "waiting", []),
      ]);
    case "stopped":
      return settled("stopped", [
        area("census", "finished", [part("brought")]),
        area("identity", "finished", [part("brought")]),
        area("notifications", "finished", [part("brought")]),
        area("vat", "not_started", [part("not_started")]),
        area("filed", "not_started", []),
      ]);
    case "paused":
      return settled("paused", [
        area("census", "finished", [part("brought")]),
        area("identity", "finished", [part("brought")]),
        area("notifications", "finished", [part("brought")]),
        area("vat", "finished", [part("nothing_found")]),
        area("filed", "running", [
          ...years("brought", "not_started", "not_started"),
        ]),
      ]);
    case "done":
      return settled("done", [
        area("census", "finished", [part("brought")]),
        area("identity", "finished", [part("brought")]),
        area("notifications", "finished", [part("brought")]),
        area("vat", "finished", [part("brought")]),
        area("filed", "finished", years("brought", "brought", "brought")),
      ]);
  }
}

/** The update's host port over demo data. Stop, a retry and a resume move the
 * demo along a step so each state can be followed; nothing is read. `begin`
 * is a start asked of the host: the run goes on for a moment and then
 * reaches `outcome`, where it stays. */
export function aeatSyncRunFixture(
  mode: AeatSyncRunMode,
  say: (line: string) => void,
): AeatSyncRunPort & { begin(outcome: AeatSyncRunMode): void } {
  let current = snapshot(mode);
  const listeners = new Set<() => void>();
  const push = () => listeners.forEach((listener) => listener());
  const set = (patch: (s: AeatSyncRunSnapshot) => AeatSyncRunSnapshot) => {
    if (current) current = patch(current);
    push();
  };
  const settle = (item: number, state: AeatSyncItemState) =>
    set((s) => ({
      ...s,
      areas: s.areas.map((a) => ({
        ...a,
        state: a.items.some((i) => i.item === item) ? "finished" : a.state,
        items: a.items.map((i) =>
          i.item === item ? { ...i, state, reason: null } : i,
        ),
      })),
    }));
  return {
    begin(outcome) {
      current = snapshot("running");
      push();
      if (outcome !== "running")
        setTimeout(() => {
          current = snapshot(outcome);
          push();
        }, 700);
    },
    progress: () => Promise.resolve(current),
    observe(changed) {
      listeners.add(changed);
      return Promise.resolve(() => listeners.delete(changed));
    },
    stop() {
      say("aeatSyncRun.stop");
      set((s) => ({ ...s, state: "stopping" }));
      setTimeout(
        () =>
          set((s) => ({
            state: "stopped",
            areas: s.areas.map((a) =>
              a.state === "waiting"
                ? {
                    ...a,
                    state: "not_started",
                    items: a.items.map((i) => ({
                      ...i,
                      state: "not_started" as const,
                    })),
                  }
                : a.state === "running"
                  ? {
                      ...a,
                      state: "finished",
                      items: a.items.map((i) =>
                        i.state === "running"
                          ? { ...i, state: "brought" as const }
                          : i,
                      ),
                    }
                  : a,
            ),
          })),
        900,
      );
      return Promise.resolve();
    },
    retry(_profile, area, item, acknowledgedUnknown) {
      say(
        `aeatSyncRun.retry ${area} ${item ?? "all"} acknowledged=${acknowledgedUnknown}`,
      );
      if (item === null) return Promise.resolve();
      settle(item, "running");
      setTimeout(() => settle(item, "brought"), 900);
      return Promise.resolve();
    },
    resume() {
      say("aeatSyncRun.resume");
      set((s) => ({ ...s, state: "running" }));
      setTimeout(
        () =>
          set((s) => ({
            state: "done",
            areas: s.areas.map((a) => ({
              ...a,
              state: "finished",
              items: a.items.map((i) =>
                i.state === "not_started" || i.state === "running"
                  ? { ...i, state: "brought" as const }
                  : i,
              ),
            })),
          })),
        1200,
      );
      return Promise.resolve();
    },
  };
}
