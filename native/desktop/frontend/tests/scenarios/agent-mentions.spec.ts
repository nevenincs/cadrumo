import { expect, test, type Page } from "@playwright/test";
import {
  agentColumn as column,
  messageField as field,
  openConversation,
  personTurns,
  scenarioOnly,
} from "../support/agent";
import { label } from "../support/strings";

// An `@` in the composer names documents the conversation has already
// stored: the list opens above the composer with every stored document whose
// name holds what follows the `@`, the keyboard and the mouse choose one, and
// the one chosen goes with the message by name and digest, never uploaded
// again. The scenario host's "IVA del tercer trimestre" has 244 stored
// documents, which it lists 100 at a time.

const open = (target: Page, query = "") =>
  target.goto(`/scenarios.html?scenario=signed-in&latency=0&bar=off${query}`);

const calls = (target: Page) =>
  target.evaluate(() => window.__scenarioHostCalls ?? []);

const list = (target: Page) =>
  target.getByRole("listbox", { name: label("desktop.agent.mention_label") });

const options = (target: Page) => list(target).getByRole("option");

const suggestions = (target: Page) =>
  target.locator('[data-slot="composer-suggestions"][data-source="documents"]');

/** The files staged for the next message, as the composer's well lists them. */
const staged = (target: Page) =>
  column(target)
    .getByRole("region", { name: label("desktop.agent.attachments") })
    .getByRole("listitem");

test.beforeEach(() => {
  scenarioOnly("the stored documents are the scenario host's");
});

test("an @ lists every stored document above the composer, and the list scrolls", async ({
  page: target,
}) => {
  await open(target);
  await openConversation(target, "IVA del tercer trimestre");
  await field(target).click();
  await field(target).pressSequentially("@");
  await expect(options(target)).toHaveCount(244);
  // The header reads every page for its count; each new @ reads them again.
  expect(
    (await calls(target)).filter((call) => call.startsWith("agentDocuments")),
  ).toEqual([
    "agentDocuments c-iva-t3",
    "agentDocuments c-iva-t3 after factura-2026-099.pdf",
    "agentDocuments c-iva-t3 after factura-2026-199.pdf",
    "agentDocuments c-iva-t3",
    "agentDocuments c-iva-t3 after factura-2026-099.pdf",
    "agentDocuments c-iva-t3 after factura-2026-199.pdf",
  ]);
  await expect(options(target).first()).toContainText("extracto-banco-t3.csv");
  await expect(options(target).last()).toContainText("ticket-gasolinera.jpg");
  // Above the composer, and scrolling rather than growing past the window.
  const listBox = await suggestions(target).boundingBox();
  const fieldBox = await field(target).boundingBox();
  expect(listBox && fieldBox && listBox.y + listBox.height).toBeLessThanOrEqual(
    fieldBox?.y ?? 0,
  );
  const scrolls = await list(target).evaluate(
    (el) => el.scrollHeight > el.clientHeight,
  );
  expect(scrolls).toBe(true);
  await options(target).last().scrollIntoViewIfNeeded();
  await expect(options(target).last()).toBeInViewport();
  // The field kept the focus throughout.
  await expect(field(target)).toBeFocused();
});

test("what follows the @ narrows the list, ignoring case", async ({
  page: target,
}) => {
  await open(target);
  await openConversation(target, "IVA del tercer trimestre");
  await field(target).click();
  await field(target).pressSequentially("Mira @factura-2026-03");
  await expect(options(target)).toHaveCount(10);
  await expect(options(target).first()).toContainText("factura-2026-030.pdf");
  await field(target).fill("Mira @NOTAS");
  await field(target).press("End");
  await expect(options(target)).toHaveCount(1);
  await expect(options(target)).toContainText("notas del trimestre.txt");
  await field(target).pressSequentially("zz");
  await expect(options(target)).toHaveCount(0);
  await expect(suggestions(target)).toContainText(
    label("desktop.agent.mention_empty"),
  );
  // A word typed after a space is no longer the @'s.
  await field(target).fill("correo@ejemplo");
  await expect(list(target)).toHaveCount(0);
});

