import { expect, test, type Page } from "@playwright/test";
import { label } from "../support/strings";

// The Documents section on a computer whose local AI is not set up: a scan
// whose read is refused for it, a reading that stood on its labels alone,
// and readers that are not ready each lead to the window's one setup prompt
// on the local AI, which says its state once and leads into setting it up.
// Where setup cannot change what is missing, or the window offers no setup,
// nothing is offered. Every value is synthetic.

const PLENOIL = "ticket-plenoil-1015.jpg";
const ARROYO = "factura-arroyo-2026-10.pdf";
/** The fixture's local AI row, as the host names and words it. */
const LOCAL_AI = "Local AI";
const NOT_SET_UP = "Not set up yet.";

const section = (target: Page) => target.locator(".ledger-documents");
const draft = (target: Page) => section(target).locator(".ledger-draft");
const tab = (target: Page, name: string) =>
  section(target).getByRole("tab", {
    name: new RegExp(`^${label(`desktop.ledger.documents.tab.${name}`)}`),
  });
const setupDialog = (target: Page) =>
  target.getByRole("dialog", { name: label("desktop.setup.title") });
const prompt = (target: Page) => target.getByRole("dialog", { name: LOCAL_AI });

async function openDocuments(
  target: Page,
  setup: string | null,
  ledger = "reader_missing",
) {
  await target.goto(
    `/scenarios.html?scenario=ledger&latency=0&bar=off&ledger=${ledger}${
      setup ? `&setup=${setup}` : ""
    }`,
  );
  // Setup unfinished opens its dialog once per launch; it is put away here.
  if (setup === "fresh" || setup === "hardware") {
    await setupDialog(target)
      .getByRole("button", { name: label("desktop.setup.not_now") })
      .click();
    await expect(setupDialog(target)).toBeHidden();
  }
  await target.locator("[data-rail=ledger]").click();
  await expect(target.locator(".ledger-movements")).toBeVisible();
  await target
    .getByRole("tab", { name: label("desktop.ledger.section.documents") })
    .click();
  await expect(section(target)).toBeVisible();
}

async function choose(target: Page, name: string) {
  await section(target)
    .locator(".ledger-review-item")
    .filter({ hasText: name })
    .click();
  await expect(draft(target).getByRole("heading", { name })).toBeVisible();
}

/** The prompt names the local AI, says its state once and nothing else of
 * the refusal behind it. */
async function promptSaysOnce(target: Page) {
  const shown = prompt(target);
  await expect(shown).toBeVisible();
  await expect(shown).toContainText(NOT_SET_UP);
  expect((await shown.innerText()).split(NOT_SET_UP).length - 1).toBe(1);
  const body = target.locator("body");
  await expect(body).not.toContainText("operator.");
  await expect(body).not.toContainText("provisioning.");
  await expect(body).not.toContainText("local_ai");
}

test("the Readers tab offers the local AI's setup and its prompt leads into it", async ({
  page: target,
}) => {
  await openDocuments(target, "fresh");
  await tab(target, "readers").click();
  const readers = section(target).locator(".ledger-readers");
  await expect(readers.locator(".ledger-reader-role")).toHaveCount(2);
  await expect(readers.locator(".ledger-reader-role").first()).toContainText(
    label("desktop.ledger.documents.reader.not_ready"),
  );
  const offer = readers.locator(".ledger-readers-set-up");
  await expect(offer).toContainText(LOCAL_AI);
  // The tab does not say the setup's state; the prompt does, once.
  await expect(readers).not.toContainText(NOT_SET_UP);
  await offer.getByRole("button", { name: "Set up", exact: true }).click();
  await promptSaysOnce(target);
  await prompt(target)
    .getByRole("button", { name: "Set up", exact: true })
    .click();
  await expect(prompt(target)).toBeHidden();
  await expect(setupDialog(target)).toBeVisible();
});

test("a scan refused for the missing local AI opens its prompt once", async ({
  page: target,
}) => {
  await openDocuments(target, "fresh");
  await choose(target, PLENOIL);
  await draft(target)
    .getByRole("button", { name: label("desktop.ledger.documents.read_again") })
    .click();
  await promptSaysOnce(target);
  await prompt(target)
    .getByRole("button", { name: label("desktop.setup.not_now") })
    .click();
  await expect(prompt(target)).toBeHidden();
  // The refusal stays on the page, and offers the same prompt again.
  const refused = draft(target)
    .getByRole("alert")
    .filter({
      hasText: label("desktop.ledger.documents.not_done"),
    });
  await expect(refused).toBeVisible();
  await expect(refused).toContainText(LOCAL_AI);
  await expect(target.getByRole("dialog")).toHaveCount(0);
  await refused.getByRole("button", { name: "Set up", exact: true }).click();
  await promptSaysOnce(target);
});

