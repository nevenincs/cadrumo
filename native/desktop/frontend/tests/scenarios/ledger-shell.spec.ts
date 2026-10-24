import { expect, test, type Locator, type Page } from "@playwright/test";
import { seedLayout } from "../support/layout";
import { label } from "../support/strings";

// The Ledger page as the shell holds it: reached from the rail, its sections
// and setup menu, the period selector, the states a read can end in, and what
// the window keeps of it. The movements themselves are drawn by later parts.

const open = (target: Page, extra = "") =>
  target.goto(`/scenarios.html?scenario=ledger&latency=0&bar=off${extra}`);

const ledgerButton = (target: Page) => target.locator("[data-rail=ledger]");
const page = (target: Page) => target.locator(".ledger-page");
const head = (target: Page) => target.locator(".pane-docs .pane-head");
const trigger = (target: Page) => head(target).locator(".ledger-period");
const menu = (target: Page) =>
  target.getByRole("dialog", {
    name: label("desktop.ledger.period.choose"),
  });
const tab = (target: Page, section: string) =>
  head(target).getByRole("tab", {
    name: label(`desktop.ledger.section.${section}`),
  });

async function openLedger(target: Page, extra = "") {
  await open(target, extra);
  await ledgerButton(target).click();
  await expect(page(target)).toBeVisible();
}

/** Opens the period dropdown and returns the year it shows. */
async function openPeriods(target: Page): Promise<Locator> {
  await trigger(target).click();
  await expect(menu(target)).toBeVisible();
  return menu(target);
}

async function choosePeriod(target: Page, year: number, code: string) {
  const periods = await openPeriods(target);
  const shown = periods.locator("[aria-live=polite]");
  for (let guard = 0; guard < 40; guard += 1) {
    const at = Number(await shown.textContent());
    if (at === year) break;
    await periods
      .getByRole("button", {
        name: label(
          at > year
            ? "desktop.ledger.period.year_previous"
            : "desktop.ledger.period.year_next",
        ),
        exact: true,
      })
      .click();
  }
  await expect(shown).toHaveText(String(year));
  await periods
    .getByRole("group", {
      name: label("desktop.ledger.period.of_year", { year }),
    })
    .getByRole("button", {
      name: code === "0A" ? label("desktop.ledger.period.year") : code,
      exact: true,
    })
    .click();
  await expect(menu(target)).toBeHidden();
}

test("the rail opens the Ledger page in the first pane, and closes it", async ({
  page: target,
}) => {
  await openLedger(target);
  await expect(ledgerButton(target)).toHaveAttribute("aria-pressed", "true");
  await expect(head(target).locator(".pane-title")).toHaveText(
    label("desktop.ledger.title"),
  );
  // One header: the page's controls sit in the pane's own, beside its
  // maximize control.
  await expect(target.locator(".pane-docs .pane-head")).toHaveCount(1);
  await expect(
    head(target).getByRole("button", {
      name: label("desktop.ledger.maximize"),
      exact: true,
    }),
  ).toBeVisible();
  await expect(page(target)).toBeFocused();
  await expect(tab(target, "movements")).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await ledgerButton(target).click();
  await expect(page(target)).toBeHidden();
  await expect(ledgerButton(target)).toHaveAttribute("aria-pressed", "false");
  await ledgerButton(target).click();
  await head(target)
    .getByRole("button", { name: label("desktop.ledger.close"), exact: true })
    .click();
  await expect(page(target)).toBeHidden();
});

