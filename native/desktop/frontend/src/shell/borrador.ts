// The Modelo 100 borrador drafts the profile holds and their comparison with
// the saved calculation, as the host serves them in the product's words. A
// draft is an observation of what AEAT printed, imported here; it is never an
// authenticated filing. A comparison keeps both sides' values and each box's
// own classification and reason. Nothing summarises the boxes as agreeing: a
// missing capture, a refused capture and a missing calculation each have a
// status of their own. Nothing here contacts AEAT.

import type {
  Borrador100ComparisonProjection,
  Borrador100QueryProjection,
  Borrador100ReadProjection,
} from "./borradorContract";

/** The host's own read command arguments: it builds the product's request from
 * them. */
export type BorradorState = "active" | "superseded" | "discarded" | "all";

/** Which stored drafts a read asks for. */
export type BorradorSelector =
  | { kind: "list"; state?: BorradorState | null }
  /** One draft, by a unique prefix of its identity. */
  | { kind: "view"; snapshot_id: string }
  /** The active draft of one filing year. */
  | { kind: "latest"; filing_year: number };

/** Reads of the profile's borrador drafts. A rejection carries `{ code }`:
 * one of `invalid`, `not_signed_in`, `refused` or `unavailable`. */
export type BorradorPort = {
  /** The full human read, with each capture's provenance. */
  read(
    profile: string,
    selector: BorradorSelector,
  ): Promise<Borrador100ReadProjection>;
  /** The same drafts without provenance. */
  query(
    profile: string,
    selector: BorradorSelector,
  ): Promise<Borrador100QueryProjection>;
  compare(
    profile: string,
    year: number,
    language: string,
  ): Promise<Borrador100ComparisonProjection>;
};