test("a reading that stood on its labels names the local AI and opens its prompt", async ({
  page: target,
}) => {
  await openDocuments(target, "fresh");
  await choose(target, ARROYO);
  const unread = draft(target).locator(".ledger-draft-unread");
  await expect(unread).toContainText(label("desktop.ledger.documents.unread"));
  await expect(unread).toContainText(
    label("desktop.ledger.documents.field.retencion_rate"),
  );
  await expect(unread).toContainText(LOCAL_AI);
  // A reading that stood is no refusal: nothing opens by itself.
  await expect(target.getByRole("dialog")).toHaveCount(0);
  await unread.getByRole("button", { name: "Set up", exact: true }).click();
  await promptSaysOnce(target);
});

test("where setup cannot change what is missing, nothing is offered", async ({
  page: target,
}) => {
  // This computer is below what the local AI needs: setup cannot help.
  await openDocuments(target, "hardware");
  await choose(target, ARROYO);
  const unread = draft(target).locator(".ledger-draft-unread");
  await expect(unread).toBeVisible();
  await expect(unread.locator(".setup-offer")).toHaveCount(0);
  await tab(target, "readers").click();
  await expect(section(target).locator(".ledger-reader-role")).toHaveCount(2);
  await expect(section(target).locator(".setup-offer")).toHaveCount(0);
});

test("a scan refused for a local AI this computer cannot set up says why and offers no setup", async ({
  page: target,
}) => {
  // The refusal still names the local AI's setup, but its row is blocked:
  // the prompt says the row's own sentence and offers only to close.
  await openDocuments(target, "hardware");
  await choose(target, PLENOIL);
  await draft(target)
    .getByRole("button", { name: label("desktop.ledger.documents.read_again") })
    .click();
  const shown = prompt(target);
  await expect(shown).toBeVisible();
  await expect(shown).toContainText(
    "This computer does not have enough memory for this.",
  );
  await expect(shown.getByRole("button")).toHaveText([
    label("desktop.setup.close"),
  ]);
  await shown
    .getByRole("button", { name: label("desktop.setup.close"), exact: true })
    .click();
  await expect(shown).toBeHidden();
  // Beside the refusal, nothing offers the setup either.
  await expect(draft(target).locator(".setup-offer")).toHaveCount(0);
});

/** Adds the folder's documents as received ones; its scan pauses for the
 * missing local AI. */
async function addFolder(target: Page) {
  await tab(target, "folder").click();
  const folder = section(target).locator(".ledger-folder");
  await folder.locator(".ledger-folder-pick").click();
  await folder
    .getByRole("radio", {
      name: label("desktop.ledger.invoices.kind_choice.received"),
    })
    .click();
  await folder.locator(".ledger-folder-add").click();
  await expect(folder.locator("[data-status=paused]")).toHaveCount(1);
  return folder;
}

test("a folder whose scan paused for the local AI names it and opens its prompt once", async ({
  page: target,
}) => {
  await openDocuments(target, "fresh");
  const folder = await addFolder(target);
  // The batch settled; its pause still leads to the local AI's prompt.
  await promptSaysOnce(target);
  await prompt(target)
    .getByRole("button", { name: label("desktop.setup.not_now") })
    .click();
  await expect(prompt(target)).toBeHidden();
  const paused = folder.locator(".ledger-batch-paused");
  await expect(paused).toContainText(
    label("desktop.ledger.documents.paused_local_ai"),
  );
  await expect(paused).toContainText(LOCAL_AI);
  await expect(target.getByRole("dialog")).toHaveCount(0);
  await paused.getByRole("button", { name: "Set up", exact: true }).click();
  await promptSaysOnce(target);
});

test("a folder paused for a local AI this computer cannot set up says why and offers no setup", async ({
  page: target,
}) => {
  await openDocuments(target, "hardware");
  const folder = await addFolder(target);
  const shown = prompt(target);
  await expect(shown).toContainText(
    "This computer does not have enough memory for this.",
  );
  await expect(shown.getByRole("button")).toHaveText([
    label("desktop.setup.close"),
  ]);
  await shown
    .getByRole("button", { name: label("desktop.setup.close"), exact: true })
    .click();
  const paused = folder.locator(".ledger-batch-paused");
  await expect(paused).toContainText(
    label("desktop.ledger.documents.paused_local_ai"),
  );
  await expect(paused.locator(".setup-offer")).toHaveCount(0);
});

