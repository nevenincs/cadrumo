import type { IconName } from "./Icon";
import type {
  Cls,
  ClsDef,
  Direction,
  Lifecycle,
  Option,
  ReviewStatus,
} from "./types";

/* ── Vocabularies. Labels are English chrome strings; tokens stay canonical.
   In the product these come from the registry projections and the locale
   catalogues; here they are written once. ─────────────────────────────── */

export const CLS: Record<Cls, ClsDef> = {
  business: {
    label: "Business",
    token: "BUSINESS",
    status: "reviewed",
    assignable: true,
  },
  personal: {
    label: "Personal",
    token: "PERSONAL",
    status: "reviewed",
    assignable: true,
  },
  mixed: {
    label: "Mixed",
    token: "MIXED",
    status: "reviewed",
    assignable: true,
  },
  pending: {
    label: "Not classified yet",
    token: "NOT_YET_PROCESSED",
    status: "pending",
  },
  unclassified: {
    label: "Processed, unclassified",
    token: "PROCESSED_UNCLASSIFIED",
    status: "pending",
  },
  failed: {
    label: "Failed validation",
    token: "FAILED_VALIDATION",
    status: "pending",
  },
  skipped: {
    label: "Skipped by rule",
    token: "SKIPPED_BY_RULE",
    status: "skipped",
  },
  excluded: {
    label: "Excluded",
    token: "REVIEWED_EXCLUDED",
    status: "excluded",
  },
};
export const CLASSIFIED = new Set<string>(["business", "personal", "mixed"]);
export const DEDUCTION_KIND: Record<string, string> = {
  domestic_current: "Domestic, current",
  domestic_investment: "Domestic, investment good",
  import_current: "Import, current",
  import_investment: "Import, investment good",
  intra_eu_current: "Intra-EU, current",
  intra_eu_investment: "Intra-EU, investment good",
  reagp_compensation: "REAGP compensation",
  rectification: "Rectification",
  investment_goods_regularisation: "Investment goods regularisation",
};
export const REVIEW_STATUS: Record<
  ReviewStatus,
  { label: string; icon: IconName }
> = {
  pending: { label: "Pending", icon: "unknown" },
  reviewed: { label: "Reviewed", icon: "check" },
  skipped: { label: "Skipped", icon: "minus" },
  excluded: { label: "Excluded", icon: "eyeOff" },
};
export const DIRECTION: Record<
  Direction,
  { label: string; token: string; icon: IconName }
> = {
  in: { label: "In", token: "INCOMING", icon: "moneyIn" },
  out: { label: "Out", token: "OUTGOING", icon: "moneyOut" },
  transfer: { label: "Transfer", token: "INTERNAL_TRANSFER", icon: "swap" },
};
export const LIFECYCLE: Record<Lifecycle, { label: string; token: string }> = {
  active: { label: "Active", token: "ACTIVE" },
  archived: { label: "Archived", token: "ARCHIVED" },
  stashed: { label: "Set aside", token: "STASHED" },
  split: { label: "Split", token: "SPLIT" },
};

