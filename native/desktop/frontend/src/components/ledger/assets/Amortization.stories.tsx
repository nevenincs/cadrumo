import type { Meta, StoryObj } from "@storybook/react-vite";
import { useEffect, useMemo, useRef, useState } from "react";
import { userEvent, waitFor, within } from "storybook/test";
import { STORY_READER, useLedgerPort } from "@/dev/LedgerStage";
import type { LedgerPort } from "../../../shell/ledger";
import type {
  ActivityAssetForecast,
  DisposalFacts,
  ListDisposal,
  ReasonFact,
} from "../../../shell/ledgerSetup";
import { translator } from "../../../shell/strings";
import { setupCall } from "../setup/setupModel";
import { AmortizationPlan } from "./AmortizationPlan";
import { AssetTimeline } from "./AssetTimeline";
import { bajaRequest, type RevisionBase } from "./assetRevision";
import { ASSET_KEYS } from "./assetsWords";

// One element's amortization plan and its append-only timeline over the
// scenario's register. Each story names the element whose plan or history
// shows one state: a partly claimed year, years on projected rates, years
// before the first edition, a maximum period that has elapsed, a free method,
// an unknown opening history, a baja and a claim that no longer matches. A
// story can also change what the plan says, to show a state the register has
// no element in: the remedy for a missing opening amount, and a legal basis
// that is long and partial at once. A story on the timeline can first do what
// a person did, through the scenario's own writes, so the record shows what
// those writes leave: a baja recorded, changed and removed, and a dotación a
// later one replaced.

type Answer = "register" | "empty" | "refused" | "loading" | "unavailable";

type Tweak =
  | "none"
  | "opening_remedy"
  | "long_partial_citations"
  | "refusal_facts"
  | "nothing_left";

/** What a person did to the element before the story opens. */
type Prepare = "none" | "baja_cycle" | "replaced_claim";

type Args = {
  assetId: string;
  year: number | null;
  /** What the plan is made to say beyond the register's own. */
  tweak: Tweak;
  /** What was done to the element before the view opens. */
  prepare: Prepare;
  /** What the read answers; the register's own unless said. */
  answer: Answer;
  /** Drawn at the width of the detail panel rather than the pane. */
  narrow: boolean;
  locale: string;
};

type PlanShape = {
  rows?:
    | {
        absence: string | null;
        absence_reason_key: string | null;
        claim_state: string;
        claimable_intervals: unknown[];
        claimable_refusal_key: string | null;
        claimable_refusal_facts: ReasonFact[];
      }[]
    | null;
  limits?: {
    legal_citations_complete: boolean;
    unavailable_reason_key: string | null;
    unavailable_reason_facts: ReasonFact[];
  } | null;
};

const ELAPSED = "ledger.actividad_asset.errors.amortization_period_elapsed";

/** The baja the register records for the element, as the detail passes it. */
function useDisposal(port: LedgerPort, assetId: string): ListDisposal | null {
  const [disposal, setDisposal] = useState<ListDisposal | null>(null);
  useEffect(() => {
    let active = true;
    void setupCall(port, "ledger.actividad-asset.list", {}, false).then(
      (call) => {
        if (!active || call.kind !== "done") return;
        const found = call.result.rows?.find((row) => row.asset_id === assetId);
        setDisposal(found?.disposal ?? null);
      },
    );
    return () => {
      active = false;
    };
  }, [port, assetId]);
  return disposal;
}

/** The scenario's port, with the plan changed as the story asks. */
function withTweak(port: LedgerPort, tweak: Tweak): LedgerPort {
  if (tweak === "none") return port;
  return {
    ...port,
    submit: ((definition: string, payload: never) => {
      const sent = port.submit(definition as never, payload) as Promise<{
        kind: string;
        result?: unknown;
      }>;
      if (definition !== "ledger.actividad-asset.plan") return sent;
      return sent.then((answer) => {
        if (answer.kind !== "settled") return answer;
        const plan = structuredClone(answer.result) as PlanShape;
        if (tweak === "opening_remedy") {
          for (const row of plan.rows ?? [])
            if (row.absence === "incomplete")
              row.absence_reason_key =
                "ledger.actividad_asset.errors.opening_history_missing";
        } else if (tweak === "refusal_facts") {
          const first = plan.rows?.[0];
          const facts: ReasonFact[] = [
            { key: "ended_on", value: "2024-12-31", kind: "date" },
          ];
          if (first) {
            first.claimable_intervals = [];
            first.claimable_refusal_key = ELAPSED;
            first.claimable_refusal_facts = facts;
          }
          if (plan.limits) {
            plan.limits.unavailable_reason_key = ELAPSED;
            plan.limits.unavailable_reason_facts = facts;
          }
        } else if (tweak === "nothing_left") {
          const first = plan.rows?.[0];
          if (first) {
            first.claim_state = "missing";
            first.claimable_intervals = [];
            first.claimable_refusal_key = null;
          }
        } else if (plan.limits) plan.limits.legal_citations_complete = false;
        return { ...answer, result: plan };
      });
    }) as LedgerPort["submit"],
  };
}

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

