import { expect, test } from "@playwright/test";
import { label } from "../support/strings";
import {
  contextFacts,
  everyView,
  expectNothingRaw,
  form,
  LANGUAGES,
  list,
  openDeclaration,
  openFromDialog,
  openList,
  rawOnScreen,
  rulesIncomplete,
} from "../support/scenarioModelo";
import { calls } from "../support/scenarioModeloWrites";

// -- every language, and the gate ------------------------------------------

for (const language of LANGUAGES) {
  test(`the list speaks ${language} and shows nothing raw`, async ({
    page: target,
  }) => {
    await openList(target, { language });
    await expect(target.locator("html")).toHaveAttribute("lang", language);
    const read = list(language);
    expect(read.output_language).toBe(language);
    await expect(
      target.getByText(read.rows[0]!.state_words).first(),
    ).toBeVisible();
    await expectNothingRaw(target, language);
    await target
      .getByRole("button", {
        name: label("workspace.declarations.list.key.new", {}, language),
      })
      .first()
      .click();
    await expect(target.getByRole("dialog")).toBeVisible();
    await expectNothingRaw(target, language);
  });

  for (const [name, shape, modelo] of [
    ["130-1T", "", "130"],
    ["130-1T-checked", "checked", "130"],
    ["130-1T-filed", "filed", "130"],
    ["130-1T-receipt", "receipt", "130"],
    ["130-1T-stale", "stale", "130"],
    ["303-1T", "", "303"],
    ["347-0A", "", "347"],
  ] as const)
    test(`modelo ${name} speaks ${language} in every view and shows nothing raw`, async ({
      page: target,
    }) => {
      const read = form(name, language);
      expect(read.form.form.language).toBe(language);
      await openDeclaration(target, modelo, { shape, language });
      if (modelo === "347") {
        const numbered = contextFacts(read.form.form.pages).filter(
          (item) => item.box_number !== null,
        );
        expect(numbered.map((item) => item.box_number)).toEqual([
          "01",
          "02",
          "03",
          "04",
        ]);
        for (const item of numbered) {
          const term = target
            .locator("dt")
            .filter({ hasText: item.label.text });
          await expect(
            term.getByText(item.box_number!, { exact: true }),
          ).toBeVisible();
          await expect(term).toContainText(item.label.text);
          // Beside it, the value_text the read model serves for that numbered
          // item, or the served words for one not known yet.
          await expect(
            term.locator("xpath=following-sibling::dd[1]"),
          ).toHaveText(
            item.value_text ??
              label("workspace.modelo.value.not_known_yet", {}, language),
          );
          // The value stays inside its own cell rather than running over the
          // fact beside it.
          expect(
            await term
              .locator("xpath=following-sibling::dd[1]")
              .evaluate((value) => value.scrollWidth <= value.clientWidth),
          ).toBe(true);
        }
        // Opening the form shows those facts as served: the window never
        // calculates to fill them.
        expect(await calls(target, "modelo submit")).toEqual([]);
      }
      if (read.header.deadline)
        await expect(
          target.getByText(read.header.deadline.text, { exact: true }),
        ).toBeVisible();
      await everyView(target, language, () =>
        expectNothingRaw(target, language),
      );
    });

  test(`a modelo whose rules are incomplete speaks ${language} in every view and shows nothing raw`, async ({
    page: target,
  }) => {
    await openFromDialog(target, rulesIncomplete.modelo, language);
    await expect(
      target
        .getByText(
          label("workspace.modelo.editor.rules_incomplete", {}, language),
        )
        .first(),
    ).toBeVisible();
    await everyView(target, language, () => expectNothingRaw(target, language));
  });
}

test("the gate sees a raw key, an identifier and an enum token", async ({
  page: target,
}) => {
  // The gate's own proof: each kind it refuses is found when present.
  await target.goto("/scenarios.html?scenario=ledger&latency=0&bar=off");
  await target.evaluate(() => {
    const probe = document.createElement("p");
    probe.setAttribute("role", "dialog");
    probe.textContent =
      "workspace.modelo.issues.title modelo.work.form calculation_failed " +
      "ley-58-2003:art-119 modelo-130-pagos-fraccionados-anteriores [19] {date}";
    document.body.append(probe);
  });
  const found = await rawOnScreen(target);
  for (const kind of [
    "catalogue key",
    "definition id",
    "enum token",
    "legal reference id",
    "binding id",
    "bracketed box id",
    "unfilled placeholder",
  ])
    expect(found.some((entry) => entry.startsWith(`${kind}:`))).toBe(true);
});
