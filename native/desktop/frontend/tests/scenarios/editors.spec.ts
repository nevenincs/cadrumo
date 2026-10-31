import { expect, test, type Page } from "@playwright/test";

// Each typed editor alone on the primitives page, in a real browser. The
// expected values are written out from the languages' own conventions.

type Open = {
  field: object;
  locale?: string;
  value?: string;
  mode?: string;
};

async function open(page: Page, { field, locale, value, mode }: Open) {
  const query = new URLSearchParams({
    harness: "editor",
    field: JSON.stringify(field),
    locale: locale ?? "en",
    value: value ?? "",
    mode: mode ?? "normalise",
  });
  await page.goto(`/primitives.html?${query}`);
  return page.getByLabel("Entry");
}
const held = (page: Page) => page.getByTestId("held");
const checked = (page: Page) => page.getByTestId("checked");
const elsewhere = (page: Page) =>
  page.getByRole("button", { name: "Elsewhere" }).focus();

const NBSP = " ";

for (const [locale, typed, shown] of [
  ["en", "1,234.56", "1,234.56"],
  // Spanish and Hungarian leave four figures without a thousands mark.
  ["es", "1.234,56", "1234,56"],
  ["ca", "1.234,56", "1.234,56"],
  ["hu", "1 234,56", "1234,56"],
] as const)
  test(`money reads and shows ${locale} marks`, async ({ page }) => {
    const entry = await open(page, { field: { kind: "money" }, locale });
    await entry.fill(typed);
    await expect(held(page)).toHaveText("1234.56");
    await expect(checked(page)).toHaveText("value 1234.56");
    await elsewhere(page);
    await expect(entry).toHaveValue(shown);
  });

for (const [locale, typed, shown] of [
  ["es", "12.345,67", "12.345,67"],
  ["hu", "12 345,67", `12${NBSP}345,67`],
] as const)
  test(`five figures carry the ${locale} thousands mark`, async ({ page }) => {
    const entry = await open(page, { field: { kind: "money" }, locale });
    await entry.fill(typed);
    await expect(held(page)).toHaveText("12345.67");
    await elsewhere(page);
    await expect(entry).toHaveValue(shown);
  });

test("a Spanish 1,234 reaches the grammar as one point two three four", async ({
  page,
}) => {
  const entry = await open(page, {
    field: { kind: "decimal", decimals: 6 },
    locale: "es",
  });
  await entry.fill("1,234");
  await expect(checked(page)).toHaveText("value 1.234");
  await elsewhere(page);
  await expect(entry).toHaveValue("1,234");
});

test("a Spanish 1.234 is refused and stays as typed", async ({ page }) => {
  const entry = await open(page, {
    field: { kind: "decimal", decimals: 6 },
    locale: "es",
  });
  await entry.fill("1.234");
  await expect(checked(page)).toHaveText("refused ambiguous_grouping");
  await elsewhere(page);
  await expect(entry).toHaveValue("1.234");
  await entry.focus();
  await expect(entry).toHaveValue("1.234");
});

test("an English 1,234 is refused", async ({ page }) => {
  const entry = await open(page, { field: { kind: "money" }, locale: "en" });
  await entry.fill("1,234");
  await expect(checked(page)).toHaveText("refused ambiguous_grouping");
});

test("a Spanish 1,000 on an amount is refused, not read as a thousand", async ({
  page,
}) => {
  const entry = await open(page, { field: { kind: "money" }, locale: "es" });
  await entry.fill("1,000");
  await expect(checked(page)).toHaveText("refused too_many_decimals");
  await elsewhere(page);
  // Refused digits show whole: nothing is rounded away.
  await expect(entry).toHaveValue("1,000");
  await entry.focus();
  await expect(entry).toHaveValue("1,000");
});

test("refused trailing zeros stay on a decimal", async ({ page }) => {
  const entry = await open(page, {
    field: { kind: "decimal", decimals: 2 },
    locale: "es",
  });
  await entry.fill("1,50000");
  await expect(checked(page)).toHaveText("refused too_many_decimals");
  await elsewhere(page);
  await expect(entry).toHaveValue("1,50000");
});