const sale = (disposal_date: string): DisposalFacts => ({
  disposal_date,
  reason: "sale",
  proceeds: { decimal: "100.00" },
  transmission_costs: { decimal: "0.00" },
  market_value: null,
  prior_free_depreciation_regime: null,
  later_affectation_on: null,
});

/** Does what a person did before the view opens, through the scenario's own
 * writes: a baja recorded, changed to another day and removed, or a dotación
 * recorded again in place of the one in effect. */
async function prepared(port: LedgerPort, assetId: string, prepare: Prepare) {
  const lastRevision = async (): Promise<RevisionBase | null> => {
    const read = await setupCall(
      port,
      "ledger.actividad-asset.inspect",
      { asset_id: assetId },
      false,
    );
    return read.kind === "done"
      ? (read.result.revisions?.at(-1) ?? null)
      : null;
  };
  if (prepare === "baja_cycle") {
    await setupCall(
      port,
      "ledger.actividad-asset.dispose",
      { asset_id: assetId, disposal: sale("2026-09-30") },
      true,
    );
    for (const disposal of [sale("2026-06-30"), null]) {
      const request = bajaRequest(await lastRevision(), disposal);
      if (request !== null)
        await setupCall(port, "ledger.actividad-asset.correct", request, true);
    }
  } else if (prepare === "replaced_claim") {
    const plan = await setupCall(
      port,
      "ledger.actividad-asset.plan",
      { asset_id: assetId },
      false,
    );
    const old =
      plan.kind === "done"
        ? plan.result.rows
            ?.flatMap((row) => row.claims)
            .find((found) => found.effective)
        : undefined;
    if (old === undefined) return;
    const forecast = await setupCall(
      port,
      "ledger.actividad-asset.forecast",
      {
        asset_id: assetId,
        covered_from: old.covered_from,
        covered_through: old.covered_through,
        requested_free_amount: null,
        supersedes_claim_id: old.claim_id,
      },
      false,
    );
    const made: ActivityAssetForecast | null =
      forecast.kind === "done" ? forecast.result.forecast : null;
    if (made !== null)
      await setupCall(
        port,
        "ledger.actividad-asset.claim",
        { forecast: made, supersedes_claim_id: old.claim_id },
        true,
      );
  }
}

function Stage({
  view,
  assetId,
  year,
  tweak,
  prepare,
  answer,
  narrow,
  locale,
}: Args & { view: "plan" | "timeline" }) {
  const base = useLedgerPort();
  const [ready, setReady] = useState(prepare === "none");
  const started = useRef(false);
  useEffect(() => {
    if (prepare === "none" || started.current) return;
    started.current = true;
    void prepared(base, assetId, prepare).then(() => setReady(true));
  }, [base, assetId, prepare]);
  const port = useMemo(
    () => withAnswer(withTweak(base, tweak), answer),
    [base, tweak, answer],
  );
  const disposal = useDisposal(base, assetId);
  if (!ready) return null;
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
          disposal={disposal}
          onOpenLink={() => undefined}
          onCorrectClaim={() => undefined}
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
    tweak: "none",
    prepare: "none",
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

/** Shows the tooltip of the mark or glyph the person can focus by its name,
 * which the story takes from the catalogue in its own language. */
const hint =
  (key: string, values?: Record<string, string | number>): Story["play"] =>
  async ({ canvasElement, globals }: PlayContext) => {
    const words = translator(String(globals.locale ?? "en"))(key, values);
    const name = new RegExp(words.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
    const mark = await waitFor(() => {
      const found = within(canvasElement).queryAllByRole("img", { name })[0];
      if (!found) throw new Error(`the mark "${words}" is not drawn yet`);
      return found;
    });
    await userEvent.hover(mark);
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
    const disclosure = await waitFor(() => {
      const found = canvasElement.querySelector(
        ".ledger-assets-citations button",
      );
      if (!found) throw new Error("the legal basis is not drawn yet");
      return found;
    });
    await userEvent.click(disclosure);
  },
});

