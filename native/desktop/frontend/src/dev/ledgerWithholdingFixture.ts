// The scenario ledger's answers to the withholding operations: the payers'
// certificate records of an ejercicio and the statements that an income class
// has none, listed whether active or withdrawn. A record is judged as the registered contract judges it, a
// refusal settles with the operation's own result as its detail, and a row
// never holds the payer's tax identifier, which is dropped once it has named
// the payer's reference. Everything it answers is synthetic.

import served from "@fixtures/desktop-withholding-refusal-words/ledgerWithholdingRefusalWords.json" with { type: "json" };
import servedEntryOptions from "@fixtures/ledger-entry-options/ledgerEntryOptions.json" with { type: "json" };
import {
  WITHHOLDING_INCOME_CLASSES,
  WITHHOLDING_ORIGINS,
} from "../shell/ledgerContract";
import type {
  JsonObject,
  JsonValue,
  LedgerDefinitionId,
} from "../shell/ledger";

type Handler = (request: JsonObject) => JsonObject;

type Tools = {
  profileId: string;
  today: string;
  now: () => string;
  hex64: (text: string) => string;
  invalid: () => never;
  stop: (reason: string, detail: JsonObject) => never;
  /** Settles refused after part of the work was kept. */
  keptInPart: (reason: string, detail: JsonObject) => never;
  /** The file a token the window was given stands for. */
  fileOf: (token: JsonValue | undefined) => { name: string };
  /** The language the backend words a refusal in. */
  language: string;
};

/** What the made-up register cannot cause itself, which a scenario asks the
 * next certificate record to meet: a file that cannot be read once chosen,
 * a record refused after its file was kept, as a race would leave it, or a
 * refusal that arrives with no words served. */
export type CertificateFault = "unreadable" | "kept_in_part" | "wordless";
declare global {
  interface Window {
    __scenarioWithholding?: {
      nextRecords(faults: CertificateFault[]): void;
    };
  }
}

const WRITE_CODE = "REFUSED_RETENCION_SOPORTADA_WRITE";
const ABSENCE_CODE = "REFUSED_RETENCION_SOPORTADA_ABSENCE";
const REVISION_CODE = "REFUSED_RETENCION_SOPORTADA_REVISION_CONFLICT";
/** The figures a certificate states for each class, as `ledger.entry-options`
 * serves them, in the order served. */
const FIGURES_OF = (incomeClass: string): string[] =>
  (
    servedEntryOptions.families.find(
      (found) => found.family === "withholding_certificate_figure",
    )?.options ?? []
  )
    .filter((option) => "group" in option && option.group === incomeClass)
    .map((option) => option.value);
const DECIMAL = /^(0|[1-9]\d*)(\.\d+)?$/;
/** The sentences the backend serves with every refusal of the record and of
 * the absence operations, by reason and language, read from its own wording. */
type ServedWords = Record<
  string,
  Record<string, { refusal_words: string; refusal_words_language: string }>
>;
const RECORD_WORDS: ServedWords = served.record;
const ABSENCE_WORDS: ServedWords = served.absence;
/** The class the scenario serves a label for; the others are served bare. */
const LABELLED = {
  [WITHHOLDING_INCOME_CLASSES[0]]: "Employment income",
  [WITHHOLDING_INCOME_CLASSES[4]]: "Economic activity income",
};

type Stored = {
  ejercicio: number;
  income_class: string;
  payer_ref: string;
  payer_legal_name: string | null;
  figures: Record<string, string>;
  origin: string;
  evidence_fingerprint: string | null;
  revision: number;
};
type Attestation = {
  ejercicio: number;
  income_class: string;
  note: string;
  state: "active" | "withdrawn";
  attested_at: string;
  withdrawn_at: string | null;
  revision: number;
};