test("big integers and six decimals keep every digit", async ({ page }) => {
  const entry = await open(page, {
    field: { kind: "decimal", decimals: 6 },
    locale: "es",
  });
  await entry.fill("9007199254740993,123456");
  await expect(checked(page)).toHaveText("value 9007199254740993.123456");
  await elsewhere(page);
  await expect(entry).toHaveValue("9.007.199.254.740.993,123456");
  await entry.focus();
  await expect(entry).toHaveValue("9007199254740993,123456");
});

test("lexeme mode sends what was typed and restyles nothing", async ({
  page,
}) => {
  const entry = await open(page, {
    field: { kind: "money" },
    locale: "es",
    mode: "lexeme",
  });
  await entry.fill("1.234,56");
  await expect(held(page)).toHaveText("1.234,56");
  await elsewhere(page);
  await expect(entry).toHaveValue("1.234,56");
});

test("an integer leaves a fraction for its check", async ({ page }) => {
  const entry = await open(page, { field: { kind: "integer" }, locale: "hu" });
  await entry.fill("1 000");
  await expect(checked(page)).toHaveText("value 1000");
  await entry.fill("1,5");
  await expect(checked(page)).toHaveText("refused not_a_number");
});

test("a fraction percent holds the fraction and is typed in points", async ({
  page,
}) => {
  const entry = await open(page, {
    field: { kind: "percent", unit: "fraction" },
    locale: "es",
  });
  await entry.fill("21");
  await expect(checked(page)).toHaveText("value 0.21");
  await entry.fill("21,5 %");
  await expect(checked(page)).toHaveText("value 0.215");
  await entry.fill("0,5");
  await expect(checked(page)).toHaveText("value 0.005");
  await entry.fill("150");
  await expect(checked(page)).toHaveText("refused percent_above_100");
  await entry.fill("21");
  await elsewhere(page);
  await expect(entry).toHaveValue("21");
});

test("a points percent holds the points", async ({ page }) => {
  const entry = await open(page, {
    field: { kind: "percent", unit: "points" },
    locale: "en",
    value: "92",
  });
  await expect(entry).toHaveValue("92");
  await entry.fill("92.5%");
  await expect(checked(page)).toHaveText("value 92.5");
});

for (const [locale, typed, shown] of [
  ["en", "10/31/2026", "Oct 31, 2026"],
  ["es", "31/10/2026", "31 oct 2026"],
  ["ca", "31/10/2026", "31 d’oct. 2026"],
  ["hu", "2026. 10. 31.", "2026. okt. 31."],
] as const)
  test(`a date reads and shows ${locale} order`, async ({ page }) => {
    const entry = await open(page, { field: { kind: "date" }, locale });
    await entry.fill(typed);
    await expect(held(page)).toHaveText("2026-10-31");
    await expect(checked(page)).toHaveText("value 2026-10-31");
    await elsewhere(page);
    await expect(entry).toHaveValue(shown);
  });

test("a date also reads ISO, and refuses what names no day", async ({
  page,
}) => {
  const entry = await open(page, { field: { kind: "date" }, locale: "es" });
  await entry.fill("2026-10-23");
  await expect(checked(page)).toHaveText("value 2026-10-23");
  await entry.fill("31/13/2026");
  await expect(held(page)).toHaveText("31/13/2026");
  await expect(checked(page)).toHaveText("refused date_not_in_calendar");
  await entry.fill("31/10/26");
  await expect(checked(page)).toHaveText("refused not_a_date");
});

const dayIn = (page: Page, iso: string) =>
  page.locator(`button[data-day="${iso}"]`);
const openCalendar = (page: Page) =>
  page.getByRole("button", { name: /Choose date|Elige|Tria|Válassz/ }).click();

test("the calendar works by keyboard", async ({ page }) => {
  await open(page, {
    field: { kind: "date" },
    value: "2026-10-15",
  });
  await openCalendar(page);
  await expect(dayIn(page, "2026-10-15")).toBeFocused();
  await page.keyboard.press("ArrowRight");
  await expect(dayIn(page, "2026-10-16")).toBeFocused();
  await page.keyboard.press("ArrowDown");
  await expect(dayIn(page, "2026-10-23")).toBeFocused();
  await page.keyboard.press("PageDown");
  await expect(dayIn(page, "2026-11-23")).toBeFocused();
  await page.keyboard.press("PageUp");
  await expect(dayIn(page, "2026-10-23")).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(held(page)).toHaveText("2026-10-15");
  await openCalendar(page);
  await expect(dayIn(page, "2026-10-15")).toBeFocused();
  await page.keyboard.press("ArrowLeft");
  await expect(dayIn(page, "2026-10-14")).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(held(page)).toHaveText("2026-10-14");
  await expect(dayIn(page, "2026-10-14")).toHaveCount(0);
});

