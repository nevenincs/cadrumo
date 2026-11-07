// The scenario ledger's prorrata register and capital goods register: the
// elections, sectors and gross declarations the register holds, and the
// capital goods declared against it. Everything it answers is synthetic.

import type { JsonObject, LedgerDefinitionId } from "../shell/ledger";
import { SCENARIO_TODAY } from "./assetsRegister";
import {
  SetupStopped,
  decimal,
  decimalOf,
  fromKeys,
  invalid,
  required,
  servedOptions,
  servedRefusal,
  text,
  whole,
  type Handler,
  type Tools,
} from "./ledgerSetupSupport";
import {
  servedMinimumAcquisitionYear,
  servedYearBounds,
} from "./servedYearAuthority";

/** The year the scenario stands in, and the earlier years the registers hold
 * entries for. */
const SCENARIO_YEAR = Number(SCENARIO_TODAY.slice(0, 4));
const PRIOR_YEAR = SCENARIO_YEAR - 1;
const ACQUISITION_YEAR = SCENARIO_YEAR - 2;

const PROVENANCES = ["aeat_autorizada", "inicio_actividad"];
const CARRIED = "carried_prior_definitiva";
const SECTOR_LETTERS = servedOptions("prorrata_sector_letter").map(
  (option) => option.value,
);
const CAPITAL_KINDS = ["mueble", "inmueble"];
const DISPOSAL_REGIMES = ["sujeta_no_exenta", "exenta_o_no_sujeta"];

type Prorrata = {
  ejercicio: number;
  regime: "general" | "especial";
  sector_id: string | null;
  provisional: string | null;
  provenance: string | null;
  reference: string | null;
  transition: { kind: string; evidence_reference: string } | null;
  definitive: string | null;
  con: string | null;
  sin: string | null;
};
type GrossDeclaration = {
  ejercicio: number;
  period: string;
  sector_id: string | null;
  gross: string;
  evidence: string;
  declared_at: string;
};

