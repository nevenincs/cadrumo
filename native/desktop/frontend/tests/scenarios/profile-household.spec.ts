import { expect, test, type Locator, type Page } from "@playwright/test";
import { windowFixture } from "../support/windowFixtures";
import { readFileSync } from "node:fs";
import { label } from "../support/strings";
import { PROFILE_SURNAMES } from "../support/profileFixture";

// The household element in the profile page. The groups, states, leaves,
// limits and refusal sentences below are what the application served through
// the `family_rows` stream of `user-profile.view` and the ascendants
// replacement, not wording of the window.

type Item = {
  kind: "family_group" | "family_row" | "family_question";
  group_key: string;
  prompt?: string;
  saved_value?: string | null;
  choices?: { value: string; label: string }[];
  label?: string;
  state?: string;
  incomplete_words?: string | null;
  max_rows?: number | null;
  leaves?: { leaf: string; label: string }[];
  add_row_action?: { action_words: string } | null;
  remove_row_action?: { action_words: string } | null;
  facts?: { leaf: string; value: string; masked: boolean }[];
};
type Served = {
  reads: Record<string, { items: Record<string, Item[]> }>;
  refusals: Record<string, Record<string, { refusal_words: string }>>;
};
const served = JSON.parse(
  readFileSync(windowFixture("desktop-household", "household"), "utf8"),
) as Served;

const LANGUAGES = ["en", "es", "ca", "hu"] as const;
type Language = (typeof LANGUAGES)[number];
const DESCENDANTS = "renta_family.descendiente";
const ASCENDANTS = "renta_family.ascendiente";

const PATH = "renta_family.convive_con_otro_progenitor";

/** The values of one group's first served row in the masked read, by leaf. */
const maskedFirstRow = (group: string) =>
  Object.fromEntries(
    served.reads
      .masked!.items.en!.find(
        (item) => item.kind === "family_row" && item.group_key === group,
      )!
      .facts!.map((fact) => [fact.leaf, fact.value]),
  );

/** The birth dates of a group's served rows, in the order the read served them. */
const servedBirthDates = (scenario: string, group: string) =>
  served.reads[scenario]!.items.en!.filter(
    (item) => item.kind === "family_row" && item.group_key === group,
  ).map((row) => row.facts!.find((fact) => fact.leaf === "birth_date")!.value);

/** The question the product served for a scenario, in a language. */
const questionOf = (scenario: string, language: Language) =>
  served.reads[scenario]!.items[language]!.find(
    (item) => item.kind === "family_question",
  )!;

const groupsOf = (scenario: string, language: Language) =>
  served.reads[scenario]!.items[language]!.filter(
    (item) => item.kind === "family_group",
  );

/** The words of the add control the product served for a group. */
const addWords = (scenario: string, index: number, language: Language = "en") =>
  groupsOf(scenario, language)[index]!.add_row_action!.action_words;

/** The words of the remove control the product served for a group. */
const removeWords = (
  scenario: string,
  index: number,
  language: Language = "en",
) => groupsOf(scenario, language)[index]!.remove_row_action!.action_words;

async function open(
  page: Page,
  household: string,
  language: Language = "en",
): Promise<Locator> {
  await page.goto(
    `/scenarios.html?scenario=user-profile&latency=0&bar=off&household=${household}&lang=${language}`,
  );
  await page
    .locator(".rail")
    .getByRole("button", {
      name: label("desktop.profile.title", {}, language),
      exact: true,
    })
    .click();
  const profile = page.locator(".user-profile-page");
  await expect(profile).toContainText(PROFILE_SURNAMES);
  return profile.locator("[data-household]");
}

const group = (household: Locator, key: string) =>
  household.locator(`[data-household-group="${key}"]`);

const question = (household: Locator) =>
  household.locator("[data-household-question]");

