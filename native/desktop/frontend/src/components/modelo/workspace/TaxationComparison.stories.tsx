import type { Meta, StoryObj } from "@storybook/react-vite";
import { useEffect, useRef, useState } from "react";
import { expect, fn, userEvent, waitFor } from "storybook/test";
import { modeloFixture, type ModeloShape } from "@/dev/modeloFixture";
import {
  servedRefusalWords,
  type LedgerErrorDetail,
} from "../../../shell/ledger";
import type { ModeloPort } from "../../../shell/modelo";
import type { OutputLanguage } from "../../../shell/modeloContract/modelo";
import type { ModeloTaxationComparisonProjection } from "../../../shell/modeloContract/modeloWork";
import { translator } from "../../../shell/strings";
import { TaxationComparison } from "./TaxationComparison";
import {
  refusedRead,
  type TaxationComparisonRead,
} from "./taxationComparisonRead";
import { WorkspaceScreen } from "./WorkspaceScreen";
import { byName } from "@/dev/globByName";

// The comparison of joint and individual filing on what the application read
// for synthetic households through `modelo.work.compare_taxation`, in every
// language: the three results it recommends, and each refusal it settled
// with, in its own sentence. The component stories draw an envelope as it was
// read; the workspace stories ask for it in the real window over the same
// envelopes. Every sentence and amount is the application's; none is written
// here.

const UNIT = "b1c431589384a105701ba15942606b5f5667cb677d6fa62e743cd0293f9baee4";
/** A declaration whose form asks for no comparison: the first quarter's
 * Modelo 130. */
const QUARTERLY_UNIT =
  "66354cafad021ef81e8c4bce2a0d361a2fa3ba568efc325ee607266291fd8fb3";

const projections = byName(
  import.meta.glob<ModeloTaxationComparisonProjection>(
    "@fixtures/modelo/compare-100-0A-*.json",
    { import: "default" },
  ),
);
const refusals = byName(
  import.meta.glob<LedgerErrorDetail>(
    "@fixtures/modelo/refusal-compare-100-0A*.json",
    { import: "default" },
  ),
);

const language = (globals: Record<string, unknown>) =>
  String(globals.locale ?? "en") as OutputLanguage;

/** The digits of a drawn amount, for comparing it with the exact decimal text
 * the application served without trusting the window's own formatting. */
const digits = (text: string | null) => (text ?? "").replace(/\D/g, "");

/** The comparison the application read for `state` in `locale`, drawn as the
 * window draws what it was served. */
function Element({
  state,
  locale,
  kind,
  profile = true,
}: {
  state: string;
  locale: OutputLanguage;
  kind: "answer" | "refusal" | "failed" | "idle" | "reading";
  /** Whether the window can open the profile. */
  profile?: boolean;
}) {
  const [read, setRead] = useState<TaxationComparisonRead | null>(null);
  const goes = useRef(fn());
  const opens = useRef(fn());
  useEffect(() => {
    void (async () => {
      if (kind === "idle") return setRead({ phase: "idle" });
      if (kind === "reading") return setRead({ phase: "reading" });
      if (kind === "failed") return setRead({ phase: "failed" });
      if (kind === "answer") {
        const load = projections[`compare-100-0A-${state}-${locale}`];
        if (!load) throw new Error(`No comparison is stored as ${state}`);
        return setRead({
          phase: "ready",
          projection: structuredClone(await load()),
        });
      }
      const key = state === "" ? "" : `-${state}`;
      const load = refusals[`refusal-compare-100-0A${key}-${locale}`];
      if (!load) throw new Error(`No refusal is stored as ${state}`);
      const detail = structuredClone(await load());
      setRead(refusedRead(servedRefusalWords(detail), detail));
    })();
  }, [state, locale, kind]);
  if (!read) return null;
  return (
    <div className="@container max-w-3xl p-6">
      <TaxationComparison
        read={read}
        onAsk={fn()}
        locale={locale}
        fieldAt={() => null}
        onGo={goes.current}
        onOpenProfile={profile ? opens.current : null}
      />
    </div>
  );
}

