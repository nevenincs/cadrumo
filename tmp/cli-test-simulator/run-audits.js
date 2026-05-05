const fs = require("fs");
const path = require("path");
const engine = require("./audit-engine.js");

const args = parseArgs(process.argv.slice(2));
const audit = engine.runAudit({
  runs: args.runs || 250,
  seed: args.seed || "kent-n26-v6",
});

const rendered = args.format === "md" || (args.out && args.out.toLowerCase().endsWith(".md"))
  ? renderMarkdown(audit)
  : JSON.stringify(audit, null, 2);

if (args.out) {
  const target = path.resolve(process.cwd(), args.out);
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, rendered, "utf8");
}

console.log(`Seed: ${audit.seed}`);
console.log(`Runs: ${audit.runs}`);
console.log(`Completion Rate: ${metric(audit, "Completion Rate")}`);
console.log(`Commands To Success: ${metric(audit, "Commands To Success")}`);
console.log(`Tax-Safety Risk: ${metric(audit, "Tax-Safety Risk")}`);
console.log("Top findings:");
const materialSections = audit.findings.filter((section) => section.items.length > 0);
materialSections.slice(0, 4).forEach((section) => {
  const first = section.items[0];
  if (first) console.log(`- ${section.title}: ${first.label} (${first.count})`);
});
if (materialSections.length === 0) console.log("- No material findings in this run set.");
if (args.out) console.log(`Wrote: ${args.out}`);

function parseArgs(values) {
  const parsed = {};
  for (let index = 0; index < values.length; index += 1) {
    const value = values[index];
    if (value === "--runs") {
      parsed.runs = Number(values[index + 1]);
      index += 1;
    } else if (value === "--seed") {
      parsed.seed = values[index + 1];
      index += 1;
    } else if (value === "--out") {
      parsed.out = values[index + 1];
      index += 1;
    } else if (value === "--format") {
      parsed.format = values[index + 1];
      index += 1;
    }
  }
  return parsed;
}

function metric(auditResult, label) {
  const item = auditResult.metrics.find((entry) => entry.label === label);
  return item ? item.value : "n/a";
}

function renderMarkdown(auditResult) {
  const lines = [
    "# Kent/N26 CLI v6 audit findings",
    "",
    `Seed: \`${auditResult.seed}\``,
    `Runs: \`${auditResult.runs}\``,
    `Generated: \`${auditResult.generatedAt}\``,
    "",
    auditResult.persona,
    "",
    "## Metrics",
    "",
    "| Metric | Value |",
    "| --- | --- |",
  ];

  auditResult.metrics.forEach((entry) => {
    lines.push(`| ${entry.label} | ${entry.value} |`);
  });

  lines.push("", "## Findings", "");
  auditResult.findings.forEach((section) => {
    lines.push(`### ${section.title}`, "");
    if (section.items.length === 0) {
      lines.push("- No material signal in this run set.", "");
      return;
    }
    section.items.forEach((item) => {
      lines.push(`- ${item.label} (${item.count}): ${item.recommendation}`);
    });
    lines.push("");
  });

  lines.push("## Sample Generated Tape", "");
  auditResult.sampleTape.commands.forEach((command) => {
    lines.push(`- \`${command}\``);
  });

  return `${lines.join("\n")}\n`;
}
