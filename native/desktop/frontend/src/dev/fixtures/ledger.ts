// A made-up 2026 ledger of a Spanish autónomo, a graphic design studio, for
// designing the Ledger page. Every name, number and NIF-shaped value is
// invented: the studio, its clients, its suppliers and its accounts. The
// ledger is generated from a fixed seed, so every run sees the same rows.

import type {
  CatalogueInvoice,
  LedgerTransaction,
  PublicDecimal,
} from "../../shell/ledger";
import { exampleInvoices } from "./ledgerInvoices";

/** The profile the fixture ledger belongs to: the profile fixture's own. */
export const LEDGER_FIXTURE_PROFILE_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
/** The fixture's today: movements reach up to this day. */
export const LEDGER_FIXTURE_TODAY = "2026-10-23";
/** The quarter a finalized Modelo 303 revision cites: its rows are sealed. */
export const SEALED_PERIOD = { filing_year: 2026, code: "1T" } as const;

/** One movement, with the facts the product keeps beside its projection. */
export type FixtureMovement = {
  transaction: LedgerTransaction;
  group_label: string | null;
  own_account_id: string | null;
  import_batch_id: string | null;
  issue: "original-file" | "gap" | "duplicate" | "parser" | null;
  /** Cited by a finalized revision: writes that change it are refused. */
  sealed: boolean;
  /** The person rejected a model's proposal for it. */
  llm_rejected: boolean;
  /** The idempotency key a manual add carried, if any. */
  idempotency_key: string | null;
};
export type FixtureEvidence = {
  evidence_id: string;
  bucket_id: string;
  source_sha256: string;
  attachment_id: string;
  media_kind: "pdf" | "image";
  supplier: string | null;
  invoice_number: string | null;
  invoice_date: string | null;
  taxable_base: string | null;
  iva_rate: string | null;
  iva_amount: string | null;
  notes: string;
  created_at: string;
  updated_at: string;
  source_path: string;
};
export type FixtureRule = {
  rule_id: string;
  description_pattern: string;
  classification: string;
  category_id: string | null;
  priority: number;
  actor: string;
  created_at: string;
};
export type FixtureAccount = {
  own_account_id: string;
  label: string;
  holding: "titular" | "cotitular";
  masked_iban: string;
  country_code: string;
  sepa_marca: string;
  has_swift_bic: boolean;
  has_bank_block: boolean;
  currency: string;
  opened_on: string | null;
  closed_on: string | null;
};
export type FixtureLedger = {
  movements: FixtureMovement[];
  invoices: CatalogueInvoice[];
  evidence: FixtureEvidence[];
  rules: FixtureRule[];
  accounts: FixtureAccount[];
};

/** A deterministic 64-hex-digit name for `text`, shaped like the product's
 * content-addressed ids. */
export function hex64(text: string): string {
  let out = "";
  for (let round = 0; round < 8; round += 1) {
    let hash = 0x811c9dc5 ^ Math.imul(round + 1, 0x9e3779b1);
    for (let at = 0; at < text.length; at += 1) {
      hash ^= text.charCodeAt(at);
      hash = Math.imul(hash, 0x01000193);
    }
    out += (hash >>> 0).toString(16).padStart(8, "0");
  }
  return out;
}

/** The id a movement's identifying facts give it. Changing its amount,
 * description, date or own account gives it a new one. */
export function movementId(facts: {
  date: string;
  amount: string;
  description: string;
  own_account_id: string | null;
  salt: string;
}): string {
  return hex64(
    [
      facts.date,
      facts.amount,
      facts.description,
      facts.own_account_id ?? "",
      facts.salt,
    ].join("␟"),
  );
}

export const cents = (value: string) => Math.round(Number(value) * 100);
export const money = (amountCents: number) => (amountCents / 100).toFixed(2);
const decimal = (amountCents: number): PublicDecimal => ({
  decimal: money(amountCents),
});