test("the arrows move the highlight, Enter and Tab choose, and Escape closes", async ({
  page: target,
}) => {
  await open(target);
  await openConversation(target, "IVA del tercer trimestre");
  await field(target).click();
  await field(target).pressSequentially("@factura-2026-00");
  await expect(options(target)).toHaveCount(9);
  await expect(options(target).first()).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await field(target).press("ArrowDown");
  await expect(options(target).nth(1)).toHaveAttribute("aria-selected", "true");
  await field(target).press("ArrowUp");
  await field(target).press("ArrowUp");
  await expect(options(target).last()).toHaveAttribute("aria-selected", "true");
  await field(target).press("ArrowDown");
  await field(target).press("ArrowDown");
  await field(target).press("Enter");
  await expect(field(target)).toHaveValue("@factura-2026-002.pdf ");
  await expect(list(target)).toHaveCount(0);
  await expect(staged(target)).toHaveCount(1);
  await expect(staged(target)).toContainText("factura-2026-002.pdf");
  // Tab chooses as well, and a second document is staged beside the first.
  await field(target).pressSequentially("y @extracto");
  await expect(options(target)).toHaveCount(1);
  await field(target).press("Tab");
  await expect(field(target)).toHaveValue(
    "@factura-2026-002.pdf y @extracto-banco-t3.csv ",
  );
  await expect(staged(target)).toHaveCount(2);
  await expect(field(target)).toBeFocused();
  // Escape closes the list and leaves what was typed.
  await field(target).pressSequentially("@tick");
  await expect(options(target)).toHaveCount(1);
  await field(target).press("Escape");
  await expect(list(target)).toHaveCount(0);
  await expect(field(target)).toHaveValue(
    "@factura-2026-002.pdf y @extracto-banco-t3.csv @tick",
  );
  await expect(staged(target)).toHaveCount(2);
});

test("a press on a document chooses it and keeps the focus in the field", async ({
  page: target,
}) => {
  await open(target);
  await openConversation(target, "IVA del tercer trimestre");
  await field(target).click();
  await field(target).pressSequentially("@libro");
  await options(target).first().click();
  await expect(field(target)).toHaveValue("@libro-registro-iva.xlsx ");
  await expect(field(target)).toBeFocused();
  await expect(staged(target)).toContainText("libro-registro-iva.xlsx");
});

test("a chosen document goes with the message by reference and is shown with it", async ({
  page: target,
}) => {
  await open(target);
  await openConversation(target, "IVA del tercer trimestre");
  await field(target).click();
  await field(target).pressSequentially("Revisa @factura-2026-031");
  await field(target).press("Enter");
  await field(target).pressSequentially("por favor");
  await field(target).press("Enter");
  // The message names the document; nothing is uploaded.
  await expect
    .poll(async () =>
      (await calls(target)).filter((call) => call.startsWith("agentSend ")),
    )
    .toEqual(["agentSend c-iva-t3 alpha/api attachments factura-2026-031.pdf"]);
  expect(
    (await calls(target)).filter((call) => /upload|register/i.test(call)),
  ).toEqual([]);
  const sent = personTurns(target).filter({
    hasText: "Revisa @factura-2026-031.pdf por favor",
  });
  await expect(
    sent.getByRole("list", { name: label("desktop.agent.sent_files") }),
  ).toContainText("factura-2026-031.pdf");
  // What went with the message is no longer staged.
  await expect(staged(target)).toHaveCount(0);
});

test("a removed document does not go with the message", async ({
  page: target,
}) => {
  await open(target);
  await openConversation(target, "IVA del tercer trimestre");
  await field(target).click();
  await field(target).pressSequentially("@notas");
  await field(target).press("Enter");
  await expect(staged(target)).toHaveCount(1);
  await staged(target)
    .getByRole("button", {
      name: label("desktop.agent.remove_file", {
        name: "notas del trimestre.txt",
      }),
    })
    .click();
  await expect(staged(target)).toHaveCount(0);
  await field(target).press("End");
  await field(target).pressSequentially("sin adjunto");
  await field(target).press("Enter");
  await expect
    .poll(async () =>
      (await calls(target)).filter((call) => call.startsWith("agentSend ")),
    )
    .toEqual(["agentSend c-iva-t3 alpha/api"]);
});

