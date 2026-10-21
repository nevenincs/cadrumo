import { expect, test } from "@playwright/test";
import { markdownBlocks } from "../src/components/agent/Markdown";

// How a reply's Markdown is read into blocks. The expected blocks are written
// out from CommonMark and GitHub's table syntax, not taken from the reader.

test.describe("a reply's Markdown", () => {
  test("is a paragraph per blank-line-separated run, line breaks kept", () => {
    expect(markdownBlocks("Uno.\nSigue.\n\n\nDos.")).toEqual([
      { kind: "paragraph", text: "Uno.\nSigue." },
      { kind: "paragraph", text: "Dos." },
    ]);
  });

  test("reads headings, rules and quotes", () => {
    expect(
      markdownBlocks("## Resumen ##\n\n---\n\n> Citado\nsigue\n\nFin"),
    ).toEqual([
      { kind: "heading", level: 2, text: "Resumen" },
      { kind: "rule" },
      {
        kind: "quote",
        blocks: [{ kind: "paragraph", text: "Citado\nsigue" }],
      },
      { kind: "paragraph", text: "Fin" },
    ]);
    // A hash with no space after it is a word, not a heading.
    expect(markdownBlocks("#etiqueta")).toEqual([
      { kind: "paragraph", text: "#etiqueta" },
    ]);
  });

  test("keeps a fence's text as written, and an open fence runs to the end", () => {
    expect(markdownBlocks('```json\n{\n  "a": 1\n}\n```\nDespués')).toEqual([
      { kind: "code", language: "json", text: '{\n  "a": 1\n}' },
      { kind: "paragraph", text: "Después" },
    ]);
    expect(markdownBlocks("Antes\n```\n# no es título")).toEqual([
      { kind: "paragraph", text: "Antes" },
      { kind: "code", language: "", text: "# no es título" },
    ]);
  });

  test("reads lists, their numbering, nesting and run-on lines", () => {
    expect(
      markdownBlocks(
        "Pasos:\n1. Uno\n   sigue\n2. Dos\n   - a\n   - b\n\n- Otra lista",
      ),
    ).toEqual([
      { kind: "paragraph", text: "Pasos:" },
      {
        kind: "list",
        ordered: true,
        start: 1,
        items: [
          [{ kind: "paragraph", text: "Uno\nsigue" }],
          [
            { kind: "paragraph", text: "Dos" },
            {
              kind: "list",
              ordered: false,
              start: 1,
              items: [
                [{ kind: "paragraph", text: "a" }],
                [{ kind: "paragraph", text: "b" }],
              ],
            },
          ],
        ],
      },
      {
        kind: "list",
        ordered: false,
        start: 1,
        items: [[{ kind: "paragraph", text: "Otra lista" }]],
      },
    ]);
    // A number that does not start at one does not break a paragraph.
    expect(markdownBlocks("Pagué en\n2026. Luego")).toEqual([
      { kind: "paragraph", text: "Pagué en\n2026. Luego" },
    ]);
  });

  test("reads a table with its alignment, padding short rows", () => {
    expect(
      markdownBlocks(
        "| Casilla | Importe |\n|:--|--:|\n| 01 | 1.200,00 |\n| 02 |",
      ),
    ).toEqual([
      {
        kind: "table",
        align: ["left", "right"],
        head: ["Casilla", "Importe"],
        rows: [
          ["01", "1.200,00"],
          ["02", ""],
        ],
      },
    ]);
  });

  test("takes plain prose as written", () => {
    expect(markdownBlocks("2 * 3 * 4 = 24, snake_case_name")).toEqual([
      { kind: "paragraph", text: "2 * 3 * 4 = 24, snake_case_name" },
    ]);
  });
});
