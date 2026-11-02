import { expect, test, type Locator, type Page } from "@playwright/test";
import { label } from "../support/strings";

// Who gets Escape when layers are stacked. One press closes the topmost layer
// and nothing else, the next closes the one beneath, focus goes back to what
// opened each, and a layer still fading never holds the key.

/** Holds every closing layer's fade open, so a press lands in it every time. */
const holdClosing = (page: Page) =>
  page.addStyleTag({
    content: `[data-state="closed"][data-slot] { animation-duration: 2s !important; }`,
  });

const CALENDAR = label("desktop.editor.date.open");

const open = async (page: Page, surface: "dialog" | "sheet" = "dialog") => {
  await page.goto("/primitives.html?harness=layers");
  const opener = page.getByRole("button", { name: `Open ${surface}` });
  await opener.click();
  const layer = page.getByRole("dialog", {
    name: surface === "dialog" ? "Layers" : "Sheet",
  });
  await expect(layer).toBeVisible();
  return { opener, layer };
};

for (const [key, reason] of [
  ["Tab", "tab"],
  ["Shift+Tab", "shift-tab"],
])
  test(`${key} closes an unmatched standalone combobox and returns to its trigger`, async ({
    page,
  }) => {
    const { layer } = await open(page);
    const trigger = layer.getByRole("button", { name: "Choice" });
    await trigger.click();
    await page
      .getByRole("combobox", { name: "Choice", exact: true })
      .fill("unmatched-zzzz-query");
    await expect(page.getByRole("option")).toHaveCount(0);
    await page.keyboard.press(key!);
    await expect(page.locator('[data-slot="combobox"]')).toHaveCount(0);
    await expect(trigger).toBeFocused();
    await expect(layer.getByTestId("cancels")).toHaveText(reason!);
    await expect(layer).toBeVisible();
  });

test("keyboard suggestions reveal wrapped options without scrolling their dialog", async ({
  page,
}) => {
  await page.goto("/primitives.html?harness=layers&tallSuggestions");
  await page.getByRole("button", { name: "Open dialog" }).click();
  const layer = page.getByRole("dialog", { name: "Layers" });
  const input = layer.getByLabel("Text", { exact: true });
  await input.fill("Choice");
  await page.keyboard.press("ArrowUp");
  const list = page.getByRole("listbox");
  await expect(list.getByRole("option")).toHaveCount(8);
  const parentScroll = await layer.evaluate((element) => ({
    page: window.scrollY,
    dialog: element.scrollTop,
  }));
  const visible = async () => {
    await expect
      .poll(() =>
        list.evaluate((element) => {
          const selected = element.querySelector('[aria-selected="true"]');
          if (!selected) return false;
          const box = element.getBoundingClientRect();
          const item = selected.getBoundingClientRect();
          return item.top >= box.top - 1 && item.bottom <= box.bottom + 1;
        }),
      )
      .toBe(true);
    await expect(input).toBeFocused();
  };
  await visible();
  await page.keyboard.press("ArrowDown");
  await visible();
  for (let at = 0; at < 7; at++) await page.keyboard.press("ArrowDown");
  await visible();
  expect(
    await layer.evaluate((element) => ({
      page: window.scrollY,
      dialog: element.scrollTop,
    })),
  ).toEqual(parentScroll);
  await page.keyboard.press("Enter");
  await expect(input).toHaveValue("Choice 8");
  await expect(list).toHaveCount(0);
});

/** Each layer that opens over the dialog, how it is opened, what shows it is
 * up, and what must hold focus once it has gone. */
type Case = {
  name: string;
  raise(layer: Locator, page: Page): Promise<void>;
  shown(page: Page): Locator;
  returnsTo(layer: Locator): Locator;
};

const CASES: Case[] = [
  {
    name: "the date editor's calendar",
    raise: (layer) => layer.getByRole("button", { name: CALENDAR }).click(),
    shown: (page) =>
      page
        .locator('[data-slot="popover-content"]')
        .filter({ has: page.getByRole("grid") }),
    returnsTo: (layer) => layer.getByRole("button", { name: CALENDAR }),
  },
  {
    name: "a combobox's list",
    raise: (layer) => layer.getByRole("button", { name: "Choice" }).click(),
    shown: (page) => page.locator('[data-slot="combobox"]'),
    returnsTo: (layer) => layer.getByRole("button", { name: "Choice" }),
  },
  {
    name: "a menu",
    raise: (layer) => layer.getByRole("button", { name: "Menu" }).click(),
    shown: (page) => page.getByRole("menu"),
    returnsTo: (layer) => layer.getByRole("button", { name: "Menu" }),
  },
  {
    name: "a dialog over the dialog",
    raise: (layer) => layer.getByRole("button", { name: "Nested" }).click(),
    shown: (page) => page.getByRole("dialog", { name: "Nested dialog" }),
    returnsTo: (layer) => layer.getByRole("button", { name: "Nested" }),
  },
];

