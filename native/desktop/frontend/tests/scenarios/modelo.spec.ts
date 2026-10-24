import { expect, test, type Locator, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import type {
  ModeloDeclarationsListProjectionV1,
  ModeloWorkbenchFormProjectionV1,
  PublicModeloFormField,
} from "../../src/shell/modeloContract";
import { label } from "../support/strings";

// The Modelo workspace across its states, over the envelopes the
// application read for a synthetic taxpayer (src/dev/fixtures/modelo/):
// a modelo whose rules are incomplete, a filled Modelo 130 with held zeros,
// the check's findings, a file for the AEAT left out of date by a later
// change, a filing recorded with and without a verified receipt, the list's
// rows that may apply, every state in all four languages, and a gate that
// no raw catalogue key or internal identifier reaches the screen. What the
// screen says is compared with what the envelope says: the window renders
// the read model's words and decides none of its own.

const LANGUAGES = ["en", "es", "ca", "hu"] as const;
type Language = (typeof LANGUAGES)[number];

const FIXTURES = fileURLToPath(
  new URL("../../src/dev/fixtures/modelo/", import.meta.url),
);
const envelope = <Envelope>(name: string): Envelope =>
  JSON.parse(readFileSync(`${FIXTURES}${name}.json`, "utf8")) as Envelope;
const form = (name: string, language: Language = "en") =>
  envelope<ModeloWorkbenchFormProjectionV1>(`modelo-${name}-${language}`);
const list = (language: Language = "en") =>
  envelope<ModeloDeclarationsListProjectionV1>(`declarations-${language}`);

/** Every box of a form, in the order its pages hold them. */
function fields(page: unknown): PublicModeloFormField[] {
  const found: PublicModeloFormField[] = [];
  const walk = (node: unknown) => {
    if (Array.isArray(node)) node.forEach(walk);
    else if (node && typeof node === "object") {
      if ("held_zero" in node && "box" in node)
        found.push(node as PublicModeloFormField);
      Object.values(node).forEach(walk);
    }
  };
  walk(page);
  return found;
}

async function openList(
  target: Page,
  { shape = "", language = "en" }: { shape?: string; language?: Language } = {},
) {
  await target.goto(
    `/scenarios.html?scenario=ledger&latency=0&bar=off&lang=${language}${shape ? `&modelo=${shape}` : ""}`,
  );
  await target.locator("[data-rail=declarations]").click();
  const grid = declarations(target, language);
  // The list is one large read; under a loaded host it takes a while.
  await expect(grid.getByRole("row").nth(1)).toBeVisible({ timeout: 15_000 });
  return grid;
}

const declarations = (target: Page, language: Language) =>
  target.getByRole("grid", {
    name: label("workspace.declarations.destination.overview", {}, language),
  });

/** The list's rows for one modelo, found by its printed number. */
const rowsOf = (grid: Locator, modelo: string) =>
  grid.getByRole("row").filter({
    has: grid.page().getByRole("gridcell", { name: modelo, exact: true }),
  });

async function openDeclaration(
  target: Page,
  modelo: string,
  options: { shape?: string; language?: Language } = {},
) {
  const grid = await openList(target, options);
  // The row of the declaration worked here, not one the calendar or the
  // AEAT lists for another period.
  const local = list(options.language).rows.find(
    (row) => row.modelo === modelo && row.opens_local_work,
  );
  if (!local) throw new Error(`no local declaration of ${modelo} is listed`);
  // The list is drawn in windows: find the modelo first, as the filer would.
  await target
    .getByRole("searchbox", {
      name: label("desktop.declarations.search.label", {}, options.language),
    })
    .fill(modelo);
  await rowsOf(grid, modelo)
    .filter({ hasText: local.period_words ?? local.modelo_title })
    .filter({ hasText: local.state_words })
    .first()
    .dblclick();
  await expect(views(target, options.language)).toBeVisible();
}

/** The declaration a creation target already holds, opened from the
 * new-declaration dialog: the way to a declaration the list could not read. */
async function openFromDialog(
  target: Page,
  modelo: string,
  language: Language = "en",
) {
  await openList(target, { language });
  const existing = list(language).creation_targets.find(
    (entry) => entry.modelo === modelo && entry.existing,
  );
  if (!existing) throw new Error(`no declaration of ${modelo} to open`);
  await target
    .getByRole("button", {
      name: label("workspace.declarations.list.key.new", {}, language),
    })
    .first()
    .click();
  const dialog = target.getByRole("dialog");
  await dialog.getByText(existing.modelo_title, { exact: true }).click();
  await dialog.getByRole("radio", { name: existing.period_words }).click();
  await dialog
    .getByRole("button", {
      name: label("workspace.declarations.list.new.open_it", {}, language),
    })
    .click();
  await expect(views(target, language)).toBeVisible();
}

const views = (target: Page, language: Language = "en") =>
  target.getByRole("tablist", {
    name: label("desktop.modelo.views.label", {}, language),
  });
const tab = (target: Page, key: string, language: Language = "en") =>
  views(target, language).getByRole("tab", {
    name: new RegExp(`^${label(key, {}, language)}`),
  });
const VIEW_KEYS = [
  "desktop.modelo.view.form",
  "workspace.modelo.step.review",
  "workspace.modelo.filing.title",
  "workspace.modelo.key.sources",
  "workspace.modelo.history.title",
] as const;

/** The declaration's view panel, which its view tabs control. */
const formPanel = (target: Page) =>
  target
    .getByRole("tabpanel")
    .filter({ has: target.getByRole("row") })
    .first();

/** The row of a box on the form's open page, found by its printed number. */
const boxRow = (target: Page, box: string) =>
  formPanel(target)
    .getByRole("row")
    .filter({
      has: target.getByRole("gridcell", { name: box, exact: true }),
    });

// -- the raw-identifier gate ---------------------------------------------

/** What must never reach the screen, each by what it would reveal. */
const RAW: readonly (readonly [string, string])[] = [
  [
    "catalogue key",
    String.raw`\b(?:workspace|desktop|application|common|cli)\.[a-z0-9_]+\.[a-z0-9_.]+`,
  ],
  ["definition id", String.raw`\bmodelo\.[a-z_]+(?:\.[a-z_]+)*`],
  ["binding id", String.raw`\b(?:modelo-\d{3}-[a-z0-9-]+|irpf\.[a-z_.]+)`],
  ["legal reference id", String.raw`\b[a-z]+(?:-[a-z0-9]+)*:art-[0-9a-z-]+`],
  ["enum token", String.raw`\b[a-z0-9]+(?:_[a-z0-9]+)+\b`],
  ["hexadecimal identifier", String.raw`\b[0-9a-f]{16,}\b`],
  // The box chip names a box; the terminal's "[nn]" notation never does here.
  ["bracketed box id", String.raw`\[\d{1,4}\]`],
  ["unfilled placeholder", String.raw`\{[a-z_]+\}`],
  ["unrendered value", String.raw`\b(?:undefined|NaN)\b|\[object Object\]`],
];

/** Every raw catalogue key or internal identifier the declarations surface
 * and its dialogs show, or name to assistive technology. The rest of the
 * shell (its logs, console and agent) is checked by its own scenarios. */
async function rawOnScreen(target: Page, language: Language = "en") {
  return target.evaluate(
    ([patterns, surface]) => {
      const roots = [
        ...document.querySelectorAll(
          `section[aria-label="${CSS.escape(surface)}"], [role="dialog"], [role="tooltip"]`,
        ),
      ] as HTMLElement[];
      const said = roots.map((root) => root.innerText);
      for (const root of roots)
        for (const element of [root, ...root.querySelectorAll("*")])
          for (const name of [
            "aria-label",
            "aria-description",
            "aria-valuetext",
            "title",
            "placeholder",
            "alt",
          ]) {
            const value = element.getAttribute(name);
            if (value) said.push(value);
          }
      const found: string[] = [];
      for (const [kind, source] of patterns) {
        const pattern = new RegExp(source, "g");
        for (const text of said)
          for (const match of text.matchAll(pattern))
            found.push(`${kind}: ${match[0]}`);
      }
      return [...new Set(found)];
    },
    [
      RAW,
      label("workspace.declarations.destination.overview", {}, language),
    ] as const,
  );
}

async function expectNothingRaw(target: Page, language: Language = "en") {
  expect(await rawOnScreen(target, language)).toEqual([]);
}

/** Every view of the open declaration, each checked once shown. */
async function everyView(
  target: Page,
  language: Language,
  check: () => Promise<void>,
) {
  for (const key of VIEW_KEYS) {
    await tab(target, key, language).click();
    await expect(tab(target, key, language)).toHaveAttribute(
      "aria-selected",
      "true",
    );
    await check();
  }
}

// -- the states ------------------------------------------------------------

test("a modelo whose rules are incomplete opens read only, without a next step", async ({
  page: target,
}) => {
  const read = form("390-0A");
  await openFromDialog(target, "390");
  const banner = target
    .getByRole("status")
    .filter({ hasText: label("workspace.modelo.editor.rules_incomplete") });
  await expect(banner).toBeVisible();
  // The read model names no next step and no result box for it.
  expect(read.next_step).toBeNull();
  for (const action of ["calculate", "verify", "resolve", "fill", "export"])
    await expect(
      target.getByRole("button", {
        name: label(`workspace.modelo.next_button.${action}`),
      }),
    ).toHaveCount(0);
  await expect(
    target.getByText(label("workspace.modelo.header.result.no_result_box")),
  ).toBeVisible();
  if (read.header.deadline)
    await expect(
      target.getByText(read.header.deadline.text, { exact: true }),
    ).toBeVisible();
  // Nothing on the form takes a value.
  await expect(formPanel(target).getByRole("textbox")).toHaveCount(0);
  await expect(
    target.getByText(label("workspace.modelo.editability.no_admission")),
  ).toHaveCount(0);
});

test("a filled Modelo 130 shows its figures, and its held zeros as zero", async ({
  page: target,
}) => {
  const filled = fields(form("130-1T-filed").form.form.pages);
  const figure = filled.find(
    (field) => field.box && !field.held_zero && field.value?.kind === "decimal",
  );
  const held = filled.find((field) => field.box && field.held_zero);
  if (!figure?.value_text || !held?.value_text)
    throw new Error("the filed 130 holds no figure and no held zero");
  await openDeclaration(target, "130", { shape: "filed" });
  await expect(boxRow(target, figure.box!)).toContainText(figure.value_text);
  await expect(boxRow(target, held.box!)).toContainText(held.value_text);
  // The header states the result the read model stated.
  const result = form("130-1T-filed").header.result;
  if (result?.amount_text)
    await expect(
      target.getByText(result.amount_text, { exact: true }).first(),
    ).toBeVisible();
});

test("a box with no value is drawn as missing, never as a zero", async ({
  page: target,
}) => {
  const draft = form("303-1T");
  // A box on its own line, as the first page lists it.
  const missing = draft.form.form.pages[0]!.sections.flatMap(
    (section) => section.blocks,
  )
    .flatMap((block) => (block.kind === "field" ? [block.field] : []))
    .find(
      (field) =>
        field.box &&
        (field.value === null || field.value.kind === "null") &&
        !field.value_text,
    );
  if (!missing) throw new Error("the 303's first page has no missing box");
  await openDeclaration(target, "303");
  // The form draws its sections as they scroll in: find the box by number.
  await target
    .getByRole("searchbox", { name: label("desktop.modelo.search.label") })
    .fill(missing.box!);
  const row = boxRow(target, missing.box!);
  await expect(row).toContainText("—");
  await expect(row).not.toContainText(/\b0[.,]00\b/);
});

test("the check lists every finding under its level, with its technical codes on request", async ({
  page: target,
}) => {
  const read = form("130-1T-checked");
  await openDeclaration(target, "130", { shape: "checked" });
  await tab(target, "workspace.modelo.step.review").click();
  await expect(target.getByText(read.verdict.words)).toBeVisible();
  for (const line of read.issue_lines) {
    const level = target.getByRole("region", {
      name: label(`workspace.modelo.level.${line.level}`),
    });
    const item = level.getByRole("listitem").filter({ hasText: line.message });
    await expect(item).toContainText(line.action);
    const codes = item.getByText(line.technical, { exact: true });
    await expect(codes).toBeHidden();
    await item
      .getByText(label("workspace.modelo.issues.technical"), { exact: true })
      .click();
    await expect(codes).toBeVisible();
  }
});

test("a file made before the declaration changed is out of date and is to be made again", async ({
  page: target,
}) => {
  const read = form("130-1T-stale");
  if (!read.header.file || read.header.file.current)
    throw new Error("the stale 130 has no out-of-date file");
  await openDeclaration(target, "130", { shape: "stale" });
  await expect(target.getByText(read.header.file.words)).toBeVisible();
  await target
    .getByRole("button", {
      name: label("workspace.modelo.next_button.export_again"),
    })
    .click();
  await expect(tab(target, "workspace.modelo.filing.title")).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(
    target.getByText(label("workspace.modelo.filing.file_earlier")),
  ).toBeVisible();
  await expect(
    target.getByRole("button", {
      name: label("workspace.modelo.filing.export_again"),
    }),
  ).toBeEnabled();
});

test("a filing recorded without a verified receipt asks for it", async ({
  page: target,
}) => {
  const read = form("130-1T-filed");
  if (!read.receipt || read.receipt.verified)
    throw new Error("the filed 130's receipt is not unverified");
  await openDeclaration(target, "130", { shape: "filed" });
  await expect(target.getByText(read.receipt.words).first()).toBeVisible();
  await target
    .getByRole("button", {
      name: label("workspace.modelo.next_button.add_receipt"),
    })
    .click();
  await expect(tab(target, "workspace.modelo.filing.title")).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(
    target.getByRole("button", {
      name: label("workspace.modelo.filing.add_receipt_pdf"),
    }),
  ).toBeEnabled();
  await expect(
    target.getByText(label("workspace.modelo.filing.not_confirmed_yet")),
  ).toBeVisible();
  // It is recorded here: nothing offers to record it again.
  await expect(
    target.getByRole("button", {
      name: label("workspace.modelo.filing.record_as_filed"),
    }),
  ).toHaveCount(0);
});

test("a filing whose receipt is verified says when, and asks for nothing", async ({
  page: target,
}) => {
  const read = form("130-1T-receipt");
  if (!read.receipt?.verified)
    throw new Error("the receipt 130's receipt is not verified");
  await openDeclaration(target, "130", { shape: "receipt" });
  await expect(target.getByText(read.receipt.words).first()).toBeVisible();
  await expect(
    target.getByRole("button", {
      name: label("workspace.modelo.next_button.add_receipt"),
    }),
  ).toHaveCount(0);
  await tab(target, "workspace.modelo.filing.title").click();
  await expect(
    target.getByRole("button", {
      name: label("workspace.modelo.filing.add_receipt_pdf"),
    }),
  ).toBeDisabled();
});

test("a row that may apply says why and opens nothing", async ({
  page: target,
}) => {
  const maybe = list().rows.filter((row) => row.group === "maybe");
  expect(maybe.length).toBeGreaterThan(0);
  const grid = await openList(target);
  const row = maybe[0]!;
  await target
    .getByRole("searchbox", {
      name: label("desktop.declarations.search.label"),
    })
    .fill(row.modelo);
  await expect(
    grid.getByRole("row").filter({ hasText: row.group_words }),
  ).toBeVisible();
  const shown = rowsOf(grid, row.modelo).filter({ hasText: row.state_words });
  await expect(shown).toBeVisible();
  if (row.advice_words) await expect(shown).toContainText(row.advice_words);
  await shown.dblclick();
  if (row.help_words)
    await expect(
      target.getByRole("status").filter({ hasText: row.help_words }),
    ).toBeVisible();
  await expect(views(target)).toHaveCount(0);
});

test("a return the AEAT holds that nothing here is linked to opens to read only", async ({
  page: target,
}) => {
  const aeat = list().rows.find((row) => row.group === "aeat_unlinked");
  if (!aeat) throw new Error("the list holds no return seen only at the AEAT");
  const grid = await openList(target);
  await target
    .getByRole("searchbox", {
      name: label("desktop.declarations.search.label"),
    })
    .fill(aeat.modelo);
  await expect(
    grid.getByRole("row").filter({ hasText: aeat.group_words }).first(),
  ).toBeVisible();
  await rowsOf(grid, aeat.modelo)
    .filter({ hasText: aeat.state_words })
    .dblclick();
  const dialog = target.getByRole("dialog", { name: aeat.modelo_title });
  await expect(dialog).toContainText(aeat.state_words);
  if (aeat.period_words) await expect(dialog).toContainText(aeat.period_words);
  for (const note of aeat.aeat_filing?.notes ?? [])
    await expect(dialog).toContainText(note);
  // Nothing is linked, made or sent from it: closing is all it offers.
  for (const name of await dialog.getByRole("button").allInnerTexts())
    expect([label("workspace.modelo.key.close"), ""]).toContain(name.trim());
  await expect(views(target)).toHaveCount(0);
});

// -- every language, and the gate ------------------------------------------

for (const language of LANGUAGES) {
  test(`the list speaks ${language} and shows nothing raw`, async ({
    page: target,
  }) => {
    await openList(target, { language });
    await expect(target.locator("html")).toHaveAttribute("lang", language);
    const read = list(language);
    expect(read.output_language).toBe(language);
    await expect(
      target.getByText(read.rows[0]!.state_words).first(),
    ).toBeVisible();
    await expectNothingRaw(target, language);
    await target
      .getByRole("button", {
        name: label("workspace.declarations.list.key.new", {}, language),
      })
      .first()
      .click();
    await expect(target.getByRole("dialog")).toBeVisible();
    await expectNothingRaw(target, language);
  });

  for (const [name, shape, modelo] of [
    ["130-1T", "", "130"],
    ["130-1T-checked", "checked", "130"],
    ["130-1T-filed", "filed", "130"],
    ["130-1T-receipt", "receipt", "130"],
    ["130-1T-stale", "stale", "130"],
    ["303-1T", "", "303"],
    ["347-0A", "", "347"],
  ] as const)
    test(`modelo ${name} speaks ${language} in every view and shows nothing raw`, async ({
      page: target,
    }) => {
      const read = form(name, language);
      expect(read.form.form.language).toBe(language);
      await openDeclaration(target, modelo, { shape, language });
      if (read.header.deadline)
        await expect(
          target.getByText(read.header.deadline.text, { exact: true }),
        ).toBeVisible();
      await everyView(target, language, () =>
        expectNothingRaw(target, language),
      );
    });

  test(`modelo 390 speaks ${language} in every view and shows nothing raw`, async ({
    page: target,
  }) => {
    await openFromDialog(target, "390", language);
    await expect(
      target
        .getByText(
          label("workspace.modelo.editor.rules_incomplete", {}, language),
        )
        .first(),
    ).toBeVisible();
    await everyView(target, language, () => expectNothingRaw(target, language));
  });
}

test("the gate sees a raw key, an identifier and an enum token", async ({
  page: target,
}) => {
  // The gate's own proof: each kind it refuses is found when present.
  await target.goto("/scenarios.html?scenario=ledger&latency=0&bar=off");
  await target.evaluate(() => {
    const probe = document.createElement("p");
    probe.setAttribute("role", "dialog");
    probe.textContent =
      "workspace.modelo.issues.title modelo.work.form calculation_failed " +
      "ley-58-2003:art-119 modelo-130-pagos-fraccionados-anteriores [19] {date}";
    document.body.append(probe);
  });
  const found = await rawOnScreen(target);
  for (const kind of [
    "catalogue key",
    "definition id",
    "enum token",
    "legal reference id",
    "binding id",
    "bracketed box id",
    "unfilled placeholder",
  ])
    expect(found.some((entry) => entry.startsWith(`${kind}:`))).toBe(true);
});
