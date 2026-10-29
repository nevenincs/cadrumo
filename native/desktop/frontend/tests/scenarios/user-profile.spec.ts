import { readFileSync } from "node:fs";
import { expect, test, type Locator, type Page } from "@playwright/test";
import { label } from "../support/strings";
import { SCENARIO_PASSWORD } from "../../src/dev/fixtures/password";
import type { UserProfile } from "../../src/shell/userProfile";

/** The titles of the sections the profile schema declares, in order, as the
 * application projected them into the generated fixture. */
const declaredSectionTitles = () =>
  (
    JSON.parse(
      readFileSync(
        new URL("../../src/dev/fixtures/userProfile.json", import.meta.url),
        "utf8",
      ),
    ) as { en: UserProfile }
  ).en.sections.map((section) => section.title);

async function open(page: Page, scenario = "user-profile", language = "en") {
  await page.goto(
    `/scenarios.html?scenario=${scenario}&latency=0&bar=off&lang=${language}`,
  );
  await page
    .locator(".rail")
    .getByRole("button", {
      name: label("desktop.profile.title", {}, language),
      exact: true,
    })
    .click();
  await expect(page.locator(".user-profile-page")).toContainText("Soler Vidal");
  return page.locator(".user-profile-page");
}

const band = (page: Page) =>
  page.getByRole("region", {
    name: label("desktop.profile.censo.band"),
    exact: true,
  });
const row = (profile: Locator, path: string) =>
  profile.locator(`[data-nav="${path}"]`);
const editButton = (profile: Locator, field: string) =>
  profile.getByRole("button", {
    name: label("desktop.profile.edit_field", { field }),
    exact: true,
  });
const save = (dialog: Locator) =>
  dialog.getByRole("button", {
    name: label("desktop.profile.save"),
    exact: true,
  });
const aeatEditor = (page: Page) =>
  page.getByRole("dialog", {
    name: label("desktop.profile.action.aeat_access"),
    exact: true,
  });
/** Chooses an item of the profile's actions menu. */
async function profileAction(page: Page, key: string) {
  await page
    .locator(".user-profile-page")
    .getByRole("button", {
      name: label("desktop.profile.action.menu"),
      exact: true,
    })
    .click();
  await page.getByRole("menuitem", { name: label(key), exact: true }).click();
}

/** Opens the compact view's options and chooses one of them. */
async function viewOption(page: Page, key: string) {
  await page
    .locator(".user-profile-page")
    .getByRole("button", { name: label("desktop.profile.view.options") })
    .click();
  await page
    .getByRole("menuitemradio", { name: label(key), exact: true })
    .click();
  await page.keyboard.press("Escape");
}

async function goToSection(page: Page, title: string) {
  await page
    .locator(".user-profile-page")
    .getByRole("button", {
      name: label("desktop.profile.sections"),
      exact: true,
    })
    .click();
  await page.getByRole("menuitem", { name: title }).click();
}

for (const language of ["en", "es", "ca", "hu"]) {
  test(`the Censo band and summary render clean Unicode in ${language}`, async ({
    page,
  }) => {
    const profile = await open(page, "censo-ready", language);
    const region = page.getByRole("region", {
      name: label("desktop.profile.censo.band", {}, language),
      exact: true,
    });
    await expect(
      region.getByRole("button", {
        name: label("desktop.profile.censo.pull", {}, language),
        exact: true,
      }),
    ).toBeEnabled();
    await expect(profile.locator("header")).toContainText(
      label("desktop.profile.required_missing", { count: 2 }, language),
    );
    await expect(profile).not.toContainText(/[ÃÂ�]|â€|Å[‘’±]/);
  });
}

test("the summary names the taxpayer and filters to what is required and missing", async ({
  page,
}) => {
  const profile = await open(page);
  const header = profile.locator("header");
  await expect(header.getByRole("heading", { level: 3 })).toHaveText(
    "Ana Soler Vidal",
  );
  await expect(header).toContainText("ana.soler@example.test");
  await expect(header).toContainText("Calle Larios 12, 2 A, Málaga · 29005");
  await expect(header).toContainText(label("desktop.profile.missing"));
  await header
    .getByRole("button", {
      name: label("desktop.profile.required_missing", { count: 3 }),
    })
    .click();
  await expect(row(profile, "identity.tax_id")).toBeVisible();
  await expect(row(profile, "identity.name")).toHaveCount(0);
  await expect(
    profile.getByText(label("desktop.profile.view.results", { count: 3 })),
  ).toBeVisible();
  // Required details carry a star and are never told apart by colour alone.
  await expect(
    row(profile, "identity.tax_id").locator("[data-part=label]"),
  ).toContainText("*");
  await expect(row(profile, "identity.tax_id")).toHaveAttribute(
    "aria-label",
    `Tax ID (NIF/NIE/CIF) (${label("desktop.profile.required")}): ${label("desktop.profile.missing")}`,
  );
});

