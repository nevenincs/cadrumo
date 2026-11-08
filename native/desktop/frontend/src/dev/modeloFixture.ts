import { requireServed } from "./servedFixtures";
// The scenario host's modelo family: the modelo port answered from the
// envelopes in @fixtures/modelo/, which scripts/modelo-fixtures.mjs reads
// through the application's own read path for a synthetic taxpayer. The
// declarations list, each declaration's form, the help cards and one edit
// preflight answer exactly what the application answered, in each of the
// four languages, and the first quarter's Modelo 130 is also read after its
// check, recorded as filed locally with and without a verified receipt, and
// with its file for the AEAT out of date; an edit renewal answers the
// renewal the application read for that baseline. Every other definition has no
// envelope here and is answered as unavailable, never with a made-up
// result. What it answers is design and test evidence only. Its call lines
// name a definition, never a value.

import type {
  FilePicks,
  FileToken,
  JsonObject,
  LedgerErrorDetail,
  LedgerFailure,
  LedgerFailureCode,
  LedgerOutcome,
} from "../shell/ledger";
import {
  isModeloDefinition,
  needsWorkUnit,
  type ModeloFilePurpose,
  type ModeloPort,
  type ModeloResult,
  type ModeloSaveFormat,
} from "../shell/modelo";
import { RELAY_PAYLOAD_LIMIT } from "../shell/relayBounds";
import { type OutputLanguage } from "../shell/modeloContract/modelo";
import { type ModeloDeclarationsListProjectionV1 } from "../shell/modeloContract/modeloDeclarations";
import type { ModeloFilingRecordViewProjection } from "../shell/modeloContract/modeloFilingRecord";
import {
  type ModeloEditOperatorInputV2,
  type ModeloEditHeldChangeV1,
  type ModeloEditPreflightProjectionV1,
  type ModeloEditRenewalProjectionV1,
} from "../shell/modeloContract/modeloEdit";
import { type ModeloExportPublicResultV3 } from "../shell/modeloContract/modeloExport";
import {
  type CreditResolutionListProjection,
  type ModeloWorkCreateProjection,
} from "../shell/modeloContract/modeloWork";
import { type ModeloCasillaHelpProjectionV1 } from "../shell/modeloContract/modeloWorkCasillaHelp";
import {
  type ModeloFormIssueLine,
  type ModeloWorkbenchFormProjectionV1,
  type PublicModeloFormField,
} from "../shell/modeloContract/modeloWorkForm";
import type { Translate } from "../shell/strings";
import { ASSET_NOTES } from "./modeloAssetNotes";
import { wholeEnvelopes } from "./modeloEnvelopePatch";
import { hex64 } from "./fixtures/ledger";

/** How the scenario's modelo family answers. `checked`, `filed`, `receipt`
 * and `stale` answer as `fixture` does, except that the first quarter's
 * Modelo 130 is read after its check, after it was recorded as filed
 * locally, after its AEAT receipt was verified, or after the declaration
 * changed once its file for the AEAT was made. `income` reads that 130 as
 * calculated over a ledger that books the quarter's activity income, never
 * checked, exported or filed: its capped boxes carry figures, and the
 * calculation's notes about them. `incomplete` lists the
 * declarations of a profile nothing was ever read from the AEAT for.
 *
 * The write shapes answer that Modelo 130's writes as the application
 * answered them: `edit` applies a typed value, `renewal` reads a form whose
 * baseline has since run out, renews it and reads the form again, and
 * `prerequisite` reads a third quarter whose apply is refused on an earlier
 * filing it waits on;
 * `exported` is the checked declaration with its file made, which exports
 * and records, `export-unverified` exports a file whose design carries no
 * completeness manifest, `export-cutoff-unverified` exports a direct debit
 * whose result says no direct-debit cutoff was checked, `export-notes`
 * exports a file whose calculation
 * noted two gaps of one kind about two elements and one of another kind, and
 * `export-unknown` loses the export's settlement, and `check-notes` reads the
 * checked declaration with two durable notes of one kind about two elements;
 * `rebase` stages on a read the declaration then moves under, so its check
 * is stale, renewing its baseline is refused, and the check on the form
 * read again reports each staged change kept, changed or dropped, and
 * `moving` moves it once more after that read, and again after the next,
 * so each check on a form read again is stale;
 * the `receipt` declaration is corrected, and `correction-refused` and
 * `correction-unknown` refuse the correction or lose its settlement;
 * `export-past-cutoff` and `report-outdated` settle the export of the file
 * for the AEAT or of the report as a refusal, with the error detail the
 * backend recorded for it and the sentence it served, in the report's
 * language.
 * `read-only-boxes` reads every box that takes a typed value as one whose kind
 * of value has no way in yet, as a date or a year box is: the application's
 * reads of these synthetic declarations hold no such box.
 * `withholding-link` reads the checked first quarter with one more blocking
 * line whose source is the suffered-withholding records, so the Check tab
 * offers to open them.
 * `list-notes` lists the first quarter's Modelo 130 with the sentences of the
 * asset notes as what its calculation noted that withholds nothing: the
 * application's list of these synthetic declarations notes none.
 * `disagreement` reads the first quarter after a value typed over box 06
 * replaced a different ledger figure, so its check states that disagreement
 * and offers to accept it: an acceptance with a reason is answered as the
 * application answered it, the form read again offers to revoke it, a
 * revocation at the revision the list served takes it back, and one at
 * another revision is refused as stale. `disagreement-raced` refuses the
 * acceptance as another session's already made, and the form read again
 * shows that acceptance; `disagreement-unknown` loses its settlement.
 *
 * The `renta` shapes list the declarations of a synthetic filer whose 2025
 * Modelo 100 is open, each read whole as the application served it.
 * `renta` is a salaried filer with no withholding certificate in the
 * register, so the credits and the totals that read them are unresolved;
 * `renta-pay` and `renta-refund` are the same filer with a certificate that
 * leaves a result to pay or to refund; `renta-activity` is a self-employed
 * filer whose activity income the ledger books. `renta-projected` and
 * `renta-credited` hold a calculated first-quarter Modelo 130 as well, so the
 * estimate from the quarterly declarations is answered: the first without a
 * certificate in the register, so the employment credit and the totals that
 * read it stay unresolved in it, the second with one. The estimate of every
 * other filer is refused as the application refused it, for want of a
 * quarterly declaration, and the refusal names the step that creates the
 * first quarter. The port follows the steps it is sent: once the quarter is
 * created the estimate is refused for want of a calculation and names the
 * step that calculates it, and once that is calculated it is refused for the
 * result the quarter does not yet produce. `renta-instalment` is the
 * salaried filer with a result to pay, read within the filing period, so the
 * settlement offers the result in two instalments and states both amounts.
 * `renta-married` is a married couple whose profile states the spouse, with a
 * certificate in the register: the comparison of joint and individual filing
 * is answered. The same couple without a certificate (`renta-uncredited`),
 * without the spouse in the profile (`renta-spouseless`), a single filer with
 * no child in the household (`renta-alone`) and a couple whose return is not
 * calculated (`renta-uncalculated`) have that comparison refused as the
 * application refused it. The first filer's is refused for want of the family
 * situation. `renta-parent` is a single parent who has not said whether they
 * live with the child's other parent, so the comparison names the box that
 * depends on it, and `renta-parentapart` is the same parent stating that they
 * do not, so it compares. `renta-y<year>` is the couple of another supported
 * filing year, read for that year's own edition. */
