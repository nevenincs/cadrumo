import { expect, test, type Page } from "@playwright/test";
import { label } from "../support/strings";

// The API keys for agents outside Cadrumo: the signed-in profile's keys, each
// with what it may do and when it was used, and the person's ways to issue
// one and to revoke one. A key is never shown: issuing hands back the
// reference an agent's launch configuration names it by, once. Issuing is the
// signed-in person's one press: nothing asks for a password or for a second
// approval. Nothing is asked of the host, and nothing shown, without a
// profile signed in here.
//
// The section is the second of the agent's settings, which the agent's own
// header opens: the same door as the providers' keys, each section read and
// shown on its own. The fixture host keeps the keys and answers as the
// product's command line does.

/** The first eight characters of each seeded key's id, which is its name. */
const USED = "3f9a1c2e";
const UNUSED = "b7c4e2d9";
const CLEANUP = "e5b1d0c2";
const SUSPENDED = "9d2f6a41";
const EXPIRED = "2a8e5c70";
const REVOKED = "6c0b9e83";

const column = (target: Page) => target.locator(".pane-agent");

const settingsButton = (target: Page) =>
  column(target).getByRole("button", { name: label("desktop.agent.settings") });

const section = (target: Page) =>
  column(target).getByRole("region", {
    name: label("desktop.agent_keys.title"),
  });

/** Opens the agent's settings, where the keys are the second section. */
async function open(target: Page, scenario = "signed-in") {
  await target.goto(`/scenarios.html?scenario=${scenario}&latency=0&bar=off`);
  await settingsButton(target).click();
  await expect(section(target)).toBeVisible();
}

const key = (target: Page, id: string) =>
  section(target)
    .getByRole("listitem")
    .filter({
      has: target.getByRole("heading", {
        name: label("desktop.agent_keys.key_title", { id }),
      }),
    });

const calls = (target: Page) =>
  target.evaluate(() => window.__scenarioHostCalls ?? []);

/** Whether `text` is anywhere a secret could have been left behind. */
const traces = (target: Page, text: string) =>
  target.evaluate((secret) => {
    const stored = (storage: Storage) =>
      Array.from({ length: storage.length }, (_, index) => {
        const name = storage.key(index) ?? "";
        return `${name}=${storage.getItem(name) ?? ""}`;
      }).join("\n");
    return {
      page: document.documentElement.outerHTML.includes(secret),
      fields: [...document.querySelectorAll("input")].some((input) =>
        input.value.includes(secret),
      ),
      local: stored(localStorage).includes(secret),
      session: stored(sessionStorage).includes(secret),
      address: location.href.includes(secret),
      calls: (window.__scenarioHostCalls ?? []).join("\n").includes(secret),
    };
  }, text);

const NOWHERE = {
  page: false,
  fields: false,
  local: false,
  session: false,
  address: false,
  calls: false,
};

const issueButton = (target: Page) =>
  section(target).getByRole("button", {
    name: label("desktop.agent_keys.issue_submit"),
  });

test.beforeEach(async ({ page: target }) => {
  await target.addInitScript(() => {
    if (sessionStorage.getItem("layout-cleared")) return;
    localStorage.clear();
    sessionStorage.setItem("layout-cleared", "1");
  });
});

