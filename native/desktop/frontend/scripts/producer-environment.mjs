// The environment a Python producer the drivers launch runs in. The
// checkout's own src comes first, then the checkout root for dev, then
// whatever the caller had, so the producer imports cadrumo from this checkout
// rather than from wherever the shared environment's editable install points.
import { delimiter, resolve } from "node:path";

export function producerEnvironment(repository, inherited = process.env) {
  const environment = { ...inherited };
  const parts = [
    resolve(repository, "src"),
    repository,
    ...(inherited.PYTHONPATH ?? "").split(delimiter),
  ].filter(Boolean);
  environment.PYTHONPATH = [...new Set(parts)].join(delimiter);
  return environment;
}
