import type {
  AeatSyncArea,
  AeatSyncPort,
  AeatSyncStart,
  AeatSyncStatus,
} from "../shell/aeatSync";

/** What the scenario's AEAT data page is served. */
export type AeatSyncMode =
  /** Nothing was ever brought. */
  | "never"
  /** Every state the page words, with counts. */
  | "mixed"
  /** Each area was last brought one day inside its horizon. */
  | "inside_horizon"
  /** Each area was last brought one day past its horizon. */
  | "past_horizon"
  /** The status read fails. */
  | "unavailable";

const DAY = 24 * 60 * 60 * 1000;

function mixed(now: number): AeatSyncArea[] {
  const ago = (days: number) => new Date(now - days * DAY).toISOString();
  return [
    {
      area: "census",
      state: "current",
      captured_at: ago(12),
      last_attempt: { at: ago(12), outcome: "brought" },
      counts: [],
      update: "bring",
    },
    {
      area: "filed",
      state: "possibly_stale",
      captured_at: ago(130),
      last_attempt: { at: ago(3), outcome: "failed" },
      counts: [
        { kind: "filed_matched", value: 9 },
        { kind: "filed_aeat_only", value: 2 },
        { kind: "filed_local_only", value: 1 },
        { kind: "filed_differing", value: 1 },
      ],
      update: "bring",
    },
    {
      area: "notifications",
      state: "possibly_stale",
      captured_at: ago(20),
      last_attempt: { at: ago(1), outcome: "unknown" },
      counts: [{ kind: "unread_notifications", value: 3 }],
      update: "bring",
    },
    {
      area: "vat",
      state: "never_brought",
      captured_at: null,
      last_attempt: null,
      counts: [],
      update: "bring",
    },
    {
      area: "borrador",
      state: "unavailable",
      captured_at: null,
      last_attempt: null,
      counts: [],
      update: "import",
    },
    {
      area: "identity",
      state: "current",
      captured_at: ago(40),
      last_attempt: { at: ago(2), outcome: "nothing_found" },
      counts: [],
      update: "bring",
    },
  ];
}

/** The days after which the backend serves each area as possibly out of
 * date. The page is told the state, never the number. */
const HORIZON_DAYS = {
  notifications: 7,
  vat: 30,
  census: 90,
  filed: 90,
  identity: 90,
} as const;

/** What the backend serves for areas last brought a day either side of
 * their horizon. */
function horizon(now: number, beyond: boolean): AeatSyncArea[] {
  const areas = (
    ["census", "filed", "notifications", "vat", "identity"] as const
  ).map((area): AeatSyncArea => {
    const at = new Date(
      now - (HORIZON_DAYS[area] + (beyond ? 1 : -1)) * DAY,
    ).toISOString();
    return {
      area,
      state: beyond ? "possibly_stale" : "current",
      captured_at: at,
      last_attempt: { at, outcome: "brought" },
      counts: [],
      update: "bring",
    };
  });
  return [
    ...areas,
    {
      area: "borrador",
      state: "never_brought",
      captured_at: null,
      last_attempt: null,
      counts: [],
      update: "import",
    },
  ];
}

function never(): AeatSyncArea[] {
  return (
    ["census", "filed", "notifications", "vat", "borrador", "identity"] as const
  ).map((area) => ({
    area,
    state: "never_brought",
    captured_at: null,
    last_attempt: null,
    counts: [],
    update: area === "borrador" ? "import" : "bring",
  }));
}

/** The AEAT data page's host port over demo data. A start is recorded and
 * tells `started`, which stands for the run the host would begin. */
export function aeatSyncFixture(
  mode: AeatSyncMode,
  say: (line: string) => void,
  started: () => void = () => undefined,
): AeatSyncPort {
  const listeners = new Set<() => void>();
  return {
    status() {
      if (mode === "unavailable")
        return Promise.reject({ code: "unavailable" });
      const status: AeatSyncStatus = {
        profile_id: "demo",
        areas:
          mode === "never"
            ? never()
            : mode === "inside_horizon" || mode === "past_horizon"
              ? horizon(Date.now(), mode === "past_horizon")
              : mixed(Date.now()),
      };
      return Promise.resolve(status);
    },
    observe(changed) {
      listeners.add(changed);
      return Promise.resolve(() => listeners.delete(changed));
    },
    start(_profile: string, request: AeatSyncStart) {
      say(`aeatSync.start ${request.areas.join(",")}`);
      started();
      listeners.forEach((listener) => listener());
      return Promise.resolve();
    },
  };
}
