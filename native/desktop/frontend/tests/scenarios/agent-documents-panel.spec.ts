import { expect, test, type Page } from "@playwright/test";
import {
  agentColumn,
  messageField,
  openConversation,
  scenarioOnly,
} from "../support/agent";
import { label } from "../support/strings";

const panel = (page: Page) =>
  agentColumn(page).getByRole("region", {
    name: label("desktop.agent.documents"),
    exact: true,
  });
const rows = (page: Page) => panel(page).getByRole("listitem");
const staged = (page: Page) =>
  agentColumn(page)
    .getByRole("region", { name: label("desktop.agent.attachments") })
    .getByRole("listitem");
const toggle = (page: Page) =>
  agentColumn(page).getByRole("button", {
    name: new RegExp(`^${label("desktop.agent.documents")}(,|$)`),
  });
const calls = (page: Page) =>
  page.evaluate(() => window.__scenarioHostCalls ?? []);
const NAME = "extracto-banco-t3.csv";

async function open(page: Page, query = "", existing = true) {
  await page.goto(
    `/scenarios.html?scenario=signed-in&latency=0&bar=off${query}`,
  );
  if (existing) await openConversation(page, "IVA del tercer trimestre");
  await toggle(page).click();
}
async function use(page: Page, name: string) {
  await panel(page)
    .getByRole("button", {
      name: label("desktop.agent.use_document", { name }),
    })
    .click();
}
test.beforeEach(() => scenarioOnly("Documents are held by the scenario host."));

test("the document panel lists every page, counts files, and assigns no tax role", async ({
  page,
}) => {
  await open(page);
  await expect(rows(page)).toHaveCount(244);
  await expect(toggle(page)).toHaveAccessibleName(/244/);
  await expect(rows(page).first()).toContainText(NAME);
  await expect(rows(page).last()).toContainText("ticket-gasolinera.jpg");
  await expect(panel(page).getByRole("combobox")).toHaveCount(0);
  await panel(page)
    .getByRole("button", { name: label("desktop.agent.close_documents") })
    .click();
  await expect(panel(page)).toHaveCount(0);
  await expect(messageField(page)).toBeVisible();
  await agentColumn(page)
    .getByRole("button", { name: label("desktop.agent.history"), exact: true })
    .click();
  await expect(
    agentColumn(page)
      .getByRole("button", { name: /IVA del tercer trimestre/ })
      .first(),
  ).toContainText(label("desktop.agent.row_documents", { count: 244 }));
});

test("staging a document and removing its reference leaves the stored file intact", async ({
  page,
}) => {
  await open(page);
  await use(page, NAME);
  await expect(staged(page)).toHaveCount(1);
  await expect(rows(page).first()).toContainText(
    label("desktop.agent.document_selected"),
  );
  await staged(page)
    .getByRole("button", {
      name: label("desktop.agent.remove_file", { name: NAME }),
    })
    .click();
  await expect(staged(page)).toHaveCount(0);
  await expect(rows(page)).toHaveCount(244);
  expect(
    (await calls(page)).filter((call) =>
      call.startsWith("agentRemoveDocuments"),
    ),
  ).toEqual([]);
});

test("deleting one stored file asks first and removes its staged reference and count", async ({
  page,
}) => {
  await open(page);
  await use(page, NAME);
  const remove = panel(page).getByRole("button", {
    name: label("desktop.agent.remove_document", { name: NAME }),
    exact: true,
  });
  await remove.click();
  const dialog = page.getByRole("dialog", {
    name: label("desktop.agent.delete"),
    exact: true,
  });
  await expect(dialog).toContainText(NAME);
  await dialog
    .getByRole("button", { name: label("desktop.agent.cancel"), exact: true })
    .click();
  await expect(remove).toBeFocused();
  expect(
    (await calls(page)).filter((call) =>
      call.startsWith("agentRemoveDocuments"),
    ),
  ).toEqual([]);
  await remove.click();
  await dialog
    .getByRole("button", { name: label("desktop.agent.delete"), exact: true })
    .click();
  await expect(rows(page)).toHaveCount(243);
  await expect(panel(page)).toBeFocused();
  await expect(staged(page)).toHaveCount(0);
  await expect(toggle(page)).toHaveAccessibleName(/243/);
  expect(
    (await calls(page)).filter((call) =>
      call.startsWith("agentRemoveDocuments"),
    ),
  ).toEqual([`agentRemoveDocuments c-iva-t3 ${NAME}`]);
});

test("Remove all deletes the conversation's stored files only after confirmation", async ({
  page,
}) => {
  await open(page);
  await expect(rows(page)).toHaveCount(244);
  await panel(page)
    .getByRole("button", {
      name: label("desktop.agent.remove_all"),
      exact: true,
    })
    .click();
  const dialog = page.getByRole("dialog", {
    name: label("desktop.agent.delete"),
    exact: true,
  });
  await expect(dialog).toContainText("244");
  await dialog
    .getByRole("button", { name: label("desktop.agent.delete"), exact: true })
    .click();
  await expect(panel(page)).toContainText(
    label("desktop.agent.documents_empty"),
  );
  await expect(rows(page)).toHaveCount(0);
  expect(
    (await calls(page)).filter((call) =>
      call.startsWith("agentRemoveDocuments"),
    ),
  ).toEqual(["agentRemoveDocuments c-iva-t3 all"]);
});