// A small seeded generator, so the fixture is the same on every run.
function generator(seed: number) {
  let state = seed >>> 0;
  const next = () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let value = state;
    value = Math.imul(value ^ (value >>> 15), value | 1);
    value ^= value + Math.imul(value ^ (value >>> 7), value | 61);
    return ((value ^ (value >>> 14)) >>> 0) / 4294967296;
  };
  return {
    next,
    between: (low: number, high: number) =>
      low + Math.floor(next() * (high - low + 1)),
    pick: <T>(items: readonly T[]): T =>
      items[Math.floor(next() * items.length)]!,
  };
}

const day = (month: number, date: number) =>
  `2026-${String(month).padStart(2, "0")}-${String(date).padStart(2, "0")}`;
const daysIn = (month: number) =>
  new Date(Date.UTC(2026, month, 0)).getUTCDate();
const stamp = (date: string, minutes: number) =>
  `${date}T${String(8 + Math.floor(minutes / 60)).padStart(2, "0")}:${String(minutes % 60).padStart(2, "0")}:00Z`;

type Kind = {
  description: string;
  counterparty: string;
  direction: "INCOMING" | "OUTGOING" | "INTERNAL_TRANSFER";
  classification: string;
  category: string | null;
  iva: "general" | "reduced" | "reverse" | "exempt" | "none";
  business_pct?: string;
  account: "acc-01" | "acc-02";
  low: number;
  high: number;
  country?: string;
  currency?: string;
};