function Screen({
  shape,
  locale,
  unit = UNIT,
  initialView = "compare",
  onOpenSurface = () => undefined,
}: {
  shape: ModeloShape;
  locale: OutputLanguage;
  unit?: string;
  initialView?: "compare" | "form";
  onOpenSurface?: (surface: string) => void;
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
        workUnitId={unit}
        language={locale}
        locale={locale}
        onBack={() => undefined}
        onOpenSurface={onOpenSurface}
        canOpenSurface={() => true}
        openLink={() => undefined}
        initialView={initialView}
      />
    </div>
  );
}

const meta: Meta = {
  title: "Modelo/Taxation comparison",
  parameters: { fill: true, layout: "fullscreen" },
};
export default meta;
type Story = StoryObj;

const comparison = (canvasElement: HTMLElement) =>
  waitFor(
    () => {
      const found = canvasElement.querySelector<HTMLElement>(
        "[data-taxation-comparison]",
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

/** The result of the comparison, once drawn. */
const resulted = (root: HTMLElement) =>
  waitFor(
    () => {
      const found = root.querySelector<HTMLElement>("[data-comparison-result]");
      if (!found) throw new Error("the result is not drawn yet");
      return found;
    },
    { timeout: 30_000 },
  );

/** The refusal of the comparison, once drawn. */
const refused = (root: HTMLElement) =>
  waitFor(
    () => {
      const found = root.querySelector<HTMLElement>(
        "[data-comparison-refusal]",
      );
      if (!found) throw new Error("the refusal is not drawn yet");
      return found;
    },
    { timeout: 30_000 },
  );

async function served(
  state: string,
  locale: OutputLanguage,
): Promise<ModeloTaxationComparisonProjection> {
  const load = projections[`compare-100-0A-${state}-${locale}`];
  if (!load) throw new Error(`No comparison is stored as ${state}`);
  return load();
}

async function servedRefusal(
  state: string,
  locale: OutputLanguage,
): Promise<LedgerErrorDetail> {
  const key = state === "" ? "" : `-${state}`;
  const load = refusals[`refusal-compare-100-0A${key}-${locale}`];
  if (!load) throw new Error(`No refusal is stored as ${state}`);
  return load();
}

/** One fact of a refusal's context, as served. */
const contextOf = (detail: LedgerErrorDetail, key: string) =>
  String(detail.context.find((fact) => fact.key === key)?.value ?? "");

/** Draws an answer and checks it against what the application served. */
async function checkAnswer(
  canvasElement: HTMLElement,
  state: string,
  locale: OutputLanguage,
  recommended: "joint" | "individual" | null,
) {
  const root = await comparison(canvasElement);
  const result = await resulted(root);
  const projection = await served(state, locale);
  const joint = one(result, "[data-comparison-mode=joint]");
  const individual = one(result, "[data-comparison-mode=individual]");
  // The exact amounts, as served, in each mode's own column.
  expect(digits(one(joint, "[data-comparison-tax]").textContent)).toBe(
    digits(projection.conjunta_cuota_resultante),
  );
  expect(
    digits(one(joint, "[data-comparison-result-amount]").textContent),
  ).toBe(digits(projection.conjunta_resultado));
  expect(digits(one(individual, "[data-comparison-tax]").textContent)).toBe(
    digits(projection.individual_cuota_resultante),
  );
  expect(
    digits(one(individual, "[data-comparison-result-amount]").textContent),
  ).toBe(digits(projection.individual_resultado));
  // Only the mode the application recommended is marked.
  expect(joint).toHaveAttribute(
    "data-recommended",
    String(recommended === "joint"),
  );
  expect(individual).toHaveAttribute(
    "data-recommended",
    String(recommended === "individual"),
  );
  expect(result.querySelectorAll("[data-slot=badge]").length).toBe(
    recommended === null ? 0 : 1,
  );
  // Its reason and the caveat of the individual figure are its sentences.
  expect(one(result, "[data-comparison-reason]").textContent).toBe(
    projection.recommendation_reason_words,
  );
  expect(one(result, "[data-comparison-caveat]").textContent).toBe(
    projection.individual_branch_caveat,
  );
}

export const AskedFor: Story = {
  name: "Not asked yet: the comparison is offered, nothing is shown",
  render: (_, { globals }) => (
    <Element state="" locale={language(globals)} kind="idle" />
  ),
  play: async ({ canvasElement }) => {
    const root = await comparison(canvasElement);
    expect(one(root, "[data-comparison-ask]")).toBeEnabled();
    expect(root.querySelector("[data-comparison-result]")).toBeNull();
    expect(root.querySelector("[data-comparison-refusal]")).toBeNull();
  },
};

export const Reading: Story = {
  name: "Reading: the question is out and cannot be asked again",
  render: (_, { globals }) => (
    <Element state="" locale={language(globals)} kind="reading" />
  ),
  play: async ({ canvasElement }) => {
    const root = await comparison(canvasElement);
    const ask = one(root, "[data-comparison-ask]");
    expect(ask).toBeDisabled();
    expect(ask).toHaveAttribute("aria-busy", "true");
  },
};

export const JointFilingLower: Story = {
  name: "Joint filing comes out lower: that mode is marked and the reason is served",
  render: (_, { globals }) => (
    <Element state="married" locale={language(globals)} kind="answer" />
  ),
  play: async ({ canvasElement, globals }) => {
    await checkAnswer(canvasElement, "married", language(globals), "joint");
  },
};

export const IndividualFilingLower: Story = {
  name: "Individual filing comes out lower: that mode is marked instead",
  render: (_, { globals }) => (
    <Element
      state="married-individual"
      locale={language(globals)}
      kind="answer"
    />
  ),
  play: async ({ canvasElement, globals }) => {
    await checkAnswer(
      canvasElement,
      "married-individual",
      language(globals),
      "individual",
    );
  },
};

export const EitherModeAcceptable: Story = {
  name: "The two results do not differ: neither mode is marked, a refund stays a refund",
  render: (_, { globals }) => (
    <Element state="married-small" locale={language(globals)} kind="answer" />
  ),
  play: async ({ canvasElement, globals }) => {
    const locale = language(globals);
    await checkAnswer(canvasElement, "married-small", locale, null);
    // A negative result is drawn with its sign, not as an amount to pay.
    const result = await resulted(canvasElement);
    const text = one(
      one(result, "[data-comparison-mode=joint]"),
      "[data-comparison-result-amount]",
    ).textContent;
    expect(text).toMatch(/^[-−]/);
  },
};

export const CouldNotRead: Story = {
  name: "The request did not reach the application: said so, nothing is guessed",
  render: (_, { globals }) => (
    <Element state="" locale={language(globals)} kind="failed" />
  ),
  play: async ({ canvasElement }) => {
    const root = await comparison(canvasElement);
    expect(root).toHaveAttribute("data-phase", "failed");
    expect(root.querySelector("[data-comparison-result]")).toBeNull();
  },
};

/** One refusal, by the file it was read into, and whether the profile is
 * where the application's refusal sends the person. */
const REFUSALS: readonly {
  state: string;
  token: string;
  profile: boolean;
}[] = [
  {
    state: "",
    token: "family_situation_unstated",
    profile: true,
  },
  {
    state: "spouseless",
    token: "spouse_unstated",
    profile: true,
  },
  {
    state: "alone",
    token: "no_family_unit",
    profile: true,
  },
  {
    state: "uncalculated",
    token: "not_calculated",
    profile: false,
  },
  {
    state: "not-declared",
    token: "not_declared",
    profile: false,
  },
  {
    state: "revision-outdated",
    token: "revision_outdated",
    profile: false,
  },
  {
    state: "entries-unknown",
    token: "entries_unknown",
    profile: false,
  },
  {
    state: "uncredited",
    token: "unresolved_boxes",
    profile: false,
  },
  {
    state: "parent",
    token: "unresolved_boxes",
    profile: false,
  },
];

function refusalStory(entry: (typeof REFUSALS)[number]): Story {
  return {
    render: (_, { globals }) => (
      <Element state={entry.state} locale={language(globals)} kind="refusal" />
    ),
    play: async ({ canvasElement, globals }) => {
      const locale = language(globals);
      const root = await comparison(canvasElement);
      const drawn = await refused(root);
      const detail = await servedRefusal(entry.state, locale);
      // The reason is the application's closed token, and its sentence is
      // drawn as served.
      expect(drawn).toHaveAttribute("data-comparison-refusal", entry.token);
      expect(drawn.querySelector("[data-tone]")?.textContent).toBe(
        servedRefusalWords(detail),
      );
      // Nothing was compared, so nothing is drawn as a result.
      expect(root.querySelector("[data-comparison-result]")).toBeNull();
      // The profile is offered exactly where the household answers.
      expect(drawn.querySelector("[data-comparison-profile]") !== null).toBe(
        entry.profile,
      );
      // The boxes the application named are named here, none as a zero.
      const named = contextOf(detail, "casilla_ids")
        .split(",")
        .filter((box) => box.trim() !== "");
      expect(
        [...drawn.querySelectorAll("[data-comparison-box]")].map((box) =>
          box.getAttribute("data-comparison-box"),
        ),
      ).toEqual(named.map((box) => box.trim()));
    },
  };
}

export const FamilySituationUnstated: Story = {
  ...refusalStory(REFUSALS[0]!),
  name: "Family situation not stated: the profile puts it right",
};
export const SpouseUnstated: Story = {
  ...refusalStory(REFUSALS[1]!),
  name: "Spouse not stated: the profile puts it right",
};
export const NoFamilyUnit: Story = {
  ...refusalStory(REFUSALS[2]!),
  name: "No family unit: the profile states it",
};
export const NotCalculated: Story = {
  ...refusalStory(REFUSALS[3]!),
  name: "Not calculated: the sentence says to calculate first",
};
export const NotDeclared: Story = {
  ...refusalStory(REFUSALS[4]!),
  name: "The form declares no filing mode: nothing to compare",
};
export const RevisionOutdated: Story = {
  ...refusalStory(REFUSALS[5]!),
  name: "Calculated on an older version of the form",
};
export const EntriesUnknown: Story = {
  ...refusalStory(REFUSALS[6]!),
  name: "The calculation does not record the entries",
};
export const UnresolvedBoxes: Story = {
  ...refusalStory(REFUSALS[7]!),
  name: "Boxes without a value: named, never read as zero",
};

export const SingleParentCohabitationUnstated: Story = {
  ...refusalStory(REFUSALS[8]!),
  name: "Single parent who has not said whether they live with the other parent: the box that depends on it is named, never read as zero",
  play: async (context) => {
    await refusalStory(REFUSALS[8]!).play?.(context);
    const detail = await servedRefusal("parent", language(context.globals));
    expect(contextOf(detail, "casilla_ids").split(",")).toContain("0461");
  },
};

export const SingleParentApart: Story = {
  name: "Single parent who lives apart from the other parent: the joint reduction is applied and joint filing comes out lower",
  render: (_, { globals }) => (
    <Element state="parentapart" locale={language(globals)} kind="answer" />
  ),
  play: async ({ canvasElement, globals }) => {
    await checkAnswer(canvasElement, "parentapart", language(globals), "joint");
  },
};

export const WithoutAProfilePage: Story = {
  name: "No profile page in this window: the household refusal is shown without a link",
  render: (_, { globals }) => (
    <Element
      state="spouseless"
      locale={language(globals)}
      kind="refusal"
      profile={false}
    />
  ),
  play: async ({ canvasElement }) => {
    const root = await comparison(canvasElement);
    const drawn = await refused(root);
    expect(drawn).toHaveAttribute("data-comparison-refusal", "spouse_unstated");
    expect(drawn.querySelector("[data-comparison-profile]")).toBeNull();
  },
};

export const AskInTheWorkspace: Story = {
  name: "In the workspace: asking compares the held values and draws both modes",
  render: (_, { globals }) => (
    <Screen shape="renta-married" locale={language(globals)} />
  ),
  play: async ({ canvasElement, globals }) => {
    const root = await comparison(canvasElement);
    await userEvent.click(one(root, "[data-comparison-ask]"));
    await checkAnswer(canvasElement, "married", language(globals), "joint");
    // The comparison is a read: it can be asked for again.
    expect(one(root, "[data-comparison-ask]")).toBeEnabled();
  },
};

export const BoxesLinkToTheForm: Story = {
  name: "In the workspace: a box without a value opens at its place in the form",
  render: (_, { globals }) => (
    <Screen shape="renta-uncredited" locale={language(globals)} />
  ),
  play: async ({ canvasElement, globals }) => {
    const locale = language(globals);
    const root = await comparison(canvasElement);
    await userEvent.click(one(root, "[data-comparison-ask]"));
    const drawn = await refused(root);
    expect(drawn).toHaveAttribute(
      "data-comparison-refusal",
      "unresolved_boxes",
    );
    const detail = await servedRefusal("uncredited", locale);
    const box = contextOf(detail, "casilla_ids").split(",")[0]?.trim();
    if (!box) throw new Error("the refusal names no box");
    const link = one(drawn, `[data-comparison-box="${box}"] button`);
    await userEvent.click(link);
    // The form is shown, with the box chosen.
    await waitFor(
      () => {
        const tab = canvasElement.querySelector<HTMLElement>(
          "[role=tab][aria-selected=true]",
        );
        expect(tab?.textContent).toContain(
          translator(locale)("desktop.modelo.view.form"),
        );
      },
      { timeout: 30_000 },
    );
  },
};

const opened = fn();

export const HouseholdRefusalOpensTheProfile: Story = {
  name: "In the workspace: a refusal the household answers leads to the profile",
  render: (_, { globals }) => {
    opened.mockClear();
    return (
      <Screen
        shape="renta-spouseless"
        locale={language(globals)}
        onOpenSurface={opened}
      />
    );
  },
  play: async ({ canvasElement }) => {
    const root = await comparison(canvasElement);
    await userEvent.click(one(root, "[data-comparison-ask]"));
    const drawn = await refused(root);
    expect(drawn).toHaveAttribute("data-comparison-refusal", "spouse_unstated");
    await userEvent.click(one(drawn, "[data-comparison-profile]"));
    expect(opened).toHaveBeenCalledWith("profile");
  },
};

export const NotOfferedWhereTheFormDoesNotAsk: Story = {
  name: "A declaration whose form asks for no comparison offers none",
  render: (_, { globals }) => (
    <Screen
      shape="fixture"
      locale={language(globals)}
      unit={QUARTERLY_UNIT}
      initialView="form"
    />
  ),
  play: async ({ canvasElement, globals }) => {
    await waitFor(
      () => {
        if (!canvasElement.querySelector("[role=tablist]"))
          throw new Error("the workspace is not drawn yet");
      },
      { timeout: 30_000 },
    );
    const compare = translator(language(globals))(
      "desktop.modelo.view.compare",
    );
    expect(
      [...canvasElement.querySelectorAll("[role=tab]")].some((tab) =>
        tab.textContent?.includes(compare),
      ),
    ).toBe(false);
  },
};
