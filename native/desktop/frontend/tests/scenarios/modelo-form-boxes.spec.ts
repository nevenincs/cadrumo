import { readdirSync, writeFileSync } from "node:fs";
import { expect, test, type Page } from "@playwright/test";
import { label } from "../support/strings";
import { openList, views, type Language } from "../support/scenarioModelo";
import { MODELO_FIXTURES } from "../support/windowFixtures";

// Every box the application served on a page of a Modelo 100 reaches the
// screen with the value it served. The form draws the pages the read serves;
// a section far from the view is drawn only once it is near, so a box placed
// on a page, in a grid, among the working figures or the unplaced boxes is
// found once its page is open and read to its end, and a reader that does not
// read the page sees only the sections near the top. The filing years are the
// ones the stored couple envelopes hold; none is named here.

const language: Language = "en";

/** The couples' shapes: one per stored filing year, and the default year's. */
const SHAPES = [
  "renta-married",
  ...readdirSync(MODELO_FIXTURES)
    .map((name) => /^modelo-100-0A-(y\d+)-en\.json$/.exec(name)?.[1])
    .filter((year): year is string => year !== undefined)
    .map((year) => `renta-${year}`),
];

/** The pair of casillas the oracle lists on the form with the amount the
 * household's earnings leave. */
const PAIR = ["c:0534", "c:0535"] as const;

type PageReport = {
  page: string;
  heading: string;
  applies: boolean | null;
  /** Keys the page serves as boxes: `c:<casilla>` or `b:<binding>`. */
  served: string[];
  /** The served value text of each box, by key. */
  values: Record<string, string | null>;
  /** What is in the page's DOM as soon as the tab is open. */
  unread: string[];
  /** What is in the DOM once the page is read to its end. */
  drawn: string[];
  /** The value each drawn box carries, by key. */
  drawnValues: Record<string, string | null>;
};

/** Opens the filer's Modelo 100 of the shape's year the way the
 * new-declaration dialog offers it. */
async function openRenta(target: Page, shape: string) {
  await openList(target, { shape, language });
  const existing = await target.evaluate(async (asked) => {
    const read = await window.__fixtureModelo!.declarations(asked);
    const found = read.creation_targets.find(
      (entry) => entry.modelo === "100" && entry.existing,
    )!;
    return { title: found.modelo_title, period: found.period_words! };
  }, language);
  await target
    .getByRole("button", {
      name: label("workspace.declarations.list.key.new", {}, language),
    })
    .first()
    .click();
  const dialog = target.getByRole("dialog");
  await dialog.getByText(existing.title, { exact: true }).click();
  await dialog.getByRole("radio", { name: existing.period }).click();
  await dialog
    .getByRole("button", {
      name: label("workspace.declarations.list.new.open_it", {}, language),
    })
    .click();
  await expect(views(target, language)).toBeVisible({ timeout: 30_000 });
}

/** What the read served for each page, in the form's order, as the boxes the
 * page places; the lists the form keeps apart from its pages come last. */
async function servedPages(target: Page) {
  return target.evaluate(async (asked) => {
    const port = window.__fixtureModelo!;
    const list = await port.declarations(asked);
    const unit = list.creation_targets.find(
      (entry) => entry.modelo === "100" && entry.existing,
    )!.existing!.work_unit_id;
    const form = (await port.form(unit, asked)).form.form;
    type Field = {
      address: { kind: string; casilla_id?: string; binding_id?: string };
      value: { text: string } | null;
    };
    const keyOf = (field: Field) =>
      field.address.kind === "casilla"
        ? `c:${field.address.casilla_id}`
        : `b:${field.address.binding_id}`;
    const placed = (
      page: string,
      heading: string,
      applies: boolean | null,
      fields: Field[],
    ) => ({
      page,
      heading,
      applies,
      served: fields.map(keyOf),
      values: Object.fromEntries(
        fields.map((field) => [keyOf(field), field.value?.text ?? null]),
      ),
    });
    const pages = form.pages.map((page) => {
      const fields: Field[] = [];
      for (const section of page.sections)
        for (const block of section.blocks) {
          if (block.kind === "field") fields.push(block.field as Field);
          else if (block.kind === "grid")
            for (const row of block.rows)
              for (const cell of row.cells)
                if (cell.field) fields.push(cell.field as Field);
          if (block.kind === "binding_inputs")
            fields.push(...(block.fields as Field[]));
        }
      return placed(page.id, page.heading.text, page.applies, fields);
    });
    const answers = form.outline.find((group) => group.kind === "answers");
    return [
      ...pages,
      ...(form.unplaced.length
        ? [
            placed(
              "unplaced",
              "unplaced",
              true,
              form.unplaced.map((entry) => entry.field as Field),
            ),
          ]
        : []),
      ...(form.working_figures.length
        ? [
            placed(
              "working-figures",
              "working figures",
              true,
              form.working_figures as Field[],
            ),
          ]
        : []),
      ...(answers && form.answers.length
        ? [
            placed(
              "answers",
              answers.heading.text,
              true,
              form.answers as Field[],
            ),
          ]
        : []),
    ];
  }, language);
}

