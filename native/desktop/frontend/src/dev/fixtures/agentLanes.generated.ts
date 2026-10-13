// GENERATED FILE - DO NOT EDIT.
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
// Agent source digest (sha256, line endings normalised): 645dd5f528373a4d87ff6bbc6f064ac837567a151b0dab3c5ef370ca5eff1c8d

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

export const DECLARED_LANES: readonly DeclaredLane[] = [
  {
    provider_id: "antigravity",
    transport: "cli",
    display_name: "Antigravity",
    execution_mode: "antigravity-cli",
    executable: true,
    model_source: "catalog",
    catalog_revision: null,
    native_controls: [],
    capability_proofs: [
      { capability: "tool_access", entry: "cadrumo" },
      { capability: "writing", entry: "cadrumo" },
      { capability: "web_retrieval", entry: null },
      { capability: "image_reading", entry: null },
      { capability: "pdf_reading", entry: null },
    ],
  },
  {
    provider_id: "claude",
    transport: "api",
    display_name: "Claude",
    execution_mode: "anthropic-api",
    executable: true,
    model_source: "catalog",
    catalog_revision: null,
    native_controls: [],
    capability_proofs: [
      { capability: "tool_access", entry: "cadrumo" },
      { capability: "writing", entry: "cadrumo" },
      { capability: "web_retrieval", entry: null },
      { capability: "image_reading", entry: null },
      { capability: "pdf_reading", entry: null },
    ],
  },
  {
    provider_id: "claude",
    transport: "cli",
    display_name: "Claude",
    execution_mode: "claude-agent-acp:node",
    executable: true,
    model_source: "catalog",
    catalog_revision: null,
    native_controls: [],
    capability_proofs: [
      { capability: "tool_access", entry: "cadrumo" },
      { capability: "writing", entry: "cadrumo" },
      { capability: "web_retrieval", entry: null },
      { capability: "image_reading", entry: null },
      { capability: "pdf_reading", entry: null },
    ],
  },
  {
    provider_id: "codex",
    transport: "api",
    display_name: "Codex",
    execution_mode: "openai-api",
    executable: true,
    model_source: "catalog",
    catalog_revision: null,
    native_controls: [],
    capability_proofs: [
      { capability: "tool_access", entry: "cadrumo" },
      { capability: "writing", entry: "cadrumo" },
      { capability: "web_retrieval", entry: null },
      { capability: "image_reading", entry: null },
      { capability: "pdf_reading", entry: null },
    ],
  },
  {
    provider_id: "codex",
    transport: "cli",
    display_name: "Codex",
    execution_mode: "codex-app-server",
    executable: true,
    model_source: "catalog",
    catalog_revision: null,
    native_controls: [],
    capability_proofs: [
      { capability: "tool_access", entry: "cadrumo" },
      { capability: "writing", entry: "cadrumo" },
      { capability: "web_retrieval", entry: null },
      { capability: "image_reading", entry: null },
      { capability: "pdf_reading", entry: null },
    ],
  },
  {
    provider_id: "deepseek",
    transport: "cli",
    display_name: "DeepSeek",
    execution_mode: "deepseek-claude-agent-acp:node",
    executable: true,
    model_source: "declared",
    catalog_revision: "declared",
    native_controls: [
      {
        control_id: "effort",
        kind: "thought_level",
        display_name: "Effort",
        options: [{ option_id: "max", display_name: "max", description: null }],
        default_option_id: null,
        description: null,
      },
    ],
    capability_proofs: [
      { capability: "tool_access", entry: "cadrumo" },
      { capability: "writing", entry: "cadrumo" },
      { capability: "web_retrieval", entry: null },
      { capability: "image_reading", entry: null },
      { capability: "pdf_reading", entry: null },
    ],
  },
  {
    provider_id: "kimi",
    transport: "cli",
    display_name: "Kimi Code",
    execution_mode: "kimi-code-acp",
    executable: true,
    model_source: "catalog",
    catalog_revision: null,
    native_controls: [],
    capability_proofs: [
      { capability: "tool_access", entry: "cadrumo" },
      { capability: "writing", entry: "cadrumo" },
      { capability: "web_retrieval", entry: null },
      { capability: "image_reading", entry: null },
      { capability: "pdf_reading", entry: null },
    ],
  },
  {
    provider_id: "minimax",
    transport: "cli",
    display_name: "MiniMax",
    execution_mode: "minimax-claude-agent-acp:node",
    executable: true,
    model_source: "declared",
    catalog_revision: "declared",
    native_controls: [],
    capability_proofs: [
      { capability: "tool_access", entry: "cadrumo" },
      { capability: "writing", entry: "cadrumo" },
      { capability: "web_retrieval", entry: null },
      { capability: "image_reading", entry: null },
      { capability: "pdf_reading", entry: null },
    ],
  },
  {
    provider_id: "moonshot",
    transport: "cli",
    display_name: "Moonshot AI",
    execution_mode: "moonshot-claude-agent-acp:node",
    executable: true,
    model_source: "declared",
    catalog_revision: "declared",
    native_controls: [
      {
        control_id: "effort",
        kind: "thought_level",
        display_name: "Effort",
        options: [{ option_id: "max", display_name: "max", description: null }],
        default_option_id: null,
        description: null,
      },
    ],
    capability_proofs: [
      { capability: "tool_access", entry: "cadrumo" },
      { capability: "writing", entry: "cadrumo" },
      { capability: "web_retrieval", entry: null },
      { capability: "image_reading", entry: null },
      { capability: "pdf_reading", entry: null },
    ],
  },
  {
    provider_id: "qwen",
    transport: "cli",
    display_name: "Qwen (Alibaba Model Studio)",
    execution_mode: "qwen-claude-agent-acp:node",
    executable: true,
    model_source: "declared",
    catalog_revision: "declared",
    native_controls: [],
    capability_proofs: [
      { capability: "tool_access", entry: "cadrumo" },
      { capability: "writing", entry: "cadrumo" },
      { capability: "web_retrieval", entry: null },
      { capability: "image_reading", entry: null },
      { capability: "pdf_reading", entry: null },
    ],
  },
  {
    provider_id: "zai",
    transport: "cli",
    display_name: "Z.ai",
    execution_mode: "zai-claude-agent-acp:node",
    executable: true,
    model_source: "declared",
    catalog_revision: "declared",
    native_controls: [],
    capability_proofs: [
      { capability: "tool_access", entry: "cadrumo" },
      { capability: "writing", entry: "cadrumo" },
      { capability: "web_retrieval", entry: null },
      { capability: "image_reading", entry: null },
      { capability: "pdf_reading", entry: null },
    ],
  },
  {
    provider_id: "zhipu",
    transport: "cli",
    display_name: "Zhipu AI",
    execution_mode: "zhipu-claude-agent-acp:node",
    executable: true,
    model_source: "declared",
    catalog_revision: "declared",
    native_controls: [],
    capability_proofs: [
      { capability: "tool_access", entry: "cadrumo" },
      { capability: "writing", entry: "cadrumo" },
      { capability: "web_retrieval", entry: null },
      { capability: "image_reading", entry: null },
      { capability: "pdf_reading", entry: null },
    ],
  },
];

