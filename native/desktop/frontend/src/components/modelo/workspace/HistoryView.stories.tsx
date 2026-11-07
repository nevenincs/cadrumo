import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState } from "react";
import type { OutputLanguage } from "../../../shell/modeloContract/modelo";
import type { ModeloWorkHistoryEntryV1 } from "../../../shell/modeloContract/modeloWorkHistory";
import { useStrings, type Translate } from "../../../shell/strings";
import { HistoryView } from "./HistoryView";

// Synthetic timeline entries exercise presentation only. Correction behavior
// is covered by the canonical application envelopes in Corrections.stories.

const language = (globals: Record<string, unknown>) =>
  String(globals.locale ?? "en") as OutputLanguage;

const meta: Meta = {
  title: "Modelo/Workspace/History",
  parameters: { layout: "padded" },
};
export default meta;
type Story = StoryObj;

function entries(t: Translate): ModeloWorkHistoryEntryV1[] {
  return (
    [
      ["filed", 18],
      ["exported", 17],
      ["verified", 16],
      ["calculated", 15],
      ["renamed", 12],
      ["created", 10],
    ] as const
  ).map(([kind, day]) => ({
    event_id: `synthetic-${kind}`,
    kind,
    words: t(`workspace.declarations.lifecycle.${kind}`),
    detail: kind === "renamed" ? "130 1T → Modelo 130 1T 2026" : null,
    occurred_at: `2026-04-${String(day).padStart(2, "0")}T10:00:00Z`,
  }));
}

function History({
  locale,
  recorded,
  correcting: initiallyCorrecting = false,
}: {
  locale: OutputLanguage;
  recorded: boolean;
  correcting?: boolean;
}) {
  const t = useStrings();
  const [correcting, setCorrecting] = useState(initiallyCorrecting);
  return (
    <HistoryView
      entries={entries(t)}
      unit={{ name: "Modelo 130 1T 2026", updated_at: "2026-04-18T10:00:00Z" }}
      recorded={recorded}
      locale={locale}
      notice={null}
      correcting={correcting}
      onCorrectingChange={setCorrecting}
      correction={null}
      onRename={async () => true}
      onDiscard={async () => true}
      onCorrect={null}
    />
  );
}

export const History130: Story = {
  name: "History · synthetic entries",
  render: (_, { globals }) => (
    <History locale={language(globals)} recorded={false} />
  ),
};