test("sections switch by tab and by the setup menu, and are remembered", async ({
  page: target,
}) => {
  await openLedger(target);
  await tab(target, "invoices").click();
  await expect(tab(target, "invoices")).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(
    page(target).getByRole("tabpanel", {
      name: label("desktop.ledger.section.invoices"),
    }),
  ).toBeVisible();
  // The arrow keys move along the tabs and choose.
  await target.keyboard.press("ArrowRight");
  await expect(tab(target, "documents")).toHaveAttribute(
    "aria-selected",
    "true",
  );

  const setup = head(target).getByRole("button", {
    name: label("desktop.ledger.setup"),
    exact: true,
  });
  await setup.click();
  const items = target.getByRole("menuitem");
  await expect(items).toHaveText(
    ["rules", "registers", "health"].map((section) =>
      label(`desktop.ledger.section.${section}`),
    ),
  );
  await target
    .getByRole("menuitem", { name: label("desktop.ledger.section.health") })
    .click();
  const current = head(target).getByRole("button", {
    name: label("desktop.ledger.setup_current", {
      section: label("desktop.ledger.section.health"),
    }),
    exact: true,
  });
  await expect(current).toBeVisible();
  await expect(head(target).getByRole("tab", { selected: true })).toHaveCount(
    0,
  );
  await expect(
    page(target).getByRole("region", {
      name: label("desktop.ledger.section.health"),
    }),
  ).toBeVisible();
  // Health is per period; Rules and Registers are not, and have no period.
  await expect(trigger(target)).toBeVisible();
  await current.click();
  await target
    .getByRole("menuitem", { name: label("desktop.ledger.section.registers") })
    .click();
  await expect(trigger(target)).toHaveCount(0);
  await head(target)
    .getByRole("button", {
      name: label("desktop.ledger.setup_current", {
        section: label("desktop.ledger.section.registers"),
      }),
      exact: true,
    })
    .click();
  await target
    .getByRole("menuitem", { name: label("desktop.ledger.section.health") })
    .click();
  // Escape closes the menu and gives focus back to its button.
  await current.click();
  await expect(items.first()).toBeVisible();
  await target.keyboard.press("Escape");
  await expect(items).toHaveCount(0);
  await expect(current).toBeFocused();

  await target.reload();
  await expect(page(target)).toBeVisible();
  await expect(current).toBeVisible();
  const stored = await target.evaluate(
    () =>
      JSON.parse(localStorage.getItem("cadrumo-shell-layout") ?? "{}").layout,
  );
  expect(stored.page).toBe("ledger");
  expect(stored.ledgerView.section).toBe("health");
});

test("the period steps across a year's end and its dropdown moves between years", async ({
  page: target,
}) => {
  await openLedger(target);
  await choosePeriod(target, 2026, "1T");
  await expect(trigger(target)).toHaveText("2026 · 1T");
  const group = head(target).getByRole("group", {
    name: label("desktop.ledger.period.label"),
  });
  const previous = group.getByRole("button", {
    name: label("desktop.ledger.period.previous"),
    exact: true,
  });
  const next = group.getByRole("button", {
    name: label("desktop.ledger.period.next"),
    exact: true,
  });
  await previous.click();
  await expect(trigger(target)).toHaveText("2025 · 4T");
  await next.click();
  await next.click();
  await expect(trigger(target)).toHaveText("2026 · 2T");
  await expect(trigger(target)).toHaveAccessibleName(
    label("desktop.ledger.period.named", {
      label: label("desktop.ledger.period.label"),
      period: "2026 · 2T",
    }),
  );

  // A whole year steps by years.
  await choosePeriod(target, 2025, "0A");
  await expect(trigger(target)).toHaveText("2025");
  await next.click();
  await expect(trigger(target)).toHaveText("2026");

  // Inside, the year moves with no field to type in, and the chosen item
  // takes focus; the arrow keys move along the grid.
  const periods = await openPeriods(target);
  await expect(periods.getByRole("textbox")).toHaveCount(0);
  await expect(
    periods.getByRole("button", {
      name: label("desktop.ledger.period.year"),
      exact: true,
    }),
  ).toBeFocused();
  await target.keyboard.press("ArrowRight");
  await expect(
    periods.getByRole("button", { name: "1T", exact: true }),
  ).toBeFocused();
  await target.keyboard.press("ArrowDown");
  await expect(periods.locator("[data-period-item]:focus")).toHaveCount(1);
  await target.keyboard.press("Escape");
  await expect(menu(target)).toBeHidden();
  await expect(trigger(target)).toBeFocused();

  // Every period, and back: the steps have nothing to step from.
  const all = await openPeriods(target);
  await all
    .getByRole("button", { name: label("desktop.ledger.period.all") })
    .click();
  await expect(trigger(target)).toHaveText(label("desktop.ledger.period.all"));
  await expect(previous).toBeDisabled();
  await expect(next).toBeDisabled();
});

