import { expect, test } from "@playwright/test";
import { label } from "../support/strings";
import { type JsonObject } from "../../src/shell/ledger";
import {
  button,
  field,
  openLedger,
  openSetup,
  area,
} from "../support/ledgerSetup";

// The Ledger page's Setup sections over the scenario host's made-up ledger: counterparty lookups, drafts, conflicts and updates, and the identity each reply belongs to.

declare global {
  interface Window {
    __counterpartyReply?: (at: number) => void;
    __counterpartyRequests?: JsonObject[];
    __counterpartyPending?: number;
  }
}

test("counterparty replies and drafts belong to the exact lookup identity", async ({
  page: target,
}) => {
  await openLedger(target);
  await target.evaluate(() => {
    const port = window.__fixtureLedger!;
    const submit = port.submit;
    const pending: (() => void)[] = [];
    window.__counterpartyPending = 0;
    window.__counterpartyRequests = [];
    window.__counterpartyReply = (at) => pending[at]!();
    port.submit = async (definition, payload) => {
      const answer = await submit(definition, payload);
      if (definition === "ledger.counterparty") {
        const request = payload as JsonObject;
        window.__counterpartyRequests!.push(request);
        if (request.action === "view")
          await new Promise<void>((resolve) => {
            pending.push(resolve);
            window.__counterpartyPending = pending.length;
          });
      }
      return answer;
    };
  });
  await openSetup(target, "rules");
  await area(target, "desktop.ledger.rules.area.counterparties");
  const tax = field(target, "desktop.ledger.counterparty.tax_id");
  const country = field(target, "desktop.ledger.counterparty.country");
  const answer = target.locator(".ledger-counterparty-answer");
  const lookup = async (id: string, hint: string, count: number) => {
    await tax.fill(id);
    await country.focus();
    await country.fill(hint);
    await expect(country).toHaveValue(hint);
    await target.locator(".ledger-counterparty-view").click();
    await expect
      .poll(() => target.evaluate(() => window.__counterpartyPending))
      .toBe(count);
  };
  const reply = (at: number) =>
    target.evaluate((at) => window.__counterpartyReply!(at), at);
  await lookup("LU20260001", "LU", 1);
  await lookup("B12345678", "ES", 2);
  await reply(1);
  await expect(answer).toContainText("B12345678");
  await reply(0);
  await expect(answer).not.toContainText("LU20260001");
  const note = field(answer, "desktop.ledger.counterparty.note");
  await note.fill("This draft belongs to B in ES");
  await country.focus();
  await country.fill("FR");
  await expect(answer).toHaveCount(0);
  await lookup("B12345678", "FR", 3);
  await reply(2);
  await expect(note).toHaveValue("");
  await lookup("B12345678", "ES", 4);
  await reply(3);
  await expect(note).toHaveValue("This draft belongs to B in ES");
  await field(answer, "desktop.ledger.counterparty.scope_label").selectOption(
    "es_mainland",
  );
  await field(answer, "desktop.ledger.counterparty.asserted_by").fill(
    "Fixture operator",
  );
  await target.locator(".ledger-counterparty-confirm").click();
  await expect
    .poll(() => target.evaluate(() => window.__counterpartyPending))
    .toBe(5);
  await reply(4);
  // Nothing offers to withdraw what is stated for the counterparty.
  await expect(target.locator(".ledger-counterparty-withdraw")).toHaveCount(0);
  await expect(answer).not.toContainText(
    label("desktop.ledger.counterparty.not_confirmed"),
  );
  const writes = await target.evaluate(() =>
    window.__counterpartyRequests!.filter(
      (request) => request.action !== "view",
    ),
  );
  expect(writes).toMatchObject([
    {
      action: "confirm",
      tax_identifier: "B12345678",
      country_code: "ES",
      note: "This draft belongs to B in ES",
    },
  ]);
  expect(writes).toHaveLength(1);
});

for (const action of ["confirm"] as const) {
  test(`an uncertain counterparty ${action} is not settled by a resolution-only lookup`, async ({
    page: target,
  }) => {
    await openLedger(target);
    await openSetup(target, "rules");
    await area(target, "desktop.ledger.rules.area.counterparties");
    await field(target, "desktop.ledger.counterparty.tax_id").fill(
      "LU20260001",
    );
    await field(target, "desktop.ledger.counterparty.country").fill("LU");
    await target.locator(".ledger-counterparty-view").click();
    const answer = target.locator(".ledger-counterparty-answer");
    await expect(answer).toBeVisible();
    await expect(answer).not.toContainText(
      label("desktop.ledger.counterparty.not_confirmed"),
    );
    await target.evaluate(() =>
      window.__scenarioLedger!.nextWrites(["unknown"]),
    );
    await field(answer, "desktop.ledger.counterparty.scope_label").selectOption(
      "eu_member",
    );
    await field(answer, "desktop.ledger.counterparty.asserted_by").fill(
      "Fixture operator",
    );
    await target.locator(".ledger-counterparty-confirm").click();
    const pause = target.locator(".ledger-paused");
    await expect(pause).toBeVisible();
    const before = await target.evaluate(
      () =>
        window.__scenarioHostCalls!.filter(
          (call) => call === "ledger ledger.counterparty",
        ).length,
    );
    await pause.locator(".ledger-paused-reread").click();
    await expect(pause).toContainText(
      label("desktop.ledger.paused.untold", {
        movement: label("desktop.ledger.counterparty.title"),
      }),
    );
    expect(
      await target.evaluate(
        () =>
          window.__scenarioHostCalls!.filter(
            (call) => call === "ledger ledger.counterparty",
          ).length,
      ),
    ).toBe(before);
  });
}

