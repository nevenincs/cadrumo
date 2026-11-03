import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";
import { buildPath } from "../../../scripts/build-paths.mjs";
import { chromeCatalogueModule } from "../../dev/chrome-catalogue.ts";

async function restored(catalogue: unknown) {
  const source = chromeCatalogueModule(catalogue);
  const module = await import(
    `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`
  );
  return module.default;
}

test("bundled chrome restores the complete canonical catalogue in its original order", async () => {
  const catalogue = JSON.parse(
    readFileSync(
      resolve(buildPath("desktop_frontend_generated"), "chrome-strings.json"),
      "utf8",
    ),
  );
  const actual = await restored(catalogue);
  assert.deepEqual(actual, catalogue);
  assert.deepEqual(Object.keys(actual), Object.keys(catalogue));
  for (const language of Object.keys(catalogue))
    assert.deepEqual(
      Object.keys(actual[language]),
      Object.keys(catalogue[language]),
    );
});

test("bundled chrome preserves special keys, empty values, tokens and escaped text", async () => {
  const entries = [
    ["__proto__", "literal prototype key"],
    ["constructor", "literal constructor key"],
    ["empty", ""],
    ["template", "Hello, {name}. ${unchanged}"],
    ["escaped", 'árvíztűrő 中文 😀 " \\ \n </script>\u2028\u2029'],
  ];
  const catalogue = Object.fromEntries([
    ["hu", Object.fromEntries(entries)],
    ["en", Object.fromEntries(entries)],
  ]);
  const actual = await restored(catalogue);
  assert.deepEqual(actual, catalogue);
  assert.deepEqual(Object.keys(actual), ["hu", "en"]);
  assert.deepEqual(
    Object.keys(actual.hu),
    entries.map(([key]) => key),
  );
  assert.equal(Object.getPrototypeOf(actual.hu), Object.prototype);
  assert.equal(Object.hasOwn(actual.hu, "__proto__"), true);
  assert.equal(chromeCatalogueModule(catalogue).includes("</script>"), false);
  assert.deepEqual(await restored({}), {});
  assert.deepEqual(await restored({ en: {}, ca: {} }), { en: {}, ca: {} });
});

test("bundling refuses malformed catalogues and differing locale keys or order", () => {
  for (const invalid of [
    null,
    [],
    "text",
    { en: null },
    { en: [] },
    { en: { key: 1 } },
  ])
    assert.throws(() => chromeCatalogueModule(invalid), TypeError);
  for (const invalid of [
    { en: { one: "1" }, ca: {} },
    { en: { one: "1" }, ca: { two: "2" } },
    { en: { one: "1", two: "2" }, ca: { two: "2", one: "1" } },
  ])
    assert.throws(
      () => chromeCatalogueModule(invalid),
      /different ordered keys/,
    );
});