test("the years with movements come from the ledger and jump the dropdown", async ({
  page: target,
}) => {
  await openLedger(target);
  const periods = await openPeriods(target);
  const years = periods.getByRole("group", {
    name: label("desktop.ledger.period.years_with_movements"),
  });
  await expect(years.getByRole("button")).toHaveText([
    "2003",
    "2011",
    "2019",
    "2024",
    "2025",
    "2026",
  ]);
  await years.getByRole("button", { name: "2003", exact: true }).click();
  // Choosing a year moves the dropdown, which stays open for the period.
  await expect(periods.locator("[aria-live=polite]")).toHaveText("2003");
  await expect(menu(target)).toBeVisible();
  await periods
    .getByRole("button", {
      name: label("desktop.ledger.period.year"),
      exact: true,
    })
    .click();
  await expect(trigger(target)).toHaveText("2003");
  await expect(page(target).locator(".ledger-movements")).toContainText(
    label("desktop.ledger.movements_count", { count: 1 }),
  );
});

test("an empty period says so in one line with its ways in", async ({
  page: target,
}) => {
  await openLedger(target, "&ledger=empty");
  const empty = page(target).locator(".ledger-empty");
  await expect(empty).toBeVisible();
  const shown = (await trigger(target).textContent()) ?? "";
  await expect(empty).toContainText(
    label("desktop.ledger.empty", { period: shown }),
  );
  // Importing and adding a movement are both offered.
  await expect(
    empty.getByRole("button", {
      name: label("desktop.ledger.action.import"),
      exact: true,
    }),
  ).not.toHaveAttribute("aria-disabled", "true");
  const add = empty.getByRole("button", {
    name: new RegExp(`^${label("desktop.ledger.action.add_movement")}`),
  });
  await expect(add).not.toHaveAttribute("aria-disabled", "true");
  // A new movement is drawn in the grid, not saved.
  await add.click();
  await expect(page(target).getByRole("grid")).toBeVisible();
  await expect(page(target).locator(".ledger-draft-status")).toHaveCount(1);
});

test("a failed read says so with its code and reads again only when asked", async ({
  page: target,
}) => {
  await openLedger(target, "&ledger=unavailable");
  const failed = page(target).locator(".ledger-failed");
  await expect(failed.getByRole("alert")).toContainText(
    label("desktop.ledger.failed"),
  );
  await expect(failed.locator("code")).not.toBeEmpty();
  // Nothing reads again by itself.
  await target.waitForTimeout(1500);
  await expect(page(target).locator(".ledger-loading")).toHaveCount(0);
  await expect(failed).toBeVisible();
  const retry = failed.getByRole("button", {
    name: label("desktop.ledger.retry"),
  });
  await retry.click();
  await expect(page(target).locator(".ledger-failed")).toBeVisible();
  await expect(page(target).locator(".ledger-failed")).toContainText(
    label("desktop.ledger.failed"),
  );
});

test("signed out, the page is withheld and says how to sign in", async ({
  page: target,
}) => {
  await seedLayout(target, { layout: { page: "ledger" } });
  await target.goto("/scenarios.html?scenario=signed-out&latency=0&bar=off");
  await expect(page(target)).toContainText(label("desktop.ledger.signed_out"));
  await expect(head(target).getByRole("tab")).toHaveCount(0);
  await expect(page(target).locator(".ledger-readiness")).toHaveCount(0);
});

test("reading a period keeps no taxpayer value in the window's storage", async ({
  page: target,
}) => {
  await openLedger(target);
  await choosePeriod(target, 2026, "1T");
  const movements = page(target).locator(".ledger-movements");
  await expect(movements).toBeVisible();
  await expect(
    movements.locator(
      ".ledger-readiness [data-readiness]:not([data-readiness=unknown])",
    ),
  ).toBeVisible();
  const stored = await target.evaluate(() => {
    const all: string[] = [];
    for (const store of [localStorage, sessionStorage])
      for (let at = 0; at < store.length; at += 1) {
        const key = store.key(at) ?? "";
        all.push(key, store.getItem(key) ?? "");
      }
    return all.join("\n");
  });
  for (const value of [
    "Talleres Ondara",
    "HOJA VERDE",
    "TRANSFERENCIA",
    "Coworking Ribera",
    "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    "2026-0",
  ])
    expect(stored).not.toContain(value);
  const layout = JSON.parse(
    (await target.evaluate(() =>
      localStorage.getItem("cadrumo-shell-layout"),
    )) ?? "{}",
  ).layout;
  // What is kept is the page's layout, and no period.
  expect(Object.keys(layout.ledgerView).sort()).toEqual([
    "columns",
    "density",
    "exportFormat",
    "groupBy",
    "inspectorOpen",
    "inspectorWidth",
    "savedView",
    "section",
  ]);
  expect(JSON.stringify(layout)).not.toContain("1T");
});

