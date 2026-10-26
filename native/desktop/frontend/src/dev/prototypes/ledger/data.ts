import type {
  Account,
  Asset,
  Batch,
  CapitalGood,
  Consent,
  Counterparty,
  Inventory,
  ProrrataYear,
  Rule,
  Cls,
  Doc,
  HistoryEntry,
  Invoice,
  Ledger,
  Movement,
  Seed,
} from "./types";
import {
  CATEGORY_LABEL,
  CLASSIFIED,
  CLS,
  LINE_RATES,
  MONTH_LABEL,
  pct,
} from "./vocab";

/* ── Synthetic data: one autónomo's 2026, deterministic. No real person,
   NIF or account is used; tax ids are visibly synthetic (repeated digits). ── */

export function mulberry32(a: number) {
  return function () {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
export function hashHex(str: string, len = 64) {
  let out = "";
  let seed = 0;
  while (out.length < len) {
    let h1 = 0xdeadbeef ^ seed,
      h2 = 0x41c6ce57 ^ seed;
    for (let i = 0; i < str.length; i++) {
      const ch = str.charCodeAt(i);
      h1 = Math.imul(h1 ^ ch, 2654435761);
      h2 = Math.imul(h2 ^ ch, 1597334677);
    }
    h1 =
      Math.imul(h1 ^ (h1 >>> 16), 2246822507) ^
      Math.imul(h2 ^ (h2 >>> 13), 3266489909);
    h2 =
      Math.imul(h2 ^ (h2 >>> 16), 2246822507) ^
      Math.imul(h1 ^ (h1 >>> 13), 3266489909);
    out +=
      (h2 >>> 0).toString(16).padStart(8, "0") +
      (h1 >>> 0).toString(16).padStart(8, "0");
    seed++;
  }
  return out.slice(0, len);
}
export const iso = (y: number, m: number, d: number) =>
  `${y}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
export function daysIn(y: number, m: number) {
  return new Date(Date.UTC(y, m, 0)).getUTCDate();
}
export function weekday(isoDate: string) {
  return new Date(isoDate + "T12:00:00Z").getUTCDay();
}
export function businessDay(y: number, m: number, d: number, back = false) {
  let day = Math.min(d, daysIn(y, m));
  for (let i = 0; i < 5; i++) {
    const w = weekday(iso(y, m, day));
    if (w !== 0 && w !== 6) break;
    day += back ? -1 : 1;
    if (day > daysIn(y, m)) {
      day = daysIn(y, m);
      back = true;
    }
  }
  return iso(y, m, day);
}
export function splitGross(cents: number, rate: number): [number, number] {
  const base = Math.round(cents / (1 + rate));
  return [base, cents - base];
}
export function quarterOf(isoDate: string) {
  return Math.floor((+isoDate.slice(5, 7) - 1) / 3) + 1;
}

export const ACCOUNTS: Account[] = [
  {
    id: "acc-01",
    label: "N26 Business",
    bank: "N26 Bank SE, Sucursal en España",
    iban: "ES21 •••• •••• •••• •••• 4417",
    currency: "EUR",
    opened: "2023-02-01",
    closed: null,
    holding: "titular",
    roles: ["Charge · Modelo 303", "Charge · Modelo 130"],
  },
  {
    id: "acc-02",
    label: "BBVA Cuenta Online",
    bank: "Banco Bilbao Vizcaya Argentaria",
    iban: "ES76 •••• •••• •••• •••• 0932",
    currency: "EUR",
    opened: "2016-09-12",
    closed: null,
    holding: "cotitular",
    roles: ["Refund · all modelos"],
  },
  {
    id: "acc-03",
    label: "Revolut Business USD",
    bank: "Revolut Bank UAB",
    iban: "LT61 •••• •••• •••• 2210",
    currency: "USD",
    opened: "2025-04-03",
    closed: null,
    holding: "titular",
    roles: [],
  },
];
// The seed's accounts only; an account added in a session lives in the store.
export const ACCOUNT_LABEL: Readonly<Record<string, string>> = Object.freeze(
  Object.fromEntries(ACCOUNTS.map((a) => [a.id, a.label])),
);

export const PROFILE = {
  name: "Alba Serrano Vidal",
  nif: "00000000T",
  activity: "Graphic design and illustration (IAE 844)",
  regime: "Estimación directa simplificada",
};

export const RATIOS: Record<string, Record<string, number>> = {
  2026: {
    telefonia_movil: 0.5,
    suministros_home_office_internet: 0.3,
    suministros_home_office_luz: 0.3,
    vehiculo_combustible: 0.5,
    ibi_vivienda_afecto: 0.2,
  },
  2025: {
    telefonia_movil: 0.5,
    suministros_home_office_internet: 0.3,
    suministros_home_office_luz: 0.3,
    vehiculo_combustible: 0.5,
  },
};
export const RATIO_ELIGIBLE = [
  "telefonia_movil",
  "telefonia_fija",
  "suministros_home_office_internet",
  "suministros_home_office_luz",
  "suministros_home_office_agua",
  "suministros_home_office_gas",
  "vehiculo_combustible",
  "vehiculo_mantenimiento",
  "vehiculo_seguro",
  "vehiculo_parking",
  "vehiculo_peaje",
  "ibi_vivienda_afecto",
  "comunidad_vivienda_afecto",
  "amortizacion_vivienda_afecto",
  "arrendamiento_vivienda_afecto",
  "hardware_amortizable",
];

type InvoiceSeed = {
  kind: string;
  cls?: string;
  series?: string;
  number: string;
  date: string;
  opDate?: string;
  counterparty: string;
  nif?: string | null;
  country: string;
  idState?: string;
  retentionRate?: number;
  recargo?: number;
  currency?: string;
  payment?: string;
  paymentId?: string;
  notes?: string;
  ivaCategory?: string;
  operationType?: string;
  rectifies?: string;
  provenance?: string;
  lines: {
    description: string;
    qty: number;
    price: number;
    rate: string;
    category?: string;
  }[];
};

export function buildData(): Ledger {
  const rnd = mulberry32(20261023);
  const pick = <T>(arr: T[]): T => arr[Math.floor(rnd() * arr.length)]!;
  const between = (a: number, b: number) => Math.round(a + rnd() * (b - a));
  const rows: Movement[] = [];
  const batches: Record<string, Batch> = {};
  const batchFor = (acc: string, y: number, m: number): Batch => {
    const key = `${acc}-${y}-${m}`;
    if (!batches[key]) {
      const file =
        acc === "acc-01"
          ? `n26-business-${y}-${String(m).padStart(2, "0")}.csv`
          : acc === "acc-02"
            ? `bbva-movimientos-${y}-${String(m).padStart(2, "0")}.xlsx`
            : `revolut-usd-${y}-${String(m).padStart(2, "0")}.csv`;
      const ingestedDay =
        m === 10
          ? acc === "acc-02"
            ? 22
            : 21
          : Math.min(daysIn(y, m + 1 > 12 ? 12 : m + 1), 4 + (m % 3));
      const ingested =
        m === 10
          ? iso(y, 10, ingestedDay)
          : iso(y, m + 1 > 12 ? 12 : m + 1, ingestedDay);
      batches[key] = {
        id: "b-" + hashHex(key, 10),
        file,
        account: acc,
        ingested,
        provider:
          acc === "acc-02"
            ? "bbva (xlsx)"
            : acc === "acc-03"
              ? "revolut (csv)"
              : "n26 (csv)",
        format: acc === "acc-02" ? "xlsx" : "csv",
        sha: hashHex("sha" + key),
        rows: 0,
      };
    }
    return batches[key];
  };
  let seq = 0;
  function add(t: Seed): Movement {
    seq++;
    const date = t.date;
    const y = +date.slice(0, 4),
      m = +date.slice(5, 7);
    const acc = t.account || "acc-01";
    const b = t.manual ? null : batchFor(acc, y, m);
    if (b) b.rows++;
    const providerId = t.manual
      ? `manual:bucket:${hashHex("k" + seq, 12)}`
      : `${acc}-${hashHex("p" + seq, 8)}`;
    const row: Movement = {
      id: hashHex([t.amount, t.description, providerId, date, acc].join("|")),
      providerId,
      booked: t.booked || date,
      valueDate: t.valueDate || null,
      amount: t.amount,
      currency: t.currency || "EUR",
      direction: t.direction || "out",
      counterparty: t.counterparty || "",
      description: t.description,
      cls: t.cls || "pending",
      share: t.share ?? null,
      category: t.category || null,
      ivaCategory: t.ivaCategory || null,
      base: t.base ?? null,
      ivaRate: t.ivaRate ?? null,
      ivaAmount: t.ivaAmount ?? null,
      recargo: t.recargo ?? null,
      irpf: t.irpf || null,
      usageRatio: t.usageRatio || null,
      counterpartyCountry: t.country || null,
      idState: t.idState || null,
      sourceJurisdiction: t.jurisdiction || null,
      account: acc,
      group: t.group || null,
      notes: t.notes || "",
      lifecycle: t.lifecycle || "active",
      classifiedBy:
        t.classifiedBy ||
        (CLASSIFIED.has(t.cls ?? "") || t.cls === "excluded"
          ? "manual"
          : t.cls === "skipped"
            ? "rule:r-traspaso"
            : "auto"),
      classifiedAt: null,
      invoiceId: null,
      evidenceId: null,
      attachments: [],
      fx: t.fx || null,
      fxMissing: !!t.fxMissing,
      batch: b ? b.id : null,
      prov: b
        ? {
            file: b.file,
            row: b.rows,
            provider: b.provider,
            format: b.format,
            ingested: b.ingested,
            sha: b.sha,
          }
        : {
            file: "manual entry",
            row: 1,
            provider: "manual",
            format: "manual",
            ingested: date,
            sha: hashHex("m" + seq),
          },
      sealed: null,
      uses: [],
      suggestion: t.suggestion || null,
      modelRejected: !!t.modelRejected,
      issue: t.issue || null,
      forceIssues: t.forceIssues || null,
      split: null,
      created:
        (b ? b.ingested : date) +
        "T09:" +
        String(10 + (seq % 49)).padStart(2, "0") +
        ":00Z",
      modified: null,
      history: [],
      remoteChange: !!t.remoteChange,
    };
    row.modified = row.created;
    if (
      CLASSIFIED.has(row.cls) ||
      row.cls === "excluded" ||
      row.cls === "skipped"
    ) {
      const d = row.created.slice(0, 10);
      row.classifiedAt =
        d + "T18:" + String(seq % 60).padStart(2, "0") + ":00Z";
      row.modified = row.classifiedAt;
    }
    rows.push(row);
    return row;
  }
  const exp = (cents: number, rate: number) => {
    const [base, iva] = splitGross(cents, rate);
    return { base, ivaRate: rate, ivaAmount: iva };
  };
  const Y = 2026;
  const lastMonth = 10;

  for (let m = 1; m <= lastMonth; m++) {
    const q = Math.ceil(m / 3);
    const fresh = m === 10; // the October statements were imported this week
    const done = (cls: Cls, extra: Partial<Seed> = {}): Partial<Seed> =>
      fresh ? { cls: extra.freshCls || "pending" } : { cls, ...extra };
    const day = (d: number) => businessDay(Y, m, d);
    const inMonth = (d: number) => d <= (m === 10 ? 23 : daysIn(Y, m));

    // Coworking desk: premises rent.
    add({
      date: day(2),
      amount: 18150,
      counterparty: "Espacio Nube Coworking SL",
      description: `ESPACIO NUBE COWORKING CUOTA ${MONTH_LABEL[m - 1]!.toUpperCase()}`,
      ...done("business", {
        category: "arrendamiento_local",
        ivaCategory: "domestic_general",
        ...exp(18150, 0.21),
        irpf: "actividad_economica",
      }),
      suggestion: fresh
        ? {
            cls: "business",
            category: "arrendamiento_local",
            ivaCategory: "domestic_general",
            confidence: 0.91,
            reason:
              "Monthly desk fee from a coworking provider, invoiced with 21% IVA; matches eleven prior business classifications for this counterparty.",
          }
        : null,
    });
    // Gestoría.
    add({
      date: day(5),
      amount: 7260,
      counterparty: "Arroyo Asesores SL",
      description: `ARROYO ASESORES HONORARIOS ${String(m).padStart(2, "0")}/2026`,
      ...done("business", {
        category: "asesoria_fiscal",
        ivaCategory: "domestic_general",
        base: 6000,
        ivaRate: 0.21,
        ivaAmount: 1260,
        irpf: "actividad_economica",
      }),
    });
    // Mobile: mixed 50 %.
    add({
      date: day(8),
      amount: 3630,
      counterparty: "Vodafone España SAU",
      description: `VODAFONE FACTURA MOVIL ${MONTH_LABEL[m - 1]!.toUpperCase()}`,
      ...done("mixed", {
        share: 0.5,
        usageRatio: "telefonia_movil",
        category: "telefonia_movil",
        ivaCategory: "domestic_general",
        base: 3000,
        ivaRate: 0.21,
        ivaAmount: 630,
        irpf: "actividad_economica",
      }),
      suggestion: fresh
        ? {
            cls: "mixed",
            share: 0.5,
            category: "telefonia_movil",
            ivaCategory: "domestic_general",
            confidence: 0.87,
            reason:
              "Mobile line used for work and personal calls; your 2026 ratio for Telefonía móvil is 50%.",
          }
        : null,
    });
    // Home internet: mixed 30 %.
    add({
      date: day(12),
      account: "acc-02",
      amount: 3000,
      counterparty: "Digi Spain Telecom SLU",
      description: "DIGI FIBRA 1GB RECIBO",
      ...done("mixed", {
        share: 0.3,
        usageRatio: "suministros_home_office_internet",
        category: "suministros_home_office_internet",
        ivaCategory: "domestic_general",
        base: 2479,
        ivaRate: 0.21,
        ivaAmount: 521,
        irpf: "actividad_economica",
      }),
    });
    // Electricity: mixed 30 %.
    const luz = between(5800, 9600);
    add({
      date: day(18),
      account: "acc-02",
      amount: luz,
      counterparty: "Iberdrola Clientes SAU",
      description: `IBERDROLA LUZ RECIBO ${MONTH_LABEL[m - 1]!.toUpperCase()}`,
      ...done("mixed", {
        share: 0.3,
        usageRatio: "suministros_home_office_luz",
        category: "suministros_home_office_luz",
        ivaCategory: "domestic_general",
        ...exp(luz, 0.21),
        irpf: "actividad_economica",
      }),
      forceIssues: m === 8 ? ["missing_home_office_afectacion"] : null,
    });
    // RETA, last business day.
    if (m < 10)
      add({
        date: businessDay(Y, m, daysIn(Y, m), true),
        amount: 29400,
        counterparty: "Tesorería General de la Seguridad Social",
        description: `SEGURIDAD SOCIAL RETA ${Y}-${String(m).padStart(2, "0")}`,
        cls: "business",
        category: "cuotas_autonomos_ss",
        irpf: "actividad_economica",
        classifiedBy: "rule:r-reta",
      });
    // N26 plan fee.
    add({
      date: day(1),
      amount: 990,
      counterparty: "N26 Bank SE",
      description: "N26 BUSINESS YOU CUOTA",
      ...done("business", {
        category: "gastos_bancarios",
        ivaCategory: "domestic_exempt",
        base: 990,
        ivaRate: 0,
        ivaAmount: 0,
        irpf: "actividad_economica",
      }),
    });
    // Health insurance.
    add({
      date: day(3),
      account: "acc-02",
      amount: 5800,
      counterparty: "Sanitas SA de Seguros",
      description: "SANITAS PRIMA SALUD AUTONOMO",
      ...done("business", {
        category: "seguros_salud_autonomo",
        ivaCategory: "domestic_exempt",
        base: 5800,
        ivaRate: 0,
        ivaAmount: 0,
        irpf: "actividad_economica",
      }),
    });
    // Cloud and software: EU reverse charge.
    const aws = between(1980, 4120);
    add({
      date: day(4),
      amount: aws,
      counterparty: "Amazon Web Services EMEA SARL",
      description: `AWS EMEA ${String(m).padStart(2, "0")}/2026 INVOICE EUINES26`,
      country: "LU",
      idState: fresh ? null : "lu",
      ...done("business", {
        category: "software_suscripcion",
        ivaCategory: "intra_community_service_acquisition_reverse_charge",
        base: aws,
        ivaRate: 0.21,
        ivaAmount: Math.round(aws * 0.21),
        irpf: "actividad_economica",
        classifiedBy: "rule:r-aws",
      }),
      remoteChange: m === 10,
      suggestion: fresh
        ? {
            cls: "business",
            category: "software_suscripcion",
            ivaCategory: "intra_community_service_acquisition_reverse_charge",
            confidence: 0.94,
            reason:
              "Cloud hosting billed from Luxembourg without IVA: an EU service acquired under reverse charge (inversión del sujeto pasivo).",
          }
        : null,
    });
    add({
      date: day(14),
      amount: 6049,
      counterparty: "Adobe Systems Software Ireland Ltd",
      description: "ADOBE CREATIVE CLOUD ALL APPS",
      country: "IE",
      idState: fresh ? null : "ie",
      ...done("business", {
        category: "software_suscripcion",
        ivaCategory: "intra_community_service_acquisition_reverse_charge",
        base: 6049,
        ivaRate: 0.21,
        ivaAmount: 1270,
        irpf: "actividad_economica",
      }),
      suggestion: fresh
        ? {
            cls: "business",
            category: "software_suscripcion",
            ivaCategory: "intra_community_service_acquisition_reverse_charge",
            confidence: 0.89,
            reason:
              "Design software subscription invoiced from Ireland; reverse charge applies to the EU service.",
          }
        : null,
    });
    // Fuel twice a month.
    [9, 23].forEach((d, i) => {
      if (!inMonth(d)) return;
      const c = m === 10 && d === 9 ? 6120 : between(4400, 7800);
      add({
        date: day(d),
        amount: c,
        counterparty: "Repsol Comercial de Productos Petrolíferos SA",
        description: `REPSOL E.S. ${pick(["VALENCIA PUERTO", "AV. CORTES", "PATERNA", "BURJASSOT"])}`,
        ...done("mixed", {
          share: 0.5,
          usageRatio:
            q === 2 && i === 1 && m === 5 ? null : "vehiculo_combustible",
          category: "vehiculo_combustible",
          ivaCategory: "domestic_general",
          ...exp(c, 0.21),
          irpf: "actividad_economica",
        }),
        suggestion: fresh
          ? {
              cls: "mixed",
              share: 0.5,
              category: "vehiculo_combustible",
              ivaCategory: "domestic_general",
              confidence: 0.72,
              reason:
                "Fuel purchase; the vehicle is shared between work and private use (ratio 50% in 2026). Keep the ticket as evidence.",
            }
          : null,
      });
    });
    // Groceries: personal by rule.
    const nGroc = m === 10 ? 3 : between(3, 5);
    for (let i = 0; i < nGroc; i++) {
      const d = between(1, m === 10 ? 22 : daysIn(Y, m));
      add({
        date: iso(Y, m, d),
        account: "acc-02",
        amount: between(1840, 9650),
        counterparty: "Mercadona SA",
        description: `MERCADONA ${pick(["AV. ARAGON", "RUZAFA", "BENIMACLET", "CAMPANAR"])} VALENCIA`,
        cls: "personal",
        classifiedBy: "rule:r-mercadona",
        country: "ES",
      });
    }
    // Meals and travel for work.
    const nMeals = m === 10 ? 2 : between(1, 3);
    for (let i = 0; i < nMeals; i++) {
      const c = between(1450, 4980);
      add({
        date: iso(Y, m, between(2, m === 10 ? 22 : 27)),
        amount: c,
        counterparty: pick([
          "Taberna La Lonja SL",
          "Bar Restaurante El Puerto",
          "Café Central Valencia SL",
        ]),
        description: "TPV RESTAURANTE COMIDA CLIENTE",
        ...done("business", {
          category: "manutencion_dietas_nacional",
          ivaCategory: "domestic_reduced",
          ...exp(c, 0.1),
          irpf: "actividad_economica",
        }),
        suggestion:
          fresh && i === 0
            ? {
                cls: "business",
                category: "manutencion_dietas_nacional",
                ivaCategory: "domestic_reduced",
                confidence: 0.58,
                reason:
                  "Restaurant on a weekday near a client's office. Low confidence: meals are deductible only when paid electronically and linked to the activity.",
              }
            : null,
      });
    }
    if (m % 2 === 0 || m === 10) {
      const c = between(2890, 7640);
      add({
        date: iso(Y, m, between(6, m === 10 ? 20 : 26)),
        amount: c,
        counterparty: "Renfe Viajeros SME SA",
        description: `RENFE BILLETE AVE VALENCIA-MADRID`,
        ...done("business", {
          category: "viajes_transporte",
          ivaCategory: "domestic_reduced",
          ...(m === 4
            ? { base: Math.round(c / 1.1), ivaRate: 0.1 }
            : exp(c, 0.1)),
          irpf: "actividad_economica",
        }),
      });
    }
    if (m === 4 || m === 6 || m === 9)
      add({
        date: iso(Y, m, 17),
        amount: 11880,
        counterparty: "NH Hotel Group SA",
        description: "NH MADRID ATOCHA ALOJAMIENTO",
        cls: "business",
        category: "viajes_alojamiento",
        ivaCategory: "domestic_reduced",
        ...exp(11880, 0.1),
        irpf: "actividad_economica",
      });
    if (inMonth(15) && m % 3 !== 1)
      add({
        date: day(15),
        amount: between(450, 1260),
        counterparty: "Saba Aparcamientos SA",
        description: "SABA PARKING ESTACION NORD",
        ...done("business", {
          category: "vehiculo_parking",
          ivaCategory: "domestic_general",
          ...exp(1000, 0.21),
          irpf: "actividad_economica",
        }),
      });
    // Personal leisure.
    add({
      date: day(11),
      account: "acc-02",
      amount: 1399,
      counterparty: "Netflix International BV",
      description: "NETFLIX.COM",
      cls: fresh ? "personal" : "personal",
      classifiedBy: "rule:r-ocio",
      country: "NL",
    });
    add({
      date: day(20),
      account: "acc-02",
      amount: 1199,
      counterparty: "Spotify AB",
      description: "SPOTIFY P1B2C3",
      cls: "personal",
      classifiedBy: "rule:r-ocio",
      country: "SE",
    });
    if (m % 2 === 1 || m === 10)
      add({
        date: iso(Y, m, between(3, 21)),
        account: "acc-02",
        amount: between(2490, 8990),
        counterparty: pick([
          "Zara España SA",
          "El Corte Inglés SA",
          "Decathlon España SA",
        ]),
        description: "COMPRA TARJETA TIENDA",
        ...done("personal"),
      });
    if (m % 3 === 0 || m === 10)
      add({
        date: iso(Y, m, between(3, 21)),
        account: "acc-02",
        amount: 6000,
        direction: "out",
        counterparty: "",
        description: "RETIRADA CAJERO BBVA",
        ...done("personal"),
      });
    // Transfer between own accounts (both legs).
    if (inMonth(16)) {
      add({
        date: day(16),
        amount: 120000,
        direction: "transfer",
        counterparty: "Alba Serrano Vidal",
        description: "TRASPASO A BBVA CUENTA ONLINE",
        cls: "skipped",
        classifiedBy: "rule:r-traspaso",
      });
      add({
        date: day(16),
        account: "acc-02",
        amount: 120000,
        direction: "transfer",
        counterparty: "Alba Serrano Vidal",
        description: "TRASPASO DESDE N26 BUSINESS",
        cls: "skipped",
        classifiedBy: "rule:r-traspaso",
      });
    }
    // Clients.
    const lumenD = day(10);
    add({
      date: lumenD,
      amount: 159000,
      direction: "in",
      counterparty: "Estudio Lumen SL",
      description: `TRANSF. ESTUDIO LUMEN SL FRA F-2026-${String(m * 2 - 1).padStart(3, "0")}`,
      ...done("business", {
        ivaCategory: "domestic_general",
        base: 150000,
        ivaRate: 0.21,
        ivaAmount: 31500,
        irpf: "actividad_economica",
      }),
      group: m >= 7 ? "Lumen rebrand" : null,
      suggestion: fresh
        ? {
            cls: "business",
            ivaCategory: "domestic_general",
            confidence: 0.96,
            reason:
              "Client payment net of 15% retención; matches issued invoice F-2026-019 for 1,815.00 (1,500.00 base).",
          }
        : null,
    });
    if (m % 2 === 0)
      add({
        date: day(24),
        amount: 254400,
        direction: "in",
        counterparty: "Norte Digital S. Coop.",
        description: `ABONO NORTE DIGITAL SCOOP FACT ${String(m).padStart(2, "0")}`,
        ...done("business", {
          ivaCategory: "domestic_general",
          base: 240000,
          ivaRate: 0.21,
          ivaAmount: 50400,
          irpf: "actividad_economica",
        }),
      });
    if (m % 3 === 0)
      add({
        date: day(28),
        amount: 339200,
        direction: "in",
        counterparty: "Grupo Atalaya Ediciones SA",
        description: `TRANSFERENCIA ATALAYA EDICIONES ${q}T`,
        cls: "business",
        ivaCategory: "domestic_general",
        base: 320000,
        ivaRate: 0.21,
        ivaAmount: 67200,
        irpf: "actividad_economica",
        group: "Atalaya catalogue",
      });
    if (m === 2 || m === 5 || m === 8 || m === 10) {
      const rate =
        m === 2 ? 0.9581 : m === 5 ? 0.9312 : m === 8 ? 0.9207 : null;
      add({
        date: iso(Y, m, m === 10 ? 21 : 19),
        account: "acc-03",
        amount: 275000,
        currency: "USD",
        direction: "in",
        counterparty: "Harbor & Pine LLC",
        description: "INCOMING SWIFT HARBOR AND PINE LLC",
        country: "US",
        jurisdiction: "US",
        ...(m === 10
          ? { cls: "pending" }
          : {
              cls: "business",
              ivaCategory: "operacion_no_sujeta",
              base: 275000,
              irpf: "actividad_economica",
            }),
        fx: rate
          ? {
              rate,
              eur: Math.round(275000 * rate),
              source: "ECB reference rate",
              date: iso(Y, m, m === 10 ? 21 : 19),
            }
          : null,
        fxMissing: !rate,
      });
    }
    // Small things.
    if (m % 3 === 2)
      add({
        date: iso(Y, m, between(5, 25)),
        amount: between(1190, 4860),
        counterparty: "Papelería Folio SL",
        description: "PAPELERIA FOLIO MATERIAL",
        ...done("business", {
          category: "material_oficina",
          ivaCategory: "domestic_general",
          ...exp(2400, 0.21),
          irpf: "actividad_economica",
        }),
      });
    if (m % 3 === 1)
      add({
        date: day(7),
        amount: 4500,
        counterparty: "Colegio Oficial de Diseño de la Comunitat Valenciana",
        description: "CUOTA COLEGIAL TRIMESTRAL",
        ...done("business", {
          category: "cuotas_colegiales",
          irpf: "actividad_economica",
        }),
      });
    if (m === 3 || m === 6 || m === 9)
      add({
        date: iso(Y, m, 22),
        amount: 735,
        counterparty: "Abertis Autopistas España SA",
        description: "PEAJE AP-7 SAGUNTO",
        cls: "business",
        category: "vehiculo_peaje",
        ivaCategory: "domestic_general",
        ...exp(735, 0.21),
        irpf: "actividad_economica",
      });
    // Bizum in/out (personal).
    if (m % 2 === 0)
      add({
        date: iso(Y, m, between(4, 25)),
        account: "acc-02",
        amount: between(1500, 4500),
        direction: "in",
        counterparty: "Pablo M.",
        description: "BIZUM RECIBIDO CENA",
        cls: "personal",
      });
    // Everyday card spending and the odd work taxi.
    const nMisc = m === 10 ? 4 : between(2, 3);
    for (let i = 0; i < nMisc; i++) {
      const [cp, desc] = pick([
        ["Consum S. Coop. V.", "CONSUM AV. PUERTO"],
        ["Glovoapp23 SA", "GLOVO PEDIDO"],
        ["Farmacia Sol Ruzafa", "FARMACIA SOL RUZAFA"],
        ["Cines Lys SA", "CINES LYS ENTRADAS"],
        ["Horno San Nicolás", "HORNO SAN NICOLAS"],
      ]);
      add({
        date: iso(Y, m, between(1, m === 10 ? 22 : 28)),
        account: "acc-02",
        amount: between(450, 3890),
        counterparty: cp,
        description: desc,
        ...done("personal"),
      });
    }
    if (m % 2 === 1 || m === 10) {
      const c = between(980, 2460);
      add({
        date: iso(Y, m, between(3, m === 10 ? 22 : 26)),
        amount: c,
        counterparty: "Maxi Mobility Spain SLU",
        description: "CABIFY TRAYECTO VALENCIA",
        ...done("business", {
          category: "viajes_transporte",
          ivaCategory: "domestic_reduced",
          ...exp(c, 0.1),
          irpf: "actividad_economica",
        }),
        suggestion: fresh
          ? {
              cls: "business",
              category: "viajes_transporte",
              ivaCategory: "domestic_reduced",
              confidence: 0.69,
              reason:
                "A ride on a weekday to a client's district; transport is taxed at 10%.",
            }
          : null,
      });
    }
  }

  // One-off movements.
  add({
    date: "2026-02-03",
    amount: 278179,
    counterparty: "PcComponentes y Multimedia SLU",
    description: "PCCOMPONENTES PEDIDO 88213",
    cls: "business",
    category: "hardware_amortizable",
    ivaCategory: "domestic_general",
    base: 229900,
    ivaRate: 0.21,
    ivaAmount: 48279,
    irpf: "actividad_economica",
    notes: "MacBook Pro 14. Depreciated as an activity asset.",
  });
  add({
    date: "2026-02-16",
    amount: 31000,
    counterparty: "Mapfre España SA",
    description: "MAPFRE POLIZA RC PROFESIONAL",
    cls: "business",
    category: "seguros_responsabilidad_civil",
    ivaCategory: "domestic_exempt",
    base: 31000,
    ivaRate: 0,
    ivaAmount: 0,
    irpf: "actividad_economica",
  });
  add({
    date: "2026-03-12",
    amount: 411400,
    counterparty: "Mobles Estudi Vidal SL",
    description: "MOBLES ESTUDI VIDAL FRA F0211",
    cls: "business",
    category: "mobiliario_amortizable",
    ivaCategory: "domestic_general",
    base: 340000,
    ivaRate: 0.21,
    ivaAmount: 71400,
    irpf: "actividad_economica",
    notes: "Desk and shelving. Bien de inversión (over 3,005.06).",
  });
  add({
    date: "2026-05-20",
    amount: 12000,
    counterparty: "LinkedIn Ireland Unlimited Company",
    description: "LINKEDIN ADS CAMPAIGN",
    country: "IE",
    idState: "ie",
    cls: "business",
    category: "publicidad_marketing",
    ivaCategory: "intra_community_service_acquisition_reverse_charge",
    base: 12000,
    ivaRate: 0.21,
    ivaAmount: 2520,
    irpf: "actividad_economica",
  });
  add({
    date: "2026-09-14",
    account: "acc-02",
    amount: 41230,
    counterparty: "Ajuntament de València",
    description: "IBI 2026 RECIBO DOMICILIADO",
    cls: "mixed",
    share: 0.2,
    usageRatio: "ibi_vivienda_afecto",
    category: "ibi_vivienda_afecto",
    ivaCategory: "domestic_not_subject",
    irpf: "actividad_economica",
  });
  add({
    date: "2026-07-07",
    amount: 8900,
    counterparty: "Escola d'Art i Disseny en línia",
    description: "CURSO TIPOGRAFIA AVANZADA",
    cls: "business",
    category: "formacion_profesional",
    ivaCategory: "domestic_exempt",
    base: 8900,
    ivaRate: 0,
    ivaAmount: 0,
    irpf: "actividad_economica",
  });
  // Tax payments: excluded from aggregation, said so.
  (
    [
      ["2026-04-20", 81240, "303", "1T"],
      ["2026-04-20", 49820, "130", "1T"],
      ["2026-07-20", 69015, "303", "2T"],
      ["2026-07-20", 51280, "130", "2T"],
    ] as [string, number, string, string][]
  ).forEach(([d, c, mo, p]) =>
    add({
      date: d,
      amount: c,
      counterparty: "Agencia Tributaria",
      description: `AEAT MODELO ${mo} ${p} 2026 CARGO`,
      cls: "excluded",
      notes: `Pago del Modelo ${mo} ${p}: a settlement, not an expense.`,
    }),
  );
  (
    [
      ["2026-10-20", 74406, "303", "3T"],
      ["2026-10-20", 53011, "130", "3T"],
    ] as [string, number, string, string][]
  ).forEach(([d, c, mo, p]) =>
    add({
      date: d,
      amount: c,
      counterparty: "Agencia Tributaria",
      description: `AEAT MODELO ${mo} ${p} 2026 CARGO`,
      cls: "pending",
    }),
  );
  // Q3 loose ends for the readiness checks.
  add({
    date: "2026-08-04",
    amount: 2399,
    counterparty: "Amazon EU SARL",
    description: "AMAZON.ES MKTPLACE PEDIDO 402-118",
    cls: "business",
    irpf: "actividad_economica",
    country: "LU",
  });
  add({
    date: "2026-08-21",
    amount: 6875,
    counterparty: "Leroy Merlin España SLU",
    description: "LEROY MERLIN COMPRA",
    cls: "business",
    ivaCategory: "domestic_general",
    irpf: "actividad_economica",
  });
  add({
    date: "2026-09-03",
    amount: 15488,
    counterparty: "Imprenta Gráficas Turia SL",
    description: "GRAFICAS TURIA IMPRESION CATALOGO",
    cls: "business",
    category: "suministros_cliente_directos",
    ivaCategory: "domestic_general",
    irpf: "actividad_economica",
    group: "Atalaya catalogue",
  });
  add({
    date: "2026-09-08",
    amount: 2450,
    counterparty: "Tienda desconocida",
    description: "TPV COMERCIO 0091273",
    cls: "failed",
    notes: "",
  });
  add({
    date: "2026-09-19",
    amount: 18900,
    counterparty: "Fotolia Estudio Freelance",
    description: "PAGO COLABORACION ILUSTRACIONES",
    cls: "business",
    category: "subcontratacion",
    ivaCategory: "unknown",
    irpf: "actividad_economica",
    group: "Atalaya catalogue",
  });
  add({
    date: "2026-08-27",
    amount: 3299,
    counterparty: "Udemy Netherlands BV",
    description: "UDEMY CURSO ANIMACION",
    cls: "pending",
    country: "NL",
    modelRejected: true,
    suggestion: null,
  });
  add({
    date: "2026-09-25",
    amount: 1299,
    counterparty: "Apple Distribution International Ltd",
    description: "APPLE.COM/BILL",
    cls: "pending",
    country: "IE",
    modelRejected: true,
  });
  add({
    date: "2026-07-29",
    amount: 5500,
    counterparty: "Taller Mecánico Benimaclet",
    description: "TALLER REVISION ITV",
    cls: "pending",
    suggestion: {
      cls: "mixed",
      share: 0.5,
      category: "vehiculo_mantenimiento",
      ivaCategory: "domestic_general",
      confidence: 0.66,
      reason:
        "Vehicle inspection and service at a garage; the vehicle is shared with private use.",
    },
  });
  // Manual, archived and stashed.
  add({
    date: "2026-08-11",
    amount: 4000,
    counterparty: "Caja de cambio",
    description: "EFECTIVO PAGO MERCADILLO IMPRESIONES",
    manual: true,
    cls: "business",
    category: "suministros_cliente_directos",
    irpf: "actividad_economica",
    notes: "Cash payment for print samples.",
    lifecycle: "stashed",
  });
  add({
    date: "2026-07-14",
    amount: 7260,
    counterparty: "Arroyo Asesores SL",
    description: "ARROYO ASESORES HONORARIOS 07/2026",
    cls: "business",
    lifecycle: "archived",
    notes: "Imported twice from two statement formats; archived the duplicate.",
    issue: "duplicate",
  });
  add({
    date: "2026-05-08",
    amount: 3630,
    counterparty: "Vodafone España SAU",
    description: "VODAFONE FACTURA MOVIL MAY",
    cls: "mixed",
    share: 0.5,
    lifecycle: "archived",
    notes: "Duplicate of the N26 row.",
  });
  // October likely duplicates and a gap note.
  const dupA = add({
    date: "2026-10-09",
    amount: 6120,
    counterparty: "Repsol Comercial de Productos Petrolíferos SA",
    description: "REPSOL E.S. PATERNA",
    cls: "pending",
    issue: "duplicate",
  });
  add({
    date: "2026-10-13",
    account: "acc-02",
    amount: 2870,
    counterparty: "Farmacia Sol Ruzafa",
    description: "FARMACIA SOL RUZAFA",
    cls: "pending",
    issue: "gap",
  });
  add({
    date: "2026-10-17",
    amount: 47190,
    counterparty: "Imprenta Gráficas Turia SL",
    description: "GRAFICAS TURIA SEGUNDA TIRADA",
    cls: "pending",
    group: "Atalaya catalogue",
    suggestion: {
      cls: "business",
      category: "suministros_cliente_directos",
      ivaCategory: "domestic_general",
      confidence: 0.83,
      reason:
        "Printing for the Atalaya catalogue project, same supplier and group as September.",
    },
  });
  add({
    date: "2026-10-22",
    amount: 2999,
    counterparty: "Domestika Inc",
    description: "DOMESTIKA CURSO LETTERING",
    cls: "pending",
    country: "US",
    currency: "EUR",
  });
  add({
    date: "2026-10-06",
    account: "acc-02",
    amount: 11900,
    counterparty: "Ikea Ibérica SA",
    description: "IKEA ALFAFAR",
    cls: "pending",
    suggestion: {
      cls: "personal",
      confidence: 0.61,
      reason:
        "Furniture store purchase on a personal card; no business pattern for this counterparty.",
    },
  });

  // Split: an Amazon order, parent plus two children.
  const parent = add({
    date: "2026-09-10",
    amount: 18640,
    counterparty: "Amazon EU SARL",
    description: "AMAZON.ES PEDIDO 405-77",
    cls: "business",
    lifecycle: "split",
    country: "LU",
  });
  const c1 = add({
    date: "2026-09-10",
    amount: 11240,
    counterparty: "Amazon EU SARL",
    description: "AMAZON.ES PEDIDO 405-77 · tablet stand and cables",
    cls: "business",
    category: "material_oficina",
    ivaCategory: "domestic_general",
    ...exp(11240, 0.21),
    irpf: "actividad_economica",
    manual: true,
    country: "LU",
  });
  const c2 = add({
    date: "2026-09-10",
    amount: 7400,
    counterparty: "Amazon EU SARL",
    description: "AMAZON.ES PEDIDO 405-77 · books",
    cls: "personal",
    manual: true,
    country: "LU",
  });
  parent.split = { role: "parent", children: [c1.id, c2.id] };
  c1.split = { role: "child", parent: parent.id, siblings: [c1.id, c2.id] };
  c2.split = { role: "child", parent: parent.id, siblings: [c1.id, c2.id] };

  // Earlier years (R21): a ledger can go back decades.
  (
    [
      [2003, 3],
      [2011, 6],
      [2019, 10],
      [2024, 24],
      [2025, 36],
    ] as [number, number][]
  ).forEach(([oy, n]) => {
    for (let i = 0; i < n; i++) {
      const om = 1 + ((i * 5) % 12),
        od = 3 + ((i * 7) % 24);
      const old = oy < 2016;
      const kind = i % 3;
      if (kind === 0) {
        const c = 60000 + ((i * 7919) % 180000);
        add({
          date: iso(oy, om, od),
          account: "acc-02",
          manual: old,
          amount: c,
          direction: "in",
          counterparty: [
            "Estudio Lumen SL",
            "Norte Digital S. Coop.",
            "Grupo Atalaya Ediciones SA",
          ][i % 3],
          description: `TRANSFERENCIA CLIENTE FRA ${oy}-${String(i + 1).padStart(3, "0")}`,
          cls: "business",
          ivaCategory: "domestic_general",
          ...exp(c, 0.21),
          irpf: "actividad_economica",
        });
      } else if (kind === 1)
        add({
          date: iso(oy, om, od),
          account: "acc-02",
          manual: old,
          amount: 1200 + ((i * 613) % 6000),
          counterparty: [
            "Mercadona SA",
            "Farmacia Sol Ruzafa",
            "Consum S. Coop. V.",
          ][i % 3],
          description: [
            "MERCADONA RUZAFA VALENCIA",
            "FARMACIA SOL RUZAFA",
            "CONSUM AV. PUERTO",
          ][i % 3]!,
          cls: "personal",
        });
      else {
        const c = 1500 + ((i * 1777) % 9000);
        add({
          date: iso(oy, om, od),
          account: "acc-02",
          manual: old,
          amount: c,
          counterparty: "Papelería Folio SL",
          description: "PAPELERIA FOLIO MATERIAL",
          cls: "business",
          category: "material_oficina",
          ivaCategory: "domestic_general",
          ...exp(c, 0.21),
          irpf: "actividad_economica",
        });
      }
    }
  });

  rows.sort(
    (a, b) =>
      (a.valueDate || a.booked).localeCompare(b.valueDate || b.booked) ||
      a.id.localeCompare(b.id),
  );

  // Sealing: the presented Modelo 303 and 130 for 1T use these rows.
  rows.forEach((r) => {
    const d = r.valueDate || r.booked;
    const q = quarterOf(d);
    if (
      r.lifecycle !== "active" ||
      !(r.cls === "business" || r.cls === "mixed")
    )
      return;
    const yr = +d.slice(0, 4);
    if (yr < 2026) {
      r.uses.push({
        modelo: "303",
        period: `${yr} ${q}T`,
        state: "filed_receipt",
        label: `Filed for ${yr} ${q}T · receipt confirmed`,
      });
      r.sealed = r.uses.slice();
      return;
    }
    if (q === 1) {
      r.uses.push({
        modelo: "303",
        period: "2026 1T",
        state: "filed_receipt",
        label: "Filed 20 Apr 2026 · receipt CSV …7QK2 confirmed",
      });
      r.uses.push({
        modelo: "130",
        period: "2026 1T",
        state: "filed_local",
        label: "Filed locally 20 Apr 2026 · AEAT status not confirmed",
      });
      r.sealed = r.uses.filter((u) => u.state !== "draft");
    } else if (q === 2) {
      r.uses.push({
        modelo: "303",
        period: "2026 2T",
        state: "draft",
        label: "Draft calculated 18 Jul 2026",
      });
      r.uses.push({
        modelo: "130",
        period: "2026 2T",
        state: "draft",
        label: "Draft calculated 18 Jul 2026",
      });
    } else if (q === 3) {
      r.uses.push({
        modelo: "303",
        period: "2026 3T",
        state: "draft",
        label: "Draft calculated 14 Oct 2026, stale",
      });
    }
  });

  // Histories.
  rows.forEach((r) => {
    const h: HistoryEntry[] = [
      {
        at: r.created,
        what: r.batch
          ? `Imported from ${r.prov.file}, row ${r.prov.row}`
          : "Added manually",
        by: r.batch ? "Bank statement import" : "You",
      },
    ];
    if (r.cls === "skipped")
      h.push({
        at: r.classifiedAt,
        what: "Skipped by rule r-traspaso (transfer between your accounts)",
        by: "Rule",
      });
    else if (r.classifiedBy.startsWith("rule:"))
      h.push({
        at: r.classifiedAt,
        what: `Classified ${CLS[r.cls].label} by the rule “${(RULES.find((x) => "rule:" + x.id === r.classifiedBy) || {}).name || r.classifiedBy}”`,
        by: "Rule",
      });
    else if (CLASSIFIED.has(r.cls))
      h.push({
        at: r.classifiedAt,
        what: `Classified ${CLS[r.cls].label}${r.share != null ? " " + pct(r.share) : ""}${r.category ? " · " + CATEGORY_LABEL[r.category] : ""}`,
        by: "You",
      });
    if (r.cls === "excluded")
      h.push({
        at: r.classifiedAt,
        what: "Excluded from filing: " + r.notes,
        by: "You",
      });
    if (r.modelRejected)
      h.push({
        at: "2026-09-29T10:12:00Z",
        what: "Model suggestion rejected: “Software subscription” does not apply, this is a personal purchase",
        by: "You",
      });
    if (r.lifecycle === "archived")
      h.push({
        at: "2026-09-02T16:40:00Z",
        what: "Archived: " + r.notes,
        by: "You",
      });
    if (r.lifecycle === "stashed")
      h.push({
        at: "2026-08-12T11:05:00Z",
        what: "Set aside: waiting for the supplier's receipt",
        by: "You",
      });
    if (r.split?.role === "parent")
      h.push({
        at: "2026-09-12T09:30:00Z",
        what: "Split into 2 parts: office supplies and personal books",
        by: "You",
      });
    r.history = h;
    r.classifiedHistory =
      CLASSIFIED.has(r.cls) && r.category && rnd() < 0.15
        ? [
            {
              at: "2026-03-02T12:00:00Z",
              cls: "business",
              category: r.category,
              by: "Model · llm:local-medium · approved by you",
            },
          ]
        : [];
  });

  // Invoices.
  const invoices: Invoice[] = [];
  const findRow = (pred: (r: Movement) => boolean) => rows.find(pred);
  function invoice(t: InvoiceSeed): Invoice {
    const lines = t.lines.map((l) => {
      const sub = Math.round(l.qty * l.price);
      const rateNum = LINE_RATES.find(([k]) => k === l.rate)![2];
      return {
        description: l.description,
        qty: l.qty,
        qtyText: String(l.qty),
        price: l.price,
        priceText: (l.price / 100).toFixed(2),
        subtotal: sub,
        rate: l.rate,
        iva: Math.round(sub * rateNum),
        category: l.category || null,
      };
    });
    const base = lines.reduce((s, l) => s + l.subtotal, 0);
    const iva = lines.reduce((s, l) => s + l.iva, 0);
    const total = base + iva + (t.recargo || 0);
    const inv = {
      id: hashHex(
        [
          t.kind,
          t.number,
          t.date,
          t.nif || "",
          t.currency || "EUR",
          total,
        ].join("|"),
      ),
      kind: t.kind,
      cls: t.cls || "ordinaria",
      series: t.series || null,
      number: t.number,
      date: t.date,
      opDate: t.opDate || null,
      counterparty: t.counterparty,
      nif: t.nif || null,
      country: t.country,
      idState: t.idState || null,
      base,
      iva,
      recargo: t.recargo || null,
      retentionRate: t.retentionRate ?? null,
      retention: t.retentionRate ? Math.round(base * t.retentionRate) : null,
      total,
      currency: t.currency || "EUR",
      lines,
      payment: t.payment || "paid",
      paymentId: t.paymentId || null,
      linked: [],
      notes: t.notes || "",
      ivaCategory: t.ivaCategory || "domestic_general",
      operationType: t.operationType || null,
      rectifies: t.rectifies || null,
      created: t.date + "T10:00:00Z",
      provenance: t.provenance || "Entered in Cadrumo",
    };
    invoices.push(inv);
    return inv;
  }
  function link(inv: Invoice, row: Movement | undefined) {
    if (!row) return;
    inv.linked.push(row.id);
    row.invoiceId = inv.id;
  }
  for (let m = 1; m <= 10; m++) {
    const n = m * 2 - 1;
    const inv = invoice({
      kind: "issued",
      series: "F",
      number: `F-2026-${String(n).padStart(3, "0")}`,
      date: iso(2026, m === 1 ? 1 : m - 1, 28),
      counterparty: "Estudio Lumen SL",
      nif: "B00000011",
      country: "ES",
      retentionRate: 0.15,
      lines: [
        {
          description: `Dirección de arte, ${MONTH_LABEL[(m + 10) % 12]} 2026`,
          qty: 1,
          price: 120000,
          rate: "RATE_21",
        },
        {
          description: "Ilustraciones editoriales",
          qty: 3,
          price: 10000,
          rate: "RATE_21",
        },
      ],
      payment: m >= 10 ? "pending" : "paid",
    });
    if (m <= 8)
      link(
        inv,
        findRow(
          (r) =>
            r.counterparty === "Estudio Lumen SL" &&
            +(r.valueDate || r.booked).slice(5, 7) === m,
        ),
      );
  }
  [2, 4, 6, 8, 10].forEach((m) => {
    const inv = invoice({
      kind: "issued",
      series: "F",
      number: `F-2026-${String(m * 2).padStart(3, "0")}`,
      date: iso(2026, m, 10),
      counterparty: "Norte Digital S. Coop.",
      nif: "F00000022",
      country: "ES",
      retentionRate: 0.15,
      lines: [
        {
          description: "Sistema de iconos y guía de estilo",
          qty: 1,
          price: 240000,
          rate: "RATE_21",
        },
      ],
      payment: m === 10 ? "overdue" : "paid",
    });
    if (m <= 8)
      link(
        inv,
        findRow(
          (r) =>
            r.counterparty === "Norte Digital S. Coop." &&
            +(r.valueDate || r.booked).slice(5, 7) === m,
        ),
      );
  });
  [3, 6, 9].forEach((m, i) => {
    const inv = invoice({
      kind: "issued",
      series: "F",
      number: `F-2026-A${i + 1}`,
      date: iso(2026, m, 15),
      counterparty: "Grupo Atalaya Ediciones SA",
      nif: "A00000033",
      country: "ES",
      retentionRate: 0.15,
      lines: [
        {
          description: `Maquetación catálogo, ${i + 1}T`,
          qty: 40,
          price: 6000,
          rate: "RATE_21",
        },
        {
          description: "Cubierta e ilustración principal",
          qty: 1,
          price: 80000,
          rate: "RATE_21",
        },
      ],
    });
    link(
      inv,
      findRow(
        (r) =>
          r.counterparty === "Grupo Atalaya Ediciones SA" &&
          +(r.valueDate || r.booked).slice(5, 7) === m,
      ),
    );
  });
  [2, 5, 8, 10].forEach((m, i) => {
    const inv = invoice({
      kind: "issued",
      series: "E",
      number: `E-2026-00${i + 1}`,
      date: iso(2026, m, 2),
      counterparty: "Harbor & Pine LLC",
      nif: null,
      country: "US",
      currency: "USD",
      ivaCategory: "operacion_no_sujeta",
      lines: [
        {
          description: "Packaging illustration, licence for North America",
          qty: 1,
          price: 275000,
          rate: "NOT_SUBJECT",
        },
      ],
      payment: m === 10 ? "paid" : "paid",
      notes:
        "Servicio no sujeto: art. 69.Uno LIVA (recipient established outside the EU).",
    });
    if (m !== 10)
      link(
        inv,
        findRow(
          (r) =>
            r.counterparty === "Harbor & Pine LLC" &&
            +(r.valueDate || r.booked).slice(5, 7) === m,
        ),
      );
  });
  invoice({
    kind: "issued",
    cls: "rectificativa",
    series: "R",
    number: "R-2026-001",
    date: "2026-06-30",
    counterparty: "Estudio Lumen SL",
    nif: "B00000011",
    country: "ES",
    rectifies: "F-2026-007",
    retentionRate: 0.15,
    lines: [
      {
        description: "Abono parcial por ilustración no entregada",
        qty: 1,
        price: 10000,
        rate: "RATE_21",
      },
    ],
    notes: "Rectifies F-2026-007 by one illustration.",
  });
  for (let m = 1; m <= 10; m++) {
    const g = invoice({
      kind: "received",
      series: "AA",
      number: `AA-26/${String(m).padStart(3, "0")}`,
      date: iso(2026, m, 3),
      counterparty: "Arroyo Asesores SL",
      nif: "B00000044",
      country: "ES",
      lines: [
        {
          description: "Honorarios asesoría fiscal y contable",
          qty: 1,
          price: 6000,
          rate: "RATE_21",
          category: "asesoria_fiscal",
        },
      ],
    });
    if (m <= 8)
      link(
        g,
        findRow(
          (r) =>
            r.counterparty === "Arroyo Asesores SL" &&
            r.lifecycle === "active" &&
            +(r.valueDate || r.booked).slice(5, 7) === m,
        ),
      );
    const c = invoice({
      kind: "received",
      number: `ENC-${2026}${String(m).padStart(2, "0")}-0187`,
      date: iso(2026, m, 1),
      counterparty: "Espacio Nube Coworking SL",
      nif: "B00000055",
      country: "ES",
      lines: [
        {
          description: "Puesto fijo coworking",
          qty: 1,
          price: 15000,
          rate: "RATE_21",
          category: "arrendamiento_local",
        },
      ],
    });
    if (m <= 9)
      link(
        c,
        findRow(
          (r) =>
            r.counterparty === "Espacio Nube Coworking SL" &&
            +(r.valueDate || r.booked).slice(5, 7) === m,
        ),
      );
  }
  for (let m = 1; m <= 6; m++) {
    const v = invoice({
      kind: "received",
      number: `VF26-${String(m).padStart(2, "0")}-559010`,
      date: iso(2026, m, 6),
      counterparty: "Vodafone España SAU",
      nif: "A00000066",
      country: "ES",
      lines: [
        {
          description: "Tarifa móvil ilimitada",
          qty: 1,
          price: 3000,
          rate: "RATE_21",
          category: "telefonia_movil",
        },
      ],
    });
    const vr = findRow(
      (r) =>
        r.counterparty === "Vodafone España SAU" &&
        r.lifecycle === "active" &&
        +(r.valueDate || r.booked).slice(5, 7) === m,
    );
    if (m === 5 && vr) {
      v.linked.push(vr.id); /* one-sided: the movement does not point back */
    } else link(v, vr);
  }
  [3, 6, 9, 10].forEach((m) => {
    const r = findRow(
      (x) =>
        x.counterparty === "Amazon Web Services EMEA SARL" &&
        +(x.valueDate || x.booked).slice(5, 7) === m,
    );
    const a = invoice({
      kind: "received",
      number: `EUINES26-${1040 + m}`,
      date: iso(2026, m, 2),
      counterparty: "Amazon Web Services EMEA SARL",
      nif: "LU00000077",
      country: "LU",
      idState: "lu",
      ivaCategory: "intra_community_service_acquisition_reverse_charge",
      operationType: "I",
      lines: [
        {
          description: "AWS cloud services",
          qty: 1,
          price: r ? r.amount : 2500,
          rate: "RATE_0",
          category: "software_suscripcion",
        },
      ],
      notes: "Inversión del sujeto pasivo.",
    });
    if (m !== 10) link(a, r);
  });
  link(
    invoice({
      kind: "received",
      number: "F0211",
      date: "2026-03-11",
      counterparty: "Mobles Estudi Vidal SL",
      nif: "B00000088",
      country: "ES",
      lines: [
        {
          description: "Mesa de trabajo regulable",
          qty: 1,
          price: 180000,
          rate: "RATE_21",
          category: "mobiliario_amortizable",
        },
        {
          description: "Estantería modular",
          qty: 2,
          price: 80000,
          rate: "RATE_21",
          category: "mobiliario_amortizable",
        },
      ],
    }),
    findRow((r) => r.counterparty === "Mobles Estudi Vidal SL"),
  );
  link(
    invoice({
      kind: "received",
      number: "FV-88213",
      date: "2026-02-02",
      counterparty: "PcComponentes y Multimedia SLU",
      nif: "B00000099",
      country: "ES",
      lines: [
        {
          description: "Portátil 14 pulgadas",
          qty: 1,
          price: 229900,
          rate: "RATE_21",
          category: "hardware_amortizable",
        },
      ],
    }),
    findRow((r) => r.counterparty.startsWith("PcComponentes")),
  );
  link(
    invoice({
      kind: "received",
      number: "RC-2026-55102",
      date: "2026-02-14",
      counterparty: "Mapfre España SA",
      nif: "A00000110",
      country: "ES",
      ivaCategory: "domestic_exempt",
      lines: [
        {
          description: "Póliza responsabilidad civil profesional",
          qty: 1,
          price: 31000,
          rate: "EXEMPT",
          category: "seguros_responsabilidad_civil",
        },
      ],
    }),
    findRow((r) => r.counterparty === "Mapfre España SA"),
  );
  link(
    invoice({
      kind: "received",
      number: "LI-IE-447102",
      date: "2026-05-19",
      counterparty: "LinkedIn Ireland Unlimited Company",
      nif: "IE00000121",
      country: "IE",
      idState: "ie",
      ivaCategory: "intra_community_service_acquisition_reverse_charge",
      operationType: "I",
      lines: [
        {
          description: "Sponsored content",
          qty: 1,
          price: 12000,
          rate: "RATE_0",
          category: "publicidad_marketing",
        },
      ],
    }),
    findRow((r) => r.counterparty.startsWith("LinkedIn")),
  );
  invoice({
    kind: "received",
    cls: "simplificada",
    number: "T-0412-33",
    date: "2026-10-09",
    counterparty: "Repsol Comercial de Productos Petrolíferos SA",
    nif: null,
    country: "ES",
    lines: [
      {
        description: "Gasolina 95",
        qty: 1,
        price: 5058,
        rate: "RATE_21",
        category: "vehiculo_combustible",
      },
    ],
    notes: "Ticket; no recipient NIF.",
  });
  invoice({
    kind: "received",
    number: "GT-2026-0917",
    date: "2026-09-02",
    counterparty: "Imprenta Gráficas Turia SL",
    nif: "B00000132",
    country: "ES",
    lines: [
      {
        description: "Impresión catálogo 500 uds",
        qty: 500,
        price: 256,
        rate: "RATE_21",
        category: "suministros_cliente_directos",
      },
    ],
    payment: "paid",
  });

  // Evidence links on a few movements.
  const docs = buildDocs(rows, invoices, findRow);
  return { rows, invoices, docs, batches: Object.values(batches), dupA };
}

export function buildDocs(
  rows: Movement[],
  invoices: Invoice[],
  findRow: (pred: (r: Movement) => boolean) => Movement | undefined,
): Doc[] {
  const inv = (num: string) => invoices.find((i) => i.number === num);
  const drafts: Omit<Doc, "sha" | "reviewSha">[] = [
    {
      id: "ev-arroyo-10",
      file: "factura-arroyo-2026-10.pdf",
      media: "pdf",
      added: "2026-10-04",
      kind: "received",
      state: "draft",
      draft: {
        supplier: ["Arroyo Asesores SL", "text_layer", "reconciled"],
        supplier_tax_id: ["B00000044", "text_layer", "reconciled"],
        invoice_number: ["AA-26/010", "text_layer", "reconciled"],
        invoice_date: ["2026-10-03", "text_layer", "anchored"],
        taxable_base: ["60.00", "text_layer", "reconciled"],
        iva_rate: ["21", "text_layer", "reconciled"],
        iva_amount: ["12.60", "text_layer", "reconciled"],
        grand_total: ["72.60", "text_layer", "reconciled"],
        currency: ["EUR", "text_layer", "reconciled"],
      },
      findings: [],
      suggestedRow: findRow(
        (r) =>
          r.counterparty === "Arroyo Asesores SL" &&
          (r.valueDate || r.booked).startsWith("2026-10"),
      ),
    },
    {
      id: "ev-repsol-0412",
      file: "ticket-repsol-0412.jpg",
      media: "image",
      added: "2026-10-10",
      kind: "received",
      state: "draft",
      draft: {
        supplier: ["Repsol E.S. Paterna", "vision", "anchored"],
        supplier_tax_id: ["A0000000?", "vision", "unanchored"],
        invoice_number: ["T-0412-33", "vision", "anchored"],
        invoice_date: ["2026-10-09", "vision", "anchored"],
        taxable_base: ["50.58", "vision", "anchored"],
        iva_rate: ["21", "vision", "anchored"],
        iva_amount: ["10.62", "vision", "anchored"],
        grand_total: ["61.21", "vision", "unanchored"],
      },
      findings: [
        {
          id: "b1f0c2a9d4e81a77",
          reason: "closure_discrepancy",
          field: "grand_total",
          detail: "Printed total 61.21 does not equal 50.58 + 10.62 = 61.20.",
          candidates: [
            { value: "61.20", note: "Base plus IVA" },
            { value: "61.21", note: "As printed" },
          ],
        },
        {
          id: "c7d2e19b04aa3f10",
          reason: "ambiguous_identity",
          field: "supplier_tax_id",
          detail: "The supplier NIF is partly unreadable on the ticket.",
          candidates: [],
        },
      ],
    },
    {
      id: "ev-nube-10",
      file: "factura-espacio-nube-oct.pdf",
      media: "pdf",
      added: "2026-10-02",
      kind: "received",
      state: "draft",
      draft: {
        supplier: ["Espacio Nube Coworking SL", "text_layer", "reconciled"],
        supplier_tax_id: ["B00000055", "text_layer", "anchored"],
        customer_tax_id: ["00000000T", "text_layer", "anchored"],
        invoice_number: ["ENC-202610-0187", "text_layer", "reconciled"],
        invoice_date: ["2026-10-01", "text_layer", "reconciled"],
        taxable_base: ["150.00", "text_layer", "reconciled"],
        iva_rate: ["21", "text_layer", "reconciled"],
        iva_amount: ["31.50", "text_layer", "reconciled"],
        grand_total: ["181.50", "text_layer", "reconciled"],
      },
      findings: [
        {
          id: "a93be0f1c2d47e55",
          reason: "ambiguous_identity",
          field: "supplier_tax_id",
          detail:
            "Two tax ids are printed: the coworking company and its management agent.",
          candidates: [
            { value: "B00000055", note: "Next to “Espacio Nube Coworking SL”" },
            { value: "B00000143", note: "In the footer, “Gestión Nube SL”" },
          ],
        },
      ],
    },
    {
      id: "ev-aws-1050",
      file: "aws-invoice-EUINES26-1050.pdf",
      media: "pdf",
      added: "2026-10-05",
      kind: "received",
      state: "draft",
      draft: {
        supplier: ["Amazon Web Services EMEA SARL", "text_layer", "reconciled"],
        supplier_tax_id: ["LU00000077", "text_layer", "reconciled"],
        invoice_number: ["EUINES26-1050", "text_layer", "reconciled"],
        invoice_date: ["2026-10-02", "text_layer", "reconciled"],
        taxable_base: ["31.12", "text_layer", "reconciled"],
        iva_rate: ["0", "text_layer", "anchored"],
        iva_amount: ["0.00", "text_layer", "anchored"],
        grand_total: ["31.12", "text_layer", "reconciled"],
      },
      findings: [
        {
          id: "f0e1d2c3b4a59687",
          reason: "undetermined_establishment",
          field: "counterparty_identification_state",
          detail:
            "Which Member State identifies the supplier for IVA is not stated in a way the reader can ground.",
          candidates: [
            { value: "lu", note: "From the LU prefix of the VAT number" },
          ],
        },
      ],
    },
    {
      id: "ev-mobles",
      file: "mobles-vidal-F0211.pdf",
      media: "pdf",
      added: "2026-03-12",
      kind: "received",
      state: "confirmed",
      invoice: inv("F0211")?.id,
      rowId: findRow((r) => r.counterparty === "Mobles Estudi Vidal SL")?.id,
      draft: {},
      findings: [],
    },
    {
      id: "ev-pcc",
      file: "pccomponentes-pedido-88213.pdf",
      media: "pdf",
      added: "2026-02-04",
      kind: "received",
      state: "confirmed",
      invoice: inv("FV-88213")?.id,
      rowId: findRow((r) => r.counterparty.startsWith("PcComponentes"))?.id,
      draft: {},
      findings: [],
    },
    {
      id: "ev-vodafone-09",
      file: "vodafone-2026-09.pdf",
      media: "pdf",
      added: "2026-09-09",
      kind: "received",
      state: "evidence",
      rowId: findRow(
        (r) =>
          r.counterparty === "Vodafone España SAU" &&
          (r.valueDate || r.booked).startsWith("2026-09"),
      )?.id,
      draft: {},
      findings: [],
    },
    {
      id: "ev-renfe",
      file: "renfe-billete-ZK21.pdf",
      media: "pdf",
      added: "2026-08-07",
      kind: "received",
      state: "evidence",
      rowId: findRow(
        (r) =>
          r.counterparty.startsWith("Renfe") &&
          (r.valueDate || r.booked).startsWith("2026-08"),
      )?.id,
      draft: {},
      findings: [],
    },
    {
      id: "ev-lumen-xml",
      file: "facturae-lumen-F2026-019.xml",
      media: "xml",
      added: "2026-09-29",
      kind: "issued",
      state: "draft",
      draft: {
        customer: ["Estudio Lumen SL", "exact_structured", "reconciled"],
        customer_tax_id: ["B00000011", "exact_structured", "reconciled"],
        invoice_number: ["F-2026-019", "exact_structured", "reconciled"],
        invoice_date: ["2026-09-28", "exact_structured", "reconciled"],
        taxable_base: ["1500.00", "exact_structured", "reconciled"],
        iva_rate: ["21", "exact_structured", "reconciled"],
        iva_amount: ["315.00", "exact_structured", "reconciled"],
        retencion_amount: ["225.00", "exact_structured", "reconciled"],
        grand_total: ["1815.00", "exact_structured", "reconciled"],
      },
      findings: [],
      note: "Structured Facturae: read deterministically, no model involved.",
    },
    {
      id: "ev-nh",
      file: "hotel-nh-madrid-atocha.pdf",
      media: "pdf",
      added: "2026-09-18",
      kind: null,
      state: "draft",
      draft: {
        supplier: ["NH Hotel Group SA", "text_layer", "anchored"],
        invoice_number: ["MAD-ATO-88123", "text_layer", "anchored"],
        invoice_date: ["2026-09-17", "text_layer", "anchored"],
        taxable_base: ["108.00", "text_layer", "reconciled"],
        iva_rate: ["10", "text_layer", "reconciled"],
        iva_amount: ["10.80", "text_layer", "reconciled"],
        grand_total: ["118.80", "text_layer", "reconciled"],
      },
      findings: [
        {
          id: "d4c3b2a1f0e9d8c7",
          reason: "unresolved_direction",
          field: "kind",
          detail:
            "Both parties appear in the header; the reader could not tell whether you issued or received it.",
          candidates: [
            { value: "received", note: "You are the guest" },
            { value: "issued", note: "" },
          ],
        },
      ],
    },
    {
      id: "ev-mapfre",
      file: "mapfre-poliza-rc-2026.pdf",
      media: "pdf",
      added: "2026-02-16",
      kind: "received",
      state: "confirmed",
      invoice: inv("RC-2026-55102")?.id,
      rowId: findRow((r) => r.counterparty === "Mapfre España SA")?.id,
      draft: {},
      findings: [],
    },
    {
      id: "ev-iberdrola-08",
      file: "iberdrola-agosto.pdf",
      media: "pdf",
      added: "2026-09-01",
      kind: "received",
      state: "paused",
      draft: {},
      findings: [],
      fallback:
        "The local reader was busy (inference slot in use). Nothing was read; extract again.",
    },
  ];
  const docs: Doc[] = drafts.map((d) => ({
    ...d,
    sha: hashHex("doc" + d.id),
    reviewSha: hashHex("rev" + d.id),
  }));
  docs.forEach((d) => {
    if (d.rowId) {
      const r = rows.find((x) => x.id === d.rowId);
      if (r) {
        if (d.state === "confirmed" || d.state === "evidence")
          r.evidenceId = d.id;
      }
    }
  });
  const ren = rows.find(
    (r) => r.counterparty.startsWith("Renfe") && r.evidenceId,
  );
  if (ren) ren.attachments = ["att-renfe-email"];
  return docs;
}

export const RULES: Rule[] = [
  {
    id: "r-reta",
    name: "Social security (RETA)",
    pattern: "SEGURIDAD SOCIAL|RETA",
    cls: "business",
    category: "cuotas_autonomos_ss",
    priority: 10,
    created: "2025-01-14",
    actor: "You",
  },
  {
    id: "r-traspaso",
    name: "Transfers between my accounts",
    pattern: "^TRASPASO",
    cls: "skipped",
    category: null,
    priority: 20,
    created: "2025-01-14",
    actor: "You",
  },
  {
    id: "r-aws",
    name: "Amazon Web Services",
    pattern: "AWS EMEA",
    cls: "business",
    category: "software_suscripcion",
    priority: 40,
    created: "2025-05-02",
    actor: "You",
  },
  {
    id: "r-mercadona",
    name: "Mercadona groceries",
    pattern: "MERCADONA",
    cls: "personal",
    category: null,
    priority: 50,
    created: "2025-01-20",
    actor: "You",
  },
  {
    id: "r-ocio",
    name: "Streaming subscriptions",
    pattern: "NETFLIX|SPOTIFY",
    cls: "personal",
    category: null,
    priority: 60,
    created: "2025-02-11",
    actor: "You",
  },
];
export const COUNTERPARTIES: Counterparty[] = [
  {
    name: "Amazon Web Services EMEA SARL",
    taxId: "LU00000077",
    country: "LU",
    scope: "EU, outside Spain",
    idState: "lu",
    confirmed: "2025-05-02",
    note: "VAT number on every invoice",
  },
  {
    name: "Adobe Systems Software Ireland Ltd",
    taxId: "IE00000154",
    country: "IE",
    scope: "EU, outside Spain",
    idState: "ie",
    confirmed: "2025-03-18",
    note: "",
  },
  {
    name: "LinkedIn Ireland Unlimited Company",
    taxId: "IE00000121",
    country: "IE",
    scope: "EU, outside Spain",
    idState: "ie",
    confirmed: "2026-05-20",
    note: "",
  },
  {
    name: "Harbor & Pine LLC",
    taxId: "US-EIN 00-0000165",
    country: "US",
    scope: "Third country",
    idState: null,
    confirmed: "2026-02-20",
    note: "Not established in the EU",
  },
  {
    name: "Udemy Netherlands BV",
    taxId: "NL00000176B01",
    country: "NL",
    scope: "Not confirmed",
    idState: null,
    confirmed: null,
    note: "",
  },
];
export const PRORRATA: ProrrataYear[] = [
  {
    year: 2026,
    regime: "General",
    provisional: "92%",
    source: "Seeded from 2025 definitive (Modelo 390, box 108)",
    definitive: "Not settled",
    sectors: [],
  },
  {
    year: 2025,
    regime: "General",
    provisional: "100%",
    source: "Seeded from 2024 definitive",
    definitive: "92%",
    sectors: [],
  },
];
export const CAPITAL_GOODS: CapitalGood[] = [
  {
    id: "bi-2026-001",
    description: "Desk and modular shelving",
    kind: "Mobiliario",
    acquired: 2026,
    ledgerRow: "Mobles Estudi Vidal SL · 12 Mar",
    cuota: 71400,
    prorrata: "92%",
    regularization: "2026–2030 (5 years)",
    disposal: null,
  },
];
export const INVENTORY: Inventory = {
  year: 2026,
  activity: "A03 · Graphic design",
  method: "FIFO",
  movements: [
    {
      id: "m-001",
      date: "2026-01-01",
      kind: "opening",
      qty: 120,
      unit: 450,
      base: 54000,
      note: "Art prints A3, carried from 2025",
    },
    {
      id: "m-002",
      date: "2026-03-20",
      kind: "purchase",
      qty: 200,
      unit: 410,
      base: 82000,
      note: "Gráficas Turia print run",
    },
    {
      id: "m-003",
      date: "2026-06-30",
      kind: "cogs",
      qty: 140,
      unit: null,
      base: null,
      note: "Sold at markets and online, 1H",
    },
    {
      id: "m-004",
      date: "2026-09-30",
      kind: "cogs",
      qty: 95,
      unit: null,
      base: null,
      note: "Sold Q3",
    },
  ],
  closing: null,
};
export const ASSETS: Asset[] = [
  {
    id: "aa-01",
    name: "MacBook Pro 14 (hardware)",
    acquired: "2026-02-03",
    base: 229900,
    method: "Linear, 25% per year",
    claimed: "2026 1T–3T: 431.06",
    revisions: 1,
  },
  {
    id: "aa-02",
    name: "Desk and shelving (mobiliario)",
    acquired: "2026-03-12",
    base: 340000,
    method: "Linear, 10% per year",
    claimed: "2026 1T–3T: 187.40",
    revisions: 2,
  },
];
export const CONSENT: Consent[] = [
  {
    at: "2026-09-18T19:02:00Z",
    file: "hotel-nh-madrid-atocha.pdf",
    provider: "Agent (off-host)",
    acknowledged: true,
    derived: [
      "Draft review d4c3b2a1…",
      "Rendered page images (in memory only)",
    ],
    effect: "Recorded before dispatch",
  },
];
