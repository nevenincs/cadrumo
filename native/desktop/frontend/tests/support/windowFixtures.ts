import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { windowFixtures } from "../../scripts/fixture-paths.mjs";

/**
 * The directory of the Modelo scenario envelopes, as a URL ending in a slash.
 *
 * They are generated into the host's build tree and never committed; a spec
 * that reads one without them seeded fails on the missing file, and
 * `just fixtures-seed modelo-envelopes` writes them.
 */
export const MODELO_FIXTURES = pathToFileURL(
  `${resolve(windowFixtures(), "modelo")}/`,
);

/**
 * One generated window projection, as a file URL: `family` is the folder its
 * producer writes into and `name` the file without its extension.
 *
 * Like the envelopes, these are build output and never committed; a spec that
 * reads one without it seeded fails on the missing file, and
 * `just fixtures-seed` writes it.
 */
export function windowFixture(family: string, name: string): URL {
  return pathToFileURL(resolve(windowFixtures(), family, `${name}.json`));
}
