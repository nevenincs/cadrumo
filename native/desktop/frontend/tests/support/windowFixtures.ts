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