test.describe("the household in the profile page", () => {
  for (const language of LANGUAGES) {
    test(`each state of a group is told apart (${language})`, async ({
      page,
    }) => {
      for (const [scenario, states] of [
        ["unknown", ["unknown", "unknown"]],
        ["none_declared", ["none_declared", "none_declared"]],
        ["rows", ["rows", "rows"]],
        ["incomplete", ["incomplete", "incomplete"]],
      ] as const) {
        const household = await open(page, scenario, language);
        for (const [index, key] of [DESCENDANTS, ASCENDANTS].entries()) {
          const shown = group(household, key);
          await expect(shown).toHaveAttribute(
            "data-household-state",
            states[index]!,
          );
          // The heading is the product's own word for the group.
          await expect(shown.getByRole("heading")).toHaveText(
            groupsOf(scenario, language)[index]!.label!,
          );
        }
      }
    });
  }

  test("an unknown group is not drawn as none, and no person is invented", async ({
    page,
  }) => {
    const household = await open(page, "unknown");
    await expect(household.locator("[data-household-person]")).toHaveCount(0);
    const unknown = group(household, DESCENDANTS);
    await expect(unknown).toContainText(
      label("desktop.profile.household.state.unknown"),
    );
    await expect(unknown).not.toContainText(
      label("desktop.profile.household.state.none_declared"),
    );
    await expect(
      unknown.getByRole("button", {
        name: label("desktop.profile.household.declare_none"),
      }),
    ).toBeVisible();
  });

  test("an incomplete group shows the product's own stated and recorded words", async ({
    page,
  }) => {
    for (const language of LANGUAGES) {
      const household = await open(page, "incomplete", language);
      const words = groupsOf("incomplete", language).map(
        (item) => item.incomplete_words!,
      );
      await expect(
        group(household, DESCENDANTS).locator("[data-household-incomplete]"),
      ).toHaveText(words[0]!);
      await expect(
        group(household, ASCENDANTS).locator("[data-household-incomplete]"),
      ).toHaveText(words[1]!);
      // The recorded person is still there.
      await expect(
        group(household, DESCENDANTS).locator("[data-household-person]"),
      ).toHaveCount(1);
    }
  });

  test("a hidden value stays hidden and its group is not rewritten here", async ({
    page,
  }) => {
    const household = await open(page, "masked");
    const hidden = household.locator("[data-masked]");
    await expect(hidden.first()).toContainText("••••");
    const text = (await household.textContent()) ?? "";
    // The child's NIF and birth date are hidden; the ascendant's are not.
    const child = maskedFirstRow(DESCENDANTS);
    expect(text).not.toContain(child.birth_date!);
    expect(text).not.toContain(child.nif!);
    expect(text.split(maskedFirstRow(ASCENDANTS).nif!)).toHaveLength(2);
    await expect(
      group(household, DESCENDANTS).getByRole("button", {
        name: label("desktop.profile.household.edit_person", { number: 1 }),
      }),
    ).toBeDisabled();
    await expect(
      group(household, ASCENDANTS).getByRole("button", {
        name: label("desktop.profile.household.edit_person", { number: 1 }),
      }),
    ).toBeEnabled();
  });

  test("a group at the design's limit takes no more people", async ({
    page,
  }) => {
    const household = await open(page, "at_cap");
    for (const [index, key] of [DESCENDANTS, ASCENDANTS].entries()) {
      const full = group(household, key);
      // The product serves no add control for a full group.
      await expect(full.locator("[data-household-add]")).toHaveCount(0);
      await expect(full).toContainText(
        label("desktop.profile.household.cap_reached"),
      );
      const cap = groupsOf("at_cap", "en")[index]!.max_rows!;
      await expect(full).toContainText(
        label("desktop.profile.household.limit", { count: cap, max: cap }),
      );
      await expect(full.locator("[data-household-person]")).toHaveCount(cap);
    }
  });

  test("a person is added through the served add control against the revision read", async ({
    page,
  }) => {
    const household = await open(page, "unknown");
    const ascendants = group(household, ASCENDANTS);
    await ascendants
      .getByRole("button", { name: addWords("unknown", 1) })
      .click();
    const dialog = page.getByRole("dialog");
    const born = groupsOf("unknown", "en")[1]!.leaves!.find(
      (leaf) => leaf.leaf === "birth_date",
    )!.label;
    await dialog.getByRole("textbox", { name: born }).fill("1950-02-03");
    await dialog.getByRole("textbox", { name: born }).blur();
    await dialog
      .getByRole("button", { name: label("desktop.profile.save") })
      .click();
    await expect(dialog).toHaveCount(0);
    await expect(ascendants).toHaveAttribute("data-household-state", "rows");
    await expect(ascendants.locator("[data-household-person]")).toHaveCount(1);
    // The other group states nothing more than it did.
    await expect(group(household, DESCENDANTS)).toHaveAttribute(
      "data-household-state",
      "unknown",
    );
    const writes = await page.evaluate(() =>
      window.__scenarioHousehold!.writes(),
    );
    expect(writes).toHaveLength(1);
    // Only the person added is sent; the product composes the set.
    expect(writes[0]!.edit).toEqual({
      kind: "ascendants",
      add_row: { facts: [{ field_key: "birth_date", value: "1950-02-03" }] },
    });
    expect(writes[0]!.expected_revision).toBeGreaterThan(0);
  });

  test("a leaf is shown while the product asks it, and an answer is read by the product", async ({
    page,
  }) => {
    const household = await open(page, "unknown");
    await group(household, DESCENDANTS)
      .getByRole("button", { name: addWords("unknown", 0) })
      .click();
    const dialog = page.getByRole("dialog");
    const leaf = (key: string) =>
      dialog.locator(`[data-household-leaf="${key}"]`);
    const leaves = groupsOf("unknown", "en")[0]!.leaves as {
      leaf: string;
      label: string;
      choices?: { value: string; label: string }[];
    }[];
    const relation = leaves.find((entry) => entry.leaf === "relacion")!;
    // Asked: no condition. Awaiting: its governing answer is missing, so
    // nothing is drawn for it.
    await expect(leaf("relacion")).toBeVisible();
    await expect(leaf("inscripcion_registro_civil")).toHaveCount(0);
    expect(
      await page.evaluate(() => window.__scenarioHousehold!.drafts()),
    ).toHaveLength(0);
    await dialog.getByRole("combobox", { name: relation.label }).selectOption({
      label: relation.choices!.find((entry) => entry.value === "adoptado")!
        .label,
    });
    await expect(leaf("inscripcion_registro_civil")).toBeVisible();
    // The answer went to the product as a draft, and nothing else did.
    expect(
      await page.evaluate(() => window.__scenarioHousehold!.drafts()),
    ).toEqual([
      {
        group: DESCENDANTS,
        facts: [{ leaf: "relacion", value: "adoptado" }],
      },
    ]);
    expect(
      await page.evaluate(() => window.__scenarioHousehold!.writes()),
    ).toHaveLength(0);
  });

  test("a refused draft is told in the refusal alert and holds Save until the next answer", async ({
    page,
  }) => {
    const household = await open(page, "unknown");
    await page.evaluate(() => window.__scenarioHousehold!.refuseNextDraft());
    await group(household, DESCENDANTS)
      .getByRole("button", { name: addWords("unknown", 0) })
      .click();
    const dialog = page.getByRole("dialog");
    // Two different dates the product served for its descendants: the draft
    // read is refused once whatever is typed, so only the change matters.
    const [first, second] = servedBirthDates("rows", DESCENDANTS).filter(
      (date, index, dates) => dates.indexOf(date) === index,
    );
    const born = groupsOf("unknown", "en")[0]!.leaves!.find(
      (entry) => entry.leaf === "birth_date",
    )!.label;
    await dialog.getByRole("textbox", { name: born }).fill(first!);
    const save = dialog.getByRole("button", {
      name: label("desktop.profile.save"),
    });
    await expect(dialog.getByRole("alert")).toBeVisible();
    await expect(save).toBeDisabled();
    await dialog.getByRole("textbox", { name: born }).fill(second!);
    await expect(dialog.getByRole("alert")).toHaveCount(0);
    await expect(save).toBeEnabled();
  });

  test("a person is removed by the index the read served, through the served remove control", async ({
    page,
  }) => {
    const household = await open(page, "rows");
    const ascendants = group(household, ASCENDANTS);
    const first = ascendants.locator("[data-household-person]").first();
    const index = (await first.getAttribute("data-household-person"))!;
    await first.getByRole("button", { name: removeWords("rows", 1) }).click();
    await page
      .getByRole("dialog")
      .getByRole("button", { name: removeWords("rows", 1) })
      .click();
    await expect(ascendants.locator("[data-household-person]")).toHaveCount(1);
    const writes = await page.evaluate(() =>
      window.__scenarioHousehold!.writes(),
    );
    expect(writes.map((write) => write.edit)).toEqual([
      { kind: "ascendants", remove_row_index: index },
    ]);
  });

  test("declaring none states a zero", async ({ page }) => {
    const household = await open(page, "unknown");
    await group(household, DESCENDANTS)
      .getByRole("button", {
        name: label("desktop.profile.household.declare_none"),
      })
      .click();
    await expect(group(household, DESCENDANTS)).toHaveAttribute(
      "data-household-state",
      "none_declared",
    );
    const writes = await page.evaluate(() =>
      window.__scenarioHousehold!.writes(),
    );
    expect(writes.map((write) => write.edit)).toEqual([
      { kind: "descendants", rows: [] },
    ]);
  });

  test("a refusal is the application's own sentence and the dialog stays open", async ({
    page,
  }) => {
    for (const language of LANGUAGES) {
      const household = await open(page, "rows", language);
      await page.evaluate(() =>
        window.__scenarioHousehold!.refuseNext("ascendants_second_nif_invalid"),
      );
      await group(household, ASCENDANTS)
        .getByRole("button", {
          name: label(
            "desktop.profile.household.edit_person",
            { number: 1 },
            language,
          ),
        })
        .click();
      const dialog = page.getByRole("dialog");
      await dialog
        .getByRole("button", {
          name: label("desktop.profile.save", {}, language),
        })
        .click();
      await expect(dialog.getByRole("alert")).toHaveText(
        served.refusals.ascendants_second_nif_invalid![language]!.refusal_words,
      );
      await expect(dialog).toBeVisible();
    }
  });

  test("a refused descendant replacement shows the application's own sentence for it", async ({
    page,
  }) => {
    for (const language of LANGUAGES) {
      const household = await open(page, "rows", language);
      await page.evaluate(() =>
        window.__scenarioHousehold!.refuseNext(
          "descendants_second_value_invalid",
        ),
      );
      await group(household, DESCENDANTS)
        .getByRole("button", {
          name: label(
            "desktop.profile.household.edit_person",
            { number: 1 },
            language,
          ),
        })
        .click();
      const dialog = page.getByRole("dialog");
      await dialog
        .getByRole("button", {
          name: label("desktop.profile.save", {}, language),
        })
        .click();
      await expect(dialog.getByRole("alert")).toHaveText(
        served.refusals.descendants_second_value_invalid![language]!
          .refusal_words,
      );
      await expect(dialog).toBeVisible();
    }
  });

  test("a write that may have landed blocks further writes until a refresh", async ({
    page,
  }) => {
    const household = await open(page, "rows");
    await page.evaluate(() => window.__scenarioHousehold!.loseNextAnswer());
    await group(household, ASCENDANTS)
      .getByRole("button", { name: removeWords("rows", 1) })
      .first()
      .click();
    await page
      .getByRole("dialog")
      .getByRole("button", { name: removeWords("rows", 1) })
      .click();
    await expect(household.getByRole("alert")).toHaveText(
      label("desktop.profile.unknown"),
    );
    for (const add of await household.locator("[data-household-add]").all())
      await expect(add).toBeDisabled();
    await household
      .getByRole("button", { name: label("desktop.profile.refresh") })
      .click();
    await expect(
      group(household, ASCENDANTS).getByRole("button", {
        name: addWords("rows", 1),
      }),
    ).toBeEnabled();
    // The read that opened the controls also ended the unknown notice.
    await expect(household.locator("[data-household-failure]")).toHaveCount(0);
    await expect(
      household.getByRole("button", { name: label("desktop.profile.refresh") }),
    ).toHaveCount(0);
  });

  for (const language of LANGUAGES) {
    test(`a single parent is asked, and not stated is told apart from no (${language})`, async ({
      page,
    }) => {
      for (const [scenario, answer] of [
        ["single_parent_unstated", "unknown"],
        ["single_parent_lives_with", "true"],
        ["single_parent_apart", "false"],
      ] as const) {
        const household = await open(page, scenario, language);
        const asked = question(household);
        await expect(asked).toHaveCount(1);
        await expect(asked).toHaveAttribute("data-household-answer", answer);
        const served = questionOf(scenario, language);
        // The words are the product's own, not the window's.
        await expect(asked.getByRole("heading")).toHaveText(served.prompt!);
        const stated = served.choices!.find(
          (choice) => choice.value === answer,
        );
        await expect(asked.locator("[data-household-mark]")).toHaveText(
          stated
            ? stated.label
            : label("desktop.profile.household.state.unknown", {}, language),
        );
        for (const choice of served.choices!)
          await expect(
            asked.getByRole("radio", { name: choice.label }),
          ).toHaveAttribute(
            "aria-checked",
            choice.value === answer ? "true" : "false",
          );
      }
    });
  }

  test("a married unit is not asked the single-parent question", async ({
    page,
  }) => {
    const household = await open(page, "married");
    await expect(question(household)).toHaveCount(0);
    await expect(group(household, DESCENDANTS)).toBeVisible();
  });

  test("the answer is written to the profile fact against the revision read, and taken back", async ({
    page,
  }) => {
    const household = await open(page, "single_parent_unstated");
    const asked = question(household);
    const choices = questionOf("single_parent_unstated", "en").choices!;
    const yes = choices.find((choice) => choice.value === "true")!;
    await asked.getByRole("radio", { name: yes.label }).click();
    await expect(asked).toHaveAttribute("data-household-answer", "true");
    await asked
      .getByRole("button", {
        name: label("desktop.profile.household.question.clear"),
      })
      .click();
    await expect(asked).toHaveAttribute("data-household-answer", "unknown");
    const writes = await page.evaluate(() =>
      window.__scenarioHousehold!.writes(),
    );
    expect(writes.map((write) => write.edit)).toEqual([
      { kind: "field", path: PATH, value: "true" },
      { kind: "field", path: PATH, value: "" },
    ]);
    // Each answer names the revision the household was read at, and the next
    // one the revision the first moved it to.
    expect(writes[0]!.expected_revision).toBeGreaterThan(0);
    expect(writes[1]!.expected_revision).toBe(writes[0]!.expected_revision + 1);
    // The groups stated nothing in the meantime.
    await expect(group(household, DESCENDANTS)).toHaveAttribute(
      "data-household-state",
      "unknown",
    );
  });
});

