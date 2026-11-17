import { expect, test, type Page } from "@playwright/test";
import { openFromDialog, tab } from "../support/scenarioModelo";

// Every box's words on a Modelo 100's form keep at least 120px of the row,
// however wide the value beside them is. A box's value is served text whose
// width the window does not choose: the filer's surname and first name is
// served at whatever length the profile holds, so the served name is read
// here twice over, as a long compound name would be, and the label beside it
// must keep its room at every window size the package is checked at.

const LABEL_MIN = 120;

/** The surname-and-first-name box of the declarant's first page. */
const NAME_BOX = "DP_APENOM_D";

/** The native window's inner sizes the package audit measures. */
const SIZES = [
  { width: 1425, height: 914 },
  { width: 1264, height: 791 },
  { width: 1008, height: 631 },
  { width: 884, height: 591 },
];

/** Serves the filer's name box twice as long as the fixture holds it, from
 * the first read of the form on. */
async function widenServedName(target: Page) {
  await target.addInitScript((casilla) => {
    const widen = (port: NonNullable<Window["__fixtureModelo"]>) => {
      const original = port.form;
      port.form = async (...args) => {
        const read = await original(...args);
        let widened = false;
        const walk = (node: unknown) => {
          if (Array.isArray(node)) node.forEach(walk);
          else if (node && typeof node === "object") {
            const field = node as {
              address?: { kind?: string; casilla_id?: string };
              value?: { kind: string; text: string } | null;
              value_text?: string | null;
            };
            if (
              field.address?.kind === "casilla" &&
              field.address.casilla_id === casilla &&
              field.value?.kind === "string" &&
              field.value_text
            ) {
              const longer = `${field.value_text} ${field.value_text}`;
              field.value = { ...field.value, text: longer };
              field.value_text = longer;
              widened = true;
            }
            Object.values(node).forEach(walk);
          }
        };
        walk(read.form.form.pages);
        if (!widened)
          throw new Error(`the fixture serves no string value for ${casilla}`);
        return read;
      };
    };
    // The fixture publishes its port on its first read; each port is
    // widened once, when it is published.
    let current: Window["__fixtureModelo"];
    Object.defineProperty(window, "__fixtureModelo", {
      configurable: true,
      get: () => current,
      set: (port: Window["__fixtureModelo"]) => {
        if (port && port !== current) widen(port);
        current = port;
      },
    });
  }, NAME_BOX);
}

/** The width of each drawn row's label holder, as the package audit reads
 * it, with the row's key and whether its words run onto a second line. */
const labelWidths = (target: Page) =>
  target.evaluate(() => {
    const widths: { key: string; width: number; wrapped: boolean }[] = [];
    for (const row of document.querySelectorAll(
      "[data-modelo-form] [role=row][data-key]",
    )) {
      if (!row.getClientRects().length) continue;
      const cell = row.querySelector(":scope > [role=gridcell]:nth-child(2)");
      const holder =
        cell?.querySelector(":scope > span > span.min-w-0") ?? cell;
      if (!holder) continue;
      const words = document.createRange();
      words.selectNodeContents(holder);
      const tops = new Set(
        [...words.getClientRects()].map((line) => Math.round(line.top)),
      );
      widths.push({
        key: row.getAttribute("data-key")!,
        width: Math.round(holder.getBoundingClientRect().width),
        wrapped: tops.size > 1,
      });
    }
    return widths;
  });

for (const size of SIZES) {
  test(`at ${size.width} by ${size.height} every field-row label of a Modelo 100 keeps ${LABEL_MIN}px beside a long served value`, async ({
    page: target,
  }) => {
    test.setTimeout(120_000);
    await target.setViewportSize(size);
    await widenServedName(target);
    await openFromDialog(target, "100", "en", "renta-married");
    await tab(target, "desktop.modelo.view.form").click();
    const form = target.locator("[data-modelo-form]");
    const name = form.locator(`[role=row][data-key$="${NAME_BOX}"]`);
    await expect(name).toBeVisible();
    await expect(name).toHaveAttribute("data-value", /^(\S.*) \1$/);
    const widths = await labelWidths(target);
    expect(widths.length).toBeGreaterThan(0);
    // A label whose whole text is shorter than 120px is drawn on one line at
    // its own width; any other is given at least 120px.
    const narrow = widths.filter(
      (entry) => entry.width < LABEL_MIN && entry.wrapped,
    );
    expect(
      narrow,
      `labels under ${LABEL_MIN}px: ${narrow.map((entry) => `${entry.key} ${entry.width}px`).join(", ")}`,
    ).toEqual([]);
    // The value is never cut: the name's whole text is on screen in its row.
    const value = name.getByRole("gridcell").nth(2);
    const cut = await value.evaluate((cell) =>
      [...cell.querySelectorAll("*")].some(
        (node) => node.scrollWidth > node.clientWidth + 1,
      ),
    );
    expect(cut, "the name's value is cut").toBe(false);
    // Nothing of the row reaches past the form.
    const past = await name.evaluate(
      (row) => row.scrollWidth > row.clientWidth + 1,
    );
    expect(past, "the name's row overflows").toBe(false);
  });
}
