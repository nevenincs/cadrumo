import { expect, test } from "@playwright/test";
import { label } from "../support/strings";
import {
  open,
  band,
  row,
  save,
  aeatEditor,
  profileAction,
} from "../support/userProfilePage";

// The profile page's AEAT access editor: Cl@ve and certificate setup, masked write-only facts and stale-profile refusal.

test("saved Cl@ve setup asks specifically for the NIE support number", async ({
  page,
}) => {
  await open(page, "censo-nie");
  const region = band(page);
  await expect(region).toContainText(
    label("auth.sync.requirement.nie_support_required"),
  );
  await expect(region).not.toContainText(
    label("auth.sync.requirement.profile_tax_id_required"),
  );
  await expect(region).not.toContainText(
    label("auth.sync.requirement.auth_method_required"),
  );
  await region
    .getByRole("button", {
      name: label("desktop.profile.censo.setup"),
      exact: true,
    })
    .click();
  // Setting up AEAT access is the window's own editor, for this profile.
  const editor = aeatEditor(page);
  await expect(editor).toContainText(
    label("auth.sync.requirement.nie_support_required"),
  );
  await editor.getByLabel("Support number", { exact: true }).fill("ABC123456");
  await save(editor).click();
  await expect(editor).toContainText(label("desktop.profile.aeat.saved"));
  await expect(editor).not.toContainText(
    label("auth.sync.requirement.nie_support_required"),
  );
  await editor
    .getByRole("button", { name: label("desktop.profile.aeat.done") })
    .click();
  // The band asks again and finds the prerequisites met.
  await expect(region).not.toContainText(
    label("auth.sync.requirement.nie_support_required"),
  );
  await expect(
    region.getByRole("button", {
      name: label("desktop.profile.censo.pull"),
      exact: true,
    }),
  ).toBeEnabled();
});

test("authentication facts are edited in the page and a masked one is write-only", async ({
  page,
}) => {
  const profile = await open(page);
  const support = row(profile, "auth.numero_soporte");
  await support.focus();
  await page.keyboard.press("Enter");
  const dialog = page.getByRole("dialog", {
    name: "Support number",
    exact: true,
  });
  const input = dialog.getByLabel("Support number", { exact: true });
  await expect(input).toHaveValue("");
  // Nothing is typed, so there is nothing to save.
  await expect(save(dialog)).toBeDisabled();
  await input.fill("ABC123456");
  await save(dialog).click();
  await expect(dialog).toHaveCount(0);
  await expect(support).toContainText("••••");
  await expect(profile).not.toContainText("ABC123456");
  // Opened again it is empty and says a value is saved; empty keeps it.
  await support.focus();
  await page.keyboard.press("Enter");
  await expect(input).toHaveValue("");
  await expect(dialog).toContainText(label("desktop.profile.aeat.saved_value"));
  await expect(save(dialog)).toBeDisabled();
  await page.keyboard.press("Escape");
  await expect(support).toContainText("••••");
  // The ordinary Clear action removes it, as it does any optional detail.
  await support.click({ button: "right" });
  await page
    .getByRole("menuitem", {
      name: label("desktop.profile.action.clear", {
        field: "Support number",
      }),
      exact: true,
    })
    .click();
  await expect(support).not.toContainText("••••");
  expect(await page.evaluate(() => window.__scenarioProfile!.writes())).toBe(2);
});

