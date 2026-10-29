import type { Meta, StoryObj } from "@storybook/react-vite";
import { useMemo, useRef } from "react";
import { userEvent } from "storybook/test";
import {
  aeatSyncResultsFixture,
  type AeatSyncResultsMode,
} from "@/dev/aeatSyncResultsFixture";
import { AEAT_SYNC_RESULTS_WORDS } from "@/dev/aeatSyncResultsWords";
import { StringsContext, translator } from "@/shell/strings";
import type { AeatSyncResultsPort } from "../../shell/aeatSyncResults";
import { Results } from "./Results";

// The results of reading from AEAT: one summary for each kind of data, with
// the filed declarations beside the profile's records, the notification list
// and the Borrador import. The port is synthetic; a retry or an import is
// recorded and changes nothing.

type Args = {
  mode: AeatSyncResultsMode | "loading";
  picked?: "file" | "cancelled";
  imported?: "imported" | "nothing_found" | "failed";
};

const noop = () => undefined;

function Page({
  mode,
  picked,
  imported,
  language,
}: Args & { language: string }) {
  // Until the catalogue carries the view's strings, the stories supply the
  // English text; a key the catalogue has wins.
  const translate = useMemo(() => {
    const own = translator(language);
    return (key: string, values?: Record<string, string | number>) => {
      const found = own(key, values);
      if (found !== key) return found;
      const english = AEAT_SYNC_RESULTS_WORDS[key];
      return english === undefined
        ? key
        : english.replace(/\{(\w+)\}/g, (whole, name: string) =>
            values && name in values ? String(values[name]) : whole,
          );
    };
  }, [language]);
  const port = useRef<AeatSyncResultsPort | null>(null);
  port.current ??=
    mode === "loading"
      ? {
          ...aeatSyncResultsFixture("mixed", noop),
          results: () => new Promise(noop),
        }
      : aeatSyncResultsFixture(mode, noop, picked, imported);
  return (
    <StringsContext.Provider value={translate}>
      <div className="mx-auto flex h-full min-h-0 w-full max-w-3xl flex-col p-4">
        <Results
          port={port.current}
          profile="synthetic"
          language={language}
          onOpenAeat={noop}
          onReviewCensus={noop}
        />
      </div>
    </StringsContext.Provider>
  );
}

const meta: Meta<Args> = {
  title: "AEAT data/Results",
  component: Page as never,
  render: (args, { globals }) => (
    <Page {...args} language={String(globals.locale ?? "en")} />
  ),
  parameters: { fill: true, layout: "fullscreen" },
};
export default meta;
type Story = StoryObj<Args>;

/** News, differences, a part that failed, unread notifications. */
export const Mixed: Story = { args: { mode: "mixed" } };
/** Everything read and nothing new. */
export const NothingNew: Story = { args: { mode: "quiet" } };
/** AEAT has nothing to show for any of it. */
export const NothingFound: Story = { args: { mode: "empty" } };
/** Each read failed for a different reason, with a retry. */
export const Failed: Story = { args: { mode: "failed" } };
/** The last read ended without a known answer. */
export const Unknown: Story = { args: { mode: "unknown" } };
/** The results cannot be read. */
export const Unavailable: Story = { args: { mode: "unavailable" } };
/** The results are being read. */
export const Loading: Story = { args: { mode: "loading" } };

const importPdf: NonNullable<Story["play"]> = async ({ canvasElement }) => {
  const button = Array.from(canvasElement.querySelectorAll("button")).find(
    (candidate) => candidate.textContent?.includes("Import PDF"),
  );
  if (button) await userEvent.click(button);
};

/** A Borrador PDF was imported. */
export const BorradorImported: Story = {
  args: { mode: "mixed", picked: "file", imported: "imported" },
  play: importPdf,
};
/** The chosen file held no Borrador. */
export const BorradorNothingFound: Story = {
  args: { mode: "mixed", picked: "file", imported: "nothing_found" },
  play: importPdf,
};
/** The import failed. */
export const BorradorFailed: Story = {
  args: { mode: "mixed", picked: "file", imported: "failed" },
  play: importPdf,
};
