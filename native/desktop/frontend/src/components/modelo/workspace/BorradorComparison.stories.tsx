import { RENTA_UNIT } from "@/dev/rentaUnit";
import type { Meta, StoryObj } from "@storybook/react-vite";
import { useEffect, useRef, useState } from "react";
import { expect, fn, userEvent, waitFor } from "storybook/test";
import { borradorFixture, type BorradorScenario } from "@/dev/borradorFixture";
import { modeloFixture } from "@/dev/modeloFixture";
import type { BorradorComparison as Comparison } from "../../../shell/borrador";
import type { ModeloPort } from "../../../shell/modelo";
import type { OutputLanguage } from "../../../shell/modeloContract/modelo";
import { translator } from "../../../shell/strings";
import { BorradorComparison } from "./BorradorComparison";
import type { BorradorComparisonRead } from "./borradorComparisonRead";
import { WorkspaceScreen } from "./WorkspaceScreen";
import { byName } from "@/dev/globByName";

// The year's AEAT draft beside the saved Modelo 100 calculation, on what the
// application read for a synthetic filer through
// `live.borrador.100.compare`, in every language, at each stage a profile
// reaches. The component stories draw an envelope as it was read; the
// workspace stories ask for it in the real window. Every status, every
// classification and every reason is the application's sentence; the draft's
// values are an observation of the AEAT's own, drawn apart from the
// calculation and never as zero.

const UNIT = RENTA_UNIT;

const envelopes = byName(
  import.meta.glob<Comparison>("@fixtures/modelo/borrador-100-0A-*.json", {
    import: "default",
  }),
);

const language = (globals: Record<string, unknown>) =>
  String(globals.locale ?? "en") as OutputLanguage;

async function served(
  state: string,
  locale: OutputLanguage,
): Promise<Comparison> {
  const load = envelopes[`borrador-100-0A-${state}-${locale}`];
  if (!load) throw new Error(`No comparison is stored as ${state}`);
  return structuredClone(await load());
}

/** The comparison the application read at `state`, drawn as the window draws
 * what it was served. */
function Element({
  state,
  locale,
  phase = "ready",
}: {
  state: string;
  locale: OutputLanguage;
  phase?: "ready" | "idle" | "reading" | "failed";
}) {
  const [read, setRead] = useState<BorradorComparisonRead | null>(null);
  const asked = useRef(fn());
  useEffect(() => {
    void (async () => {
      if (phase === "idle") return setRead({ phase: "idle" });
      if (phase === "reading") return setRead({ phase: "reading" });
      if (phase === "failed")
        return setRead({ phase: "failed", code: "unavailable" });
      setRead({ phase: "ready", comparison: await served(state, locale) });
    })();
  }, [state, locale, phase]);
  if (!read) return null;
  return (
    <div className="@container max-w-3xl p-6">
      <BorradorComparison read={read} onAsk={asked.current} locale={locale} />
    </div>
  );
}

function Screen({
  scenario,
  locale,
}: {
  scenario: BorradorScenario | null;
  locale: OutputLanguage;
}) {
  const port = useRef<ModeloPort | null>(null);
  port.current ??= modeloFixture({
    say: () => undefined,
    translate: translator,
    wait: async () => undefined,
    signedIn: () => true,
    shape: "renta-married",
  });
  const drafts = useRef(
    scenario ? borradorFixture({ scenario, say: () => undefined }) : undefined,
  );
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
        initialView="compare"
        borrador={drafts.current}
      />
    </div>
  );
}

const meta: Meta = {
  title: "Modelo/Borrador comparison",
  parameters: { fill: true, layout: "fullscreen" },
};
export default meta;
type Story = StoryObj;

const comparison = (canvasElement: HTMLElement) =>
  waitFor(
    () => {
      const found = canvasElement.querySelector<HTMLElement>(
        "[data-borrador-comparison]",
      );
      if (!found) throw new Error("the comparison is not drawn yet");
      return found;
    },
    { timeout: 30_000 },
  );

const one = (root: ParentNode, selector: string) => {
  const found = root.querySelector<HTMLElement>(selector);
  if (!found) throw new Error(`${selector} is not drawn`);
  return found;
};

const resulted = (root: HTMLElement) =>
  waitFor(
    () => {
      const found = root.querySelector<HTMLElement>("[data-borrador-result]");
      if (!found) throw new Error("the result is not drawn yet");
      return found;
    },
    { timeout: 30_000 },
  );