test("search, show, group and sort arrange the saved details", async ({
  page,
}) => {
  const profile = await open(page);
  await profile.getByRole("searchbox").fill("malaga");
  await expect(row(profile, "contact.fiscal_address")).toBeVisible();
  await expect(profile.getByRole("region", { name: /^Identity/ })).toHaveCount(
    0,
  );
  await profile.getByRole("searchbox").press("Escape");
  await expect(profile.getByRole("searchbox")).toHaveValue("");
  await viewOption(page, "desktop.profile.view.show_unset");
  await expect(row(profile, "identity.tax_id")).toBeVisible();
  await expect(row(profile, "identity.name")).toHaveCount(0);
  await viewOption(page, "desktop.profile.view.show_all");
  await viewOption(page, "desktop.profile.view.group_status");
  const required = profile.getByRole("region", {
    name: new RegExp(`^${label("desktop.profile.view.status_required")}`),
  });
  await expect(required.locator("[data-kind='row']")).toHaveCount(3);
  // Grouped by status, each detail names its section.
  await expect(required).toContainText("Tax residence and jurisdiction");
  await viewOption(page, "desktop.profile.view.group_none");
  await viewOption(page, "desktop.profile.view.sort_missing");
  const first = profile.locator("[data-kind='row']").first();
  await expect(first).toHaveAttribute("data-nav", "identity.tax_id");
  await profile.getByRole("searchbox").fill("no matching detail");
  await expect(profile).toContainText(label("desktop.profile.empty"));
});

test("edits and repeatable entries use saved data", async ({ page }) => {
  const profile = await open(page);
  await editButton(profile, "Given name").click();
  const dialog = page.getByRole("dialog", { name: "Given name", exact: true });
  await dialog.getByLabel("Given name", { exact: true }).fill("Ana Updated");
  await save(dialog).click();
  await expect(dialog).toHaveCount(0);
  await expect(profile.locator("header")).toContainText("Ana Updated");
  await goToSection(page, "Business activities");
  const activities = profile.getByRole("region", {
    name: "Business activities",
  });
  await activities
    .getByRole("button", { name: label("desktop.profile.add"), exact: true })
    .click();
  const entry = page.getByRole("dialog", {
    name: "Business activities",
    exact: true,
  });
  await entry
    .getByRole("textbox", { name: "Activity description", exact: true })
    .fill("Partner Two");
  await save(entry).click();
  await expect(activities).toContainText("Partner Two");
  await expect(activities).toContainText(
    label("desktop.profile.entries_count", { count: 1 }),
  );
});

test("details open for editing by double click, Enter, F2 and the hover button", async ({
  page,
}) => {
  const profile = await open(page);
  const given = row(profile, "identity.name");
  const dialog = page.getByRole("dialog", { name: "Given name", exact: true });
  for (const target of ["Given name", "Ana"]) {
    await given.getByText(target, { exact: true }).dblclick();
    await expect(dialog.getByLabel("Given name", { exact: true })).toHaveValue(
      "Ana",
    );
    await page.keyboard.press("Escape");
    await expect(dialog).toHaveCount(0);
  }
  for (const key of ["Enter", "F2"]) {
    await given.focus();
    await page.keyboard.press(key);
    await expect(dialog).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(given).toBeFocused();
  }
  // The edit button is drawn only on hover or focus.
  const button = editButton(profile, "Given name");
  await page.mouse.move(0, 0);
  await profile.getByRole("searchbox").focus();
  await expect(button).toHaveCSS("opacity", "0");
  await given.hover();
  await expect(button).toHaveCSS("opacity", "1");
  await button.click();
  await expect(dialog).toBeVisible();
  await page.keyboard.press("Escape");
  // The sign-in method is set in the window's AEAT editor, not a TUI.
  await row(profile, "auth.provider").focus();
  await page.keyboard.press("Enter");
  await expect(aeatEditor(page)).toBeVisible();
});