for (const { name, raise, shown, returnsTo } of CASES) {
  test(`Escape closes ${name}, and the next the dialog`, async ({ page }) => {
    const { opener, layer } = await open(page);
    await raise(layer, page);
    await expect(shown(page)).toBeVisible();

    await page.keyboard.press("Escape");
    await expect(shown(page)).toHaveCount(0);
    await expect(layer).toBeVisible();
    await expect(page.getByTestId("leaves")).toHaveText("0");
    await expect(returnsTo(layer)).toBeFocused();

    await page.keyboard.press("Escape");
    await expect(layer).toHaveCount(0);
    await expect(opener).toBeFocused();
  });

  test(`a second Escape as ${name} fades closes the dialog`, async ({
    page,
  }) => {
    const { opener, layer } = await open(page);
    await holdClosing(page);
    await raise(layer, page);
    await expect(shown(page)).toBeVisible();

    await page.keyboard.press("Escape");
    // Gone from the keyboard, still on screen.
    await expect(shown(page)).toHaveAttribute("data-state", "closed");
    await expect(layer).toHaveAttribute("data-state", "open");
    await page.keyboard.press("Escape");
    await expect(layer).toHaveAttribute("data-state", "closed");
    await expect(page.getByTestId("leaves")).toHaveText("1");
    await expect(layer).toHaveCount(0);
    await expect(shown(page)).toHaveCount(0);
    await expect(opener).toBeFocused();
  });

  test(`a rapid double Escape from ${name} leaves nothing up`, async ({
    page,
  }) => {
    const { opener, layer } = await open(page);
    await raise(layer, page);
    await expect(shown(page)).toBeVisible();

    await page.keyboard.press("Escape");
    await page.keyboard.press("Escape");
    await expect(layer).toHaveCount(0);
    await expect(shown(page)).toHaveCount(0);
    await expect(page.getByTestId("leaves")).toHaveText("1");
    await expect(opener).toBeFocused();
  });
}

test("Escape closes a suggestion list, and the next the dialog", async ({
  page,
}) => {
  const { opener, layer } = await open(page);
  const field = layer.getByLabel("Text");
  await field.fill("Al");
  const list = page.locator('[data-slot="suggestions"]');
  await expect(list).toBeVisible();

  await page.keyboard.press("Escape");
  await expect(list).toHaveCount(0);
  await expect(layer).toBeVisible();
  await expect(field).toBeFocused();
  await expect(field).toHaveValue("Al");

  await page.keyboard.press("Escape");
  await expect(layer).toHaveCount(0);
  await expect(opener).toBeFocused();
});

test("a rapid double Escape from a suggestion list leaves nothing up", async ({
  page,
}) => {
  const { opener, layer } = await open(page);
  await layer.getByLabel("Text").fill("Al");
  await expect(page.locator('[data-slot="suggestions"]')).toBeVisible();

  await page.keyboard.press("Escape");
  await page.keyboard.press("Escape");
  await expect(layer).toHaveCount(0);
  await expect(opener).toBeFocused();
});

test("focus left in the dialog does not take Escape from a popover over it", async ({
  page,
}) => {
  const { layer } = await open(page);
  const quiet = layer.getByRole("button", { name: "Quiet" });
  await quiet.click();
  const popover = page.getByRole("dialog", { name: "Quiet popover" });
  await expect(popover).toBeVisible();
  await expect(quiet).toBeFocused();

  await page.keyboard.press("Escape");
  await expect(popover).toHaveCount(0);
  await expect(page.getByTestId("leaves")).toHaveText("0");
  await expect(layer).toHaveAttribute("data-state", "open");
});

