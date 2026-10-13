// Writes the scenario host's lanes from cadrumo-agent: which providers it
// has, each one's API and command-line lanes, their names and execution
// modes, the efforts a gateway declares, and the credential each lane takes.
// Every value is read from the agent's own registry and its catalog response
// by `agent_catalog_dump.py`, run with the interpreter of the checkout named
// by CADRUMO_DEV_AGENT_CHECKOUT; none is typed here.
//
//   CADRUMO_DEV_AGENT_CHECKOUT=<absolute path> node scripts/agent-catalog-fixture.mjs
//   CADRUMO_DEV_AGENT_CHECKOUT=<absolute path> node scripts/agent-catalog-fixture.mjs --check
//
// `--check` writes nothing and fails when the file on disk is not what the
// agent would generate now.
import { spawnSync } from "node:child_process";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, isAbsolute, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";
import { format, resolveConfig } from "prettier";

const here = dirname(fileURLToPath(import.meta.url));
const frontend = resolve(here, "..");
const output = resolve(frontend, "src/dev/fixtures/agentLanes.generated.ts");
// The credential kind of a lane is declared by the backend's catalogue.
const backend = resolve(
  frontend,
  "../../../src/cadrumo/_data/provider_settings/catalog.toml",
);

const { values } = parseArgs({ options: { check: { type: "boolean" } } });

const checkout = process.env.CADRUMO_DEV_AGENT_CHECKOUT;
if (!checkout || !isAbsolute(checkout))
  fail(
    "Set CADRUMO_DEV_AGENT_CHECKOUT to the absolute path of a cadrumo-agent checkout.",
  );
const python = join(
  checkout,
  ".venv",
  process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
);
if (!existsSync(python))
  fail(`The checkout has no environment to run: ${python} is missing.`);

function fail(message) {
  console.error(message);
  process.exit(1);
}

const ran = spawnSync(
  python,
  ["-I", resolve(here, "agent_catalog_dump.py"), backend],
  {
    encoding: "utf8",
    cwd: checkout,
    env: { ...process.env, PYTHONDONTWRITEBYTECODE: "1" },
  },
);
if (ran.status !== 0)
  fail(`cadrumo-agent could not be read:\n${ran.stderr || ran.error}`);
const agent = JSON.parse(ran.stdout);

const source = `// GENERATED FILE - DO NOT EDIT.
// Regenerate: CADRUMO_DEV_AGENT_CHECKOUT=<cadrumo-agent checkout> node scripts/agent-catalog-fixture.mjs
//
// What cadrumo-agent declares about its provider lanes, read from its own
// registry (provider_definitions.py, graph/enums.py, providers/registry.py,
// providers/gateways.py, providers/execution_modes.py, providers/effort.py)
// and printed through its own
// ProviderCatalogResponse (api/schemas/provider_catalog.py), so each lane is
// shaped as the catalog serves it. Each lane's credential kind is the one the
// backend's provider-settings catalogue declares, checked against the agent's
// lanes, names and gateway endpoints when this was generated.
//
// Not here, because cadrumo-agent only learns them on a host at run time: a
// lane's health, the models of a catalog lane and what each takes, and how
// far each capability is proven. The scenario host adds those, named as
// fixtures. A lane is addressed as <provider>_<transport>.
//
// Agent source digest (sha256, line endings normalised): ${agent.digest}

import type {
  AgentLaneCapability,
  AgentProviderLane,
} from "../../shell/agentSession";
import type { ProviderSettingsRecord } from "../../shell/providerSettings";

/** What the agent declares of one lane. */
export type DeclaredLane = Pick<
  AgentProviderLane,
  | "provider_id"
  | "transport"
  | "display_name"
  | "execution_mode"
  | "executable"
  | "model_source"
> & {
  /** The catalog revision of a lane that declares its catalog. */
  catalog_revision: string | null;
  /** The controls the lane advertises with no model: a gateway's efforts. */
  native_controls: NonNullable<AgentProviderLane["catalog"]["native_controls"]>;
  /** The capabilities the agent states for the lane, and the tool server of
   * the two it states for one; their states are a host's to find. */
  capability_proofs: {
    capability: AgentLaneCapability;
    entry: string | null;
  }[];
};

/** A lane a profile keeps a credential for. */
export type DeclaredSettingsLane = Pick<
  ProviderSettingsRecord,
  "id" | "provider" | "display_name" | "transport" | "auth_kind"
> & { default_base_url: string | null };

export const DECLARED_LANES: readonly DeclaredLane[] = ${JSON.stringify(agent.lanes)};

export const DECLARED_SETTINGS_LANES: readonly DeclaredSettingsLane[] = ${JSON.stringify(agent.settings)};
`;

const formatted = await format(source, {
  ...(await resolveConfig(output)),
  filepath: output,
});

if (values.check) {
  const current = existsSync(output) ? readFileSync(output, "utf8") : "";
  if (current !== formatted)
    fail(
      "agentLanes.generated.ts is not what cadrumo-agent declares now; regenerate it.",
    );
  console.log("agentLanes.generated.ts matches cadrumo-agent.");
} else {
  writeFileSync(output, formatted);
  console.log(`Wrote ${output}`);
}
