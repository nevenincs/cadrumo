import { expect, type Page, test } from "@playwright/test";
import type { ModeloReconciliationImportProjection } from "../../src/shell/modeloContract/modeloReconcile";
import { label } from "../support/strings";
import {
  envelope,
  form,
  LANGUAGES,
  openDeclaration,
  tab,
} from "../support/scenarioModelo";
import { calls, filing } from "../support/scenarioModeloWrites";

test("recording the filing keeps it local, and a verified receipt is another state", async ({
  page: target,
}) => {
  const recorded = form("130-1T-filed").receipt;
  const verified = form("130-1T-receipt").receipt;
  if (!recorded || recorded.verified || !verified?.verified)
    throw new Error("the recorded and the verified 130 do not differ");
  await filing(target, "exported");
  await target
    .getByRole("button", {
      name: label("workspace.modelo.filing.record_as_filed"),
    })
    .click();
  await target
    .getByRole("dialog")
    .getByRole("button", {
      name: label("application.modelo.lifecycle.file_confirm_accept"),
    })
    .click();
  await expect(
    target.getByText(label("workspace.modelo.filing.recorded_here")).first(),
  ).toBeVisible();
  expect(await calls(target, "modelo submit modelo.work.file")).toHaveLength(1);
  // Recorded here, its receipt not verified: the AEAT's side is still open.
  await expect(target.getByText(recorded.words).first()).toBeVisible();
  await expect(
    target.getByText(label("workspace.modelo.filing.not_confirmed_yet")),
  ).toBeVisible();
  await expect(target.getByText(verified.words)).toHaveCount(0);
});

for (const language of LANGUAGES)
  test(`receipt comparison exposes every returned difference and limitation in ${language}`, async ({
    page: target,
  }) => {
    const imported =
      envelope<ModeloReconciliationImportProjection>("reconcile-130");
    await openDeclaration(target, "130", { shape: "filed", language });
    await tab(target, "workspace.modelo.filing.title", language).click();
    await target
      .getByRole("button", {
        name: label("workspace.modelo.filing.add_receipt_pdf", {}, language),
      })
      .click();
    await expect(
      target.getByText(
        label(
          imported.verdict === "matches"
            ? "workspace.modelo.filing.reconciliation.matches"
            : "workspace.modelo.filing.reconciliation.differs",
          {},
          language,
        ),
      ),
    ).toBeVisible();
    const report = target.locator(".modelo-reconciliation");
    // Each difference is a row of its own, its declaration's value beside the
    // receipt's: two rows, or one row's two sides, may read the same.
    const rows = report
      .getByRole("region", {
        name: label(
          "workspace.modelo.filing.reconciliation.differences",
          {},
          language,
        ),
      })
      .locator(":scope > ul > li");
    await expect(rows).toHaveCount(imported.diffs.length);
    for (const [index, diff] of imported.diffs.entries()) {
      const sides = rows.nth(index).locator("dd");
      await expect(sides.nth(0)).toHaveText(diff.work_unit_value);
      await expect(sides.nth(1)).toHaveText(diff.evidence_value);
    }
    for (const advisory of imported.advisories) {
      const item = report
        .getByRole("listitem")
        .filter({ hasText: advisory.message });
      await expect(
        item.getByText(advisory.message, { exact: true }),
      ).toBeVisible();
      await item.locator("summary").click();
      await expect(
        item.getByText(advisory.code, { exact: true }),
      ).toBeVisible();
      for (const [key, value] of advisory.context) {
        await expect(item.locator("dt").filter({ hasText: key })).toBeVisible();
        await expect(
          item.locator("dd").filter({ hasText: value }),
        ).toBeVisible();
      }
    }
    await expect(
      report.getByText(imported.narrative, { exact: true }),
    ).toBeHidden();
    await report.locator(":scope > details > summary").click();
    await expect(
      report.getByText(imported.narrative, { exact: true }),
    ).toBeVisible();
    await expect(report).not.toContainText(imported.source_path);
    if (language === "en")
      await report.screenshot({
        path: test.info().outputPath("receipt-comparison.png"),
      });
    expect(await calls(target, "modelo pickFile evidence")).toHaveLength(1);
  });

