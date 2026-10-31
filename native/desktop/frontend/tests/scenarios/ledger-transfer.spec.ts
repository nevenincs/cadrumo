import { expect, test, type Locator, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { label } from "../support/strings";

// The Ledger page's Import and Export dialogs over the scenario host's
// made-up ledger: a bank statement previewed and applied exactly as read,
// an invoice book, documents, and an export whose file is chosen last.

const engine = readFileSync(
  fileURLToPath(
    new URL("../../node_modules/axe-core/axe.min.js", import.meta.url),
  ),
  "utf8",
);

const STUDIO = "extracto-cuenta-estudio-2026-10.csv";
const PERSONAL = "extracto-cuenta-personal-2026-10.ofx";
const CARD = "movimientos-tarjeta.pdf";
/** What an absolute path looks like on any platform. */
const PATH = /(?<![A-Za-z0-9])[A-Za-z]:[\\/](?![\\/])|\/(?:Users|home)\//;

/** The export's own button, with its count or without. */
const SEND = new RegExp(
  `^${label("desktop.ledger.export.send_unknown")}( \\(\\d+\\))?$`,
);
const head = (target: Page) => target.locator(".pane-docs .pane-head");
const importDialog = (target: Page) =>
  target.getByRole("dialog", { name: label("desktop.ledger.import.title") });
const exportDialog = (target: Page) =>
  target.getByRole("dialog", { name: label("desktop.ledger.export.title") });
const button = (scope: Page | Locator, key: string, values = {}) =>
  scope.getByRole("button", { name: label(key, values), exact: true });

async function openLedger(target: Page, scheme?: "light" | "dark") {
  if (scheme)
    await target.addInitScript((appearance) => {
      localStorage.setItem(
        "cadrumo-shell-layout",
        JSON.stringify({ prefs: { appearance } }),
      );
    }, scheme);
  await target.goto("/scenarios.html?scenario=ledger&latency=0&bar=off");
  await target.locator("[data-rail=ledger]").click();
  await expect(target.locator(".ledger-page")).toBeVisible();
  await expect(target.locator(".ledger-movements")).toBeVisible();
}

async function openImport(target: Page) {
  await button(head(target), "desktop.ledger.action.import").click();
  const dialog = importDialog(target);
  await expect(dialog).toBeVisible();
  // Focus starts on the step's heading.
  await expect(
    dialog.getByRole("heading", {
      name: label("desktop.ledger.import.heading.what"),
    }),
  ).toBeFocused();
  return dialog;
}

async function chooseKind(dialog: Locator, kind: string) {
  await dialog
    .getByRole("radio", { name: label(`desktop.ledger.import.kind.${kind}`) })
    .click();
}

const fileRow = (dialog: Locator, name: string) =>
  dialog.getByRole("listitem").filter({ hasText: name });

async function previewStatements(target: Page) {
  const dialog = await openImport(target);
  await button(dialog, "desktop.ledger.import.choose_files").click();
  await expect(
    dialog.getByText(label("desktop.ledger.import.left_out", { count: 1 })),
  ).toBeVisible();
  await expect(
    dialog
      .getByRole("list", { name: label("desktop.ledger.import.chosen") })
      .getByRole("listitem"),
  ).toHaveCount(3);
  await button(dialog, "desktop.ledger.import.preview").click();
  await expect(
    dialog.getByRole("heading", {
      name: label("desktop.ledger.import.heading.preview"),
    }),
  ).toBeFocused();
  await expect(fileRow(dialog, STUDIO)).toContainText(
    label("desktop.ledger.import.file_counts", {
      rows: 14,
      fresh: 14,
      skipped: 0,
    }),
  );
  return dialog;
}

async function audit(target: Page) {
  await target.evaluate(engine);
  return target.evaluate(async () => {
    const axe = (
      window as unknown as {
        axe: {
          run(
            context: unknown,
            options: unknown,
          ): Promise<{
            violations: { id: string; nodes: { target: string[] }[] }[];
          }>;
        };
      }
    ).axe;
    const result = await axe.run(
      { exclude: [[".docs-frame"], [".xterm"]] },
      { resultTypes: ["violations"] },
    );
    return result.violations.map((violation) => ({
      id: violation.id,
      nodes: violation.nodes.map((node) => node.target.join(" ")),
    }));
  });
}

async function noPathShown(target: Page) {
  const shown = await target.evaluate(
    () => `${document.body.innerText}\n${document.body.outerHTML}`,
  );
  expect(shown).not.toMatch(PATH);
}

test("a bank statement is previewed per file, applied as previewed, and a changed file is refused", async ({
  page: target,
}) => {
  await openLedger(target);
  const dialog = await previewStatements(target);

  // The statement that names no account waits for a choice; the one whose
  // rows name a registered account says so; the unreadable one is refused.
  const studioAccount = fileRow(dialog, STUDIO).getByRole("combobox", {
    name: label("desktop.ledger.import.account"),
  });
  await expect(studioAccount).toHaveValue("");
  // A detected account is the same choice, made already and changeable.
  const personalAccount = fileRow(dialog, PERSONAL).getByRole("combobox", {
    name: label("desktop.ledger.import.account"),
  });
  await expect(personalAccount).toHaveAccessibleDescription(
    label("desktop.ledger.import.account_detected"),
  );
  await expect(personalAccount.locator("option:checked")).toHaveText(
    /Cuenta personal/,
  );
  await expect(fileRow(dialog, CARD)).toContainText(
    label("desktop.ledger.import.refusal.transaction_validation"),
  );
  // Likely duplicates are a glyph and a count, their words in a popover.
  const duplicates = fileRow(dialog, STUDIO).getByRole("button", {
    name: label("desktop.ledger.import.duplicates_chip", { count: 2 }),
  });
  // Marked with the copy glyph the grid and the strip use, not readiness's.
  await expect(duplicates.locator("[data-icon=copy]")).toHaveCount(1);
  await duplicates.click();
  await expect(
    target.getByRole("dialog", {
      name: label("desktop.ledger.import.duplicates_chip", { count: 2 }),
    }),
  ).toContainText(label("desktop.ledger.import.duplicates_note"));
  await target.keyboard.press("Escape");
  await expect(dialog).toBeVisible();
  const apply = button(dialog, "desktop.ledger.import.apply_files", {
    count: 2,
  });
  await expect(apply).toBeDisabled();
  await expect(
    dialog.getByText(label("desktop.ledger.import.choose_accounts")),
  ).toBeVisible();
  await studioAccount.selectOption({ label: "Cuenta del estudio · ES**1234" });
  await expect(apply).toBeEnabled();
  await noPathShown(target);

  // The OFX changes on disk after its preview: it is refused, the other
  // file imports, and the changed one is previewed again before it imports.
  await target.evaluate(
    (name) => window.__scenarioLedger!.changeFile(name),
    PERSONAL,
  );
  await apply.click();
  await expect(
    dialog.getByRole("heading", {
      name: label("desktop.ledger.import.heading.result"),
    }),
  ).toBeFocused();
  await expect(fileRow(dialog, PERSONAL)).toContainText(
    label("desktop.ledger.import.refusal.source_changed"),
  );
  await expect(fileRow(dialog, STUDIO)).toContainText(
    label("desktop.ledger.import.file_imported", { fresh: 14, skipped: 0 }),
  );
  await expect(
    dialog.getByText(label("desktop.ledger.import.imported", { count: 14 })),
  ).toBeVisible();
  await button(dialog, "desktop.ledger.import.preview_again").click();
  await expect(
    dialog
      .getByRole("list", { name: label("desktop.ledger.import.files") })
      .getByRole("listitem"),
  ).toHaveCount(1);
  await expect(fileRow(dialog, PERSONAL)).toContainText(
    label("desktop.ledger.import.account_detected"),
  );
  await button(dialog, "desktop.ledger.import.apply_files", {
    count: 1,
  }).click();
  await expect(fileRow(dialog, PERSONAL)).toContainText(
    label("desktop.ledger.import.file_imported", { fresh: 9, skipped: 0 }),
  );
  await button(dialog, "desktop.ledger.import.done").click();
  await expect(dialog).toBeHidden();

  // Importing the same files again brings nothing new.
  const again = await previewStatements(target);
  await fileRow(again, STUDIO)
    .getByRole("combobox", { name: label("desktop.ledger.import.account") })
    .selectOption({ label: "Cuenta del estudio · ES**1234" });
  await expect(fileRow(again, STUDIO)).toContainText(
    label("desktop.ledger.import.file_counts", {
      rows: 14,
      fresh: 0,
      skipped: 14,
    }),
  );
  await expect(
    again.getByText(label("desktop.ledger.import.nothing_new_note")),
  ).toBeVisible();
  await expect(
    button(again, "desktop.ledger.import.nothing_new"),
  ).toBeDisabled();
});

test("likely duplicates are imported and compared with the movement already in the ledger", async ({
  page: target,
}) => {
  await openLedger(target);
  const dialog = await previewStatements(target);
  await fileRow(dialog, STUDIO)
    .getByRole("combobox", { name: label("desktop.ledger.import.account") })
    .selectOption({ label: label("desktop.ledger.import.no_account") });
  await button(dialog, "desktop.ledger.import.apply_files", {
    count: 2,
  }).click();
  const flagged = dialog.getByRole("region", {
    name: label("desktop.ledger.import.duplicates"),
  });
  await expect(flagged.getByRole("listitem")).toHaveCount(2);
  await flagged
    .getByRole("button", { name: label("desktop.ledger.import.compare") })
    .first()
    .click();
  const compare = target.getByRole("dialog", {
    name: label("desktop.ledger.import.compare_title"),
  });
  await expect(compare).toBeVisible();
  await expect(compare).toContainText(
    label("desktop.ledger.import.compare_imported"),
  );
  await expect(compare).toContainText(
    label("desktop.ledger.import.compare_existing"),
  );
  // The existing movement sits on the same day with the same amount.
  await expect(compare.locator(".bg-accent").nth(1)).toBeVisible();
  await expect(compare).not.toContainText(
    label("desktop.ledger.import.compare_none"),
  );
  await target.keyboard.press("Escape");
  await expect(compare).toBeHidden();
  await expect(dialog).toBeVisible();

  // The imported movements are shown over their own days.
  await button(dialog, "desktop.ledger.import.show_imported").click();
  await expect(dialog).toBeHidden();
  await expect(head(target).locator(".ledger-period")).toHaveText(/2026 · Oct/);
  await expect(target.locator(".ledger-shown-import")).toBeVisible();
  await noPathShown(target);
});

test("an invoice book has no preview and lists the rows it refused", async ({
  page: target,
}) => {
  await openLedger(target);
  const dialog = await openImport(target);
  await chooseKind(dialog, "book");
  await button(dialog, "desktop.ledger.import.choose_file").click();
  await expect(dialog).toContainText("libro-facturas-recibidas-2026.xlsx");
  const preview = button(dialog, "desktop.ledger.import.preview");
  // The book's kind has no default.
  await expect(preview).toBeDisabled();
  await dialog
    .getByRole("radio", { name: label("desktop.ledger.import.kind_received") })
    .click();
  const country = dialog.getByRole("combobox", {
    name: label("desktop.ledger.import.country"),
  });
  await expect(country).toHaveValue("");
  await country.fill("e");
  await expect(preview).toBeDisabled();
  await country.fill("es");
  // Left, the field shows the code it holds with its name in the window's
  // language, which in English is Spain.
  await country.blur();
  await expect(country).toHaveValue("ES · Spain");
  await preview.click();
  await expect(dialog).toContainText(
    label("desktop.ledger.import.book_no_preview"),
  );
  await button(dialog, "desktop.ledger.import.apply_book").click();
  await expect(
    dialog.getByText(label("desktop.ledger.import.book_created", { count: 4 })),
  ).toBeVisible();
  const refused = dialog.getByRole("table", {
    name: label("desktop.ledger.import.refused_rows"),
  });
  await expect(refused.getByRole("row")).toHaveCount(2);
  await expect(refused.getByRole("row").nth(1)).toContainText("5");
  await expect(refused).toContainText(
    "B0000004 is not a valid tax identification number.",
  );
  await expect(dialog).toContainText(
    label("desktop.ledger.import.unmapped", { columns: "Observaciones" }),
  );
  await noPathShown(target);
});

test("documents are added as evidence and a drop on the window adds files", async ({
  page: target,
}) => {
  await openLedger(target);
  const dialog = await openImport(target);
  await chooseKind(dialog, "documents");
  await expect(dialog).toContainText(
    label("desktop.ledger.import.accepts.documents"),
  );
  await button(dialog, "desktop.ledger.import.choose_files").click();
  await expect(dialog).toContainText("factura-estudio-lumen.xml");
  await target.evaluate(() =>
    window.__scenarioLedger!.drop(["ticket-taxi-0912.png", "notas.docx"]),
  );
  const chosen = dialog.getByRole("list", {
    name: label("desktop.ledger.import.chosen"),
  });
  await expect(chosen.getByRole("listitem")).toHaveCount(4);
  await expect(
    dialog.getByText(label("desktop.ledger.import.left_out", { count: 1 })),
  ).toBeVisible();
  const preview = button(dialog, "desktop.ledger.import.preview");
  await expect(preview).toBeDisabled();
  await dialog
    .getByRole("radio", { name: label("desktop.ledger.import.kind_received") })
    .click();
  await preview.click();
  await button(dialog, "desktop.ledger.import.apply_documents", {
    count: 4,
  }).click();
  await expect(
    dialog.getByText(
      label("desktop.ledger.import.documents_added", { count: 4 }),
    ),
  ).toBeVisible();
  await expect(dialog).toContainText(
    label("desktop.ledger.import.documents_result", {
      waiting: 2,
      held: 0,
      paused: 0,
    }),
  );
  await button(dialog, "desktop.ledger.import.show_documents").click();
  await expect(dialog).toBeHidden();
  await expect(
    head(target).getByRole("tab", {
      name: label("desktop.ledger.section.documents"),
    }),
  ).toHaveAttribute("aria-selected", "true");
});

test("the export file is chosen last and cleared when the format or period changes", async ({
  page: target,
}) => {
  await openLedger(target);
  await button(head(target), "desktop.ledger.action.export").click();
  const dialog = exportDialog(target);
  await expect(
    dialog.getByRole("heading", {
      name: label("desktop.ledger.export.heading"),
    }),
  ).toBeFocused();
  const file = dialog.locator(".ledger-export-file");
  const noFile = label("desktop.ledger.export.no_file");
  await expect(file).toHaveText(noFile);
  const send = dialog.getByRole("button", {
    name: SEND,
  });
  // The count is the button's own.
  await expect(send).toHaveText(/\(\d+\)/);
  await expect(send).toBeDisabled();

  await button(dialog, "desktop.ledger.export.choose_file").click();
  await expect(file).toHaveText(/\.csv$/);
  await expect(send).toBeEnabled();
  // A new format clears the file.
  await dialog.getByRole("radio", { name: "XLSX" }).click();
  await expect(file).toHaveText(noFile);
  await expect(send).toBeDisabled();
  await button(dialog, "desktop.ledger.export.choose_file").click();
  await expect(file).toHaveText(/\.xlsx$/);
  // So does a new period.
  await dialog
    .getByRole("group", { name: label("desktop.ledger.export.period") })
    .getByRole("button", {
      name: label("desktop.ledger.period.previous"),
      exact: true,
    })
    .click();
  await expect(file).toHaveText(noFile);
  await button(dialog, "desktop.ledger.export.choose_file").click();
  await expect(file).toHaveText(/-3T\.xlsx$/);
  await send.click();
  await expect(
    dialog.getByRole("heading", {
      name: label("desktop.ledger.export.heading_done"),
    }),
  ).toBeFocused();
  await expect(dialog).toContainText(/\.xlsx: \d+\./);
  await noPathShown(target);
  await button(dialog, "desktop.ledger.export.close").first().click();
  await expect(dialog).toBeHidden();

  // The format is remembered as a preference; the file is not.
  await button(head(target), "desktop.ledger.action.export").click();
  await expect(
    exportDialog(target).getByRole("radio", { name: "XLSX" }),
  ).toHaveAttribute("aria-checked", "true");
  await expect(exportDialog(target).locator(".ledger-export-file")).toHaveText(
    noFile,
  );
  const stored = await target.evaluate(() =>
    localStorage.getItem("cadrumo-shell-layout"),
  );
  expect(stored).toContain('"exportFormat":"xlsx"');
  expect(stored).not.toMatch(/-3T|\.xlsx/);
});

test("the export counts readiness with the page's own pills and keeps its button in view", async ({
  page: target,
}) => {
  await target.setViewportSize({ width: 1280, height: 800 });
  await openLedger(target);
  const strip = target.locator(".ledger-movements .ledger-readiness");
  await expect(strip.locator("[data-readiness]").first()).toBeVisible();
  const pills = async (scope: Locator) =>
    scope.evaluate((list) =>
      [...list.querySelectorAll("[data-readiness]")].map(
        (pill) =>
          `${pill.getAttribute("data-readiness")}:${pill.textContent ?? ""}`,
      ),
    );
  const onPage = await pills(strip);
  await button(head(target), "desktop.ledger.action.export").click();
  const dialog = exportDialog(target);
  const shown = dialog.locator(".ledger-export-readiness .ledger-readiness");
  await expect(shown).toBeVisible();
  expect(await pills(shown)).toEqual(onPage);
  // The footer stays in view however long the dialog is.
  await button(dialog, "desktop.ledger.export.choose_file").click();
  const send = dialog.getByRole("button", { name: SEND });
  await expect(send).toBeInViewport();
  // The help sits behind the info glyph, not inline.
  await expect(dialog).not.toContainText(
    label("desktop.ledger.export.file_hint"),
  );
  // A pill there filters the grid to what it counts.
  await shown.locator("[data-readiness] button").first().click();
  await expect(dialog).toBeHidden();
  await expect(
    strip.locator("[data-readiness] button[aria-pressed=true]"),
  ).toHaveCount(1);
});

test("staged changes hold the export until the person reviews them or exports without them", async ({
  page: target,
}) => {
  await target.goto("/primitives.html?harness=ledger-export&staged=3");
  const dialog = exportDialog(target);
  await expect(dialog).toContainText(
    label("desktop.ledger.export.staged", { count: 3 }),
  );
  await button(dialog, "desktop.ledger.export.choose_file").click();
  const send = dialog.getByRole("button", {
    name: SEND,
  });
  await expect(send).toBeDisabled();
  const without = button(dialog, "desktop.ledger.export.without_staged");
  await without.click();
  await expect(without).toHaveAttribute("aria-pressed", "true");
  await expect(send).toBeEnabled();
  // Exporting without them folds the warning to one line.
  await expect(dialog.locator(".ledger-export-staged")).toHaveText(
    new RegExp(`^${label("desktop.ledger.export.staged_short", { count: 3 })}`),
  );
  await button(dialog, "desktop.ledger.export.copy_invoices").click();
  await expect(dialog).toContainText(/Invoices copied: \d+/);
  await button(dialog, "desktop.ledger.export.review_staged").click();
  await expect(dialog).toBeHidden();
  const events = await target.evaluate(() => window.__exportEvents ?? []);
  expect(events.slice(-2)).toEqual(["close", "review"]);
  expect(events[0]).toMatch(/^copy:\d+$/);
});

for (const scheme of ["light", "dark"] as const)
  test(`the import steps and the export have no accessibility violations (${scheme})`, async ({
    page: target,
  }) => {
    await openLedger(target, scheme);
    await expect(target.locator("html")).toHaveAttribute("data-scheme", scheme);
    const dialog = await openImport(target);
    await button(dialog, "desktop.ledger.import.choose_files").click();
    expect(await audit(target)).toEqual([]);
    await button(dialog, "desktop.ledger.import.preview").click();
    await expect(fileRow(dialog, PERSONAL)).toContainText(
      label("desktop.ledger.import.account_detected"),
    );
    expect(await audit(target)).toEqual([]);
    await fileRow(dialog, STUDIO)
      .getByRole("combobox", { name: label("desktop.ledger.import.account") })
      .selectOption({ label: "Cuenta del estudio · ES**1234" });
    await button(dialog, "desktop.ledger.import.apply_files", {
      count: 2,
    }).click();
    await expect(
      dialog.getByRole("region", {
        name: label("desktop.ledger.import.duplicates"),
      }),
    ).toBeVisible();
    expect(await audit(target)).toEqual([]);
    await button(dialog, "desktop.ledger.import.done").click();
    await button(head(target), "desktop.ledger.action.export").click();
    await button(
      exportDialog(target),
      "desktop.ledger.export.choose_file",
    ).click();
    expect(await audit(target)).toEqual([]);
  });

test("Export for another period checks that period and says it with the same strip", async ({
  page: target,
}) => {
  await openLedger(target);
  await button(head(target), "desktop.ledger.action.export").click();
  const dialog = exportDialog(target);
  await expect(dialog.locator(".ledger-export-readiness")).toBeVisible();
  await dialog
    .getByRole("group", { name: label("desktop.ledger.export.period") })
    .getByRole("button", {
      name: label("desktop.ledger.period.previous"),
      exact: true,
    })
    .click();
  const strip = dialog.locator(".ledger-export-readiness .ledger-readiness");
  await expect(strip.locator("[data-readiness]")).not.toHaveCount(0);
  await expect(strip.locator("[data-readiness=unknown]")).toHaveCount(0);
  // The pills count that period; they only say, since the grid shows the
  // page's period.
  await expect(strip.getByRole("button")).toHaveCount(0);
  await expect(dialog).not.toContainText(
    label("desktop.ledger.readiness.not_ready_period"),
  );
});

test("the export's body grows before it scrolls, and its actions never cover the file it saves to", async ({
  page: target,
}) => {
  await target.setViewportSize({ width: 1440, height: 900 });
  await openLedger(target);
  await button(head(target), "desktop.ledger.action.export").click();
  const dialog = exportDialog(target);
  await button(dialog, "desktop.ledger.export.choose_file").click();
  const file = dialog.locator(".ledger-export-file");
  await expect(file).toHaveText(/\.\w+$/);
  const body = (await dialog.locator(".ledger-export-body").boundingBox())!;
  const actions = (await dialog
    .locator("[data-slot=dialog-footer]")
    .boundingBox())!;
  expect(actions.y).toBeGreaterThanOrEqual(body.y + body.height);
  await expect(file).toBeInViewport({ ratio: 1 });
});
