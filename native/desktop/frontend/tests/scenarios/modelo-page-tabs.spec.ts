import { expect, test, type Page } from "@playwright/test";
import { label } from "../support/strings";
import { openList, views, type Language } from "../support/scenarioModelo";

// The form's page tabs read what the application served for each page, in
// the window's language. The 2025 Renta serves words for every page; the
// 2024 one serves only each page's registry path, with the disclosure
// `technical`, and its tab draws that path as the key it is (`data-key`)
// glossed by the served words for a technical name; the window words
// nothing of its own.

const LANGUAGES_UNDER_TEST: readonly Language[] = ["en", "es"];

type ServedHeading = { text: string; disclosure: string };

/** Opens the filer's Modelo 100 of the shape's year the way the new-declaration
 * dialog offers it: the list reads the stored declarations, not the shape's. */
async function openRenta(target: Page, shape: string, language: Language) {
  await openList(target, { shape, language });
  const existing = await target.evaluate(async (asked) => {
    const read = await window.__fixtureModelo!.declarations(asked);
    const found = read.creation_targets.find(
      (entry) => entry.modelo === "100" && entry.existing,
    )!;
    return { title: found.modelo_title, period: found.period_words! };
  }, language);
  await target
    .getByRole("button", {
      name: label("workspace.declarations.list.key.new", {}, language),
    })
    .first()
    .click();
  const dialog = target.getByRole("dialog");
  await dialog.getByText(existing.title, { exact: true }).click();
  await dialog.getByRole("radio", { name: existing.period }).click();
  await dialog
    .getByRole("button", {
      name: label("workspace.declarations.list.new.open_it", {}, language),
    })
    .click();
  await expect(views(target, language)).toBeVisible({ timeout: 30_000 });
}

/** The headings the application served for the pages of the filer's Modelo
 * 100, in the form's order. */
async function servedHeadings(
  target: Page,
  language: Language,
): Promise<ServedHeading[]> {
  return target.evaluate(async (asked) => {
    const port = window.__fixtureModelo!;
    const list = await port.declarations(asked);
    const unit = list.creation_targets.find(
      (entry) => entry.modelo === "100" && entry.existing,
    )!.existing!.work_unit_id;
    const read = await port.form(unit, asked);
    return read.form.form.pages.map((served) => ({
      text: served.heading.text,
      disclosure: served.heading.disclosure,
    }));
  }, language);
}

const pageTabs = (target: Page, language: Language) =>
  target
    .getByRole("tablist", {
      name: label("desktop.modelo.form.pages", {}, language),
    })
    .getByRole("tab");

for (const language of LANGUAGES_UNDER_TEST) {
  test(`form page tabs read the words the application served (${language})`, async ({
    page: target,
  }) => {
    await openRenta(target, "renta-married", language);
    const served = await servedHeadings(target, language);
    expect(served.length).toBeGreaterThan(1);
    expect(served.every((heading) => heading.disclosure !== "technical")).toBe(
      true,
    );
    const tabs = pageTabs(target, language);
    await expect(tabs.first()).toBeVisible();
    for (const [index, heading] of served.entries()) {
      const tab = tabs.nth(index);
      // The window sets an official label written in capitals in sentence
      // case; nothing else of the served words changes.
      expect(
        ((await tab.textContent()) ?? "").replace(/\d+$/, "").toLowerCase(),
      ).toBe(heading.text.toLowerCase());
      await expect(tab.locator("[data-key]")).toHaveCount(0);
    }
  });

  test(`form page tabs that were served only a registry path draw it as a key (${language})`, async ({
    page: target,
  }) => {
    await openRenta(target, "renta-y2024", language);
    const served = await servedHeadings(target, language);
    expect(served.length).toBeGreaterThan(1);
    const tabs = pageTabs(target, language);
    await expect(tabs.first()).toBeVisible();
    for (const [index, heading] of served.entries()) {
      expect(heading.disclosure).toBe("technical");
      const tab = tabs.nth(index);
      const key = tab.locator("[data-key]");
      await expect(key).toHaveAttribute("data-key", heading.text);
      await expect(key).toHaveText(heading.text);
      await expect(key).toHaveAttribute(
        "title",
        label("workspace.modelo.disclosure.technical", {}, language),
      );
    }
  });
}
