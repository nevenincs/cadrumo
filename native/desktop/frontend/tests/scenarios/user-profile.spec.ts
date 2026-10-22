import { expect, test, type Page } from "@playwright/test";
import { label } from "../support/strings";

async function open(page: Page, scenario = "user-profile") {
  await page.goto(`/scenarios.html?scenario=${scenario}&latency=0&bar=off`);
  await page
    .locator(".rail")
    .getByRole("button", { name: label("desktop.profile.title"), exact: true })
    .click();
  await expect(page.locator(".user-profile-page")).toContainText("Soler Vidal");
}

for (const language of ["en", "es", "ca", "hu"]) {
  test(`Censo labels render clean Unicode in ${language}`, async ({ page }) => {
    await page.goto(
      `/scenarios.html?scenario=censo-ready&latency=0&bar=off&lang=${language}`,
    );
    await page
      .locator(".rail")
      .getByRole("button", {
        name: label("desktop.profile.title", {}, language),
        exact: true,
      })
      .click();
    await page
      .locator(".user-profile-page")
      .getByRole("button", {
        name: label("desktop.profile.censo.title", {}, language),
        exact: true,
      })
      .click();
    const dialog = page.getByRole("dialog");
    await expect(
      dialog.getByRole("button", {
        name: label("desktop.profile.censo.pull", {}, language),
        exact: true,
      }),
    ).toBeEnabled();
    await expect(dialog).not.toContainText(
      /[\u00c3\u00c2\ufffd]|\u00e2\u20ac|\u00c5[\u2018\u2019\u00b1]/,
    );
  });
}
test("profile filters, edits and repeatable entries use saved data", async ({
  page,
}) => {
  await open(page);
  const profile = page.locator(".user-profile-page");
  await profile.getByRole("searchbox").fill("malaga");
  await expect(profile).toContainText("Málaga");
  await expect(profile.getByRole("region", { name: "Identity" })).toHaveCount(
    0,
  );
  await profile.getByRole("searchbox").clear();
  await profile
    .getByLabel(label("desktop.profile.filter"), { exact: true })
    .selectOption("missing");
  await expect(profile).toContainText("Tax ID (NIF/NIE/CIF)");
  await expect(profile).not.toContainText("Soler Vidal");
  await profile
    .getByLabel(label("desktop.profile.filter"), { exact: true })
    .selectOption("all");
  await profile
    .getByRole("button", {
      name: label("desktop.profile.edit_field", { field: "Given name" }),
      exact: true,
    })
    .click();
  const dialog = page.getByRole("dialog", { name: "Given name", exact: true });
  await dialog.getByLabel("Given name", { exact: true }).fill("Ana Updated");
  await dialog
    .getByRole("button", { name: label("desktop.profile.save"), exact: true })
    .click();
  await expect(dialog).toHaveCount(0);
  await expect(profile).toContainText("Ana Updated");
  await profile
    .getByLabel(label("desktop.profile.sections"), { exact: true })
    .selectOption("activities");
  await profile
    .getByRole("button", { name: label("desktop.profile.add"), exact: true })
    .click();
  const row = page.getByRole("dialog", {
    name: "Business activities",
    exact: true,
  });
  await row
    .getByRole("textbox", { name: "Activity description", exact: true })
    .fill("Partner Two");
  await row
    .getByRole("button", { name: label("desktop.profile.save"), exact: true })
    .click();
  await expect(profile).toContainText("Partner Two");
});

