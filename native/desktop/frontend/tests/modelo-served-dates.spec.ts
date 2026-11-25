import { readFileSync } from "node:fs";
import { expect, test } from "@playwright/test";
import { formatDay } from "../src/shared/dateFormats";
import type { ModeloDeclarationsListProjectionV1 } from "../src/shell/modeloContract/modeloDeclarations";
import { MODELO_FIXTURES } from "./support/windowFixtures";

// A date the application words reads as the window writes one in the same
// language, on the envelopes the application's read path produced.

const list = (language: string) =>
  JSON.parse(
    readFileSync(
      new URL(`declarations-${language}.json`, MODELO_FIXTURES),
      "utf8",
    ),
  ) as ModeloDeclarationsListProjectionV1;

for (const language of ["en", "es", "ca", "hu"])
  test(`the ${language} list's dates read as the window writes them`, () => {
    const served = list(language);
    const rows = served.rows.filter((row) => row.deadline !== null);
    expect(rows.length).toBeGreaterThan(0);
    for (const row of rows) {
      const day = formatDay(language, row.deadline ?? "");
      expect(row.deadline_text).toBe(day);
      if (row.due_words) expect(row.due_words).toContain(day);
    }
    const seen = served.sources.flatMap((source) =>
      source.observed_at ? [source] : [],
    );
    expect(seen.length).toBeGreaterThan(0);
    for (const source of seen)
      expect(source.words).toContain(
        formatDay(language, (source.observed_at ?? "").slice(0, 10)),
      );
  });