export const MODELO_SHAPES = [
  "wallet",
  "fixture",
  "checked",
  "filed",
  "receipt",
  "stale",
  "income",
  "incomplete",
  "edit",
  "renewal",
  "prerequisite",
  "exported",
  "export-unverified",
  "export-cutoff-unverified",
  "export-notes",
  "check-notes",
  "withholding-link",
  "export-unknown",
  "correction-refused",
  "correction-unknown",
  "export-past-cutoff",
  "report-outdated",
  "rebase",
  "moving",
  "read-only-boxes",
  "list-notes",
  "related-filings",
  "disagreement",
  "disagreement-raced",
  "disagreement-unknown",
  "renta",
  "renta-pay",
  "renta-refund",
  "renta-activity",
  "renta-projected",
  "renta-credited",
  "renta-instalment",
  "renta-married",
  "renta-uncredited",
  "renta-spouseless",
  "renta-alone",
  "renta-uncalculated",
  "renta-parent",
  "renta-parentapart",
  "refused",
  /** A creation refused for a profile fact the application wants, which names
   * that fact's own row as the way on. */
  "profile-field",
  /** A creation refused for a profile whose setup was never declared
   * complete, which names that declaration as the way on. */
  "profile-setup",
  "unknown",
  "unavailable",
  "slow",
] as const;
/** The shapes a scenario names, and `renta-y<year>`: the couple of a filing
 * year the registry supports, whose own edition decides what its Modelo 100
 * offers. Which years exist is what the stored envelopes hold, so no year is
 * listed here. */
export type ModeloShape = (typeof MODELO_SHAPES)[number] | `renta-y${number}`;

/** The shape a scenario's `modelo` parameter names, if it names one. */
export function modeloShape(name: string | null): ModeloShape | undefined {
  if (name === null) return undefined;
  return (
    MODELO_SHAPES.find((shape) => shape === name) ??
    (/^renta-y\d+$/.test(name) ? (name as ModeloShape) : undefined)
  );
}

/** The declaration whose later states the `checked` and `filed` shapes read. */
const LATER_STATES = "130-1T";

/** The refusal recorded for an estimate asked for at each stage of the first
 * quarter's Modelo 130: each names the step that puts it right, and the last,
 * once the quarter is calculated without the answers it refuses without,
 * names the quarter's open boxes and the step that opens it. */
const PROJECT_REFUSAL = {
  none: "project-no-quarters",
  drafted: "project-no-calculation",
  calculated: "project-quarter-incomplete",
} as const;

/** The 2025 Modelo 100, whose filer the `renta` shapes choose. */
const RENTA = "100-0A";

/** The filer's form a `renta` shape reads: the salaried filer without a
 * certificate is the declaration itself. */
const rentaForm = (shape: ModeloShape): string =>
  shape.startsWith("renta-")
    ? `${RENTA}-${shape.slice("renta-".length)}`
    : RENTA;

/** Every box a form's pages hold. */
function fields(node: unknown): PublicModeloFormField[] {
  if (Array.isArray(node)) return node.flatMap(fields);
  if (!node || typeof node !== "object") return [];
  const own =
    "held_zero" in node && "edit_address" in node
      ? [node as PublicModeloFormField]
      : [];
  return [...own, ...Object.values(node).flatMap(fields)];
}

/** Delay added to every answer of the `slow` shape. */
const SLOW_MS = 4000;

/** A rejected call, shaped as the host rejects one. */
class Refusal extends Error {
  readonly code: LedgerFailureCode;
  readonly operation_id: string | null;
  readonly reason?: string;
  constructor(readonly failure: LedgerFailure) {
    super(failure.code);
    this.code = failure.code;
    this.operation_id = failure.operation_id;
    if (failure.reason !== undefined) this.reason = failure.reason;
  }
}
const reject = (
  code: LedgerFailureCode,
  extra: Partial<LedgerFailure> = {},
): never => {
  throw new Refusal({ code, operation_id: null, ...extra });
};

