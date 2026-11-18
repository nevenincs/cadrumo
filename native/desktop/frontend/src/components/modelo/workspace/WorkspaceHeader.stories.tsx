import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState, type ReactNode } from "react";
import { expect, userEvent, waitFor } from "storybook/test";
import form130 from "@fixtures/modelo/modelo-130-1T-en.json" with { type: "json" };
import type { ModeloFormResultView } from "../../../shell/modeloContract/modeloWork";
import type { ModeloWorkbenchFormProjectionV1 } from "../../../shell/modeloContract/modeloWorkForm";
import type { OutputLanguage } from "../../../shell/modeloContract/modelo";
import { usePanePreference } from "../../../shell/panePreference";
import { ModeloWorkspace } from "./Workspace";
import { WORKSPACE_PANE_IDS } from "./WorkspacePanes";

// The declaration header of one workspace, drawn over a served envelope. Its
// geometry must not move when its words do: each story shows one case, and
// the last two change the status while measuring the header.

const noop = () => undefined;

const SERVED = form130 as unknown as ModeloWorkbenchFormProjectionV1;

const NARROW = 528;
const DESKTOP = 1056;

// Display test data only: a figure the served envelope does not carry, so the
// figure's line is drawn, and sentences longer than any place keeps.
const stated: ModeloFormResultView = {
  ...SERVED.header.result!,
  state: "stated",
  direction: "to_pay",
  words: "To pay",
  amount_text: "1.234,56 €",
  text: "Result: to pay 1.234,56 €",
  short_text: "To pay 1.234,56 €",
  help: [],
  out_of_date_words: null,
};

const withResult = (
  result: ModeloFormResultView | null,
): ModeloWorkbenchFormProjectionV1 => ({
  ...SERVED,
  header: { ...SERVED.header, result },
});

const SHORT = withResult(stated);

const LONG_SENTENCE =
  "and then a good deal more wording than the place it is drawn in can keep on one line, so that it has to be cut";

const longWords = (): ModeloWorkbenchFormProjectionV1 => {
  const copy = structuredClone(withResult(stated));
  const { header } = copy;
  if (header.deadline)
    header.deadline.text = `${header.deadline.text} ${LONG_SENTENCE}`;
  header.file = {
    current: true,
    words: `Exported file ${LONG_SENTENCE}`,
  } as NonNullable<typeof header.file>;
  if (header.result) {
    header.result.words = `${header.result.words} ${LONG_SENTENCE}`;
    header.result.short_text = `${header.result.short_text} ${LONG_SENTENCE}`;
  }
  return copy;
};

const NOT_STATED: ModeloFormResultView = {
  ...stated,
  state: "not_calculated",
  direction: "unknown",
  words: null,
  amount_text: null,
  text: "Result: not calculated yet",
  short_text: "Result: not calculated yet",
  brief_text: "Result: not calculated yet",
};

const language = (globals: Record<string, unknown>) =>
  String(globals.locale ?? "en") as OutputLanguage;

const placeholder = (name: string) => <p className="p-6">{name}</p>;

function Workspace({
  envelope,
  locale,
  stagedCount = 0,
  busy = false,
  reading = false,
}: {
  envelope: ModeloWorkbenchFormProjectionV1;
  locale: OutputLanguage;
  stagedCount?: number;
  busy?: boolean;
  reading?: boolean;
}) {
  const side = usePanePreference(WORKSPACE_PANE_IDS.side);
  const details = usePanePreference(WORKSPACE_PANE_IDS.details);
  return (
    <ModeloWorkspace
      envelope={envelope}
      locale={locale}
      view="form"
      onViewChange={noop}
      stagedCount={stagedCount}
      panes={{ side, details }}
      busy={busy}
      reading={reading}
      slots={{
        form: placeholder("Form"),
        filing: placeholder("Filing"),
        check: placeholder("Check"),
        sources: placeholder("Sources"),
        history: placeholder("History"),
      }}
      onRun={noop}
      onReview={noop}
      onDiscardStaged={noop}
      onJumpToFirstAttention={noop}
      onCorrect={noop}
      onBack={noop}
    />
  );
}

/** A frame of fixed width and height, so a story shows the header and the
 * tabs and nothing under them. */
function Sized({ width, children }: { width: number; children: ReactNode }) {
  return (
    <div className="h-105 max-w-full border border-border" style={{ width }}>
      {children}
    </div>
  );
}

/** The workspace's states in turn, with a button outside the header that
 * moves to the next. */
const STATES = [
  { stagedCount: 0, reading: false, result: stated },
  { stagedCount: 1, reading: false, result: stated },
  { stagedCount: 0, reading: true, result: stated },
  { stagedCount: 0, reading: false, result: NOT_STATED },
] as const;

function Changing({
  width,
  locale,
}: {
  width: number;
  locale: OutputLanguage;
}) {
  const [index, setIndex] = useState(0);
  const state = STATES[index]!;
  return (
    <div className="flex flex-col gap-3">
      <button
        type="button"
        className="self-start rounded-md border border-border px-3 py-1 text-sm"
        onClick={() => setIndex((held) => (held + 1) % STATES.length)}
      >
        Next state
      </button>
      <Sized width={width}>
        <Workspace
          envelope={withResult(state.result)}
          locale={locale}
          stagedCount={state.stagedCount}
          reading={state.reading}
        />
      </Sized>
    </div>
  );
}

