import { expect, test } from "@playwright/test";
import type { ModeloFilingRecordViewProjection } from "../../src/shell/modeloContract/modeloFilingRecord";
import type { ModeloWorkAmendmentContextProjection } from "../../src/shell/modeloContract/modeloWorkAmendmentContext";
import { envelope, LANGUAGES, openList } from "../support/scenarioModelo";
import { label } from "../support/strings";

for (const language of LANGUAGES) {
  test(`saved original and successive corrections navigate both ways in ${language}`, async ({
    page,
  }) => {
    const t = (key: string) =>
      label(`workspace.declarations.related_filings.${key}`, {}, language);
    const original = envelope<ModeloFilingRecordViewProjection>(
      `filing-view-130-original-${language}`,
    );
    const first = envelope<ModeloFilingRecordViewProjection>(
      `filing-view-130-correction-1-${language}`,
    );
    const second = envelope<ModeloFilingRecordViewProjection>(
      `filing-view-130-correction-2-${language}`,
    );
    const before = envelope<ModeloWorkAmendmentContextProjection>(
      `amendment-context-130-correction-1-${language}`,
    );
    const after = envelope<ModeloWorkAmendmentContextProjection>(
      `amendment-context-130-correction-2-${language}`,
    );
    const grid = await openList(page, { shape: "related-filings", language });
    const row = grid
      .getByRole("row")
      .filter({ hasText: t("title") })
      .first();
    await row.dblclick();
    const dialog = page.getByRole("dialog", { name: t("title") });
    const picker = dialog.getByRole("combobox", { name: t("select") });
    await expect(picker).toHaveValue(original.filing_record_id);
    await expect(picker.getByRole("option")).toHaveCount(3);
    await picker.selectOption(second.filing_record_id);
    await expect(picker).toHaveValue(second.filing_record_id);
    const selected = second.related_filings.find(
      (item) => item.filing_record_id === second.filing_record_id,
    );
    if (!selected)
      throw new Error("The saved filing is absent from its related group");
    await expect(
      dialog
        .getByRole("paragraph")
        .filter({ hasText: selected.confirmation_words })
        .first(),
    ).toBeVisible();
    const changed = after.correction?.rows.find((item) => {
      const prior = before.correction?.rows.find(
        (other) => other.casilla_id === item.casilla_id,
      );
      return prior && prior.filed_value !== item.filed_value;
    });
    const prior = before.correction?.rows.find(
      (item) => item.casilla_id === changed?.casilla_id,
    );
    if (!changed || !prior)
      throw new Error(
        "The canonical correction has no changed labeled saved value",
      );
    const valueRow = dialog.getByRole("row").filter({ hasText: changed.label });
    await expect(
      valueRow.getByRole("cell", { name: prior.filed_value_text, exact: true }),
    ).toBeVisible();
    await expect(
      valueRow.getByRole("cell", {
        name: changed.filed_value_text,
        exact: true,
      }),
    ).toBeVisible();
    await expect(
      valueRow.getByRole("cell", { name: t("changed"), exact: true }),
    ).toBeVisible();
    await dialog
      .getByText(t("base"), { exact: true })
      .locator("..")
      .getByRole("button")
      .click();
    await expect(picker).toHaveValue(first.filing_record_id);
    await dialog
      .getByText(t("base"), { exact: true })
      .locator("..")
      .getByRole("button")
      .click();
    await expect(picker).toHaveValue(original.filing_record_id);
    await dialog
      .getByText(t("corrections"), { exact: true })
      .locator("..")
      .getByRole("button")
      .click();
    await expect(picker).toHaveValue(first.filing_record_id);
    await page.keyboard.press("Escape");
    await expect(dialog).toBeHidden();
    await expect(grid).toBeVisible();
  });
}
