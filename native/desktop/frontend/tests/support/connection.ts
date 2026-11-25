import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { buildPath } from "../../../scripts/build-paths.mjs";
import { label } from "./strings";

/** The words for how a lane is reached, from what the catalogue serves of it:
 * a lane that needs no key is a server on this computer, whatever its
 * transport. */
export const connectionLabel = (served: {
  transport: string;
  auth_kind?: string;
}): string =>
  label(
    served.auth_kind === "none"
      ? "desktop.providers.connection_local"
      : served.transport === "api"
        ? "desktop.providers.connection_api"
        : "desktop.providers.connection_app",
  );

/** The providers the agent ships artwork for, from the generated file the
 * shell is built from: one of them wears its mark, any other the generic
 * one. */
const ARTWORK = JSON.parse(
  readFileSync(
    resolve(buildPath("desktop_frontend_generated"), "provider-icons.json"),
    "utf8",
  ),
) as { providers: Record<string, unknown> };

/** Whether `provider` wears its own bundled mark. */
export const bundledMark = (provider: string): boolean =>
  Object.hasOwn(ARTWORK.providers, provider);