test("a counterparty conflict keeps the draft and shows both authoritative values", async ({
  page: target,
}) => {
  await openLedger(target);
  await target.evaluate(() => {
    const port = window.__fixtureLedger!;
    const submit = port.submit;
    port.submit = async (definition, payload) => {
      const request = payload as JsonObject;
      if (
        definition === "ledger.counterparty" &&
        request.action === "confirm"
      ) {
        const answer = await submit(definition, {
          action: "view",
          tax_identifier: request.tax_identifier,
          country_code: request.country_code,
        } as typeof payload);
        if (answer.kind !== "settled") return answer;
        return {
          ...answer,
          result: {
            ...answer.result,
            action: "confirm",
            resolution: null,
            facts: null,
            recorded: null,
            changed: false,
            conflict_context: [
              ["confirmed_scope", "eu_member"],
              ["asserted_scope", "es_mainland"],
            ],
          },
        } as typeof answer;
      }
      return submit(definition, payload);
    };
  });
  await openSetup(target, "rules");
  await area(target, "desktop.ledger.rules.area.counterparties");
  await field(target, "desktop.ledger.counterparty.tax_id").fill("LU20260001");
  await target.locator(".ledger-counterparty-view").click();
  const answer = target.locator(".ledger-counterparty-answer");
  await field(answer, "desktop.ledger.counterparty.scope_label").selectOption(
    "es_mainland",
  );
  await field(answer, "desktop.ledger.counterparty.asserted_by").fill(
    "Fixture operator",
  );
  await field(answer, "desktop.ledger.counterparty.note").fill(
    "Retain this proposed correction",
  );
  await target.locator(".ledger-counterparty-confirm").click();
  const conflict = answer
    .getByRole("alert")
    .filter({ hasText: label("desktop.ledger.counterparty.conflict") });
  await expect(conflict).toBeVisible();
  await expect(conflict).toContainText(
    label("desktop.ledger.counterparty.scope.eu_member"),
  );
  await expect(conflict).toContainText(
    label("desktop.ledger.counterparty.scope.es_mainland"),
  );
  await expect(field(answer, "desktop.ledger.counterparty.note")).toHaveValue(
    "Retain this proposed correction",
  );
  await expect(
    field(answer, "desktop.ledger.counterparty.asserted_by"),
  ).toHaveValue("Fixture operator");
  await expect(target.locator(".ledger-paused")).toHaveCount(0);
  await button(answer, "desktop.ledger.counterparty.withdraw").click();
  await target.locator(".ledger-counterparty-withdraw").click();
  await expect(conflict).toHaveCount(0);
});

test("a settled counterparty answer that omits a proposed value keeps the draft", async ({
  page: target,
}) => {
  await openLedger(target);
  await target.evaluate(() => {
    const port = window.__fixtureLedger!;
    const submit = port.submit;
    port.submit = async (definition, payload) => {
      const answer = await submit(definition, payload);
      if (
        definition === "ledger.counterparty" &&
        (payload as JsonObject).action === "confirm" &&
        answer.kind === "settled"
      ) {
        const result = answer.result as unknown as {
          facts: Record<string, unknown>;
        };
        return {
          ...answer,
          result: {
            ...answer.result,
            facts: { ...result.facts, territorial_scope: null },
          },
        } as typeof answer;
      }
      return answer;
    };
  });
  await openSetup(target, "rules");
  await area(target, "desktop.ledger.rules.area.counterparties");
  await field(target, "desktop.ledger.counterparty.tax_id").fill("LU20260001");
  await target.locator(".ledger-counterparty-view").click();
  const answer = target.locator(".ledger-counterparty-answer");
  await field(answer, "desktop.ledger.counterparty.scope_label").selectOption(
    "eu_member",
  );
  await field(answer, "desktop.ledger.counterparty.asserted_by").fill(
    "Fixture operator",
  );
  await field(answer, "desktop.ledger.counterparty.note").fill(
    "Keep the proposed scope",
  );
  await target.locator(".ledger-counterparty-confirm").click();
  await expect(answer.getByRole("alert")).toContainText(
    label("desktop.ledger.counterparty.not_applied"),
  );
  await expect(field(answer, "desktop.ledger.counterparty.note")).toHaveValue(
    "Keep the proposed scope",
  );
  await expect(target.locator(".ledger-paused")).toHaveCount(0);
});

