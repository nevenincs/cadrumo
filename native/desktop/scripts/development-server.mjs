// The fixed listener assignments consumed by just dev and native builds.
import { readFileSync } from "node:fs";

export function developmentServer() {
  const value = JSON.parse(
    readFileSync(
      new URL("../development-server.json", import.meta.url),
      "utf8",
    ),
  );
  if (typeof value.host !== "string" || !value.host.trim())
    throw new Error("Missing development bind address");
  const keys = ["devPort", "previewPort", "docsPort", "cataloguePort"];
  for (const key of keys)
    if (!Number.isInteger(value[key]) || value[key] < 1 || value[key] > 65535)
      throw new Error(`Invalid development ${key}`);
  if (new Set(keys.map((key) => value[key])).size !== keys.length)
    throw new Error("Development listeners must have distinct ports");
  return value;
}
