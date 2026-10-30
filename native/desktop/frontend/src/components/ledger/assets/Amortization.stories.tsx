import type { Meta, StoryObj } from "@storybook/react-vite";
import { useMemo } from "react";
import { userEvent, waitFor, within } from "storybook/test";
import { STORY_READER, useLedgerPort } from "@/dev/LedgerStage";
import type { LedgerPort } from "../../../shell/ledger";
import { AmortizationPlan } from "./AmortizationPlan";
import { AssetTimeline } from "./AssetTimeline";

// One element's amortization plan and its append-only timeline over the
// scenario's register. Each story names the element whose plan or history
// shows one state: a partly claimed year, years on projected rates, years
// before the first edition, a maximum period that has elapsed, a free method,
// an unknown opening history, a baja and a claim that no longer matches.

type Answer = "register" | "empty" | "refused" | "loading" | "unavailable";

type Args = {
  assetId: string;
  year: number | null;
  /** What the read answers; the register's own unless said. */
  answer: Answer;
  /** Drawn at the width of the detail panel rather than the pane. */
  narrow: boolean;
  locale: string;
};

/** The scenario's port, with the plan and timeline reads answered as the
 * story asks. */
function withAnswer(port: LedgerPort, answer: Answer): LedgerPort {
  if (answer === "register") return port;
  const settled = (result: object) =>
    Promise.resolve({
      kind: "settled",
      operation_id: "story",
      revision: 1,
      result,
    });
  return {
    ...port,
    submit: ((definition: string, payload: never) => {
      if (
        definition !== "ledger.actividad-asset.plan" &&
        definition !== "ledger.actividad-asset.timeline"
      )
        return port.submit(definition as never, payload);
      if (answer === "loading") return new Promise(() => undefined);
      if (answer === "unavailable")
        return Promise.resolve({
          kind: "running",
          operation_id: "story",
          revision: 1,
          cancellable: false,
        });
      const shape =
        definition === "ledger.actividad-asset.plan"
          ? { rows: [] }
          : { events: [] };
      if (answer === "empty")
        return settled({
          outcome: "succeeded",
          refusal: null,
          asset_id: "story",
          ...shape,
        });
      return settled({
        outcome: "refused",
        refusal: {
          code: "REFUSED_ACTIVIDAD_ASSET_VALIDATION",
          precondition_verdict: null,
          accelerated_da18: null,
          reason_key: "ledger.actividad_asset.errors.asset_not_found",
          reason_facts: [],
        },
        asset_id: null,
        ...shape,
      });
    }) as LedgerPort["submit"],
  };
}

function Stage({
  view,
  assetId,
  year,
  answer,
  narrow,
  locale,
}: Args & { view: "plan" | "timeline" }) {
  const base = useLedgerPort();
  const port = useMemo(() => withAnswer(base, answer), [base, answer]);
  return (
    <div
      className={
        narrow
          ? "flex h-full min-h-0 max-w-xl flex-col bg-card"
          : "flex h-full min-h-0 flex-col bg-card"
      }
    >
      {view === "plan" ? (
        <AmortizationPlan
          port={port}
          reader={STORY_READER}
          assetId={assetId}
          locale={locale}
          year={year}
          onOpenLink={() => undefined}
        />
      ) : (
        <AssetTimeline
          port={port}
          reader={STORY_READER}
          assetId={assetId}
          locale={locale}
        />
      )}
    </div>
  );
}

const meta: Meta<Args> = {
  title: "Ledger/Assets/Amortization",
  args: {
    assetId: "furgoneta",
    year: null,
    answer: "register",
    narrow: false,
    locale: "en",
  },
  argTypes: {
    locale: { table: { disable: true } },
    answer: {
      control: "select",
      options: ["register", "empty", "refused", "loading", "unavailable"],
    },
  },
  parameters: { fill: true, layout: "fullscreen" },
};
export default meta;
type Story = StoryObj<Args>;

type PlayContext = Parameters<NonNullable<Story["play"]>>[0];

/** Opens the claims of the plan's year, once the plan is drawn. */
const open =
  (...years: number[]): Story["play"] =>
  async ({ canvasElement }: PlayContext) => {
    for (const year of years) {
      const control = await waitFor(() => {
        const found = within(canvasElement).queryByRole("button", {
          name: new RegExp(String(year)),
        });
        if (!found) throw new Error(`${year} is not drawn yet`);
        return found;
      });
      await userEvent.click(control);
    }
  };

