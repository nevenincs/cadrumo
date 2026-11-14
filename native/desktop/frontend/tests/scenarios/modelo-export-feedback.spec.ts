import { expect, test, type Page } from "@playwright/test";
import { label } from "../support/strings";
import {
  declarations,
  list,
  openList,
  rowsOf,
  tab,
  views,
} from "../support/scenarioModelo";
import { calls } from "../support/scenarioModeloWrites";

// Pressing the export button must always end in a file or in words: a
// cancelled or lost save dialog, a request that never settles and a read model
// that offers nothing to save each say so, and a wait shows that it is waiting.

const EXPORT = () => label("workspace.modelo.filing.export_again", {}, "en");
const BUSY = () => label("desktop.navigation.busy");
const NOT_DONE = () => label("workspace.modelo.outcome.not_done");

/** Opens the Export and record view of the 130 after `patch` has run on the
 * scenario's modelo port, which the first list read has already created. */
async function openFiling(target: Page, patch: () => void) {
  const grid = await openList(target, { shape: "exported" });
  await target.evaluate(patch);
  const local = list().rows.find(
    (row) => row.modelo === "130" && row.opens_local_work,
  );
  if (!local) throw new Error("no local declaration of 130 is listed");
  await target
    .getByRole("searchbox", {
      name: label("desktop.declarations.search.label", {}, "en"),
    })
    .fill("130");
  await rowsOf(declarations(target, "en"), "130")
    .filter({ hasText: local.period_words ?? local.modelo_title })
    .filter({ hasText: local.state_words })
    .first()
    .dblclick();
  await expect(views(target, "en")).toBeVisible();
  await tab(target, "workspace.modelo.filing.title").click();
  void grid;
}

const exportButton = (target: Page) =>
  target.getByRole("button", { name: EXPORT() });

test("a save dialog closed without a choice says nothing was done", async ({
  page: target,
}) => {
  await openFiling(target, () => {
    window.__fixtureModelo!.saveFile = async () => ({ files: [], refused: 0 });
  });
  await exportButton(target).click();
  await expect(target.getByText(NOT_DONE())).toBeVisible();
  expect(await calls(target, "modelo submit modelo.export")).toHaveLength(0);
});

test("a save dialog that fails says nothing was done", async ({
  page: target,
}) => {
  await openFiling(target, () => {
    window.__fixtureModelo!.saveFile = async () => {
      throw new Error("the host has no dialog");
    };
  });
  await exportButton(target).click();
  await expect(target.getByText(NOT_DONE())).toBeVisible();
});

test("a save dialog that has not answered shows that it is waiting", async ({
  page: target,
}) => {
  await openFiling(target, () => {
    window.__fixtureModelo!.saveFile = () => new Promise(() => undefined);
  });
  await exportButton(target).click();
  await expect(exportButton(target)).toBeDisabled();
  await expect(target.getByText(BUSY())).toBeVisible();
  await expect(
    exportButton(target).locator('[data-slot="spinner"], [role="progressbar"]'),
  ).not.toHaveCount(0);
});

test("an export that is still running shows that it is waiting", async ({
  page: target,
}) => {
  await openFiling(target, () => {
    const port = window.__fixtureModelo!;
    const running = {
      kind: "running" as const,
      operation_id: "operation-export-running",
      revision: 1,
      cancellable: false,
    };
    const submit = port.submit;
    port.submit = async (...args) => {
      await submit(...args);
      return running;
    };
    port.observe = async () => running;
  });
  await exportButton(target).click();
  await expect(target.getByText(BUSY())).toBeVisible();
  await expect(exportButton(target)).toBeDisabled();
  await expect(
    exportButton(target).locator('[data-slot="spinner"], [role="progressbar"]'),
  ).not.toHaveCount(0);
});

test("a read model that names no file kind to save says nothing was done", async ({
  page: target,
}) => {
  await openFiling(target, () => {
    const port = window.__fixtureModelo!;
    const form = port.form;
    port.form = async (...args) => {
      const read = await form(...args);
      for (const option of read.export_offer?.artefacts ?? [])
        option.save_format = null;
      return read;
    };
  });
  await exportButton(target).click();
  await expect(target.getByText(NOT_DONE())).toBeVisible();
  expect(await calls(target, "modelo saveFile")).toHaveLength(0);
});

test("a read model with no calculation to export says nothing was done", async ({
  page: target,
}) => {
  await openFiling(target, () => {
    const port = window.__fixtureModelo!;
    const form = port.form;
    port.form = async (...args) => {
      const read = await form(...args);
      read.calculation_revision_id = null;
      return read;
    };
  });
  await exportButton(target).click();
  await expect(target.getByText(NOT_DONE())).toBeVisible();
  expect(await calls(target, "modelo saveFile")).toHaveLength(0);
});
