import { expect, type Locator, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import type { ModeloDeclarationsListProjectionV1 } from "../../src/shell/modeloContract/modeloDeclarations";
import type {
  ModeloWorkbenchFormProjectionV1,
  PublicModeloFormContextFieldBlock,
  PublicModeloFormField,
} from "../../src/shell/modeloContract/modeloWorkForm";
import { label } from "./strings";
import { MODELO_FIXTURES } from "./windowFixtures";

declare global {
  interface Window {
    __modeloHelpGate?: { failed: boolean; reads: number };
    __modeloWorkRecovery?: { terminal: boolean; failReads: number };
    __modeloCompared?: {
      sourceKind: string;
      calculation: string | null;
      count: number;
    };
    __modeloFileGate?: {
      release: () => void;
      tokens: string[];
      forgotten: string[];
    };
  }
}

export const LANGUAGES = ["en", "es", "ca", "hu"] as const;
export type Language = (typeof LANGUAGES)[number];

export const FIXTURES = fileURLToPath(MODELO_FIXTURES);
export const envelope = <Envelope>(name: string): Envelope =>
  JSON.parse(readFileSync(`${FIXTURES}${name}.json`, "utf8")) as Envelope;
export const form = (name: string, language: Language = "en") =>
  envelope<ModeloWorkbenchFormProjectionV1>(`modelo-${name}-${language}`);
export const list = (language: Language = "en") =>
  envelope<ModeloDeclarationsListProjectionV1>(`declarations-${language}`);

/** The declaration the producer chose, from the registry, to open with rules
 * short of calculation grade: the scenarios name it by this role, not by a
 * modelo. */
export const rulesIncomplete = envelope<{
  modelo: string;
  period_code: string;
  work_unit_id: string;
}>("scenario-rules-incomplete");

/** The name the exported 130's filing file is saved under, as the window
 * names it from the declaration's period. */
export const FILING_FILE = (() => {
  const read = form("130-1T-exported").form.form;
  return `modelo-${read.modelo}-${read.period.filing_year}-${read.period.code}.boe`;
})();

/** Every box of a form, in the order its pages hold them. */
export function fields(page: unknown): PublicModeloFormField[] {
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

export function contextFacts(
  node: unknown,
): PublicModeloFormContextFieldBlock[] {
  if (Array.isArray(node)) return node.flatMap(contextFacts);
  if (!node || typeof node !== "object") return [];
  if ("kind" in node && node.kind === "context_field")
    return [node as PublicModeloFormContextFieldBlock];
  return Object.values(node).flatMap(contextFacts);
}

export async function openList(
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

export const declarations = (target: Page, language: Language) =>
  target.getByRole("grid", {
    name: label("workspace.declarations.destination.overview", {}, language),
  });

/** The list's rows for one modelo, found by its printed number. */
export const rowsOf = (grid: Locator, modelo: string) =>
  grid.getByRole("row").filter({
    has: grid.page().getByRole("gridcell", { name: modelo, exact: true }),
  });

export async function openDeclaration(
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
export async function openFromDialog(
  target: Page,
  modelo: string,
  language: Language = "en",
  shape = "",
) {
  await openList(target, { language, shape });
  // A named shape lists what the host serves for it, not the stored default.
  const served = shape
    ? await target.evaluate(
        async (asked) => window.__fixtureModelo!.declarations(asked),
        language,
      )
    : list(language);
  const existing = served.creation_targets.find(
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

export const views = (target: Page, language: Language = "en") =>
  target.getByRole("tablist", {
    name: label("desktop.modelo.views.label", {}, language),
  });
export const tab = (target: Page, key: string, language: Language = "en") =>
  views(target, language).getByRole("tab", {
    name: new RegExp(`^${label(key, {}, language)}`),
  });
export const VIEW_KEYS = [
  "desktop.modelo.view.form",
  "workspace.modelo.step.review",
  "workspace.modelo.filing.title",
  "workspace.modelo.key.sources",
  "workspace.modelo.history.title",
] as const;

/** The declaration's view panel, which its view tabs control. */
export const formPanel = (target: Page) =>
  target
    .getByRole("tabpanel")
    .filter({ has: target.getByRole("row") })
    .first();

/** The row of a box on the form's open page, found by its printed number. */
export const boxRow = (target: Page, box: string) =>
  formPanel(target)
    .getByRole("row")
    .filter({
      has: target.getByRole("gridcell", { name: box, exact: true }),
    });

// -- the raw-identifier gate ---------------------------------------------

/** What must never reach the screen, each by what it would reveal. */
export const RAW: readonly (readonly [string, string])[] = [
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
export async function rawOnScreen(target: Page, language: Language = "en") {
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

export async function expectNothingRaw(
  target: Page,
  language: Language = "en",
) {
  expect(await rawOnScreen(target, language)).toEqual([]);
}

/** Every view of the open declaration, each checked once shown. */
export async function everyView(
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