test("field labels, values and keyboard activation open the editor", async ({
  page,
}) => {
  await open(page);
  const profile = page.locator(".user-profile-page");
  const field = profile.getByRole("button", {
    name: label("desktop.profile.edit_field", { field: "Given name" }),
    exact: true,
  });
  const dialog = page.getByRole("dialog", { name: "Given name", exact: true });
  for (const target of ["Given name", "Ana"]) {
    const text = profile.getByText(target, { exact: true });
    await text.scrollIntoViewIfNeeded();
    const box = (await text.boundingBox())!;
    await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
    await expect(dialog.getByLabel("Given name", { exact: true })).toHaveValue(
      "Ana",
    );
    await page.keyboard.press("Escape");
    await expect(dialog).toHaveCount(0);
  }
  for (const key of ["Enter", "Space"]) {
    await field.focus();
    await page.keyboard.press(key);
    await expect(dialog).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(field).toBeFocused();
  }
  const empty = profile
    .locator("dt")
    .filter({ hasText: "Tax ID (NIF/NIE/CIF)" });
  const box = (await empty.boundingBox())!;
  await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
  await expect(
    page.getByRole("dialog", { name: "Tax ID (NIF/NIE/CIF)", exact: true }),
  ).toBeVisible();
});
test("external changes refresh once, preserve drafts and block stale saves", async ({
  page,
}) => {
  await open(page);
  const profile = page.locator(".user-profile-page");
  await profile
    .getByRole("button", {
      name: label("desktop.profile.edit_field", { field: "Given name" }),
      exact: true,
    })
    .click();
  const dialog = page.getByRole("dialog", { name: "Given name", exact: true });
  await dialog.getByLabel("Given name", { exact: true }).fill("Unsaved draft");
  await page.evaluate(() =>
    window.__scenarioProfile!.update("Changed by the agent"),
  );
  await expect(profile).toContainText("Changed by the agent");
  await expect(dialog.getByLabel("Given name", { exact: true })).toHaveValue(
    "Unsaved draft",
  );
  await expect(
    dialog.getByRole("button", {
      name: label("desktop.profile.save"),
      exact: true,
    }),
  ).toBeDisabled();
  expect(await page.evaluate(() => window.__scenarioProfile!.writes())).toBe(0);
  const before = await page.evaluate(() => window.__scenarioProfile!.reads());
  await page.evaluate(() => window.__scenarioProfile!.burst());
  await expect
    .poll(() => page.evaluate(() => window.__scenarioProfile!.reads()))
    .toBe(before + 2);
});

test("a server conflict refreshes the profile without discarding the draft or retrying", async ({
  page,
}) => {
  await open(page);
  const profile = page.locator(".user-profile-page");
  await profile
    .getByRole("button", {
      name: label("desktop.profile.edit_field", { field: "Given name" }),
      exact: true,
    })
    .click();
  const dialog = page.getByRole("dialog", { name: "Given name", exact: true });
  await dialog
    .getByLabel("Given name", { exact: true })
    .fill("Keep this draft");
  const before = await page.evaluate(() => window.__scenarioProfile!.reads());
  await page.evaluate(() => window.__scenarioProfile!.conflict());
  await dialog
    .getByRole("button", { name: label("desktop.profile.save"), exact: true })
    .click();
  await expect
    .poll(() => page.evaluate(() => window.__scenarioProfile!.reads()))
    .toBe(before + 1);
  await expect(dialog.getByLabel("Given name", { exact: true })).toHaveValue(
    "Keep this draft",
  );
  await expect(
    dialog.getByRole("button", {
      name: label("desktop.profile.save"),
      exact: true,
    }),
  ).toBeDisabled();
  expect(await page.evaluate(() => window.__scenarioProfile!.writes())).toBe(1);
});

test("section navigation combines with search and saved-field filters", async ({
  page,
}) => {
  await open(page);
  const profile = page.locator(".user-profile-page");
  const sections = profile.getByLabel(label("desktop.profile.sections"), {
    exact: true,
  });
  const filter = profile.getByLabel(label("desktop.profile.filter"), {
    exact: true,
  });
  await sections.selectOption("identity");
  await expect(profile.getByRole("region", { name: "Identity" })).toBeVisible();
  await expect(
    profile.getByRole("region", { name: "Contact and fiscal address" }),
  ).toHaveCount(0);
  await filter.selectOption("saved");
  await expect(profile).toContainText("Soler Vidal");
  await expect(profile).not.toContainText("Tax ID (NIF/NIE/CIF)");
  await profile.getByRole("searchbox").fill("no matching detail");
  await expect(profile).toContainText(label("desktop.profile.empty"));
  await profile.getByRole("searchbox").clear();
  await sections.selectOption("contact");
  await expect(profile).toContainText("Málaga");
  await expect(profile).not.toContainText("Soler Vidal");
  await sections.selectOption("");
  await filter.selectOption("all");
  await expect(profile.getByRole("region", { name: "Identity" })).toBeVisible();
  await expect(
    profile.getByRole("region", { name: "Contact and fiscal address" }),
  ).toBeVisible();
});