/** Checks the status the application served and returns the result. */
async function checkStatus(
  canvasElement: HTMLElement,
  state: string,
  locale: OutputLanguage,
) {
  const root = await comparison(canvasElement);
  const result = await resulted(root);
  const read = await served(state, locale);
  expect(result).toHaveAttribute("data-status", read.status.token);
  expect(one(result, "[data-borrador-status]").textContent).toBe(
    read.status.words,
  );
  return { root, result, read };
}

export const NotAskedYet: Story = {
  name: "Not asked yet: the comparison is offered, nothing is shown",
  render: (_, { globals }) => (
    <Element state="compared" locale={language(globals)} phase="idle" />
  ),
  play: async ({ canvasElement }) => {
    const root = await comparison(canvasElement);
    expect(one(root, "[data-comparison-ask]")).toBeEnabled();
    expect(root.querySelector("[data-borrador-result]")).toBeNull();
  },
};

export const Reading: Story = {
  name: "Reading: the question is out and cannot be asked again",
  render: (_, { globals }) => (
    <Element state="compared" locale={language(globals)} phase="reading" />
  ),
  play: async ({ canvasElement }) => {
    const root = await comparison(canvasElement);
    expect(one(root, "[data-comparison-ask]")).toBeDisabled();
  },
};

export const CouldNotRead: Story = {
  name: "The read did not answer: said so, no comparison is guessed",
  render: (_, { globals }) => (
    <Element state="compared" locale={language(globals)} phase="failed" />
  ),
  play: async ({ canvasElement }) => {
    const root = await comparison(canvasElement);
    expect(root).toHaveAttribute("data-phase", "failed");
    expect(root.querySelector("[data-borrador-result]")).toBeNull();
  },
};

export const NoDraftImported: Story = {
  name: "No draft imported: there is nothing to compare, and it is not agreement",
  render: (_, { globals }) => (
    <Element state="no-capture" locale={language(globals)} />
  ),
  play: async ({ canvasElement, globals }) => {
    const { result, read } = await checkStatus(
      canvasElement,
      "no-capture",
      language(globals),
    );
    expect(read.rows.length).toBe(0);
    expect(result.querySelector("[data-borrador-box]")).toBeNull();
    expect(result.querySelector("[data-borrador-side]")).toBeNull();
  },
};

export const DraftTheRulesRefuse: Story = {
  name: "A stored draft cannot be read: counted, never mistaken for an empty store",
  render: (_, { globals }) => (
    <Element state="capture-refused" locale={language(globals)} />
  ),
  play: async ({ canvasElement, globals }) => {
    const { result, read } = await checkStatus(
      canvasElement,
      "capture-refused",
      language(globals),
    );
    expect(read.refused_captures).toBeGreaterThan(0);
    expect(one(result, "[data-refused-captures]")).toHaveAttribute(
      "data-refused-captures",
      String(read.refused_captures),
    );
    expect(result.querySelector("[data-borrador-box]")).toBeNull();
  },
};

export const DraftWithoutACalculation: Story = {
  name: "A draft and no saved calculation: the draft is named, the calculation is missing",
  render: (_, { globals }) => (
    <Element state="no-calculation" locale={language(globals)} />
  ),
  play: async ({ canvasElement, globals }) => {
    const { result, read } = await checkStatus(
      canvasElement,
      "no-calculation",
      language(globals),
    );
    const draft = one(result, "[data-borrador-side=draft]");
    expect(draft.textContent).toContain(read.capture!.evidence.words);
    expect(result.querySelector("[data-borrador-side=calculation]")).toBeNull();
    expect(result.querySelector("[data-borrador-box]")).toBeNull();
  },
};

export const BoxByBox: Story = {
  name: "Compared: each box with both values, how they stand and why, in the application's words",
  render: (_, { globals }) => (
    <Element state="compared" locale={language(globals)} />
  ),
  play: async ({ canvasElement, globals }) => {
    const locale = language(globals);
    const t = translator(locale);
    const { result, read } = await checkStatus(
      canvasElement,
      "compared",
      locale,
    );
    expect(result.querySelector("[data-borrador-stale]")).toBeNull();
    // Every served row is drawn once, under its own classification.
    expect(result.querySelectorAll("[data-borrador-box]").length).toBe(
      read.rows.length,
    );
    for (const row of read.rows) {
      const drawn = one(result, `[data-borrador-box="${row.casilla_id}"]`);
      expect(drawn).toHaveAttribute(
        "data-classification",
        row.classification.token,
      );
      expect(drawn.textContent).toContain(row.reason.words);
      expect(drawn.closest("[data-borrador-group]")).toHaveAttribute(
        "data-borrador-group",
        row.classification.token,
      );
      // A side with no value says so; it is never drawn as zero.
      const draftCell = one(drawn, "[data-borrador-value]");
      if (row.borrador_value === null) {
        expect(draftCell.textContent).toBe(
          t("desktop.modelo.compare.borrador.no_value"),
        );
      } else {
        expect(draftCell.textContent).not.toBe(
          t("desktop.modelo.compare.borrador.no_value"),
        );
      }
    }
    // The count of each group is the application's count.
    for (const [token, count] of Object.entries(read.counts)) {
      const group = result.querySelector(`[data-borrador-group=${token}]`);
      if (count === 0) expect(group).toBeNull();
      else expect(group).toHaveAttribute("data-count", String(count));
    }
  },
};

