import { useCallback, useEffect, useMemo, useRef, useState } from "react";

/** The areas of a person's AEAT data the window shows, by the name the host
 * serves them under. */
export type AeatSyncAreaId =
  "census" | "filed" | "notifications" | "vat" | "borrador" | "identity";

/** The order the overview draws the areas in. */
export const AEAT_SYNC_AREAS: readonly AeatSyncAreaId[] = [
  "census",
  "filed",
  "notifications",
  "vat",
  "borrador",
  "identity",
];

/** How current an area is, as the host judged it: it keeps the staleness
 * horizons, the window only words the answer. */
export type AeatSyncState =
  "never_brought" | "current" | "possibly_stale" | "unavailable";

/** How the last try at an area ended. */
export type AeatSyncOutcome =
  "brought" | "nothing_found" | "failed" | "unknown";

/** A number the host serves beside an area. */
export type AeatSyncCountKind =
  | "unread_notifications"
  | "filed_matched"
  | "filed_aeat_only"
  | "filed_local_only"
  | "filed_differing";

export type AeatSyncArea = {
  area: AeatSyncAreaId;
  state: AeatSyncState;
  /** An ISO instant: when the area was last brought; null if never. */
  captured_at: string | null;
  last_attempt: { at: string; outcome: AeatSyncOutcome } | null;
  counts: { kind: AeatSyncCountKind; value: number }[];
  /** `bring` areas are updated from AEAT; `import` ones, from a file. */
  update: "bring" | "import";
};

export type AeatSyncStatus = {
  profile_id: string;
  areas: AeatSyncArea[];
};

/** What the window asks the host to bring. */
export type AeatSyncStart = {
  areas: AeatSyncAreaId[];
  years?: number[];
  forms?: string[];
  dry_run: boolean;
};

export type AeatSyncPort = {
  /** What was brought and when, from the profile's own records; it reaches
   * no network. */
  status(language: string): Promise<AeatSyncStatus>;
  /** Calls `changed` whenever what status serves may have changed. */
  observe(changed: () => void): Promise<() => void>;
  /** Asks the host to bring the areas. A rejection is read by
   * `aeatSyncFailure`; after `unknown` it is not retried. */
  start(request: AeatSyncStart): Promise<void>;
};

export type AeatSyncFailure =
  "unavailable" | "not_signed_in" | "refused" | "unknown";

/** A rejected call's `{ code }` as the failure the window words. */
export function aeatSyncFailure(error: unknown): AeatSyncFailure {
  const code = (error as { code?: unknown } | null)?.code;
  return code === "not_signed_in" || code === "refused" || code === "unknown"
    ? code
    : "unavailable";
}

const dayFormats = new Map<string, Intl.DateTimeFormat>();

/** An instant as a day in `locale`; null where it is not a date. */
export function aeatSyncDay(locale: string, instant: string): string | null {
  const at = new Date(instant);
  if (!Number.isFinite(at.getTime())) return null;
  let format = dayFormats.get(locale);
  if (!format) {
    try {
      format = new Intl.DateTimeFormat(locale, { dateStyle: "medium" });
    } catch {
      format = new Intl.DateTimeFormat(undefined, { dateStyle: "medium" });
    }
    dayFormats.set(locale, format);
  }
  return format.format(at);
}

type State = {
  data: AeatSyncStatus | null;
  loading: boolean;
  error: AeatSyncFailure | null;
};
const EMPTY: State = { data: null, loading: true, error: null };

/** One mounted reader of the overview. Pushes coalesce behind a single
 * read, and what was read is dropped when the profile, language or port
 * changes. */
export function useAeatSync(
  port: AeatSyncPort | undefined,
  reader: string | null,
  language: string,
  shown: boolean,
) {
  const identity = useMemo(
    () => ({ port, reader, language, shown }),
    [port, reader, language, shown],
  );
  const [stored, setStored] = useState({ identity, state: EMPTY });
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
        update({ loading: true });
        try {
          update({ data: await port.status(language), error: null });
        } catch (error) {
          const code = aeatSyncFailure(error);
          update({
            data: code === "not_signed_in" ? null : state.data,
            error: code,
          });
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
      .catch(() => update({ loading: false, error: "unavailable" }));
    return () => {
      alive = false;
      unsubscribe?.();
      control.current = null;
    };
  }, [identity, port, reader, language, shown]);
  const refresh = useCallback(() => control.current?.refresh(), []);
  const state =
    stored.identity === identity && reader !== null && shown
      ? stored.state
      : EMPTY;
  return { ...state, refresh };
}