test("declaration comparison is available before filing and keeps a served refusal visible", async ({
  page: target,
}) => {
  await filing(target, "");
  const words = "The test declaration cannot be compared with this PDF.";
  await target.evaluate((words) => {
    const port = window.__fixtureModelo!;
    const submit = port.submit;
    port.submit = async (...args) => {
      if (args[0] !== "modelo.reconcile.import") return submit(...args);
      const request = args[1] as {
        source_kind: string;
        calculation_revision_id: string | null;
      };
      window.__modeloCompared = {
        sourceKind: request.source_kind,
        calculation: request.calculation_revision_id,
        count: (window.__modeloCompared?.count ?? 0) + 1,
      };
      return {
        kind: "refused",
        operation_id: "fixture-declaration-comparison",
        revision: 1,
        reason: null,
        detail: {
          detail_version: 1,
          kind: "application",
          error_code: null,
          message_key: null,
          context: [],
          context_entries_omitted: 0,
          precondition_verdict_json: null,
          refusal_words: words,
        },
      };
    };
  }, words);
  const compare = target.getByRole("button", {
    name: label("workspace.modelo.filing.compare_declaration"),
  });
  await expect(compare).toBeEnabled();
  await expect(
    target.getByRole("button", {
      name: label("workspace.modelo.filing.add_receipt_pdf"),
    }),
  ).toBeDisabled();
  await compare.click();
  await expect(target.getByText(words, { exact: true })).toBeVisible();
  await expect(compare).toBeEnabled();
  expect(await target.evaluate(() => window.__modeloCompared)).toMatchObject({
    sourceKind: "declaration",
    count: 1,
  });
  expect(await calls(target, "modelo pickFile evidence")).toHaveLength(1);
});

test("declaration comparison stays available with a verified receipt and shares unknown-write protection", async ({
  page: target,
}) => {
  await filing(target, "receipt");
  await target.evaluate(() => {
    const port = window.__fixtureModelo!;
    const submit = port.submit;
    port.submit = async (...args) => {
      if (args[0] !== "modelo.reconcile.import") return submit(...args);
      const request = args[1] as {
        source_kind: string;
        calculation_revision_id: string | null;
      };
      window.__modeloCompared = {
        sourceKind: request.source_kind,
        calculation: request.calculation_revision_id,
        count: (window.__modeloCompared?.count ?? 0) + 1,
      };
      throw Object.assign(new Error("fixture unknown outcome"), {
        code: "unknown",
        operation_id: null,
      });
    };
  });
  const compare = target.getByRole("button", {
    name: label("workspace.modelo.filing.compare_declaration"),
  });
  await expect(compare).toBeEnabled();
  await expect(
    target.getByRole("button", {
      name: label("workspace.modelo.filing.add_receipt_pdf"),
    }),
  ).toBeDisabled();
  await compare.click();
  await expect(target.locator(".modelo-write-hold")).toContainText(
    label("workspace.modelo.write_hold.unresolved"),
  );
  await expect(compare).toBeDisabled();
  await tab(target, "desktop.modelo.view.form").click();
  await tab(target, "workspace.modelo.filing.title").click();
  await expect(compare).toBeDisabled();
  expect(await target.evaluate(() => window.__modeloCompared)).toMatchObject({
    sourceKind: "declaration",
    count: 1,
  });
});

for (const shape of ["limited-match", "missing-value"] as const) {
  test(`reconciliation preserves ${shape} without inventing values or verification`, async ({
    page: target,
  }) => {
    await filing(target, "filed");
    const answer =
      envelope<ModeloReconciliationImportProjection>("reconcile-130");
    if (shape === "limited-match") {
      answer.verdict = "matches";
      answer.narrative = "Test comparison limited to identity.";
      answer.diffs = [];
      expect(answer.advisories.length).toBeGreaterThan(0);
    } else {
      answer.diffs = [
        {
          field_name: "01",
          work_unit_value: "0.00",
          evidence_value: "",
          kind: "casilla_missing_in_filed",
          diff_kind: "casilla",
          legal_refs: ["test-legal-reference"],
          source_refs: ["test-source-reference"],
        },
      ];
    }
    await target.evaluate((answer) => {
      const port = window.__fixtureModelo!;
      const submit = port.submit;
      port.submit = async (...args) => {
        const result = await submit(...args);
        return args[0] === "modelo.reconcile.import" &&
          result.kind === "settled"
          ? ({ ...result, result: answer } as typeof result)
          : result;
      };
    }, answer);
    await target
      .getByRole("button", {
        name: label("workspace.modelo.filing.add_receipt_pdf"),
      })
      .click();
    const report = target.locator(".modelo-reconciliation");
    await expect(report.locator('[data-slot="alert"]')).toHaveAttribute(
      "data-tone",
      "warning",
    );
    if (shape === "limited-match") {
      await expect(report).toContainText(
        label("workspace.modelo.filing.reconciliation.matches"),
      );
      for (const advisory of answer.advisories)
        await expect(report).toContainText(advisory.message);
    } else {
      await expect(report.getByText("0.00", { exact: true })).toBeVisible();
      await expect(
        report.getByText(
          label("workspace.modelo.filing.reconciliation.not_present"),
          { exact: true },
        ),
      ).toBeVisible();
      await expect(
        report.getByText("test-legal-reference", { exact: true }),
      ).toBeVisible();
      await expect(
        report.getByText("test-source-reference", { exact: true }),
      ).toBeVisible();
      await expect(report.getByRole("link")).toHaveCount(0);
    }
  });
}

/** Opens the correction of the receipt-confirmed 130 in `shape` and sends
 * one corrected figure, with the reason. */
