import type { Meta, StoryObj } from "@storybook/react-vite";
import { useEffect, useRef, useState } from "react";
import { expect, userEvent, waitFor } from "storybook/test";
import { modeloFixture, type ModeloShape } from "@/dev/modeloFixture";
import { translator } from "../../../shell/strings";
import type { ModeloPort } from "../../../shell/modelo";
import type { OutputLanguage } from "../../../shell/modeloContract/modelo";
import type {
  ModeloFormElection,
  PublicModeloFormExportOffer,
} from "../../../shell/modeloContract/modeloWorkForm";
import { Settlement } from "./Settlement";
import { WorkspaceScreen } from "./WorkspaceScreen";
import { byName } from "@/dev/globByName";

// How the result is settled. The component stories draw the export offer the
// application served for a result in each state a settlement can be in, and
// the workspace story draws it where the filer answers it, on the Modelo 100
// of a salaried filer read within the filing period. Every sentence and every
// amount is the application's; none is written here.

const UNIT = "b1c431589384a105701ba15942606b5f5667cb677d6fa62e743cd0293f9baee4";

const offers = byName(
  import.meta.glob<PublicModeloFormExportOffer>(
    "@fixtures/modelo/settlement-100-0A-*.json",
    { import: "default" },
  ),
);

const language = (globals: Record<string, unknown>) =>
  String(globals.locale ?? "en") as OutputLanguage;

/** The offer the application served for `state`, in `locale`, once read. */
function Offer({ state, locale }: { state: string; locale: OutputLanguage }) {
  const [offer, setOffer] = useState<PublicModeloFormExportOffer | null>(null);
  const [answers, setAnswers] = useState<
    Partial<Record<ModeloFormElection, string>>
  >({});
  useEffect(() => {
    const load = offers[`settlement-100-0A-${state}-${locale}`];
    if (!load) throw new Error(`No settlement is stored as ${state}`);
    void load().then((read) => setOffer(structuredClone(read)));
  }, [state, locale]);
  if (!offer) return null;
  return (
    <div className="@container max-w-3xl p-6">
      <Settlement
        questions={offer.elections}
        answers={answers}
        onAnswer={(election, value) =>
          setAnswers((now) => ({ ...now, [election]: value }))
        }
      />
    </div>
  );
}

function Screen({
  shape,
  locale,
}: {
  shape: ModeloShape;
  locale: OutputLanguage;
}) {
  const port = useRef<ModeloPort | null>(null);
  port.current ??= modeloFixture({
    say: () => undefined,
    translate: translator,
    wait: async () => undefined,
    signedIn: () => true,
    shape,
  });
  return (
    <div className="flex h-full min-h-0 flex-col">
      <WorkspaceScreen
        port={port.current}
        workUnitId={UNIT}
        language={locale}
        locale={locale}
        onBack={() => undefined}
        onOpenSurface={() => undefined}
        canOpenSurface={() => true}
        openLink={() => undefined}
        initialView="file"
      />
    </div>
  );
}

const meta: Meta = {
  title: "Modelo/Settlement",
  parameters: { fill: true, layout: "fullscreen" },
};
export default meta;
type Story = StoryObj;

const settlement = (canvasElement: HTMLElement) =>
  waitFor(
    () => {
      const found =
        canvasElement.querySelector<HTMLElement>("[data-settlement]");
      if (!found) throw new Error("the settlement is not drawn yet");
      return found;
    },
    { timeout: 15_000 },
  );

const election = (canvasElement: HTMLElement, name: string) => {
  const found = canvasElement.querySelector<HTMLElement>(
    `[data-election=${name}]`,
  );
  if (!found) throw new Error(`the ${name} question is not drawn`);
  return found;
};

