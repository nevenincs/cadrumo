import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

// Expected chrome text comes from the generated catalogue, the same file the
// shell reads. Before it exists the shell shows each key, and so do these.
const path = fileURLToPath(
  new URL("../../src/generated/chrome-strings.json", import.meta.url),
);
const catalogue: Record<string, Record<string, string>> = existsSync(path)
  ? (JSON.parse(readFileSync(path, "utf8")) as Record<
      string,
      Record<string, string>
    >)
  : {};

/** The chrome string for `key` in `locale`, with `{name}` values filled in. */
export function label(
  key: string,
  values: Record<string, string | number> = {},
  locale = "en",
): string {
  const template = catalogue[locale]?.[key] ?? catalogue.en?.[key] ?? key;
  return template.replace(/\{(\w+)\}/g, (whole, name: string) =>
    name in values ? String(values[name]) : whole,
  );
}