test("repeatable entries can be updated and removed with confirmation", async ({
  page,
}) => {
  await open(page);
  await page
    .locator(".user-profile-page")
    .getByLabel(label("desktop.profile.sections"), { exact: true })
    .selectOption("activities");
  const partners = page.getByRole("region", {
    name: "Business activities",
    exact: true,
  });
  await partners
    .getByRole("button", { name: label("desktop.profile.add"), exact: true })
    .click();
  const dialog = page.getByRole("dialog", {
    name: "Business activities",
    exact: true,
  });
  const save = dialog.getByRole("button", {
    name: label("desktop.profile.save"),
    exact: true,
  });
  await dialog
    .getByRole("textbox", { name: "Activity description", exact: true })
    .fill("First Partner");
  await save.click();
  await expect(dialog).toHaveCount(0);
  await partners
    .getByRole("button", {
      name: label("desktop.profile.edit_field", {
        field: "Activity description",
      }),
      exact: true,
    })
    .click();
  await expect(
    dialog.getByRole("textbox", { name: "Activity description", exact: true }),
  ).toHaveValue("First Partner");
  await dialog
    .getByRole("textbox", { name: "Activity description", exact: true })
    .fill("Updated Partner");
  await save.click();
  await expect(dialog).toHaveCount(0);
  await expect(partners).toContainText("Updated Partner");
  await partners
    .getByRole("button", { name: label("desktop.profile.remove"), exact: true })
    .click();
  await expect(dialog).toContainText(label("desktop.profile.remove_help"));
  await dialog
    .getByRole("button", { name: label("desktop.profile.cancel"), exact: true })
    .last()
    .click();
  await expect(partners).toContainText("Updated Partner");
  await partners
    .getByRole("button", { name: label("desktop.profile.remove"), exact: true })
    .click();
  await dialog
    .getByRole("button", { name: label("desktop.profile.remove"), exact: true })
    .click();
  await expect(dialog).toHaveCount(0);
  await expect(partners).not.toContainText("Updated Partner");
  await expect(
    partners.getByRole("button", {
      name: label("desktop.profile.add"),
      exact: true,
    }),
  ).toBeEnabled();
});
test("a refused save keeps the draft without claiming success", async ({
  page,
}) => {
  await open(page);
  await page
    .locator(".user-profile-page")
    .getByRole("button", {
      name: label("desktop.profile.edit_field", { field: "Given name" }),
      exact: true,
    })
    .click();
  const dialog = page.getByRole("dialog", { name: "Given name", exact: true });
  await dialog.getByLabel("Given name", { exact: true }).fill("Keep my draft");
  await page.evaluate(() => window.__scenarioProfile!.refuse());
  await dialog
    .getByRole("button", { name: label("desktop.profile.save"), exact: true })
    .click();
  await expect(dialog.getByRole("alert")).toContainText(
    label("desktop.profile.refused"),
  );
  await expect(dialog.getByLabel("Given name", { exact: true })).toHaveValue(
    "Keep my draft",
  );
});

test("uncertain saves require an explicit refresh before retrying", async ({
  page,
}) => {
  await open(page);
  await page
    .locator(".user-profile-page")
    .getByRole("button", {
      name: label("desktop.profile.edit_field", { field: "Given name" }),
      exact: true,
    })
    .click();
  const dialog = page.getByRole("dialog", { name: "Given name", exact: true });
  await dialog
    .getByLabel("Given name", { exact: true })
    .fill("Recovered draft");
  await page.evaluate(() => window.__scenarioProfile!.uncertain());
  const save = dialog.getByRole("button", {
    name: label("desktop.profile.save"),
    exact: true,
  });
  await save.click();
  await expect(dialog.getByRole("alert")).toContainText(
    label("desktop.profile.unknown"),
  );
  await expect(save).toBeDisabled();
  await dialog
    .getByRole("button", {
      name: label("desktop.profile.refresh"),
      exact: true,
    })
    .click();
  await expect(save).toBeEnabled();
  await expect(dialog.getByLabel("Given name", { exact: true })).toHaveValue(
    "Recovered draft",
  );
  await save.click();
  await expect(dialog).toHaveCount(0);
  await expect(page.locator(".user-profile-page")).toContainText(
    "Recovered draft",
  );
});

test("signing out hides private data even when an old read completes later", async ({
  page,
}) => {
  await open(page);
  // The account picker may retain its public profile label after sign-out;
  // use a distinct private field value to detect disclosure from an old read.
  const privateName = "Private taxpayer detail";
  await page.evaluate(
    (name) => window.__scenarioProfile!.update(name),
    privateName,
  );
  await expect(page.locator(".user-profile-page")).toContainText(privateName);
  await page.evaluate(() => window.__scenarioProfile!.deferRead());
  await page
    .locator(".user-profile-page")
    .getByRole("button", {
      name: label("desktop.profile.refresh"),
      exact: true,
    })
    .click();
  await page
    .getByRole("button", { name: label("desktop.titlebar.profile_menu") })
    .click();
  await page
    .getByRole("menuitem", {
      name: label("desktop.account.sign_out"),
      exact: true,
    })
    .click();
  await expect(page.locator(".user-profile-page")).toHaveCount(0);
  await page.evaluate(() => window.__scenarioProfile!.releaseRead());
  await expect(page.getByText(privateName, { exact: true })).toHaveCount(0);
});

