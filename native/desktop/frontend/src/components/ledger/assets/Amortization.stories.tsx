import type { Meta, StoryObj } from "@storybook/react-vite";
import { useEffect, useMemo, useState } from "react";
import { userEvent, waitFor, within } from "storybook/test";
import { STORY_READER, useLedgerPort } from "@/dev/LedgerStage";
import type { LedgerPort } from "../../../shell/ledger";
import { AmortizationPlan } from "./AmortizationPlan";
import { AssetTimeline } from "./AssetTimeline";
import { submitProvisional, type AssetBaja } from "./assetsContract";

// One element's amortization plan and its append-only timeline over the
// scenario's register, which spans decades. Each story names the element
// whose plan or history shows one state of the audit: a method change, a
// missing year, a recorded zero, a free method, an unknown opening history,
// a baja, years on projected rates, and a plan of forty years.

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
        },
        asset_id: null,
        ...shape,
      });
    }) as LedgerPort["submit"],
  };
}

/** The baja the list states for an element, as the detail would pass it. */
function useBaja(port: LedgerPort, assetId: string): AssetBaja | null {
  const [baja, setBaja] = useState<AssetBaja | null>(null);
  useEffect(() => {
    let active = true;
    void submitProvisional(port, "ledger.actividad-asset.list", {}).then(
      (outcome) => {
        if (!active || outcome.kind !== "settled") return;
        setBaja(
          outcome.result.rows.find((row) => row.asset_id === assetId)?.baja ??
            null,
        );
      },
    );
    return () => {
      active = false;
    };
  }, [port, assetId]);
  return baja;
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
  const baja = useBaja(base, assetId);
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
          baja={baja}
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

export const PlanSettledForDecades: Story = plan({
  name: "Plan, decades old and settled",
  args: { assetId: "plotter" },
});

export const PlanOfFortyYears: Story = plan({
  name: "Plan, forty years with a year in view",
  args: { assetId: "taller", year: 2026 },
});

export const PlanMethodChange: Story = plan({
  name: "Plan, a method change and a replaced claim",
  args: { assetId: "servidor" },
  play: open(2014, 2015),
});

export const PlanMissingAndPartial: Story = plan({
  name: "Plan, a missing year, a partial one and an overlap",
  args: { assetId: "furgoneta" },
  play: open(2023, 2024, 2026),
});

export const PlanProjectedRates: Story = plan({
  name: "Plan, years on projected rates",
  args: { assetId: "furgoneta", year: 2027 },
});

export const PlanRecordedZero: Story = plan({
  name: "Plan, a recorded zero beside a missing year",
  args: { assetId: "licencia" },
  play: open(2022),
});

export const PlanFreeMethod: Story = plan({
  name: "Plan, free depreciation",
  args: { assetId: "prensa" },
});

export const PlanOpeningHistoryUnknown: Story = plan({
  name: "Plan, opening history never stated",
  args: { assetId: "escaner" },
});

export const PlanBaja: Story = plan({
  name: "Plan, closed by a baja",
  args: { assetId: "camara" },
  play: open(2024),
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
  name: "Timeline, a method correction and replaced claims",
  args: { assetId: "servidor" },
});

export const TimelineTimeNotKept: Story = timeline({
  name: "Timeline, events from before time was kept",
  args: { assetId: "plotter" },
});

export const TimelineDescription: Story = timeline({
  name: "Timeline, a description outside the calculation",
  args: { assetId: "furgoneta" },
});

export const TimelineBaja: Story = timeline({
  name: "Timeline, a baja and the claim it replaced",
  args: { assetId: "camara" },
});

export const TimelineLong: Story = timeline({
  name: "Timeline, forty years",
  args: { assetId: "taller" },
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
