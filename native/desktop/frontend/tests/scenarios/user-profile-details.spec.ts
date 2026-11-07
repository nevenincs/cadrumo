import { expect, test, type Page } from "@playwright/test";
import { label } from "../support/strings";
import {
  PROFILE_NAME,
  PROFILE_SECTION_TITLES,
  profileStated,
} from "../support/profileFixture";
import {
  open,
  row,
  editButton,
  save,
  aeatEditor,
  goToSection,
} from "../support/userProfilePage";
import { fixtureYear } from "../../src/dev/fixtureDates";

// The profile page's details: the Censo summary, search and sort, per-year details and opening them for edit.

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
    PROFILE_NAME,
  );
  await expect(header).toContainText(profileStated("identity.email"));
  await expect(header).toContainText(
    `${profileStated("contact.fiscal_address")} · ${profileStated("contact.postcode")}`,
  );
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
  await profile
    .getByRole("searchbox")
    .fill(profileStated("contact.fiscal_address").split(/[ ,]+/).pop()!);
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

test("a detail stated per ejercicio asks the year and keeps the other years' answers", async ({
  page,
}) => {
  const profile = await open(page);
  const answer = async (choice: string, year: string) => {
    await row(
      profile,
      "irpf.activity_income_imputation_criterion",
    ).scrollIntoViewIfNeeded();
    await editButton(profile, "Income and expense timing").click();
    const dialog = page.getByRole("dialog", {
      name: "Income and expense timing",
      exact: true,
    });
    await dialog.getByRole("combobox").selectOption(choice);
    await expect(save(dialog)).toBeDisabled();
    await dialog
      .getByRole("textbox", { name: label("desktop.profile.ejercicio") })
      .fill(year);
    await save(dialog).click();
    await expect(dialog).toHaveCount(0);
  };
  const cash = String(fixtureYear - 2);
  const accrual = String(fixtureYear - 1);
  await answer("cobros_y_pagos", cash);
  await answer("devengo", accrual);

  await editButton(profile, "Income and expense timing").click();
  const dialog = page.getByRole("dialog", {
    name: "Income and expense timing",
    exact: true,
  });
  await expect(dialog).toContainText(new RegExp(`${cash}: .*\n?`));
  await expect(dialog).toContainText(new RegExp(`${accrual}: `));
});

test("details open for editing by double click, Enter, F2 and the hover button", async ({
  page,
}) => {
  const profile = await open(page);
  const given = row(profile, "identity.name");
  const dialog = page.getByRole("dialog", { name: "Given name", exact: true });
  const stored = profileStated("identity.name");
  for (const target of ["Given name", stored]) {
    await given.getByText(target, { exact: true }).dblclick();
    await expect(dialog.getByLabel("Given name", { exact: true })).toHaveValue(
      stored,
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
    `writeClipboard ${profileStated("identity.email").length} characters`,
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
    PROFILE_SECTION_TITLES,
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
  ).toHaveAttribute("autocomplete", "off");
  await page
    .getByRole("dialog")
    .getByRole("button", { name: label("desktop.profile.cancel"), exact: true })
    .last()
    .click();
  await page
    .locator('[data-dock-header="docs"]')
    .getByRole("button", {
      name: label("desktop.dock.expand"),
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
  await expect(profile).toContainText(
    profileStated("contact.contact_person_phone"),
  );
});

test("a date left unfinished stays in its field, is refused, and never clears the saved date", async ({
  page,
}) => {
  const profile = await open(page);
  const birth = row(profile, "renta_taxpayer.birth_date");
  const writes = () => page.evaluate(() => window.__scenarioProfile!.writes());
  const dialog = page.getByRole("dialog", { name: "Birth date", exact: true });
  const field = dialog.getByLabel("Birth date", { exact: true });
  const edit = async () => {
    await birth.focus();
    await page.keyboard.press("Enter");
    await expect(dialog).toBeVisible();
  };

  await edit();
  await field.fill("1985-03-15");
  await save(dialog).click();
  await expect(dialog).toHaveCount(0);
  await expect(birth).toContainText("1985");
  const saved = await writes();

  await edit();
  await field.fill("1985-03");
  await save(dialog).click();
  await expect(dialog).toBeVisible();
  await expect(field).toHaveValue("1985-03");
  await expect(field).toHaveAttribute("aria-invalid", "true");
  await expect(dialog.getByRole("alert")).toContainText("1985-03");
  expect(await writes()).toBe(saved);

  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(birth).toContainText("1985");
  expect(await writes()).toBe(saved);
});
