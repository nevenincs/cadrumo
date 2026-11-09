// The registry's closed lists for a ledger entry form as the window holds them
// once `ledger.entry-options` has served them: the IVA and IRPF categories,
// the spending categories with their families, the categories a usage ratio
// applies to, the invoice classes, the premises situations, the prorrata
// provenances and sector letters, the capital goods kinds and disposals, and
// the statement formats this installation parses.
// The window keeps no list of its own, so until they are served, or where the
// read failed, each is empty and `state` says which. Nothing here decides
// whether a value is allowed; the ledger does.

import type { LedgerEntryOptionsResult } from "./ledgerSetup";

/** Whether the lists are being read, were read, or could not be. */
export type VocabularyState = "loading" | "unavailable" | "ready";

export type ServedVocabulary = {
  state: VocabularyState;
  ivaCategories: readonly string[];
  irpfCategories: readonly string[];
  /** The spending categories by the family the registry files them under,
   * in the registry's order. */
  categoryFamilies: readonly (readonly [string, readonly string[]])[];
  /** Every spending category, family by family. */
  categories: readonly string[];
  /** The spending categories a business-use share applies to. */
  usageRatioCategories: readonly string[];
  invoiceClasses: readonly string[];
  /** The invoice class the registry files as the plain one, the simplified
   * one and the corrective one; null where none is served with that group. */
  defaultClass: string | null;
  simplifiedClass: string | null;
  correctiveClass: string | null;
  premisesSituations: readonly string[];
  prorrataProvenances: readonly string[];
  sectorLetters: readonly string[];
  capitalKinds: readonly string[];
  capitalDisposals: readonly string[];
  /** The statement formats an import offers: those whose parser this
   * installation carries. */
  importFormats: readonly string[];
  /** The currency a new movement is offered when no own account names one;
   * null until it is served. */
  defaultCurrency: string | null;
};

const NONE: readonly string[] = [];

/** What the window holds before anything is served, outside the page, and
 * where the read failed: no value of any list. */
export const NO_VOCABULARY: ServedVocabulary = {
  state: "unavailable",
  ivaCategories: NONE,
  irpfCategories: NONE,
  categoryFamilies: [],
  categories: NONE,
  usageRatioCategories: NONE,
  invoiceClasses: NONE,
  defaultClass: null,
  simplifiedClass: null,
  correctiveClass: null,
  premisesSituations: NONE,
  prorrataProvenances: NONE,
  sectorLetters: NONE,
  capitalKinds: NONE,
  capitalDisposals: NONE,
  importFormats: NONE,
  defaultCurrency: null,
};

/** The lists out of a served answer; with none, the state says why there are
 * none. */
export function servedVocabulary(
  result: LedgerEntryOptionsResult | null,
  state: VocabularyState,
): ServedVocabulary {
  if (result === null) return { ...NO_VOCABULARY, state };
  const values = (family: string): readonly string[] =>
    result.families
      .find((served) => served.family === family)
      ?.options.map((option) => option.value) ?? NONE;
  const classOfGroup = (group: string): string | null =>
    result.families
      .find((served) => served.family === "invoice_class")
      ?.options.find((option) => option.group === group)?.value ?? null;
  const families = new Map<string, string[]>();
  for (const family of result.families)
    if (family.family === "spending_category")
      for (const option of family.options) {
        const group = option.group ?? "";
        families.set(group, [...(families.get(group) ?? []), option.value]);
      }
  const categoryFamilies = [...families].map(
    ([family, members]) => [family, members] as const,
  );
  return {
    state,
    ivaCategories: values("iva_category"),
    irpfCategories: values("irpf_category"),
    categoryFamilies,
    categories: categoryFamilies.flatMap(([, members]) => members),
    usageRatioCategories: values("usage_ratio_category"),
    invoiceClasses: values("invoice_class"),
    defaultClass: classOfGroup("default"),
    simplifiedClass: classOfGroup("simplified"),
    correctiveClass: classOfGroup("corrective"),
    premisesSituations: values("premises_situation"),
    prorrataProvenances: values("prorrata_provenance"),
    sectorLetters: values("prorrata_sector_letter"),
    capitalKinds: values("capital_good_kind"),
    capitalDisposals: values("capital_good_disposal"),
    importFormats: values("import_format"),
    defaultCurrency: result.default_currency || null,
  };
}

/** The family a spending category is filed under, or null for an id not
 * served. */
export function categoryFamily(
  vocabulary: ServedVocabulary,
  category: string,
): string | null {
  return (
    vocabulary.categoryFamilies.find(([, members]) =>
      members.includes(category),
    )?.[0] ?? null
  );
}

/** Whether `id` is a served spending category. */
export const isSpendingCategory = (
  vocabulary: ServedVocabulary,
  id: string,
): boolean => vocabulary.categories.includes(id);

/** Whether a business-use share applies to `category`. */
export const takesShare = (
  vocabulary: ServedVocabulary,
  category: string,
): boolean => vocabulary.usageRatioCategories.includes(category);

/** The families and members a business-use share applies to, in the
 * registry's order; a family none of whose members takes one is left out. */
export function shareCategoryFamilies(
  vocabulary: ServedVocabulary,
): readonly (readonly [string, readonly string[]])[] {
  return vocabulary.categoryFamilies.flatMap(([family, members]) => {
    const sharing = members.filter((member) => takesShare(vocabulary, member));
    return sharing.length ? [[family, sharing] as const] : [];
  });
}