test("the keyboard walks details and sections, and finds search and help", async ({
  page,
}) => {
  const profile = await open(page);
  await row(profile, "identity.tax_id").focus();
  await page.keyboard.press("ArrowDown");
  await expect(row(profile, "identity.name")).toBeFocused();
  await page.keyboard.press("k");
  await expect(row(profile, "identity.tax_id")).toBeFocused();
  await page.keyboard.press("]");
  const operator = profile.locator("[data-kind='head']").nth(1);
  await expect(operator).toBeFocused();
  await page.keyboard.press("ArrowLeft");
  await expect(operator).toHaveAttribute("aria-expanded", "false");
  await page.keyboard.press("ArrowRight");
  await expect(operator).toHaveAttribute("aria-expanded", "true");
  await page.keyboard.press("[");
  await expect(profile.locator("[data-kind='head']").first()).toBeFocused();
  await page.keyboard.press("End");
  await expect(profile.locator("[data-nav]").last()).toBeFocused();
  // One stop in the tab order: the detail last focused.
  await expect(profile.locator("[data-nav][tabindex='0']")).toHaveCount(1);
  await page.keyboard.press("/");
  await expect(profile.getByRole("searchbox")).toBeFocused();
  await row(profile, "identity.name").focus();
  await page.keyboard.press("?");
  await expect(
    page.getByRole("dialog", {
      name: label("desktop.profile.keys.title"),
      exact: true,
    }),
  ).toBeVisible();
});

test("a detail's context menu offers its own actions, by pointer and by key", async ({
  page,
}) => {
  const profile = await open(page);
  await row(profile, "identity.email").click({ button: "right" });
  const menu = page.getByRole("menu");
  const edit = menu.getByRole("menuitem", {
    name: label("desktop.profile.edit_field", { field: "Contact email" }),
  });
  await expect(edit).toBeVisible();
  // Each shows the key the page runs it by: Copy's is pressed below, and
  // Enter's in the test of the details' keys.
  const mac = process.platform === "darwin";
  await expect(edit.locator("kbd")).toHaveText("Enter");
  const copy = menu.getByRole("menuitem", {
    name: label("desktop.profile.action.copy", { field: "Contact email" }),
  });
  await expect(copy.locator("kbd")).toHaveText(
    mac ? ["⌘", "C"] : ["Ctrl", "C"],
  );
  // Clearing has no key of the page's own, so it shows none.
  await expect(
    menu
      .getByRole("menuitem", {
        name: label("desktop.profile.action.clear", { field: "Contact email" }),
      })
      .locator("kbd"),
  ).toHaveCount(0);
  await copy.click();
  await expect(
    page.getByRole("status").getByText(label("desktop.toast.copied")),
  ).toBeVisible();
  // The value itself, through the host's clipboard.
  expect(await page.evaluate(() => window.__scenarioHostCalls ?? [])).toContain(
    `writeClipboard ${"ana.soler@example.test".length} characters`,
  );
  // The key the menu shows copies it again.
  const copies = () =>
    page.evaluate(
      () =>
        (window.__scenarioHostCalls ?? []).filter((call) =>
          call.startsWith("writeClipboard"),
        ).length,
    );
  const copied = await copies();
  await row(profile, "identity.email").focus();
  await page.keyboard.press(mac ? "Meta+KeyC" : "Control+KeyC");
  await expect.poll(copies).toBe(copied + 1);
  // The menu key opens it on the focused detail; a missing value cannot be copied.
  await row(profile, "identity.tax_id").focus();
  await page.keyboard.press("Shift+F10");
  await expect(
    page.getByRole("menuitem", {
      name: label("desktop.profile.action.copy", {
        field: "Tax ID (NIF/NIE/CIF)",
      }),
    }),
  ).toBeDisabled();
  await page.keyboard.press("Escape");
  await expect(row(profile, "identity.tax_id")).toBeFocused();
});

test("the actions menu leads each action with its icon and shows the chord of the key that runs it", async ({
  page,
}) => {
  await open(page);
  await page
    .locator(".user-profile-page")
    .getByRole("button", {
      name: label("desktop.profile.action.menu"),
      exact: true,
    })
    .click();
  const menu = page.getByRole("menu");
  const item = (key: string) =>
    menu.getByRole("menuitem", { name: label(key), exact: true });
  const full = item("desktop.profile.maximize");
  await expect(full.locator("[data-icon=maximize]")).toHaveCount(1);
  // The window's own chord for full screen, in the platform's notation.
  await expect(full.locator("kbd")).toHaveText(
    process.platform === "darwin" ? ["⇧", "⌘", "M"] : ["Ctrl", "Shift", "M"],
  );
  // Searching and the key sheet have keys of the page's own, typed rather than
  // placed, as "/" and "?" sit elsewhere on other layouts; the registry binds
  // neither. The page's key test presses both.
  const search = item("desktop.profile.search");
  await expect(search.locator("[data-icon=search]")).toHaveCount(1);
  await expect(search.locator("kbd")).toHaveText("/");
  await expect(item("desktop.profile.keys.title").locator("kbd")).toHaveText(
    "?",
  );
  // Collapsing every group has no key.
  await expect(
    item("desktop.profile.action.collapse").locator("kbd"),
  ).toHaveCount(0);
});