const CLIENTS = [
  "Talleres Ondara, S.L.",
  "Editorial Brisa Norte, S.A.",
  "Clínica Dental Arrecife, S.L.P.",
  "Cooperativa Olivar del Sur",
  "Hotel Mirador Azul, S.L.",
  "Bodegas Peña Rubia, S.L.",
];
const CLIENT_NIFS = [
  "B00000017",
  "A00000025",
  "B00000033",
  "F00000041",
  "B00000058",
  "B00000066",
];
const RECURRING: Kind[] = [
  {
    description: "CUOTA AUTONOMOS TGSS",
    counterparty: "Tesorería General de la Seguridad Social",
    direction: "OUTGOING",
    classification: "BUSINESS",
    category: "cuotas_autonomos_ss",
    iva: "none",
    account: "acc-01",
    low: 29400,
    high: 29400,
  },
  {
    description: "RECIBO TELEFONIA ALBOR MOVIL",
    counterparty: "Telefonía Albor, S.A.",
    direction: "OUTGOING",
    classification: "BUSINESS",
    category: "telefonia_movil",
    iva: "general",
    account: "acc-01",
    low: 3509,
    high: 4235,
  },
  {
    description: "FIBRA HOGAR ALBOR",
    counterparty: "Telefonía Albor, S.A.",
    direction: "OUTGOING",
    classification: "MIXED",
    category: "suministros_home_office_internet",
    iva: "general",
    business_pct: "0.30",
    account: "acc-02",
    low: 4235,
    high: 4235,
  },
  {
    description: "ELECTRICA COSTA CLARA FACTURA LUZ",
    counterparty: "Eléctrica Costa Clara, S.A.",
    direction: "OUTGOING",
    classification: "MIXED",
    category: "suministros_home_office_luz",
    iva: "general",
    business_pct: "0.30",
    account: "acc-02",
    low: 5810,
    high: 9875,
  },
  {
    description: "COWORKING RIBERA PUESTO FIJO",
    counterparty: "Coworking Ribera, S.L.",
    direction: "OUTGOING",
    classification: "BUSINESS",
    category: "arrendamiento_local",
    iva: "general",
    account: "acc-01",
    low: 21780,
    high: 21780,
  },
  {
    description: "SOFTNUBE IRELAND SUSCRIPCION",
    counterparty: "SoftNube Ireland Ltd",
    direction: "OUTGOING",
    classification: "BUSINESS",
    category: "software_suscripcion",
    iva: "reverse",
    account: "acc-01",
    low: 5999,
    high: 5999,
    country: "IE",
  },
  {
    description: "COMISION MANTENIMIENTO CUENTA",
    counterparty: "",
    direction: "OUTGOING",
    classification: "BUSINESS",
    category: "gastos_bancarios",
    iva: "exempt",
    account: "acc-01",
    low: 600,
    high: 600,
  },
  {
    description: "TRASPASO A CUENTA PERSONAL",
    counterparty: "",
    direction: "INTERNAL_TRANSFER",
    classification: "PERSONAL",
    category: null,
    iva: "none",
    account: "acc-01",
    low: 120000,
    high: 180000,
  },
];
const OCCASIONAL: Kind[] = [
  {
    description: "GASOLINERA RUTA 7",
    counterparty: "Estación de Servicio Ruta 7, S.L.",
    direction: "OUTGOING",
    classification: "MIXED",
    category: "vehiculo_combustible",
    iva: "general",
    business_pct: "0.50",
    account: "acc-01",
    low: 4500,
    high: 7800,
  },
  {
    description: "PAPELERIA TRAZO",
    counterparty: "Papelería Trazo",
    direction: "OUTGOING",
    classification: "BUSINESS",
    category: "material_oficina",
    iva: "general",
    account: "acc-01",
    low: 1290,
    high: 8650,
  },
  {
    description: "PARKING CENTRO MUNICIPAL",
    counterparty: "Aparcamientos Centro Lumbre",
    direction: "OUTGOING",
    classification: "BUSINESS",
    category: "vehiculo_parking",
    iva: "general",
    account: "acc-01",
    low: 450,
    high: 1800,
  },
  {
    description: "TREN ALTA VELOCIDAD BILLETE",
    counterparty: "Viajeros Meridiano, S.A.",
    direction: "OUTGOING",
    classification: "BUSINESS",
    category: "viajes_transporte",
    iva: "reduced",
    account: "acc-01",
    low: 3890,
    high: 11240,
  },
];
const PERSONAL: Kind[] = [
  {
    description: "SUPERMERCADO HOJA VERDE",
    counterparty: "Supermercados Hoja Verde, S.A.",
    direction: "OUTGOING",
    classification: "PERSONAL",
    category: null,
    iva: "none",
    account: "acc-02",
    low: 1835,
    high: 12460,
  },
  {
    description: "FARMACIA NUBE BLANCA",
    counterparty: "Farmacia Nube Blanca",
    direction: "OUTGOING",
    classification: "PERSONAL",
    category: null,
    iva: "none",
    account: "acc-02",
    low: 480,
    high: 3620,
  },
  {
    description: "RESTAURANTE LA ALACENA",
    counterparty: "La Alacena de Tomás, S.L.",
    direction: "OUTGOING",
    classification: "PERSONAL",
    category: null,
    iva: "none",
    account: "acc-02",
    low: 2200,
    high: 6800,
  },
  {
    description: "CINES ESTRELLA POLAR",
    counterparty: "Cines Estrella Polar",
    direction: "OUTGOING",
    classification: "PERSONAL",
    category: null,
    iva: "none",
    account: "acc-02",
    low: 900,
    high: 2400,
  },
  {
    description: "BAZAR EL FARO COMPRA",
    counterparty: "Bazar El Faro",
    direction: "OUTGOING",
    classification: "PERSONAL",
    category: null,
    iva: "none",
    account: "acc-02",
    low: 350,
    high: 4990,
  },
];

const TRIP_HOTEL: Kind = {
  description: "HOTEL PUERTO LEVANTE ESTANCIA",
  counterparty: "Hotel Puerto Levante, S.L.",
  direction: "OUTGOING",
  classification: "BUSINESS",
  category: "viajes_alojamiento",
  iva: "reduced",
  account: "acc-01",
  low: 24200,
  high: 24200,
};