const meta: Meta = {
  title: "Modelo/Workspace header",
  parameters: { layout: "padded" },
};
export default meta;
type Story = StoryObj;

const headerOf = async (canvasElement: HTMLElement) =>
  waitFor(
    () => {
      const found = canvasElement.querySelector<HTMLElement>("header");
      if (!found) throw new Error("the header is not drawn yet");
      return found;
    },
    { timeout: 15_000 },
  );

export const DesktopShort: Story = {
  name: "Desktop · short words",
  render: (_, { globals }) => (
    <Sized width={DESKTOP}>
      <Workspace envelope={SHORT} locale={language(globals)} />
    </Sized>
  ),
};

export const NarrowShort: Story = {
  name: "Narrow · short words",
  render: (_, { globals }) => (
    <Sized width={NARROW}>
      <Workspace envelope={SHORT} locale={language(globals)} />
    </Sized>
  ),
};

/** Long words are cut, never wrapped: the header does not outgrow its room
 * and says which of its words were cut. */
const staysWithinItsRoom = async ({
  canvasElement,
}: {
  canvasElement: HTMLElement;
}) => {
  const header = await headerOf(canvasElement);
  await waitFor(() =>
    expect(canvasElement.querySelector("[data-clipped]")).not.toBeNull(),
  );
  await expect(header.scrollWidth).toBeLessThanOrEqual(header.clientWidth);
};

export const DesktopLong: Story = {
  name: "Desktop · long words",
  render: (_, { globals }) => (
    <Sized width={DESKTOP}>
      <Workspace envelope={longWords()} locale={language(globals)} />
    </Sized>
  ),
  play: staysWithinItsRoom,
};

export const NarrowLong: Story = {
  name: "Narrow · long words",
  render: (_, { globals }) => (
    <Sized width={NARROW}>
      <Workspace envelope={longWords()} locale={language(globals)} />
    </Sized>
  ),
  play: staysWithinItsRoom,
};

export const DesktopBusy: Story = {
  name: "Desktop · operation in progress",
  render: (_, { globals }) => (
    <Sized width={DESKTOP}>
      <Workspace
        envelope={withResult(NOT_STATED)}
        locale={language(globals)}
        busy
      />
    </Sized>
  ),
};

export const DesktopReading: Story = {
  name: "Desktop · reading again",
  render: (_, { globals }) => (
    <Sized width={DESKTOP}>
      <Workspace envelope={SHORT} locale={language(globals)} reading />
    </Sized>
  ),
};

export const NarrowReading: Story = {
  name: "Narrow · reading again",
  render: (_, { globals }) => (
    <Sized width={NARROW}>
      <Workspace envelope={SHORT} locale={language(globals)} reading />
    </Sized>
  ),
};

type Measure = {
  height: number;
  tabsTop: number;
  stepRight: number;
  resultRight: number;
  figureRight: number | null;
};

const measure = (canvasElement: HTMLElement): Measure => {
  const header = canvasElement.querySelector("header");
  const tabs = canvasElement.querySelector('[role="tablist"]');
  const step = canvasElement.querySelector("[data-header-step]");
  const result = canvasElement.querySelector("[data-header-result]");
  const figure = canvasElement.querySelector("[data-header-figure]");
  if (!header || !tabs || !step || !result)
    throw new Error("the header is not drawn yet");
  return {
    height: header.getBoundingClientRect().height,
    tabsTop: tabs.getBoundingClientRect().top,
    stepRight: step.getBoundingClientRect().right,
    resultRight: result.getBoundingClientRect().right,
    figureRight: figure ? figure.getBoundingClientRect().right : null,
  };
};

const frame = () =>
  new Promise<void>((done) =>
    requestAnimationFrame(() => requestAnimationFrame(() => done())),
  );

/** Goes through every state and expects the header to keep its geometry. */
const keepsItsGeometry = async ({
  canvasElement,
}: {
  canvasElement: HTMLElement;
}) => {
  await headerOf(canvasElement);
  const next = [...canvasElement.querySelectorAll("button")].find(
    (candidate) => candidate.textContent === "Next state",
  );
  if (!next) throw new Error("the button is not drawn yet");
  await frame();
  const first = measure(canvasElement);
  await expect(first.figureRight).not.toBeNull();
  for (let turn = 0; turn < STATES.length; turn += 1) {
    await userEvent.click(next);
    await frame();
    const now = measure(canvasElement);
    await expect(Math.abs(now.height - first.height)).toBeLessThanOrEqual(1);
    await expect(Math.abs(now.tabsTop - first.tabsTop)).toBeLessThanOrEqual(1);
    await expect(Math.abs(now.stepRight - first.stepRight)).toBeLessThanOrEqual(
      1,
    );
    await expect(
      Math.abs(now.resultRight - first.resultRight),
    ).toBeLessThanOrEqual(1);
    // The figure is drawn in the states that state the result.
    if (now.figureRight !== null && first.figureRight !== null)
      await expect(
        Math.abs(now.figureRight - first.figureRight),
      ).toBeLessThanOrEqual(1);
  }
};

export const DesktopChanging: Story = {
  name: "Desktop · status changing",
  render: (_, { globals }) => (
    <Changing width={DESKTOP} locale={language(globals)} />
  ),
  play: keepsItsGeometry,
};

export const NarrowChanging: Story = {
  name: "Narrow · status changing",
  render: (_, { globals }) => (
    <Changing width={NARROW} locale={language(globals)} />
  ),
  play: keepsItsGeometry,
};