test("the method and its route are edited in the window, with the facts each asks for", async ({
  page,
}) => {
  const profile = await open(page);
  await profileAction(page, "desktop.profile.action.aeat_access");
  const editor = aeatEditor(page);
  await expect(editor).toContainText(
    label("auth.sync.requirement.auth_method_required"),
  );
  await expect(save(editor)).toBeDisabled();
  const method = editor.getByLabel("Authentication method", { exact: true });
  const dni = editor.getByLabel("DNI or NIE for Cl@ve", { exact: true });
  const supportNumber = editor.getByLabel("Support number", { exact: true });
  const validity = editor.getByLabel("Validity date", { exact: true });
  const route = editor.getByLabel("Cl@ve Móvil route", { exact: true });
  const passphrase = editor.getByLabel(
    label("desktop.profile.aeat.passphrase"),
    { exact: true },
  );
  await method.selectOption("clave_movil");
  await expect(route).toHaveValue("app_request");
  for (const field of [dni, supportNumber, validity])
    await expect(field).toBeVisible();
  await expect(editor).toContainText(
    label("desktop.profile.aeat.document_hint"),
  );
  await route.selectOption("qr");
  await expect(dni).toBeVisible();
  await expect(supportNumber).toHaveCount(0);
  await expect(validity).toHaveCount(0);
  await method.selectOption("certificate");
  await expect(route).toHaveCount(0);
  await expect(dni).toHaveCount(0);
  await expect(passphrase).toBeVisible();
  await method.selectOption("clave_movil");
  await route.selectOption("app_request");
  await dni.fill("12345678Z");
  await validity.fill("2030-01-31");
  await save(editor).click();
  await expect(editor).toContainText(label("desktop.profile.aeat.saved"));
  // The facts, then the method: each under the revision the one before left.
  expect(await page.evaluate(() => window.__scenarioProfile!.writes())).toBe(3);
  await expect(editor).not.toContainText(
    label("auth.sync.requirement.auth_method_required"),
  );
  await expect(editor).not.toContainText(
    label("auth.sync.requirement.dni_validity_required"),
  );
  await editor
    .getByRole("button", { name: label("desktop.profile.aeat.done") })
    .click();
  await expect(editor).toHaveCount(0);
  await expect(row(profile, "auth.provider")).toContainText("Cl@ve Móvil");
  await expect(row(profile, "auth.clave_movil_route")).toContainText(
    "Request in app",
  );
  await expect(row(profile, "auth.fecha_validez")).toContainText("••••");
  await expect(profile).not.toContainText("2030-01-31");
});

test("a certificate is chosen in the native dialog and its passphrase is kept out of the page", async ({
  page,
}) => {
  const profile = await open(page);
  await row(profile, "auth.provider").focus();
  await page.keyboard.press("F2");
  const editor = aeatEditor(page);
  await editor
    .getByLabel("Authentication method", { exact: true })
    .selectOption("certificate");
  await expect(editor).toContainText(
    label("desktop.profile.aeat.certificate_none"),
  );
  const choose = editor.getByRole("button", {
    name: label("desktop.profile.aeat.certificate_choose"),
  });
  // A file that is not a certificate is refused by the dialog's host.
  await page.evaluate(() => window.__scenarioProfile!.failPick());
  await choose.click();
  await expect(editor.getByRole("alert")).toContainText(
    label("auth.sync.requirement.certificate_file_required"),
  );
  await expect(editor).toContainText(
    label("desktop.profile.aeat.certificate_none"),
  );
  await choose.click();
  await expect(editor.getByRole("alert")).toHaveCount(0);
  // Only the file's name comes back to the window.
  await expect(editor).toContainText("firma-ana-soler.p12");
  const secret = editor.getByLabel(label("desktop.profile.aeat.passphrase"), {
    exact: true,
  });
  await expect(secret).toHaveAttribute("type", "password");
  await expect(secret).toHaveAttribute("autocomplete", "new-password");
  await secret.fill("correct horse battery");
  await save(editor).click();
  await expect(editor).toContainText(label("desktop.profile.aeat.saved"));
  await expect(secret).toHaveValue("");
  await expect(editor).not.toContainText(
    label("auth.sync.requirement.certificate_file_required"),
  );
  await expect(editor).not.toContainText(
    label("auth.sync.requirement.certificate_passphrase_required"),
  );
  await expect(editor).toContainText(
    label("desktop.profile.aeat.certificate_saved"),
  );
  expect(
    await page.evaluate(() => ({
      saved: window.__scenarioProfile!.credentials(),
      file: window.__scenarioProfile!.certificate(),
    })),
  ).toEqual({ saved: ["certificate"], file: "firma-ana-soler.p12" });
  expect(
    await page.evaluate(() => document.documentElement.outerHTML),
  ).not.toContain("correct horse battery");
  // Closed and opened again, no passphrase is kept for the next time.
  await editor
    .getByRole("button", { name: label("desktop.profile.aeat.done") })
    .click();
  await row(profile, "auth.provider").focus();
  await page.keyboard.press("Enter");
  await expect(secret).toHaveValue("");
});

