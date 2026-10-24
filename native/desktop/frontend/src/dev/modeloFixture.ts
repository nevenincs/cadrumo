// The scenario host's modelo family: the modelo port answered from the
// envelopes in ./fixtures/modelo/, which scripts/modelo-fixtures.mjs reads
// through the application's own read path for a synthetic taxpayer. The
// declarations list, each declaration's form, the help cards and one edit
// preflight answer exactly what the application answered, in each of the
// four languages, and the first quarter's Modelo 130 is also read after its
// check, recorded as filed locally with and without a verified receipt, and
// with its file for the AEAT out of date; an edit renewal
// answers the baseline the form admitted. Every other definition has no
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
  MODELO_EDIT_BODY_LIMIT,
  isModeloDefinition,
  needsWorkUnit,
  type ModeloFilePurpose,
  type ModeloPort,
  type ModeloResult,
  type ModeloSaveFormat,
} from "../shell/modelo";
import type {
  ModeloCasillaHelpProjectionV1,
  ModeloDeclarationsListProjectionV1,
  ModeloEditOperatorInputV2,
  ModeloEditPreflightProjectionV1,
  ModeloEditRenewalProjectionV1,
  ModeloWorkbenchFormProjectionV1,
  OutputLanguage,
} from "../shell/modeloContract";
import { hex64 } from "./fixtures/ledger";

/** How the scenario's modelo family answers. `checked`, `filed`, `receipt`
 * and `stale` answer as `fixture` does, except that the first quarter's
 * Modelo 130 is read after its check, after it was recorded as filed
 * locally, after its AEAT receipt was verified, or after the declaration
 * changed once its file for the AEAT was made. `incomplete` lists the
 * declarations of a profile nothing was ever read from the AEAT for. */
export const MODELO_SHAPES = [
  "fixture",
  "checked",
  "filed",
  "receipt",
  "stale",
  "incomplete",
  "refused",
  "unknown",
  "unavailable",
  "slow",
] as const;
export type ModeloShape = (typeof MODELO_SHAPES)[number];

/** The declaration whose later states the `checked` and `filed` shapes read. */
const LATER_STATES = "130-1T";

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

  const state =
    shape === "checked" ||
    shape === "filed" ||
    shape === "receipt" ||
    shape === "stale"
      ? shape
      : null;
  const readForm = async (workUnitId: string, language: OutputLanguage) => {
    const name = await formName(workUnitId);
    const later = state && name === LATER_STATES ? `-${state}` : "";
    const form =
      name &&
      (await envelope<ModeloWorkbenchFormProjectionV1>(
        `modelo-${name}${later}-${language}`,
      ));
    return form || reject("refused", { reason: "profile_mismatch" });
  };
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
            const baseline = request.baseline as {
              work_unit_id?: unknown;
            } | null;
            const form = await readForm(String(baseline?.work_unit_id), "en");
            if (!form.admitted_baseline) return unserved();
            const renewal: ModeloEditRenewalProjectionV1 = {
              result_version: 1,
              profile_id: form.profile_id,
              work_unit_id: form.work_unit_id,
              renewed_baseline: form.admitted_baseline,
              refusal: null,
              refusal_words: null,
            };
            return renewal;
          }
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
        if (body.byteLength > MODELO_EDIT_BODY_LIMIT) reject("invalid");
        let input: ModeloEditOperatorInputV2;
        try {
          input = JSON.parse(
            new TextDecoder().decode(body),
          ) as ModeloEditOperatorInputV2;
        } catch {
          return reject("invalid");
        }
        const workUnitId = input.submission?.baseline?.work_unit_id;
        if (definition === "modelo.edit.preflight") {
          const name = workUnitId ? await formName(workUnitId) : null;
          const preflight =
            name &&
            (await envelope<ModeloEditPreflightProjectionV1>(
              `preflight-${name.split("-")[0]}`,
            ));
          if (preflight)
            return settle(preflight) as LedgerOutcome<
              ModeloResult<typeof definition>
            >;
        }
        return unserved();
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
