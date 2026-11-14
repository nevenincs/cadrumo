import { expect, test } from "@playwright/test";
import { ASSET_NOTES } from "../../src/dev/modeloAssetNotes";
import { label } from "../support/strings";
import {
  declarations,
  envelope,
  FILING_FILE,
  LANGUAGES,
  list,
  openDeclaration,
  rowsOf,
  tab,
  views,
} from "../support/scenarioModelo";
import { calls, filing, refusal } from "../support/scenarioModeloWrites";

test("an export writes the file the filer saved, through its save token", async ({
  page: target,
}) => {
  await filing(target, "exported");
  await target
    .getByRole("button", {
      name: label("workspace.modelo.filing.export_again"),
    })
    .click();
  await expect(
    target.getByText(
      label("workspace.modelo.filing.saved", {
        name: FILING_FILE,
      }),
    ),
  ).toBeVisible();
  // The file was named in the save dialog and sent as its token; the file
  // the export wrote is shown in its folder.
  expect(await calls(target, "modelo saveFile")).toHaveLength(1);
  expect(await calls(target, "modelo submit modelo.export")).toHaveLength(1);
  await expect(
    target.getByText(label("workspace.modelo.filing.completeness_unverified")),
  ).toHaveCount(0);
  await target
    .getByRole("button", {
      name: label("workspace.modelo.filing.show_in_folder"),
    })
    .click();
  expect(await calls(target, "modelo revealFile")).toHaveLength(1);
});

for (const language of LANGUAGES) {
  test(`an export states what its calculation noted about the assets, in ${language}`, async ({
    page: target,
  }) => {
    await target.goto(
      `/scenarios.html?scenario=ledger&latency=0&bar=off&lang=${language}&modelo=export-notes`,
    );
    await target.locator("[data-rail=declarations]").click();
    const grid = declarations(target, language);
    await expect(grid.getByRole("row").nth(1)).toBeVisible({ timeout: 15_000 });
    const local = list(language).rows.find(
      (row) => row.modelo === "130" && row.opens_local_work,
    );
    if (!local) throw new Error("no local declaration of 130 is listed");
    await target
      .getByRole("searchbox", {
        name: label("desktop.declarations.search.label", {}, language),
      })
      .fill("130");
    await rowsOf(grid, "130")
      .filter({ hasText: local.period_words ?? local.modelo_title })
      .filter({ hasText: local.state_words })
      .first()
      .dblclick();
    await expect(views(target, language)).toBeVisible();
    await tab(target, "workspace.modelo.filing.title", language).click();
    // Nothing is said before a file is made.
    const notes = target.getByRole("region", {
      name: label("workspace.modelo.notes.title", {}, language),
    });
    await expect(notes).toHaveCount(0);
    await target
      .getByRole("button", {
        name: label("workspace.modelo.filing.export_again", {}, language),
      })
      .click();
    await expect(notes).toBeVisible();
    const items = notes.getByRole("listitem");
    await expect(items).toHaveCount(ASSET_NOTES.length);
    // Each note is its own item: its sentence with its values, then its kind.
    for (const note of ASSET_NOTES) {
      const item = items.filter({ hasText: note.message });
      await expect(item).toHaveCount(1);
      await expect(item).toContainText(note.detail);
    }
    await expect(notes.getByRole("button")).toHaveCount(0);
    // No catalogue key and no unfilled value reaches the filer.
    const said = await notes.innerText();
    expect(said).not.toMatch(/application\.modelo|workspace\.modelo|\{\w+\}/);
  });
}

test("an export that cannot vouch for its completeness says so", async ({
  page: target,
}) => {
  expect(
    envelope<{ completeness: string }>("export-165-unverified").completeness,
  ).toBe("unverified");
  await filing(target, "export-unverified");
  await target
    .getByRole("button", {
      name: label("workspace.modelo.filing.export_again"),
    })
    .click();
  await expect(
    target.getByText(label("workspace.modelo.filing.completeness_unverified")),
  ).toBeVisible();
});

/** The warning an export states when its result says no direct-debit cutoff
 * was checked. */
const CUTOFF_UNVERIFIED = "tui.modelo.export.result.warning.cutoff_unverified";

test("an export whose result says its direct-debit cutoff was checked states no cutoff warning", async ({
  page: target,
}) => {
  const exported = envelope<{
    fichero_boe: { domiciliation_cutoff_unverified: boolean };
  }>("export-130");
  expect(exported.fichero_boe.domiciliation_cutoff_unverified).toBe(false);
  await filing(target, "exported");
  await target
    .getByRole("button", {
      name: label("workspace.modelo.filing.export_again"),
    })
    .click();
  const saved = target.getByText(
    label("workspace.modelo.filing.saved", { name: FILING_FILE }),
  );
  await expect(saved).toBeVisible();
  await expect(target.getByText(label(CUTOFF_UNVERIFIED))).toHaveCount(0);
});