/** The withholding operations over a small synthetic register. */
export function withholdingOperations(tools: Tools) {
  const {
    profileId,
    today,
    now,
    hex64,
    invalid,
    stop,
    keptInPart,
    fileOf,
    language,
  } = tools;
  const faults: CertificateFault[] = [];
  window.__scenarioWithholding = {
    nextRecords: (next) => faults.push(...next),
  };
  /** The fingerprints of the bytes custody holds: the seeded certificate,
   * and each file a record has kept. */
  const custody = new Set<string>([hex64("certificate:employer")]);
  const fileDigest = (name: string) => hex64(`certificate-file:${name}`);
  const year = Number(today.slice(0, 4));
  const decimal = (value: string) => ({ decimal: value });
  const stored: Stored[] = [
    {
      ejercicio: year,
      income_class: WITHHOLDING_INCOME_CLASSES[0],
      payer_ref: hex64("payer:employer"),
      payer_legal_name: "Empresa Ejemplo SL",
      figures: {
        importe_integro_dinerario: "30000.00",
        valoracion_especie: "0",
        retencion: "4500.00",
        ingreso_a_cuenta: "0",
        ingreso_a_cuenta_repercutido: "0",
        reducciones_aplicables: "0",
        gastos_deducibles: "0",
      },
      origin: WITHHOLDING_ORIGINS[0],
      evidence_fingerprint: hex64("certificate:employer"),
      revision: 1,
    },
  ];
  // Two statements stand from the start: one active, one withdrawn since.
  const attestations: Attestation[] = [
    {
      ejercicio: year,
      income_class: WITHHOLDING_INCOME_CLASSES[4],
      note: "No professional fees were withheld.",
      state: "active",
      attested_at: `${year}-02-10T09:00:00Z`,
      withdrawn_at: null,
      revision: 2,
    },
    {
      ejercicio: year,
      income_class: WITHHOLDING_INCOME_CLASSES[1],
      note: "No dividends were paid.",
      state: "withdrawn",
      attested_at: `${year}-02-12T09:00:00Z`,
      withdrawn_at: `${year}-03-01T09:00:00Z`,
      revision: 3,
    },
  ];
  let revisions = 3;

  const revisionOf = (revision: number) => `rev-${revision}`;
  /** A payment figure every stored certificate states. */
  const paid = (found: Stored, name: string): string =>
    found.figures[name] ?? invalid();
  const rowOf = (found: Stored): JsonObject => {
    const label = (LABELLED as Record<string, string | undefined>)[
      found.income_class
    ];
    const pago = (
      Number(paid(found, "retencion")) + Number(paid(found, "ingreso_a_cuenta"))
    ).toFixed(2);
    return {
      ejercicio: found.ejercicio,
      income_class: found.income_class,
      ...(label ? { income_class_label: label } : {}),
      payer_ref: found.payer_ref,
      payer_legal_name: found.payer_legal_name,
      importe_integro_dinerario: decimal(
        paid(found, "importe_integro_dinerario"),
      ),
      valoracion_especie: decimal(paid(found, "valoracion_especie")),
      retencion: decimal(paid(found, "retencion")),
      ingreso_a_cuenta: decimal(paid(found, "ingreso_a_cuenta")),
      ingreso_a_cuenta_repercutido: decimal(
        paid(found, "ingreso_a_cuenta_repercutido"),
      ),
      pago_a_cuenta: decimal(pago),
      origin: found.origin,
      evidence_fingerprint: found.evidence_fingerprint,
      revision_id: revisionOf(found.revision),
    };
  };
  const attestationOf = (found: Attestation): JsonObject => ({
    ejercicio: found.ejercicio,
    income_class: found.income_class,
    note: found.note,
    state: found.state,
    attested_at: found.attested_at,
    withdrawn_at: found.withdrawn_at,
    revision_id: revisionOf(found.revision),
  });
  /** A listed attestation also words its income class, as the payers' rows
   * do where a label is served. */
  const attestationRowOf = (found: Attestation): JsonObject => {
    const label = (LABELLED as Record<string, string | undefined>)[
      found.income_class
    ];
    return {
      ...attestationOf(found),
      ...(label ? { income_class_label: label } : {}),
    };
  };

  const whole = (value: JsonValue | undefined): number =>
    typeof value === "number" && Number.isInteger(value) ? value : invalid();
  const text = (value: JsonValue | undefined): string | null =>
    typeof value === "string" && value !== "" ? value : null;
  const choice = (
    value: JsonValue | undefined,
    members: readonly string[],
  ): string => {
    const found = text(value);
    return found !== null && members.includes(found) ? found : invalid();
  };
  const figure = (value: JsonValue | undefined): string => {
    if (
      typeof value !== "object" ||
      value === null ||
      Array.isArray(value) ||
      typeof value.decimal !== "string" ||
      !DECIMAL.test(value.decimal)
    )
      return invalid();
    return value.decimal;
  };
  const only = (request: JsonObject, allowed: readonly string[]) => {
    if (Object.keys(request).some((key) => !allowed.includes(key))) invalid();
  };

  /** The sentence served for a reason, in the window's language. */
  const wordsOf = (words: ServedWords, reason: string) => {
    const found = words[reason];
    if (!found) throw new Error(`no refusal words are served for ${reason}`);
    return found[language] ?? found.en;
  };
  const certificateRefusal = (
    code: string,
    reason: string,
    ejercicio: number,
    withWords = true,
  ): never =>
    stop(code, {
      outcome: "refused",
      profile_id: profileId,
      ejercicio,
      row: null,
      count: null,
      refusal: {
        code,
        reason,
        ejercicio,
        ...(withWords ? wordsOf(RECORD_WORDS, reason) : {}),
      },
    });
  const keptInPartRefusal = (
    code: string,
    reason: string,
    ejercicio: number,
  ): never =>
    keptInPart(code, {
      outcome: "refused",
      profile_id: profileId,
      ejercicio,
      row: null,
      count: null,
      refusal: { code, reason, ejercicio, ...wordsOf(RECORD_WORDS, reason) },
    });
  const absenceRefusal = (
    code: string,
    reason: string,
    ejercicio: number,
    incomeClass: string,
  ): never =>
    stop(code, {
      outcome: "refused",
      profile_id: profileId,
      ejercicio,
      attestation: null,
      refusal: {
        code,
        reason,
        ejercicio,
        income_class: incomeClass,
        ...wordsOf(ABSENCE_WORDS, reason),
      },
    });
  const attestationFor = (ejercicio: number, incomeClass: string) =>
    attestations.find(
      (found) =>
        found.ejercicio === ejercicio && found.income_class === incomeClass,
    );

  const reads: Partial<Record<LedgerDefinitionId, Handler>> = {
    "ledger.retencion_soportada.list": (request) => {
      only(request, ["ejercicio"]);
      const ejercicio = whole(request.ejercicio);
      return {
        profile_id: profileId,
        ejercicio,
        rows: stored
          .filter((found) => found.ejercicio === ejercicio)
          .map(rowOf),
      };
    },
    "ledger.retencion_soportada.list_absences": (request) => {
      only(request, ["ejercicio"]);
      const ejercicio = whole(request.ejercicio);
      return {
        profile_id: profileId,
        ejercicio,
        attestations: attestations
          .filter((found) => found.ejercicio === ejercicio)
          .sort(
            (left, right) =>
              WITHHOLDING_INCOME_CLASSES.indexOf(
                left.income_class as (typeof WITHHOLDING_INCOME_CLASSES)[number],
              ) -
              WITHHOLDING_INCOME_CLASSES.indexOf(
                right.income_class as (typeof WITHHOLDING_INCOME_CLASSES)[number],
              ),
          )
          .map(attestationRowOf),
      };
    },
  };
  const writes: Partial<Record<LedgerDefinitionId, Handler>> = {
    "ledger.retencion_soportada.record": (request) => {
      only(request, [
        "ejercicio",
        "income_class",
        "payer_tax_id",
        "payer_legal_name",
        ...new Set(
          WITHHOLDING_INCOME_CLASSES.flatMap((name) => FIGURES_OF(name)),
        ),
        "origin",
        "evidence_fingerprint",
        "source_path",
        "expected_revision_id",
      ]);
      const ejercicio = whole(request.ejercicio);
      const incomeClass = choice(
        request.income_class,
        WITHHOLDING_INCOME_CLASSES,
      );
      const taxId = text(request.payer_tax_id);
      if (taxId === null || taxId.length > 32) return invalid();
      const origin = choice(request.origin, WITHHOLDING_ORIGINS);
      // A certificate states exactly the figures served for its class: one
      // sent that the class does not state is invalid, one it states and
      // that is left out is refused, a class-specific one in the served words.
      const stated = FIGURES_OF(incomeClass);
      const sentFigures = Object.keys(request).filter((name) =>
        WITHHOLDING_INCOME_CLASSES.some((other) =>
          FIGURES_OF(other).includes(name),
        ),
      );
      if (sentFigures.some((name) => !stated.includes(name))) return invalid();
      const left = stated.filter((name) => request[name] === undefined);
      if (left.length > 0) {
        const sharedByAll = (name: string) =>
          WITHHOLDING_INCOME_CLASSES.every((other) =>
            FIGURES_OF(other).includes(name),
          );
        if (left.some(sharedByAll)) return invalid();
        return certificateRefusal(
          WRITE_CODE,
          "trabajo_certificate_figure_missing",
          ejercicio,
        );
      }
      const figures: Stored["figures"] = Object.fromEntries(
        stated.map((name) => [name, figure(request[name])]),
      );
      const given = text(request.evidence_fingerprint);
      if (given !== null && !/^[0-9a-f]{64}$/.test(given)) return invalid();
      const picked = text(request.source_path);
      const file = picked === null ? null : fileOf(picked);
      const fault = faults.shift();
      // The file is read first, and a fingerprint given with it only
      // cross-checks the bytes read.
      if (fault === "wordless")
        return certificateRefusal(WRITE_CODE, "validation", ejercicio, false);
      if (file !== null) {
        if (fault === "unreadable")
          return certificateRefusal(
            WRITE_CODE,
            "certificate_file_unreadable",
            ejercicio,
          );
        if (given !== null && given !== fileDigest(file.name))
          return certificateRefusal(
            WRITE_CODE,
            "certificate_fingerprint_mismatch",
            ejercicio,
          );
      }
      const fingerprint = file === null ? given : fileDigest(file.name);
      if (origin === WITHHOLDING_ORIGINS[0] && fingerprint === null)
        return certificateRefusal(
          WRITE_CODE,
          "certificate_fingerprint_required",
          ejercicio,
        );
      if (
        Number(figures["ingreso_a_cuenta_repercutido"]) >
        Number(figures["ingreso_a_cuenta"])
      )
        return certificateRefusal(
          WRITE_CODE,
          "repercutido_exceeds_ingreso_a_cuenta",
          ejercicio,
        );
      // A fingerprint with no file names bytes custody must already hold.
      if (file === null && fingerprint !== null && !custody.has(fingerprint))
        return certificateRefusal(
          WRITE_CODE,
          "certificate_not_in_custody",
          ejercicio,
        );
      const payerRef = hex64(`payer:${taxId}`);
      if (
        stored.some(
          (found) =>
            found.ejercicio === ejercicio &&
            found.income_class === incomeClass &&
            found.payer_ref === payerRef,
        )
      )
        return certificateRefusal(REVISION_CODE, "stale_revision", ejercicio);
      if (file !== null) custody.add(fileDigest(file.name));
      // The file is kept, and the record is then refused: the register
      // changed between the checks and the write.
      if (fault === "kept_in_part")
        return keptInPartRefusal(REVISION_CODE, "stale_revision", ejercicio);
      revisions += 1;
      const row: Stored = {
        ejercicio,
        income_class: incomeClass,
        payer_ref: payerRef,
        payer_legal_name: text(request.payer_legal_name),
        figures,
        origin,
        evidence_fingerprint: fingerprint,
        revision: revisions,
      };
      stored.push(row);
      return {
        outcome: "recorded",
        profile_id: profileId,
        ejercicio,
        row: rowOf(row),
        count: stored.filter((found) => found.ejercicio === ejercicio).length,
        refusal: null,
      };
    },
    "ledger.retencion_soportada.remove": (request) => {
      only(request, [
        "ejercicio",
        "income_class",
        "payer_ref",
        "expected_revision_id",
      ]);
      const ejercicio = whole(request.ejercicio);
      const incomeClass = choice(
        request.income_class,
        WITHHOLDING_INCOME_CLASSES,
      );
      const payerRef = text(request.payer_ref) ?? invalid();
      const expected = text(request.expected_revision_id) ?? invalid();
      const found = stored.find(
        (other) =>
          other.ejercicio === ejercicio &&
          other.income_class === incomeClass &&
          other.payer_ref === payerRef,
      );
      if (!found) return certificateRefusal(WRITE_CODE, "not_found", ejercicio);
      if (revisionOf(found.revision) !== expected)
        return certificateRefusal(REVISION_CODE, "stale_revision", ejercicio);
      stored.splice(stored.indexOf(found), 1);
      return {
        outcome: "removed",
        profile_id: profileId,
        ejercicio,
        row: null,
        count: stored.filter((other) => other.ejercicio === ejercicio).length,
        refusal: null,
      };
    },
    "ledger.retencion_soportada.attest_absence": (request) => {
      only(request, [
        "ejercicio",
        "income_class",
        "note",
        "expected_revision_id",
      ]);
      const ejercicio = whole(request.ejercicio);
      const incomeClass = choice(
        request.income_class,
        WITHHOLDING_INCOME_CLASSES,
      );
      const note = text(request.note) ?? invalid();
      const expected = text(request.expected_revision_id);
      if (
        stored.some(
          (found) =>
            found.ejercicio === ejercicio && found.income_class === incomeClass,
        )
      )
        return absenceRefusal(
          ABSENCE_CODE,
          "records_present",
          ejercicio,
          incomeClass,
        );
      const prior = attestationFor(ejercicio, incomeClass);
      if (prior?.state === "active")
        return absenceRefusal(
          ABSENCE_CODE,
          "already_attested",
          ejercicio,
          incomeClass,
        );
      if (prior && expected !== revisionOf(prior.revision))
        return absenceRefusal(
          REVISION_CODE,
          "stale_revision",
          ejercicio,
          incomeClass,
        );
      revisions += 1;
      const next: Attestation = {
        ejercicio,
        income_class: incomeClass,
        note,
        state: "active",
        attested_at: now(),
        withdrawn_at: null,
        revision: revisions,
      };
      if (prior) attestations.splice(attestations.indexOf(prior), 1, next);
      else attestations.push(next);
      return {
        outcome: "attested",
        profile_id: profileId,
        ejercicio,
        attestation: attestationOf(next),
        refusal: null,
      };
    },
    "ledger.retencion_soportada.withdraw_absence": (request) => {
      only(request, ["ejercicio", "income_class", "expected_revision_id"]);
      const ejercicio = whole(request.ejercicio);
      const incomeClass = choice(
        request.income_class,
        WITHHOLDING_INCOME_CLASSES,
      );
      const expected = text(request.expected_revision_id) ?? invalid();
      const prior = attestationFor(ejercicio, incomeClass);
      if (!prior || prior.state !== "active")
        return absenceRefusal(
          ABSENCE_CODE,
          "not_attested",
          ejercicio,
          incomeClass,
        );
      if (revisionOf(prior.revision) !== expected)
        return absenceRefusal(
          REVISION_CODE,
          "stale_revision",
          ejercicio,
          incomeClass,
        );
      revisions += 1;
      prior.state = "withdrawn";
      prior.withdrawn_at = now();
      prior.revision = revisions;
      return {
        outcome: "withdrawn",
        profile_id: profileId,
        ejercicio,
        attestation: attestationOf(prior),
        refusal: null,
      };
    },
  };
  return { reads, writes };
}