// From the Modelo 100: the household's rows are drawn there from the profile,
// and the way to correct them leads to the profile page through the form's
// existing routing of a source's surface.

const workspace = (target: Page) => target.locator(".declarations-workspace");

/** Opens the filer's 2025 Modelo 100 the way the list offers it. */
async function openRenta(target: Page, household: string) {
  await target.goto(
    `/scenarios.html?scenario=user-profile&latency=0&bar=off&modelo=renta&household=${household}`,
  );
  await target.locator("[data-rail=declarations]").click();
  const read = await target.evaluate(async () =>
    window.__fixtureModelo!.declarations("en"),
  );
  const existing = read.creation_targets.find(
    (entry) => entry.modelo === "100" && entry.existing,
  )!;
  await target
    .getByRole("button", { name: label("workspace.declarations.list.key.new") })
    .first()
    .click();
  const dialog = target.getByRole("dialog");
  await dialog.getByText(existing.modelo_title, { exact: true }).click();
  await dialog.getByRole("radio", { name: existing.period_words! }).click();
  await dialog
    .getByRole("button", {
      name: label("workspace.declarations.list.new.open_it"),
    })
    .click();
  await expect(
    workspace(target).getByRole("heading", { level: 1 }),
  ).toBeVisible({ timeout: 30_000 });
}