test("the palette leads with the focused detail and reaches every section", async ({
  page,
}) => {
  const profile = await open(page);
  await row(profile, "identity.email").focus();
  await page.keyboard.press("Control+k");
  const palette = page.getByRole("dialog", {
    name: label("desktop.palette.label"),
  });
  const results = palette.getByRole("listbox");
  await expect(results.getByRole("option").first()).toHaveText(
    label("desktop.profile.edit_field", { field: "Contact email" }),
  );
  await expect(
    results.getByRole("option", {
      name: label("desktop.profile.password.title"),
    }),
  ).toBeVisible();
  // A way to each section is listed only for a query.
  await expect(
    palette.getByRole("option", {
      name: label("desktop.profile.action.go_to", {
        section: "Contact and fiscal address",
      }),
    }),
  ).toHaveCount(0);
  // The palette's search has focus.
  await page.keyboard.type("profile section contact");
  await palette
    .getByRole("option", {
      name: label("desktop.profile.action.go_to", {
        section: "Contact and fiscal address",
      }),
    })
    .click();
  await expect(profile.locator('[data-nav="head:contact"]')).toBeFocused();
});

test("external changes refresh once, preserve drafts and block stale saves", async ({
  page,
}) => {
  const profile = await open(page);
  await editButton(profile, "Given name").click();
  const dialog = page.getByRole("dialog", { name: "Given name", exact: true });
  await dialog.getByLabel("Given name", { exact: true }).fill("Unsaved draft");
  await page.evaluate(() =>
    window.__scenarioProfile!.update("Changed by the agent"),
  );
  await expect(profile).toContainText("Changed by the agent");
  await expect(dialog.getByLabel("Given name", { exact: true })).toHaveValue(
    "Unsaved draft",
  );
  await expect(save(dialog)).toBeDisabled();
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
  const profile = await open(page);
  await editButton(profile, "Given name").click();
  const dialog = page.getByRole("dialog", { name: "Given name", exact: true });
  await dialog
    .getByLabel("Given name", { exact: true })
    .fill("Keep this draft");
  const before = await page.evaluate(() => window.__scenarioProfile!.reads());
  await page.evaluate(() => window.__scenarioProfile!.conflict());
  await save(dialog).click();
  await expect
    .poll(() => page.evaluate(() => window.__scenarioProfile!.reads()))
    .toBe(before + 1);
  await expect(dialog.getByLabel("Given name", { exact: true })).toHaveValue(
    "Keep this draft",
  );
  await expect(save(dialog)).toBeDisabled();
  expect(await page.evaluate(() => window.__scenarioProfile!.writes())).toBe(1);
});

test("repeatable entries can be updated and removed with confirmation", async ({
  page,
}) => {
  const profile = await open(page);
  await goToSection(page, "Business activities");
  const activities = profile.getByRole("region", {
    name: "Business activities",
  });
  await expect(activities).toContainText(label("desktop.profile.entries_none"));
  await activities
    .getByRole("button", { name: label("desktop.profile.add"), exact: true })
    .click();
  const dialog = page.getByRole("dialog", {
    name: "Business activities",
    exact: true,
  });
  const description = dialog.getByRole("textbox", {
    name: "Activity description",
    exact: true,
  });
  await description.fill("First Partner");
  await save(dialog).click();
  await expect(dialog).toHaveCount(0);
  await activities
    .getByRole("button", {
      name: label("desktop.profile.action.edit_entry"),
      exact: true,
    })
    .click();
  await expect(description).toHaveValue("First Partner");
  await description.fill("Updated Partner");
  await save(dialog).click();
  await expect(dialog).toHaveCount(0);
  await expect(activities).toContainText("Updated Partner");
  const remove = activities.getByRole("button", {
    name: label("desktop.profile.remove"),
    exact: true,
  });
  await remove.click();
  await expect(dialog).toContainText(label("desktop.profile.remove_help"));
  await dialog
    .getByRole("button", { name: label("desktop.profile.cancel"), exact: true })
    .last()
    .click();
  await expect(activities).toContainText("Updated Partner");
  // Delete on a focused entry asks the same question.
  await activities.locator("[data-kind='row']").focus();
  await page.keyboard.press("Delete");
  await dialog
    .getByRole("button", { name: label("desktop.profile.remove"), exact: true })
    .click();
  await expect(dialog).toHaveCount(0);
  await expect(activities).not.toContainText("Updated Partner");
  await expect(activities).toContainText(label("desktop.profile.entries_none"));
});