const plan = (extra: Partial<Story> = {}): Story => ({
  ...extra,
  render: (args, { globals }) => (
    <Stage {...args} view="plan" locale={String(globals.locale ?? "en")} />
  ),
});

const timeline = (extra: Partial<Story> = {}): Story => ({
  ...extra,
  render: (args, { globals }) => (
    <Stage {...args} view="timeline" locale={String(globals.locale ?? "en")} />
  ),
});

// ---- The plan --------------------------------------------------------------

export const PlanPartlyClaimed: Story = plan({
  name: "Plan, a partly claimed year, years to come and rates carried forward",
  args: { assetId: "furgoneta", year: 2026 },
  play: open(2026),
});

export const PlanLongListOfLegalBasis: Story = plan({
  name: "Plan, eleven provisions behind the election, collapsed with their count",
  args: { assetId: "furgoneta", year: 2026 },
  play: async ({ canvasElement }: PlayContext) => {
    const summary = await waitFor(() => {
      const found = canvasElement.querySelector(
        ".ledger-assets-citations summary",
      );
      if (!found) throw new Error("the legal basis is not drawn yet");
      return found;
    });
    await userEvent.click(summary);
  },
});

export const PlanPartialListOfLegalBasis: Story = plan({
  name: "Plan, a legal basis that could not be resolved whole says it is partial",
  args: { assetId: "herramienta", year: 2026 },
});

export const PlanBeforeTheFirstEdition: Story = plan({
  name: "Plan, years before the first edition: no figure",
  args: { assetId: "compresor" },
});

export const PlanCoveredByOpening: Story = plan({
  name: "Plan, years the opening amount covers",
  args: { assetId: "plotter" },
});

export const PlanProjectedRates: Story = plan({
  name: "Plan, a year on projected rates",
  args: { assetId: "licencia", year: 2027 },
});

export const PlanMaximumPeriodElapsed: Story = plan({
  name: "Plan, the maximum period has elapsed",
  args: { assetId: "cristaleria" },
  play: open(2024),
});

export const PlanFreeMethodClaimed: Story = plan({
  name: "Plan, free depreciation, claimed",
  args: { assetId: "taladro" },
});

export const PlanFreeMethodOpen: Story = plan({
  name: "Plan, free depreciation, still to claim",
  args: { assetId: "impresora" },
});

export const PlanOpeningHistoryMissing: Story = plan({
  name: "Plan, opening history never stated",
  args: { assetId: "estanteria" },
});

export const PlanOutOfService: Story = plan({
  name: "Plan, an element out of service",
  args: { assetId: "camara" },
  play: open(2025),
});

export const PlanStaleClaim: Story = plan({
  name: "Plan, a claim recorded under an earlier revision",
  args: { assetId: "servidor" },
  play: open(2025),
});

export const PlanInThePanel: Story = plan({
  name: "Plan, at the detail panel's width",
  args: { assetId: "servidor", narrow: true },
});

export const PlanEmpty: Story = plan({
  name: "Plan, no year yet",
  args: { answer: "empty" },
});

export const PlanRefused: Story = plan({
  name: "Plan, read refused",
  args: { answer: "refused" },
});

export const PlanReading: Story = plan({
  name: "Plan, being read",
  args: { answer: "loading" },
});

export const PlanUnavailable: Story = plan({
  name: "Plan, ledger not answering",
  args: { answer: "unavailable" },
});

// ---- The timeline ----------------------------------------------------------

export const TimelineCorrection: Story = timeline({
  name: "Timeline, a correction and a claim that no longer matches",
  args: { assetId: "servidor" },
});

export const TimelineDescription: Story = timeline({
  name: "Timeline, a description outside the calculation",
  args: { assetId: "furgoneta" },
});

export const TimelineWithoutName: Story = timeline({
  name: "Timeline, an element never described",
  args: { assetId: "herramienta" },
});

export const TimelineBaja: Story = timeline({
  name: "Timeline, an element out of service",
  args: { assetId: "camara" },
});

export const TimelineInThePanel: Story = timeline({
  name: "Timeline, at the detail panel's width",
  args: { assetId: "camara", narrow: true },
});

export const TimelineEmpty: Story = timeline({
  name: "Timeline, nothing appended",
  args: { answer: "empty" },
});

export const TimelineRefused: Story = timeline({
  name: "Timeline, read refused",
  args: { answer: "refused" },
});

export const TimelineReading: Story = timeline({
  name: "Timeline, being read",
  args: { answer: "loading" },
});

export const TimelineUnavailable: Story = timeline({
  name: "Timeline, ledger not answering",
  args: { answer: "unavailable" },
});