test("full schema, collapsible sections, sidebar and browser autofill", async ({
  page,
}) => {
  await open(page);
  const profile = page.locator(".user-profile-page");
  await expect(
    profile
      .getByLabel(label("desktop.profile.sections"), { exact: true })
      .locator("option"),
  ).toHaveCount(27);
  await profile
    .getByRole("button", {
      name: label("desktop.profile.collapse_all"),
      exact: true,
    })
    .click();
  await expect(
    profile.getByRole("button", {
      name: label("desktop.profile.edit_field", { field: "Given name" }),
      exact: true,
    }),
  ).not.toBeVisible();
  await profile.getByRole("button", { name: "Identity", exact: true }).click();
  await profile
    .getByRole("button", {
      name: label("desktop.profile.edit_field", { field: "Given name" }),
      exact: true,
    })
    .click();
  await expect(
    page.getByRole("dialog").getByLabel("Given name", { exact: true }),
  ).toHaveAttribute("autocomplete", "given-name");
  await page
    .getByRole("dialog")
    .getByRole("button", { name: label("desktop.profile.cancel"), exact: true })
    .last()
    .click();
  await page
    .locator(".pane-docs")
    .getByRole("button", {
      name: label("desktop.profile.maximize"),
      exact: true,
    })
    .click();
  await expect(profile.getByRole("navigation")).toBeVisible();
  await profile
    .getByRole("navigation")
    .getByRole("button", { name: "Contact and fiscal address", exact: true })
    .click();
  await expect(profile).toContainText("952000000");
  await expect(profile).not.toContainText("Review your saved details");
});

test("Censo checks saved prerequisites and edits the missing identity", async ({
  page,
}) => {
  await open(page);
  await page
    .getByRole("button", {
      name: label("desktop.profile.censo.title"),
      exact: true,
    })
    .click();
  const dialog = page.getByRole("dialog", {
    name: label("desktop.profile.censo.title"),
    exact: true,
  });
  await expect(dialog).toContainText(
    label("auth.sync.requirement.profile_tax_id_required"),
  );
  await expect(
    dialog.getByRole("button", {
      name: label("desktop.profile.censo.pull"),
      exact: true,
    }),
  ).toHaveCount(0);
  await dialog
    .getByRole("button", {
      name: label("desktop.profile.censo.identity"),
      exact: true,
    })
    .click();
  const editor = page.getByRole("dialog", {
    name: "Tax ID (NIF/NIE/CIF)",
    exact: true,
  });
  await editor.getByRole("textbox").fill("X1234567L");
  await editor
    .getByRole("button", { name: label("desktop.profile.save"), exact: true })
    .click();
  await expect(dialog).not.toContainText(
    label("auth.sync.requirement.profile_tax_id_required"),
  );
  await expect(dialog).toContainText(
    label("auth.sync.requirement.auth_method_required"),
  );
  expect(await page.evaluate(() => window.__scenarioCenso!.starts())).toBe(0);
});

test("Censo review preserves manual values and saves only after approval", async ({
  page,
}) => {
  await open(page, "censo-ready");
  const started = Date.now();
  await page
    .getByRole("button", {
      name: label("desktop.profile.censo.title"),
      exact: true,
    })
    .click();
  const dialog = page.getByRole("dialog", {
    name: label("desktop.profile.censo.title"),
    exact: true,
  });
  await dialog
    .getByRole("button", {
      name: label("desktop.profile.censo.pull"),
      exact: true,
    })
    .click();
  await expect(dialog).toContainText("Calle Nueva 1");
  await expect(
    dialog.getByText(label("desktop.profile.censo.preserve"), { exact: true }),
  ).toHaveCount(2);
  expect(await page.evaluate(() => window.__scenarioProfile!.writes())).toBe(0);
  console.log(
    JSON.stringify({
      benchmark: "censo_browser_review",
      elapsed_ms: Date.now() - started,
    }),
  );
  await dialog
    .getByRole("button", {
      name: label("desktop.profile.censo.apply"),
      exact: true,
    })
    .click();
  await expect(dialog).toContainText(label("desktop.profile.censo.done"));
  await dialog
    .getByRole("button", {
      name: label("desktop.profile.censo.return"),
      exact: true,
    })
    .click();
  const profile = page.locator(".user-profile-page");
  await expect(profile).toContainText("1234567UF7613S0001AB");
  await expect(profile).toContainText("Calle Larios 12");
  expect(await page.evaluate(() => window.__scenarioProfile!.writes())).toBe(1);
});