test("a refused save keeps the draft without claiming success", async ({
  page,
}) => {
  const profile = await open(page);
  await editButton(profile, "Given name").click();
  const dialog = page.getByRole("dialog", { name: "Given name", exact: true });
  await dialog.getByLabel("Given name", { exact: true }).fill("Keep my draft");
  await page.evaluate(() => window.__scenarioProfile!.refuse());
  await save(dialog).click();
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
  const profile = await open(page);
  await editButton(profile, "Given name").click();
  const dialog = page.getByRole("dialog", { name: "Given name", exact: true });
  await dialog
    .getByLabel("Given name", { exact: true })
    .fill("Recovered draft");
  await page.evaluate(() => window.__scenarioProfile!.uncertain());
  await save(dialog).click();
  await expect(dialog.getByRole("alert")).toContainText(
    label("desktop.profile.unknown"),
  );
  await expect(save(dialog)).toBeDisabled();
  await dialog
    .getByRole("button", {
      name: label("desktop.profile.refresh"),
      exact: true,
    })
    .click();
  await expect(save(dialog)).toBeEnabled();
  await expect(dialog.getByLabel("Given name", { exact: true })).toHaveValue(
    "Recovered draft",
  );
  await save(dialog).click();
  await expect(dialog).toHaveCount(0);
  await expect(profile).toContainText("Recovered draft");
});