export const DECLARED_SETTINGS_LANES: readonly DeclaredSettingsLane[] = [
  {
    id: "claude_api",
    provider: "claude",
    transport: "api",
    display_name: "Claude",
    default_base_url: null,
    auth_kind: "api_key",
  },
  {
    id: "antigravity_cli",
    provider: "antigravity",
    transport: "cli",
    display_name: "Antigravity",
    default_base_url: null,
    auth_kind: "provider_sign_in_only",
  },
  {
    id: "claude_cli",
    provider: "claude",
    transport: "cli",
    display_name: "Claude",
    default_base_url: null,
    auth_kind: "oauth_token_or_provider_sign_in",
  },
  {
    id: "codex_cli",
    provider: "codex",
    transport: "cli",
    display_name: "Codex",
    default_base_url: null,
    auth_kind: "provider_sign_in_only",
  },
  {
    id: "deepseek_cli",
    provider: "deepseek",
    transport: "cli",
    display_name: "DeepSeek",
    default_base_url: "https://api.deepseek.com/anthropic",
    auth_kind: "api_key_with_base_url",
  },
  {
    id: "kimi_cli",
    provider: "kimi",
    transport: "cli",
    display_name: "Kimi Code",
    default_base_url: null,
    auth_kind: "api_key",
  },
  {
    id: "minimax_cli",
    provider: "minimax",
    transport: "cli",
    display_name: "MiniMax",
    default_base_url: "https://api.minimax.io/anthropic",
    auth_kind: "api_key_with_base_url",
  },
  {
    id: "moonshot_cli",
    provider: "moonshot",
    transport: "cli",
    display_name: "Moonshot AI",
    default_base_url: "https://api.moonshot.ai/anthropic",
    auth_kind: "api_key_with_base_url",
  },
  {
    id: "codex_api",
    provider: "codex",
    transport: "api",
    display_name: "Codex",
    default_base_url: null,
    auth_kind: "api_key",
  },
  {
    id: "qwen_cli",
    provider: "qwen",
    transport: "cli",
    display_name: "Qwen (Alibaba Model Studio)",
    default_base_url: null,
    auth_kind: "api_key_with_base_url",
  },
  {
    id: "zai_cli",
    provider: "zai",
    transport: "cli",
    display_name: "Z.ai",
    default_base_url: "https://api.z.ai/api/anthropic",
    auth_kind: "api_key_with_base_url",
  },
  {
    id: "zhipu_cli",
    provider: "zhipu",
    transport: "cli",
    display_name: "Zhipu AI",
    default_base_url: "https://open.bigmodel.cn/api/anthropic",
    auth_kind: "api_key_with_base_url",
  },
];
