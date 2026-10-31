import { expect, test, type Locator, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import type {
  ModeloDeclarationsListProjectionV1,
  ModeloWorkbenchFormProjectionV1,
  PublicModeloFormField,
} from "../../src/shell/modeloContract";
import { ASSET_NOTES } from "../../src/dev/modeloAssetNotes";
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

test("the check lists every finding under its level, in plain words only", async ({
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
    await expect(item).not.toContainText(line.technical);
  }
});

/** What the catalogue says of one calculation note: its own sentence with its
 * values, and the kind of thing it is. */
const noteWords = (
  note: (typeof ASSET_NOTES)[number],
  language: Language = "en",
) => ({
  fact: label(
    `application.modelo.calc_diagnostic_fact.${note.fact.sentence}`,
    Object.fromEntries(note.fact.values),
    language,
  ),
  kind: label(
    `application.modelo.calc_diagnostic.${note.reason}.what`,
    {},
    language,
  ),
});

test("the check draws each asset note as its own line to read, asking for nothing and counting nothing", async ({
  page: target,
}) => {
  const read = form("130-1T-checked");
  await openDeclaration(target, "130", { shape: "check-notes" });
  await tab(target, "workspace.modelo.step.review").click();
  const level = target.getByRole("region", {
    name: label("workspace.modelo.level.check"),
  });
  // Two elements with a gap of one kind are two lines, each stating its own
  // element and dates, and the kind of thing it is as the second line.
  for (const note of ASSET_NOTES) {
    const words = noteWords(note);
    const item = level.getByRole("listitem").filter({ hasText: words.fact });
    await expect(item).toHaveCount(1);
    await expect(item).toContainText(words.kind);
    // It leads nowhere to fill, and it is not a button to press.
    await expect(item.getByRole("button")).toHaveCount(0);
  }
  await expect(level.getByRole("listitem")).toHaveCount(ASSET_NOTES.length);
  // The verdict and the counts are the read model's, as without the notes.
  await expect(target.getByText(read.verdict.words)).toBeVisible();
  expect(read.verdict.status).toBe("blocked");
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

// -- writes ------------------------------------------------------------------
// Each write answers what the application answered for it (envelopes under
// src/dev/fixtures/modelo/ read through the registered operations); a write
// whose settlement was not seen, or that was refused before it ran, is the
// host's own answer.

/** The scenario host's call lines that are `line`, or `line` and what it
 * names after it, such as a file's kind. */
const calls = async (target: Page, line: string) =>
  (await target.evaluate(() => window.__scenarioHostCalls ?? [])).filter(
    (call) => call === line || call.startsWith(`${line} `),
  );

/** Types `text` over a box, as the filer does, and waits until it is staged. */
async function stage(target: Page, box: string, text: string) {
  await boxRow(target, box)
    .getByRole("gridcell")
    .nth(2)
    .getByRole("button")
    .click();
  const entry = target.getByRole("textbox", {
    name: label("workspace.modelo.editor.new_value_for_box", { box }),
  });
  await entry.fill(text);
  await entry.press("Enter");
  await expect(boxRow(target, box)).toContainText(
    label("workspace.modelo.attention.staged"),
  );
}

/** Opens the review of what is staged, and waits until the check answers. */
async function review(target: Page, count = 1) {
  await target
    .getByRole("button", { name: label("workspace.modelo.next_button.apply") })
    .first()
    .click();
  await expect(
    target.getByRole("dialog", {
      name: label("workspace.modelo.review.title", { count }),
    }),
  ).toBeVisible();
  // Its title counts what is staged, which an apply clears.
  const dialog = target.getByRole("dialog");
  await expect(
    dialog.getByText(label("workspace.modelo.review.checking")),
  ).toHaveCount(0);
  return dialog;
}

const applyButton = (dialog: Locator) =>
  dialog.getByRole("button", { name: label("workspace.modelo.review.apply") });

/** The value the producer's edits stage on box 06, as the filer types it. */
const TYPED_06 = "1.234,56";

test("an applied edit settles, clears what was staged and shows what was stored", async ({
  page: target,
}) => {
  const after = fields(form("130-1T-applied").form.form.pages).find(
    (field) => field.box === "06",
  );
  if (!after?.value_text) throw new Error("the applied 130 holds no box 06");
  await openDeclaration(target, "130", { shape: "edit" });
  await stage(target, "06", TYPED_06);
  const dialog = await review(target);
  await applyButton(dialog).click();
  await expect(
    dialog.getByText(label("workspace.modelo.operation.done")),
  ).toBeVisible();
  await dialog
    .getByRole("button", { name: label("workspace.modelo.key.close") })
    .last()
    .click();
  await expect(boxRow(target, "06")).toContainText(after.value_text);
  await expect(boxRow(target, "06")).not.toContainText(
    label("workspace.modelo.attention.staged"),
  );
  expect(await calls(target, "modelo edit modelo.edit.apply")).toHaveLength(1);
});

test("staged edits survive a renewal of a baseline that went stale", async ({
  page: target,
}) => {
  const stale = envelope<{
    outcome: { outcome: string; refusal?: { kind: string } };
  }>("preflight-130-1T-expiring-stale");
  expect(stale.outcome.refusal?.kind).toBe("stale_edit_baseline");
  await openDeclaration(target, "130", { shape: "renewal" });
  await stage(target, "06", TYPED_06);
  const dialog = await review(target);
  // The check answered stale, the baseline was renewed, the declaration read
  // again and the edits checked again: nothing staged was lost.
  const sequence = (
    await target.evaluate(() => window.__scenarioHostCalls ?? [])
  ).filter(
    (call) =>
      call === "modelo edit modelo.edit.preflight" ||
      call === "modelo submit modelo.edit.renew" ||
      call.startsWith("modelo form "),
  );
  const renewed = sequence.indexOf("modelo submit modelo.edit.renew");
  expect(sequence.slice(renewed - 1, renewed + 3)).toEqual([
    "modelo edit modelo.edit.preflight",
    "modelo submit modelo.edit.renew",
    "modelo form en",
    "modelo edit modelo.edit.preflight",
  ]);
  expect(await calls(target, "modelo submit modelo.edit.renew")).toHaveLength(
    1,
  );
  await expect(dialog.getByRole("listitem")).toHaveCount(1);
  await expect(dialog.getByRole("listitem")).toContainText("06");
  // The check on the renewed baseline was evaluated: the edit may be applied.
  await expect(applyButton(dialog)).toBeEnabled();
  await dialog
    .getByRole("button", { name: label("workspace.modelo.review.back") })
    .click();
  await expect(boxRow(target, "06")).toContainText(
    label("workspace.modelo.attention.staged"),
  );
});

test("an apply whose settlement was not seen holds every write until the declaration is read again", async ({
  page: target,
}) => {
  const unknown = (where: Locator | Page) =>
    where.getByRole("alert").filter({
      hasText: label("workspace.modelo.review.unknown"),
    });
  await openDeclaration(target, "130", { shape: "unknown" });
  await stage(target, "06", TYPED_06);
  const dialog = await review(target);
  await applyButton(dialog).click();
  await expect(unknown(dialog)).toBeVisible();
  await expect(applyButton(dialog)).toBeDisabled();
  // Closing and reviewing again sends nothing: it may have committed.
  await dialog
    .getByRole("button", { name: label("workspace.modelo.key.close") })
    .last()
    .click();
  await review(target);
  await expect(unknown(target)).toBeVisible();
  expect(await calls(target, "modelo edit modelo.edit.apply")).toHaveLength(1);
  const preflights = (await calls(target, "modelo edit modelo.edit.preflight"))
    .length;
  // Reading the declaration again releases the hold, and the edits are
  // checked again before anything more is applied.
  await target
    .getByRole("button", { name: label("workspace.modelo.read_again") })
    .click();
  await expect(unknown(target)).toHaveCount(0);
  await expect
    .poll(
      async () =>
        (await calls(target, "modelo edit modelo.edit.preflight")).length,
    )
    .toBeGreaterThan(preflights);
  expect(await calls(target, "modelo edit modelo.edit.apply")).toHaveLength(1);
});

test("a refused apply names the earlier filing it waits on", async ({
  page: target,
}) => {
  const held = envelope<{
    prerequisite: { casilla_id: string; words: string | null } | null;
  }>("apply-prerequisite-130-3T-prerequisite").prerequisite;
  if (!held?.words) throw new Error("the refused apply holds no prerequisite");
  await openDeclaration(target, "130", { shape: "prerequisite" });
  await stage(target, "06", TYPED_06);
  const dialog = await review(target);
  await applyButton(dialog).click();
  await expect(
    dialog.getByText(label("workspace.modelo.operation.not_done")),
  ).toBeVisible();
  for (const line of held.words.split("\n"))
    await expect(dialog).toContainText(line);
  await expect(
    dialog.getByRole("button", {
      name: label("workspace.modelo.apply_prerequisite.action"),
    }),
  ).toBeVisible();
  // Nothing was applied: the edit stays staged.
  await dialog
    .getByRole("button", { name: label("workspace.modelo.review.back") })
    .click();
  await expect(boxRow(target, "06")).toContainText(
    label("workspace.modelo.attention.staged"),
  );
});

/** Opens the Export and record view of the 130 in `shape`. */
async function filing(target: Page, shape: string) {
  await openDeclaration(target, "130", { shape });
  await tab(target, "workspace.modelo.filing.title").click();
}

test("an export writes the file the filer saved, through its save token", async ({
  page: target,
}) => {
  await filing(target, "exported");
  await target
    .getByRole("button", {
      name: label("workspace.modelo.filing.export_again"),
    })
    .click();
  await expect(
    target.getByText(
      label("workspace.modelo.filing.saved", {
        name: "modelo-130-2026-1T.boe",
      }),
    ),
  ).toBeVisible();
  // The file was named in the save dialog and sent as its token; the file
  // the export wrote is shown in its folder.
  expect(await calls(target, "modelo saveFile")).toHaveLength(1);
  expect(await calls(target, "modelo submit modelo.export")).toHaveLength(1);
  await expect(
    target.getByText(label("workspace.modelo.filing.completeness_unverified")),
  ).toHaveCount(0);
  await target
    .getByRole("button", {
      name: label("workspace.modelo.filing.show_in_folder"),
    })
    .click();
  expect(await calls(target, "modelo revealFile")).toHaveLength(1);
});

for (const language of LANGUAGES) {
  test(`an export states what its calculation noted about the assets, in ${language}`, async ({
    page: target,
  }) => {
    await target.goto(
      `/scenarios.html?scenario=ledger&latency=0&bar=off&lang=${language}&modelo=export-notes`,
    );
    await target.locator("[data-rail=declarations]").click();
    const grid = declarations(target, language);
    await expect(grid.getByRole("row").nth(1)).toBeVisible({ timeout: 15_000 });
    const local = list(language).rows.find(
      (row) => row.modelo === "130" && row.opens_local_work,
    );
    if (!local) throw new Error("no local declaration of 130 is listed");
    await target
      .getByRole("searchbox", {
        name: label("desktop.declarations.search.label", {}, language),
      })
      .fill("130");
    await rowsOf(grid, "130")
      .filter({ hasText: local.period_words ?? local.modelo_title })
      .filter({ hasText: local.state_words })
      .first()
      .dblclick();
    await expect(views(target, language)).toBeVisible();
    await tab(target, "workspace.modelo.filing.title", language).click();
    // Nothing is said before a file is made.
    const notes = target.getByRole("region", {
      name: label("workspace.modelo.notes.title", {}, language),
    });
    await expect(notes).toHaveCount(0);
    await target
      .getByRole("button", {
        name: label("workspace.modelo.filing.export_again", {}, language),
      })
      .click();
    await expect(notes).toBeVisible();
    const items = notes.getByRole("listitem");
    await expect(items).toHaveCount(ASSET_NOTES.length);
    // Each note is its own item: its sentence with its values, then its kind.
    for (const note of ASSET_NOTES) {
      const words = noteWords(note, language);
      const item = items.filter({ hasText: words.fact });
      await expect(item).toHaveCount(1);
      await expect(item).toContainText(words.kind);
    }
    await expect(notes.getByRole("button")).toHaveCount(0);
    // No catalogue key and no unfilled value reaches the filer.
    const said = await notes.innerText();
    expect(said).not.toMatch(/application\.modelo|workspace\.modelo|\{\w+\}/);
  });
}

test("an export that cannot vouch for its completeness says so", async ({
  page: target,
}) => {
  expect(
    envelope<{ completeness: string }>("export-165-unverified").completeness,
  ).toBe("unverified");
  await filing(target, "export-unverified");
  await target
    .getByRole("button", {
      name: label("workspace.modelo.filing.export_again"),
    })
    .click();
  await expect(
    target.getByText(label("workspace.modelo.filing.completeness_unverified")),
  ).toBeVisible();
});

test("an export whose settlement was not seen is unknown and holds", async ({
  page: target,
}) => {
  await filing(target, "export-unknown");
  const exportAgain = target.getByRole("button", {
    name: label("workspace.modelo.filing.export_again"),
  });
  await exportAgain.click();
  await expect(
    target.getByText(label("workspace.modelo.outcome.unknown")).first(),
  ).toBeVisible();
  await expect(exportAgain).toBeDisabled();
  expect(await calls(target, "modelo submit modelo.export")).toHaveLength(1);
});

test("recording the filing keeps it local, and a verified receipt is another state", async ({
  page: target,
}) => {
  const recorded = form("130-1T-filed").receipt;
  const verified = form("130-1T-receipt").receipt;
  if (!recorded || recorded.verified || !verified?.verified)
    throw new Error("the recorded and the verified 130 do not differ");
  await filing(target, "exported");
  await target
    .getByRole("button", {
      name: label("workspace.modelo.filing.record_as_filed"),
    })
    .click();
  await target
    .getByRole("dialog")
    .getByRole("button", {
      name: label("application.modelo.lifecycle.file_confirm_accept"),
    })
    .click();
  await expect(
    target.getByText(label("workspace.modelo.filing.recorded_here")).first(),
  ).toBeVisible();
  expect(await calls(target, "modelo submit modelo.work.file")).toHaveLength(1);
  // Recorded here, its receipt not verified: the AEAT's side is still open.
  await expect(target.getByText(recorded.words).first()).toBeVisible();
  await expect(
    target.getByText(label("workspace.modelo.filing.not_confirmed_yet")),
  ).toBeVisible();
  await expect(target.getByText(verified.words)).toHaveCount(0);
});

test("a receipt imported against the filing says whether it matches", async ({
  page: target,
}) => {
  const imported = envelope<{ verdict: string; narrative: string }>(
    "reconcile-130",
  );
  await filing(target, "filed");
  await target
    .getByRole("button", {
      name: label("workspace.modelo.filing.add_receipt_pdf"),
    })
    .click();
  await expect(
    target.getByText(
      label(
        imported.verdict === "matches"
          ? "workspace.modelo.filing.receipt_matches"
          : "workspace.modelo.filing.receipt_differs",
      ),
    ),
  ).toBeVisible();
  await expect(target.getByText(imported.narrative)).toBeVisible();
  expect(await calls(target, "modelo pickFile evidence")).toHaveLength(1);
});

/** Opens the correction of the receipt-confirmed 130 in `shape` and sends
 * one corrected figure, with the reason. */
async function correct(target: Page, shape: string, figure: string) {
  const context = envelope<{
    correction: {
      reason_prompt: string;
      rows: { casilla_id: string; box: string | null; label: string }[];
    };
  }>("amendment-context-130").correction;
  await openDeclaration(target, "130", { shape });
  await target
    .getByRole("button", { name: label("workspace.modelo.correction.title") })
    .first()
    .click();
  const dialog = target.getByRole("dialog", {
    name: label("workspace.modelo.correction.title"),
  });
  await dialog
    .getByRole("textbox", { name: context.reason_prompt })
    .fill("A deductible expense was left out.");
  const row = context.rows.find((entry) => entry.casilla_id === "06")!;
  await dialog
    .getByRole("textbox", {
      name: label("workspace.modelo.editor.new_value_for_box", {
        box: row.box ?? row.label,
      }),
    })
    .fill(figure);
  await dialog
    .getByRole("button", { name: label("workspace.modelo.correction.confirm") })
    .click();
  return dialog;
}

test("a correction that settles closes and the declaration is read again", async ({
  page: target,
}) => {
  const dialog = await correct(target, "receipt", "150");
  await expect(dialog).toBeHidden();
  expect(await calls(target, "modelo submit modelo.work.amend")).toHaveLength(
    1,
  );
});

test("a corrected figure the application cannot read is said beside it, and nothing is sent", async ({
  page: target,
}) => {
  const read = envelope<{ parsed: { refusal_words: string | null }[] }>(
    "preflight-130-1T-receipt-correction-refused",
  ).parsed[0];
  if (!read?.refusal_words)
    throw new Error("the unreadable entry has no words");
  const dialog = await correct(target, "receipt", "doce");
  await expect(dialog).toContainText(read.refusal_words);
  expect(await calls(target, "modelo submit modelo.work.amend")).toHaveLength(
    0,
  );
});

test("a refused correction says so and keeps the dialog", async ({
  page: target,
}) => {
  const dialog = await correct(target, "correction-refused", "150");
  await expect(dialog).toBeVisible();
  // The sentence does not name the code the host refused it with.
  await expect(dialog).toContainText(label("workspace.modelo.outcome.refused"));
  await expect(dialog).not.toContainText("operation_denied");
});

test("a correction whose settlement was not seen is unknown and sends nothing more", async ({
  page: target,
}) => {
  const dialog = await correct(target, "correction-unknown", "150");
  await expect(dialog).toContainText(label("workspace.modelo.outcome.unknown"));
  await expect(
    dialog.getByRole("button", {
      name: label("workspace.modelo.correction.confirm"),
    }),
  ).toBeDisabled();
  expect(await calls(target, "modelo submit modelo.work.amend")).toHaveLength(
    1,
  );
});

test("the real Modelo 303 takes a typed value and checks it as staged", async ({
  page: target,
}) => {
  const typed = envelope<{
    parsed: { value_text: string | null }[];
  }>("preflight-303-1T-entry-42").parsed[0];
  if (!typed?.value_text) throw new Error("the 303 entry read no value");
  await openDeclaration(target, "303");
  // The form draws its sections as they scroll in: find the box by number.
  await target
    .getByRole("searchbox", { name: label("desktop.modelo.search.label") })
    .fill("42");
  // The application read the entry as a figure; the box says it as typed.
  await stage(target, "42", "1.234,56");
  await expect(boxRow(target, "42")).toContainText("1.234,56");
  const dialog = await review(target);
  await expect(dialog.getByRole("listitem")).toContainText("42");
  await expect(applyButton(dialog)).toBeVisible();
  // Each body the window sent was within the host's bound and answered.
  await expect(
    dialog.getByText(label("workspace.modelo.review.check_failed")),
  ).toHaveCount(0);
});

// -- a declaration that moved under the staged edits -------------------------

type RebaseEntry = {
  address: { kind: string; casilla_id?: string };
  kind: string;
  outcome: "kept" | "changed" | "dropped";
};

/** What the check on the declaration read again found of the change held
 * on the box printed `box`, as the application judged it. */
function rebaseOf(box: string): RebaseEntry["outcome"] {
  const entry = envelope<{ rebase: RebaseEntry[] }>(
    "preflight-130-1T-rebased-review-06clear-08set-10set-from-130-1T-rebase",
  ).rebase.find((item) => item.address.casilla_id === box);
  if (!entry) throw new Error(`the review says nothing of box ${box}`);
  return entry.outcome;
}

/** Stages, on the read the declaration then moves under, a clear of box 06
 * and typed values in boxes 08 and 10, and opens their review. */
async function stageUnderRebase(target: Page) {
  await openDeclaration(target, "130", { shape: "rebase" });
  // The filer's own value comes out of a box with Delete on its row.
  await boxRow(target, "06").getByRole("gridcell").nth(1).click();
  await target.keyboard.press("Delete");
  await expect(boxRow(target, "06")).toContainText(
    label("workspace.modelo.staged.clear"),
  );
  await stage(target, "08", "250");
  await stage(target, "10", "75");
  return review(target, 3);
}

test("a declaration that moved under the staged edits says what became of them", async ({
  page: target,
}) => {
  expect([rebaseOf("06"), rebaseOf("08"), rebaseOf("10")]).toEqual([
    "dropped",
    "changed",
    "kept",
  ]);
  const dialog = await stageUnderRebase(target);
  await expect(
    dialog
      .getByRole("alert")
      .or(dialog.getByRole("status"))
      .filter({
        hasText: label("workspace.modelo.rebase.moved"),
      }),
  ).toContainText(
    [
      label("workspace.modelo.rebase.moved"),
      label("workspace.modelo.rebase.changed", { count: 1 }),
      label("workspace.modelo.rebase.dropped", { count: 1 }),
    ].join(" "),
  );
  expect(await calls(target, "modelo submit modelo.edit.renew")).toHaveLength(
    1,
  );
});

test("a staged edit the renewal dropped is no longer staged", async ({
  page: target,
}) => {
  const dialog = await stageUnderRebase(target);
  // Two of the three changes are left to apply.
  await expect(dialog.getByRole("listitem")).toHaveCount(2);
  await expect(
    dialog.getByRole("listitem").filter({ hasText: "06" }),
  ).toHaveCount(0);
  await dialog
    .getByRole("button", { name: label("workspace.modelo.review.back") })
    .click();
  await expect(boxRow(target, "06")).not.toContainText(
    label("workspace.modelo.staged.clear"),
  );
});

test("a staged edit the renewal kept is staged again against the box as it now stands", async ({
  page: target,
}) => {
  const now = fields(form("130-1T-rebased").form.form.pages).find(
    (field) => field.box === "10",
  );
  if (!now) throw new Error("the moved 130 holds no box 10");
  const dialog = await stageUnderRebase(target);
  await dialog
    .getByRole("button", { name: label("workspace.modelo.review.back") })
    .click();
  const row = boxRow(target, "10");
  await expect(row).toContainText(label("workspace.modelo.attention.staged"));
  await expect(row).toContainText(
    label("workspace.modelo.was", { value: now.value_text ?? "—" }),
  );
});

test("a changed edit stays marked until the filer acknowledges it", async ({
  page: target,
}) => {
  const dialog = await stageUnderRebase(target);
  const changed = dialog.getByRole("listitem").filter({ hasText: "08" });
  await expect(changed).toContainText(
    label("workspace.modelo.review.before_changed"),
  );
  await expect(applyButton(dialog)).toBeDisabled();
  // Looking again keeps the mark: it holds until it is acknowledged.
  await dialog
    .getByRole("button", { name: label("workspace.modelo.review.back") })
    .click();
  const again = await review(target, 2);
  await expect(
    again.getByRole("listitem").filter({ hasText: "08" }),
  ).toContainText(label("workspace.modelo.review.before_changed"));
  await expect(applyButton(again)).toBeDisabled();
  await again
    .getByRole("checkbox", {
      name: label("workspace.modelo.review.acknowledge"),
    })
    .check();
  await expect(applyButton(again)).toBeEnabled();
});

test("a stale check whose renewal is refused reads the declaration again once, and the check on it stands", async ({
  page: target,
}) => {
  const stale = envelope<{
    outcome: { refusal?: { kind: string } };
    rebase: RebaseEntry[];
  }>("preflight-130-1T-rebase-stale");
  // The stale refusal says nothing of the held changes; only the check on
  // the declaration read again does.
  expect(stale.outcome.refusal?.kind).toBe("stale_edit_baseline");
  expect(stale.rebase).toEqual([]);
  // More than the baseline's lifetime moved, so renewing it is refused.
  const renewal = envelope<{ renewed_baseline: unknown; refusal: unknown }>(
    "renew-130-1T-rebase",
  );
  expect(renewal.renewed_baseline).toBeNull();
  expect(renewal.refusal).not.toBeNull();
  const dialog = await stageUnderRebase(target);
  // Stale check, the refused renewal, one read of the declaration, the
  // check again.
  const sequence = (
    await target.evaluate(() => window.__scenarioHostCalls ?? [])
  ).filter(
    (call) =>
      call === "modelo edit modelo.edit.preflight" ||
      call === "modelo submit modelo.edit.renew" ||
      call.startsWith("modelo form "),
  );
  const renewed = sequence.indexOf("modelo submit modelo.edit.renew");
  expect(renewed).toBeGreaterThan(0);
  expect(sequence[renewed - 1]).toBe("modelo edit modelo.edit.preflight");
  const after = sequence.slice(renewed + 1);
  expect(after.filter((call) => call.startsWith("modelo form "))).toHaveLength(
    1,
  );
  expect(after[0]).toMatch(/^modelo form /);
  expect(after.slice(1)).toContain("modelo edit modelo.edit.preflight");
  expect(await calls(target, "modelo submit modelo.edit.renew")).toHaveLength(
    1,
  );
  // What the check on the declaration read again reported stands: the
  // dropped change is said, the changed one is marked and holds the apply
  // until it is acknowledged.
  await expect(dialog).toContainText(
    label("workspace.modelo.rebase.dropped", { count: 1 }),
  );
  const changed = dialog.getByRole("listitem").filter({ hasText: "08" });
  await expect(changed).toContainText(
    label("workspace.modelo.review.before_changed"),
  );
  await expect(applyButton(dialog)).toBeDisabled();
  await dialog
    .getByRole("checkbox", {
      name: label("workspace.modelo.review.acknowledge"),
    })
    .check();
  await expect(applyButton(dialog)).toBeEnabled();
});

test("a declaration still changing after it was read again stops after that one read and says so", async ({
  page: target,
}) => {
  // The real sequence: stale on the read the edits were staged on, its
  // renewal refused, and stale again on the declaration read again, since
  // it moved once more.
  for (const name of [
    "preflight-130-1T-rebase-stale",
    "preflight-130-1T-moving-stale",
  ]) {
    const stale = envelope<{
      outcome: { refusal?: { kind: string } };
      rebase: RebaseEntry[];
    }>(name);
    expect(stale.outcome.refusal?.kind).toBe("stale_edit_baseline");
    expect(stale.rebase).toEqual([]);
  }
  await openDeclaration(target, "130", { shape: "moving" });
  await boxRow(target, "06").getByRole("gridcell").nth(1).click();
  await target.keyboard.press("Delete");
  await stage(target, "08", "250");
  await stage(target, "10", "75");
  await target
    .getByRole("button", { name: label("workspace.modelo.next_button.apply") })
    .first()
    .click();
  const dialog = target.getByRole("dialog");
  await expect(dialog).toContainText(
    label("workspace.modelo.rebase.still_moving"),
  );
  // One renewal and one read of the declaration, and nothing after them.
  const sequence = (
    await target.evaluate(() => window.__scenarioHostCalls ?? [])
  ).filter(
    (call) =>
      call === "modelo edit modelo.edit.preflight" ||
      call === "modelo submit modelo.edit.renew" ||
      call.startsWith("modelo form "),
  );
  const renewed = sequence.indexOf("modelo submit modelo.edit.renew");
  expect(sequence.slice(renewed + 1)).toEqual([
    "modelo form en",
    "modelo edit modelo.edit.preflight",
  ]);
  expect(await calls(target, "modelo submit modelo.edit.renew")).toHaveLength(
    1,
  );
  await expect(applyButton(dialog)).toHaveCount(0);
  // The edits are still the filer's: nothing was applied or let go.
  await dialog
    .getByRole("button", { name: label("workspace.modelo.review.back") })
    .click();
  await expect(boxRow(target, "08")).toContainText(
    label("workspace.modelo.attention.staged"),
  );
});

/** Stages the rebase changes in the `moving` shape and reviews them until
 * the window says the declaration is still changing. */
async function stillMoving(target: Page) {
  await openDeclaration(target, "130", { shape: "moving" });
  await boxRow(target, "06").getByRole("gridcell").nth(1).click();
  await target.keyboard.press("Delete");
  await stage(target, "08", "250");
  await stage(target, "10", "75");
  await target
    .getByRole("button", { name: label("workspace.modelo.next_button.apply") })
    .first()
    .click();
  const dialog = target.getByRole("dialog");
  await expect(dialog).toContainText(
    label("workspace.modelo.rebase.still_moving"),
  );
  return dialog;
}

/** The host calls of a review's recovery: checks, renewals and reads. */
const recovery = async (target: Page) =>
  (await target.evaluate(() => window.__scenarioHostCalls ?? [])).filter(
    (call) =>
      call === "modelo edit modelo.edit.preflight" ||
      call === "modelo submit modelo.edit.renew" ||
      call.startsWith("modelo form "),
  );

/** What a review asked of the host after its last renewal. */
async function afterLastRenewal(target: Page) {
  const sequence = await recovery(target);
  return sequence.slice(
    sequence.lastIndexOf("modelo submit modelo.edit.renew") + 1,
  );
}

test("checking again after the declaration is still changing renews and reads once more, then stops", async ({
  page: target,
}) => {
  // Each renewal is refused, and each read finds the declaration moved again.
  for (const name of ["renew-130-1T-rebase", "renew-130-1T-moving"])
    expect(
      envelope<{ renewed_baseline: unknown }>(name).renewed_baseline,
    ).toBeNull();
  const dialog = await stillMoving(target);
  expect(await calls(target, "modelo submit modelo.edit.renew")).toHaveLength(
    1,
  );
  await dialog
    .getByRole("button", { name: label("workspace.modelo.review.check_again") })
    .click();
  await expect(dialog).toContainText(
    label("workspace.modelo.rebase.still_moving"),
  );
  await expect
    .poll(
      async () =>
        (await calls(target, "modelo submit modelo.edit.renew")).length,
    )
    .toBe(2);
  // One more renewal, one more read, the check on it, and nothing after.
  await expect
    .poll(() => afterLastRenewal(target))
    .toEqual(["modelo form en", "modelo edit modelo.edit.preflight"]);
  await expect(applyButton(dialog)).toHaveCount(0);
});

test("reopening the review after the declaration is still changing reads it again once", async ({
  page: target,
}) => {
  const dialog = await stillMoving(target);
  await dialog
    .getByRole("button", { name: label("workspace.modelo.review.back") })
    .click();
  await expect(dialog).toBeHidden();
  await target
    .getByRole("button", { name: label("workspace.modelo.next_button.apply") })
    .first()
    .click();
  const again = target.getByRole("dialog");
  await expect(again).toContainText(
    label("workspace.modelo.rebase.still_moving"),
  );
  await expect
    .poll(
      async () =>
        (await calls(target, "modelo submit modelo.edit.renew")).length,
    )
    .toBe(2);
  await expect
    .poll(() => afterLastRenewal(target))
    .toEqual(["modelo form en", "modelo edit modelo.edit.preflight"]);
  // The edits are still staged throughout.
  await again
    .getByRole("button", { name: label("workspace.modelo.review.back") })
    .click();
  await expect(boxRow(target, "08")).toContainText(
    label("workspace.modelo.attention.staged"),
  );
});
