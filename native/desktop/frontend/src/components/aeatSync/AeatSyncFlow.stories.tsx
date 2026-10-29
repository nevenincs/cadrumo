import type { Meta, StoryObj } from "@storybook/react-vite";
import { useEffect, useMemo, useRef } from "react";
import {
  aeatSyncPrepareFixture,
  type AeatSyncPrepareMode,
} from "@/dev/aeatSyncPrepareFixture";
import { ProvisioningStage } from "@/dev/ProvisioningStage";
import type { SetupShape } from "@/dev/setupFixture";
import { useProvisioning } from "../../shell/provisioning";
import { AeatSyncFlow } from "./AeatSyncFlow";

// What stands between "Update from AEAT" and the first read, over the
// scenario host's synthetic setup and AEAT checks: the secure browser
// missing, installing and failing; AEAT access not set up; approval on the
// phone; and a session that ran out part-way.

const noop = () => undefined;

type Args = {
  mode: AeatSyncPrepareMode;
  shape: SetupShape;
  reason?: "start" | "session_ended";
  /** Installs the browser as soon as the setup is read, approving its plan. */
  installing?: boolean;
};

/** Tells the synthetic check when the staged setup has made the browser
 * ready, as the host's own check reads it. */
function Reader({ ready }: { ready: { current: boolean } }) {
  const store = useProvisioning();
  const state = store.rows.find((row) => row.kind === "browser")?.state;
  useEffect(() => {
    ready.current = state === "ready";
  }, [ready, state]);
  return null;
}

function Screen({
  mode,
  shape,
  reason,
  installing,
  language,
}: Args & { language: string }) {
  const ready = useRef(false);
  const port = useMemo(
    () => aeatSyncPrepareFixture(mode, { browserReady: () => ready.current }),
    [mode],
  );
  const starts = useMemo(
    () => (installing ? [{ item: "browser", approve: true }] : []),
    [installing],
  );
  return (
    <ProvisioningStage shape={shape} latencyMs={2500} starts={starts}>
      <Reader ready={ready} />
      <div className="mx-auto grid w-full max-w-xl gap-3 p-4">
        <AeatSyncFlow
          port={port}
          locale={language}
          {...(reason ? { reason } : {})}
          onReady={noop}
          onClose={noop}
          onOpenAccess={noop}
        />
      </div>
    </ProvisioningStage>
  );
}

const meta: Meta<Args> = {
  title: "AEAT data/Before updating",
  args: { mode: "browser_missing", shape: "fresh" },
  render: (args, { globals }) => (
    <Screen {...args} language={String(globals.locale ?? "en")} />
  ),
  parameters: { layout: "fullscreen" },
};
export default meta;
type Story = StoryObj<Args>;

/** The secure browser is not installed: why it is needed, its size, and
 * "Install and continue". */
export const BrowserMissing: Story = {};
/** The install is running: the setup's own progress and cancel; the update
 * continues by itself when it finishes. */
export const BrowserInstalling: Story = { args: { installing: true } };
/** The install failed or the network is blocked: the setup's own wording and
 * recovery, and a way back. */
export const BrowserInstallFailed: Story = {
  args: { mode: "browser_attention", shape: "offline" },
};
/** AEAT access is not set up yet in the profile. */
export const AccessNotSetUp: Story = {
  args: { mode: "access_missing", shape: "ready" },
};
/** AEAT asks the person to approve the sign-in on their phone. */
export const WaitingForPhone: Story = {
  args: { mode: "phone", shape: "ready" },
};
/** AEAT ended the session part-way through an update. */
export const SessionTimedOut: Story = {
  args: { mode: "ready", shape: "ready", reason: "session_ended" },
};