test("signing out hides private data even when an old read completes later", async ({
  page,
}) => {
  const profile = await open(page);
  // The account picker may retain its public profile label after sign-out;
  // use a distinct private field value to detect disclosure from an old read.
  const privateName = "Private taxpayer detail";
  await page.evaluate(
    (name) => window.__scenarioProfile!.update(name),
    privateName,
  );
  await expect(profile).toContainText(privateName);
  await page.evaluate(() => window.__scenarioProfile!.deferRead());
  await profileAction(page, "desktop.profile.action.refresh");
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

test("full schema, collapsible sections, section index and browser autofill", async ({
  page,
}) => {
  const profile = await open(page);
  await profile
    .getByRole("button", {
      name: label("desktop.profile.sections"),
      exact: true,
    })
    .click();
  await expect(page.getByRole("menuitem")).toContainText(
    declaredSectionTitles(),
  );
  await page.keyboard.press("Escape");
  await profile
    .getByRole("button", {
      name: label("desktop.profile.action.collapse"),
      exact: true,
    })
    .click();
  await expect(row(profile, "identity.name")).toBeHidden();
  await profile.locator('[data-nav="head:identity"]').click();
  await editButton(profile, "Given name").click();
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
  const index = profile.getByRole("navigation", {
    name: label("desktop.profile.sections"),
  });
  await expect(index).toBeVisible();
  // Full screen offers its options side by side.
  await expect(
    profile.getByRole("radiogroup", {
      name: label("desktop.profile.view.show"),
    }),
  ).toBeVisible();
  await index
    .getByRole("button", { name: "Contact and fiscal address" })
    .click();
  await expect(row(profile, "contact.contact_person_phone")).toBeInViewport();
  await expect(profile).toContainText("952000000");
});

test("Censo checks saved prerequisites and edits the missing identity", async ({
  page,
}) => {
  await open(page);
  const region = band(page);
  await expect(region).toContainText(
    label("auth.sync.requirement.profile_tax_id_required"),
  );
  await expect(
    region.getByRole("button", {
      name: label("desktop.profile.censo.pull"),
      exact: true,
    }),
  ).toHaveCount(0);
  await region
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
  await save(editor).click();
  await expect(region).not.toContainText(
    label("auth.sync.requirement.profile_tax_id_required"),
  );
  await expect(region).toContainText(
    label("auth.sync.requirement.auth_method_required"),
  );
  expect(await page.evaluate(() => window.__scenarioCenso!.starts())).toBe(0);
});

test("a Censo review is shown on the details it changes and saves only after approval", async ({
  page,
}) => {
  const profile = await open(page, "censo-ready");
  const started = Date.now();
  const region = band(page);
  await region
    .getByRole("button", {
      name: label("desktop.profile.censo.pull"),
      exact: true,
    })
    .click();
  await region
    .getByRole("button", {
      name: label("desktop.profile.censo.review_count", { count: 3 }),
    })
    .click();
  const address = row(profile, "contact.fiscal_address");
  await expect(address).toBeFocused();
  await expect(address).toContainText("Calle Nueva 1");
  await expect(address).toContainText(label("desktop.profile.censo.preserve"));
  await expect(
    profile.getByText(label("desktop.profile.censo.preserve"), { exact: true }),
  ).toHaveCount(2);
  const cadastral = row(profile, "contact.fiscal_address_cadastral_reference");
  await expect(cadastral).toContainText(label("desktop.profile.censo.adopt"));
  expect(await page.evaluate(() => window.__scenarioProfile!.writes())).toBe(0);
  console.log(
    JSON.stringify({
      benchmark: "censo_browser_review",
      elapsed_ms: Date.now() - started,
    }),
  );
  await region
    .getByRole("button", {
      name: label("desktop.profile.censo.apply"),
      exact: true,
    })
    .click();
  await expect(region).toContainText(label("desktop.profile.censo.done"));
  await expect(cadastral).toContainText("1234567UF7613S0001AB");
  await expect(
    cadastral.getByTitle(label("desktop.profile.censo.source")),
  ).toBeVisible();
  await expect(address).toContainText("Calle Larios 12");
  await expect(address).not.toContainText("Calle Nueva 1");
  expect(await page.evaluate(() => window.__scenarioProfile!.writes())).toBe(1);
  await region
    .getByRole("button", {
      name: label("desktop.profile.dismiss"),
      exact: true,
    })
    .click();
  await expect(
    region.getByRole("button", {
      name: label("desktop.profile.censo.pull"),
      exact: true,
    }),
  ).toBeEnabled();
});

test("an uncertain Censo start is not silently retried", async ({ page }) => {
  await open(page, "censo-uncertain");
  const region = band(page);
  const pull = region.getByRole("button", {
    name: label("desktop.profile.censo.pull"),
    exact: true,
  });
  await pull.click();
  await expect(region).toContainText(
    label("desktop.profile.censo.unknown_start"),
  );
  await region
    .getByRole("button", {
      name: label("desktop.profile.refresh"),
      exact: true,
    })
    .click();
  await expect(region).toContainText(
    label("desktop.profile.censo.unknown_start"),
  );
  await expect(pull).toHaveCount(0);
  expect(await page.evaluate(() => window.__scenarioCenso!.starts())).toBe(1);
});

test("an initially unknown status recovers the admitted operation", async ({
  page,
}) => {
  await open(page, "censo-initial-unknown");
  const region = band(page);
  await region
    .getByRole("button", {
      name: label("desktop.profile.censo.pull"),
      exact: true,
    })
    .click();
  await expect(region).toContainText(label("desktop.profile.censo.unknown"));
  await page.evaluate(() => window.__scenarioCenso!.releaseStatus());
  await expect(region).toContainText(
    label("desktop.profile.censo.review_count", { count: 3 }),
  );
  expect(await page.evaluate(() => window.__scenarioCenso!.starts())).toBe(1);
});

test("a late readiness check does not erase a profile refusal", async ({
  page,
}) => {
  await open(page, "censo-refused");
  const region = band(page);
  const pull = region.getByRole("button", {
    name: label("desktop.profile.censo.pull"),
    exact: true,
  });
  await pull.click();
  await expect(region).toContainText(
    label("desktop.profile.censo.profile_mismatch"),
  );
  await page.evaluate(() => window.__scenarioCenso!.holdReadiness());
  await region
    .getByRole("button", {
      name: label("desktop.profile.refresh"),
      exact: true,
    })
    .click();
  await pull.click();
  await expect(region).toContainText(
    label("desktop.profile.censo.profile_mismatch"),
  );
  await page.evaluate(() => window.__scenarioCenso!.releaseReadiness());
  await expect
    .poll(() => page.evaluate(() => window.__scenarioCenso!.readinessChecks()))
    .toBe(2);
  await expect(region).toContainText(
    label("desktop.profile.censo.profile_mismatch"),
  );
  expect(await page.evaluate(() => window.__scenarioCenso!.starts())).toBe(2);
});

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

test("the profile page reads a pull it was left from before it offers another", async ({
  page,
}) => {
  await open(page, "censo-ready");
  const region = band(page);
  const pull = region.getByRole("button", {
    name: label("desktop.profile.censo.pull"),
    exact: true,
  });
  const review = region.getByRole("button", {
    name: label("desktop.profile.censo.review_count", { count: 3 }),
  });
  await pull.click();
  await expect(review).toBeVisible();
  const rail = page.locator(".rail");
  await rail
    .getByRole("button", { name: label("desktop.calendar.title"), exact: true })
    .click();
  await page
    .getByRole("button", { name: label("desktop.navigation.leave.discard") })
    .click();
  await expect(page.locator(".user-profile-page")).not.toBeVisible();
  // Back on the page while the host's answer is on its way: nothing can be
  // started until it comes.
  await page.evaluate(() => window.__scenarioCenso!.holdStatus());
  await rail
    .getByRole("button", { name: label("desktop.profile.title"), exact: true })
    .click();
  await expect(pull).toBeDisabled();
  expect(await page.evaluate(() => window.__scenarioCenso!.starts())).toBe(1);
  await page.evaluate(() => window.__scenarioCenso!.releaseStatus());
  await expect(review).toBeVisible();
  await expect(pull).toHaveCount(0);
  expect(await page.evaluate(() => window.__scenarioCenso!.starts())).toBe(1);
  expect(await page.evaluate(() => window.__scenarioCenso!.pulls())).toBe(1);
});

test("discarding Censo changes does not write profile data", async ({
  page,
}) => {
  await open(page, "censo-ready");
  const region = band(page);
  await region
    .getByRole("button", {
      name: label("desktop.profile.censo.pull"),
      exact: true,
    })
    .click();
  await region
    .getByRole("button", {
      name: label("desktop.profile.censo.reject"),
      exact: true,
    })
    .click();
  await expect(region).toContainText(label("desktop.profile.censo.stopped"));
  await expect(page.locator(".user-profile-page")).not.toContainText(
    "Calle Nueva 1",
  );
  expect(await page.evaluate(() => window.__scenarioProfile!.writes())).toBe(0);
});

test("Censo progress notifications coalesce without starting another pull", async ({
  page,
}) => {
  await open(page, "censo-ready");
  const region = band(page);
  await region
    .getByRole("button", {
      name: label("desktop.profile.censo.pull"),
      exact: true,
    })
    .click();
  await expect(page.locator(".user-profile-page")).toContainText(
    "Calle Nueva 1",
  );
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
    region.getByRole("button", {
      name: label("desktop.profile.censo.apply"),
      exact: true,
    }),
  ).toBeEnabled();
});

test("the password changes only with the current one, and an unconfirmed change is not retried", async ({
  page,
}) => {
  await open(page);
  await profileAction(page, "desktop.profile.password.title");
  const dialog = page.getByRole("dialog", {
    name: label("desktop.profile.password.title"),
    exact: true,
  });
  const fill = async (current: string, next: string, again = next) => {
    await dialog
      .getByLabel(label("desktop.profile.password.current"), { exact: true })
      .fill(current);
    await dialog
      .getByLabel(label("desktop.profile.password.new"), { exact: true })
      .fill(next);
    await dialog
      .getByLabel(label("desktop.profile.password.again"), { exact: true })
      .fill(again);
    await dialog
      .getByRole("button", {
        name: label("desktop.profile.password.title"),
        exact: true,
      })
      .click();
  };
  const changes = () =>
    page.evaluate(() => window.__scenarioPassword!.changes());
  await fill(SCENARIO_PASSWORD, "a new password", "another password");
  await expect(dialog.getByRole("alert")).toHaveText(
    label("desktop.account.create.mismatch"),
  );
  await fill(SCENARIO_PASSWORD, "short");
  await expect(dialog.getByRole("alert")).toHaveText(
    label("desktop.account.create.password_short", { min: 8 }),
  );
  expect(await changes()).toBe(0);
  await fill("not the password", "a new password");
  await expect(dialog.getByRole("alert")).toHaveText(
    label("desktop.profile.password.rejected"),
  );
  // Nothing typed is kept once it has been sent.
  await expect(
    dialog.getByLabel(label("desktop.profile.password.current"), {
      exact: true,
    }),
  ).toHaveValue("");
  await fill(SCENARIO_PASSWORD, "a new password");
  await expect(dialog).toHaveCount(0);
  await expect(
    page
      .getByRole("status")
      .getByText(label("desktop.profile.password.changed")),
  ).toBeVisible();
  expect(await changes()).toBe(2);
  await page.evaluate(() => window.__scenarioPassword!.uncertain());
  await profileAction(page, "desktop.profile.password.title");
  await fill(SCENARIO_PASSWORD, "a newer password");
  await expect(dialog.getByRole("alert")).toHaveText(
    label("desktop.profile.password.unknown"),
  );
  await expect(
    dialog.getByRole("button", {
      name: label("desktop.profile.password.title"),
      exact: true,
    }),
  ).toBeDisabled();
  expect(await changes()).toBe(3);
});

test("a save waits for a pending refresh and submits the unchanged draft once", async ({
  page,
}) => {
  const profile = await open(page);
  await editButton(profile, "Given name").click();
  const dialog = page.getByRole("dialog", { name: "Given name", exact: true });
  await dialog.getByLabel("Given name", { exact: true }).fill("Queued draft");
  await page.evaluate(() => {
    window.__scenarioProfile!.deferRead();
    window.__scenarioProfile!.burst();
  });
  await expect(profile).toContainText(label("desktop.profile.loading"));
  await save(dialog).click();
  await expect(
    dialog.getByRole("button", {
      name: label("desktop.profile.saving"),
      exact: true,
    }),
  ).toBeDisabled();
  expect(await page.evaluate(() => window.__scenarioProfile!.writes())).toBe(0);
  await page.evaluate(() => window.__scenarioProfile!.releaseRead());
  await expect(dialog).toHaveCount(0);
  await expect(profile).toContainText("Queued draft");
  expect(await page.evaluate(() => window.__scenarioProfile!.writes())).toBe(1);
});

test("a committed save stays busy through readback and coalesced observations", async ({
  page,
}) => {
  const profile = await open(page);
  await editButton(profile, "Given name").click();
  const dialog = page.getByRole("dialog", { name: "Given name", exact: true });
  const input = dialog.getByLabel("Given name", { exact: true });
  await input.fill("Saved after readback");
  const before = await page.evaluate(() => window.__scenarioProfile!.reads());
  await page.evaluate(() => window.__scenarioProfile!.deferRead());
  await save(dialog).click();
  await expect
    .poll(() => page.evaluate(() => window.__scenarioProfile!.reads()))
    .toBe(before + 1);
  expect(await page.evaluate(() => window.__scenarioProfile!.writes())).toBe(1);
  await expect(
    dialog.getByRole("button", {
      name: label("desktop.profile.saving"),
      exact: true,
    }),
  ).toBeDisabled();
  await expect(input).toBeDisabled();
  await expect(
    dialog.getByRole("button", {
      name: label("desktop.profile.cancel"),
      exact: true,
    }),
  ).toBeDisabled();
  await page.keyboard.press("Escape");
  await expect(dialog).toBeVisible();
  // Even an additional form submission cannot replay the committed edit.
  await dialog.locator("form").evaluate((form) => {
    if (form instanceof HTMLFormElement) form.requestSubmit();
  });
  await page.evaluate(() => window.__scenarioProfile!.burst());
  expect(await page.evaluate(() => window.__scenarioProfile!.writes())).toBe(1);
  expect(await page.evaluate(() => window.__scenarioProfile!.reads())).toBe(
    before + 1,
  );
  await page.evaluate(() => {
    window.__scenarioProfile!.releaseRead();
    window.__scenarioProfile!.deferRead();
  });
  await expect
    .poll(() => page.evaluate(() => window.__scenarioProfile!.reads()))
    .toBe(before + 2);
  await expect(input).toBeDisabled();
  await expect(dialog).toBeVisible();
  await page.evaluate(() => window.__scenarioProfile!.releaseRead());
  await expect(dialog).toHaveCount(0);
  await expect(profile.locator("header")).toContainText("Saved after readback");
  expect(await page.evaluate(() => window.__scenarioProfile!.writes())).toBe(1);
  await editButton(profile, "Given name").click();
  await expect(input).toBeEnabled();
});

test("a committed save with failed readback unlocks and refreshes without replay", async ({
  page,
}) => {
  const profile = await open(page);
  await editButton(profile, "Given name").click();
  const dialog = page.getByRole("dialog", { name: "Given name", exact: true });
  await dialog.getByLabel("Given name", { exact: true }).fill("Already saved");
  const before = await page.evaluate(() => window.__scenarioProfile!.reads());
  await page.evaluate(() => window.__scenarioProfile!.deferRead());
  await save(dialog).click();
  await expect
    .poll(() => page.evaluate(() => window.__scenarioProfile!.reads()))
    .toBe(before + 1);
  await expect(
    dialog.getByRole("button", {
      name: label("desktop.profile.saving"),
      exact: true,
    }),
  ).toBeDisabled();
  await page.evaluate(() => window.__scenarioProfile!.rejectRead());
  await expect(dialog).toHaveCount(0);
  await expect(profile.getByRole("alert")).toContainText(
    label("desktop.profile.saved_unread"),
  );
  await expect(profile).not.toContainText(label("desktop.profile.loading"));
  expect(await page.evaluate(() => window.__scenarioProfile!.writes())).toBe(1);
  const refresh = profile.getByRole("button", {
    name: label("desktop.profile.refresh"),
    exact: true,
  });
  await expect(refresh).toBeEnabled();
  await refresh.click();
  await expect(profile.locator("header")).toContainText("Already saved");
  await expect(profile.getByRole("alert")).toHaveCount(0);
  expect(await page.evaluate(() => window.__scenarioProfile!.writes())).toBe(1);
});

test("a failed pending profile read leaves loading and allows a retry", async ({
  page,
}) => {
  const profile = await open(page);
  await page.evaluate(() => window.__scenarioProfile!.deferRead());
  await profileAction(page, "desktop.profile.action.refresh");
  await expect(profile).toContainText(label("desktop.profile.loading"));
  await page.evaluate(() => window.__scenarioProfile!.rejectRead());
  await expect(profile.getByRole("alert")).toContainText(
    label("desktop.profile.unavailable"),
  );
  await expect(profile).not.toContainText(label("desktop.profile.loading"));
  await expect(profile).toContainText("Soler Vidal");
  const refresh = profile.getByRole("button", {
    name: label("desktop.profile.refresh"),
    exact: true,
  });
  await expect(refresh).toBeEnabled();
  await refresh.click();
  await expect(profile).toContainText("Soler Vidal");
  await expect(profile.getByRole("alert")).toHaveCount(0);
  await expect(profile).not.toContainText(label("desktop.profile.loading"));
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
  await expect(secret).toHaveAttribute("autocomplete", "off");
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
