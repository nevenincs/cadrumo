import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";
import { mkdir, mkdtemp, rm, utimes, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { after, before, test } from "node:test";
import {
  READ_CHUNK_BYTES,
  fileHits,
  messageHits,
  search,
  storageHits,
  writtenForms,
} from "./privacy.ts";

// The ledger privacy check's search, on synthetic files and a made-up
// storage dump: it finds a planted value in every form a writer gives it,
// and names only where. Run with `node --test tests/live/privacy.unit.ts`.

let root = "";
before(async () => {
  root = await mkdtemp(join(tmpdir(), "ledger-privacy-"));
});
after(async () => {
  await rm(root, { recursive: true, force: true });
});

/** A value no fixture holds by chance, with characters outside ASCII. */
const planted = () => `Papelería Ñandú ${randomUUID()}`;

/** A fresh directory below the test's root. */
async function directory(name: string): Promise<string> {
  const path = join(root, `${name}-${randomUUID()}`);
  await mkdir(path, { recursive: true });
  return path;
}

/** No result may carry the value or any part of it longer than a word. */
function carriesNothingOf(value: string, results: readonly string[]) {
  const words = value.split(" ").filter((word) => word.length >= 6);
  for (const result of results)
    for (const word of [value, ...words])
      assert.ok(!result.includes(word), "a result repeated the value");
}

test("a value is written as itself, JSON-escaped, and escaped to ASCII in either case", () => {
  assert.deepEqual(writtenForms('Ñu "Sur"'), [
    'Ñu "Sur"',
    'Ñu \\"Sur\\"',
    '\\u00d1u \\"Sur\\"',
    '\\u00D1u \\"Sur\\"',
  ]);
  // A plain ASCII value has one form.
  assert.deepEqual(writtenForms("Coworking Ribera"), ["Coworking Ribera"]);
});

test("a clean tree has no hits and nothing unread", async () => {
  const tree = await directory("clean");
  await writeFile(join(tree, "cadrumo.log"), "signed in; ledger read\n");
  await mkdir(join(tree, "nested"));
  await writeFile(join(tree, "nested", "empty.bin"), Buffer.alloc(0));
  const found = await fileHits(search([planted()]), [{ root: tree }]);
  assert.deepEqual(found, { hits: [], unread: [] });
});

test("a planted value is found in UTF-8, UTF-16LE and JSON-escaped files, by place only", async () => {
  const value = planted();
  const tree = await directory("planted");
  const json = JSON.stringify({ description: value });
  // Python's json.dumps escapes every character outside ASCII by default.
  const ascii = json.replace(
    /[\u0080-￿]/g,
    (unit) => `\\u${unit.charCodeAt(0).toString(16).padStart(4, "0")}`,
  );
  assert.ok(!ascii.includes(value));
  const files = {
    "utf8.log": Buffer.from(`row ${value} read\n`, "utf8"),
    "utf16.log": Buffer.from(`row ${value} read\n`, "utf16le"),
    "escaped.json": Buffer.from(ascii, "utf8"),
    "plain.json": Buffer.from(json, "utf8"),
    "clean.log": Buffer.from("nothing here\n", "utf8"),
  };
  for (const [name, bytes] of Object.entries(files))
    await writeFile(join(tree, name), bytes);
  const found = await fileHits(search([value]), [{ root: tree }]);
  assert.deepEqual(found.unread, []);
  assert.deepEqual(found.hits.sort(), [
    `file ${join(tree, "escaped.json")} (utf-8)`,
    `file ${join(tree, "plain.json")} (utf-8)`,
    `file ${join(tree, "utf16.log")} (utf-16le)`,
    `file ${join(tree, "utf8.log")} (utf-8)`,
  ]);
  carriesNothingOf(value, found.hits);
});

test("a value split across two reads is still found", async () => {
  const value = planted();
  const tree = await directory("split");
  const encoded = Buffer.from(value, "utf8");
  const half = Math.floor(encoded.length / 2);
  // The value's first half ends the first chunk.
  const bytes = Buffer.concat([
    Buffer.alloc(READ_CHUNK_BYTES - half, 0x20),
    encoded,
    Buffer.from("\n"),
  ]);
  await writeFile(join(tree, "large.log"), bytes);
  const found = await fileHits(search([value]), [{ root: tree }]);
  assert.deepEqual(found.hits, [`file ${join(tree, "large.log")} (utf-8)`]);
});

test("only files written at or after a root's time count", async () => {
  const value = planted();
  const tree = await directory("since");
  await writeFile(join(tree, "old.log"), value);
  await writeFile(join(tree, "new.log"), value);
  const since = Date.now();
  const earlier = new Date(since - 60_000);
  await utimes(join(tree, "old.log"), earlier, earlier);
  const later = new Date(since + 1_000);
  await utimes(join(tree, "new.log"), later, later);
  const found = await fileHits(search([value]), [{ root: tree, since }]);
  assert.deepEqual(found.hits, [`file ${join(tree, "new.log")} (utf-8)`]);
});

test("a path that holds a value is named by position, and a missing root is no finding", async () => {
  const value = `Talleres${randomUUID()}`;
  const tree = await directory("named");
  await writeFile(join(tree, `${value}.log`), value);
  const found = await fileHits(search([value]), [
    { root: tree },
    { root: join(tree, "absent") },
  ]);
  assert.deepEqual(found, {
    hits: [`file 1 under ${tree} (its path holds a value) (utf-8)`],
    unread: [],
  });
  carriesNothingOf(value, found.hits);
});

test("a scanned directory whose own path holds a value is named by position", async () => {
  const value = `Ribera${randomUUID()}`;
  const tree = join(await directory("rooted"), value);
  await mkdir(tree);
  await writeFile(join(tree, "cadrumo.log"), value);
  const found = await fileHits(search([value]), [
    { root: join(root, "absent") },
    { root: tree },
  ]);
  assert.deepEqual(found, {
    hits: ["file 1 under scanned directory 2 (its path holds a value) (utf-8)"],
    unread: [],
  });
});

test("a directory that cannot be listed is unread, not clean", async () => {
  const tree = await directory("unlisted");
  // A file where a directory is expected cannot be listed.
  const logs = join(tree, "logs");
  await writeFile(logs, "not a directory");
  const found = await fileHits(search([planted()]), [{ root: logs }]);
  assert.deepEqual(found, { hits: [], unread: [`directory ${logs}`] });
});

test("a planted value in a storage dump is found by area and key, and a key holding one by position", () => {
  const value = planted();
  const layout = JSON.stringify({ layout: { ledgerView: { density: "x" } } });
  const entries = [
    { area: "localStorage", key: "cadrumo-shell-layout", text: layout },
    {
      area: "sessionStorage",
      key: "ledger-draft",
      text: JSON.stringify({ notes: value }),
    },
    { area: "IndexedDB", key: "cache/rows", text: `row\n${value}` },
    { area: "localStorage", key: `search:${value}`, text: "1" },
    { area: "cookie", key: "theme", text: "dark" },
  ];
  const hits = storageHits(search([value]), entries);
  assert.deepEqual(hits, [
    "sessionStorage ledger-draft",
    "IndexedDB cache/rows",
    "localStorage entry 4",
  ]);
  carriesNothingOf(value, hits);
});

test("presentation keys and a saved view's filter keys are no finding; its typed text is", () => {
  const typed = "Coworking Ribera";
  const view = { savedView: "pending", filters: { category: "office" } };
  const clean = [
    { area: "localStorage", key: "layout", text: JSON.stringify(view) },
  ];
  assert.deepEqual(storageHits(search([typed]), clean), []);
  // The representative defect: the view keeps the search as typed.
  const leaked = [
    {
      area: "localStorage",
      key: "layout",
      text: JSON.stringify({ ...view, search: typed }),
    },
  ];
  assert.deepEqual(storageHits(search([typed]), leaked), [
    "localStorage layout",
  ]);
});

test("messages are named by position", () => {
  const value = planted();
  const hits = messageHits(search([value]), "console message", [
    "ledger.list settled",
    `failed to render ${JSON.stringify(value)}`,
  ]);
  assert.deepEqual(hits, ["console message 2"]);
  carriesNothingOf(value, hits);
});

test("empty values are left out of the search", () => {
  const found = search(["", "Gráficas Turia"]);
  assert.ok(found.forms.every(Boolean));
  assert.equal(
    storageHits(found, [{ area: "a", key: "k", text: "" }]).length,
    0,
  );
});