/** A form read after its calculation kept asset notes: each is a line to
 * check, as the backend words it, and a note of the form. */
function withAssetNotes(
  form: ModeloWorkbenchFormProjectionV1,
  t: Translate,
): ModeloWorkbenchFormProjectionV1 {
  return {
    ...form,
    issue_lines: [
      ...form.issue_lines,
      ...ASSET_NOTES.map((note): ModeloFormIssueLine => ({
        level: "check",
        box: null,
        where: null,
        message: note.message,
        action: t("workspace.modelo.notes.lead"),
        detail: note.detail,
        technical: note.reason,
        address: null,
        in_records: false,
        surface: null,
        from_calculation: true,
        recalculates: false,
        finding_id: null,
        resolution_answer: null,
        answer_lead_words: null,
        answer_lead_words_language: null,
      })),
    ],
  };
}

/** A form read with one blocking line whose figures come from the payers'
 * withholding certificates, which the Check tab can open. */
function withWithholdingLine(
  form: ModeloWorkbenchFormProjectionV1,
): ModeloWorkbenchFormProjectionV1 {
  return {
    ...form,
    issue_lines: [
      {
        level: "blocks",
        box: null,
        where: null,
        message:
          "The withholding payers took from your income is not recorded yet.",
        action:
          "Record the payers' certificates or state that none was withheld.",
        detail: null,
        technical: "withholding_not_recorded",
        address: null,
        in_records: false,
        surface: "withholding",
        from_calculation: false,
        recalculates: false,
        finding_id: null,
        resolution_answer: null,
        answer_lead_words: null,
        answer_lead_words_language: null,
      },
      ...form.issue_lines,
    ],
  };
}

type Row = ModeloDeclarationsListProjectionV1["rows"][number];

/** A list stored before its rows carried calculation notes, read as the
 * application's model reads it: a row that names none noted none. */
function withStoredDefaults(
  list: ModeloDeclarationsListProjectionV1,
): ModeloDeclarationsListProjectionV1 {
  return {
    ...list,
    rows: list.rows.map((row) => {
      const stored: Omit<Row, "calculation_notes"> &
        Partial<Pick<Row, "calculation_notes">> = row;
      return { ...stored, calculation_notes: stored.calculation_notes ?? [] };
    }),
  };
}

/** The declarations list with the asset notes' sentences on the first local
 * Modelo 130 row, as what its calculation noted that withholds nothing. */
function withListNotes(
  list: ModeloDeclarationsListProjectionV1,
): ModeloDeclarationsListProjectionV1 {
  const noted = list.rows.find(
    (row) => row.modelo === "130" && row.opens_local_work,
  );
  return {
    ...list,
    rows: list.rows.map((row) =>
      row === noted
        ? {
            ...row,
            calculation_notes: ASSET_NOTES.map((note) => note.message),
          }
        : row,
    ),
  };
}

/** A form read with its typed boxes as boxes that cannot be typed into, each
 * saying why as the backend words it. */
function withReadOnlyBoxes(
  form: ModeloWorkbenchFormProjectionV1,
  t: Translate,
): ModeloWorkbenchFormProjectionV1 {
  for (const field of fields(form.form.form.pages))
    if (field.takes_typed_value) {
      field.editability = "not_writable";
      field.not_writable_reason = "value_channel_unavailable";
      field.editability_words = t(
        "workspace.modelo.not_writable.value_channel_unavailable",
      );
      field.takes_typed_value = false;
      field.clearable = false;
    }
  return form;
}

/** Every envelope by name, each read on first use: the largest forms are
 * over a megabyte. */
export type ModeloEnvelopes = Record<string, () => Promise<unknown>>;

/** The envelopes on disk, as the development server serves them. */
function servedEnvelopes(): ModeloEnvelopes {
  const found = requireServed(
    "modelo/*.json",
    import.meta.glob<unknown>("@fixtures/modelo/*.json", {
      import: "default",
    }),
  );
  return Object.fromEntries(
    Object.entries(found).map(([path, load]) => [
      path.slice(path.lastIndexOf("/") + 1, -".json".length),
      load,
    ]),
  );
}

/** An untouched form envelope, named by its modelo and period. */
const DECLARATION = /^modelo-(\d+-[0-9A-Z]+)-en$/;

type Options = {
  say: (call: string) => void;
  wait: () => Promise<void>;
  signedIn: () => boolean;
  shape: ModeloShape;
  /** Where a runner without the development server reads the envelopes. */
  envelopes?: ModeloEnvelopes;
  /** The words of a language. The generated catalogue is a build-tool module
   * that only the bundler resolves, so the caller that has it brings it; a
   * runner that does not takes the keys as they are. */
  translate: (language: string) => Translate;
};

const PURPOSE_FILES: Record<ModeloFilePurpose, string> = {
  evidence: "justificante-modelo-130-2026-1T.pdf",
  report: "informe-calculo-modelo-130.pdf",
  package: "paquete-revision-modelo-130.zip",
  signature: "paquete-revision-modelo-130.sig",
  envelope: "respuesta-asesoria.sealed",
};

declare global {
  interface Window {
    /** Active synthetic modelo port, for controlled operation observations. */
    __fixtureModelo?: ModeloPort;
  }
}