test("an export whose result says no direct-debit cutoff was checked says so beside the saved file", async ({
  page: target,
}) => {
  await filing(target, "export-cutoff-unverified");
  await target
    .getByRole("button", {
      name: label("workspace.modelo.filing.export_again"),
    })
    .click();
  const notice = target.getByRole("status").filter({
    hasText: label("workspace.modelo.filing.saved", {
      name: FILING_FILE,
    }),
  });
  await expect(notice).toBeVisible();
  // The warning is the sentence the command line states for the same flag,
  // in the notice that says the file is not proof of filing.
  await expect(notice.getByText(label(CUTOFF_UNVERIFIED))).toBeVisible();
  await expect(
    notice.getByText(label("workspace.modelo.filing.completeness_unverified")),
  ).toHaveCount(0);
});

for (const language of ["en", "es"] as const)
  test(`a refused export says why in the sentence the backend served, in ${language}`, async ({
    page: target,
  }) => {
    const served = refusal("domiciliation-past-cutoff", language);
    if (!served.refusal_words) throw new Error("the refusal serves no words");
    await openDeclaration(target, "130", {
      shape: "export-past-cutoff",
      language,
    });
    await tab(target, "workspace.modelo.filing.title", language).click();
    await target
      .getByRole("button", {
        name: label("workspace.modelo.filing.export_again", {}, language),
      })
      .click();
    const notice = target
      .getByText(served.refusal_words, { exact: true })
      .first();
    await expect(notice).toBeVisible();
    // The served sentence carries the cutoff and its legal references; the
    // window shows it as served and names neither code nor generic notice.
    await expect(notice).toContainText("Orden HAC/3625/2003, art. 3");
    await expect(
      target.getByText(
        label("workspace.modelo.outcome.not_done", {}, language),
      ),
    ).toHaveCount(0);
    await expect(target.getByText(served.error_code)).toHaveCount(0);
  });

test("a refused report of an outdated calculation says why in the sentence the backend served", async ({
  page: target,
}) => {
  const served = refusal("report-outdated");
  if (!served.refusal_words) throw new Error("the refusal serves no words");
  await filing(target, "report-outdated");
  await target
    .getByRole("button", {
      name: label("workspace.modelo.filing.copy.calculation_report_pdf.action"),
    })
    .click();
  await expect(
    target.getByText(served.refusal_words, { exact: true }).first(),
  ).toBeVisible();
  await expect(
    target.getByText(label("workspace.modelo.outcome.not_done")),
  ).toHaveCount(0);
});

test("an export whose settlement was not seen is unknown and holds", async ({
  page: target,
}) => {
  await filing(target, "export-unknown");
  const exportAgain = target.getByRole("button", {
    name: label("workspace.modelo.filing.export_again"),
  });
  await exportAgain.click();
  await expect(
    target.getByText(label("workspace.modelo.write_hold.unknown")).first(),
  ).toBeVisible();
  await expect(exportAgain).toBeDisabled();
  expect(await calls(target, "modelo submit modelo.export")).toHaveLength(1);
  await tab(target, "workspace.modelo.history.title").click();
  await expect(
    target.getByRole("button", {
      name: label("workspace.modelo.history.rename"),
      exact: true,
    }),
  ).toBeDisabled();
  await target
    .locator(".declarations-workspace")
    .getByRole("button", {
      name: label("workspace.declarations.destination.overview"),
      exact: true,
    })
    .click();
  const local = list().rows.find(
    (row) => row.modelo === "130" && row.opens_local_work,
  )!;
  await rowsOf(declarations(target, "en"), "130")
    .filter({ hasText: local.period_words ?? local.modelo_title })
    .filter({ hasText: local.state_words })
    .first()
    .dblclick();
  await expect(target.locator(".modelo-write-hold")).toBeVisible();
  await tab(target, "workspace.modelo.filing.title").click();
  await expect(exportAgain).toBeDisabled();
  expect(await calls(target, "modelo submit modelo.export")).toHaveLength(1);
  const listsBeforeCompletion = (await calls(target, "modelo declarations"))
    .length;
  await target.evaluate(() => {
    window.__fixtureModelo!.observe = async (operation) => ({
      kind: "refused",
      operation_id: operation,
      revision: 2,
      reason: null,
      detail: null,
    });
  });
  await target
    .getByRole("button", {
      name: label("workspace.modelo.write_hold.check_status"),
    })
    .click();
  await target
    .getByRole("button", { name: label("workspace.modelo.read_again") })
    .click();
  await expect(target.locator(".modelo-write-hold")).toHaveCount(0);
  await target
    .locator(".declarations-workspace")
    .getByRole("button", {
      name: label("workspace.declarations.destination.overview"),
      exact: true,
    })
    .click();
  await expect
    .poll(async () => (await calls(target, "modelo declarations")).length)
    .toBeGreaterThan(listsBeforeCompletion);
});