test("each key says what it may do, when it was issued and last used, and where it stands", async ({
  page: target,
}) => {
  await open(target);
  await expect(section(target)).toBeVisible();

  const used = key(target, USED);
  await expect(used).toContainText(label("desktop.agent_keys.standing_active"));
  await expect(used).toContainText(
    label("desktop.agent_keys.scope_profile_values"),
  );
  await expect(used).toContainText(
    label("desktop.agent_keys.scope_tax_values"),
  );
  await expect(used).toContainText(
    label("desktop.agent_keys.scope_all_operations"),
  );
  await expect(used).toContainText(/Issued .+ · Expires .+ · Last used .+/);

  // A key that never let an agent in says so, and does not read tax values.
  const unused = key(target, UNUSED);
  await expect(unused).toContainText(label("desktop.agent_keys.never_used"));
  await expect(unused).toContainText(
    label("desktop.agent_keys.scope_no_tax_values"),
  );

  await expect(key(target, SUSPENDED)).toContainText(
    label("desktop.agent_keys.standing_suspended"),
  );
  // A key past its end is expired whatever its grant says.
  await expect(key(target, EXPIRED)).toContainText(
    label("desktop.agent_keys.standing_expired"),
  );
  await expect(key(target, EXPIRED)).toContainText(/Expired /);
  // A revoked key is final: nothing to do with it.
  const revoked = key(target, REVOKED);
  await expect(revoked).toContainText(
    label("desktop.agent_keys.standing_revoked"),
  );
  await expect(revoked.getByRole("button")).toHaveCount(0);
  await expect(revoked).not.toContainText(/Expires /);
});

test("one press issues a key and shows its reference once", async ({
  page: target,
}) => {
  await open(target);
  const before = await section(target)
    .getByRole("heading", { level: 4 })
    .count();
  const form = section(target).getByRole("form", {
    name: label("desktop.agent_keys.issue"),
  });
  // Tax values are off until the person turns them on.
  const tax = form.getByLabel(label("desktop.agent_keys.tax_values"));
  await expect(tax).not.toBeChecked();
  await tax.check();
  await expect(issueButton(target)).toBeEnabled();
  await issueButton(target).click();

  // The reference is shown at once: no step stood between the press and it.
  const reference = section(target).getByLabel(
    label("desktop.agent_keys.reference_label"),
  );
  await expect(reference).toBeVisible();
  const shown = await reference.inputValue();
  expect(shown).toMatch(/^[0-9a-f-]{36}$/);
  await expect(section(target)).toContainText(
    label("desktop.agent_keys.issued_once"),
  );
  expect((await calls(target)).filter((call) => /Issue/.test(call))).toEqual([
    "agentAccessIssue",
  ]);

  // The key is in the list, with the tax values the person turned on.
  await expect(section(target).getByRole("heading", { level: 4 })).toHaveCount(
    before + 1,
  );
  await expect(
    section(target)
      .locator(".agent-key")
      .filter({ hasText: label("desktop.agent_keys.scope_tax_values") }),
  ).toHaveCount(3);

  // Copying asks the clipboard for the reference and nothing else.
  await section(target)
    .getByRole("button", { name: label("desktop.agent_keys.copy") })
    .click();
  await expect(
    section(target).getByRole("button", {
      name: label("desktop.agent_keys.copied"),
    }),
  ).toBeVisible();
  // The host was asked for the reference's thirty-six characters, and its
  // call log holds their number and nothing else.
  expect(
    (await calls(target)).filter((call) => call.startsWith("writeClipboard")),
  ).toEqual(["writeClipboard 36 characters"]);

  // Done brings the issuing choice back, with tax values off again.
  await section(target)
    .getByRole("button", { name: label("desktop.agent_keys.done") })
    .click();
  await expect(reference).toHaveCount(0);
  await expect(
    section(target).getByLabel(label("desktop.agent_keys.tax_values")),
  ).not.toBeChecked();
  await expect(issueButton(target)).toBeVisible();
});

test("the reference is left nowhere once it is closed", async ({
  page: target,
}) => {
  await open(target);
  await issueButton(target).click();
  const reference = section(target).getByLabel(
    label("desktop.agent_keys.reference_label"),
  );
  const shown = await reference.inputValue();
  expect(shown).toMatch(/^[0-9a-f-]{36}$/);

  await section(target)
    .getByRole("button", { name: label("desktop.agent_keys.done") })
    .click();
  await expect(reference).toHaveCount(0);
  // Not on the page, in its storage, its address or what the host was asked.
  expect(await traces(target, shown)).toEqual(NOWHERE);
});

