// The scenario host's modelo family: the modelo port answered from the
// envelopes in ./fixtures/modelo/, which scripts/modelo-fixtures.mjs reads
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
import {
  type ModeloCasillaHelpProjectionV1,
  type ModeloDeclarationsListProjectionV1,
  type ModeloEditOperatorInputV2,
  type ModeloEditHeldChangeV1,
  type ModeloEditPreflightProjectionV1,
  type ModeloEditRenewalProjectionV1,
  type ModeloExportPublicResultV3,
  type ModeloFormIssueLine,
  type ModeloWorkbenchFormProjectionV1,
  type PublicModeloFormField,
  type OutputLanguage,
} from "../shell/modeloContract";
import { translator } from "../shell/strings";
import { ASSET_NOTES } from "./modeloAssetNotes";
import { hex64 } from "./fixtures/ledger";

/** How the scenario's modelo family answers. `checked`, `filed`, `receipt`
 * and `stale` answer as `fixture` does, except that the first quarter's
 * Modelo 130 is read after its check, after it was recorded as filed
 * locally, after its AEAT receipt was verified, or after the declaration
 * changed once its file for the AEAT was made. `incomplete` lists the
 * declarations of a profile nothing was ever read from the AEAT for.
 *
 * The write shapes answer that Modelo 130's writes as the application
 * answered them: `edit` applies a typed value, `renewal` reads a form whose
 * baseline has since run out, renews it and reads the form again, and
 * `prerequisite` reads a third quarter whose apply is refused on an earlier
 * filing it waits on;
 * `exported` is the checked declaration with its file made, which exports
 * and records, `export-unverified` exports a file whose design carries no
 * completeness manifest, `export-notes` exports a file whose calculation
 * noted two gaps of one kind about two elements and one of another kind, and
 * `export-unknown` loses the export's settlement, and `check-notes` reads the
 * checked declaration with two durable notes of one kind about two elements;
 * `rebase` stages on a read the declaration then moves under, so its check
 * is stale, renewing its baseline is refused, and the check on the form
 * read again reports each staged change kept, changed or dropped, and
 * `moving` moves it once more after that read, and again after the next,
 * so each check on a form read again is stale;
 * the `receipt` declaration is corrected, and `correction-refused` and
 * `correction-unknown` refuse the correction or lose its settlement. */
export const MODELO_SHAPES = [
  "fixture",
  "checked",
  "filed",
  "receipt",
  "stale",
  "incomplete",
  "edit",
  "renewal",
  "prerequisite",
  "exported",
  "export-unverified",
  "export-notes",
  "check-notes",
  "export-unknown",
  "correction-refused",
  "correction-unknown",
  "rebase",
  "moving",
  "refused",
  "unknown",
  "unavailable",
  "slow",
] as const;
export type ModeloShape = (typeof MODELO_SHAPES)[number];

/** The declaration whose later states the `checked` and `filed` shapes read. */
const LATER_STATES = "130-1T";

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
  language: OutputLanguage,
): ModeloWorkbenchFormProjectionV1 {
  const t = translator(language);
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
      })),
    ],
  };
}

/** Every envelope by name, each read on first use: the largest forms are
 * over a megabyte. */
export type ModeloEnvelopes = Record<string, () => Promise<unknown>>;

/** The envelopes on disk, as the development server serves them. */
function servedEnvelopes(): ModeloEnvelopes {
  const found = import.meta.glob<unknown>("./fixtures/modelo/*.json", {
    import: "default",
  });
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
};

const PURPOSE_FILES: Record<ModeloFilePurpose, string> = {
  evidence: "justificante-modelo-130-2026-1T.pdf",
  report: "informe-calculo-modelo-130.pdf",
  package: "paquete-revision-modelo-130.zip",
  signature: "paquete-revision-modelo-130.sig",
  envelope: "respuesta-asesoria.sealed",
};

export function modeloFixture(options: Options): ModeloPort {
  const { say, signedIn, shape } = options;
  const catalogue = options.envelopes ?? servedEnvelopes();
  /** The envelope stored under `name`, or null where none was read. */
  async function envelope<Envelope>(name: string): Promise<Envelope | null> {
    const load = catalogue[name];
    return load ? (structuredClone(await load()) as Envelope) : null;
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
  let recorded = false;
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
      case "receipt":
        return `130-1T-${shape}`;
      case "check-notes":
        return "130-1T-checked";
      case "correction-refused":
      case "correction-unknown":
        return "130-1T-receipt";
      case "exported":
      case "export-unverified":
      case "export-notes":
      case "export-unknown":
        return recorded ? "130-1T-filed" : "130-1T-exported";
      case "edit":
        return applied ? "130-1T-applied" : "130-1T-exported";
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
  const readForm = async (workUnitId: string, language: OutputLanguage) => {
    const name = await formName(workUnitId);
    const read = name === LATER_STATES ? laterState() : name;
    const form =
      read &&
      (await envelope<ModeloWorkbenchFormProjectionV1>(
        `modelo-${read}-${language}`,
      ));
    const admitted = form ? form.admitted_baseline?.baseline_id : undefined;
    if (read && admitted) admittedBy.set(admitted, read);
    if (!form) return reject("refused", { reason: "profile_mismatch" });
    return shape === "check-notes" && name === LATER_STATES
      ? withAssetNotes(form, language)
      : form;
  };
  /** The envelope `name` of a write the scenario answers, or unserved. */
  const written = async (name: string): Promise<unknown> =>
    (await envelope<unknown>(name)) ?? unserved();
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
      say(`modelo declarations ${language}`);
      await answer();
      const list = await envelope<ModeloDeclarationsListProjectionV1>(
        `declarations${shape === "incomplete" ? "-incomplete" : ""}-${language}`,
      );
      return list ?? reject("unavailable");
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
      const result = await (async (): Promise<unknown> => {
        switch (definition) {
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
            return shape === "filed" ? written("reconcile-130") : unserved();
          case "modelo.work.metadata":
            return receiptShape ? written("metadata-130-receipt") : unserved();
          case "modelo.work.amendment_context":
            return receiptShape ? written("amendment-context-130") : unserved();
          case "modelo.work.amend":
            if (shape === "correction-unknown")
              reject("unknown", { operation_id: nextOperation() });
            if (shape === "correction-refused")
              reject("refused", {
                operation_id: nextOperation(),
                reason: "operation_denied",
              });
            return shape === "receipt" ? written("amend-130") : unserved();
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
            ? /^[-+\d.,\s]+$/.test(correction.lexeme)
              ? `preflight-${form}-correction`
              : `preflight-${form}-correction-refused`
            : entries.length > 0
              ? `preflight-${form}-entry-${entries
                  .map((entry) =>
                    "casilla_id" in entry.address
                      ? entry.address.casilla_id
                      : entry.address.binding_id,
                  )
                  .join("-")}`
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