for (const picker of ["saveFile", "pickFile"] as const) {
  test(`a late ${picker} result releases its files without submitting after leaving filing`, async ({
    page: target,
  }) => {
    await filing(target, picker === "saveFile" ? "exported" : "filed");
    await target.evaluate((method) => {
      const port = window.__fixtureModelo!;
      let release!: () => void;
      const waiting = new Promise<void>((done) => {
        release = done;
      });
      const state = (window.__modeloFileGate = {
        release,
        tokens: [] as string[],
        forgotten: [] as string[],
      });
      const forget = port.forgetFiles;
      port.forgetFiles = async (tokens) => {
        state.forgotten.push(...tokens);
        return forget(tokens);
      };
      if (method === "saveFile") {
        const pick = port.saveFile;
        port.saveFile = async (...args) => {
          const result = await pick(...args);
          state.tokens.push(...result.files.map((file) => file.token));
          await waiting;
          return result;
        };
      } else {
        const pick = port.pickFile;
        port.pickFile = async (...args) => {
          const result = await pick(...args);
          state.tokens.push(...result.files.map((file) => file.token));
          await waiting;
          return result;
        };
      }
    }, picker);
    await target
      .getByRole("button", {
        name: label(
          picker === "saveFile"
            ? "workspace.modelo.filing.export_again"
            : "workspace.modelo.filing.add_receipt_pdf",
        ),
      })
      .click();
    await expect
      .poll(() => target.evaluate(() => window.__modeloFileGate!.tokens.length))
      .toBe(1);
    await tab(target, "desktop.modelo.view.form").click();
    await target.evaluate(() => window.__modeloFileGate!.release());
    await expect
      .poll(() => target.evaluate(() => window.__modeloFileGate!.forgotten))
      .toEqual(await target.evaluate(() => window.__modeloFileGate!.tokens));
    expect(
      await calls(
        target,
        picker === "saveFile"
          ? "modelo submit modelo.export"
          : "modelo submit modelo.reconcile.import",
      ),
    ).toHaveLength(0);
    await tab(target, "workspace.modelo.filing.title").click();
    await expect(
      target.getByRole("button", {
        name: label(
          picker === "saveFile"
            ? "workspace.modelo.filing.export_again"
            : "workspace.modelo.filing.add_receipt_pdf",
        ),
      }),
    ).toBeEnabled();
  });
}

test("an export that settles after leaving filing releases its output token and reads the declaration again itself", async ({
  page: target,
}) => {
  await filing(target, "exported");
  await target.evaluate(() => {
    const port = window.__fixtureModelo!;
    let release!: () => void;
    const waiting = new Promise<void>((done) => {
      release = done;
    });
    const state = (window.__modeloFileGate = {
      release,
      tokens: [] as string[],
      forgotten: [] as string[],
    });
    const save = port.saveFile;
    port.saveFile = async (...args) => {
      const result = await save(...args);
      state.tokens.push(...result.files.map((file) => file.token));
      return result;
    };
    const forget = port.forgetFiles;
    port.forgetFiles = async (tokens) => {
      state.forgotten.push(...tokens);
      return forget(tokens);
    };
    const submit = port.submit;
    port.submit = async (...args) => {
      const result = await submit(...args);
      if (args[0] === "modelo.export") await waiting;
      return result;
    };
  });
  await target
    .getByRole("button", {
      name: label("workspace.modelo.filing.export_again"),
    })
    .click();
  await expect
    .poll(
      async () => (await calls(target, "modelo submit modelo.export")).length,
    )
    .toBe(1);
  await tab(target, "desktop.modelo.view.form").click();
  const readsBeforeSettling = (await calls(target, "modelo form")).length;
  await target.evaluate(() => window.__modeloFileGate!.release());
  await expect
    .poll(() => target.evaluate(() => window.__modeloFileGate!.forgotten))
    .toEqual(await target.evaluate(() => window.__modeloFileGate!.tokens));
  // The write was this window's own and its view has gone: the scope reads
  // the declaration itself, so no reload control is left to press.
  await expect
    .poll(async () => (await calls(target, "modelo form")).length)
    .toBeGreaterThan(readsBeforeSettling);
  await expect(target.locator(".modelo-write-hold")).toHaveCount(0);
  expect(await calls(target, "modelo submit modelo.export")).toHaveLength(1);
});
