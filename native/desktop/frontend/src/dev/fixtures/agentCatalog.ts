import type {
  AgentCatalogEntry,
  AgentProviderCatalog,
  AgentProviderLane,
} from "../../shell/agentSession";

// A provider catalog in the shape cadrumo-agent serves it, for the scenario
// host. The lanes are the ones cadrumo-agent declares, each under its own
// execution mode; their health varies so every way a lane can be held back
// is shown. Every model is made up and named as a fixture: what a real
// model is called, which efforts it takes and what it can do come only from
// cadrumo-agent's own catalog.

const CHECKED = "2026-10-13T08:00:00Z";

type Health = AgentProviderLane["health"];

const HEALTHY: Health = {
  configured: "available",
  transport: "available",
  authentication: "authenticated",
  catalog: "available",
  admission: "admitted",
  selectable: true,
  reasons: [],
  checked_at: CHECKED,
};

function lane(
  provider_id: string,
  display_name: string,
  execution_mode: string,
  models: AgentCatalogEntry[],
  extra: Omit<Partial<AgentProviderLane>, "health" | "catalog"> & {
    health?: Partial<Health>;
    catalog?: Partial<AgentProviderLane["catalog"]>;
  } = {},
): AgentProviderLane {
  const { health, catalog, ...rest } = extra;
  return {
    provider_id,
    display_name,
    execution_mode,
    executable: true,
    model_source: "catalog",
    health: { ...HEALTHY, ...health },
    catalog: {
      schema_version: 1,
      state: {
        status: "available",
        checked_at: CHECKED,
        revision: "fixture-1",
      },
      recommended_entry_id: models[0]?.entry_id ?? null,
      models,
      native_controls: [],
      ...catalog,
    },
    ...rest,
  };
}

const entry = (
  entry_id: string,
  display_name: string,
  efforts: AgentCatalogEntry["efforts"],
  extra: Partial<AgentCatalogEntry> = {},
): AgentCatalogEntry => ({
  entry_id,
  model: entry_id,
  display_name,
  efforts,
  default_effort: efforts?.[Math.min(1, efforts.length - 1)] ?? null,
  ...extra,
});

/** A gateway lane that has no key in this profile. */
const unkeyed = (provider_id: string, display_name: string) =>
  lane(provider_id, display_name, `${provider_id}-claude-agent-acp:node`, [], {
    health: {
      configured: "unavailable",
      catalog: "unknown",
      admission: "unknown",
      selectable: false,
      reasons: ["credential_missing"],
    },
    catalog: { state: { status: "unknown", checked_at: CHECKED } },
  });

export const FIXTURE_CATALOG: AgentProviderCatalog = {
  api_version: "1",
  providers: [
    lane(
      "anthropic",
      "Anthropic",
      "anthropic-api",
      [
        entry(
          "fixture-deep",
          "Fixture Deep",
          ["low", "medium", "high", "xhigh", "max"],
          { description: "A made-up model that takes every effort up to max." },
        ),
        entry("fixture-quick", "Fixture Quick", ["low", "medium"]),
        entry("fixture-plain", "Fixture Plain", []),
      ],
      {
        capability_proofs: [
          { capability: "tool_access", entry: null, state: "proven" },
          { capability: "pdf_reading", entry: "fixture-deep", state: "proven" },
          {
            capability: "image_reading",
            entry: "fixture-deep",
            state: "unproven",
          },
        ],
      },
    ),
    lane(
      "openai",
      "OpenAI",
      "openai-api",
      [
        entry("fixture-tiered", "Fixture Tiered", ["low", "medium", "high"], {
          native_control_ids: ["service_tier"],
        }),
        entry("fixture-ultra", "Fixture Ultra", ["high", "ultra"]),
      ],
      {
        catalog: {
          recommended_entry_id: "fixture-ultra",
          native_controls: [
            {
              control_id: "service_tier",
              kind: "service_tier",
              display_name: "Fixture service tier",
              options: [
                { option_id: "standard", display_name: "Fixture standard" },
                { option_id: "priority", display_name: "Fixture priority" },
              ],
              default_option_id: "standard",
            },
          ],
        },
      },
    ),
    lane("claude", "Claude", "claude-agent-acp:node", [], {
      health: {
        authentication: "unauthenticated",
        selectable: false,
        reasons: ["sign_in_required"],
      },
    }),
    lane("codex", "Codex", "codex-app-server", [
      entry("fixture-coder", "Fixture Coder", [
        "low",
        "medium",
        "high",
        "xhigh",
      ]),
    ]),
    lane("kimi", "Kimi", "kimi-code-acp", [], {
      health: { configured: "unavailable", selectable: false },
    }),
    lane("antigravity", "Antigravity", "antigravity-cli", [], {
      executable: false,
      health: { transport: "unavailable", selectable: false },
    }),
    lane(
      "deepseek",
      "DeepSeek",
      "deepseek-claude-agent-acp:node",
      [entry("fixture-gateway", "Fixture Gateway", ["high"])],
      { model_source: "declared" },
    ),
    unkeyed("zai", "Z.ai"),
    unkeyed("zhipu", "Zhipu"),
    unkeyed("moonshot", "Moonshot"),
    unkeyed("minimax", "MiniMax"),
    unkeyed("qwen", "Qwen"),
  ],
};