export function modeloFixture(options: Options): ModeloPort {
  const { say, signedIn, shape } = options;
  const catalogue = wholeEnvelopes(options.envelopes ?? servedEnvelopes());
  /** The envelope stored under `name`, or null where none was read. */
  async function envelope<Envelope>(name: string): Promise<Envelope | null> {
    const load = catalogue[name];
    return load ? (structuredClone(await load()) as Envelope) : null;
  }
  async function relatedFilingName(
    id: unknown,
    language: string,
  ): Promise<string | null> {
    for (const name of [
      "130-original",
      "130-correction-1",
      "130-correction-2",
    ]) {
      const view = await envelope<ModeloFilingRecordViewProjection>(
        `filing-view-${name}-${language}`,
      );
      if (view?.filing_record_id === id) return name;
    }
    return null;
  }
  /** The declarations whose forms were read, by work unit. */
  const forms: Record<string, string> = {};
  async function formName(workUnitId: string): Promise<string | null> {
    if (forms[workUnitId]) return forms[workUnitId];
    for (const name of Object.keys(catalogue)) {
      const declaration = DECLARATION.exec(name)?.[1];
      if (!declaration) continue;
      const form = await envelope<ModeloWorkbenchFormProjectionV1>(name);
      if (form) forms[form.work_unit_id] = declaration;
    }
    // The first quarter the scenario created is the declaration whose form
    // was read, so the estimate's step that opens it finds one.
    if (!forms[workUnitId] && quarter !== "none") {
      const created = await envelope<ModeloWorkCreateProjection>("create-130");
      if (
        created?.outcome.kind === "success" &&
        created.outcome.unit.work_unit_id === workUnitId
      )
        forms[workUnitId] = LATER_STATES;
    }
    return forms[workUnitId] ?? null;
  }
  let operations = 0;
  const outcomes = new Map<string, LedgerOutcome>();
  const files = new Map<FileToken, { name: string; picked: boolean }>();

  const answer = async () => {
    await options.wait();
    if (shape === "slow")
      await new Promise((done) => window.setTimeout(done, SLOW_MS));
    if (shape === "unavailable") reject("unavailable");
    if (!signedIn()) reject("not_signed_in");
  };
  const nextOperation = () => {
    operations += 1;
    return hex64(`modelo-operation:${operations}`);
  };
  const settle = (result: unknown): LedgerOutcome => {
    const operation = nextOperation();
    const outcome: LedgerOutcome = {
      kind: "settled",
      operation_id: operation,
      revision: 3,
      result: result as JsonObject,
    };
    outcomes.set(operation, outcome);
    return outcome;
  };
  // A write the scenario cannot serve: `unknown` is a lost settlement,
  // `refused` a refusal that wrote nothing, and otherwise nothing is sent.
  const unserved = (): never => {
    if (shape === "unknown")
      reject("unknown", { operation_id: nextOperation() });
    if (shape === "refused")
      reject("refused", {
        operation_id: nextOperation(),
        reason: "operation_denied",
      });
    return reject("unavailable");
  };

  // What the scenario's writes did, as far as they settled.
  let applied = false;
  // How far the answer to the disagreement the applied 130 states has come.
  let answered: "open" | "accepted" | "revoked" = "open";
  let recorded = false;
  let corrected = false;
  // How far the first quarter's Modelo 130 has come for a filer whose
  // estimate is refused: not created, created, or calculated.
  let quarter: "none" | "drafted" | "calculated" = "none";
  let walletStage: "empty" | "seed" | "correct" | "override" = "empty";
  // How many renewals were answered, granted or refused: after each the
  // window reads the declaration again.
  let renewals = 0;
  /** The envelope the first quarter's Modelo 130 is read from, by shape and
   * by what was written. */
  const laterState = (): string => {
    switch (shape) {
      case "checked":
      case "filed":
      case "stale":
      case "income":
        return `130-1T-${shape}`;
      case "receipt":
        return corrected ? "130-1T-correction-1-pending" : "130-1T-receipt";
      case "check-notes":
      case "withholding-link":
        return "130-1T-checked";
      case "correction-refused":
      case "correction-unknown":
        return "130-1T-receipt";
      case "exported":
      case "export-unverified":
      case "export-cutoff-unverified":
      case "export-notes":
      case "export-unknown":
      case "export-past-cutoff":
      case "report-outdated":
        return recorded ? "130-1T-filed" : "130-1T-exported";
      case "edit":
        return applied ? "130-1T-applied" : "130-1T-exported";
      case "disagreement":
      case "disagreement-raced":
      case "disagreement-unknown":
        return answered === "open" ? "130-1T-applied" : `130-1T-${answered}`;
      // Read half an hour ago; read again after its renewal, it admits a
      // fresh baseline.
      case "renewal":
        return renewals > 0 ? "130-1T-renewed" : "130-1T-expiring";
      case "rebase":
        return renewals > 0 ? "130-1T-rebased" : "130-1T-rebase";
      case "moving":
        // Each renewal the window asks for is refused, and each read after
        // one finds the declaration moved again.
        return (
          ["130-1T-rebase", "130-1T-moving"][renewals] ?? "130-1T-moving-again"
        );
      case "prerequisite":
        return "130-3T-prerequisite";
      default:
        return LATER_STATES;
    }
  };
  /** The written form each admitted baseline was read from. */
  const admittedBy = new Map<string, string>();
  /** The language the window last read a form in, which the application
   * words an estimate in. */
  let spoken: OutputLanguage = "en";
  /** The written form a read of the declaration `name` is answered with
   * now. */
  const writtenRead = (name: string | null) =>
    shape === "wallet" && name === "303-1T"
      ? `303-1T-wallet-${walletStage}`
      : name === LATER_STATES
        ? laterState()
        : name === RENTA
          ? rentaForm(shape)
          : name;
  const readForm = async (workUnitId: string, language: OutputLanguage) => {
    spoken = language;
    const name = await formName(workUnitId);
    const read = writtenRead(name);
    const form =
      read &&
      (await envelope<ModeloWorkbenchFormProjectionV1>(
        `modelo-${read}-${language}`,
      ));
    const admitted = form ? form.admitted_baseline?.baseline_id : undefined;
    if (read && admitted) admittedBy.set(admitted, read);
    if (!form) return reject("refused", { reason: "profile_mismatch" });
    if (shape === "read-only-boxes")
      return withReadOnlyBoxes(form, options.translate(language));
    if (shape === "withholding-link" && name === LATER_STATES)
      return withWithholdingLine(form);
    return shape === "check-notes" && name === LATER_STATES
      ? withAssetNotes(form, options.translate(language))
      : form;
  };
  /** The envelope `name` of a write the scenario answers, or unserved. */
  const written = async (name: string): Promise<unknown> =>
    (await envelope<unknown>(name)) ?? unserved();
  /** A write the backend refused once it ran: it settles without writing,
   * carrying the error detail recorded for `refusal` in `language`. */
  const refusedWith = async (
    refusal: string,
    language: unknown,
  ): Promise<LedgerOutcome> => {
    const detail = await envelope<JsonObject>(
      `refusal-${refusal}-${String(language)}`,
    );
    if (!detail) return unserved();
    const operation = nextOperation();
    const outcome: LedgerOutcome = {
      kind: "refused",
      operation_id: operation,
      revision: 3,
      reason: typeof detail.error_code === "string" ? detail.error_code : null,
      detail: detail as unknown as LedgerErrorDetail,
    };
    outcomes.set(operation, outcome);
    return outcome;
  };
  /** A write the backend refused once it ran with the typed refusal its
   * definition declares: it settles without writing, carrying the refusal
   * stored under `name`. */
  const refusedAs = async (name: string): Promise<LedgerOutcome> => {
    const detail = await envelope<{ refusal?: { code?: unknown } }>(name);
    if (!detail) return unserved();
    const operation = nextOperation();
    const outcome: LedgerOutcome = {
      kind: "refused",
      operation_id: operation,
      revision: 3,
      reason:
        typeof detail.refusal?.code === "string" ? detail.refusal.code : null,
      detail: detail as unknown as LedgerErrorDetail,
    };
    outcomes.set(operation, outcome);
    return outcome;
  };
  const disagreementShape =
    shape === "disagreement" ||
    shape === "disagreement-raced" ||
    shape === "disagreement-unknown";
  /** The disagreement the applied 130's check offers to answer, as its form
   * states it, and the calculation it was read for. */
  const disagreementTarget = async () => {
    const form = await envelope<ModeloWorkbenchFormProjectionV1>(
      "modelo-130-1T-applied-en",
    );
    const line = form?.issue_lines.find((each) => each.finding_id !== null);
    return form && line
      ? {
          finding_id: line.finding_id,
          calculation_revision_id: form.calculation_revision_id,
        }
      : null;
  };
  /** A file the host issued for `picked` (a pick) or not (a save). */
  const issued = (token: unknown, picked: boolean) => {
    const file = files.get(token as FileToken);
    if (!file || file.picked !== picked) reject("invalid");
  };
  /** The first quarter's export, whose calculation kept notes with it: two
   * elements with a gap of one kind, and a purchase booked as an expense. */
  const exportWithNotes = async (): Promise<unknown> => {
    const exported = (await written(
      "export-130",
    )) as ModeloExportPublicResultV3;
    return {
      ...exported,
      fichero_boe: exported.fichero_boe && {
        ...exported.fichero_boe,
        calculation_notes: ASSET_NOTES,
      },
    };
  };
  /** The first quarter's export paid by direct debit, whose result says no
   * direct-debit cutoff could be checked for it. */
  const exportCutoffUnverified = async (): Promise<unknown> => {
    const exported = (await written(
      "export-130",
    )) as ModeloExportPublicResultV3;
    return {
      ...exported,
      fichero_boe: exported.fichero_boe && {
        ...exported.fichero_boe,
        resolved_result_disposition: "U",
        payment_election: "domiciliacion",
        domiciliation_cutoff_unverified: true,
      },
    };
  };
  const receiptShape =
    shape === "receipt" ||
    shape === "correction-refused" ||
    shape === "correction-unknown";
  // Every edit envelope was read on the baseline of one written form and is
  // named after it, so a baseline names the form a write was read for; a
  // baseline no written form admitted names none, and its write is invalid.
  // The forms this port served are known by their baselines as they are
  // read. Only a baseline from elsewhere reads every written form, whose
  // envelopes are many and some of them megabytes.
  let everyForm: Promise<void> | null = null;
  const readEveryForm = async () => {
    // Seconds of reading: a check that waits on it can outlast its review.
    say("modelo scan written forms");
    for (const name of Object.keys(catalogue)) {
      const read = /^modelo-(.+)-(?:en|es|ca|hu)$/.exec(name)?.[1];
      if (!read) continue;
      const form = await envelope<ModeloWorkbenchFormProjectionV1>(name);
      const admitted = form?.admitted_baseline?.baseline_id;
      if (admitted) admittedBy.set(admitted, read);
    }
  };
  const formAdmitting = async (baselineId: unknown): Promise<string> => {
    if (typeof baselineId !== "string") return reject("invalid");
    if (!admittedBy.has(baselineId)) await (everyForm ??= readEveryForm());
    return admittedBy.get(baselineId) ?? reject("invalid");
  };
  /** A held change's box as a form field addresses it. */
  const heldBox = (address: ModeloEditHeldChangeV1["address"]) =>
    "casilla_id" in address ? address.casilla_id : address.binding_id;
  /** The review read for the changes this window holds: one per set of held
   * changes and form they were staged on, and of those the one whose form
   * shows each box in the state the window holds it in. A held state no
   * staged-on form shows is refused. */
  const reviewHeld = async (
    form: string,
    held: ModeloEditHeldChangeV1[],
  ): Promise<string> => {
    const prefix = `preflight-${form}-review${held
      .map((change) => `-${heldBox(change.address)}${change.kind}`)
      .sort()
      .join("")}-from-`;
    for (const name of Object.keys(catalogue).filter((each) =>
      each.startsWith(prefix),
    )) {
      const states = new Map(
        fields(
          (
            await envelope<ModeloWorkbenchFormProjectionV1>(
              `modelo-${name.slice(prefix.length)}-en`,
            )
          )?.form.form.pages,
        ).map((field) => [
          JSON.stringify(field.edit_address),
          field.state_digest,
        ]),
      );
      const stands = held.every(
        (change) =>
          states.get(
            JSON.stringify(
              "casilla_id" in change.address
                ? { kind: "casilla", casilla_id: change.address.casilla_id }
                : change.address,
            ),
          ) === change.held_state,
      );
      if (stands) return name;
    }
    return reject("invalid");
  };
  /** A held change or a report entry, by its box and kind. */
  const heldKey = (change: { address: unknown; kind: string }) =>
    `${JSON.stringify(change.address)}|${change.kind}`;
  const readHelp = async (
    workUnitId: string,
    casillaId: string,
    language: OutputLanguage,
  ) => {
    const name = await formName(workUnitId);
    const modelo = name?.split("-")[0];
    const card =
      modelo &&
      (await envelope<ModeloCasillaHelpProjectionV1>(
        `help-${modelo}-${casillaId}-${language}`,
      ));
    return card || reject("unavailable");
  };

  const port: ModeloPort = {
    async declarations(language) {
      if (typeof window !== "undefined") window.__fixtureModelo = port;
      say(`modelo declarations ${language}`);
      await answer();
      const list = await envelope<ModeloDeclarationsListProjectionV1>(
        `declarations${
          shape === "related-filings"
            ? "-corrections"
            : shape === "wallet"
              ? "-wallet"
              : shape === "incomplete"
                ? "-incomplete"
                : shape.startsWith("renta")
                  ? "-renta"
                  : ""
        }-${language}`,
      );
      if (!list) return reject("unavailable");
      const read = withStoredDefaults(list);
      return shape === "list-notes" ? withListNotes(read) : read;
    },
    async form(workUnitId, language) {
      say(`modelo form ${language}`);
      await answer();
      return readForm(workUnitId, language);
    },
    async casillaHelp(request) {
      say(`modelo casillaHelp ${request.language}`);
      await answer();
      return readHelp(request.workUnitId, request.casillaId, request.language);
    },
    async submit(definition, payload, ...workUnit) {
      say(`modelo submit ${definition}`);
      await answer();
      if (!isModeloDefinition(definition)) reject("not_admitted");
      const request = payload as JsonObject;
      if ("profile_id" in request || "bucket_id" in request) reject("invalid");
      if (needsWorkUnit(definition) !== (workUnit.length === 1))
        reject("invalid");
      const language = request.output_language as OutputLanguage;
      if (definition === "modelo.export" && shape === "export-past-cutoff") {
        issued(request.output_path, false);
        return (await refusedWith(
          "domiciliation-past-cutoff",
          request.report_language,
        )) as LedgerOutcome<ModeloResult<typeof definition>>;
      }
      if (definition === "modelo.export" && shape === "report-outdated") {
        issued(request.output_path, false);
        return (await refusedWith(
          "report-outdated",
          request.report_language,
        )) as LedgerOutcome<ModeloResult<typeof definition>>;
      }
      if (
        definition === "modelo.project" &&
        !catalogue[`project-${rentaForm(shape)}-${spoken}`]
      )
        return (await refusedWith(
          PROJECT_REFUSAL[quarter],
          spoken,
        )) as LedgerOutcome<ModeloResult<typeof definition>>;
      if (
        disagreementShape &&
        (definition === "modelo.work.accept_disagreement" ||
          definition === "modelo.work.revoke_disagreement")
      ) {
        const target = await disagreementTarget();
        if (
          !target ||
          request.finding_id !== target.finding_id ||
          request.calculation_revision_id !== target.calculation_revision_id
        )
          return unserved();
        if (definition === "modelo.work.accept_disagreement") {
          if (typeof request.reason !== "string" || !request.reason.trim())
            reject("invalid");
          if (shape === "disagreement-unknown")
            reject("unknown", { operation_id: nextOperation() });
          // Another session accepted it first: this one is refused, and the
          // declaration read again shows the acceptance.
          if (shape === "disagreement-raced" || answered === "accepted") {
            answered = "accepted";
            return (await refusedAs(
              `accept-130-1T-accepted-refused-${language}`,
            )) as LedgerOutcome<ModeloResult<typeof definition>>;
          }
          if (answered !== "open") return unserved();
          const accepted = await written("accept-130-1T-applied");
          answered = "accepted";
          return settle(accepted) as LedgerOutcome<
            ModeloResult<typeof definition>
          >;
        }
        if (answered !== "accepted") return unserved();
        const held = await envelope<CreditResolutionListProjection>(
          `disagreements-130-1T-accepted-${language}`,
        );
        const stored = held?.resolutions.find(
          (row) => row.finding_id === target.finding_id,
        );
        if (!stored) return unserved();
        // A revocation at a revision the acceptance is no longer at is
        // refused as stale.
        if (request.expected_revision_id !== stored.revision_id)
          return (await refusedAs(
            `revoke-130-1T-accepted-stale-${language}`,
          )) as LedgerOutcome<ModeloResult<typeof definition>>;
        const revoked = await written("revoke-130-1T-accepted");
        answered = "revoked";
        return settle(revoked) as LedgerOutcome<
          ModeloResult<typeof definition>
        >;
      }
      if (
        definition === "modelo.work.compare_taxation" &&
        shape.startsWith("renta") &&
        !catalogue[`compare-${rentaForm(shape)}-${spoken}`]
      )
        return (await refusedWith(
          `compare-${rentaForm(shape)}`,
          spoken,
        )) as LedgerOutcome<ModeloResult<typeof definition>>;
      // A profile the application will not file for: the creation is refused
      // with the door the refusal names, as the backend recorded it, and
      // nothing is written. A creation names no output language, so the
      // refusal is worded in the one the window last read in.
      if (
        definition === "modelo.work.create" &&
        (shape === "profile-field" || shape === "profile-setup")
      )
        return (await refusedWith(shape, spoken)) as LedgerOutcome<
          ModeloResult<typeof definition>
        >;
      const result = await (async (): Promise<unknown> => {
        switch (definition) {
          case "modelo.work.compare_taxation":
            return shape.startsWith("renta")
              ? written(`compare-${rentaForm(shape)}-${spoken}`)
              : unserved();
          case "modelo.iva-wallet.balance": {
            if (shape !== "wallet") return unserved();
            // The balance is served for the year the written read was taken at.
            const balance = await envelope<JsonObject>(
              `iva-wallet-balance-${walletStage}`,
            );
            return balance && request.as_of_year === balance.as_of_year
              ? balance
              : unserved();
          }
          case "modelo.iva-wallet.seed":
          case "modelo.iva-wallet.correct":
          case "modelo.iva-wallet.override": {
            if (shape !== "wallet") return unserved();
            const mode = definition.slice("modelo.iva-wallet.".length);
            const before =
              mode === "seed"
                ? "empty"
                : mode === "correct"
                  ? "seed"
                  : "correct";
            // A write is answered when it carries what the written one did.
            const result = await envelope<JsonObject>(`iva-wallet-${mode}`);
            if (!result || walletStage !== before) return unserved();
            const period = request.period as
              { filing_year?: unknown; code?: unknown } | undefined;
            const recorded = result.period as
              { filing_year?: unknown; code?: unknown } | undefined;
            const carried = (["amount", "reason", "evidence_locator"] as const)
              .filter((field) => field in result)
              .every((field) => request[field] === result[field]);
            if (
              period?.filing_year !== recorded?.filing_year ||
              period?.code !== recorded?.code ||
              !carried
            )
              return unserved();
            walletStage =
              mode === "seed"
                ? "seed"
                : mode === "correct"
                  ? "correct"
                  : "override";
            return result;
          }
          case "modelo.project":
            return written(`project-${rentaForm(shape)}-${spoken}`);
          case "modelo.declarations.list":
            return port.declarations(language);
          case "modelo.work.form":
            return readForm(String(request.work_unit_id), language);
          case "modelo.work.casilla_help":
            return readHelp(
              String(request.work_unit_id),
              String(request.casilla_id),
              language,
            );
          case "modelo.edit.renew": {
            // The renewal the application gave the baseline this request
            // names, granted or refused.
            const baseline = request.baseline as { baseline_id?: unknown };
            const form = await formAdmitting(baseline?.baseline_id);
            const renewal = await envelope<ModeloEditRenewalProjectionV1>(
              `renew-${form}`,
            );
            if (!renewal) return unserved();
            renewals += 1;
            // A granted renewal issues the baseline the declaration's next
            // read admits, and the window may check on it before that read
            // lands; it names that form now rather than through a scan of
            // every written form.
            const renewed = renewal.renewed_baseline;
            if (renewed) {
              const next = writtenRead(await formName(renewed.work_unit_id));
              const read = next
                ? await envelope<ModeloWorkbenchFormProjectionV1>(
                    `modelo-${next}-${spoken}`,
                  )
                : undefined;
              if (
                next &&
                read?.admitted_baseline?.baseline_id === renewed.baseline_id
              )
                admittedBy.set(renewed.baseline_id, next);
            }
            return renewal;
          }
          case "modelo.edit.apply_prerequisite": {
            const form = await formAdmitting(request.baseline_id);
            return shape === "prerequisite"
              ? written(`apply-prerequisite-${form}`)
              : unserved();
          }
          case "modelo.export": {
            issued(request.output_path, false);
            if (shape === "export-unknown")
              reject("unknown", { operation_id: nextOperation() });
            if (shape === "export-unverified")
              return written("export-165-unverified");
            if (shape === "export-cutoff-unverified")
              return exportCutoffUnverified();
            if (shape === "export-notes") return exportWithNotes();
            return shape === "exported" ? written("export-130") : unserved();
          }
          case "modelo.work.file": {
            if (shape !== "exported") return unserved();
            const filed = await written("file-130");
            recorded = true;
            return filed;
          }
          case "modelo.reconcile.import":
            issued(request.source_path, true);
            return shape === "filed" && request.source_kind === "justificante"
              ? written("reconcile-130")
              : unserved();
          case "modelo.work.create": {
            // The first quarter, which a refused estimate asks to create.
            if (quarter !== "none" || !shape.startsWith("renta"))
              return unserved();
            const created = await written("create-130");
            quarter = "drafted";
            return created;
          }
          case "modelo.work.calculate": {
            // The quarter just created, whose id the refusal that followed
            // named.
            const drafted =
              await envelope<ModeloWorkCreateProjection>("create-130");
            if (
              quarter !== "drafted" ||
              drafted?.outcome.kind !== "success" ||
              drafted.outcome.unit.work_unit_id !== request.work_unit_id
            )
              return unserved();
            const calculated = await written("calculate-130");
            quarter = "calculated";
            return calculated;
          }
          case "modelo.work.disagreements":
            return disagreementShape
              ? written(`disagreements-${laterState()}-${language}`)
              : unserved();
          case "modelo.work.metadata":
            return receiptShape
              ? written(
                  corrected
                    ? "metadata-130-correction-1-pending"
                    : "metadata-130-receipt",
                )
              : unserved();
          case "modelo.filing_record.view": {
            const name = await relatedFilingName(
              request.filing_record_id,
              language,
            );
            return name
              ? written(`filing-view-${name}-${language}`)
              : unserved();
          }
          case "modelo.work.amendment_context": {
            if (shape === "related-filings") {
              const name = await relatedFilingName(
                request.filing_record_id,
                language,
              );
              return name
                ? written(`amendment-context-${name}-${language}`)
                : unserved();
            }
            return receiptShape
              ? written(
                  corrected
                    ? `amendment-context-130-correction-1-pending-${language}`
                    : "amendment-context-130",
                )
              : unserved();
          }
          case "modelo.work.amend":
            if (shape === "correction-unknown")
              reject("unknown", { operation_id: nextOperation() });
            if (shape === "correction-refused")
              reject("refused", {
                operation_id: nextOperation(),
                reason: "operation_denied",
              });
            if (shape === "receipt") {
              const amended = await written("amend-130");
              corrected = true;
              return amended;
            }
            return unserved();
          default:
            return unserved();
        }
      })();
      return settle(result) as LedgerOutcome<ModeloResult<typeof definition>>;
    },
    async edit(definition, body) {
      try {
        say(`modelo edit ${definition}`);
        await answer();
        if (body.byteLength > RELAY_PAYLOAD_LIMIT) reject("invalid");
        let input: ModeloEditOperatorInputV2;
        try {
          input = JSON.parse(
            new TextDecoder().decode(body),
          ) as ModeloEditOperatorInputV2;
        } catch {
          return reject("invalid");
        }
        // The answer is the one the application gave on the baseline this
        // body names: a baseline no written form admitted is refused.
        const submission = input.submission;
        const form = await formAdmitting(submission?.baseline?.baseline_id);
        if (definition === "modelo.edit.preflight") {
          // Which check was sent: a correction's figures, entries as typed,
          // or the staged changes, which a form read before the declaration
          // moved, or before its baseline ran out, answers as stale.
          const entries = submission.lexemes ?? [];
          const correction = entries.find(
            (entry) => entry.address.kind === "correction",
          );
          const held = submission.held ?? [];
          const read = correction
            ? /^[-\u2212+\d.,\s]+$/.test(correction.lexeme)
              ? `preflight-${form}-correction`
              : `preflight-${form}-correction-refused`
            : entries.length > 0
              ? `preflight-${form}-entry-${entries
                  .map((entry) =>
                    "casilla_id" in entry.address
                      ? entry.address.casilla_id
                      : entry.address.binding_id,
                  )
                  .join("-")}-${entries[0]?.entry_locale}`
              : catalogue[`preflight-${form}-stale`]
                ? `preflight-${form}-stale`
                : await reviewHeld(form, held);
          const preflight =
            read && (await envelope<ModeloEditPreflightProjectionV1>(read));
          if (!preflight) return unserved();
          // Read for exactly this baseline and, where it reports on them,
          // exactly the changes this window holds.
          const outcome = preflight.outcome;
          const on =
            outcome.outcome === "evaluated"
              ? outcome.baseline_id
              : "baseline_id" in outcome.refusal
                ? outcome.refusal.baseline_id
                : submission.baseline.baseline_id;
          if (on !== submission.baseline.baseline_id) reject("invalid");
          const sent = held.map(heldKey).sort();
          const reported = preflight.rebase.map(heldKey).sort();
          if (reported.length > 0 && reported.join() !== sent.join())
            reject("invalid");
          return settle(preflight) as LedgerOutcome<
            ModeloResult<typeof definition>
          >;
        }
        if (shape === "prerequisite")
          reject("refused", { operation_id: nextOperation() });
        const result = await envelope<unknown>(`apply-${form}`);
        if (!result) return unserved();
        applied = true;
        return settle(result) as LedgerOutcome<ModeloResult<typeof definition>>;
      } finally {
        body.fill(0);
      }
    },
    async observe(operation) {
      say("modelo observe");
      await answer();
      return outcomes.get(operation) ?? reject("unknown");
    },
    async review() {
      say("modelo review");
      await answer();
      return reject("unavailable");
    },
    async answer() {
      say("modelo answer");
      await answer();
      return reject("review_changed");
    },
    async cancel(operation) {
      say("modelo cancel");
      await answer();
      return outcomes.get(operation) ?? reject("unknown");
    },
    async pickFile(purpose: ModeloFilePurpose) {
      say(`modelo pickFile ${purpose}`);
      await answer();
      return issue(PURPOSE_FILES[purpose], true);
    },
    async saveFile(format: ModeloSaveFormat, _label, suggestedName) {
      say(`modelo saveFile ${format}`);
      await answer();
      const stem = (suggestedName ?? "modelo").replace(/\.[^.]*$/, "");
      return issue(`${stem}.${format}`, false);
    },
    async forgetFiles(tokens) {
      say("modelo forgetFiles");
      for (const token of tokens) files.delete(token);
    },
    async revealFile(token) {
      say("modelo revealFile");
      await answer();
      const file = files.get(token);
      if (!file) reject("file_unavailable");
      if (file?.picked) reject("invalid");
    },
  };
  const issue = (name: string, picked: boolean): FilePicks => {
    const token =
      `file-${hex64(`modelo-file:${files.size}:${name}`).slice(0, 32)}` as FileToken;
    files.set(token, { name, picked });
    return { files: [{ token, name, bytes: null }], refused: 0 };
  };
  return port;
}
