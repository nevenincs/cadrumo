import { expect, test } from "@playwright/test";
import type { ModeloFormRecordAttention } from "../../src/shell/modeloContract/modeloWorkForm";
import { label } from "../support/strings";
import { list, openList, rowsOf, views } from "../support/scenarioModelo";

// A section whose tables of records the last check found something about
// shows what the read model counted for it, level by level, beside its
// heading. The window counts nothing itself: each mark is a served level with
// its served count, and a section the read counts nothing for shows no mark.

const SERVED: ModeloFormRecordAttention[] = [
  { level: "check", count: 3, counts_as: "check", asks_filer: false },
  { level: "limitation", count: 1, counts_as: "check", asks_filer: false },
];

declare global {
  interface Window {
    __recordAttention?: { marked: string; quiet: string };
  }
}

test("a section shows the record attention the read model counted for its tables of records", async ({
  page: target,
}) => {
  const grid = await openList(target);
  await target.evaluate((served) => {
    const port = window.__fixtureModelo!;
    const original = port.form;
    port.form = async (...args) => {
      const read = await original(...args);
      const [first, ...rest] = read.form.form.pages;
      const [marked, quiet, ...others] = first?.sections ?? [];
      if (!first || !marked || !quiet)
        throw new Error("the fixture's first page has fewer than two sections");
      window.__recordAttention = {
        marked: marked.heading.text,
        quiet: quiet.heading.text,
      };
      return {
        ...read,
        form: {
          ...read.form,
          form: {
            ...read.form.form,
            pages: [
              {
                ...first,
                sections: [
                  { ...marked, record_attention: served },
                  { ...quiet, record_attention: [] },
                  ...others,
                ],
              },
              ...rest,
            ],
          },
        },
      };
    };
  }, SERVED);
  const local = list().rows.find(
    (row) => row.modelo === "130" && row.opens_local_work,
  );
  if (!local) throw new Error("The fixture has no local 130");
  await target
    .getByRole("searchbox", {
      name: label("desktop.declarations.search.label"),
      exact: true,
    })
    .fill("130");
  await rowsOf(grid, "130")
    .filter({ hasText: local.period_words ?? local.modelo_title })
    .filter({ hasText: local.state_words })
    .first()
    .dblclick();
  await expect(views(target)).toBeVisible();
  const headings = await target.evaluate(() => window.__recordAttention!);

  const marked = target
    .getByRole("group", { name: headings.marked, exact: true })
    .first();
  await expect(marked).toBeVisible();
  const marks = marked.locator("[data-record-attention]");
  await expect(marks).toHaveCount(SERVED.length);
  for (const [index, served] of SERVED.entries()) {
    const mark = marks.nth(index);
    await expect(mark).toHaveAttribute("data-record-attention", served.level);
    await expect(mark).toHaveText(String(served.count));
    await expect(
      mark.getByRole("img", {
        name: label(`workspace.modelo.level.${served.level}`),
        exact: true,
      }),
    ).toBeVisible();
  }

  const quiet = target
    .getByRole("group", { name: headings.quiet, exact: true })
    .first();
  await expect(quiet).toBeVisible();
  await expect(quiet.locator("[data-record-attention]")).toHaveCount(0);
});