test("a credential that did not reach the runtime or was left unconfirmed is reported and never retried", async ({
  page,
}) => {
  const profile = await open(page);
  await row(profile, "auth.provider").focus();
  await page.keyboard.press("Enter");
  const editor = aeatEditor(page);
  await editor
    .getByLabel("Authentication method", { exact: true })
    .selectOption("clave_permanente");
  await editor
    .getByLabel("DNI or NIE for Cl@ve", { exact: true })
    .fill("12345678Z");
  const item = label("desktop.profile.aeat.password", {
    method: "Cl@ve Permanente",
  });
  const secret = editor.getByLabel(item, { exact: true });
  const attempts = () =>
    page.evaluate(() => window.__scenarioProfile!.credentialAttempts());
  const writes = () => page.evaluate(() => window.__scenarioProfile!.writes());
  const credentials = () =>
    page.evaluate(() => window.__scenarioProfile!.credentials());
  // Each way a save can end without being confirmed saved, as the host says it.
  const endings = [
    ["refused", "credential_failed"],
    ["unknown", "credential_unknown"],
    ["saved_unread", "credential_unknown"],
    ["unavailable", "credential_unavailable"],
  ] as const;
  let sent = 0;
  for (const [outcome, key] of endings) {
    await page.evaluate(
      (ending) => window.__scenarioProfile!.failCredential(ending),
      outcome,
    );
    await secret.fill(`try ${sent}`);
    await save(editor).click();
    await expect(editor.getByRole("alert")).toContainText(
      label(`desktop.profile.aeat.${key}`, { item }),
    );
    sent++;
    await expect(secret).toHaveValue("");
    // Nothing is typed, so nothing can be sent again by itself.
    await expect(save(editor)).toBeDisabled();
    expect(await attempts()).toBe(sent);
    expect(await credentials()).toEqual([]);
    // The fact and the method were saved before the secret was sent, once.
    expect(await writes()).toBe(2);
  }
  await expect(editor).toContainText(
    label("auth.sync.requirement.clave_password_required"),
  );
  // The person's own next attempt is the only retry.
  await secret.fill("last try");
  await save(editor).click();
  await expect(editor).toContainText(label("desktop.profile.aeat.saved"));
  expect(await attempts()).toBe(sent + 1);
  expect(await credentials()).toEqual(["clave_permanente"]);
  await expect(editor).not.toContainText(
    label("auth.sync.requirement.clave_password_required"),
  );
  // No profile edit was repeated for it.
  expect(await writes()).toBe(2);
});

test("the AEAT editor does not save over a profile that changed elsewhere", async ({
  page,
}) => {
  const profile = await open(page);
  await row(profile, "auth.provider").focus();
  await page.keyboard.press("Enter");
  const editor = aeatEditor(page);
  await editor
    .getByLabel("Authentication method", { exact: true })
    .selectOption("clave_permanente");
  await page.evaluate(() => window.__scenarioProfile!.update("Elsewhere"));
  await expect(editor).toContainText(label("desktop.profile.conflict"));
  await expect(save(editor)).toBeDisabled();
  expect(await page.evaluate(() => window.__scenarioProfile!.writes())).toBe(0);
});
