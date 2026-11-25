import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { buildPath } from "../../../scripts/build-paths.mjs";

/**
 * The directory of the Modelo scenario envelopes, as a URL ending in a slash.
 *
 * They are generated into the selected build tree and never committed; a spec
 * that reads one without them seeded fails on the missing file, and the
 * build's desktop-window-fixtures target writes them.
 */
export const MODELO_FIXTURES = pathToFileURL(
  `${resolve(buildPath("window_fixtures"), "modelo")}/`,
);

/**
 * One generated window projection, as a file URL: `family` is the folder its
 * producer writes into and `name` the file without its extension.
 *
 * Like the envelopes, these are build output and never committed; a spec that
 * reads one without it seeded fails on the missing file, and the
 * desktop-window-fixtures target writes it.
 */
export function windowFixture(family: string, name: string): URL {
  return pathToFileURL(
    resolve(buildPath("window_fixtures"), family, `${name}.json`),
  );
}