export const FAMILIES: [string, string, string[]][] = [
  [
    "social_security",
    "Social security",
    ["cuotas_colegiales", "cuotas_autonomos_ss", "mutualidad_alternativa"],
  ],
  [
    "premises",
    "Business premises",
    ["arrendamiento_local", "ibi_local_afecto", "suministros_local_afecto"],
  ],
  [
    "home_office_suministros",
    "Home-office utilities",
    [
      "suministros_home_office_luz",
      "suministros_home_office_agua",
      "suministros_home_office_gas",
      "suministros_home_office_internet",
      "telefonia_fija",
    ],
  ],
  [
    "home_office_ownership",
    "Home-office ownership",
    [
      "amortizacion_vivienda_afecto",
      "ibi_vivienda_afecto",
      "comunidad_vivienda_afecto",
      "arrendamiento_vivienda_afecto",
    ],
  ],
  ["telecoms", "Telecoms", ["telefonia_movil"]],
  [
    "office",
    "Office and equipment",
    [
      "material_oficina",
      "software_suscripcion",
      "hardware_amortizable",
      "mobiliario_amortizable",
      "reparaciones_conservacion",
      "publicidad_marketing",
      "formacion_profesional",
    ],
  ],
  [
    "vehicle",
    "Vehicle",
    [
      "vehiculo_combustible",
      "vehiculo_mantenimiento",
      "vehiculo_seguro",
      "vehiculo_peaje",
      "vehiculo_parking",
    ],
  ],
  [
    "meals",
    "Meals",
    ["manutencion_dietas_nacional", "manutencion_dietas_extranjero"],
  ],
  [
    "professional_services",
    "Professional services",
    ["asesoria_fiscal", "asesoria_juridica", "asesoria_contable"],
  ],
  ["travel", "Travel", ["viajes_transporte", "viajes_alojamiento"]],
  [
    "insurance",
    "Insurance",
    ["seguros_responsabilidad_civil", "seguros_salud_autonomo"],
  ],
  ["financial", "Financial", ["gastos_bancarios", "gastos_financieros"]],
  [
    "direct_costs",
    "Direct costs",
    ["suministros_cliente_directos", "subcontratacion"],
  ],
  ["taxes", "Taxes", ["tributos_fiscalmente_deducibles"]],
];
export const CATEGORY_LABEL: Record<string, string> = {
  cuotas_colegiales: "Professional association fees",
  cuotas_autonomos_ss: "RETA contributions",
  mutualidad_alternativa: "Mutualidad (RETA alternative)",
  arrendamiento_local: "Premises rent",
  ibi_local_afecto: "IBI on premises",
  suministros_local_afecto: "Premises utilities",
  suministros_home_office_luz: "Home office: electricity",
  suministros_home_office_agua: "Home office: water",
  suministros_home_office_gas: "Home office: gas",
  suministros_home_office_internet: "Home office: internet",
  telefonia_fija: "Landline",
  amortizacion_vivienda_afecto: "Home office: depreciation",
  ibi_vivienda_afecto: "Home office: IBI",
  comunidad_vivienda_afecto: "Home office: community fees",
  arrendamiento_vivienda_afecto: "Home office: rent",
  telefonia_movil: "Mobile phone",
  material_oficina: "Office supplies",
  software_suscripcion: "Software subscriptions",
  hardware_amortizable: "Hardware (depreciable)",
  mobiliario_amortizable: "Furniture (depreciable)",
  reparaciones_conservacion: "Repairs and upkeep",
  publicidad_marketing: "Advertising and marketing",
  formacion_profesional: "Professional training",
  vehiculo_combustible: "Fuel",
  vehiculo_mantenimiento: "Vehicle maintenance",
  vehiculo_seguro: "Vehicle insurance",
  vehiculo_peaje: "Tolls",
  vehiculo_parking: "Parking",
  manutencion_dietas_nacional: "Meals in Spain",
  manutencion_dietas_extranjero: "Meals abroad",
  asesoria_fiscal: "Tax advisory (gestoría)",
  asesoria_juridica: "Legal advisory",
  asesoria_contable: "Accounting services",
  viajes_transporte: "Travel: transport",
  viajes_alojamiento: "Travel: accommodation",
  seguros_responsabilidad_civil: "Liability insurance",
  seguros_salud_autonomo: "Health insurance",
  gastos_bancarios: "Bank fees",
  gastos_financieros: "Financial costs",
  suministros_cliente_directos: "Direct client supplies",
  subcontratacion: "Subcontracting",
  tributos_fiscalmente_deducibles: "Deductible taxes (tributos)",
};
export const CATEGORY_FAMILY: Record<string, string> = {};
FAMILIES.forEach(([fam, , cats]) =>
  cats.forEach((c) => (CATEGORY_FAMILY[c] = fam)),
);
export const FAMILY_LABEL: Record<string, string> = Object.fromEntries(
  FAMILIES.map(([k, l]) => [k, l]),
);
export const CATEGORY_OPTIONS: Option[] = FAMILIES.flatMap(
  ([, famLabel, cats]) =>
    cats.map((c) => ({
      value: c,
      label: CATEGORY_LABEL[c] ?? c,
      group: famLabel,
      token: c,
    })),
);

