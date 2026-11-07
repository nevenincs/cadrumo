import type { Meta, StoryObj } from "@storybook/react-vite";
import { useEffect, useRef, useState } from "react";
import { expect, userEvent, waitFor, within } from "storybook/test";
import { modeloFixture, type ModeloShape } from "@/dev/modeloFixture";
import { byName } from "@/dev/globByName";
import { wholeEnvelopes } from "@/dev/modeloEnvelopePatch";
import type { ModeloPort } from "../../../shell/modelo";
import type { OutputLanguage } from "../../../shell/modeloContract/modelo";
import type { ModeloWorkAmendmentContextProjection } from "../../../shell/modeloContract/modeloWorkAmendmentContext";
import { translator } from "../../../shell/strings";
import { WorkspaceScreen } from "./WorkspaceScreen";
import { CorrectionDialog } from "./CorrectionDialog";

const envelopes = wholeEnvelopes(
  byName(
    import.meta.glob<unknown>("@fixtures/modelo/*.json", {
      import: "default",
    }),
  ),
);

async function correctionContext() {
  const load = envelopes["amendment-context-130"];
  if (!load)
    throw new Error("The canonical correction context is not generated");
  return (await load()) as ModeloWorkAmendmentContextProjection;
}

const language = (globals: Record<string, unknown>) =>
  String(globals.locale ?? "en") as OutputLanguage;

function CorrectionWorkspace({
  shape,
  locale,
}: {
  shape: ModeloShape;
  locale: OutputLanguage;
}) {
  const [context, setContext] =
    useState<ModeloWorkAmendmentContextProjection | null>(null);
  const port = useRef<ModeloPort | null>(null);
  port.current ??= modeloFixture({
    say: () => undefined,
    translate: translator,
    wait: async () => undefined,
    signedIn: () => true,
    shape,
  });
  useEffect(() => {
    let current = true;
    void correctionContext().then((read) => {
      if (current) setContext(read);
    });
    return () => {
      current = false;
    };
  }, []);
  if (!context) return null;
  return (
    <div className="flex h-full min-h-0 flex-col">
      <WorkspaceScreen
        port={port.current}
        workUnitId={context.unit.work_unit_id}
        language={locale}
        locale={locale}
        onBack={() => undefined}
        onOpenSurface={() => undefined}
        canOpenSurface={() => true}
        openLink={() => undefined}
        initialView="history"
      />
    </div>
  );
}

const meta: Meta = {
  title: "Modelo/Corrections",
  parameters: { fill: true, layout: "fullscreen" },
};
export default meta;
type Story = StoryObj;

async function openCorrection(
  canvasElement: HTMLElement,
  locale: OutputLanguage,
) {
  const t = translator(locale);
  const trigger = await within(canvasElement).findByRole("button", {
    name: t("workspace.modelo.correction.title"),
  });
  await userEvent.click(trigger);
  const dialog = await within(canvasElement.ownerDocument.body).findByRole(
    "dialog",
    { name: t("workspace.modelo.correction.title") },
  );
  const context = (await correctionContext()).correction;
  if (!context) throw new Error("The fixture offers no correction context");
  await within(dialog).findByRole("textbox", { name: context.reason_prompt });
  return { dialog, context, t };
}

async function submitCorrection(
  canvasElement: HTMLElement,
  locale: OutputLanguage,
) {
  const opened = await openCorrection(canvasElement, locale);
  const { dialog, context, t } = opened;
  const confirm = within(dialog).getByRole("button", {
    name: t("workspace.modelo.correction.confirm"),
  });
  expect(confirm).toBeDisabled();
  await userEvent.type(
    within(dialog).getByRole("textbox", { name: context.reason_prompt }),
    "Income was understated in the recorded declaration.",
  );
  // This is the entry for which the canonical scenario records a preflight.
  const row = context.rows.find((entry) => entry.casilla_id === "01");
  if (!row) throw new Error("The canonical correction entry is missing");
  await userEvent.type(
    within(dialog).getByRole("textbox", {
      name: t("workspace.modelo.editor.new_value_for_box", {
        box: row.box ?? row.label,
      }),
    }),
    "10000",
  );
  expect(confirm).toBeEnabled();
  await userEvent.click(confirm);
  return { ...opened, confirm };
}