const RATE = { general: 21, reduced: 10 } as const;

function receivedInvoice(
  invoiceId: string,
  number: string,
  issued: string,
  baseCents: number,
  ivaCents: number,
  linked: string,
): CatalogueInvoice {
  return {
    invoice_id: invoiceId,
    bucket_id: null,
    kind: "received",
    invoice_number: number,
    issued_at: issued,
    counterparty_name: "Coworking Ribera, S.L.",
    counterparty_tax_id: "B00000074",
    counterparty_country: "ES",
    base_total: decimal(baseCents),
    iva_total: decimal(ivaCents),
    grand_total: decimal(baseCents + ivaCents),
    currency: "EUR",
    payment_status: "PAID",
    linked_transaction_ids: [linked],
    source_filename: null,
    source_sha256: null,
    source_row_index: null,
    notes: "",
    retention_rate: null,
    retention_amount: null,
    recargo_amount: null,
    operation_type: null,
    lines: [
      {
        description: "Puesto fijo en espacio compartido",
        quantity: { decimal: "1" },
        unit_price: decimal(baseCents),
        subtotal: decimal(baseCents),
        iva_rate: "RATE_21",
        iva_amount: decimal(ivaCents),
        spending_category_id: "arrendamiento_local",
        oss_rate_kind: null,
      },
    ],
    invoice_class: "ORDINARIA",
    series: null,
    operation_date: issued,
    operation_date_role: "OPERATION_PERFORMED",
    iva_category: "domestic_general",
    rectifies_invoice_number: null,
    fx_rate: null,
    fx_rate_date: null,
    fx_rate_source: null,
    base_total_eur: null,
    iva_total_eur: null,
    grand_total_eur: null,
    referencia_catastral: null,
  };
}

