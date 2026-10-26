import { open, readdir, stat } from "node:fs/promises";
import { join } from "node:path";

// The ledger privacy check's search: where any of a set of values, held only
// in the spec's memory, appears in the window's storage, its messages or the
// files of a run. Every result names a place, never a value or the text
// around it, so a failure can be reported without repeating what it found.
// Only Node's own modules are imported, so `node --test` runs the unit test
// beside this file without a bundler.

/** How much of a file is read at once. */
export const READ_CHUNK_BYTES = 1 << 20;

/** The values to look for, in every form a writer can give them. */
export type Search = {
  readonly forms: readonly string[];
  readonly bytes: readonly { needle: Buffer; encoding: string }[];
  readonly longest: number;
};

/** Where the values were found, and the places that could not be read:
 * an unread place is not a clean one. */
export type Found = { hits: string[]; unread: string[] };

/** One stored item: its storage area, its key and its text. */
export type StoredEntry = { area: string; key: string; text: string };

/** A directory to scan, and the time in milliseconds since the epoch a file
 * must have been written at or after to count. */
export type ScanRoot = { root: string; since?: number };

const asciiEscaped = (json: string, hex: (digits: string) => string) =>
  json.replace(
    /[\u0080-￿]/g,
    (unit) => `\\u${hex(unit.charCodeAt(0).toString(16).padStart(4, "0"))}`,
  );

/** `value` as itself, JSON-escaped, and JSON-escaped to ASCII with either
 * case of hex digit, as JavaScript, Python and Rust serializers write it. */
export function writtenForms(value: string): string[] {
  const json = JSON.stringify(value).slice(1, -1);
  return [
    ...new Set([
      value,
      json,
      asciiEscaped(json, (digits) => digits),
      asciiEscaped(json, (digits) => digits.toUpperCase()),
    ]),
  ];
}

/** The search for `values`: each written form as text, and as UTF-8 and
 * UTF-16LE bytes. Empty values are left out, since they match everything. */
export function search(values: Iterable<string>): Search {
  const forms = [...new Set([...values].filter(Boolean).flatMap(writtenForms))];
  const bytes = forms.flatMap((form) =>
    (["utf-8", "utf-16le"] as const).map((encoding) => ({
      needle: Buffer.from(form, encoding === "utf-8" ? "utf8" : "utf16le"),
      encoding,
    })),
  );
  const longest = Math.max(1, ...bytes.map(({ needle }) => needle.length));
  return { forms, bytes, longest };
}

/** Whether `text` holds any of the values. */
export const holds = (found: Search, text: string) =>
  found.forms.some((form) => text.includes(form));

/** The places among stored entries that hold a value. A key that holds one
 * is named by its position, never by itself. */
export function storageHits(
  found: Search,
  entries: readonly StoredEntry[],
): string[] {
  const hits: string[] = [];
  entries.forEach((entry, at) => {
    if (!holds(found, entry.key) && !holds(found, entry.text)) return;
    hits.push(
      holds(found, entry.key)
        ? `${entry.area} entry ${at + 1}`
        : `${entry.area} ${entry.key}`,
    );
  });
  return hits;
}

/** The messages that hold a value, named `${source} ${n}` by position. */
export function messageHits(
  found: Search,
  source: string,
  messages: readonly string[],
): string[] {
  return messages.flatMap((message, at) =>
    holds(found, message) ? [`${source} ${at + 1}`] : [],
  );
}

/** The encodings in which a file's bytes hold a value, read in bounded
 * chunks with an overlap so no match is split between two. */
async function fileEncodings(found: Search, path: string): Promise<string[]> {
  const encodings = new Set<string>();
  const file = await open(path, "r");
  try {
    const chunk = Buffer.alloc(READ_CHUNK_BYTES);
    let tail = Buffer.alloc(0);
    for (;;) {
      const { bytesRead } = await file.read(chunk, 0, chunk.length, null);
      if (bytesRead === 0) break;
      const window = Buffer.concat([tail, chunk.subarray(0, bytesRead)]);
      for (const { needle, encoding } of found.bytes)
        if (!encodings.has(encoding) && window.includes(needle))
          encodings.add(encoding);
      tail = Buffer.from(
        window.subarray(Math.max(0, window.length - (found.longest - 1))),
      );
    }
  } finally {
    await file.close();
  }
  return [...encodings].sort();
}

/** Every regular file below `roots`, following no link, with the roots
 * that do not exist left out and the directories that cannot be listed
 * named. A file below a root with `since` counts only when it was written
 * at or after it. A path that holds a value is named by its position. */
export async function fileHits(
  found: Search,
  roots: readonly ScanRoot[],
): Promise<Found> {
  const hits: string[] = [];
  const unread: string[] = [];
  let counted = 0;
  const rootName = (scan: ScanRoot) =>
    holds(found, scan.root)
      ? `scanned directory ${roots.indexOf(scan) + 1}`
      : scan.root;
  const place = (path: string, scan: ScanRoot) =>
    holds(found, path)
      ? `file ${counted} under ${rootName(scan)} (its path holds a value)`
      : `file ${path}`;
  const walk = async (directory: string, scan: ScanRoot): Promise<void> => {
    let entries;
    try {
      entries = await readdir(directory, { withFileTypes: true });
    } catch (error) {
      if (
        directory === scan.root &&
        (error as NodeJS.ErrnoException).code === "ENOENT"
      )
        return;
      unread.push(
        holds(found, directory)
          ? `a directory under ${rootName(scan)}`
          : `directory ${directory}`,
      );
      return;
    }
    for (const entry of entries) {
      const path = join(directory, entry.name);
      if (entry.isSymbolicLink()) continue;
      if (entry.isDirectory()) {
        await walk(path, scan);
        continue;
      }
      if (!entry.isFile()) continue;
      counted += 1;
      try {
        if (scan.since !== undefined && (await stat(path)).mtimeMs < scan.since)
          continue;
        for (const encoding of await fileEncodings(found, path))
          hits.push(`${place(path, scan)} (${encoding})`);
      } catch {
        unread.push(place(path, scan));
      }
    }
  };
  for (const scan of roots) await walk(scan.root, scan);
  return { hits, unread };
}
