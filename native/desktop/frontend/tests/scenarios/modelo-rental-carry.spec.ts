import { expect, type Locator, type Page, test } from "@playwright/test";
import { RENTAL_ROWS } from "../../src/dev/modeloRentalCarryFixture";
import { label } from "../support/strings";
import { openFromDialog } from "../support/scenarioModelo";
import { applyButton, calls, review } from "../support/scenarioModeloWrites";

// The statement of a family stated row by row, one per let property: the
// window draws what the form serves, one row for each entry, named in the
// entry's own row words, and stages one statement for each binding the
// entry names at the address of that binding and that row. The entries and
// their words are the scenario host's made reads; the window adds none.

const offer = (target: Page) => target.locator("section[data-statements]");
const rowOf = (target: Page, identity: string) =>
  offer(target).locator(`li[data-statement-row="${identity}"]`);
const [FIRST, SECOND] = RENTAL_ROWS;
if (!FIRST || !SECOND) throw new Error("the scenario serves two rows");

type SentIntent = {
  kind: string;
  address: { kind: string; binding_id: string; row_identity?: string | null };
};

/** The intents of the last body the host was sent for `definition`. */
async function sent(target: Page, definition: string): Promise<SentIntent[]> {
  const prefix = `modelo edit body ${definition} `;
  const found = (
    await target.evaluate(() => window.__scenarioHostCalls ?? [])
  ).filter((call) => call.startsWith(prefix));
  const last = found.at(-1);
  if (!last) throw new Error(`no body was sent for ${definition}`);
  return JSON.parse(last.slice(prefix.length)) as SentIntent[];
}

const stageButton = (section: Locator) =>
  section.getByRole("button", {
    name: label("desktop.modelo.statements.stage"),
  });

test("a form serving one statement per property draws one row for each, in the words served", async ({
  page: target,
}) => {
  await openFromDialog(target, "100", "en", "rental-carry");
  await expect(rowOf(target, FIRST.identity)).toContainText(FIRST.words);
  await expect(rowOf(target, SECOND.identity)).toContainText(SECOND.words);
  // The entries of one family are two rows, never one.
  await expect(offer(target).locator("[data-statement-row]")).toHaveCount(2);
  // The form-wide entries come first and carry no row.
  const entries = offer(target).locator("li[data-statement]");
  const count = await entries.count();
  expect(count).toBeGreaterThan(2);
  for (const at of [count - 2, count - 1])
    await expect(entries.nth(at)).toHaveAttribute("data-statement-row", /.+/);
  for (let at = 0; at < count - 2; at += 1)
    await expect(entries.nth(at)).not.toHaveAttribute("data-statement-row");
});

test("ticking one property stages one statement for each binding it names, at that property's row", async ({
  page: target,
}) => {
  await openFromDialog(target, "100", "en", "rental-carry");
  await rowOf(target, FIRST.identity).getByRole("checkbox").check();
  await stageButton(offer(target)).click();
  const dialog = await review(target, FIRST.bindings.length);
  await expect(dialog.locator("[data-statement-line]")).toHaveCount(1);
  await expect(dialog.locator("[data-statement-line]")).toContainText(
    FIRST.words,
  );
  const expected = FIRST.bindings.map((binding) => ({
    kind: "attest_no_amount",
    address: {
      kind: "binding",
      binding_id: binding,
      row_identity: FIRST.identity,
    },
  }));
  expect(await sent(target, "modelo.edit.preflight")).toEqual(expected);
  await applyButton(dialog).click();
  await expect(
    dialog.getByText(label("workspace.modelo.operation.done")),
  ).toBeVisible();
  expect(await sent(target, "modelo.edit.apply")).toEqual(expected);
  expect(await calls(target, "modelo edit modelo.edit.apply")).toHaveLength(1);
});

test("both properties ticked stage each binding once per row, and an unticked one is taken back", async ({
  page: target,
}) => {
  await openFromDialog(target, "100", "en", "rental-carry");
  await rowOf(target, FIRST.identity).getByRole("checkbox").check();
  await rowOf(target, SECOND.identity).getByRole("checkbox").check();
  await stageButton(offer(target)).click();
  const both = FIRST.bindings.length + SECOND.bindings.length;
  const dialog = await review(target, both);
  const pairs = (await sent(target, "modelo.edit.preflight")).map(
    (intent) => `${intent.address.binding_id}@${intent.address.row_identity}`,
  );
  expect(pairs.sort()).toEqual(
    [
      ...FIRST.bindings.map((id) => `${id}@${FIRST.identity}`),
      ...SECOND.bindings.map((id) => `${id}@${SECOND.identity}`),
    ].sort(),
  );
  await dialog
    .getByRole("button", { name: label("workspace.modelo.review.back") })
    .click();
  await rowOf(target, FIRST.identity).getByRole("checkbox").uncheck();
  await stageButton(offer(target)).click();
  await review(target, SECOND.bindings.length);
  expect(
    (await sent(target, "modelo.edit.preflight")).map(
      (intent) => intent.address.row_identity,
    ),
  ).toEqual(SECOND.bindings.map(() => SECOND.identity));
});

test("a form serving no row entry draws its statements as before", async ({
  page: target,
}) => {
  await openFromDialog(target, "100", "en", "renta-pay");
  await expect(
    offer(target).locator("li[data-statement]").first(),
  ).toBeVisible();
  await expect(offer(target).locator("[data-statement-row]")).toHaveCount(0);
});
