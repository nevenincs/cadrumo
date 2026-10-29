import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { AeatSyncAreaId, AeatSyncOutcome } from "./aeatSync";

// What the AEAT data window shows after data was read from AEAT: a summary
// for each kind of data, the filed declarations set against the profile's own
// records, the notification list and the Borrador import. Everything here is
// read from AEAT or from the profile; nothing is filed or sent. The host
// serves closed states and counts, never an operation or record identifier.

/** Why a read did not complete, in the closed set the host classifies. */
export type AeatSyncReason =
  "session_ended" | "no_access" | "unavailable" | "refused" | "other";

/** One part of a read that failed: which declarations, if the read was
 * narrowed to a year or a form. */
export type AeatSyncFailedPart = {
  /** The retry's address for this part. */
  part: number;
  year: number | null;
  /** A modelo number such as "303"; null where not narrowed to a form. */
  form: string | null;
  reason: AeatSyncReason;
};

/** What the last read of one kind of data came to. */
export type AeatSyncResult = {
  area: AeatSyncAreaId;
  outcome: AeatSyncOutcome;
  /** An ISO instant; null if nothing was read. */
  at: string | null;
  /** Entries that were not in the profile before. */
  new_count: number;
  /** Entries that differ from what the profile held. */
  changed_count: number;
  failed: AeatSyncFailedPart[];
  /** Census only: a comparison with the profile waits for the person. */
  review_pending: boolean;
};

/** How a filed declaration at AEAT stands against the profile's own record. */
export type FiledMatch = "matched" | "aeat_only" | "local_only" | "differing";

/** What differs, where the two disagree. */
export type FiledDifference = "amount" | "status" | "date";

export type FiledRow = {
  /** A modelo number such as "303". */
  form: string;
  year: number;
  /** A period such as "1T"; null for an annual form. */
  period: string | null;
  match: FiledMatch;
  /** The profile's own record: a draft, or marked as filed on this computer. */
  record: { status: "draft" | "marked_filed"; on: string } | null;
  /** What AEAT showed when it was last read; null if it showed nothing. */
  aeat: { seen_on: string } | null;
  /** Whether AEAT's receipt for it was checked and confirmed. */
  receipt: "confirmed" | "not_confirmed";
  differences: FiledDifference[];
};

export type NotificationRow = {
  subject: string;
  /** An ISO date the notification reached the person's mailbox at AEAT. */
  received_on: string;
  read: boolean;
  /** An ISO date; null while unread. */
  read_on: string | null;
};

export type AeatSyncResults = {
  areas: AeatSyncResult[];
  filed: FiledRow[];
  notifications: NotificationRow[];
};

/** A Borrador file chosen in the native dialog: a token the host resolves and
 * the file's name; the path never reaches the window. */
export type BorradorFile = { token: string; name: string };

/** What importing a Borrador file came to. */
export type BorradorImportResult = "imported" | "nothing_found" | "failed";

export type AeatSyncResultsPort = {
  /** Reads the profile's own records of what was read from AEAT; it reaches
   * no network. */
  results(profile: string, language: string): Promise<AeatSyncResults>;
  /** Reads one kind of data again, or one failed part of it. A rejection is
   * read by `aeatSyncFailure`; after `unknown` it is not retried. */
  retry(profile: string, area: AeatSyncAreaId, part?: number): Promise<void>;
  /** Null when the person closes the dialog without choosing. */
  pickBorrador(): Promise<BorradorFile | null>;
  /** Reads the chosen Borrador PDF into the profile, for the filing `year`
   * the person chose. */
  importBorrador(
    profile: string,
    file: string,
    year?: number,
  ): Promise<BorradorImportResult>;
};

type State = {
  data: AeatSyncResults | null;
  loading: boolean;
  failed: boolean;
};
const EMPTY: State = { data: null, loading: true, failed: false };

/** The results for one profile and language. A new profile, language or port
 * drops what was read. */
export function useAeatSyncResults(
  port: AeatSyncResultsPort | undefined,
  profile: string | null,
  language: string,
) {
  const identity = useMemo(
    () => ({ port, profile, language }),
    [port, profile, language],
  );
  const [stored, setStored] = useState({ identity, state: EMPTY });
  const control = useRef<(() => void) | null>(null);
  useEffect(() => {
    control.current = null;
    if (!port || profile === null) return;
    let alive = true;
    let latest = 0;
    let state = EMPTY;
    const update = (patch: Partial<State>) => {
      if (!alive) return;
      state = { ...state, ...patch };
      setStored({ identity, state });
    };
    const read = async () => {
      const mine = ++latest;
      update({ loading: true });
      try {
        const data = await port.results(profile, language);
        if (mine === latest) update({ data, failed: false, loading: false });
      } catch {
        if (mine === latest) update({ failed: true, loading: false });
      }
    };
    control.current = () => void read();
    void read();
    return () => {
      alive = false;
      control.current = null;
    };
  }, [identity, port, profile, language]);
  const refresh = useCallback(() => control.current?.(), []);
  const state =
    stored.identity === identity && profile !== null ? stored.state : EMPTY;
  return { ...state, refresh };
}
