// The Declarations page's port to the modelo family's registered operations,
// as the desktop host serves them over the signed-in person's session. The
// page names one admitted definition and its registered request without the
// profile; the host fills the profile where the request declares one and
// takes the subject from the contract. Three reads answer the runtime's
// projections unchanged: the declarations list, a declaration's form and a
// box's help card. An edit's typed entries and amounts travel only as the raw
// bytes of one preflight or apply call. Files travel as tokens the host issued
// for the person's own picks, never as paths. Results and staged edits live
// in the page's memory only: never in storage, a log line or an error.
//
// The page renders what these read models state. It never classifies a box
// or a declaration, never words a step, a value or a citation, and never
// draws a missing value as zero; a need for any of these is a field the
// application owes.

import type {
  FilePicks,
  FileToken,
  JsonObject,
  LedgerDecision,
  LedgerOutcome,
  LedgerReview,
} from "./ledger";
import {
  MODELO_DEFINITIONS,
  type ModeloCasillaHelpProjectionV1,
  type ModeloContracts,
  type ModeloDeclarationsListProjectionV1,
  type ModeloEditOperatorInputV2,
  type ModeloWorkbenchFormProjectionV1,
  type OutputLanguage,
} from "./modeloContract";

export type ModeloDefinitionId = (typeof MODELO_DEFINITIONS)[number];
export function isModeloDefinition(id: string): id is ModeloDefinitionId {
  return (MODELO_DEFINITIONS as readonly string[]).includes(id);
}

/** The operator the desktop names on modelo requests that take an actor;
 * the TUI names "operator:tui-modelo". */
export const MODELO_ACTOR = "operator:desktop-modelo";

/** The definitions whose request is the edit's financial body: they are
 * sent through `edit`, never through `submit`. */
export const MODELO_EDIT_DEFINITIONS = [
  "modelo.edit.preflight",
  "modelo.edit.apply",
] as const;
export type ModeloEditDefinitionId = (typeof MODELO_EDIT_DEFINITIONS)[number];

/** The definitions whose subject is the work unit owning the stored record
 * their request names; only the store knows it, so the page names it from
 * the form it read. Every other definition takes no work unit. */
export const MODELO_STORED_SUBJECT_DEFINITIONS = [
  "modelo.export",
  "modelo.review_package.build",
  "modelo.work.amend",
  "modelo.work.file",
  "modelo.work.revision_snapshot",
  "modelo.work.verify",
] as const;
export type ModeloStoredSubjectDefinitionId =
  (typeof MODELO_STORED_SUBJECT_DEFINITIONS)[number];
export function needsWorkUnit(
  id: ModeloDefinitionId,
): id is ModeloStoredSubjectDefinitionId {
  return (MODELO_STORED_SUBJECT_DEFINITIONS as readonly string[]).includes(id);
}

/** The longest edit body, in bytes, the host sends on. A longer one is
 * refused with `invalid` before anything is sent; the page splits the edit. */
export const MODELO_EDIT_BODY_LIMIT = 16_383;

type Contract<D extends ModeloDefinitionId> = D extends keyof ModeloContracts
  ? ModeloContracts[D]
  : never;

/** A definition's registered request as the page sends it: the host fills
 * the profile, and naming it is refused. */
export type ModeloRequest<D extends ModeloDefinitionId> =
  Contract<D> extends { request: infer Request }
    ? Omit<Request, "profile_id" | "bucket_id">
    : JsonObject;
/** A definition's registered result, under its contract's schema. */
export type ModeloResult<D extends ModeloDefinitionId> =
  Contract<D> extends { result: infer Result } ? Result : JsonObject;
/** The review a definition pauses for, where its contract declares one. */
export type ModeloReviewDocument<D extends ModeloDefinitionId> =
  Contract<D> extends { review: infer Review } ? Review : JsonObject;

/** What a file the person picks is for, and the kinds the dialog offers. */
export type ModeloFilePurpose =
  "evidence" | "report" | "package" | "signature" | "envelope";
/** The kind of file a save writes; a token of another kind than the field
 * takes is refused with `invalid`. */
export type ModeloSaveFormat =
  "boe" | "xml" | "csv" | "pdf" | "xlsx" | "zip" | "sig" | "sealed";

/** The operator input of one preflight or apply, as UTF-8 bytes: the edit
 * session's admitted baseline and its staged intents, and for a preflight
 * the entries as the filer typed them. */
export function modeloEditBody(input: ModeloEditOperatorInputV2): Uint8Array {
  return new TextEncoder().encode(JSON.stringify(input));
}

export type ModeloPort = {
  /** Every row of the signed-in profile's declarations list, said in
   * `language`, in the order the application lists them. */
  declarations(
    language: OutputLanguage,
  ): Promise<ModeloDeclarationsListProjectionV1>;
  /** One declaration's form, with the edit baseline admitted with it or why
   * it cannot be edited. */
  form(
    workUnitId: string,
    language: OutputLanguage,
  ): Promise<ModeloWorkbenchFormProjectionV1>;
  /** One box's help card, for the revision and calculation the form
   * showed. */
  casillaHelp(request: {
    workUnitId: string;
    casillaId: string;
    registryRevisionId: string;
    calculationRevisionId: string | null;
    language: OutputLanguage;
  }): Promise<ModeloCasillaHelpProjectionV1>;
  /** Submits one admitted operation and follows it until it settles or
   * waits on the person. One attempt: nothing is retried, and a write whose
   * settlement was not observed rejects with `unknown`. A definition
   * whose subject is a stored record names the form's work unit. */
  submit<D extends Exclude<ModeloDefinitionId, ModeloEditDefinitionId>>(
    definition: D,
    payload: ModeloRequest<D>,
    ...workUnit: D extends ModeloStoredSubjectDefinitionId
      ? [workUnit: string]
      : []
  ): Promise<LedgerOutcome<ModeloResult<D>>>;
  /** Sends the bytes of `modeloEditBody` for a preflight or an apply, which
   * this one call consumes and zeroes. An apply that waits on the runtime
   * answers `running`; the page follows it with `observe`. */
  edit<D extends ModeloEditDefinitionId>(
    definition: D,
    body: Uint8Array,
  ): Promise<LedgerOutcome<ModeloResult<D>>>;
  /** Where an operation this page submitted stands now. */
  observe(operation: string): Promise<LedgerOutcome>;
  /** The review a paused operation shows, with its digest. */
  review<Review = JsonObject>(operation: string): Promise<LedgerReview<Review>>;
  /** Answers the review whose digest the page showed. */
  answer(
    operation: string,
    reviewDigest: string,
    decision: LedgerDecision,
  ): Promise<LedgerOutcome>;
  /** Asks to cancel at the revision the page observed. */
  cancel(operation: string, revision: number): Promise<LedgerOutcome>;
  /** Opens the native dialog for one file of `purpose`; `filterLabel` names
   * the kinds it offers in the page's language. */
  pickFile(purpose: ModeloFilePurpose, filterLabel: string): Promise<FilePicks>;
  /** Opens the native save dialog for a file in `format`. */
  saveFile(
    format: ModeloSaveFormat,
    filterLabel: string,
    suggestedName?: string,
  ): Promise<FilePicks>;
  /** Forgets tokens the page no longer shows. */
  forgetFiles(tokens: FileToken[]): Promise<void>;
  /** Shows a file the host saved for `saveFile`'s token in the system file
   * manager, after the operation wrote it. A picked file's token is refused
   * with `invalid`; a forgotten, earlier or missing file with
   * `file_unavailable`. */
  revealFile(token: FileToken): Promise<void>;
};