/** Opens the Ledger's import on the bank statements, with the window's
 * setup dialog put away, and previews every statement it offers. */
async function previewStatements(target: Page, setup: string) {
  await target.goto(
    `/scenarios.html?scenario=ledger&latency=0&bar=off&ledger=reader_missing&setup=${setup}`,
  );
  // A status that cannot be read opens no setup dialog to put away.
  if (setup !== "unavailable") {
    await setupDialog(target)
      .getByRole("button", { name: label("desktop.setup.not_now") })
      .click();
    await expect(setupDialog(target)).toBeHidden();
  }
  await target.locator("[data-rail=ledger]").click();
  await expect(target.locator(".ledger-movements")).toBeVisible();
  await target
    .locator(".pane-docs .pane-head")
    .getByRole("button", {
      name: label("desktop.ledger.action.import"),
      exact: true,
    })
    .click();
  const dialog = target.getByRole("dialog", {
    name: label("desktop.ledger.import.title"),
  });
  await dialog
    .getByRole("button", {
      name: label("desktop.ledger.import.choose_files"),
      exact: true,
    })
    .click();
  await dialog
    .getByRole("button", {
      name: label("desktop.ledger.import.preview"),
      exact: true,
    })
    .click();
  return dialog
    .getByRole("listitem")
    .filter({ hasText: "movimientos-tarjeta.pdf" });
}

test("a PDF statement only the local AI reads names it and offers its setup", async ({
  page: target,
}) => {
  const card = await previewStatements(target, "fresh");
  await expect(card).toContainText(
    label("desktop.ledger.import.refusal.reader_unavailable"),
  );
  await expect(card).toContainText(LOCAL_AI);
  // A preview is no refusal of the import: nothing opens by itself.
  await expect(prompt(target)).toHaveCount(0);
  await card.getByRole("button", { name: "Set up", exact: true }).click();
  await promptSaysOnce(target);
});

test("a PDF statement for a local AI this computer cannot set up says why and offers no setup", async ({
  page: target,
}) => {
  const card = await previewStatements(target, "hardware");
  await expect(card).toContainText(
    label("desktop.ledger.import.refusal.reader_unavailable"),
  );
  // The import settles, so no prompt opens: the card itself says why.
  await expect(card.locator(".setup-held")).toHaveText(
    `${LOCAL_AI}: This computer does not have enough memory for this.`,
  );
  await expect(card.locator(".setup-offer")).toHaveCount(0);
  await expect(card.getByRole("button")).toHaveCount(0);
  await expect(prompt(target)).toHaveCount(0);
});

test("a PDF statement while the setup status cannot be read offers nothing", async ({
  page: target,
}) => {
  const card = await previewStatements(target, "unavailable");
  await expect(card).toContainText(
    label("desktop.ledger.import.refusal.reader_unavailable"),
  );
  await expect(card.locator(".setup-offer")).toHaveCount(0);
  await expect(card.locator(".setup-held")).toHaveCount(0);
  await expect(card.getByRole("button")).toHaveCount(0);
  await expect(prompt(target)).toHaveCount(0);
  await expect(setupDialog(target)).toHaveCount(0);
});

test("a reader held back by memory offers no setup, though the local AI is not set up", async ({
  page: target,
}) => {
  // The vision role is not ready because this computer lacks the memory to
  // load it now; its row names no setup, so none is offered even while the
  // local AI's setup is unfinished.
  await openDocuments(target, "fresh", "documents");
  await tab(target, "readers").click();
  const readers = section(target).locator(".ledger-readers");
  await expect(readers.locator(".ledger-reader-role")).toHaveCount(2);
  await expect(readers.locator(".ledger-reader-role").nth(1)).toContainText(
    label("desktop.ledger.documents.reader.not_ready"),
  );
  await expect(readers.locator(".setup-offer")).toHaveCount(0);
});

test("a window that offers no setup offers nothing and opens nothing", async ({
  page: target,
}) => {
  await openDocuments(target, null);
  await choose(target, PLENOIL);
  await draft(target)
    .getByRole("button", { name: label("desktop.ledger.documents.read_again") })
    .click();
  await expect(
    draft(target)
      .getByRole("alert")
      .filter({
        hasText: label("desktop.ledger.documents.not_done"),
      }),
  ).toBeVisible();
  await expect(target.getByRole("dialog")).toHaveCount(0);
  await expect(section(target).locator(".setup-offer")).toHaveCount(0);
});
