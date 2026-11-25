import "./support/servedLimits";
import { expect, test } from "@playwright/test";
import {
  categoryLabel,
  ivaCategoryLabel,
  vocabularyEmpty,
} from "../src/components/ledger/movements/movementWords";
import { parseCell } from "../src/components/ledger/editing/editingModel";
import { classifyCells } from "../src/shell/ledgerCommands";
import { EMPTY_CONTENT } from "../src/shell/ledgerStage";
import {
  NO_VOCABULARY,
  categoryFamily,
  servedVocabulary,
  shareCategoryFamilies,
} from "../src/shell/ledgerServedVocabulary";
import { servedDraftCurrency } from "../src/shell/ledgerMovementReads";
import { hexId, movement } from "./support/ledger";
import { SERVED } from "./support/servedVocabulary";
import { recordedCheck } from "./support/stagedCheck";
import { label } from "./support/strings";

// The registry's lists the window holds once `ledger.entry-options` has
// served them, and what it does while they are not: nothing is offered, a
// stored id shows as itself, and the picker says why it is empty. No page is
// opened.

const t = (key: string) => label(key);
const LOADING = servedVocabulary(null, "loading");
const UNAVAILABLE = servedVocabulary(null, "unavailable");

test("the lists are the served answer, in its order and grouped as it groups", () => {
  expect(SERVED.state).toBe("ready");
  expect(SERVED.categories.length).toBeGreaterThan(0);
  expect(SERVED.categoryFamilies.flatMap(([, members]) => members)).toEqual(
    SERVED.categories,
  );
  // A category is filed under one family, the one the answer names.
  expect(new Set(SERVED.categories).size).toBe(SERVED.categories.length);
  const [family, members] = SERVED.categoryFamilies[0]!;
  expect(categoryFamily(SERVED, members[0]!)).toBe(family);
  expect(categoryFamily(SERVED, "not_a_served_category")).toBeNull();
  for (const list of [
    SERVED.ivaCategories,
    SERVED.irpfCategories,
    SERVED.invoiceClasses,
    SERVED.premisesSituations,
    SERVED.prorrataProvenances,
    SERVED.sectorLetters,
    SERVED.capitalKinds,
    SERVED.capitalDisposals,
  ])
    expect(list.length).toBeGreaterThan(0);
});

test("a share applies to the served usage-ratio categories and their families only", () => {
  expect(SERVED.usageRatioCategories.length).toBeGreaterThan(0);
  const offered = shareCategoryFamilies(SERVED);
  expect(offered.flatMap(([, members]) => [...members]).sort()).toEqual(
    [...SERVED.usageRatioCategories].sort(),
  );
  for (const [family, members] of offered) {
    const all = SERVED.categoryFamilies.find(([name]) => name === family);
    expect(all, family).toBeDefined();
    expect(members.every((member) => all![1].includes(member))).toBe(true);
  }
});

test("until they are served, or where the read failed, every list is empty and the state says which", () => {
  for (const [vocabulary, state] of [
    [LOADING, "loading"],
    [UNAVAILABLE, "unavailable"],
    [NO_VOCABULARY, "unavailable"],
  ] as const) {
    expect(vocabulary.state).toBe(state);
    expect(vocabulary.categories).toEqual([]);
    expect(vocabulary.categoryFamilies).toEqual([]);
    expect(vocabulary.ivaCategories).toEqual([]);
    expect(vocabulary.usageRatioCategories).toEqual([]);
    expect(vocabulary.invoiceClasses).toEqual([]);
    expect(vocabulary.premisesSituations).toEqual([]);
    expect(vocabulary.capitalKinds).toEqual([]);
  }
});

test("an empty picker says it is being read or not available, and no match once served", () => {
  const none = t("desktop.ledger.edit.no_match");
  expect(vocabularyEmpty(t, LOADING, none, 0)).toBe(
    label("desktop.ledger.form.reading"),
  );
  expect(vocabularyEmpty(t, UNAVAILABLE, none, 0)).toBe(
    label("desktop.ledger.unavailable"),
  );
  expect(vocabularyEmpty(t, SERVED, none, 0)).toBe(none);
  // A list with something to offer is never described as unavailable.
  expect(vocabularyEmpty(t, UNAVAILABLE, none, 3)).toBe(none);
});