export const SplitStatesBothAmounts: Story = {
  name: "Within the period: the split states both instalments, each marked advisory",
  render: (_, { globals }) => (
    <Offer state="least" locale={language(globals)} />
  ),
  play: async ({ canvasElement }) => {
    await settlement(canvasElement);
    const question = election(canvasElement, "instalment");
    expect(question).toHaveAttribute("data-state", "available");
    const figures = question.querySelectorAll<HTMLElement>("[data-figure]");
    expect(figures.length).toBe(2);
    // The amounts are the application's exact decimal text, drawn in its
    // words; a figure no official rule fixes is marked and says why.
    for (const figure of figures) {
      expect(figure).toHaveAttribute("data-advisory", "true");
      expect(figure).toHaveAttribute("data-amount", "0.01");
      expect(figure.querySelector("[data-slot=badge]")).not.toBeNull();
    }
  },
};

export const NothingLeftForTheSecond: Story = {
  name: "An amount whose second instalment would be nothing: paid at once, in the application's words",
  render: (_, { globals }) => (
    <Offer state="nothing" locale={language(globals)} />
  ),
  play: async ({ canvasElement }) => {
    await settlement(canvasElement);
    const question = election(canvasElement, "instalment");
    expect(question).toHaveAttribute("data-state", "unavailable");
    expect(question).toHaveAttribute(
      "data-reason",
      "second_instalment_nothing",
    );
    expect(question.querySelector("[data-figure]")).toBeNull();
    expect(question.querySelector("select")).toBeNull();
    expect(question.textContent).toMatch(/\S/);
    // Paying it all at once stays open.
    expect(
      election(canvasElement, "payment").querySelector("select"),
    ).not.toBeNull();
  },
};

export const SettlementUnsupported: Story = {
  name: "A settlement Cadrumo does not compute: refused, not offered",
  render: (_, { globals }) => (
    <Offer state="unsupported" locale={language(globals)} />
  ),
  play: async ({ canvasElement }) => {
    await settlement(canvasElement);
    for (const name of ["payment", "instalment"]) {
      const question = election(canvasElement, name);
      expect(question).toHaveAttribute("data-reason", "settlement_unsupported");
      expect(question.querySelector("select")).toBeNull();
      expect(question.querySelector("[data-figure]")).toBeNull();
    }
  },
};

export const PastTheFilingPeriod: Story = {
  name: "After the filing period: the split is unavailable and says why",
  render: (_, { globals }) => (
    <Offer state="overdue" locale={language(globals)} />
  ),
  play: async ({ canvasElement }) => {
    await settlement(canvasElement);
    const question = election(canvasElement, "instalment");
    expect(question).toHaveAttribute("data-reason", "past_filing_window");
    expect(question.querySelector("[data-figure]")).toBeNull();
  },
};

export const CorrectiveReturn: Story = {
  name: "A corrective return: the split is unavailable and says why",
  render: (_, { globals }) => (
    <Offer state="amendment" locale={language(globals)} />
  ),
  play: async ({ canvasElement }) => {
    await settlement(canvasElement);
    const question = election(canvasElement, "instalment");
    expect(question).toHaveAttribute("data-reason", "amendment");
    expect(question.querySelector("select")).toBeNull();
  },
};

export const AnswerTheSplit: Story = {
  name: "Choosing an answer keeps the figures beside it",
  render: (_, { globals }) => (
    <Offer state="least" locale={language(globals)} />
  ),
  play: async ({ canvasElement }) => {
    await settlement(canvasElement);
    const select = election(canvasElement, "instalment").querySelector(
      "select",
    );
    if (!select) throw new Error("the split is not offered");
    const split = [...select.options].find(
      (option) => option.value !== "single",
    );
    if (!split) throw new Error("the split has no answer to choose");
    await userEvent.selectOptions(select, split.value);
    expect(select.value).toBe(split.value);
    expect(
      election(canvasElement, "instalment").querySelectorAll("[data-figure]")
        .length,
    ).toBe(2);
  },
};

export const InTheFilingView: Story = {
  name: "Export view of a salaried filer within the period: payment and split",
  render: (_, { globals }) => (
    <Screen shape="renta-instalment" locale={language(globals)} />
  ),
  play: async ({ canvasElement }) => {
    await settlement(canvasElement);
    const question = election(canvasElement, "instalment");
    expect(question).toHaveAttribute("data-state", "available");
    expect(question.querySelectorAll("[data-figure]").length).toBe(2);
    expect(election(canvasElement, "payment")).toHaveAttribute(
      "data-state",
      "available",
    );
  },
};