export function fixtureLedger(): FixtureLedger {
  const random = generator(20_260_101);
  const movements: FixtureMovement[] = [];
  const invoices: CatalogueInvoice[] = [];
  const evidence: FixtureEvidence[] = [];
  let sequence = 0;

  const push = (
    kind: Kind,
    date: string,
    amountCents: number,
    extra: Partial<FixtureMovement> & {
      invoice_id?: string | null;
      evidence_id?: string | null;
      attachment_id?: string | null;
      currency?: string;
      fx_rate?: string;
      value_in_eur?: string;
    } = {},
  ) => {
    sequence += 1;
    const month = Number(date.slice(5, 7));
    const recent = month >= 9;
    const unprocessed =
      recent && kind.classification !== "PERSONAL" && random.next() < 0.45;
    const classification = unprocessed
      ? "NOT_YET_PROCESSED"
      : kind.classification;
    const business =
      classification === "BUSINESS" || classification === "MIXED";
    const rate =
      kind.iva === "general"
        ? RATE.general
        : kind.iva === "reduced"
          ? RATE.reduced
          : 0;
    const base = rate
      ? Math.round((amountCents * 100) / (100 + rate))
      : amountCents;
    const amount = money(amountCents);
    const description = kind.description;
    const account = kind.account;
    const created = stamp(date, random.between(0, 600));
    const transaction: LedgerTransaction = {
      transaction_id: movementId({
        date,
        amount,
        description,
        own_account_id: account,
        salt: String(sequence),
      }),
      date,
      booked_date: date,
      value_date: date,
      amount,
      currency: extra.currency ?? kind.currency ?? "EUR",
      direction: kind.direction,
      counterparty: kind.counterparty,
      description,
      business_classification: classification,
      business_pct: business && kind.business_pct ? kind.business_pct : null,
      category_id: business ? kind.category : null,
      taxable_base: business && kind.iva !== "none" ? money(base) : null,
      iva_rate:
        business && rate
          ? `0.${String(rate).padStart(2, "0")}`
          : business && kind.iva === "reverse"
            ? "0.21"
            : null,
      iva_amount:
        business && rate
          ? money(amountCents - base)
          : business && kind.iva === "reverse"
            ? money(Math.round(amountCents * 0.21))
            : null,
      iva_category: !business
        ? null
        : kind.iva === "general"
          ? "domestic_general"
          : kind.iva === "reduced"
            ? "domestic_reduced"
            : kind.iva === "reverse"
              ? "intra_community_service_acquisition_reverse_charge"
              : kind.iva === "exempt"
                ? "domestic_exempt"
                : "domestic_not_subject",
      counterparty_country: kind.country ?? (kind.counterparty ? "ES" : null),
      counterparty_identification_state: kind.country ?? null,
      irpf_category: null,
      m210_income_classification: null,
      usage_ratio_id: null,
      prorrata_reference: null,
      purchase_invoice_evidence_id: extra.evidence_id ?? null,
      invoice_id: extra.invoice_id ?? null,
      attachment_ids: extra.attachment_id ? [extra.attachment_id] : [],
      notes: "",
      lifecycle_state: "ACTIVE",
      classified_by: unprocessed
        ? ""
        : kind.classification === "PERSONAL"
          ? "rule"
          : "operator",
      classified_at: unprocessed ? null : created,
      classification_reason: unprocessed
        ? ""
        : kind.classification === "PERSONAL"
          ? "rule:hoja-verde"
          : "operator",
      classification_confidence: null,
      source_jurisdiction: null,
      value_in_eur: extra.value_in_eur ?? null,
      fx_rate: extra.fx_rate ?? null,
      created_at: created,
      modified_at: created,
    };
    movements.push({
      transaction,
      group_label: extra.group_label ?? null,
      own_account_id: account,
      import_batch_id: `import-2026-${String(month).padStart(2, "0")}`,
      issue: extra.issue ?? null,
      sealed: month <= 3,
      llm_rejected: extra.llm_rejected ?? false,
      idempotency_key: null,
    });
    return transaction;
  };

  for (let month = 1; month <= 10; month += 1) {
    const last = month === 10 ? 23 : daysIn(month);
    // The studio invoices its clients and is paid a few weeks later.
    const clientsThisMonth = random.between(4, 6);
    for (let at = 0; at < clientsThisMonth; at += 1) {
      const client = random.between(0, CLIENTS.length - 1);
      const baseCents = random.pick([
        45000, 68000, 90000, 120000, 150000, 210000,
      ]);
      const ivaCents = Math.round(baseCents * 0.21);
      const retentionCents = Math.round(baseCents * 0.15);
      const issued = day(month, random.between(1, Math.min(10, last)));
      const number = `2026-${String(invoices.length + 1).padStart(3, "0")}`;
      const invoiceId = hex64(`invoice:${number}`);
      const paid = day(month, random.between(Math.min(15, last), last));
      const paidCents = baseCents + ivaCents - retentionCents;
      const kind: Kind = {
        description: `TRANSFERENCIA ${CLIENTS[client]!.toUpperCase()} FRA ${number}`,
        counterparty: CLIENTS[client]!,
        direction: "INCOMING",
        classification: "BUSINESS",
        category: null,
        iva: "general",
        account: "acc-01",
        low: paidCents,
        high: paidCents,
      };
      const projectGroup =
        client === 0 && month >= 4 && month <= 7 ? "Proyecto web Ondara" : null;
      const row = push(kind, paid, paidCents, {
        invoice_id: invoiceId,
        group_label: projectGroup,
      });
      row.taxable_base = money(baseCents);
      row.iva_rate = "0.21";
      row.iva_amount = money(ivaCents);
      row.irpf_category = "actividad_economica";
      invoices.push({
        invoice_id: invoiceId,
        bucket_id: null,
        kind: "issued",
        invoice_number: number,
        issued_at: issued,
        counterparty_name: CLIENTS[client]!,
        counterparty_tax_id: CLIENT_NIFS[client]!,
        counterparty_country: "ES",
        base_total: decimal(baseCents),
        iva_total: decimal(ivaCents),
        grand_total: decimal(baseCents + ivaCents),
        currency: "EUR",
        payment_status: "PAID",
        linked_transaction_ids: [row.transaction_id],
        source_filename: null,
        source_sha256: null,
        source_row_index: null,
        notes: "",
        retention_rate: { decimal: "0.15" },
        retention_amount: decimal(retentionCents),
        recargo_amount: null,
        operation_type: null,
        lines: [
          {
            description: "Diseño de identidad y piezas gráficas",
            quantity: { decimal: "1" },
            unit_price: decimal(baseCents),
            subtotal: decimal(baseCents),
            iva_rate: "RATE_21",
            iva_amount: decimal(ivaCents),
            spending_category_id: null,
            oss_rate_kind: null,
          },
        ],
        invoice_class: "ORDINARIA",
        series: "2026",
        operation_date: issued,
        operation_date_role: "OPERATION_PERFORMED",
        iva_category: "domestic_general",
        rectifies_invoice_number: null,
        fx_rate: null,
        fx_rate_date: null,
        fx_rate_source: null,
        base_total_eur: null,
        iva_total_eur: null,
        grand_total_eur: null,
        referencia_catastral: null,
      });
    }
    // A client abroad pays in dollars every other month.
    if (month % 2 === 0) {
      const usd = random.pick([180000, 240000]);
      const rate = random.pick(["0.9182", "0.9247", "0.9311"]);
      push(
        {
          description: "SWIFT BRIGHT HARBOR LTD",
          counterparty: "Bright Harbor Ltd",
          direction: "INCOMING",
          classification: "BUSINESS",
          category: null,
          iva: "none",
          account: "acc-01",
          low: usd,
          high: usd,
          country: "US",
          currency: "USD",
        },
        day(month, random.between(5, Math.min(25, last))),
        usd,
        {
          currency: "USD",
          fx_rate: rate,
          value_in_eur: money(Math.round(usd * Number(rate))),
        },
      );
    }
    for (const kind of RECURRING) {
      const date = day(month, Math.min(last, random.between(1, 28)));
      const amount = random.between(kind.low, kind.high);
      const withEvidence = kind.category === "arrendamiento_local";
      const evidenceId = withEvidence ? hex64(`evidence:${month}`) : null;
      if (evidenceId) {
        const base = Math.round((amount * 100) / 121);
        evidence.push({
          evidence_id: evidenceId,
          bucket_id: LEDGER_FIXTURE_PROFILE_ID,
          source_sha256: hex64(`evidence-bytes:${month}`),
          attachment_id: hex64(`evidence-bytes:${month}`),
          media_kind: month % 3 === 0 ? "image" : "pdf",
          supplier: "Coworking Ribera, S.L.",
          invoice_number: `CR-2026-${String(month).padStart(4, "0")}`,
          invoice_date: day(month, 1),
          taxable_base: money(base),
          iva_rate: "21",
          iva_amount: money(amount - base),
          notes: "",
          created_at: stamp(day(month, 2), 30),
          updated_at: stamp(day(month, 2), 30),
          source_path: `coworking-ribera-2026-${String(month).padStart(2, "0")}.pdf`,
        });
      }
      const paid = push(kind, date, amount, {
        evidence_id: evidenceId,
        attachment_id: evidenceId ? hex64(`evidence-bytes:${month}`) : null,
      });
      if (evidenceId) {
        // The coworking's monthly invoice, received and linked to its payment.
        const base = Math.round((amount * 100) / 121);
        const number = `CR-2026-${String(month).padStart(4, "0")}`;
        const invoiceId = hex64(`invoice:${number}`);
        paid.invoice_id = invoiceId;
        invoices.push(
          receivedInvoice(
            invoiceId,
            number,
            day(month, 1),
            base,
            amount - base,
            paid.transaction_id,
          ),
        );
      }
    }
    const occasional = random.between(2, 4);
    for (let at = 0; at < occasional; at += 1) {
      const kind = random.pick(OCCASIONAL);
      push(
        kind,
        day(month, random.between(1, last)),
        random.between(kind.low, kind.high),
        {
          group_label:
            month === 3 && kind.category === "viajes_transporte"
              ? "Viaje feria Valencia"
              : null,
        },
      );
    }
    if (month === 3) {
      // The trip to a trade fair, kept together as a group.
      for (const [kind, amount, date] of [
        [OCCASIONAL[3]!, 8640, day(3, 11)],
        [TRIP_HOTEL, 24200, day(3, 13)],
      ] as const)
        push(kind, date, amount, { group_label: "Viaje feria Valencia" });
    }
    const personal = random.between(16, 20);
    for (let at = 0; at < personal; at += 1) {
      const kind = random.pick(PERSONAL);
      push(
        kind,
        day(month, random.between(1, last)),
        random.between(kind.low, kind.high),
      );
    }
    // The quarter's tax payments are excluded from the activity's figures.
    if (month === 4 || month === 7 || month === 10) {
      for (const modelo of ["303", "130"]) {
        const row = push(
          {
            description: `PAGO AEAT MODELO ${modelo}`,
            counterparty: "Agencia Estatal de Administración Tributaria",
            direction: "OUTGOING",
            classification: "REVIEWED_EXCLUDED",
            category: null,
            iva: "none",
            account: "acc-01",
            low: 0,
            high: 0,
          },
          day(month, 20),
          random.between(42000, 98000),
        );
        row.notes = `Pago trimestral modelo ${modelo}`;
      }
    }
  }

  // A few rows the import flagged, and model proposals the person rejected.
  const flagged: FixtureMovement["issue"][] = ["duplicate", "gap", "parser"];
  flagged.forEach((issue, at) => {
    movements[40 + at * 37]!.issue = issue;
  });
  for (const at of [300, 301]) {
    const rejected = movements[at];
    if (rejected) rejected.llm_rejected = true;
  }

  // Something for readiness to find in the open quarters: business
  // expenses whose category was never chosen, and foreign income whose
  // exchange rate was not found, so its euro value is not known.
  const open = movements.filter(
    (movement) =>
      movement.transaction.date >= "2026-07-01" &&
      movement.transaction.lifecycle_state === "ACTIVE",
  );
  open
    .filter(
      (movement) =>
        movement.transaction.business_classification === "BUSINESS" &&
        movement.transaction.direction === "OUTGOING" &&
        movement.transaction.category_id !== null,
    )
    .filter((_, at) => at % 5 === 2)
    .forEach((movement) => {
      movement.transaction.category_id = null;
    });
  const foreign = open.filter(
    (movement) => movement.transaction.currency !== "EUR",
  );
  for (const movement of foreign.slice(-1)) {
    movement.transaction.value_in_eur = null;
    movement.transaction.fx_rate = null;
  }

  // A few movements from earlier years, so that moving between years, and
  // the years that hold movements, have something to find. Added after the
  // year's rows so none of those changes. Before the accounts were opened a
  // movement is bound to none.
  for (const [date, kind, amountCents] of [
    ["2003-05-14", PERSONAL[0]!, 2310],
    ["2011-11-02", PERSONAL[1]!, 1475],
    ["2019-06-21", OCCASIONAL[1]!, 3630],
    ["2024-03-08", OCCASIONAL[1]!, 1815],
    ["2024-12-19", PERSONAL[0]!, 6240],
    ["2025-09-30", OCCASIONAL[0]!, 5600],
  ] as const) {
    push(kind, date, amountCents);
    const earlier = movements.at(-1)!;
    const year = date.slice(0, 4);
    earlier.sealed = false;
    earlier.import_batch_id = `import-${year}-${date.slice(5, 7)}`;
    if (year < "2012") earlier.own_account_id = null;
  }

  return {
    movements,
    invoices: [...invoices, ...exampleInvoices(hex64)],
    evidence,
    rules: [
      {
        rule_id: hex64("CUOTA AUTONOMOS|BUSINESS|cuotas_autonomos_ss"),
        description_pattern: "CUOTA AUTONOMOS",
        classification: "BUSINESS",
        category_id: "cuotas_autonomos_ss",
        priority: 10,
        actor: "operator",
        created_at: "2026-01-04T10:00:00Z",
      },
      {
        rule_id: hex64("HOJA VERDE|PERSONAL|"),
        description_pattern: "HOJA VERDE",
        classification: "PERSONAL",
        category_id: null,
        priority: 50,
        actor: "operator",
        created_at: "2026-01-04T10:02:00Z",
      },
      {
        rule_id: hex64("COMISION MANTENIMIENTO|BUSINESS|gastos_bancarios"),
        description_pattern: "COMISION MANTENIMIENTO",
        classification: "BUSINESS",
        category_id: "gastos_bancarios",
        priority: 100,
        actor: "operator",
        created_at: "2026-02-11T18:20:00Z",
      },
    ],
    accounts: [
      {
        own_account_id: "acc-01",
        label: "Cuenta del estudio",
        holding: "titular",
        masked_iban: "ES**1234",
        country_code: "ES",
        sepa_marca: "1",
        has_swift_bic: false,
        has_bank_block: false,
        currency: "EUR",
        opened_on: "2019-03-01",
        closed_on: null,
      },
      {
        own_account_id: "acc-02",
        label: "Cuenta personal",
        holding: "titular",
        masked_iban: "ES**8810",
        country_code: "ES",
        sepa_marca: "1",
        has_swift_bic: false,
        has_bank_block: false,
        currency: "EUR",
        opened_on: "2012-09-14",
        closed_on: null,
      },
    ],
  };
}

