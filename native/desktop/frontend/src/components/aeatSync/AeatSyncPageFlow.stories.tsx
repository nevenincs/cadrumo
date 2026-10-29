import type { Meta, StoryObj } from "@storybook/react-vite";
import { useEffect, useMemo, useRef } from "react";
import { expect, userEvent, waitFor, within } from "storybook/test";
import { aeatSyncFixture } from "@/dev/aeatSyncFixture";
import {
  aeatSyncPrepareFixture,
  type AeatSyncPrepareMode,
} from "@/dev/aeatSyncPrepareFixture";
import {
  aeatSyncResultsFixture,
  type AeatSyncResultsMode,
} from "@/dev/aeatSyncResultsFixture";
import {
  aeatSyncRunFixture,
  type AeatSyncRunMode,
} from "@/dev/aeatSyncRunFixture";
import { ProvisioningStage } from "@/dev/ProvisioningStage";
import type { SetupShape } from "@/dev/setupFixture";
import { useProvisioning } from "../../shell/provisioning";
import { translator } from "../../shell/strings";
import { AeatSyncPage } from "./AeatSyncPage";

// The whole AEAT data page over synthetic ports: the overview, "Update from
// AEAT" through the checks that block (the secure browser, AEAT access) or
// straight on, the update as it goes, and its results. Nothing is read from
// AEAT; each story names where the update ends.

type Args = {
  /** What the check before the update finds. */
  before: AeatSyncPrepareMode;
  /** Where the update ends. */
  run: AeatSyncRunMode;
  results: AeatSyncResultsMode;
  shape: SetupShape;
};

const noop = () => undefined;

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
  before,
  run,
  results,
  shape,
  language,
}: Args & { language: string }) {
  const page = useRef<HTMLElement | null>(null);
  const ready = useRef(false);
  const ports = useMemo(() => {
    const running = aeatSyncRunFixture("idle", noop);
    return {
      status: aeatSyncFixture("mixed", noop, () => running.begin(run)),
      running,
      results: aeatSyncResultsFixture(results, noop),
      prepare: aeatSyncPrepareFixture(before, {
        browserReady: () => ready.current,
      }),
    };
  }, [before, run, results]);
  const starts = useMemo(() => [{ item: "browser", approve: true }], []);
  return (
    <ProvisioningStage
      shape={shape}
      latencyMs={1500}
      starts={before === "browser_missing" ? starts : []}
    >
      <Reader ready={ready} />
      <div className="flex h-full min-h-0 flex-col">
        <AeatSyncPage
          port={ports.status}
          results={ports.results}
          run={ports.running}
          prepare={ports.prepare}
          reader="synthetic"
          language={language}
          shown
          page={page}
          onOpenAccess={noop}
          onOpenAeat={noop}
          onReviewCensus={noop}
        />
      </div>
    </ProvisioningStage>
  );
}

const meta: Meta<Args> = {
  title: "AEAT data/Page",
  args: { before: "ready", run: "done", results: "mixed", shape: "ready" },
  render: (args, { globals }) => (
    <Screen
      key={`${args.before}${args.run}${args.results}${args.shape}`}
      {...args}
      language={String(globals.locale ?? "en")}
    />
  ),
  parameters: { fill: true, layout: "fullscreen" },
};
export default meta;
type Story = StoryObj<Args>;

const update: NonNullable<Story["play"]> = async ({
  canvasElement,
  globals,
}) => {
  const words = translator(String(globals.locale ?? "en"));
  const canvas = within(canvasElement);
  const button = await canvas.findByRole("button", {
    name: words("desktop.aeat_sync.bring_all"),
  });
  await waitFor(() => expect(button).toBeEnabled());
  await userEvent.click(button);
};

/** What was brought and when, with "Update from AEAT". */
export const Overview: Story = {};
/** Update from AEAT: nothing blocks, the update goes on in view and ends in
 * its results. */
export const UpdateToResults: Story = { play: update };
/** The update goes on until it is stopped. */
export const Running: Story = { args: { run: "running" }, play: update };
/** The secure browser is missing: it is installed and the update goes on. */
export const BrowserMissing: Story = {
  args: { before: "browser_missing", shape: "fresh" },
  play: update,
};
/** AEAT access is not set up in the profile. */
export const AccessNotSetUp: Story = {
  args: { before: "access_missing" },
  play: update,
};
/** AEAT ends the session part-way: sign in again to carry on. */
export const SessionTimedOut: Story = {
  args: { run: "paused" },
  play: update,
};
/** Some parts could not be updated. */
export const PartialFailure: Story = {
  args: { run: "partial_failure", results: "failed" },
  play: update,
};
/** A part whose outcome could not be confirmed. */
export const UnknownOutcome: Story = {
  args: { run: "unknown", results: "unknown" },
  play: update,
};
/** AEAT had nothing new. */
export const NothingNew: Story = {
  args: { run: "nothing_found", results: "quiet" },
  play: update,
};