for (const [locale, first, month] of [
  ["en", "Sun", "October"],
  ["es", "lun", "octubre"],
  ["ca", "dl.", "octubre"],
  ["hu", "H", "október"],
] as const)
  test(`the calendar's week and months follow ${locale}`, async ({ page }) => {
    await open(page, { field: { kind: "date" }, locale, value: "2026-10-15" });
    await openCalendar(page);
    const headers = page.locator("[data-slot=popover-content] thead th");
    await expect(headers.first()).toContainText(first);
    await expect(headers).toHaveCount(7);
    await expect(
      page.locator("[data-slot=popover-content] select option", {
        hasText: month,
      }),
    ).toHaveCount(1);
  });

test("the calendar respects limits", async ({ page }) => {
  await open(page, {
    field: { kind: "date", min: "2026-10-05", max: "2026-10-25" },
    value: "2026-10-15",
  });
  await openCalendar(page);
  await expect(dayIn(page, "2026-10-04")).toBeDisabled();
  await expect(dayIn(page, "2026-10-26")).toBeDisabled();
  await expect(dayIn(page, "2026-10-05")).toBeEnabled();
});

for (const timezoneId of [
  "Pacific/Apia",
  "Pacific/Kiritimati",
  "Etc/GMT+12",
  "America/Los_Angeles",
])
  test.describe(`in ${timezoneId}`, () => {
    test.use({ timezoneId });
    test("a picked or shown day is that day", async ({ page }) => {
      const entry = await open(page, {
        field: { kind: "date" },
        value: "2026-01-01",
      });
      await expect(entry).toHaveValue("Jan 1, 2026");
      await openCalendar(page);
      await expect(dayIn(page, "2026-01-01")).toBeFocused();
      await dayIn(page, "2026-01-31").click();
      await expect(held(page)).toHaveText("2026-01-31");
      await expect(entry).toHaveValue("Jan 31, 2026");
    });
  });

test("codes hold capitals and no spaces", async ({ page }) => {
  const entry = await open(page, { field: { kind: "taxId" } });
  await entry.fill("b 12 345 678");
  await expect(held(page)).toHaveText("B12345678");
});

test("a country is held as its code and shown with its name", async ({
  page,
}) => {
  const entry = await open(page, { field: { kind: "country" }, locale: "es" });
  await entry.fill("es");
  await expect(checked(page)).toHaveText("value ES");
  await elsewhere(page);
  await expect(entry).toHaveValue("ES · España");
  await entry.focus();
  await expect(entry).toHaveValue("ES");
});

test("a currency is held as its code and shown with its name", async ({
  page,
}) => {
  const entry = await open(page, { field: { kind: "currency" }, locale: "en" });
  await entry.fill("eur");
  await elsewhere(page);
  await expect(entry).toHaveValue("EUR · Euro");
  await entry.fill("EU");
  await expect(checked(page)).toHaveText("refused not_a_currency");
});

test("an IBAN shows in groups and a secret one does not", async ({ page }) => {
  const entry = await open(page, { field: { kind: "iban" } });
  await entry.fill("es91 2100 0418 4502 0005 1332");
  await expect(held(page)).toHaveText("ES9121000418450200051332");
  await expect(checked(page)).toHaveText("value ES9121000418450200051332");
  await elsewhere(page);
  await expect(entry).toHaveValue("ES91 2100 0418 4502 0005 1332");
  const secret = await open(page, { field: { kind: "iban", secret: true } });
  await expect(secret).toHaveAttribute("type", "password");
  await secret.fill("ES91 2100 0418 4502 0005 1332");
  await elsewhere(page);
  await expect(secret).toHaveValue("ES9121000418450200051332");
});

test("a host's attributes reach the text box", async ({ page }) => {
  const entry = await open(page, { field: { kind: "date" } });
  await expect(entry).toHaveAttribute("aria-required", "true");
  await entry.focus();
  await elsewhere(page);
  await expect(page.getByTestId("blurs")).toHaveText("1");
});