test("the full staged-file list exposes hidden files and Remove all only unstages them", async ({
  page,
}) => {
  await open(page);
  await expect(rows(page)).toHaveCount(244);
  for (let at = 0; at < 10; at++)
    await rows(page).nth(at).getByRole("button", { name: /^Use / }).click();
  const overflow = agentColumn(page).getByRole("button", { name: /more/ });
  await overflow.click();
  const dialog = page.getByRole("dialog", {
    name: label("desktop.agent.attachments"),
    exact: true,
  });
  await expect(dialog.getByRole("listitem")).toHaveCount(10);
  await page.keyboard.press("Escape");
  await expect(overflow).toBeFocused();
  await overflow.click();
  await dialog
    .getByRole("button", {
      name: label("desktop.agent.remove_file", { name: NAME }),
      exact: true,
    })
    .click();
  await expect(dialog.getByRole("listitem")).toHaveCount(9);
  await dialog
    .getByRole("button", {
      name: label("desktop.agent.remove_all"),
      exact: true,
    })
    .click();
  await expect(dialog.getByRole("listitem")).toHaveCount(0);
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(messageField(page)).toBeFocused();
  await expect(rows(page)).toHaveCount(244);
  expect(
    (await calls(page)).filter((call) =>
      call.startsWith("agentRemoveDocuments"),
    ),
  ).toEqual([]);
});

test("the document picker enforces the message reference limit and frees a slot when unstaged", async ({
  page,
}) => {
  await open(page);
  await expect(rows(page)).toHaveCount(244);
  // The scenario upload holds the first 31 files already in this conversation.
  // One Add files action delivers the same stored events as ordinary uploads.
  await page.evaluate(async () => {
    const session = window.__fixtureAgentSession;
    const views = window.__fixtureAgentViews;
    if (!session || !views?.documents) throw new Error("Missing fixture agent");
    const held = (
      await views.documents({ conversation_id: "c-iva-t3" })
    ).documents.slice(0, 31);
    if (held.length !== 31) throw new Error("Missing fixture documents");
    session.attach = async (conversationId, _filterLabel, onEvent) => {
      if (conversationId !== "c-iva-t3") throw new Error("Wrong conversation");
      const picks = held.map((document, at) => ({
        id: `limit-setup-${at}`,
        name: document.name,
        size_bytes: document.size_bytes,
        state: "queued" as const,
        code: null,
      }));
      picks.forEach((pick, at) =>
        onEvent({ kind: "stored", id: pick.id, document: held[at]! }),
      );
      return picks;
    };
  });
  // Refresh the rendered attach handler after installing the fixture answer.
  await toggle(page).click();
  await toggle(page).click();
  await panel(page)
    .getByRole("button", {
      name: label("desktop.agent.add_files"),
      exact: true,
    })
    .click();
  await expect(rows(page).nth(30)).toContainText(
    label("desktop.agent.document_selected"),
  );
  const last = rows(page).nth(31).getByRole("button", { name: /^Use / });
  await last.click();
  await expect(rows(page).nth(31)).toContainText(
    label("desktop.agent.document_selected"),
  );
  const next = rows(page).nth(32).getByRole("button", { name: /^Use / });
  await expect(next).toHaveAttribute("aria-disabled", "true");
  await staged(page)
    .getByRole("button", {
      name: label("desktop.agent.remove_file", { name: NAME }),
      exact: true,
    })
    .click();
  await expect(next).not.toHaveAttribute("aria-disabled", "true");
  await next.click();
  await expect(rows(page).nth(32)).toContainText(
    label("desktop.agent.document_selected"),
  );
});

test("Add files works from the empty document panel and refreshes its stored listing", async ({
  page,
}) => {
  await open(page, "", false);
  await expect(panel(page)).toContainText(
    label("desktop.agent.documents_empty"),
  );
  await panel(page)
    .getByRole("button", {
      name: label("desktop.agent.add_files"),
      exact: true,
    })
    .click();
  await expect(rows(page)).toHaveCount(1);
  await expect(rows(page).first()).toContainText("recibo-luz.pdf");
  await expect(staged(page)).toHaveCount(3);
  await expect(toggle(page)).toHaveAccessibleName(/1/);
});

test("a listing failure stays a failure and can be retried", async ({
  page,
}) => {
  await open(page, "&documents=failed");
  await expect(agentColumn(page).getByRole("alert")).toContainText(
    label("desktop.agent.mention_failed"),
  );
  await expect(
    page.getByText(label("desktop.agent.documents_empty"), { exact: true }),
  ).toHaveCount(0);
  const before = (await calls(page)).filter((call) =>
    call.startsWith("agentDocuments"),
  ).length;
  await agentColumn(page)
    .getByRole("button", {
      name: label("desktop.providers.refresh"),
      exact: true,
    })
    .click();
  await expect
    .poll(
      async () =>
        (await calls(page)).filter((call) => call.startsWith("agentDocuments"))
          .length,
    )
    .toBeGreaterThan(before);
});

test("a refused deletion keeps the file, reports failure, and never retries the mutation", async ({
  page,
}) => {
  await open(page);
  await expect(rows(page)).toHaveCount(244);
  await page.evaluate(() => {
    const session = window.__fixtureAgentSession;
    if (!session) throw new Error("Missing session");
    session.removeDocuments = async () => {
      (window.__scenarioHostCalls ??= []).push("refusedDocumentRemoval");
      throw { code: "agent_gateway_unreachable" };
    };
  });
  await panel(page)
    .getByRole("button", {
      name: label("desktop.agent.remove_document", { name: NAME }),
      exact: true,
    })
    .click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: label("desktop.agent.delete"), exact: true })
    .click();
  await expect(agentColumn(page).getByRole("alert")).toContainText(
    label("desktop.agent.document_remove_failed"),
  );
  await expect(rows(page)).toHaveCount(244);
  expect(
    (await calls(page)).filter((call) => call === "refusedDocumentRemoval"),
  ).toHaveLength(1);
});
