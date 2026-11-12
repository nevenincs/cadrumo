import type { InventoryOptionsResult } from "../../../shell/ledgerSetup";

// ---- What the backend offers -------------------------------------------------
//
// Every closed choice a form offers is read from the backend, which serves
// each with the key of its word. Nothing here lists a method, a kind, a
// reason or a basis.

/** What a form treats specially among the choices the backend serves. */
export type OptionRole =
  "cost_check" | "iva_check" | "count_authority" | "purchase";
/** One choice the backend serves, the key of its word, and the part it plays
 * in a form where it plays one. */
export type Served = {
  value: string;
  label_key: string;
  role?: string | null;
  effect_key?: string | null;
};
/** The choices served, by the family they belong to. */
export type Offers = Readonly<Record<string, readonly Served[]>>;
/** What the builders judge a request by: the values of each family, and the
 * value that plays each role. */
export type Vocabulary = {
  readonly values: Readonly<Record<string, readonly string[]>>;
  readonly roles: Readonly<Partial<Record<OptionRole, string>>>;
};

export const NO_OFFERS: Offers = {};
export const NO_VOCABULARY: Vocabulary = { values: {}, roles: {} };

export const offersOf = (result: InventoryOptionsResult): Offers =>
  Object.fromEntries(
    result.families.map((found) => [found.family, found.options]),
  );

const ROLES: readonly OptionRole[] = [
  "cost_check",
  "iva_check",
  "count_authority",
  "purchase",
];

export const vocabularyOf = (offers: Offers): Vocabulary => ({
  values: Object.fromEntries(
    Object.entries(offers).map(([family, options]) => [
      family,
      options.map((option) => option.value),
    ]),
  ),
  roles: Object.fromEntries(
    ROLES.flatMap((role) => {
      const found = Object.values(offers)
        .flat()
        .find((option) => option.role === role);
      return found ? [[role, found.value]] : [];
    }),
  ),
});

/** Whether a value is the one that plays a role. */
export const plays = (
  vocabulary: Vocabulary,
  role: OptionRole,
  value: string | undefined,
): boolean => value !== undefined && vocabulary.roles[role] === value;

/** What a price, or one of its extra costs, can rest on: the served kinds of
 * proof less the two checks. */
export const priceKinds = (vocabulary: Vocabulary): readonly string[] =>
  (vocabulary.values.acquisition_evidence_kind ?? []).filter(
    (kind) =>
      !plays(vocabulary, "cost_check", kind) &&
      !plays(vocabulary, "iva_check", kind),
  );

/** Where the words of each stored token are kept, by family. */
export const LABEL_FAMILY = {
  valuation_method: "application.inventory.labels.valuation_method.",
  movement_kind: "application.inventory.labels.movement_kind.",
  attributable_cost_kind:
    "application.inventory.labels.attributable_cost_kind.",
  acquisition_evidence_kind:
    "application.inventory.labels.acquisition_evidence_kind.",
  correction_reason: "application.inventory.labels.correction_reason.",
  retirement_reason: "application.inventory.labels.retirement_reason.",
  history_kind: "application.inventory.labels.history_kind.",
  closing_authority: "application.inventory.labels.closing_authority.",
  closing_valuation_basis:
    "application.inventory.labels.closing_valuation_basis.",
  decision_evidence_role:
    "application.inventory.labels.decision_evidence_role.",
  physical_evidence_role:
    "application.inventory.labels.physical_evidence_role.",
} as const;
export type LabelFamily = keyof typeof LABEL_FAMILY;

/** The word for a stored token; a token without one is not named, never
 * shown as the token. */
export function wordOf(
  t: (key: string) => string,
  family: LabelFamily,
  token: string | null | undefined,
): string {
  if (token === null || token === undefined || token === "")
    return t("desktop.ledger.stock.unnamed");
  const key = `${LABEL_FAMILY[family]}${token}`;
  const said = t(key);
  return said === key ? t("desktop.ledger.stock.unnamed") : said;
}

/** The word for a stored token: the one the backend serves for it, else the
 * word of its family, else unknown. */
export function wordFrom(
  t: (key: string) => string,
  offers: Offers,
  family: LabelFamily,
  token: string | null | undefined,
): string {
  const served = (offers[family] ?? []).find((found) => found.value === token);
  return served ? servedWord(t, served) : wordOf(t, family, token);
}

/** The word a served choice carries, by its own key. */
export function servedWord(t: (key: string) => string, served: Served): string {
  const said = t(served.label_key);
  return said === served.label_key ? t("desktop.ledger.stock.unnamed") : said;
}

/** The sentence the backend serves for what choosing a value does; null
 * where none is served or its words are missing. */
export function effectWord(
  t: (key: string) => string,
  offers: Offers,
  family: string,
  token: string,
): string | null {
  const key = (offers[family] ?? []).find(
    (found) => found.value === token,
  )?.effect_key;
  if (!key) return null;
  const said = t(key);
  return said === key ? null : said;
}

export type ProofSlotKey = "price" | "cost_check" | "iva_check";

/** The kinds a slot's file can be: a check has the one kind of its own. */
export function slotKinds(
  slot: ProofSlotKey,
  vocabulary: Vocabulary,
): readonly string[] {
  if (slot === "price") return priceKinds(vocabulary);
  const own =
    vocabulary.roles[slot === "cost_check" ? "cost_check" : "iva_check"];
  return own === undefined ? [] : [own];
}
