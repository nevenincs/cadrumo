import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import {
  CLI_STATE_CAUSES,
  NEXT_STEPS,
  SIGN_IN_CAUSES,
  cliStateCause,
  consoleCommand,
  consoleCommandTemplate,
  nextStep,
  signInCause,
} from "../../src/shell/providerSignInWords.ts";

// The closed words a provider sign-in or status read serves, as the window
// accepts them, checked against the service's own declaration of them. Run
// with `node --test tests/live/provider-sign-in-words.unit.ts`.

const contracts = readFileSync(
  resolve(
    dirname(fileURLToPath(import.meta.url)),
    "../../../../../src/cadrumo_agent_service/providers/application/contracts.py",
  ),
  "utf8",
);

/** The first group of every match of `pattern` in `text`. */
const captured = (text: string, pattern: RegExp): string[] =>
  [...text.matchAll(pattern)].flatMap((match) => match[1] ?? []);

/** The quoted words of a `Name = Literal[...]` declaration. */
function literalWords(name: string): string[] {
  const block = captured(
    contracts,
    new RegExp(`${name} = Literal\\[([^\\]]*)\\]`, "g"),
  )[0];
  assert.ok(block, name);
  return captured(block, /"([a-z_]+)"/g);
}

/** The values of a `class Name(StrEnum)` declaration. */
function enumWords(name: string): string[] {
  const start = contracts.indexOf(`class ${name}(StrEnum):`);
  assert.notEqual(start, -1, name);
  const rest = contracts.slice(start + 1);
  const end = rest.search(/\n(class |@dataclass)/);
  return captured(rest.slice(0, end), /^ {4}[A-Z_]+ = "([a-z_]+)"/gm);
}

test("the window accepts exactly the words the service closes", () => {
  const causes = new Set([
    ...literalWords("HelperCause"),
    ...literalWords("ServiceCause"),
  ]);
  const statusCauses = enumWords("CliStateCause");
  assert.deepEqual([...CLI_STATE_CAUSES].sort(), [...statusCauses].sort());
  assert.deepEqual([...SIGN_IN_CAUSES].sort(), [...causes].sort());
  assert.deepEqual([...NEXT_STEPS].sort(), enumWords("NextStep").sort());
});

test("a word outside a closed set is dropped, never passed on", () => {
  assert.equal(signInCause("timed_out"), "timed_out");
  assert.equal(signInCause("raw provider output"), undefined);
  assert.equal(signInCause(7), undefined);
  assert.equal(nextStep("console_sign_in"), "console_sign_in");
  assert.equal(nextStep("reboot"), undefined);
  assert.equal(cliStateCause("probe_timed_out"), "probe_timed_out");
  assert.equal(cliStateCause("timed_out"), undefined);
  assert.equal(cliStateCause(null), undefined);
});

test("the console command is a bounded printable template with one provider slot", () => {
  const served = "aeat config provider-login --provider {provider}";
  assert.equal(consoleCommandTemplate(served), served);
  for (const refused of [
    undefined,
    7,
    "",
    "aeat config provider-login",
    "aeat {provider} {provider}",
    "cat /etc/passwd {provider}",
    "type C:\\x {provider}",
    "aeat\n{provider}",
    `aeat ${"x".repeat(300)} {provider}`,
  ])
    assert.equal(consoleCommandTemplate(refused), undefined, String(refused));
  assert.equal(
    consoleCommand(served, "codex"),
    "aeat config provider-login --provider codex",
  );
  assert.equal(consoleCommand(served, "Codex CLI; rm"), undefined);
  assert.equal(consoleCommand(undefined, "codex"), undefined);
});