/** The scenario ledger's prorrata and capital goods answers. */
export function prorrataOperations(tools: Tools) {
  const { profileId, hex64, now } = tools;
  const served = servedRefusal(tools.language);
  const prorrata: Prorrata[] = [
    {
      ejercicio: PRIOR_YEAR,
      regime: "general",
      sector_id: null,
      provisional: "90",
      provenance: "inicio_actividad",
      reference: "REF-2025-0042",
      transition: null,
      definitive: "92",
      con: "48200",
      sin: "4190",
    },
  ];
  const sectors: { sector_id: string; letra: string; codes: string[] }[] = [];
  const grossDeclarations: GrossDeclaration[] = [
    {
      ejercicio: SCENARIO_YEAR,
      period: "1T",
      sector_id: null,
      gross: "1234.56",
      evidence: "LIQ-2026-1T",
      declared_at: "2026-02-10T09:00:00Z",
    },
  ];
  const capital: JsonObject[] = [
    {
      identifier: "BI-2024-01",
      description: "Plotter de gran formato",
      acquisition_year: ACQUISITION_YEAR,
      cuota_soportada: decimal("714"),
      prorrata_inicial_pct: decimal("92"),
      kind: "mueble",
      art108_elegible: true,
      acquisition_ledger_id: hex64("capital:plotter"),
      prorrata_sector_id: null,
      disposal: null,
      deduccion_efectuada: decimal("656.88"),
      schema_version: "1",
    },
  ];

  // ---- Prorrata ------------------------------------------------------------

  const entryOf = (found: Prorrata): JsonObject => ({
    ejercicio: found.ejercicio,
    regime: found.regime,
    especial_transition: found.transition,
    sector_id: found.sector_id,
    interrupted: false,
    provisional_percentage: found.provisional
      ? decimal(found.provisional)
      : null,
    provisional_provenance: found.provenance,
    authorisation_reference: found.reference,
    definitive_percentage: found.definitive ? decimal(found.definitive) : null,
    definitive_volume_con_derecho: found.con ? decimal(found.con) : null,
    definitive_volume_sin_derecho: found.sin ? decimal(found.sin) : null,
    source_observation_ref: null,
    source_registry_snapshot_refs: [],
    schema_version: "1",
  });
  const sectorOf = (found: (typeof sectors)[number]): JsonObject => ({
    sector_id: found.sector_id,
    letra: found.letra,
    member_activity_codes: found.codes,
  });
  const grossOf = (found: GrossDeclaration): JsonObject => ({
    ejercicio: found.ejercicio,
    period: found.period,
    sector_id: found.sector_id,
    gross_cuota: decimal(found.gross),
    evidence_reference: found.evidence,
    provenance: "operator_declared",
    declared_at: found.declared_at,
  });
  const prorrataResult = (
    operation: string,
    extra: JsonObject = {},
  ): JsonObject => ({
    operation_id: operation,
    profile_id: profileId,
    outcome: "success",
    entry: null,
    sector_definition: null,
    gross_declaration: null,
    seed_source: null,
    findings: [],
    prior_ejercicio: null,
    count: prorrata.length,
    refusal: null,
    ...extra,
  });
  const prorrataRefusal = (
    operation: string,
    code: string,
    reason: string,
    detail: string,
    extra: JsonObject = {},
  ): never => {
    throw new SetupStopped(code, {
      ...prorrataResult(operation),
      outcome: "refused",
      count: null,
      refusal: {
        code,
        reason,
        detail,
        ejercicio: null,
        sector_id: null,
        findings: [],
        accepted_provenances: [],
        existing_provenance: null,
        ...extra,
        ...served("prorrata", reason),
      },
    });
  };
  const VALIDATION = "REFUSED_PROFILE_PRORRATA_REGISTER_VALIDATION";
  const findEntry = (ejercicio: number, sector: string | null) =>
    prorrata.find(
      (found) => found.ejercicio === ejercicio && found.sector_id === sector,
    );
  const sectorKnown = (sector: string | null) =>
    sector === null || sectors.some((found) => found.sector_id === sector);

  function elect(operation: string, request: JsonObject): JsonObject {
    const ejercicio = whole(request.ejercicio);
    const percentage = decimalOf(request.percentage);
    if (Number(percentage) > 100) invalid();
    const provenance = text(request.provenance);
    const reference = text(request.reference);
    const sector = text(request.sector_id);
    const evidence = text(request.evidence_reference);
    if (operation === "revoke_especial" && !evidence) invalid();
    if (!sectorKnown(sector))
      return prorrataRefusal(
        operation,
        VALIDATION,
        "validation",
        "Unknown sector.",
        {
          ejercicio,
          sector_id: sector,
        },
      );
    if (provenance === null || provenance === CARRIED)
      return prorrataRefusal(
        operation,
        "REFUSED_PRORRATA_ELECTION",
        "provenance_required",
        provenance === CARRIED
          ? "A carried prior definitive is seeded, not elected."
          : "An election names where its percentage comes from.",
        { ejercicio, accepted_provenances: PROVENANCES },
      );
    if (!PROVENANCES.includes(provenance))
      return prorrataRefusal(
        operation,
        "REFUSED_PRORRATA_ELECTION",
        "provenance_not_electable",
        "That provenance is computed, not declared.",
        { ejercicio, accepted_provenances: PROVENANCES },
      );
    if (!reference)
      return prorrataRefusal(
        operation,
        "REFUSED_PRORRATA_ELECTION",
        "reference_required",
        "This provenance stands on a document: name its reference.",
        { ejercicio },
      );
    const existing = findEntry(ejercicio, sector);
    if (operation === "revoke_especial" && existing?.regime !== "especial")
      return prorrataRefusal(
        operation,
        VALIDATION,
        "validation",
        "The ejercicio is not in prorrata especial.",
        { ejercicio, sector_id: sector },
      );
    const entry: Prorrata = {
      ejercicio,
      regime: operation === "elect_especial" ? "especial" : "general",
      sector_id: sector,
      provisional: percentage,
      provenance,
      reference,
      transition:
        operation === "elect_especial"
          ? evidence
            ? { kind: "opcion", evidence_reference: evidence }
            : null
          : operation === "revoke_especial"
            ? { kind: "revocacion", evidence_reference: evidence! }
            : null,
      definitive: existing?.definitive ?? null,
      con: existing?.con ?? null,
      sin: existing?.sin ?? null,
    };
    if (existing) prorrata.splice(prorrata.indexOf(existing), 1, entry);
    else prorrata.push(entry);
    return prorrataResult(operation, { entry: entryOf(entry) });
  }

  const findGross = (
    ejercicio: number,
    period: string,
    sector: string | null,
  ) =>
    grossDeclarations.find(
      (found) =>
        found.ejercicio === ejercicio &&
        found.period === period &&
        found.sector_id === sector,
    );

  const prorrataWrites: Record<string, Handler> = {
    "ledger.prorrata.seed": (request) => {
      fromKeys(request, ["ejercicio"]);
      const ejercicio = whole(request.ejercicio);
      const prior = findEntry(ejercicio - 1, null);
      if (!prior?.definitive)
        return prorrataRefusal(
          "seed",
          "REFUSED_PROFILE_PRORRATA_WHOLE_SEED",
          "seed_source_absent",
          `No definitive percentage for ${ejercicio - 1} to seed from.`,
          { ejercicio },
        );
      if (findEntry(ejercicio, null))
        return prorrataRefusal(
          "seed",
          "REFUSED_PROFILE_PRORRATA_WHOLE_SEED",
          "seed_existing_blocked",
          `${ejercicio} already has an entry.`,
          { ejercicio },
        );
      const entry: Prorrata = {
        ejercicio,
        regime: prior.regime,
        sector_id: null,
        provisional: prior.definitive,
        provenance: CARRIED,
        reference: null,
        transition: null,
        definitive: null,
        con: null,
        sin: null,
      };
      prorrata.push(entry);
      return prorrataResult("seed", {
        entry: entryOf(entry),
        prior_ejercicio: ejercicio - 1,
        seed_source: {
          modelo: "390",
          filing_year: ejercicio - 1,
          period: "0A",
          casilla_id: "108",
          stamped_revision_id: hex64(`m390:${ejercicio - 1}`),
          authority: "local_prior_observation",
        },
      });
    },
    "ledger.prorrata.declare_sector": (request) => {
      fromKeys(request, ["sector_id", "letra", "member_activity_codes"]);
      const sector = required(request.sector_id);
      const letra = required(request.letra);
      const codes = request.member_activity_codes ?? [];
      if (
        !Array.isArray(codes) ||
        codes.some((code) => typeof code !== "string")
      )
        return invalid();
      if (!SECTOR_LETTERS.includes(letra))
        return prorrataRefusal(
          "declare_sector",
          VALIDATION,
          "validation",
          "Not a differentiated-sector letter.",
          { sector_id: sector },
        );
      const declared = { sector_id: sector, letra, codes: codes as string[] };
      const at = sectors.findIndex((found) => found.sector_id === sector);
      if (at >= 0) sectors.splice(at, 1, declared);
      else sectors.push(declared);
      return prorrataResult("declare_sector", {
        sector_definition: sectorOf(declared),
      });
    },
    "ledger.prorrata.elect_general": (request) => {
      fromKeys(request, [
        "ejercicio",
        "percentage",
        "provenance",
        "reference",
        "sector_id",
      ]);
      return elect("elect_general", request);
    },
    "ledger.prorrata.elect_especial": (request) => {
      fromKeys(request, [
        "ejercicio",
        "percentage",
        "provenance",
        "reference",
        "sector_id",
        "evidence_reference",
      ]);
      return elect("elect_especial", request);
    },
    "ledger.prorrata.revoke_especial": (request) => {
      fromKeys(request, [
        "ejercicio",
        "percentage",
        "provenance",
        "reference",
        "sector_id",
        "evidence_reference",
      ]);
      return elect("revoke_especial", request);
    },
    "ledger.prorrata.declare_gross": (request) => {
      fromKeys(request, [
        "ejercicio",
        "period",
        "sector_id",
        "gross_cuota",
        "evidence_reference",
        "replace",
      ]);
      const ejercicio = whole(request.ejercicio);
      const period = required(request.period);
      const sector = text(request.sector_id);
      const gross = decimalOf(request.gross_cuota);
      const evidence = required(request.evidence_reference);
      if (request.replace !== undefined && typeof request.replace !== "boolean")
        return invalid();
      if (!sectorKnown(sector))
        return prorrataRefusal(
          "declare_gross",
          VALIDATION,
          "gross_declaration_sector_unknown",
          `Sector ${sector} is not a declared differentiated sector.`,
          { ejercicio, sector_id: sector },
        );
      const existing = findGross(ejercicio, period, sector);
      if (existing && request.replace !== true)
        return prorrataRefusal(
          "declare_gross",
          VALIDATION,
          "gross_declaration_duplicate",
          `A gross declaration already exists for ${period}.`,
          { ejercicio, sector_id: sector },
        );
      const declared: GrossDeclaration = {
        ejercicio,
        period,
        sector_id: sector,
        gross,
        evidence,
        declared_at: now(),
      };
      if (existing)
        grossDeclarations.splice(
          grossDeclarations.indexOf(existing),
          1,
          declared,
        );
      else grossDeclarations.push(declared);
      return prorrataResult("declare_gross", {
        gross_declaration: grossOf(declared),
        count: grossDeclarations.length,
      });
    },
    "ledger.prorrata.remove_gross": (request) => {
      fromKeys(request, ["ejercicio", "period", "sector_id"]);
      const ejercicio = whole(request.ejercicio);
      const period = required(request.period);
      const sector = text(request.sector_id);
      const existing = findGross(ejercicio, period, sector);
      if (!existing)
        return prorrataRefusal(
          "remove_gross",
          VALIDATION,
          "gross_declaration_absent",
          `No gross declaration exists for ${period}.`,
          { ejercicio, sector_id: sector },
        );
      grossDeclarations.splice(grossDeclarations.indexOf(existing), 1);
      return prorrataResult("remove_gross", {
        gross_declaration: grossOf(existing),
        count: grossDeclarations.length,
      });
    },
    "ledger.prorrata.seed_sector": (request) => {
      fromKeys(request, ["ejercicio", "sector_id"]);
      const ejercicio = whole(request.ejercicio);
      const sector = required(request.sector_id);
      const prior = findEntry(ejercicio - 1, sector);
      if (!sectorKnown(sector) || !prior?.definitive)
        return prorrataRefusal(
          "seed_sector",
          "REFUSED_PROFILE_PRORRATA_SECTOR_LIFECYCLE",
          "sector_prior_definitive_absent",
          `Sector ${sector} has no ${ejercicio - 1} definitive.`,
          { ejercicio, sector_id: sector },
        );
      const entry: Prorrata = {
        ...prior,
        ejercicio,
        provisional: prior.definitive,
        provenance: CARRIED,
        reference: null,
        transition: null,
        definitive: null,
        con: null,
        sin: null,
      };
      prorrata.push(entry);
      return prorrataResult("seed_sector", { entry: entryOf(entry) });
    },
    "ledger.prorrata.settle_sector": (request) => {
      fromKeys(request, [
        "ejercicio",
        "sector_id",
        "con_derecho_volume",
        "sin_derecho_volume",
      ]);
      const ejercicio = whole(request.ejercicio);
      const sector = required(request.sector_id);
      const con = decimalOf(request.con_derecho_volume);
      const sin = decimalOf(request.sin_derecho_volume);
      const entry = findEntry(ejercicio, sector);
      if (!entry)
        return prorrataRefusal(
          "settle_sector",
          "REFUSED_PROFILE_PRORRATA_SECTOR_LIFECYCLE",
          "sector_settlement_entry_absent",
          `Sector ${sector} has no ${ejercicio} entry to settle.`,
          { ejercicio, sector_id: sector },
        );
      const total = Number(con) + Number(sin);
      entry.con = con;
      entry.sin = sin;
      // LIVA art. 104.Dos: rounded up to the next whole unit.
      entry.definitive = String(
        total === 0 ? 0 : Math.ceil((Number(con) / total) * 100),
      );
      return prorrataResult("settle_sector", { entry: entryOf(entry) });
    },
  };

  // ---- Capital goods -------------------------------------------------------

  function declareCapital(request: JsonObject): JsonObject {
    fromKeys(request, [
      "identifier",
      "description",
      "acquisition_year",
      "acquisition_ledger_id",
      "cuota_soportada",
      "prorrata_inicial_pct",
      "kind",
      "art108_elegible",
      "prorrata_sector_id",
      "disposal_year",
      "disposal_regime",
    ]);
    const identifier = required(request.identifier);
    const year = whole(request.acquisition_year);
    if (year < servedMinimumAcquisitionYear || year > servedYearBounds.last)
      invalid();
    const cuota = decimalOf(request.cuota_soportada);
    const pct = decimalOf(request.prorrata_inicial_pct);
    const kind = required(request.kind);
    const refuse = (reason: string, extra: JsonObject = {}): never => {
      throw new SetupStopped("REFUSED_PROFILE_BIENES_INVERSION_VALIDATION", {
        outcome: "refused",
        profile_id: profileId,
        record: null,
        count: null,
        refusal: {
          code: "REFUSED_PROFILE_BIENES_INVERSION_VALIDATION",
          reason,
          missing: null,
          identifier,
          ...extra,
          ...served(
            "capital_goods",
            reason === "disposal_incomplete"
              ? `${reason}.${String(extra.missing)}`
              : reason,
            { identifier },
          ),
        },
      });
    };
    if (!CAPITAL_KINDS.includes(kind) || Number(pct) > 100)
      return refuse("validation");
    const disposalYear = request.disposal_year ?? null;
    const disposalRegime = text(request.disposal_regime);
    if ((disposalYear === null) !== (disposalRegime === null))
      return refuse("disposal_incomplete", {
        missing: disposalYear === null ? "year" : "regime",
      });
    if (disposalRegime !== null && !DISPOSAL_REGIMES.includes(disposalRegime))
      return refuse("validation");
    if (capital.some((found) => found.identifier === identifier))
      return refuse("duplicate_identifier");
    const record: JsonObject = {
      identifier,
      description: required(request.description),
      acquisition_year: year,
      cuota_soportada: decimal(cuota),
      prorrata_inicial_pct: decimal(pct),
      kind,
      art108_elegible: request.art108_elegible !== false,
      acquisition_ledger_id: required(request.acquisition_ledger_id),
      prorrata_sector_id: text(request.prorrata_sector_id),
      disposal:
        disposalYear === null
          ? null
          : { year: whole(disposalYear), regime: disposalRegime },
      deduccion_efectuada: decimal(
        ((Number(cuota) * Number(pct)) / 100).toFixed(2).replace(/\.?0+$/, ""),
      ),
      schema_version: "1",
    };
    capital.push(record);
    return {
      outcome: "declared",
      profile_id: profileId,
      record,
      count: capital.length,
      refusal: null,
    };
  }

  const reads: Partial<Record<LedgerDefinitionId, Handler>> = {
    "ledger.prorrata.list": (request) => {
      fromKeys(request, []);
      return {
        profile_id: profileId,
        entries: [...prorrata]
          .sort((a, b) => b.ejercicio - a.ejercicio)
          .map((found) => {
            const kind = found.definitive ? "definitiva" : "provisional";
            const sector = found.sector_id ? `:${found.sector_id}` : "";
            return {
              ...entryOf(found),
              reference_id: `prorrata:${found.ejercicio}:${kind}:${found.regime}${sector}`,
              reference_kind: kind,
            };
          }),
        sectors: sectors.map(sectorOf),
        gross_declarations: grossDeclarations.map(grossOf),
        count: prorrata.length,
      };
    },
    "ledger.bienes_inversion.list": (request) => {
      fromKeys(request, []);
      return { profile_id: profileId, rows: capital };
    },
  };
  const writes: Partial<Record<LedgerDefinitionId, Handler>> = {
    ...prorrataWrites,
    "ledger.bienes_inversion.declare": declareCapital,
  };

  return { reads, writes };
}
