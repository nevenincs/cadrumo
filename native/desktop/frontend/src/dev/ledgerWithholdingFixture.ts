// The scenario ledger's answers to the withholding operations: the payers'
// certificate records of an ejercicio and the statements that an income class
// has none. A record is judged as the registered contract judges it, a
// refusal settles with the operation's own result as its detail, and a row
// never holds the payer's tax identifier, which is dropped once it has named
// the payer's reference. Everything it answers is synthetic.

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
};

const WRITE_CODE = "REFUSED_RETENCION_SOPORTADA_WRITE";
const ABSENCE_CODE = "REFUSED_RETENCION_SOPORTADA_ABSENCE";
const REVISION_CODE = "REFUSED_RETENCION_SOPORTADA_REVISION_CONFLICT";
const AMOUNTS = [
  "importe_integro_dinerario",
  "valoracion_especie",
  "retencion",
  "ingreso_a_cuenta",
  "ingreso_a_cuenta_repercutido",
] as const;
const DECIMAL = /^(0|[1-9]\d*)(\.\d+)?$/;
/** Words the backend serves with a refusal, which the window shows as served. */
const SERVED_WORDS: Record<string, string> = {
  repercutido_exceeds_ingreso_a_cuenta:
    "The payment on account passed on to you cannot be more than the payment on account.",
};
/** The class the scenario serves a label for; the others are served bare. */
const LABELLED = { [WITHHOLDING_INCOME_CLASSES[0]]: "Employment income" };

type Stored = {
  ejercicio: number;
  income_class: string;
  payer_ref: string;
  payer_legal_name: string | null;
  figures: Record<(typeof AMOUNTS)[number], string>;
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
  const { profileId, today, now, hex64, invalid, stop } = tools;
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
      },
      origin: WITHHOLDING_ORIGINS[0],
      evidence_fingerprint: hex64("certificate:employer"),
      revision: 1,
    },
  ];
  const attestations: Attestation[] = [];
  let revisions = 1;

  const revisionOf = (revision: number) => `rev-${revision}`;
  const rowOf = (found: Stored): JsonObject => {
    const label = (LABELLED as Record<string, string | undefined>)[
      found.income_class
    ];
    const pago = (
      Number(found.figures.retencion) + Number(found.figures.ingreso_a_cuenta)
    ).toFixed(2);
    return {
      ejercicio: found.ejercicio,
      income_class: found.income_class,
      ...(label ? { income_class_label: label } : {}),
      payer_ref: found.payer_ref,
      payer_legal_name: found.payer_legal_name,
      importe_integro_dinerario: decimal(
        found.figures.importe_integro_dinerario,
      ),
      valoracion_especie: decimal(found.figures.valoracion_especie),
      retencion: decimal(found.figures.retencion),
      ingreso_a_cuenta: decimal(found.figures.ingreso_a_cuenta),
      ingreso_a_cuenta_repercutido: decimal(
        found.figures.ingreso_a_cuenta_repercutido,
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

  const certificateRefusal = (
    code: string,
    reason: string,
    ejercicio: number,
  ): never =>
    stop(code, {
      outcome: "refused",
      profile_id: profileId,
      ejercicio,
      row: null,
      count: null,
      refusal: { code, reason, ejercicio },
      ...(SERVED_WORDS[reason] ? { refusal_words: SERVED_WORDS[reason] } : {}),
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
      refusal: { code, reason, ejercicio, income_class: incomeClass },
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
  };
  const writes: Partial<Record<LedgerDefinitionId, Handler>> = {
    "ledger.retencion_soportada.record": (request) => {
      only(request, [
        "ejercicio",
        "income_class",
        "payer_tax_id",
        "payer_legal_name",
        ...AMOUNTS,
        "origin",
        "evidence_fingerprint",
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
      const figures = Object.fromEntries(
        AMOUNTS.map((name) => [name, figure(request[name])]),
      ) as Stored["figures"];
      const fingerprint = text(request.evidence_fingerprint);
      if (fingerprint !== null && !/^[0-9a-f]{64}$/.test(fingerprint))
        return invalid();
      if (origin === WITHHOLDING_ORIGINS[0] && fingerprint === null)
        return certificateRefusal(
          WRITE_CODE,
          "certificate_fingerprint_required",
          ejercicio,
        );
      if (
        Number(figures.ingreso_a_cuenta_repercutido) >
        Number(figures.ingreso_a_cuenta)
      )
        return certificateRefusal(
          WRITE_CODE,
          "repercutido_exceeds_ingreso_a_cuenta",
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