test("a successful counterparty update keeps its attribution through a failed refresh without keeping a saved draft", async ({
  page: target,
}) => {
  await openLedger(target);
  await target.evaluate(() => {
    const port = window.__fixtureLedger!;
    const submit = port.submit;
    let failView = false;
    port.submit = async (definition, payload) => {
      if (
        definition === "ledger.counterparty" &&
        (payload as JsonObject).action === "view" &&
        failView
      ) {
        failView = false;
        throw Object.assign(new Error("fixture read failure"), {
          code: "unavailable",
        });
      }
      const answer = await submit(definition, payload);
      if (
        definition === "ledger.counterparty" &&
        (payload as JsonObject).action === "confirm" &&
        answer.kind === "settled"
      ) {
        const result = answer.result as unknown as {
          facts: Record<string, unknown>;
        };
        failView = true;
        return {
          ...answer,
          result: {
            ...answer.result,
            facts: { ...result.facts, asserted_by: "Original operator" },
          },
        } as typeof answer;
      }
      return answer;
    };
  });
  await openSetup(target, "rules");
  await area(target, "desktop.ledger.rules.area.counterparties");
  await field(target, "desktop.ledger.counterparty.tax_id").fill("LU20260001");
  await target.locator(".ledger-counterparty-view").click();
  const answer = target.locator(".ledger-counterparty-answer");
  await field(answer, "desktop.ledger.counterparty.scope_label").selectOption(
    "eu_member",
  );
  await field(answer, "desktop.ledger.counterparty.asserted_by").fill(
    "Current operator",
  );
  await field(answer, "desktop.ledger.counterparty.note").fill("Updated note");
  await target.locator(".ledger-counterparty-confirm").click();
  await expect(
    target.getByRole("status").filter({ hasText: "Original operator" }),
  ).toBeVisible();
  await expect(answer).toHaveCount(0);
  await target.locator(".ledger-counterparty-view").click();
  await expect(field(answer, "desktop.ledger.counterparty.note")).toHaveValue(
    "",
  );
  await expect(
    field(answer, "desktop.ledger.counterparty.asserted_by"),
  ).toHaveValue("");
  await expect(answer).not.toContainText(
    label("desktop.ledger.counterparty.not_applied"),
  );
  await target.locator(".ledger-counterparty-view").click();
  await expect(
    target.getByRole("status").filter({ hasText: "Original operator" }),
  ).toBeVisible();
  await field(target, "desktop.ledger.counterparty.tax_id").fill("B12345678");
  await expect(
    target.getByRole("status").filter({ hasText: "Original operator" }),
  ).toHaveCount(0);
});

test("a counterparty can confirm only its VAT state and keeps edits made while saving", async ({
  page: target,
}) => {
  await openLedger(target);
  await target.evaluate(() => {
    const port = window.__fixtureLedger!;
    const submit = port.submit;
    window.__counterpartyRequests = [];
    port.submit = async (definition, payload) => {
      const request = payload as JsonObject;
      const answer = await submit(definition, payload);
      if (
        definition === "ledger.counterparty" &&
        request.action === "confirm"
      ) {
        window.__counterpartyRequests!.push(request);
        await new Promise<void>((resolve) => {
          window.__counterpartyReply = () => resolve();
        });
      }
      return answer;
    };
  });
  await openSetup(target, "rules");
  await area(target, "desktop.ledger.rules.area.counterparties");
  await field(target, "desktop.ledger.counterparty.tax_id").fill("LU20260001");
  await target.locator(".ledger-counterparty-view").click();
  const answer = target.locator(".ledger-counterparty-answer");
  await field(answer, "desktop.ledger.counterparty.state").fill("LU");
  const confirm = target.locator(".ledger-counterparty-confirm");
  await expect(confirm).toHaveAttribute("aria-disabled", "true");
  const actor = field(answer, "desktop.ledger.counterparty.asserted_by");
  await expect(actor).toHaveAttribute("maxlength", "256");
  await actor.fill("Fixture operator");
  const note = field(answer, "desktop.ledger.counterparty.note");
  await note.fill("Submitted note");
  await confirm.click();
  await expect
    .poll(() => target.evaluate(() => window.__counterpartyRequests!.length))
    .toBe(1);
  await note.fill("A later unsaved edit");
  await target.evaluate(() => window.__counterpartyReply!(0));
  await expect(note).toHaveValue("A later unsaved edit");
  expect(
    await target.evaluate(() => window.__counterpartyRequests),
  ).toMatchObject([
    {
      action: "confirm",
      country_code: null,
      territorial_scope: null,
      identification_state: "LU",
      asserted_by: "Fixture operator",
      note: "Submitted note",
    },
  ]);
});