export const PlanLongAndPartialLegalBasis: Story = plan({
  name: "Plan, eleven provisions and a list that is also partial",
  args: { assetId: "furgoneta", year: 2026, tweak: "long_partial_citations" },
  play: async ({ canvasElement }: PlayContext) => {
    const disclosure = await waitFor(() => {
      const found = canvasElement.querySelector(
        ".ledger-assets-citations button",
      );
      if (!found) throw new Error("the legal basis is not drawn yet");
      return found;
    });
    await userEvent.click(disclosure);
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

export const PlanYearWithoutOfficialTables: Story = plan({
  name: "Plan, a year with no official tables, said in words",
  args: { assetId: "compresor", narrow: true },
});

export const PlanMissingOpeningAmount: Story = plan({
  name: "Plan, an opening amount never entered says where to enter it",
  args: { assetId: "estanteria", narrow: true, tweak: "opening_remedy" },
});

export const PlanCoveredByOpening: Story = plan({
  name: "Plan, years the opening amount covers",
  args: { assetId: "plotter" },
});

export const PlanProjectedRates: Story = plan({
  name: "Plan, estimated years carry their own glyph beside the year and each figure",
  args: { assetId: "licencia", year: 2027 },
  play: hint(ASSET_KEYS.plan.projected_note, { year: 2027 }),
});

export const PlanMinimumAccumulated: Story = plan({
  name: "Plan, the minimum column is headed as accumulated to year end, with its note",
  args: { assetId: "furgoneta", year: 2026 },
  play: hint(ASSET_KEYS.plan.column.minimum_note),
});

export const PlanNothingRecordedMark: Story = plan({
  name: "Plan, a year with nothing recorded has its own mark, not Not known",
  args: { assetId: "servidor" },
  play: hint(ASSET_KEYS.mark.nothing_recorded),
});

export const PlanDoesNotApplyMark: Story = plan({
  name: "Plan, a figure that does not apply has its own mark, not Not known",
  args: { assetId: "plotter" },
  play: hint(ASSET_KEYS.mark.not_applicable),
});

export const PlanMinimumUnknown: Story = plan({
  name: "Plan, a minimum with an earlier year unresolved is Not known with its reason, never a figure",
  args: { assetId: "plotter" },
  play: hint("ledger.actividad_asset.disposal_finding.minimum_unresolved"),
});

export const PlanLimitsLastDayOfThePeriod: Story = plan({
  name: "Plan, the maximum period ends on its last day, not on the boundary after it",
  args: { assetId: "cristaleria", narrow: true },
});

export const PlanReasonWithFacts: Story = plan({
  name: "Plan, the reason a year cannot be recorded and the limit reason carry their dates",
  args: { assetId: "cristaleria", tweak: "refusal_facts" },
});

export const PlanNothingLeftToRecord: Story = plan({
  name: "Plan, a year with nothing left to record says so only when no reason is given",
  args: { assetId: "furgoneta", tweak: "nothing_left" },
});

export const PlanScrollsSideways: Story = plan({
  name: "Plan, a table wider than the panel fades at the edge that continues",
  args: { assetId: "furgoneta", narrow: true },
});

export const PlanBaja: Story = plan({
  name: "Plan, the baja is said above the table with its date and reason",
  args: { assetId: "camara" },
});

export const PlanMaximumPeriodElapsed: Story = plan({
  name: "Plan, the maximum period has elapsed",
  args: { assetId: "cristaleria", narrow: true },
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
  name: "Plan, a dotación that no longer matches says why and what to do",
  args: { assetId: "servidor", narrow: true },
  play: open(2025),
});

export const PlanStaleClaimCollapsed: Story = plan({
  name: "Plan, a stale dotación shows a warning on the collapsed year, not a tick",
  args: { assetId: "servidor", narrow: true },
  play: hint(ASSET_KEYS.plan.no_match),
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

export const TimelineBajaRecordedChangedRemoved: Story = timeline({
  name: "Timeline, a baja recorded, changed to another day and removed, each on its own day",
  args: { assetId: "taladro", prepare: "baja_cycle" },
});

export const TimelineReplacedClaim: Story = timeline({
  name: "Timeline, a dotación a later one replaced is dimmed and no longer in effect",
  args: { assetId: "furgoneta", prepare: "replaced_claim" },
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