test("a stored id shows as itself where the chrome has no word for it", () => {
  expect(categoryLabel(t, "zz_a_new_category")).toBe("zz_a_new_category");
  expect(ivaCategoryLabel(t, "zz_a_new_category")).toBe("zz_a_new_category");
  const served = SERVED.categories[0]!;
  expect(categoryLabel(t, served)).not.toBe(served);
});

test("typed text is taken for a category only from a served list", () => {
  const typed = (vocabulary: typeof SERVED, raw: string) =>
    parseCell("category", "category_id", raw, {
      direction: (token) => token,
      classification: (token) => token,
      category: (id) => categoryLabel(t, id),
      ivaCategory: (id) => id,
      irpfCategory: (id) => id,
      categories: vocabulary.categories,
      ivaCategories: vocabulary.ivaCategories,
      irpfCategories: vocabulary.irpfCategories,
      account: (id) => id,
      accounts: [],
      noAccount: "",
    });
  const served = SERVED.categories[0]!;
  expect(typed(SERVED, served)).toEqual({
    kind: "value",
    value: { value: served },
  });
  expect(typed(SERVED, "zz_a_new_category")).toMatchObject({
    kind: "refused",
    refusal: { key: "unknown_choice" },
  });
  // Nothing is held to compare it with, so nothing is taken for one.
  expect(typed(LOADING, served)).toMatchObject({ kind: "refused" });
  expect(typed(UNAVAILABLE, served)).toMatchObject({ kind: "refused" });
});

test("a category fits a classify command only if it is served, and a share only if it applies", () => {
  const OUT = hexId("20");
  const rows = new Map([[OUT, movement(OUT)]]);
  const plain = SERVED.categories.find(
    (category) => !SERVED.usageRatioCategories.includes(category),
  )!;
  const shared = SERVED.usageRatioCategories[0]!;
  const classify = (kind: "business" | "mixed", category: string) =>
    classifyCells(
      {
        kind,
        ids: [OUT],
        category,
        share: "50",
        check: recordedCheck(EMPTY_CONTENT, rows, {
          ids: [OUT],
          categories: [category],
        }),
      },
      rows,
    ).kind;
  expect(classify("business", plain)).toBe("staged");
  expect(classify("mixed", plain)).toBe("needs");
  expect(classify("mixed", shared)).toBe("staged");
  expect(classify("business", "zz_a_new_category")).toBe("needs");
  // While the ledger has not answered, or could not, no category is staged.
  const unanswered = (kind: "business" | "mixed", category: string) =>
    classifyCells(
      { kind, ids: [OUT], category, share: "50", check: null },
      rows,
    );
  expect(unanswered("business", plain)).toEqual({
    kind: "needs",
    field: "category",
  });
  expect(unanswered("mixed", shared)).toEqual({
    kind: "needs",
    field: "category",
  });
});

test("a new movement is offered the served functional currency unless the accounts say otherwise", () => {
  const served = SERVED.defaultCurrency;
  expect(served).not.toBeNull();
  expect(UNAVAILABLE.defaultCurrency).toBeNull();
  const account = (currency: string | null) => ({
    id: "a",
    label: "A",
    currency,
  });
  // Accounts read, none naming a currency: the served default.
  expect(servedDraftCurrency([], served)).toBe(served);
  expect(servedDraftCurrency([account(null)], served)).toBe(served);
  // Accounts not read: nothing is offered yet.
  expect(servedDraftCurrency(null, served)).toBeNull();
  // The accounts' own currency wins, and a disagreement offers nothing.
  expect(servedDraftCurrency([account("GBP"), account("GBP")], served)).toBe(
    "GBP",
  );
  expect(
    servedDraftCurrency([account("GBP"), account("USD")], served),
  ).toBeNull();
});