/** The boxes in the open page's DOM, by key, with the value each carries. */
const inDom = (target: Page) =>
  target.locator("[data-modelo-form]").evaluate((element) => {
    const found: Record<string, string | null> = {};
    for (const node of element.querySelectorAll("[data-key]"))
      found[node.getAttribute("data-key")!] = node.getAttribute("data-value");
    return found;
  });

/** Brings each section of the open page into view in turn: a section far from
 * the view is drawn only once it is near, and drawing the ones before it
 * moves it. */
async function readToTheEnd(target: Page) {
  await target.locator("[data-modelo-form]").evaluate(async (element) => {
    const frame = () =>
      new Promise<void>((done) => requestAnimationFrame(() => done()));
    for (const section of element.querySelectorAll("section[id^=section-]")) {
      section.scrollIntoView({ block: "start" });
      await frame();
      await frame();
    }
    element.scrollTop = element.scrollHeight;
    await frame();
    await frame();
  });
}

for (const shape of SHAPES) {
  test(`every box the ${shape} Modelo 100 serves on a page is drawn there with its value`, async ({
    page: target,
  }) => {
    test.setTimeout(240_000);
    await openRenta(target, shape);
    const served = await servedPages(target);
    expect(served.length).toBeGreaterThan(1);
    const tabs = target
      .getByRole("tablist", {
        name: label("desktop.modelo.form.pages", {}, language),
      })
      .getByRole("tab");
    await expect(tabs).toHaveCount(served.length);
    // Before any page is read: the form's search names a box by its printed
    // number and draws it, whatever section of its page it is in.
    for (const key of PAIR) {
      const index = served.findIndex((entry) => entry.served.includes(key));
      expect(index, `${key} is placed on a page of the form`).toBeGreaterThan(
        -1,
      );
      await tabs.nth(index).click();
      const search = target.getByRole("searchbox", {
        name: label("desktop.modelo.search.label", {}, language),
      });
      await search.fill(key.slice("c:".length));
      const drawn = target.locator(`[data-modelo-form] [data-key="${key}"]`);
      await expect(drawn).toHaveCount(1);
      await expect(drawn).toHaveAttribute(
        "data-value",
        served[index]!.values[key]!,
      );
      await search.fill("");
    }
    const report: PageReport[] = [];
    for (const [index, entry] of served.entries()) {
      await tabs.nth(index).click();
      await expect(tabs.nth(index)).toHaveAttribute("aria-selected", "true");
      const unread = Object.keys(await inDom(target));
      await readToTheEnd(target);
      const drawnValues = await inDom(target);
      report.push({
        ...entry,
        unread,
        drawn: Object.keys(drawnValues),
        drawnValues,
      });
    }
    writeFileSync(
      `../../../.tmp/2026-11-14-frontend-box0534/pages-${shape}.json`,
      JSON.stringify(report, null, 1),
    );

    for (const entry of report) {
      // A page the application serves as not applying draws its words, not
      // its boxes.
      if (entry.applies === false) continue;
      const missing = entry.served.filter((key) => !entry.drawn.includes(key));
      expect(missing, `page ${entry.page} ${entry.heading}`).toEqual([]);
      for (const key of entry.served)
        expect(entry.drawnValues[key] ?? null, `${entry.page} ${key}`).toBe(
          entry.values[key],
        );
    }

    // The pair is on a page of the form with the figures the read served.
    const all = new Map(
      report.flatMap((entry) =>
        entry.served.map((key) => [key, entry] as const),
      ),
    );
    for (const key of PAIR) {
      const entry = all.get(key);
      expect(entry, `${key} is placed on a page of the form`).toBeDefined();
      expect(entry!.drawn).toContain(key);
      expect(entry!.drawnValues[key]).toBe(entry!.values[key]);
      expect(entry!.values[key]).not.toBeNull();
    }
  });
}