export function emptyLedger(): FixtureLedger {
  return { movements: [], invoices: [], evidence: [], rules: [], accounts: [] };
}

/** How many movements the large ledger adds to October 2026. */
export const LARGE_LEDGER_EXTRA = 5_000;

/** The fixture ledger holding `rows` movements in the fourth quarter of
 * 2026, generated the same way on every run. */
export function ledgerOfRows(rows: number): FixtureLedger {
  const held = fixtureLedger().movements.filter((movement) =>
    /^2026-1[0-2]-/.test(movement.transaction.date),
  ).length;
  return largeLedger(Math.max(0, rows - held));
}

/** The fixture ledger with thousands more movements in October 2026, the
 * size a busy period reaches, for measuring the grid. Each is a copy of an
 * October movement with its own id, day and amount. */
export function largeLedger(extra = LARGE_LEDGER_EXTRA): FixtureLedger {
  const ledger = fixtureLedger();
  const october = ledger.movements.filter((movement) =>
    movement.transaction.date.startsWith("2026-10-"),
  );
  for (let at = 0; at < extra; at += 1) {
    const source = october[at % october.length]!;
    const date = day(10, 1 + (at % 23));
    const amount = money(500 + ((at * 7919) % 250_000));
    const description = `${source.transaction.description} ${String(at).padStart(4, "0")}`;
    ledger.movements.push({
      ...source,
      transaction: {
        ...source.transaction,
        transaction_id: movementId({
          date,
          amount,
          description,
          own_account_id: source.own_account_id,
          salt: `large-${at}`,
        }),
        date,
        booked_date: date,
        value_date: date,
        amount,
        description,
        taxable_base: null,
        iva_amount: null,
      },
      sealed: false,
    });
  }
  ledger.movements.sort(
    (a, b) =>
      a.transaction.date.localeCompare(b.transaction.date) ||
      a.transaction.transaction_id.localeCompare(b.transaction.transaction_id),
  );
  return ledger;
}
