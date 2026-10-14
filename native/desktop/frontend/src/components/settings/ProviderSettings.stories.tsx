import type { Meta, StoryObj } from "@storybook/react-vite";
import type { ComponentProps } from "react";
import { FIXTURE_SETTINGS_LANES } from "@/dev/providerSettingsFixture";
import { ProviderSettings } from "./ProviderSettings";
import type { ProviderStatus } from "./types";

// Appearance only: the made-up lanes of the scenario host, grouped by
// provider, in each state they can be in. Cadrumo lists no real providers:
// the lanes and where each stands are made up. Saving, disabling and
// resetting do nothing here, and no key is stored or shown.

type Args = ComponentProps<typeof ProviderSettings>;

const NOOP = () => undefined;

/** Where each made-up lane stands; the rest have nothing set. */
const STANDING: Record<string, Partial<ProviderStatus>> = {
  alpha_api: { mode: "key", readiness: "ready", source: "profile" },
  alpha_cli: {
    mode: "provider_sign_in",
    readiness: "ready",
    source: "profile",
    cliState: "installed_signed_in",
  },
  beta_api: { mode: "key", readiness: "not_verified", source: "profile" },
  beta_cli: {
    mode: "provider_sign_in",
    readiness: "sign_in_required",
    reason: "sign_in_with_provider_tool",
    cliState: "installed_signed_out",
  },
  gamma_cli: {
    readiness: "unusable",
    reason: "not_configured",
    cliState: "not_installed",
  },
  delta_cli: { mode: "disabled", readiness: "disabled", cliState: "unknown" },
  relay_cli: {
    mode: "key",
    readiness: "unusable",
    source: "profile",
    baseUrl: "https://gateway.example/relay",
  },
};

export const PROVIDERS: ProviderStatus[] = FIXTURE_SETTINGS_LANES.map(
  (lane): ProviderStatus => ({
    id: lane.id,
    provider: lane.provider,
    name: lane.display_name,
    transport: lane.transport,
    authKind: lane.auth_kind,
    mode: "unset",
    readiness: "missing",
    source: "none",
    ...(lane.transport === "cli" ? { cliState: "installed_signed_in" } : {}),
    ...(lane.default_base_url ? { defaultBaseUrl: lane.default_base_url } : {}),
    ...STANDING[lane.id],
  }),
);

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
  args: { busyId: "alpha_api" },
};

export const Outcomes: Story = {
  name: "Saved but unread, and refused",
  args: {
    outcomes: {
      beta_api: { kind: "saved_unread" },
      relay_cli: { kind: "refused", code: "base_url_rejected" },
      delta_cli: { kind: "refused", code: "revision_conflict" },
    },
  },
};
