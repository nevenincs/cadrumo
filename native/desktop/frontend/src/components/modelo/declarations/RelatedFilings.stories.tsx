import type { Meta, StoryObj } from "@storybook/react-vite";
import { useEffect, useRef, useState } from "react";
import { expect, within } from "storybook/test";
import { byName } from "@/dev/globByName";
import { wholeEnvelopes } from "@/dev/modeloEnvelopePatch";
import { modeloFixture } from "@/dev/modeloFixture";
import type { ModeloPort } from "../../../shell/modelo";
import type { OutputLanguage } from "../../../shell/modeloContract/modelo";
import type { ModeloFilingRecordViewProjection } from "../../../shell/modeloContract/modeloFilingRecord";
import { translator } from "../../../shell/strings";
import { RelatedFilingsDialog } from "./RelatedFilingsDialog";

const envelopes = wholeEnvelopes(
  byName(
    import.meta.glob<unknown>("@fixtures/modelo/*.json", { import: "default" }),
  ),
);

function SavedRead({
  state,
  language,
}: {
  state: "ready" | "loading" | "unavailable";
  language: OutputLanguage;
}) {
  const [initial, setInitial] =
    useState<ModeloFilingRecordViewProjection | null>(null);
  const port = useRef<ModeloPort | null>(null);
  if (!port.current) {
    const fixture = modeloFixture({
      shape: "related-filings",
      translate: translator,
      say: () => undefined,
      signedIn: () => true,
      wait:
        state === "loading"
          ? () => new Promise<void>(() => undefined)
          : async () => undefined,
    });
    port.current =
      state === "unavailable"
        ? {
            ...fixture,
            submit: async () => {
              throw new Error("Synthetic transport unavailable");
            },
          }
        : fixture;
  }
  useEffect(() => {
    let active = true;
    const load = envelopes[`filing-view-130-correction-2-${language}`];
    if (!load) throw new Error("Canonical related filing envelope is missing");
    void load().then((result) => {
      if (active) setInitial(result as ModeloFilingRecordViewProjection);
    });
    return () => {
      active = false;
    };
  }, [language]);
  if (!initial) return null;
  return (
    <RelatedFilingsDialog
      port={port.current}
      filingId={initial.filing_record_id}
      filings={initial.related_filings}
      language={language}
      locale={language}
      title={translator(language)(
        "workspace.declarations.related_filings.title",
      )}
      onClose={() => undefined}
    />
  );
}

const meta: Meta<typeof SavedRead> = {
  title: "Modelo/Related filings",
  component: SavedRead,
  args: { state: "ready" },
  render: (args, { globals }) => (
    <SavedRead
      {...args}
      language={String(globals.locale ?? "en") as OutputLanguage}
    />
  ),
  parameters: { layout: "fullscreen" },
};
export default meta;
type Story = StoryObj<typeof SavedRead>;

export const SavedComparison: Story = {
  play: async ({ canvasElement, globals }) => {
    const t = translator(String(globals.locale ?? "en"));
    const dialog = await within(canvasElement.ownerDocument.body).findByRole(
      "dialog",
    );
    await within(dialog).findByText(
      t("workspace.declarations.related_filings.saved_values"),
    );
    expect(within(dialog).getByRole("combobox")).toBeEnabled();
  },
};
export const Reading: Story = { args: { state: "loading" } };
export const ReadUnavailable: Story = {
  args: { state: "unavailable" },
  play: async ({ canvasElement, globals }) => {
    const t = translator(String(globals.locale ?? "en"));
    const dialog = await within(canvasElement.ownerDocument.body).findByRole(
      "dialog",
    );
    await within(dialog).findByRole("alert");
    expect(
      within(dialog).getByRole("button", {
        name: t("workspace.declarations.related_filings.retry"),
      }),
    ).toBeEnabled();
  },
};
