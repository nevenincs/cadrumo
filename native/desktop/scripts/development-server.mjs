// The fixed listener assignments consumed by just dev and native builds.
import { readFileSync } from "node:fs";

// Every listener the display, the browser tests and the catalogue use. The
// browser tests have ports of their own, so a test run never meets a server
// a developer has open.
export const PORT_KEYS = [
  "devPort",
  "previewPort",
  "docsPort",
  "cataloguePort",
  "scenariosPort",
  "scenariosDocsPort",
  "hotPort",
];

export function developmentServer() {
  const value = JSON.parse(
    readFileSync(
      new URL("../development-server.json", import.meta.url),
      "utf8",
    ),
  );
  if (typeof value.host !== "string" || !value.host.trim())
    throw new Error("Missing development bind address");
  for (const key of PORT_KEYS)
    if (!Number.isInteger(value[key]) || value[key] < 1 || value[key] > 65535)
      throw new Error(`Invalid development ${key}`);
  if (new Set(PORT_KEYS.map((key) => value[key])).size !== PORT_KEYS.length)
    throw new Error("Development listeners must have distinct ports");
  return value;
}