export const DifferencesAreStated: Story = {
  name: "Compared: a box that differs states the difference of the calculation from the draft",
  render: (_, { globals }) => (
    <Element state="compared" locale={language(globals)} />
  ),
  play: async ({ canvasElement, globals }) => {
    const locale = language(globals);
    const { result, read } = await checkStatus(
      canvasElement,
      "compared",
      locale,
    );
    const differing = read.rows.filter((row) => row.difference !== null);
    expect(differing.length).toBeGreaterThan(0);
    for (const row of differing) {
      const drawn = one(result, `[data-borrador-box="${row.casilla_id}"]`);
      expect(one(drawn, "[data-borrador-difference]")).toHaveAttribute(
        "data-borrador-difference",
        row.difference!.decimal,
      );
    }
  },
};

export const DraftIsAnObservation: Story = {
  name: "The draft is drawn apart as an observation; the calculation is local and unmarked",
  render: (_, { globals }) => (
    <Element state="compared" locale={language(globals)} />
  ),
  play: async ({ canvasElement, globals }) => {
    const locale = language(globals);
    const t = translator(locale);
    const { result, read } = await checkStatus(
      canvasElement,
      "compared",
      locale,
    );
    const draft = one(result, "[data-borrador-side=draft]");
    const calculation = one(result, "[data-borrador-side=calculation]");
    expect(draft.textContent).toContain(
      t("desktop.modelo.compare.borrador.observation"),
    );
    expect(draft.textContent).toContain(read.capture!.evidence.words);
    expect(calculation.textContent).toContain(read.calculation!.evidence.words);
    expect(calculation.textContent).not.toContain(
      t("desktop.modelo.compare.borrador.observation"),
    );
    // Not the same evidence: the sentences differ.
    expect(read.capture!.evidence.words).not.toBe(
      read.calculation!.evidence.words,
    );
  },
};

export const StaleComparison: Story = {
  name: "Stale: both sides were read but no longer describe each other, and the reasons are listed",
  render: (_, { globals }) => (
    <Element state="stale" locale={language(globals)} />
  ),
  play: async ({ canvasElement, globals }) => {
    const { result, read } = await checkStatus(
      canvasElement,
      "stale",
      language(globals),
    );
    expect(read.stale_reasons.length).toBeGreaterThan(0);
    for (const reason of read.stale_reasons)
      expect(
        one(result, `[data-stale-reason=${reason.token}]`).textContent,
      ).toBe(reason.words);
    // The boxes are still drawn, each with its own classification.
    expect(result.querySelectorAll("[data-borrador-box]").length).toBe(
      read.rows.length,
    );
  },
};

export const AskInTheWorkspace: Story = {
  name: "In the workspace: asking reads the draft and the calculation without touching the form",
  render: (_, { globals }) => (
    <Screen scenario="compared" locale={language(globals)} />
  ),
  play: async ({ canvasElement, globals }) => {
    const locale = language(globals);
    const root = await comparison(canvasElement);
    await userEvent.click(one(root, "[data-comparison-ask]"));
    const { read } = await checkStatus(canvasElement, "compared", locale);
    expect(read.rows.length).toBeGreaterThan(0);
  },
};

export const NotOfferedWithoutDrafts: Story = {
  name: "A window that cannot read the profile's drafts offers no draft comparison",
  render: (_, { globals }) => (
    <Screen scenario={null} locale={language(globals)} />
  ),
  play: async ({ canvasElement }) => {
    await waitFor(
      () => {
        if (!canvasElement.querySelector("[data-taxation-comparison]"))
          throw new Error("the comparisons are not drawn yet");
      },
      { timeout: 30_000 },
    );
    expect(
      canvasElement.querySelector("[data-borrador-comparison]"),
    ).toBeNull();
  },
};
