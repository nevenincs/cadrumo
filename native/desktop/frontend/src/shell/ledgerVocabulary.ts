// The ledger's closed vocabularies as the page names them: the spending
// categories and their families, the IVA categories and the IRPF categories.
// They mirror the published registry's catalogues, which stay the authority;
// a test holds this copy to the registry's own lists. The page shows each by
// its localized label, and an id it does not know as the id itself, never as
// a guess.

/** The spending categories, by family, in the registry's order. */
export const SPENDING_CATEGORY_FAMILIES = [
  [
    "social_security",
    ["cuotas_colegiales", "cuotas_autonomos_ss", "mutualidad_alternativa"],
  ],
  [
    "premises",
    ["arrendamiento_local", "ibi_local_afecto", "suministros_local_afecto"],
  ],
  [
    "home_office_suministros",
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
    [
      "amortizacion_vivienda_afecto",
      "ibi_vivienda_afecto",
      "comunidad_vivienda_afecto",
      "arrendamiento_vivienda_afecto",
    ],
  ],
  ["telecoms", ["telefonia_movil"]],
  [
    "office",
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
    [
      "vehiculo_combustible",
      "vehiculo_mantenimiento",
      "vehiculo_seguro",
      "vehiculo_peaje",
      "vehiculo_parking",
    ],
  ],
  ["meals", ["manutencion_dietas_nacional", "manutencion_dietas_extranjero"]],
  [
    "professional_services",
    ["asesoria_fiscal", "asesoria_juridica", "asesoria_contable"],
  ],
  ["travel", ["viajes_transporte", "viajes_alojamiento"]],
  ["insurance", ["seguros_responsabilidad_civil", "seguros_salud_autonomo"]],
  ["financial", ["gastos_bancarios", "gastos_financieros"]],
  ["direct_costs", ["suministros_cliente_directos", "subcontratacion"]],
  ["taxes", ["tributos_fiscalmente_deducibles"]],
] as const satisfies readonly (readonly [string, readonly string[]])[];

export type SpendingCategoryFamily =
  (typeof SPENDING_CATEGORY_FAMILIES)[number][0];
export type SpendingCategory =
  (typeof SPENDING_CATEGORY_FAMILIES)[number][1][number];

/** Every spending category, family by family. */
export const SPENDING_CATEGORIES: readonly SpendingCategory[] =
  SPENDING_CATEGORY_FAMILIES.flatMap(([, members]) => members);

const FAMILY_OF = new Map<string, SpendingCategoryFamily>(
  SPENDING_CATEGORY_FAMILIES.flatMap(([family, members]) =>
    members.map((member) => [member, family] as const),
  ),
);

/** The family a category belongs to, or null for an id the page does not
 * know. */
export function categoryFamily(
  category: string,
): SpendingCategoryFamily | null {
  return FAMILY_OF.get(category) ?? null;
}

export function isSpendingCategory(id: string): id is SpendingCategory {
  return FAMILY_OF.has(id);
}

/** The spending categories whose deduction the registry measures by a
 * usage ratio, personal or home-area, in the registry's order: the ones a
 * business-use share applies to, so a Mixed movement takes one of them. */
export const USAGE_RATIO_CATEGORIES = [
  "arrendamiento_vivienda_afecto",
  "suministros_home_office_luz",
  "suministros_home_office_agua",
  "suministros_home_office_gas",
  "suministros_home_office_internet",
  "amortizacion_vivienda_afecto",
  "ibi_vivienda_afecto",
  "comunidad_vivienda_afecto",
  "telefonia_fija",
] as const satisfies readonly SpendingCategory[];

const TAKES_SHARE = new Set<string>(USAGE_RATIO_CATEGORIES);

/** Whether a business-use share applies to `category`. */
export const takesShare = (category: string) => TAKES_SHARE.has(category);

/** The families and their members a business-use share applies to, in the
 * registry's order; a family none of whose members takes one is left out. */
export const SHARE_CATEGORY_FAMILIES: readonly (readonly [
  SpendingCategoryFamily,
  readonly SpendingCategory[],
])[] = SPENDING_CATEGORY_FAMILIES.flatMap(([family, members]) => {
  const sharing = members.filter((member) => TAKES_SHARE.has(member));
  return sharing.length ? [[family, sharing] as const] : [];
});

/** The IVA categories of the registry's regulation catalogue. */
export const IVA_CATEGORIES = [
  "domestic_general",
  "domestic_reduced",
  "domestic_super_reduced",
  "domestic_zero",
  "domestic_exempt",
  "domestic_not_subject",
  "domestic_reverse_charge",
  "intra_community_supply",
  "intra_community_acquisition_reverse_charge",
  "intra_community_triangulation",
  "export_third_country_zero_rated",
  "export_assimilated_zero_rated",
  "import_third_country",
  "recargo_equivalencia",
  "regimen_simplificado",
  "reagp_compensation",
  "operacion_no_sujeta",
  "erroneous_invoice",
  "unknown",
  "intra_community_service_supply",
  "intra_community_service_acquisition_reverse_charge",
] as const;
export type IvaCategory = (typeof IVA_CATEGORIES)[number];
export const isIvaCategory = (id: string): id is IvaCategory =>
  (IVA_CATEGORIES as readonly string[]).includes(id);

/** The IRPF categories of the registry's ledger taxonomy. */
export const IRPF_CATEGORIES = [
  "actividad_economica",
  "arrendamiento_local",
  "arrendamiento_vivienda_afecto",
  "trabajo",
] as const;
export type IrpfCategory = (typeof IRPF_CATEGORIES)[number];
export const isIrpfCategory = (id: string): id is IrpfCategory =>
  (IRPF_CATEGORIES as readonly string[]).includes(id);

/** A movement's classifications: the three a person decides, then the
 * dispositions the product sets. */
export const CLASSIFICATIONS = [
  "BUSINESS",
  "PERSONAL",
  "MIXED",
  "NOT_YET_PROCESSED",
  "PROCESSED_UNCLASSIFIED",
  "SKIPPED_BY_RULE",
  "FAILED_VALIDATION",
  "REVIEWED_EXCLUDED",
] as const;
export type Classification = (typeof CLASSIFICATIONS)[number];
export const isClassification = (id: string): id is Classification =>
  (CLASSIFICATIONS as readonly string[]).includes(id);

export const DIRECTIONS = [
  "INCOMING",
  "OUTGOING",
  "INTERNAL_TRANSFER",
] as const;
export type Direction = (typeof DIRECTIONS)[number];
export const isDirection = (id: string): id is Direction =>
  (DIRECTIONS as readonly string[]).includes(id);

export const LIFECYCLE_STATES = [
  "ACTIVE",
  "ARCHIVED",
  "STASHED",
  "SPLIT",
] as const;
export type LifecycleState = (typeof LIFECYCLE_STATES)[number];
export const isLifecycleState = (id: string): id is LifecycleState =>
  (LIFECYCLE_STATES as readonly string[]).includes(id);

/** What an import marked on a movement, as the list filters it. */
export const IMPORT_ISSUES = [
  "original-file",
  "gap",
  "duplicate",
  "parser",
] as const;
export type ImportIssue = (typeof IMPORT_ISSUES)[number];
