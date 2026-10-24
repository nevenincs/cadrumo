import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState } from "react";
import type {
  ModeloAmendmentCorrectionContextV1,
  ModeloWorkHistoryEntryV1,
  OutputLanguage,
} from "../../../shell/modeloContract";
import { useStrings, type Translate } from "../../../shell/strings";
import { HistoryView } from "./HistoryView";

// The History view and the correction dialog on synthetic records in the
// shapes of the worded history read and the amendment context, which the
// scenario port does not serve. Entry words are the catalogue's; the
// correction is never sent from these stories.

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

const money = (casilla: string, box: string, label: string, filed: string) => ({
  casilla_id: casilla,
  box,
  label,
  help: null,
  data_type: "decimal",
  filed_value: filed,
  filed_value_text: `${filed.replace(".", ",")} €`,
  edit_address: { kind: "correction" as const, casilla_id: casilla },
  grammar: {
    data_type: "decimal",
    family: "decimal" as const,
    channel: "decimal" as const,
    max_fraction_digits: 2,
    sign: "any" as const,
    minimum: null,
    maximum: null,
    choices: null,
    min_length: null,
    max_length: null,
    pattern: null,
    ratio_unit: null,
    money_operand_bound: true,
    required: false,
    constraints_declared: true,
  },
  legal_refs: [],
});

const CORRECTION: ModeloAmendmentCorrectionContextV1 = {
  language: "es",
  filed: {
    filing_record_id: "synthetic-filing",
    modelo_title: "Modelo 130 · IRPF pago fraccionado estimación directa",
    period_words: "1.er trimestre 2026",
    declaration_kind: "original",
    declaration_kind_words: "Ordinaria",
    filed_at: "2026-04-18T10:00:00Z",
    filed_on: "18/04/2026",
  },
  kinds: [
    {
      kind: "complementaria",
      words: "Complementaria",
      help: "Ingresa la diferencia cuando el resultado sube.",
    },
    {
      kind: "rectificativa",
      words: "Rectificativa",
      help: "Corrige cuando el resultado baja.",
    },
  ],
  motive_applies: false,
  motive_kind: null,
  motive_help: null,
  motives: [],
  reason_prompt: "¿Por qué corriges esta declaración?",
  rows: [
    money("01", "01", "Ingresos computables", "12400.00"),
    money("02", "02", "Gastos fiscalmente deducibles", "3100.00"),
  ],
};

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
      correction={CORRECTION}
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

export const Correction: Story = {
  name: "History · correction, synthetic context",
  render: (_, { globals }) => (
    <History locale={language(globals)} recorded correcting />
  ),
};