export const FiledAndProposed: Story = {
  name: "Filed values and permitted correction controls",
  render: (_, { globals }) => (
    <CorrectionWorkspace shape="receipt" locale={language(globals)} />
  ),
  play: async ({ canvasElement, globals }) => {
    const { dialog, context, t } = await openCorrection(
      canvasElement,
      language(globals),
    );
    for (const kind of context.kinds)
      expect(
        within(dialog).getByText(kind.words, { exact: true }),
      ).toBeVisible();
    const row = context.rows.find((entry) => entry.casilla_id === "01");
    if (!row) throw new Error("The canonical correction entry is missing");
    const input = within(dialog).getByRole("textbox", {
      name: t("workspace.modelo.editor.new_value_for_box", {
        box: row.box ?? row.label,
      }),
    });
    expect(input.closest("li")).toHaveTextContent(row.filed_value_text);
    expect(input).toHaveValue("");
    await userEvent.type(input, "10000");
    expect(input.closest("li")).toHaveTextContent(row.filed_value_text);
    await userEvent.keyboard("{Escape}");
    await waitFor(() => expect(dialog).not.toBeInTheDocument());
  },
};

export const Saved: Story = {
  name: "A successful correction returns to the refreshed declaration",
  render: (_, { globals }) => (
    <CorrectionWorkspace shape="receipt" locale={language(globals)} />
  ),
  play: async ({ canvasElement, globals }) => {
    const { dialog } = await submitCorrection(canvasElement, language(globals));
    await waitFor(() => expect(dialog).not.toBeInTheDocument());
  },
};

export const Refused: Story = {
  name: "A refused correction preserves the proposed values",
  render: (_, { globals }) => (
    <CorrectionWorkspace
      shape="correction-refused"
      locale={language(globals)}
    />
  ),
  play: async ({ canvasElement, globals }) => {
    const { dialog, t } = await submitCorrection(
      canvasElement,
      language(globals),
    );
    await within(dialog).findByText(t("workspace.modelo.outcome.refused"));
    expect(dialog).toBeVisible();
  },
};

export const UnknownSettlement: Story = {
  name: "Unknown settlement holds further corrections",
  render: (_, { globals }) => (
    <CorrectionWorkspace
      shape="correction-unknown"
      locale={language(globals)}
    />
  ),
  play: async ({ canvasElement, globals }) => {
    const { dialog, confirm, t } = await submitCorrection(
      canvasElement,
      language(globals),
    );
    await within(dialog).findByText(t("workspace.modelo.write_hold.unknown"));
    await waitFor(() => expect(confirm).toBeDisabled());
    expect(dialog).toBeVisible();
  },
};

export const LoadingContext: Story = {
  name: "Correction options are being read",
  render: (_, { globals }) => (
    <CorrectionDialog
      open
      context={null}
      contextState={{
        kind: "loading",
        words: translator(language(globals))(
          "workspace.modelo.correction.loading",
        ),
      }}
      onCorrect={null}
      onOpenChange={() => undefined}
    />
  ),
  play: async ({ canvasElement, globals }) => {
    const t = translator(language(globals));
    const dialog = within(canvasElement.ownerDocument.body).getByRole("dialog");
    expect(within(dialog).getByRole("status")).toHaveTextContent(
      t("workspace.modelo.correction.loading"),
    );
    expect(
      within(dialog).getByRole("button", {
        name: t("workspace.modelo.correction.confirm"),
      }),
    ).toBeDisabled();
  },
};

export const UnavailableContext: Story = {
  name: "Unavailable context offers no correction",
  render: (_, { globals }) => (
    <CorrectionDialog
      open
      context={null}
      contextState={{
        kind: "unavailable",
        words: translator(language(globals))(
          "workspace.modelo.correction.unavailable",
        ),
      }}
      onCorrect={null}
      onOpenChange={() => undefined}
    />
  ),
  play: async ({ canvasElement, globals }) => {
    const t = translator(language(globals));
    const dialog = within(canvasElement.ownerDocument.body).getByRole("dialog");
    expect(within(dialog).getByRole("alert")).toHaveTextContent(
      t("workspace.modelo.correction.unavailable"),
    );
    expect(
      within(dialog).getByRole("button", {
        name: t("workspace.modelo.correction.confirm"),
      }),
    ).toBeDisabled();
  },
};