test("Escape with a tooltip showing still closes the layer, not the tooltip alone", async ({
  page,
}) => {
  const { opener, layer } = await open(page);
  const explained = layer.getByRole("button", { name: "Explained" });
  await explained.focus();
  await expect(page.getByRole("tooltip")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(layer).toHaveCount(0);
  await expect(opener).toBeFocused();
});

test("Escape with a tooltip showing closes a combobox at the first press", async ({
  page,
}) => {
  const { layer } = await open(page);
  const explained = layer.getByRole("button", { name: "Explained" });
  await explained.hover();
  await expect(page.getByRole("tooltip")).toBeVisible();
  const choice = layer.getByRole("button", { name: "Choice" });
  await choice.focus();
  await page.keyboard.press("Enter");
  const list = page.locator('[data-slot="combobox"]');
  await expect(list).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(list).toHaveCount(0);
  await expect(layer).toHaveAttribute("data-state", "open");
});

test("Escape closes the inner of two popovers and then the outer", async ({
  page,
}) => {
  const { layer } = await open(page);
  await layer.getByRole("button", { name: "Outer" }).click();
  const outer = page.getByRole("dialog", { name: "Outer popover" });
  await outer.getByRole("button", { name: "Inner" }).click();
  const inner = page.getByRole("dialog", { name: "Inner popover" });
  await expect(inner).toBeVisible();

  await page.keyboard.press("Escape");
  await expect(inner).toHaveCount(0);
  await expect(outer).toBeVisible();
  await expect(outer.getByRole("button", { name: "Inner" })).toBeFocused();

  await page.keyboard.press("Escape");
  await expect(outer).toHaveCount(0);
  await expect(layer).toBeVisible();
  await expect(layer.getByRole("button", { name: "Outer" })).toBeFocused();
});

test("a rapid triple Escape walks the whole stack", async ({ page }) => {
  const { opener, layer } = await open(page);
  await layer.getByRole("button", { name: "Outer" }).click();
  const outer = page.getByRole("dialog", { name: "Outer popover" });
  await outer.getByRole("button", { name: "Inner" }).click();
  await expect(
    page.getByRole("dialog", { name: "Inner popover" }),
  ).toBeVisible();

  await page.keyboard.press("Escape");
  await page.keyboard.press("Escape");
  await page.keyboard.press("Escape");
  await expect(layer).toHaveCount(0);
  await expect(page.getByTestId("leaves")).toHaveText("1");
  await expect(opener).toBeFocused();
});

test("a sheet gives Escape to the calendar first, even while it fades", async ({
  page,
}) => {
  const { opener, layer } = await open(page, "sheet");
  await holdClosing(page);
  await layer.getByRole("button", { name: CALENDAR }).click();
  const calendar = page.getByRole("grid");
  await expect(calendar).toBeVisible();

  await page.keyboard.press("Escape");
  await expect(layer).toHaveAttribute("data-state", "open");
  await page.keyboard.press("Escape");
  await expect(layer).toHaveCount(0);
  await expect(opener).toBeFocused();
});

test("a combobox left by Escape reports Escape, and by a press outside reports that", async ({
  page,
}) => {
  const { layer } = await open(page);
  const choice = layer.getByRole("button", { name: "Choice" });
  const cancels = page.getByTestId("cancels");
  await choice.click();
  await expect(page.locator('[data-slot="combobox"]')).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(cancels).toHaveText("escape");

  await expect(page.locator('[data-slot="combobox"]')).toHaveCount(0);
  await choice.click();
  await expect(page.locator('[data-slot="combobox"]')).toBeVisible();
  await layer.getByRole("heading", { name: "Layers" }).click();
  await expect(cancels).toHaveText("escape outside");
});

test("a combobox's refusal is a field error under its trigger, read with it", async ({
  page,
}) => {
  const { layer } = await open(page);
  const choice = layer.getByRole("button", { name: "Choice" });
  await expect(layer.locator('[data-slot="field-error"]')).toHaveCount(0);
  await expect(choice).not.toHaveAttribute("aria-invalid", "true");

  await layer.getByRole("button", { name: "Refuse" }).click();
  const error = layer.locator('[data-slot="field-error"]');
  await expect(error).toHaveText("Choose another.");
  await expect(error).toHaveRole("alert");
  await expect(choice).toHaveAttribute("aria-invalid", "true");
  await expect(choice).toHaveAccessibleDescription("Choose another.");

  // Still there, and still the one, once the list is open over it.
  await choice.click();
  const search = page.locator('[data-slot="combobox"] input');
  await expect(search).toHaveAttribute("aria-invalid", "true");
  await expect(search).toHaveAccessibleDescription("Choose another.");
  await expect(page.locator('[data-slot="field-error"]')).toHaveCount(1);
});
