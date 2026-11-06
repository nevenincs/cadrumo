import { expect, test } from "@playwright/test";
import { build } from "esbuild";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import type { ModeloWorkCalculatePublicResultV3 } from "../src/shell/modeloContract/modeloWork";
import { MODELO_FIXTURES } from "./support/windowFixtures";

// What the calculation of a Modelo 130 said it could give no value for, drawn
// from the envelope the application served, in its own words and apart from
// the boxes that hold a figure. The component is compiled here with the
// project's own JSX setting and rendered to markup, because the test runner
// replaces JSX in the files it loads.

const served = JSON.parse(
  readFileSync(new URL("calculate-130.json", MODELO_FIXTURES), "utf8"),
) as ModeloWorkCalculatePublicResultV3;

type Draw = (props: { bindings: unknown[]; casillas: unknown[] }) => string;

async function compiled(): Promise<Draw> {
  const component = fileURLToPath(
    new URL(
      "../src/components/modelo/workspace/UnresolvedFindings.tsx",
      import.meta.url,
    ),
  );
  const built = await build({
    stdin: {
      contents: `
        import { createElement } from "react";
        import { renderToStaticMarkup } from "react-dom/server";
        import { UnresolvedFindings } from ${JSON.stringify(component)};
        export const draw = (props) =>
          renderToStaticMarkup(
            createElement(UnresolvedFindings, {
              ...props,
              bindingsTitle: "inputs",
              casillasTitle: "boxes",
              boxName: (box) => createElement("span", null, box),
            }),
          );
      `,
      resolveDir: fileURLToPath(new URL("..", import.meta.url)),
      loader: "js",
    },
    bundle: true,
    write: false,
    platform: "node",
    format: "cjs",
    jsx: "automatic",
    logLevel: "silent",
  });
  const module = { exports: {} as { draw: Draw } };
  new Function(
    "module",
    "exports",
    "require",
    built.outputFiles.map((file) => file.text).join(""),
  )(module, module.exports, createRequire(import.meta.url));
  return module.exports.draw;
}

const text = (markup: string) =>
  markup
    .replace(/<[^>]+>/g, " ")
    .replace(/&#x27;|&#39;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, "&");

test("the calculation serves findings, and no value for a box it lists", () => {
  expect(served.result_version).toBe(3);
  expect(served.unresolved_bindings.length).toBeGreaterThan(0);
  expect(served.unresolved_casillas.length).toBeGreaterThan(0);
  const valued = new Set(
    served.calculation.casilla_values.map((row) => row.key),
  );
  for (const row of served.unresolved_casillas)
    expect(valued.has(row.casilla_id)).toBe(false);
  for (const row of served.unresolved_bindings)
    if (row.casilla_id) expect(valued.has(row.casilla_id)).toBe(false);
});

test("each unresolved input and box is drawn with the application's words, never a figure", async () => {
  const markup = (await compiled())({
    bindings: served.unresolved_bindings,
    casillas: served.unresolved_casillas,
  });
  const words = text(markup);
  for (const row of served.unresolved_bindings) {
    expect(markup).toContain(`data-unresolved-credit="${row.casilla_id}"`);
    expect(words).toContain(row.words);
    if (row.source_words) expect(words).toContain(row.source_words);
  }
  for (const row of served.unresolved_casillas) {
    expect(markup).toContain(`data-unresolved-box="${row.casilla_id}"`);
    expect(words).toContain(row.reason_words);
  }
  // The window draws no amount for a box that has none.
  expect(words).not.toMatch(/\d+[.,]\d{2}\b/);
  // Boxes left for one reason share the one sentence that says it.
  for (const sentence of new Set(
    served.unresolved_casillas.map((row) => row.reason_words),
  ))
    expect(words.split(sentence)).toHaveLength(2);
});

test("nothing is drawn when the calculation left nothing without a value", async () => {
  expect((await compiled())({ bindings: [], casillas: [] })).toBe("");
});
