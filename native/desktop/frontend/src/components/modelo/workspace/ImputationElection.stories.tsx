import { RENTA_UNIT } from "@/dev/rentaUnit";
import type { Meta, StoryObj } from "@storybook/react-vite";
import { useRef } from "react";
import { expect, userEvent, waitFor, within } from "storybook/test";
import fixtures from "@fixtures/desktop-imputation-election/imputationElection.json" with { type: "json" };
import { modeloFixture } from "@/dev/modeloFixture";
import {
  imputationElectionFixture,
  type ElectionFixture,
  type ElectionRefusal,
  type ElectionScenario,
} from "@/dev/imputationElectionFixture";
import type { ModeloPort } from "../../../shell/modelo";
import type { OutputLanguage } from "../../../shell/modeloContract/modelo";
import { translator } from "../../../shell/strings";
import { ImputationElection } from "./ImputationElection";
import { WorkspaceScreen } from "./WorkspaceScreen";

// The imputation election element on what the application read for synthetic
// profiles through `user-profile.imputation-election.read`: the questions,
// choices and refusals are its served words in the story's language. A write
// lands in the fixture and the element reads it again.

const noop = () => undefined;
const PROFILE = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
/** The ejercicio the application read the elections for. */
const YEAR = fixtures.reads.devengo.en.tax_year;

const language = (globals: Record<string, unknown>) =>
  String(globals.locale ?? "en") as OutputLanguage;

function Element({
  scenario,
  locale,
  refuse,
}: {
  scenario: ElectionScenario;
  locale: string;
  refuse?: ElectionRefusal;
}) {
  const fixture = useRef<ElectionFixture | null>(null);
  if (fixture.current === null) {
    fixture.current = imputationElectionFixture(scenario, locale);
    if (refuse) fixture.current.refuseNext(refuse);
  }
  return (
    <div className="max-w-xl">
      <ImputationElection
        profile={PROFILE}
        taxYear={YEAR}
        language={locale}
        reads={fixture.current.reads}
        change={fixture.current.change}
      />
    </div>
  );
}

const meta: Meta = {
  title: "Modelo/Workspace/Imputation election",
  parameters: { layout: "padded" },
};
export default meta;
type Story = StoryObj;

/** Waits for the election to be read, then returns its radios. */
async function choices(canvasElement: HTMLElement) {
  const canvas = within(canvasElement);
  return waitFor(() => {
    const found = canvas.getAllByRole("radio");
    if (found.length < 2) throw new Error("the choices are not drawn yet");
    return found;
  });
}

export const Undeclared: Story = {
  name: "Undeclared: no year stated, nothing chosen",
  render: (_, { globals }) => (
    <Element scenario="undeclared" locale={language(globals)} />
  ),
  play: async ({ canvasElement }) => {
    const radios = await choices(canvasElement);
    // An unstated year is not read as any of the choices.
    for (const radio of radios) expect(radio).not.toBeChecked();
    expect(
      canvasElement.querySelector("[data-election-state]"),
    ).toHaveAttribute("data-election-state", "undeclared");
  },
};

export const DeclaredAccrual: Story = {
  name: "Declared: the first choice, other years listed",
  render: (_, { globals }) => (
    <Element scenario="devengo" locale={language(globals)} />
  ),
  play: async ({ canvasElement }) => {
    const radios = await choices(canvasElement);
    expect(radios[0]).toBeChecked();
    expect(radios[1]).not.toBeChecked();
  },
};

export const DeclaredCashWithAccounting: Story = {
  name: "Declared: the second choice, with the accounting answer asked",
  render: (_, { globals }) => (
    <Element scenario="cobros_y_pagos" locale={language(globals)} />
  ),
  play: async ({ canvasElement }) => {
    const radios = await choices(canvasElement);
    expect(radios[1]).toBeChecked();
    // The accounting question follows, with its stated answer.
    const canvas = within(canvasElement);
    await waitFor(() =>
      expect(canvas.getAllByRole("radiogroup")).toHaveLength(2),
    );
  },
};