test("the documents a message named are shown with it when the conversation is read again", async ({
  page: target,
}) => {
  await open(target);
  await openConversation(target, "¿Puedo deducir los gastos del coche?");
  const files = personTurns(target)
    .first()
    .getByRole("list", { name: label("desktop.agent.sent_files") });
  await expect(files).toContainText("contrato-renting.pdf");
});

test("a conversation not started yet has nothing stored, and says so", async ({
  page: target,
}) => {
  await open(target);
  await field(target).click();
  await field(target).pressSequentially("@");
  await expect(suggestions(target)).toContainText(
    label("desktop.agent.mention_empty"),
  );
  await expect(options(target)).toHaveCount(0);
  expect(
    (await calls(target)).filter((call) => call.startsWith("agentDocuments")),
  ).toEqual([]);
});

test("storage the host does not serve, or cannot read, is said, never shown as empty", async ({
  page: target,
}) => {
  for (const [documents, key] of [
    ["unavailable", "desktop.agent.mention_unavailable"],
    ["failed", "desktop.agent.mention_failed"],
  ] as const) {
    await open(target, `&documents=${documents}`);
    await openConversation(target, "IVA del tercer trimestre");
    await field(target).click();
    await field(target).pressSequentially("@fac");
    await expect(suggestions(target)).toContainText(label(key));
    await expect(suggestions(target)).not.toContainText(
      label("desktop.agent.mention_empty"),
    );
    await expect(options(target)).toHaveCount(0);
  }
});

const addFiles = (target: Page) =>
  column(target).getByRole("button", {
    name: label("desktop.agent.add_files"),
  });

test("attached files are stored in the conversation, then named like any stored document", async ({
  page: target,
}) => {
  await open(target);
  await openConversation(target, "IVA del tercer trimestre");
  await addFiles(target).click();
  // The host picks and streams the files; the page is told only of each.
  await expect
    .poll(async () =>
      (await calls(target)).filter((call) => call.startsWith("agentAttach")),
    )
    .toEqual([`agentAttach c-iva-t3 ${label("desktop.agent.attach_filter")}`]);
  await expect(staged(target)).toHaveCount(3);
  await expect(staged(target).filter({ hasText: "copias.zip" })).toContainText(
    label("desktop.agent.upload_format_refused"),
  );
  await expect(
    staged(target).filter({ hasText: "escaneo-anual.pdf" }),
  ).toContainText(label("desktop.agent.upload_quota_exceeded"));
  // The one stored is named for the next message, and @ now lists it.
  await field(target).click();
  await field(target).pressSequentially("@recibo");
  await expect(options(target)).toHaveCount(1);
  await expect(options(target)).toContainText("recibo-luz.pdf");
  await field(target).press("Enter");
  await expect(
    staged(target).filter({ hasText: "recibo-luz.pdf" }),
  ).toHaveCount(1);
  // Refused files never go; the stored one goes by reference.
  for (const name of ["copias.zip", "escaneo-anual.pdf"])
    await staged(target)
      .getByRole("button", {
        name: label("desktop.agent.remove_file", { name }),
      })
      .click();
  await field(target).pressSequentially("el recibo");
  await field(target).press("Enter");
  await expect
    .poll(async () =>
      (await calls(target)).filter((call) => call.startsWith("agentSend ")),
    )
    .toEqual(["agentSend c-iva-t3 alpha/api attachments recibo-luz.pdf"]);
});

test("attaching to a conversation not started yet reserves it first", async ({
  page: target,
}) => {
  await open(target);
  await addFiles(target).click();
  await expect
    .poll(async () =>
      (await calls(target)).filter(
        (call) =>
          call === "agentStartConversation" || call.startsWith("agentAttach"),
      ),
    )
    .toEqual([
      "agentStartConversation",
      expect.stringMatching(/^agentAttach r-\d+ /) as unknown as string,
    ]);
  await expect(staged(target)).toHaveCount(3);
});

test("a host that stores no documents offers no way to attach them", async ({
  page: target,
}) => {
  await open(target, "&documents=unavailable");
  await expect(addFiles(target)).toHaveAttribute("aria-disabled", "true");
});