test("the page offers its actions to the palette and leaves the grid its keys", async ({
  page: target,
}) => {
  await openLedger(target);
  await page(target).focus();
  // Alt+Left and Alt+Right are the documentation's only where it is shown.
  const taken = await target.evaluate(
    () =>
      new Promise<boolean>((resolve) => {
        // A chord the shell takes is stopped before it bubbles this far.
        const timer = window.setTimeout(() => resolve(true), 500);
        const seen = (event: KeyboardEvent) => {
          window.removeEventListener("keydown", seen);
          window.clearTimeout(timer);
          resolve(event.defaultPrevented);
        };
        window.addEventListener("keydown", seen);
        document.querySelector(".ledger-page")?.dispatchEvent(
          new KeyboardEvent("keydown", {
            key: "ArrowLeft",
            code: "ArrowLeft",
            altKey: true,
            bubbles: true,
            cancelable: true,
          }),
        );
      }),
  );
  expect(taken).toBe(false);

  await target.keyboard.press("Control+KeyK");
  const palette = target.locator(".palette");
  await palette
    .getByRole("combobox", { name: label("desktop.palette.label") })
    .fill(label("desktop.ledger.action.go_to_period").replace("…", ""));
  await target.keyboard.press("Enter");
  await expect(palette).toBeHidden();
  await expect(menu(target)).toBeVisible();
  await target.keyboard.press("Escape");
  await expect(menu(target)).toBeHidden();

  await target.keyboard.press("Control+KeyK");
  await palette
    .getByRole("combobox", { name: label("desktop.palette.label") })
    .fill(
      label("desktop.ledger.action.section", {
        section: label("desktop.ledger.section.rules"),
      }),
    );
  await target.keyboard.press("Enter");
  await expect(
    head(target).getByRole("button", {
      name: label("desktop.ledger.setup_current", {
        section: label("desktop.ledger.section.rules"),
      }),
      exact: true,
    }),
  ).toBeVisible();
});

test("readiness is a glyph and a count per thing it counts, with the words in its name", async ({
  page: target,
}) => {
  await openLedger(target);
  await choosePeriod(target, 2026, "1T");
  const pills = page(target).locator(".ledger-readiness [data-readiness]");
  await expect(
    page(target).locator(".ledger-readiness [data-readiness=unknown]"),
  ).toHaveCount(0);
  await expect(pills).not.toHaveCount(0);
  const kinds = await pills.evaluateAll((items) =>
    items.map((item) => item.getAttribute("data-readiness")),
  );
  // Each counts its own thing, so none repeats, and the tick stands alone.
  expect(new Set(kinds).size).toBe(kinds.length);
  if (kinds.includes("ready")) expect(kinds).toEqual(["ready"]);
  for (const pill of await pills.all()) {
    // Seen: only a number, if anything. Said: a sentence, with no glyph.
    const seen = await pill.evaluate((item) =>
      [...item.querySelectorAll("[aria-hidden=true]")]
        .map((part) => part.textContent ?? "")
        .join(""),
    );
    expect(seen).toMatch(/^\d*$/);
    const said = (await pill.textContent()) ?? "";
    expect(said.length).toBeGreaterThan(seen.length + 3);
    expect(said).not.toMatch(/[⚠○⊘✓◌]/u);
  }
  if (kinds.includes("to_classify"))
    await expect(
      pills.filter({
        hasText: label("desktop.ledger.count.to_classify", {
          count: "",
        }).trim(),
      }),
    ).toHaveCount(1);
});