export const ChoosingAskingTheAccounting: Story = {
  name: "Choosing the second choice asks the accounting question",
  render: (_, { globals }) => (
    <Element scenario="undeclared" locale={language(globals)} />
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const radios = await choices(canvasElement);
    expect(canvas.getAllByRole("radiogroup")).toHaveLength(1);
    await userEvent.click(radios[1]!);
    await waitFor(() =>
      expect(canvas.getAllByRole("radiogroup")).toHaveLength(2),
    );
  },
};

export const Contradictory: Story = {
  name: "Contradictory: more than one answer stated, none chosen",
  render: (_, { globals }) => (
    <Element scenario="contradictory" locale={language(globals)} />
  ),
  play: async ({ canvasElement }) => {
    const radios = await choices(canvasElement);
    for (const radio of radios) expect(radio).not.toBeChecked();
    expect(
      canvasElement.querySelector("[data-election-state]"),
    ).toHaveAttribute("data-election-state", "contradictory");
  },
};

export const SavedAndReadAgain: Story = {
  name: "Saved: the write lands and the election is read again",
  render: (_, { globals }) => (
    <Element scenario="undeclared" locale={language(globals)} />
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const radios = await choices(canvasElement);
    await userEvent.click(radios[0]!);
    await userEvent.click(canvas.getAllByRole("button")[0]!);
    await waitFor(() =>
      expect(
        canvasElement.querySelector("[data-election-state]"),
      ).toHaveAttribute("data-election-state", "declared"),
    );
  },
};

export const RefusedWrite: Story = {
  name: "Refused: the application's own sentence, the choice kept",
  render: (_, { globals }) => (
    <Element
      scenario="undeclared"
      locale={language(globals)}
      refuse="unknown_choice"
    />
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const radios = await choices(canvasElement);
    await userEvent.click(radios[0]!);
    await userEvent.click(canvas.getAllByRole("button")[0]!);
    await canvas.findByRole("alert");
    expect((await choices(canvasElement))[0]).toBeChecked();
  },
};

export const ChangedElsewhere: Story = {
  name: "Conflict: the profile moved, the choice is kept against the new revision",
  render: (_, { globals }) => (
    <Element scenario="undeclared" locale={language(globals)} refuse="stale" />
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const radios = await choices(canvasElement);
    await userEvent.click(radios[1]!);
    await userEvent.click(canvas.getAllByRole("button")[0]!);
    await canvas.findByRole("alert");
  },
};

function Sources({ locale }: { locale: OutputLanguage }) {
  const port = useRef<ModeloPort | null>(null);
  const election = useRef<ElectionFixture | null>(null);
  port.current ??= modeloFixture({
    say: noop,
    translate: translator,
    wait: async () => undefined,
    signedIn: () => true,
    shape: "renta-activity",
  });
  election.current ??= imputationElectionFixture("undeclared", locale);
  return (
    <div className="flex h-full min-h-0 flex-col">
      <WorkspaceScreen
        port={port.current}
        workUnitId={RENTA_UNIT}
        language={locale}
        locale={locale}
        onBack={noop}
        onOpenSurface={noop}
        canOpenSurface={() => true}
        openLink={noop}
        initialView="sources"
        profileCompanions={{
          reads: {
            household: () => Promise.reject({ code: "unavailable" }),
            householdDraft: () => Promise.reject({ code: "unavailable" }),
            imputationElection: election.current.reads.imputationElection,
          },
          change: election.current.change,
        }}
      />
    </div>
  );
}

export const InTheSourcesView: Story = {
  name: "In the Renta's Sources view, for a declaration that asks for it",
  parameters: { fill: true, layout: "fullscreen" },
  render: (_, { globals }) => <Sources locale={language(globals)} />,
};