export const IVA_GROUPS: [string, [string, string, number?][]][] = [
  [
    "Domestic",
    [
      ["domestic_general", "General rate", 0.21],
      ["domestic_reduced", "Reduced rate", 0.1],
      ["domestic_super_reduced", "Super-reduced rate", 0.04],
      ["domestic_zero", "Zero rate", 0],
      ["domestic_exempt", "Exempt"],
      ["domestic_not_subject", "Not subject (domestic)"],
    ],
  ],
  ["Not subject", [["operacion_no_sujeta", "Operación no sujeta"]]],
  [
    "Intra-community",
    [
      ["intra_community_supply", "Intra-community supply"],
      ["intra_community_triangulation", "Triangulation"],
      ["intra_community_service_supply", "EU service supply"],
      [
        "intra_community_service_acquisition_reverse_charge",
        "EU service acquisition (reverse charge)",
      ],
      [
        "intra_community_acquisition_reverse_charge",
        "EU goods acquisition (reverse charge)",
      ],
    ],
  ],
  [
    "Exports and imports",
    [
      ["export_third_country_zero_rated", "Export, third country"],
      ["export_assimilated_zero_rated", "Export-assimilated"],
      ["import_third_country", "Import, third country"],
    ],
  ],
  [
    "Special regimes",
    [
      ["domestic_reverse_charge", "Domestic reverse charge (ISP)"],
      ["recargo_equivalencia", "Recargo de equivalencia"],
      ["regimen_simplificado", "Régimen simplificado"],
      ["reagp_compensation", "REAGP compensation"],
    ],
  ],
  [
    "Anomalies",
    [
      ["erroneous_invoice", "Erroneous invoice"],
      ["unknown", "Unknown"],
    ],
  ],
];
export const IVA_LABEL: Record<string, string> = {};
export const IVA_RATE: Record<string, number> = {};
export const IVA_OPTIONS: Option[] = [];
IVA_GROUPS.forEach(([g, items]) =>
  items.forEach(([k, l, r]) => {
    IVA_LABEL[k] = l;
    if (r !== undefined) IVA_RATE[k] = r;
    IVA_OPTIONS.push({
      value: k,
      label: l,
      group: g,
      token: k,
      note: r !== undefined ? pct(r) : undefined,
    });
  }),
);
export function pct(f: number) {
  return `${+(f * 100).toFixed(2)}%`;
}

export const IRPF: Record<string, string> = {
  actividad_economica: "Economic activity",
  arrendamiento_local: "Rental: business premises",
  arrendamiento_vivienda_afecto: "Rental: home used for the activity",
  trabajo: "Employment income (trabajo)",
};
export const IRPF_OPTIONS = Object.entries(IRPF).map(([k, l]) => ({
  value: k,
  label: l,
  token: k,
}));

export const REASONS: Record<string, string> = {
  missing_business_classification: "Missing classification",
  missing_category: "Missing category",
  missing_taxable_base: "Missing taxable base",
  missing_iva_amount: "Missing IVA amount",
  missing_iva_rate: "Missing IVA rate",
  missing_eur_tax_substrate: "Missing EUR tax figures",
  missing_counterparty_identification_state: "Missing VAT-identification state",
  domestic_identification_on_intra_community_transaction:
    "Spanish VAT id on an intra-community movement",
  eu_member_state_on_export_transaction: "EU state on an export",
  missing_counterparty_establishment_on_export:
    "Missing establishment on an export",
  inadmissible_deduction_classification: "Inadmissible deduction",
  missing_proportionality_reference: "Mixed without a usage ratio",
  unsupported_currency: "Foreign currency without EUR rate",
  unsupported_period: "Unsupported period",
  censo_ratio_mismatch: "Censo ratio mismatch",
  missing_home_office_afectacion: "Missing home-office afectación",
  anomaly_non_declarable_iva_category: "Non-declarable IVA category",
  anomaly_non_declarable_recargo_equivalencia: "Non-declarable recargo",
};
export const IMPORT_ISSUES: Record<string, string> = {
  "original-file": "Original file",
  gap: "Gap in statement",
  duplicate: "Possible duplicate",
  parser: "Parser note",
};

