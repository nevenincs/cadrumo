// The packaged run's results directory: results.json, summary.txt and an
// evidence/ folder, with one PASS, FAIL, SKIP or INFO line per check.
import { mkdirSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";

export class Results {
  constructor(directory) {
    this.directory = directory;
    this.evidenceDirectory = resolve(directory, "evidence");
    mkdirSync(this.evidenceDirectory, { recursive: true });
    this.checks = [];
    this.secrets = [];
  }

  /** A value that must never reach a results file. */
  secret(value) {
    if (typeof value === "string" && value.length >= 8)
      this.secrets.push(value);
  }

  scrub(text) {
    let out = text;
    for (const secret of this.secrets)
      out = out.split(secret).join("<redacted>");
    return out;
  }

  record({ id, title, verdict, detail, data, kind = "check" }) {
    const entry = {
      id,
      kind,
      title,
      verdict,
      detail,
      at: new Date().toISOString(),
    };
    if (data !== undefined) entry.data = data;
    this.checks.push(entry);
    console.log(this.scrub(`${verdict} ${id} - ${title}: ${detail}`));
    return entry;
  }

  evidence(name, value) {
    const text =
      typeof value === "string" ? value : JSON.stringify(value, null, 2);
    writeFileSync(resolve(this.evidenceDirectory, name), this.scrub(text));
    return `evidence/${name}`;
  }

  async screenshot(page, name) {
    try {
      await page.screenshot({
        path: resolve(this.evidenceDirectory, `${name}.png`),
        timeout: 10000,
      });
      return `evidence/${name}.png`;
    } catch {
      return null;
    }
  }

  finish(run) {
    const counts = {};
    for (const check of this.checks)
      counts[check.verdict] = (counts[check.verdict] ?? 0) + 1;
    const document = { run, counts, checks: this.checks };
    writeFileSync(
      resolve(this.directory, "results.json"),
      this.scrub(JSON.stringify(document, null, 2)),
    );
    const lines = [
      `CADRUMO packaged desktop test ${run.startedAt}`,
      ...Object.entries(run.summary ?? {}).map(
        ([key, value]) => `${key}: ${value}`,
      ),
      `counts: ${JSON.stringify(counts)}`,
      "",
      ...this.checks.map(
        (check) =>
          `${check.verdict} ${check.id} - ${check.title}: ${check.detail}`,
      ),
    ];
    writeFileSync(
      resolve(this.directory, "summary.txt"),
      this.scrub(`${lines.join("\n")}\n`),
    );
    return counts;
  }
}
