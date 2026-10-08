import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { buildPath } from "../../../scripts/build-paths.mjs";

// Expected chrome text comes from the generated catalogue, the same file the
// shell is built from: an output of the build directory in use.
const catalogue = JSON.parse(
  readFileSync(
    resolve(buildPath("desktop_frontend_generated"), "chrome-strings.json"),
    "utf8",
  ),
) as Record<string, Record<string, string>>;

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