test.describe("the household from the Modelo 100", () => {
  test("the outline group that keeps boxes in the profile leads to the profile", async ({
    page: target,
  }) => {
    await openRenta(target, "incomplete");
    await target
      .getByRole("tab", { name: label("desktop.modelo.side.outline") })
      .click();
    const tree = workspace(target).getByRole("tree", {
      name: label("desktop.modelo.outline.label"),
    });
    const served = await target.evaluate(async () => {
      const port = window.__fixtureModelo!;
      const list = await port.declarations("en");
      const unit = list.creation_targets.find(
        (entry) => entry.modelo === "100" && entry.existing,
      )!.existing!.work_unit_id;
      return (await port.form(unit, "en")).form.form;
    });
    // Whatever the read model served as a group with a box kept in the
    // profile has the way there; one with none has not.
    const keeps = (group: (typeof served.outline)[number]) =>
      served.pages
        .flatMap((page) => page.sections)
        .filter((section) => group.section_ids.includes(section.id))
        .some((section) =>
          JSON.stringify(section.blocks).includes('"surface":"profile"'),
        );
    const withLink = served.outline.filter(keeps);
    expect(withLink.length).toBeGreaterThan(0);
    expect(withLink.length).toBeLessThan(served.outline.length);
    await expect(tree.locator("[data-outline-profile]")).toHaveCount(
      withLink.length,
    );
    const household = served.outline.find((group) =>
      group.section_ids.some((id) =>
        id.startsWith("datosidentificativos-hijos"),
      ),
    )!;
    await tree.locator(`[data-outline-profile="${household.id}"]`).click();
    const profile = target.locator(".user-profile-page");
    await expect(profile).toBeVisible();
    await expect(profile.locator("[data-household]")).toBeVisible();
  });

  test("a check line that leads to the profile opens it", async ({
    page: target,
  }) => {
    await openRenta(target, "incomplete");
    await workspace(target)
      .getByRole("tab", {
        name: new RegExp(`^${label("workspace.modelo.step.review")}`),
      })
      .click();
    await workspace(target)
      .getByRole("button", {
        name: label("workspace.modelo.surface.open.profile"),
      })
      .first()
      .click();
    await expect(target.locator(".user-profile-page")).toBeVisible();
  });
});
