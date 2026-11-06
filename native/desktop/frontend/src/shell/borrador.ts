// The Modelo 100 borrador drafts the profile holds and their comparison with
// the saved calculation, as the host serves them in the product's words. A
// draft is an observation of what AEAT printed, imported here; it is never an
// authenticated filing. A comparison keeps both sides' values and each box's
// own classification and reason. Nothing summarises the boxes as agreeing: a
// missing capture, a refused capture and a missing calculation each have a
// status of their own. Nothing here contacts AEAT.

import type { ModeloFormText } from "./modeloContract/modeloWorkForm";

export type BorradorState = "active" | "superseded" | "discarded" | "all";

/** Which stored drafts a read asks for. */
export type BorradorSelector =
  | { kind: "list"; state?: BorradorState | null }
  /** One draft, by a unique prefix of its identity. */
  | { kind: "view"; snapshot_id: string }
  /** The active draft of one filing year. */
  | { kind: "latest"; filing_year: number };

/** A decimal as the product spells it, or a text. */
export type BorradorScalar = string | number | boolean | { decimal: string };

export type BorradorPeriod = { filing_year: number; code: string };

export type BorradorSnapshotSummary = {
  snapshot_id: string;
  filing_year: number;
  period: BorradorPeriod;
  /** An ISO instant. */
  captured_at: string;
  binding_count: number;
  state: "active" | "superseded" | "discarded";
  /** The capture's provenance, served by the full read and not by the
   * query. */
  source_url?: string;
};

export type BorradorSnapshotDetail = BorradorSnapshotSummary & {
  binding_values: { key: string; value: BorradorScalar }[];
};

/** A stored draft the pinned rules refuse: named, never valued. */
export type BorradorRefusedSnapshot = {
  snapshot_id: string;
  filing_year: number;
  period: BorradorPeriod;
  captured_at: string;
  state: "active" | "superseded" | "discarded";
  reason: string;
};

export type BorradorRead = {
  profile_id: string;
  kind: "list" | "view" | "latest";
  rows: BorradorSnapshotSummary[];
  snapshot: BorradorSnapshotDetail | null;
  filing_year: number | null;
  /** Stored drafts the rules refuse, so a refused draft never reads as an
   * absent one. */
  refused_snapshots: BorradorRefusedSnapshot[];
  /** Stored drafts written under an older storage schema, which can be
   * neither read nor named. */
  outdated_stored_snapshots: number;
};

/** A token the product stated and its words in the requested language. */
export type BorradorWords = { token: string; words: string };

export type BorradorCompared = {
  /** The box as the form prints it; null where it has no printed number. */
  box: string | null;
  casilla_id: string;
  label: ModeloFormText;
  /** Null means the draft holds no value for the box, never zero. */
  borrador_value: BorradorScalar | null;
  /** Null means the calculation holds no value for the box, never zero. */
  calculation_value: BorradorScalar | null;
  /** A calculated zero the registry proves does not apply, as distinct from
   * a measured zero. */
  calculation_absent_by_design: boolean;
  /** The calculation minus the draft, present only where both hold amounts. */
  difference: { decimal: string } | null;
  classification: BorradorWords;
  reason: BorradorWords;
};

export type BorradorComparison = {
  profile_id: string;
  filing_year: number;
  language: string;
  status: BorradorWords;
  stale_reasons: BorradorWords[];
  capture: {
    snapshot_id: string;
    captured_at: string;
    registry_revision_id: string;
    evidence: BorradorWords;
  } | null;
  /** Stored drafts that could not be read, so an empty comparison is never
   * mistaken for an empty store. */
  refused_captures: number;
  outdated_stored_captures: number;
  calculation: {
    calculation_revision_id: string;
    state: string;
    created_at: string;
    registry_revision_id: string;
    replayed_snapshot_id: string | null;
    evidence: BorradorWords;
  } | null;
  /** Empty unless the status is `compared` or `stale`. */
  rows: BorradorCompared[];
  counts: {
    agree: number;
    differ: number;
    only_in_borrador: number;
    only_in_calculation: number;
    not_comparable: number;
  };
};

/** Reads of the profile's borrador drafts. A rejection carries `{ code }`:
 * one of `invalid`, `not_signed_in`, `refused` or `unavailable`. */
export type BorradorPort = {
  /** The full human read, with each capture's provenance. */
  read(profile: string, selector: BorradorSelector): Promise<BorradorRead>;
  /** The same drafts without provenance. */
  query(profile: string, selector: BorradorSelector): Promise<BorradorRead>;
  compare(
    profile: string,
    year: number,
    language: string,
  ): Promise<BorradorComparison>;
};
