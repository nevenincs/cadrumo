import { expect, test, type Page } from "@playwright/test";
import { readdirSync, readFileSync } from "node:fs";
import type {
  CreditResolutionListProjection,
  CreditResolutionMutationProjection,
} from "../../src/shell/modeloContract/modeloWork";
import type { ModeloWorkbenchFormProjectionV1 } from "../../src/shell/modeloContract/modeloWorkForm";
import { label } from "../support/strings";
import { MODELO_FIXTURES } from "../support/windowFixtures";

// The answer to a source disagreement, in one declaration's Check view over
// the scenario's modelo family, which answers the envelopes the application
// read for a synthetic filer: the first-quarter Modelo 130 after a value
// typed over box 06 replaced a different ledger figure. Which line offers to
// accept or to revoke, what an acceptance covers and why an answer was
// refused are read from those envelopes; the window words only its controls.

const LANGUAGES = ["en", "es", "ca", "hu"] as const;
type Language = (typeof LANGUAGES)[number];
const REASON = "The ledger misses an invoice booked late.";

const stored = <T>(name: string): T =>
  JSON.parse(
    readFileSync(new URL(`${name}.json`, MODELO_FIXTURES), "utf8"),
  ) as T;

/** A command line, flag or markup an action would show had it not been
 * worded for the person. */
const UNWORDED = /aeat |--|</;

const workspace = (target: Page) => target.locator(".declarations-workspace");
const tab = (target: Page, key: string, language: Language) =>
  workspace(target).getByRole("tab", {
    name: new RegExp(`^${label(key, {}, language)}`),
  });

/** The check line stating the disagreement, as the stored form words it. */
const disagreementLine = (form: string, language: Language) => {
  const read = stored<ModeloWorkbenchFormProjectionV1>(
    `modelo-${form}-${language}`,
  );
  const line = read.issue_lines.find((each) => each.finding_id !== null);
  if (!line) throw new Error(`the stored ${form} states no disagreement`);
  return line;
};

/** Opens the first-quarter Modelo 130 in `shape` on its Check view. */
async function openCheck(target: Page, shape: string, language: Language) {
  await target.goto(
    `/scenarios.html?scenario=ledger&latency=0&bar=off&modelo=${shape}&lang=${language}`,
  );
  await target.locator("[data-rail=declarations]").click();
  await target
    .locator(".declarations-page")
    .getByRole("grid")
    .locator("[data-kind=data]")
    .filter({ hasText: "Modelo 130" })
    .first()
    .dblclick();
  await expect(
    workspace(target).getByRole("heading", { level: 1 }),
  ).toBeVisible();
  await tab(target, "workspace.modelo.step.review", language).click();
}

const offered = (
  target: Page,
  answer: "accept" | "revoke",
  language: Language,
) =>
  workspace(target).getByRole("button", {
    name: label(`desktop.modelo.disagreement.${answer}`, {}, language),
  });

/** Opens the acceptance, gives the reason and sends it. */
async function accept(target: Page, language: Language) {
  await offered(target, "accept", language).click();
  const dialog = target.getByRole("dialog");
  const confirm = dialog.getByRole("button", {
    name: label("desktop.modelo.disagreement.confirm_accept", {}, language),
  });
  // Nothing is sent without a reason.
  await expect(confirm).toBeDisabled();
  await dialog
    .getByRole("textbox", {
      name: label("desktop.modelo.disagreement.reason_label", {}, language),
    })
    .fill(REASON);
  await confirm.click();
  return dialog;
}

