import type { Meta, StoryObj } from "@storybook/react-vite";
import type { ComponentProps } from "react";
import { ProviderSettings } from "./ProviderSettings";
import type { ProviderStatus } from "./types";

// Appearance only: the providers of a made-up profile in each state they
// can be in. Saving, turning off and resetting do nothing here, and no key
// is stored or shown.

type Args = ComponentProps<typeof ProviderSettings>;

const NOOP = () => undefined;

export const PROVIDERS: ProviderStatus[] = [
  {
    id: "anthropic",
    name: "Claude",
    transport: "api",
    authKind: "api_key",
    consumers: ["assistant", "extraction"],
    mode: "key",
    readiness: "ready",
    source: "profile",
  },
  {
    id: "claude",
    name: "Claude",
    transport: "cli",
    authKind: "oauth_token_or_provider_sign_in",
    consumers: ["assistant"],
    mode: "provider_sign_in",
    readiness: "ready",
    source: "profile",
  },
  {
    id: "openai",
    name: "OpenAI",
    transport: "api",
    authKind: "api_key",
    consumers: ["assistant"],
    mode: "key",
    readiness: "not_verified",
    source: "profile",
  },
  {
    id: "gemini",
    name: "Gemini",
    transport: "api",
    authKind: "api_key",
    consumers: ["extraction"],
    mode: "unset",
    readiness: "missing",
    source: "none",
  },
  {
    id: "deepseek",
    name: "DeepSeek",
    transport: "cli",
    authKind: "api_key_with_base_url",
    consumers: ["assistant"],
    mode: "unset",
    readiness: "missing",
    source: "none",
    defaultBaseUrl: "https://gateway.example/deepseek",
  },
  {
    id: "qwen",
    name: "Qwen",
    transport: "cli",
    authKind: "api_key_with_base_url",
    consumers: ["assistant"],
    mode: "key",
    readiness: "unusable",
    source: "profile",
    baseUrl: "https://gateway.example/qwen",
  },
  {
    id: "kimi",
    name: "Kimi",
    transport: "cli",
    authKind: "api_key",
    consumers: ["assistant"],
    mode: "disabled",
    readiness: "disabled",
    source: "none",
  },
  {
    id: "codex",
    name: "Codex",
    transport: "cli",
    authKind: "provider_sign_in_only",
    consumers: ["assistant"],
    mode: "unset",
    readiness: "sign_in_required",
    source: "none",
  },
];

const meta = {
  title: "Shell/Settings/AI providers",
  parameters: { surface: "chrome" },
  args: {
    providers: PROVIDERS,
    development: false,
    onSave: NOOP,
    onTurnOff: NOOP,
    onReset: NOOP,
    onRefresh: NOOP,
  },
  render: (args: Args) => (
    <div className="w-settings max-w-full">
      <ProviderSettings {...args} />
    </div>
  ),
} satisfies Meta<Args>;
export default meta;
type Story = StoryObj<typeof meta>;

export const Installed: Story = {};

export const Development: Story = {
  name: "Development build",
  args: {
    development: true,
    // Where no key is set, the development environment's is used.
    providers: PROVIDERS.map((provider) =>
      provider.mode === "unset" && provider.authKind !== "provider_sign_in_only"
        ? { ...provider, readiness: "ready", source: "environment" }
        : provider,
    ),
  },
};

export const Saving: Story = {
  args: { busyId: "openai" },
};

export const Outcomes: Story = {
  name: "Saved but unread, and refused",
  args: {
    outcomes: {
      openai: { kind: "saved_unread" },
      qwen: { kind: "refused", code: "base_url_rejected" },
      kimi: { kind: "refused", code: "revision_conflict" },
    },
  },
};