test("nothing asks for a password, and issuing needs no second approval", async ({
  page: target,
}) => {
  await open(target);
  const field = section(target).locator(
    'input[type="password"], input[autocomplete*="password"]',
  );
  await expect(field).toHaveCount(0);
  await expect(section(target)).not.toContainText(/password|contraseña/i);

  await issueButton(target).click();
  await expect(
    section(target).getByLabel(label("desktop.agent_keys.reference_label")),
  ).toBeVisible();
  await expect(field).toHaveCount(0);
  await expect(section(target).getByRole("dialog")).toHaveCount(0);
  await expect(target.getByRole("dialog")).toHaveCount(0);
  await expect(section(target)).not.toContainText(/password|contraseña/i);
});

test("a key is revoked only after the person confirms, and then has nothing left to do", async ({
  page: target,
}) => {
  await open(target);
  const unused = key(target, UNUSED);
  await unused
    .getByRole("button", { name: label("desktop.agent_keys.revoke") })
    .click();
  await expect(unused).toContainText(
    label("desktop.agent_keys.revoke_confirm"),
  );
  // Cancelling revokes nothing, and the host is not asked.
  await unused
    .getByRole("button", { name: label("desktop.agent_keys.cancel") })
    .click();
  await expect(unused).toContainText(
    label("desktop.agent_keys.standing_active"),
  );
  expect((await calls(target)).filter((call) => /Revoke/.test(call))).toEqual(
    [],
  );

  await unused
    .getByRole("button", { name: label("desktop.agent_keys.revoke") })
    .click();
  await unused
    .getByRole("button", {
      name: label("desktop.agent_keys.revoke_confirm_action"),
    })
    .click();
  await expect(unused).toContainText(
    label("desktop.agent_keys.standing_revoked"),
  );
  await expect(unused.getByRole("button")).toHaveCount(0);
  expect((await calls(target)).filter((call) => /Revoke/.test(call))).toEqual([
    `agentAccessRevoke ${UNUSED}`,
  ]);
});

test("a revoked key whose stored copy is still being removed says so", async ({
  page: target,
}) => {
  await open(target);
  const pending = key(target, CLEANUP);
  await pending
    .getByRole("button", { name: label("desktop.agent_keys.revoke") })
    .click();
  await pending
    .getByRole("button", {
      name: label("desktop.agent_keys.revoke_confirm_action"),
    })
    .click();
  await expect(pending).toContainText(
    label("desktop.agent_keys.standing_revoked"),
  );
  await expect(pending.getByRole("status")).toContainText(
    label("desktop.agent_keys.cleanup_pending"),
  );
});

test("the keys are read when the settings open, with the providers' own section beside them", async ({
  page: target,
}) => {
  await target.goto("/scenarios.html?scenario=signed-in&latency=0&bar=off");
  // Nothing of the keys is asked until the settings are opened.
  expect(
    (await calls(target)).filter((call) => /^agentAccess/.test(call)),
  ).toEqual([]);
  await settingsButton(target).click();
  await expect(key(target, USED)).toBeVisible();
  expect(
    (await calls(target)).filter((call) => /^agentAccess/.test(call)),
  ).toEqual(["agentAccessList"]);
  // The providers' keys are the other section, read on their own.
  await expect(
    column(target).getByRole("region", {
      name: label("desktop.providers.title"),
    }),
  ).toBeVisible();
  // Closing the settings forgets nothing it must keep and asks nothing more.
  await settingsButton(target).click();
  await expect(section(target)).toHaveCount(0);
  expect(
    (await calls(target)).filter((call) => /^agentAccess/.test(call)),
  ).toEqual(["agentAccessList"]);
});

test("without a profile signed in here, the settings are not offered and nothing is asked", async ({
  page: target,
}) => {
  await target.goto("/scenarios.html?scenario=signed-out&latency=0&bar=off");
  await expect(settingsButton(target)).toHaveCount(0);
  await expect(section(target)).toHaveCount(0);
  expect(
    (await calls(target)).filter((call) => /^agentAccess/.test(call)),
  ).toEqual([]);
});