for (const language of LANGUAGES)
  test(`a disagreement is accepted with a reason and revoked, in ${language}`, async ({
    page: target,
  }) => {
    await openCheck(target, "disagreement", language);
    const open = disagreementLine("130-1T-applied", language);
    const blocks = workspace(target).getByRole("region", {
      name: label("workspace.modelo.level.blocks", {}, language),
    });
    await expect(blocks).toContainText(open.message);
    await expect(offered(target, "revoke", language)).toHaveCount(0);
    // Every action the check shows is worded for the person.
    for (const action of await blocks.locator("li").allInnerTexts())
      expect(action).not.toMatch(UNWORDED);

    await offered(target, "accept", language).click();
    // The dialog leads with what the acceptance records, as served.
    await expect(target.getByRole("dialog")).toContainText(
      open.answer_lead_words!,
    );
    expect(open.answer_lead_words_language).toBe(language);
    await target
      .getByRole("dialog")
      .getByRole("button", {
        name: label("workspace.modelo.editor.cancel", {}, language),
      })
      .click();
    const dialog = await accept(target, language);
    await expect(dialog).toBeHidden();
    // Read again, the line offers to revoke, and the answer is listed in the
    // application's words beside the reason given.
    await expect(offered(target, "revoke", language)).toBeVisible();
    const listed = stored<CreditResolutionListProjection>(
      `disagreements-130-1T-accepted-${language}`,
    ).resolutions[0]!;
    const answers = workspace(target).getByRole("region", {
      name: label("desktop.modelo.disagreement.list_title", {}, language),
    });
    await expect(answers).toContainText(listed.answer_words);
    await expect(answers).toContainText(listed.state_words);
    await expect(answers).toContainText(listed.current_words);
    await expect(answers.locator("[data-answer-state=active]")).toHaveCount(1);

    await offered(target, "revoke", language).click();
    const revoking = target.getByRole("dialog");
    await expect(revoking).toContainText(listed.answer_words);
    await expect(revoking).toContainText(
      disagreementLine("130-1T-accepted", language).answer_lead_words!,
    );
    await revoking
      .getByRole("button", {
        name: label("desktop.modelo.disagreement.confirm_revoke", {}, language),
      })
      .click();
    await expect(revoking).toBeHidden();
    await expect(offered(target, "accept", language)).toBeVisible();
    const revoked = stored<CreditResolutionListProjection>(
      `disagreements-130-1T-revoked-${language}`,
    ).resolutions.find((row) => row.state === "revoked")!;
    const shown = answers.locator("[data-answer-state=revoked]");
    await expect(shown).toHaveCount(1);
    await expect(shown).toContainText(revoked.state_words);
    // A revoked answer cannot be taken back again; the application says why.
    expect(revoked.revocable).toBe(false);
    await expect(shown).toContainText(revoked.revoke_refusal_words!);
  });

for (const language of LANGUAGES)
  test(`an acceptance refused as already made says the application's words, in ${language}`, async ({
    page: target,
  }) => {
    await openCheck(target, "disagreement-raced", language);
    const dialog = await accept(target, language);
    const refused = stored<CreditResolutionMutationProjection>(
      `accept-130-1T-accepted-refused-${language}`,
    ).refusal!;
    expect(refused.refusal_words_language).toBe(language);
    await expect(dialog.getByRole("alert").first()).toContainText(
      refused.refusal_words!,
    );
    await dialog
      .getByRole("button", {
        name: label("workspace.modelo.editor.cancel", {}, language),
      })
      .click();
    // Read again, the declaration shows the acceptance made elsewhere.
    await expect(offered(target, "revoke", language)).toBeVisible();
  });

test("an acceptance whose settlement was not seen is unknown and sent no more", async ({
  page: target,
}) => {
  await openCheck(target, "disagreement-unknown", "en");
  const dialog = await accept(target, "en");
  await expect(
    dialog.getByRole("button", {
      name: label("desktop.modelo.disagreement.confirm_accept"),
    }),
  ).toBeDisabled();
  // Nothing is offered to answer while what it did is unknown.
  await dialog
    .getByRole("button", { name: label("workspace.modelo.editor.cancel") })
    .click();
  await expect(offered(target, "accept", "en")).toHaveCount(0);
});

test("a declaration whose check states no disagreement offers no answer", async ({
  page: target,
}) => {
  await openCheck(target, "checked", "en");
  await expect(offered(target, "accept", "en")).toHaveCount(0);
  await expect(offered(target, "revoke", "en")).toHaveCount(0);
  await expect(
    workspace(target).getByRole("region", {
      name: label("desktop.modelo.disagreement.list_title"),
    }),
  ).toHaveCount(0);
});

test("no stored check line words its action as a command", () => {
  const forms = readdirSync(MODELO_FIXTURES).filter((name) =>
    /^modelo-.*\.json$/.test(name),
  );
  expect(forms.length).toBeGreaterThan(0);
  for (const name of forms) {
    const form = JSON.parse(
      readFileSync(new URL(name, MODELO_FIXTURES), "utf8"),
    ) as Partial<ModeloWorkbenchFormProjectionV1>;
    for (const line of form.issue_lines ?? []) {
      expect(line.action, name).not.toMatch(UNWORDED);
      // A lead is served exactly where an answer is offered.
      expect(line.answer_lead_words === null, name).toBe(
        line.resolution_answer === null,
      );
    }
  }
});