test("an uncertain Censo start is not silently retried", async ({ page }) => {
  await open(page, "censo-uncertain");
  await page
    .getByRole("button", {
      name: label("desktop.profile.censo.title"),
      exact: true,
    })
    .click();
  const dialog = page.getByRole("dialog", {
    name: label("desktop.profile.censo.title"),
    exact: true,
  });
  await dialog
    .getByRole("button", {
      name: label("desktop.profile.censo.pull"),
      exact: true,
    })
    .click();
  await expect(dialog).toContainText(label("desktop.profile.unknown"));
  await expect(
    dialog.getByRole("button", {
      name: label("desktop.profile.censo.pull"),
      exact: true,
    }),
  ).toBeDisabled();
  expect(await page.evaluate(() => window.__scenarioCenso!.starts())).toBe(1);
});

test("saved Cl@ve setup asks specifically for the NIE support number", async ({
  page,
}) => {
  await open(page, "censo-nie");
  await page
    .getByRole("button", {
      name: label("desktop.profile.censo.title"),
      exact: true,
    })
    .click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toContainText(
    label("auth.sync.requirement.nie_support_required"),
  );
  await expect(dialog).not.toContainText(
    label("auth.sync.requirement.profile_tax_id_required"),
  );
  await expect(dialog).not.toContainText(
    label("auth.sync.requirement.auth_method_required"),
  );
  await dialog
    .getByRole("button", {
      name: label("desktop.profile.censo.setup"),
      exact: true,
    })
    .click();
  await expect(
    page.getByRole("dialog", {
      name: label("desktop.agent.aeat_setup_title"),
      exact: true,
    }),
  ).toBeVisible();
});

test("discarding Censo changes does not write profile data", async ({
  page,
}) => {
  await open(page, "censo-ready");
  await page
    .getByRole("button", {
      name: label("desktop.profile.censo.title"),
      exact: true,
    })
    .click();
  const dialog = page.getByRole("dialog");
  await dialog
    .getByRole("button", {
      name: label("desktop.profile.censo.pull"),
      exact: true,
    })
    .click();
  await dialog
    .getByRole("button", {
      name: label("desktop.profile.censo.reject"),
      exact: true,
    })
    .click();
  await expect(dialog).toContainText(label("desktop.profile.censo.stopped"));
  expect(await page.evaluate(() => window.__scenarioProfile!.writes())).toBe(0);
});

test("Censo progress notifications coalesce without starting another pull", async ({
  page,
}) => {
  await open(page, "censo-ready");
  await page
    .getByRole("button", {
      name: label("desktop.profile.censo.title"),
      exact: true,
    })
    .click();
  const dialog = page.getByRole("dialog");
  await dialog
    .getByRole("button", {
      name: label("desktop.profile.censo.pull"),
      exact: true,
    })
    .click();
  await expect(dialog).toContainText("Calle Nueva 1");
  await expect
    .poll(() => page.evaluate(() => window.__scenarioCenso!.statuses()))
    .toBeGreaterThan(0);
  const before = await page.evaluate(() => window.__scenarioCenso!.statuses());
  await page.evaluate(() => window.__scenarioCenso!.burst());
  await expect
    .poll(() => page.evaluate(() => window.__scenarioCenso!.statuses()))
    .toBe(before + 2);
  expect(await page.evaluate(() => window.__scenarioCenso!.starts())).toBe(1);
  await expect(
    dialog.getByRole("button", {
      name: label("desktop.profile.censo.apply"),
      exact: true,
    }),
  ).toBeEnabled();
});

test("a failed pending profile read leaves loading and allows a retry", async ({
  page,
}) => {
  await open(page);
  const profile = page.locator(".user-profile-page");
  const refresh = profile.getByRole("button", {
    name: label("desktop.profile.refresh"),
    exact: true,
  });
  await page.evaluate(() => window.__scenarioProfile!.deferRead());
  await refresh.click();
  await expect(profile).toContainText(label("desktop.profile.loading"));
  await page.evaluate(() => window.__scenarioProfile!.rejectRead());
  await expect(profile.getByRole("alert")).toContainText(
    label("desktop.profile.unavailable"),
  );
  await expect(profile).not.toContainText(label("desktop.profile.loading"));
  await expect(refresh).toBeEnabled();
  await refresh.click();
  await expect(profile).toContainText("Soler Vidal");
  await expect(profile.getByRole("alert")).toHaveCount(0);
  await expect(profile).not.toContainText(label("desktop.profile.loading"));
});