async function correct(target: Page, shape: string, figure: string) {
  const context = envelope<{
    correction: {
      reason_prompt: string;
      rows: { casilla_id: string; box: string | null; label: string }[];
    };
  }>("amendment-context-130").correction;
  await openDeclaration(target, "130", { shape });
  await target
    .getByRole("button", { name: label("workspace.modelo.correction.title") })
    .first()
    .click();
  const dialog = target.getByRole("dialog", {
    name: label("workspace.modelo.correction.title"),
  });
  await dialog
    .getByRole("textbox", { name: context.reason_prompt })
    .fill("Income was understated in the recorded declaration.");
  const row = context.rows.find((entry) => entry.casilla_id === "01")!;
  await dialog
    .getByRole("textbox", {
      name: label("workspace.modelo.editor.new_value_for_box", {
        box: row.box ?? row.label,
      }),
    })
    .fill(figure);
  await dialog
    .getByRole("button", { name: label("workspace.modelo.correction.confirm") })
    .click();
  return dialog;
}

test("a correction that settles closes and the declaration is read again", async ({
  page: target,
}) => {
  const dialog = await correct(target, "receipt", "10000");
  await expect(dialog).toBeHidden();
  expect(await calls(target, "modelo submit modelo.work.amend")).toHaveLength(
    1,
  );
  const pending = form("130-1T-correction-1-pending").receipt;
  if (!pending || pending.verified)
    throw new Error("The corrected filing must await official confirmation");
  await tab(target, "workspace.modelo.filing.title").click();
  await expect(target.getByText(pending.words).first()).toBeVisible();
  await expect(
    target.getByText(label("workspace.modelo.filing.not_confirmed_yet")),
  ).toBeVisible();
});

test("a corrected figure the application cannot read is said beside it, and nothing is sent", async ({
  page: target,
}) => {
  const read = envelope<{ parsed: { refusal_words: string | null }[] }>(
    "preflight-130-1T-receipt-correction-refused",
  ).parsed[0];
  if (!read?.refusal_words)
    throw new Error("the unreadable entry has no words");
  const dialog = await correct(target, "receipt", "doce");
  await expect(dialog).toContainText(read.refusal_words);
  expect(await calls(target, "modelo submit modelo.work.amend")).toHaveLength(
    0,
  );
});

test("a refused correction says so and keeps the dialog", async ({
  page: target,
}) => {
  const dialog = await correct(target, "correction-refused", "10000");
  await expect(dialog).toBeVisible();
  // The sentence does not name the code the host refused it with.
  await expect(dialog).toContainText(label("workspace.modelo.outcome.refused"));
  await expect(dialog).not.toContainText("operation_denied");
});

test("a correction whose settlement was not seen is unknown and sends nothing more", async ({
  page: target,
}) => {
  const dialog = await correct(target, "correction-unknown", "10000");
  await expect(dialog).toContainText(
    label("workspace.modelo.write_hold.unknown"),
  );
  await expect(
    dialog.getByRole("button", {
      name: label("workspace.modelo.correction.confirm"),
    }),
  ).toBeDisabled();
  expect(await calls(target, "modelo submit modelo.work.amend")).toHaveLength(
    1,
  );
});

test("recording the filing reads the declaration again by itself, with no hold to press", async ({
  page: target,
}) => {
  await filing(target, "exported");
  const before = (await calls(target, "modelo form")).length;
  // The window's own read after the write is held open, as a slow host's is.
  await target.evaluate(() => {
    const port = window.__fixtureModelo!;
    const form = port.form;
    const gate = window as unknown as { __releaseRead?: () => void };
    port.form = async (...args) => {
      await new Promise<void>((release) => {
        gate.__releaseRead = release;
      });
      return form(...args);
    };
  });
  await target
    .getByRole("button", {
      name: label("workspace.modelo.filing.record_as_filed"),
    })
    .click();
  await target
    .getByRole("dialog")
    .getByRole("button", {
      name: label("application.modelo.lifecycle.file_confirm_accept"),
    })
    .click();
  await expect
    .poll(async () => calls(target, "modelo submit modelo.work.file"))
    .toHaveLength(1);
  await expect
    .poll(() =>
      target.evaluate(
        () =>
          typeof (window as unknown as { __releaseRead?: () => void })
            .__releaseRead,
      ),
    )
    .toBe("function");
  // The window is reading: it asks nobody to read again.
  await target.waitForTimeout(800);
  await expect(target.locator(".modelo-write-hold")).toHaveCount(0);
  await target.evaluate(() =>
    (window as unknown as { __releaseRead: () => void }).__releaseRead(),
  );
  await expect(
    target.getByText(label("workspace.modelo.filing.recorded_here")).first(),
  ).toBeVisible();
  await expect
    .poll(async () => (await calls(target, "modelo form")).length - before)
    .toBe(1);
  await expect(target.locator(".modelo-write-hold")).toHaveCount(0);
});