export const EU_STATES = [
  "at",
  "be",
  "bg",
  "cy",
  "cz",
  "de",
  "dk",
  "ee",
  "es",
  "fi",
  "fr",
  "gr",
  "hr",
  "hu",
  "ie",
  "it",
  "lt",
  "lu",
  "lv",
  "mt",
  "nl",
  "pl",
  "pt",
  "ro",
  "se",
  "si",
  "sk",
  "xi",
];
export const PERIOD_CODES: string[] = ["1T", "2T", "3T", "4T"];
export const MONTHS = [
  "01",
  "02",
  "03",
  "04",
  "05",
  "06",
  "07",
  "08",
  "09",
  "10",
  "11",
  "12",
];
export const MONTH_LABEL = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
];
export const TODAY = "2026-10-23";

export const PROVIDERS: [string, string][] = [
  ["auto", "Detect automatically"],
  ["n26-csv", "N26 CSV"],
  ["csv", "CSV (other bank)"],
  ["ofx", "OFX"],
  ["qfx", "QFX"],
  ["xlsx", "XLSX"],
  ["xls", "XLS (provisional)"],
  ["pdf-n26", "N26 statement PDF"],
];
export const INVOICE_CLASS: Record<string, string> = {
  ordinaria: "Ordinaria",
  simplificada: "Simplificada",
  rectificativa: "Rectificativa",
};
export const PAYMENT: Record<string, string> = {
  paid: "Paid",
  pending: "Pending",
  partial: "Partially paid",
  overdue: "Overdue",
  cancelled: "Cancelled",
};
export const LINE_RATES: [string, string, number][] = [
  ["RATE_0", "0%", 0],
  ["RATE_2", "2%", 0.02],
  ["RATE_4", "4%", 0.04],
  ["RATE_5", "5%", 0.05],
  ["RATE_7.5", "7.5%", 0.075],
  ["RATE_10", "10%", 0.1],
  ["RATE_21", "21%", 0.21],
  ["EXEMPT", "Exempt", 0],
  ["NOT_SUBJECT", "Not subject", 0],
];
export const OPERATION_TYPES: Record<string, string> = {
  E: "E · Intra-community supply",
  A: "A · Intra-community acquisition",
  S: "S · Service supplied",
  I: "I · Service acquired",
  T: "T · Triangulation",
  M: "M · Goods after import",
  H: "H · Goods after import (representative)",
  R: "R · Consignment transfer",
  D: "D · Consignment return",
  C: "C · Consignment substitution",
};
export const FIELD_ORIGIN: Record<string, string> = {
  exact_structured: "Read from the e-invoice",
  text_layer: "Read from the PDF",
  text_rules: "Read from the PDF text",
  vision: "Read from the image",
  tabular_mapped: "From a spreadsheet column",
  operator: "Entered by you",
  derived: "Worked out from other fields",
};
export const GROUNDING: Record<string, string> = {
  reconciled: "totals agree",
  anchored: "found next to its label",
  unanchored: "not confirmed on the page",
};
export const BLOCK_REASON: Record<string, string> = {
  closure_discrepancy: "Totals do not close",
  ambiguous_identity: "Ambiguous party identity",
  unresolved_direction: "Issued or received is unclear",
  contradicted_regime: "Regime legend contradicts the figures",
  undetermined_establishment: "Establishment undetermined",
  unmodelled_invoice_class: "Invoice class not modelled",
  contradicted_invoice_class: "Invoice class contradicted",
};
