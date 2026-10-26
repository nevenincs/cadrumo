import { randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";
import {
  expect,
  test,
  type Locator,
  type Page,
  type Request,
  type Response,
} from "@playwright/test";
import { label } from "../support/strings";
import {
  fileHits,
  holds,
  messageHits,
  search,
  storageHits,
  type ScanRoot,
  type StoredEntry,
} from "./privacy";

// The Ledger page on the person's own ledger, in the packaged window: what
// the page shows and what a person stages never reaches the window's
// storage, its console, the run's files or the logs written during the run.
// The values looked for are read from the window and held only in this
// spec's memory. Nothing here names one: test titles, failures, assertions
// and log lines carry places and counts, and a step that could quote the
// page throws an error of its own instead of Playwright's. The spec saves,
// applies, imports and exports nothing, and discards what it staged.

// Playwright writes the page's accessibility snapshot beside a failure
// unless this is set; this worker runs only this project.
process.env.PLAYWRIGHT_NO_COPY_PROMPT = "1";

/** How long a real ledger may take to read. */
const READ_MS = 3 * 60_000;
/** How long the page may take to read one storage area. */
const STORAGE_MS = 20_000;
/** Shorter text is too common to tell a leak from chance. */
const WORTH = 6;
/** The drawn rows whose shown values are read. */
const SHOWN_ROWS = 8;
/** The listed movements whose stored text is kept, across every read. */
const LISTED_VALUES = 300;
/** The host's command endpoint, which every host call reaches. */
const IPC_HOST = "ipc.localhost";
/** A submission whose definition could not be read: taken for a write. */
const UNREADABLE = "(an unreadable submission)";
/** The host commands that answer a review, change an own account or open a
 * native file dialog: none of them belongs in this run. */
const NEVER_SENT = new Set([
  "ledger_answer",
  "ledger_own_account",
  "ledger_files_pick",
  "ledger_files_save",
]);

/** The definitions whose contract permits an effect other than none or
 * unknown, from the contract manifest the runtime is built from. */
function writeDefinitions(): Set<string> {
  const manifest = JSON.parse(
    readFileSync(
      new URL(
        "../../../../../src/cadrumo/_data/operations/contract_manifest.json",
        import.meta.url,
      ),
      "utf8",
    ),
  ) as {
    operations: {
      contract: { definition_id: string; permitted_effects: string[] };
    }[];
  };
  return new Set(
    manifest.operations
      .map(({ contract }) => contract)
      .filter((contract) =>
        contract.permitted_effects.some(
          (effect) => effect !== "none" && effect !== "unknown",
        ),
      )
      .map((contract) => contract.definition_id),
  );
}

/** Runs `work`; a failure throws an error naming only `what`, because
 * Playwright's own can quote the page: a locator's text, an element's
 * preview or an accessibility snapshot of the ledger. */
async function step<T>(what: string, work: () => Promise<T>): Promise<T> {
  try {
    return await work();
  } catch {
    throw new Error(`The ledger privacy check stopped while ${what}.`);
  }
}

/** Where the files to scan are: the run's directory, and the directories
 * whose files written since the run started are the run's logs. */
function runScope(): ScanRoot[] {
  const run = process.env.CADRUMO_DEV_DESKTOP_LIVE_RUN_DIRECTORY;
  const written: unknown = JSON.parse(
    process.env.CADRUMO_DEV_DESKTOP_LIVE_WRITTEN ?? "null",
  );
  const started = Number(process.env.CADRUMO_DEV_DESKTOP_LIVE_STARTED_AT);
  if (
    !run ||
    !Array.isArray(written) ||
    !written.every((root) => typeof root === "string") ||
    !Number.isFinite(started)
  )
    throw new Error(
      "The ledger privacy check runs through its lane: just desktop-agent-live --ledger-privacy.",
    );
  return [
    { root: run },
    ...written.map((root: string) => ({ root, since: started * 1000 })),
  ];
}

/** Refuses to start where anything could record the window: a trace, a
 * screenshot or a video, or Playwright's debug log of the protocol. */
function refuseRecording() {
  const use = test.info().project.use;
  const recording = (["trace", "screenshot", "video"] as const).filter(
    (name) => use[name] !== "off",
  );
  if (recording.length > 0)
    throw new Error(
      `The ledger privacy project records the window: ${recording.join(", ")}.`,
    );
  if (process.env.PWDEBUG || process.env.DEBUG)
    throw new Error(
      "Playwright's debug log would print the page's values; unset DEBUG and PWDEBUG.",
    );
}

/** Keeps `text` among the values when it is long enough to tell apart. */
function keep(values: Set<string>, text: unknown) {
  if (typeof text !== "string") return;
  const trimmed = text.trim();
  if (trimmed.length >= WORTH) values.add(trimmed);
}

/** What the host was asked during the run, and the text of the movements
 * its list reads answered; a stored amount is too short and too common to
 * look for. Only command names and definition ids are kept of the calls;
 * request bodies are read and dropped. */
function observeHost(page: Page, values: Set<string>) {
  const commands: string[] = [];
  const definitions: string[] = [];
  const reads: Promise<void>[] = [];
  let listed = 0;
  const command = (request: Request) => {
    const url = new URL(request.url());
    return url.hostname === IPC_HOST
      ? decodeURIComponent(url.pathname.slice(1))
      : null;
  };
  const definition = (request: Request) => {
    try {
      const body = JSON.parse(request.postData() ?? "") as {
        definition?: unknown;
      };
      return typeof body.definition === "string" ? body.definition : null;
    } catch {
      return null;
    }
  };
  const keepListed = (outcome: unknown) => {
    const rows = (outcome as { result?: { rows?: unknown } } | null)?.result
      ?.rows;
    if (!Array.isArray(rows)) return;
    for (const row of rows) {
      const transaction =
        (row as { transaction?: Record<string, unknown> } | null)
          ?.transaction ?? {};
      for (const field of ["description", "counterparty", "notes"])
        if (listed < LISTED_VALUES) {
          const before = values.size;
          keep(values, transaction[field]);
          listed += values.size - before;
        }
    }
  };
  const onRequest = (request: Request) => {
    const name = command(request);
    if (name === null) return;
    commands.push(name);
    if (name === "ledger_submit")
      definitions.push(definition(request) ?? UNREADABLE);
  };
  const onResponse = (response: Response) => {
    const request = response.request();
    if (command(request) !== "ledger_submit") return;
    if (definition(request) !== "ledger.list") return;
    reads.push(response.json().then(keepListed, () => undefined));
  };
  page.on("request", onRequest);
  page.on("response", onResponse);
  return {
    commands,
    definitions,
    async stop() {
      page.off("request", onRequest);
      page.off("response", onResponse);
      await Promise.allSettled(reads);
    },
  };
}

const ledger = (page: Page) => page.locator(".ledger-page");
const dataRows = (page: Page) =>
  ledger(page).locator("[role=grid] [data-kind=data]");
const head = (page: Page) => page.locator(".pane-docs .pane-head");
const tray = (page: Page) => page.locator(".ledger-tray");

/** Waits for the period's read to end: rows drawn and nothing still being
 * read, the page's empty state, or its failure. */
async function readState(page: Page): Promise<"rows" | "empty" | "failed"> {
  const deadline = Date.now() + READ_MS;
  for (;;) {
    const state = await page.evaluate(() => {
      const root = document.querySelector(".ledger-page");
      if (!root) return null;
      if (root.querySelector(".ledger-failed")) return "failed";
      if (root.querySelector(".ledger-empty")) return "empty";
      const reading =
        root.querySelector(".ledger-loading") ??
        root.querySelector(".ledger-movements > p[role=status]");
      if (reading) return null;
      return root.querySelector("[role=grid] [data-kind=data]") ? "rows" : null;
    });
    if (state !== null) return state;
    if (Date.now() > deadline) throw new Error("not read");
    await page.waitForTimeout(250);
  }
}

/** The values the first drawn rows show, as a person reads them: their
 * descriptions, counterparties and amounts, and one category. */
function shownValues(page: Page) {
  return page.evaluate((limit) => {
    const shown = (cell: Element | null) => {
      if (!cell) return "";
      const copy = cell.cloneNode(true) as Element;
      for (const hidden of copy.querySelectorAll(".sr-only")) hidden.remove();
      return (copy.textContent ?? "").trim();
    };
    const rows = [
      ...document.querySelectorAll(".ledger-page [role=grid] [data-kind=data]"),
    ].slice(0, limit);
    const column = (name: string) =>
      rows.map((row) => shown(row.querySelector(`[data-column=${name}]`)));
    return {
      descriptions: column("description"),
      counterparties: column("counterparty"),
      amounts: column("amount"),
      category: column("category").find((text) => text.length > 0) ?? null,
    };
  }, SHOWN_ROWS);
}

/** Stages `text` in a row's `column` through its cell editor, as a person
 * types it; false where the row takes no edit there. */
async function stageInto(
  page: Page,
  row: Locator,
  column: string,
  text: string,
): Promise<boolean> {
  const cell = row.locator(`[data-column=${column}]`);
  if ((await cell.count()) === 0) return false;
  await cell.click();
  await page.keyboard.press("Enter");
  const editor = page.locator(".ledger-cell-editor");
  const opened = await editor
    .waitFor({ state: "visible", timeout: 5_000 })
    .then(
      () => true,
      () => false,
    );
  if (!opened) return false;
  await editor.fill(text);
  await page.keyboard.press("Enter");
  await editor.waitFor({ state: "hidden" });
  return true;
}

/** Stages `text` in the first of the drawn rows from `from` that takes it,
 * in its counterparty or else its description; returns the next row. */
async function stageSomewhere(
  page: Page,
  from: number,
  text: string,
): Promise<number | null> {
  const count = Math.min(await dataRows(page).count(), SHOWN_ROWS);
  for (let at = from; at < count; at += 1)
    for (const column of ["counterparty", "description"])
      if (await stageInto(page, dataRows(page).nth(at), column, text))
        return at + 1;
  return null;
}

/** Opens a dialog from the page's header and closes it with Escape, as a
 * person who changes their mind does. */
async function openAndCancel(page: Page, action: string, title: string) {
  await head(page)
    .getByRole("button", { name: label(action), exact: true })
    .click();
  const dialog = page.getByRole("dialog", { name: label(title) });
  await dialog.waitFor({ state: "visible" });
  await page.keyboard.press("Escape");
  await dialog.waitFor({ state: "hidden" });
}

/** How many movements the tray counts as staged; zero without a tray. */
async function stagedUnits(page: Page): Promise<number> {
  if ((await tray(page).count()) === 0) return 0;
  return Number(
    await tray(page)
      .locator(".ledger-tray-toggle span[aria-hidden=true]")
      .textContent(),
  );
}

/** Discards what is staged through the tray's own Discard, first closing
 * an editor or dialog a stopped step left open over it. */
async function discard(page: Page) {
  const open = page.locator(".ledger-cell-editor, [role=dialog]");
  for (let at = 0; at < 3 && (await open.count()) > 0; at += 1)
    await page.keyboard.press("Escape");
  if ((await tray(page).count()) === 0) return;
  const toggle = tray(page).locator(".ledger-tray-toggle");
  if ((await toggle.getAttribute("aria-expanded")) !== "true")
    await toggle.click();
  await tray(page).locator(".ledger-tray-discard").click();
  await tray(page).waitFor({ state: "detached", timeout: 10_000 });
}

/** Every item of the window's web storage, IndexedDB and Cache Storage,
 * and its cookies, as text; and the areas that could not be read. */
async function storedEntries(
  page: Page,
): Promise<{ entries: StoredEntry[]; unread: string[] }> {
  const found = await page.evaluate(async (boundMs) => {
    const entries: { area: string; key: string; text: string }[] = [];
    const unread: string[] = [];
    const within = <T>(work: Promise<T>) =>
      Promise.race([
        work,
        new Promise<never>((_, refuse) =>
          setTimeout(() => refuse(new Error("timed out")), boundMs),
        ),
      ]);
    const decode = (bytes: ArrayBuffer | ArrayBufferView) => {
      const view =
        bytes instanceof ArrayBuffer
          ? new Uint8Array(bytes)
          : new Uint8Array(bytes.buffer, bytes.byteOffset, bytes.byteLength);
      return [
        new TextDecoder("utf-8").decode(view),
        new TextDecoder("utf-16le").decode(view),
      ];
    };
    const texts = async (
      value: unknown,
      seen: WeakSet<object>,
      out: string[],
      depth: number,
    ): Promise<void> => {
      if (value === null || value === undefined) return;
      if (typeof value !== "object") {
        out.push(String(value));
        return;
      }
      if (seen.has(value) || depth > 32) return;
      seen.add(value);
      if (value instanceof Blob) out.push(...decode(await value.arrayBuffer()));
      else if (value instanceof ArrayBuffer || ArrayBuffer.isView(value))
        out.push(...decode(value));
      else if (value instanceof Date) out.push(String(value.getTime()));
      else {
        const items =
          value instanceof Map
            ? [...value.entries()].flat()
            : value instanceof Set
              ? [...value]
              : Array.isArray(value)
                ? value
                : Object.entries(value).flat();
        for (const item of items) await texts(item, seen, out, depth + 1);
      }
    };
    const flatten = async (value: unknown) => {
      const out: string[] = [];
      await texts(value, new WeakSet(), out, 0);
      return out.join("\n");
    };
    const settle = <T>(request: IDBRequest<T>) =>
      new Promise<T>((done, refuse) => {
        request.onsuccess = () => done(request.result);
        request.onerror = () => refuse(request.error);
      });

    for (const [area, store] of [
      ["localStorage", localStorage],
      ["sessionStorage", sessionStorage],
    ] as const)
      for (let at = 0; at < store.length; at += 1) {
        const key = store.key(at) ?? "";
        entries.push({ area, key, text: store.getItem(key) ?? "" });
      }
    try {
      const databases = await within(indexedDB.databases());
      for (const [at, { name }] of databases.entries()) {
        if (!name) continue;
        try {
          const database = await within(
            new Promise<IDBDatabase>((done, refuse) => {
              const request = indexedDB.open(name);
              request.onsuccess = () => done(request.result);
              request.onerror = () => refuse(request.error);
              request.onblocked = () => refuse(new Error("blocked"));
            }),
          );
          try {
            for (const store of Array.from(database.objectStoreNames)) {
              const items = database
                .transaction(store, "readonly")
                .objectStore(store);
              const [keys, values] = await within(
                Promise.all([
                  settle(items.getAllKeys()),
                  settle(items.getAll()),
                ]),
              );
              entries.push({
                area: "IndexedDB",
                key: `${name}/${store}`,
                text: await flatten([keys, values]),
              });
            }
          } finally {
            database.close();
          }
        } catch {
          unread.push(`IndexedDB database ${at + 1}`);
        }
      }
    } catch {
      unread.push("IndexedDB's list of databases");
    }
    if (typeof caches !== "undefined")
      try {
        await within(
          (async () => {
            for (const name of await caches.keys()) {
              const cache = await caches.open(name);
              for (const request of await cache.keys()) {
                const response = await cache.match(request);
                const body = response
                  ? decode(await response.arrayBuffer())
                  : [];
                entries.push({
                  area: "Cache Storage",
                  key: name,
                  text: [request.url, ...body].join("\n"),
                });
              }
            }
          })(),
        );
      } catch {
        unread.push("Cache Storage");
      }
    entries.push({ area: "document.cookie", key: "", text: document.cookie });
    return { entries, unread };
  }, STORAGE_MS);
  for (const cookie of await page.context().cookies())
    found.entries.push({
      area: "cookie",
      key: `${cookie.name} (${cookie.domain})`,
      text: cookie.value,
    });
  return found;
}

// Before the window is attached, so a refusal leaves nothing of it behind.
test.beforeAll(() => {
  refuseRecording();
  runScope();
});

test("no ledger value or staged edit reaches the window's storage, its console or the run's files", async ({
  page,
}) => {
  const roots = runScope();
  const writes = writeDefinitions();
  const marker = `cadrumo-privacy-${randomUUID()}`;
  const values = new Set<string>([marker]);
  const messages: string[] = [];
  const errors: string[] = [];
  page.on("console", (message) => messages.push(message.text()));
  page.on("pageerror", (error) =>
    errors.push(`${error.message}\n${error.stack ?? ""}`),
  );
  const host = observeHost(page, values);
  const places = new Set<string>();
  const unread = new Set<string>();
  const checkStorage = async () => {
    const stored = await step("reading the window's storage", () =>
      storedEntries(page),
    );
    for (const place of storageHits(search(values), stored.entries))
      places.add(place);
    for (const place of stored.unread) unread.add(place);
  };

  let failure: unknown = null;
  try {
    // A fresh shell, with the storage the fixture emptied: no page it
    // restored read the ledger before the observers above were attached.
    await step("reloading the shell", () => page.reload());
    await step("opening the Ledger page", async () => {
      if (!(await ledger(page).isVisible()))
        await page.locator("[data-rail=ledger]").click();
      await expect(ledger(page)).toBeVisible();
    });
    let state = await step("reading the current period", () => readState(page));
    if (state === "empty") {
      // The current quarter has no movements: every period has the values.
      await step("choosing every period", async () => {
        await head(page).locator(".ledger-period").click();
        await page.locator(".ledger-period-all").click();
        await ledger(page)
          .locator(".ledger-empty")
          .waitFor({ state: "detached", timeout: 10_000 })
          .catch(() => undefined);
      });
      state = await step("reading every period", () => readState(page));
    }
    if (state === "failed")
      throw new Error("The ledger read failed; the window says why.");
    if (state === "empty")
      throw new Error(
        "The ledger holds no movements, so the check has no value to look for.",
      );

    const read = await step("reading the shown movements", () =>
      shownValues(page),
    );
    const before = values.size;
    for (const text of [
      ...read.descriptions,
      ...read.counterparties,
      ...read.amounts,
      read.category,
    ])
      keep(values, text);
    const shown = values.size - before;
    const description = read.descriptions.find((text) => text.length >= WORTH);
    if (shown < 3 || description === undefined)
      throw new Error(
        `The shown movements gave ${shown} values long enough to look for; the check needs 3 and a description.`,
      );

    await step("opening and cancelling the import dialog", () =>
      openAndCancel(
        page,
        "desktop.ledger.action.import",
        "desktop.ledger.import.title",
      ),
    );
    await step("opening and cancelling the export dialog", () =>
      openAndCancel(
        page,
        "desktop.ledger.action.export",
        "desktop.ledger.export.title",
      ),
    );

    // The marker in one movement, and a description typed into another
    // where the period draws a second that takes an edit.
    const next = await step("staging the marker", () =>
      stageSomewhere(page, 0, marker),
    );
    if (next === null)
      throw new Error("No drawn movement took an edit to stage.");
    await step("staging a description", () =>
      stageSomewhere(page, next, description),
    );
    const staged = await step("counting the staged movements", () =>
      stagedUnits(page),
    );
    if (staged < 1) throw new Error("The tray counts nothing staged.");

    await step("opening the inspector", async () => {
      const panel = page.locator("aside.ledger-panel");
      if (!(await panel.isVisible())) {
        await dataRows(page).first().locator("[data-column=status]").click();
        await page.keyboard.press("Alt+KeyI");
      }
      await panel.waitFor({ state: "visible" });
    });
    await step("searching for a shown description", async () => {
      await ledger(page)
        .getByRole("searchbox", { name: label("desktop.ledger.search.label") })
        .fill(description);
      await expect
        .poll(
          async () =>
            (await dataRows(page).count()) +
            (await ledger(page).locator(".ledger-filtered-empty").count()),
        )
        .toBeGreaterThan(0);
    });

    // With the edit staged and the search typed: the worst moment.
    await checkStorage();
  } catch (error) {
    failure = error;
  }
  const discarded = await step("discarding the staged edit", () =>
    discard(page),
  ).then(
    () => true,
    () => false,
  );
  if (failure !== null) throw failure;
  expect(discarded, "the tray's Discard dropped the staged edit").toBe(true);
  const left = await step("counting what is still staged", () =>
    stagedUnits(page),
  );
  expect(left, "movements still staged").toBe(0);

  await checkStorage();
  await host.stop();
  const found = search(values);
  for (const place of [
    ...messageHits(found, "console message", messages),
    ...messageHits(found, "page error", errors),
  ])
    places.add(place);
  const files = await step("scanning the run's files and logs", () =>
    fileHits(found, roots),
  );
  for (const place of files.hits) places.add(place);
  for (const place of files.unread) unread.add(place);
  // A place is named by its location; one that would repeat a value is not.
  for (const place of [...places, ...unread])
    if (holds(found, place)) throw new Error("A place's name holds a value.");

  expect([...places], "places holding a ledger value or the marker").toEqual(
    [],
  );
  expect([...unread], "places the check could not read").toEqual([]);
  expect(
    host.definitions.filter(
      (definition) => writes.has(definition) || definition === UNREADABLE,
    ),
    "write definitions submitted",
  ).toEqual([]);
  expect(
    host.commands.filter((command) => NEVER_SENT.has(command)),
    "host commands that answer, change an account or pick a file",
  ).toEqual([]);
  // The host calls were seen: the period's read went through them.
  expect(host.definitions, "ledger reads submitted").toContain("ledger.list");
  const applied = await step("looking for a review or apply", () =>
    page.locator(".ledger-review, .ledger-apply-done").count(),
  );
  expect(applied, "a review or apply the page opened").toBe(0);
});
