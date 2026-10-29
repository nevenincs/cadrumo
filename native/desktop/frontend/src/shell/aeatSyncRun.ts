import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { AeatSyncAreaId } from "./aeatSync";
import { aeatSyncFailure } from "./aeatSync";
import type { AeatSyncReason } from "./aeatSyncResults";

// The run of an update from AEAT as the window follows it: which kinds of
// data are being read, what each part came to, and the few things the person
// can do while it goes on. The host keeps the queue and classifies every
// outcome; the window words what it is served. Every read here is a read of
// AEAT: nothing is filed or sent.

/** Where one part of the run stands. `not_started` is a part the run ended
 * before reaching, whether the person stopped it or the AEAT session ended. */
export type AeatSyncItemState =
  | "waiting"
  | "running"
  | "brought"
  | "nothing_found"
  | "failed"
  | "unknown"
  | "not_started";

/** One part of an area: the whole area, or one year of filed declarations. */
export type AeatSyncRunItem = {
  /** The host's address of this part, for a retry; never shown. */
  item: number;
  /** The year of a filed-declarations part; null where the area is one part. */
  year: number | null;
  state: AeatSyncItemState;
  /** Why a part failed; null for any other state. */
  reason: AeatSyncReason | null;
};

/** Areas finish independently, so each carries its own standing. */
export type AeatSyncRunAreaState =
  "waiting" | "running" | "finished" | "not_started";

export type AeatSyncRunArea = {
  area: AeatSyncAreaId;
  state: AeatSyncRunAreaState;
  /** The worst outcome of the parts settled so far, as the host judged it;
   * null before any part settled. */
  outcome: AeatSyncAreaOutcome | null;
  /** Empty while the host is still working out the parts, as for the years
   * of filed declarations before they are known. */
  items: AeatSyncRunItem[];
};

/** `stopping` is a stop the person asked for that waits for the step in
 * progress; `paused` is a run whose AEAT session ended. */
export type AeatSyncRunState =
  "running" | "stopping" | "stopped" | "paused" | "done";

export type AeatSyncRunSnapshot = {
  state: AeatSyncRunState;
  /** In the order the host runs them. */
  areas: AeatSyncRunArea[];
};

export type AeatSyncRunPort = {
  /** The run now going on or last ended in this window; null before any. */
  progress(profile: string): Promise<AeatSyncRunSnapshot | null>;
  /** Calls `changed` whenever `progress` may answer differently. */
  observe(changed: () => void): Promise<() => void>;
  /** Lets the step in progress finish and starts nothing further. */
  stop(profile: string): Promise<void>;
  /** Reads one part of an area again, on the person's request. A part whose
   * outcome is unknown is read again only when `acknowledgedUnknown` says the
   * person was told it may already have been brought. */
  retry(
    profile: string,
    area: AeatSyncAreaId,
    item: number | null,
    acknowledgedUnknown: boolean,
  ): Promise<void>;
  /** Carries on from the part where the run paused, once the person signed
   * in again. */
  resume(profile: string): Promise<void>;
};

/** How an area came out once its parts settled, as the host serves it. */
export type AeatSyncAreaOutcome =
  "brought" | "nothing_found" | "failed" | "unknown";

/** How many parts are done, and how many there are, for a progress bar. */
export function aeatSyncRunShare(snapshot: AeatSyncRunSnapshot): {
  settled: number;
  total: number;
} {
  const items = snapshot.areas.flatMap((a) => a.items);
  const open = (s: AeatSyncItemState) => s === "waiting" || s === "running";
  return {
    settled: items.filter((i) => !open(i.state)).length,
    total: items.length,
  };
}

/** The parts that failed or whose outcome is unknown, which need a look. */
export function aeatSyncRunProblems(snapshot: AeatSyncRunSnapshot): number {
  return snapshot.areas
    .flatMap((a) => a.items)
    .filter((i) => i.state === "failed" || i.state === "unknown").length;
}

export type AeatSyncRunProblem = "failed" | "unknown";

type State = {
  snapshot: AeatSyncRunSnapshot | null;
  loading: boolean;
  error: boolean;
};
const EMPTY: State = { snapshot: null, loading: true, error: false };

/** One mounted follower of the run. Pushes coalesce behind a single read, and
 * what was read is dropped when the profile or port changes. */
export function useAeatSyncRun(
  port: AeatSyncRunPort | undefined,
  reader: string | null,
  shown: boolean,
) {
  const identity = useMemo(
    () => ({ port, reader, shown }),
    [port, reader, shown],
  );
  const [stored, setStored] = useState({ identity, state: EMPTY });
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<AeatSyncRunProblem | null>(null);
  const control = useRef<{ refresh(): void } | null>(null);
  useEffect(() => {
    control.current = null;
    if (!port || reader === null || !shown) return;
    let alive = true,
      reading = false,
      again = false;
    let unsubscribe: (() => void) | undefined;
    let state = EMPTY;
    const update = (patch: Partial<State>) => {
      if (!alive) return;
      state = { ...state, ...patch };
      setStored({ identity, state });
    };
    const refresh = async () => {
      if (!alive) return;
      if (reading) {
        again = true;
        return;
      }
      reading = true;
      do {
        again = false;
        try {
          update({ snapshot: await port.progress(reader), error: false });
        } catch {
          update({ error: true });
        }
      } while (alive && again);
      reading = false;
      update({ loading: false });
    };
    control.current = { refresh: () => void refresh() };
    void port
      .observe(() => void refresh())
      .then((stop) => {
        if (!alive) {
          stop();
          return;
        }
        unsubscribe = stop;
        void refresh();
      })
      .catch(() => update({ loading: false, error: true }));
    return () => {
      alive = false;
      unsubscribe?.();
      control.current = null;
    };
  }, [identity, port, reader, shown]);
  const refresh = useCallback(() => control.current?.refresh(), []);
  const act = useCallback(
    async (call: (port: AeatSyncRunPort, profile: string) => Promise<void>) => {
      if (!port || reader === null) return;
      setBusy(true);
      setProblem(null);
      try {
        await call(port, reader);
      } catch (error) {
        setProblem(aeatSyncFailure(error) === "unknown" ? "unknown" : "failed");
      } finally {
        setBusy(false);
        refresh();
      }
    },
    [port, reader, refresh],
  );
  const state =
    stored.identity === identity && reader !== null && shown
      ? stored.state
      : EMPTY;
  return {
    ...state,
    busy,
    problem,
    stop: useCallback(() => act((p, id) => p.stop(id)), [act]),
    retry: useCallback(
      (
        area: AeatSyncAreaId,
        item: number | null,
        acknowledgedUnknown: boolean,
      ) => act((p, id) => p.retry(id, area, item, acknowledgedUnknown)),
      [act],
    ),
    resume: useCallback(() => act((p, id) => p.resume(id)), [act]),
  };
}
