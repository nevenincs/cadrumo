import type { Meta, StoryObj } from "@storybook/react-vite";
import { useRef } from "react";
import { expect, userEvent, waitFor, within } from "storybook/test";
import {
  householdFixture,
  type HouseholdFixture,
  type HouseholdRefusal,
  type HouseholdScenario,
} from "@/dev/householdFixture";
import fixtures from "@/dev/fixtures/household.json";
import { translator } from "../../shell/strings";
import { Household } from "./Household";

// The household element on what the application served for synthetic profiles
// through the `family_rows` stream of `user-profile.view`: every group, state,
// leaf, limit and refusal sentence is its served text in the story's
// language. A write lands in the fixture and the element reads it again.

/** The label the product serves for a leaf of a group, in a language. */
function servedLabel(
  scenario: HouseholdScenario,
  locale: string,
  group: number,
  leaf: string,
): string {
  const byLanguage = fixtures.reads[scenario].items as unknown as Record<
    string,
    { kind: string; leaves?: { leaf: string; label: string }[] }[]
  >;
  const groups = (byLanguage[locale] ?? byLanguage.en!).filter(
    (item) => item.kind === "family_group",
  );
  return groups[group]!.leaves!.find((entry) => entry.leaf === leaf)!.label;
}

/** The question the product served for a scenario, in a language. */
function servedQuestion(scenario: HouseholdScenario, locale: string) {
  const byLanguage = fixtures.reads[scenario].items as unknown as Record<
    string,
    {
      kind: string;
      prompt?: string;
      saved_value?: string | null;
      choices?: { value: string; label: string }[];
    }[]
  >;
  return (byLanguage[locale] ?? byLanguage.en!).find(
    (item) => item.kind === "family_question",
  )!;
}

const language = (globals: Record<string, unknown>) =>
  String(globals.locale ?? "en");

function Element({
  scenario,
  locale,
  refuse,
  lose,
}: {
  scenario: HouseholdScenario;
  locale: string;
  refuse?: HouseholdRefusal;
  lose?: boolean;
}) {
  const fixture = useRef<HouseholdFixture | null>(null);
  if (fixture.current === null) {
    fixture.current = householdFixture(scenario, locale);
    if (refuse) fixture.current.refuseNext(refuse);
    if (lose) fixture.current.loseNextAnswer();
  }
  return (
    <div className="max-w-3xl">
      <Household
        reads={fixture.current.reads}
        change={fixture.current.change}
        language={locale}
      />
    </div>
  );
}

const meta: Meta = {
  title: "Profile/Household",
  parameters: { layout: "padded" },
};
export default meta;
type Story = StoryObj;

/** Waits for the household to be read, then returns its groups by state. */
async function groups(canvasElement: HTMLElement) {
  await waitFor(() => {
    if (!canvasElement.querySelector("[data-household-group]"))
      throw new Error("the household is not drawn yet");
  });
  return [...canvasElement.querySelectorAll("[data-household-group]")].map(
    (group) => ({
      key: group.getAttribute("data-household-group"),
      state: group.getAttribute("data-household-state"),
      element: group as HTMLElement,
    }),
  );
}

export const Unknown: Story = {
  name: "Unknown: nothing stated, which is not none",
  render: (_, { globals }) => (
    <Element scenario="unknown" locale={language(globals)} />
  ),
  play: async ({ canvasElement }) => {
    const shown = await groups(canvasElement);
    expect(shown.map((group) => group.state)).toEqual(["unknown", "unknown"]);
    // No person is drawn, and no group claims to be empty.
    expect(
      canvasElement.querySelectorAll("[data-household-person]"),
    ).toHaveLength(0);
  },
};

export const NoneDeclared: Story = {
  name: "None declared: the profile states a count of zero",
  render: (_, { globals }) => (
    <Element scenario="none_declared" locale={language(globals)} />
  ),
  play: async ({ canvasElement }) => {
    const shown = await groups(canvasElement);
    expect(shown.map((group) => group.state)).toEqual([
      "none_declared",
      "none_declared",
    ]);
  },
};

export const Rows: Story = {
  name: "Rows: the people recorded, in the product's words",
  render: (_, { globals }) => (
    <Element scenario="rows" locale={language(globals)} />
  ),
  play: async ({ canvasElement }) => {
    const shown = await groups(canvasElement);
    expect(shown.map((group) => group.state)).toEqual(["rows", "rows"]);
    expect(
      canvasElement.querySelectorAll("[data-household-person]"),
    ).toHaveLength(4);
  },
};

export const Incomplete: Story = {
  name: "Incomplete: the product's own N stated, M recorded",
  render: (_, { globals }) => (
    <Element scenario="incomplete" locale={language(globals)} />
  ),
  play: async ({ canvasElement }) => {
    const shown = await groups(canvasElement);
    expect(shown.map((group) => group.state)).toEqual([
      "incomplete",
      "incomplete",
    ]);
    const words = [
      ...canvasElement.querySelectorAll("[data-household-incomplete]"),
    ].map((element) => element.textContent ?? "");
    // The two numbers are the product's, one sentence per incomplete group.
    expect(words).toHaveLength(2);
    expect(words[0]).toMatch(/3/);
    expect(words[1]).toMatch(/2/);
    // The recorded people are still shown.
    expect(
      canvasElement.querySelectorAll("[data-household-person]"),
    ).toHaveLength(2);
  },
};

export const Masked: Story = {
  name: "Masked: a hidden value stays hidden and its group is not rewritten here",
  render: (_, { globals }) => (
    <Element scenario="masked" locale={language(globals)} />
  ),
  play: async ({ canvasElement, globals }) => {
    const shown = await groups(canvasElement);
    const hidden = canvasElement.querySelectorAll("[data-masked]");
    expect(hidden.length).toBeGreaterThan(0);
    // The values the masked read holds behind the mask, which no hidden fact may show.
    const concealed = (
      fixtures.reads.masked.items.en as unknown as {
        kind: string;
        facts?: { value: string; masked: boolean }[];
      }[]
    )
      .flatMap((item) => item.facts ?? [])
      .filter((fact) => fact.masked)
      .map((fact) => fact.value);
    for (const fact of hidden) {
      expect(fact.textContent).toContain("••••");
      for (const value of concealed)
        expect(fact.textContent).not.toContain(value);
    }
    // A replacement would have to state the hidden values again, so the group
    // that holds them offers no edit; the group without them still does.
    const t = translator(language(globals));
    const canvas = within(shown[0]!.element);
    expect(
      canvas.getByRole("button", {
        name: t("desktop.profile.household.edit_person", { number: 1 }),
      }),
    ).toBeDisabled();
    expect(
      within(shown[1]!.element).getByRole("button", {
        name: t("desktop.profile.household.edit_person", { number: 1 }),
      }),
    ).toBeEnabled();
  },
};

export const AtTheCap: Story = {
  name: "At the cap: the design's limit is served, and no more can be added",
  render: (_, { globals }) => (
    <Element scenario="at_cap" locale={language(globals)} />
  ),
  play: async ({ canvasElement, globals }) => {
    const shown = await groups(canvasElement);
    const t = translator(language(globals));
    for (const group of shown)
      expect(
        within(group.element).getByRole("button", {
          name: t("desktop.profile.household.add"),
        }),
      ).toBeDisabled();
    expect(
      canvasElement.querySelectorAll("[data-household-person]"),
    ).toHaveLength(19);
  },
};

export const AddsAPerson: Story = {
  name: "Adding: a person is stated and the household is read again",
  render: (_, { globals }) => (
    <Element scenario="unknown" locale={language(globals)} />
  ),
  play: async ({ canvasElement, globals }) => {
    const locale = language(globals);
    const t = translator(locale);
    const shown = await groups(canvasElement);
    const ascendants = shown[1]!;
    await userEvent.click(
      within(ascendants.element).getByRole("button", {
        name: t("desktop.profile.household.add"),
      }),
    );
    const dialog = within(await within(document.body).findByRole("dialog"));
    // The date of birth is the one thing the product asks of every person.
    const born = dialog.getByRole("textbox", {
      name: new RegExp(servedLabel("unknown", locale, 1, "birth_date")),
    });
    await userEvent.type(born, "1950-02-03");
    await userEvent.tab();
    await userEvent.click(
      dialog.getByRole("button", { name: t("desktop.profile.save") }),
    );
    await waitFor(() =>
      expect(
        canvasElement.querySelector(
          "[data-household-group='renta_family.ascendiente']",
        ),
      ).toHaveAttribute("data-household-state", "rows"),
    );
    expect(
      canvasElement.querySelectorAll("[data-household-person]"),
    ).toHaveLength(1);
    // The other group states nothing more than it did.
    expect(
      canvasElement.querySelector(
        "[data-household-group='renta_family.descendiente']",
      ),
    ).toHaveAttribute("data-household-state", "unknown");
  },
};

export const RefusedWrite: Story = {
  name: "Refused: the application's own sentence, the person kept in the dialog",
  render: (_, { globals }) => (
    <Element
      scenario="rows"
      locale={language(globals)}
      refuse="ascendants_second_nif_invalid"
    />
  ),
  play: async ({ canvasElement, globals }) => {
    const t = translator(language(globals));
    const shown = await groups(canvasElement);
    await userEvent.click(
      within(shown[1]!.element).getByRole("button", {
        name: t("desktop.profile.household.edit_person", { number: 1 }),
      }),
    );
    const dialog = within(await within(document.body).findByRole("dialog"));
    await userEvent.click(
      dialog.getByRole("button", { name: t("desktop.profile.save") }),
    );
    const refusal = await within(document.body).findByRole("alert");
    expect(refusal.textContent ?? "").toMatch(/2/);
    // What was typed is still there for another try.
    expect(within(document.body).getByRole("dialog")).toBeTruthy();
  },
};

export const UnknownOutcome: Story = {
  name: "Unknown outcome: writes stay closed until the person refreshes",
  render: (_, { globals }) => (
    <Element scenario="rows" locale={language(globals)} lose />
  ),
  play: async ({ canvasElement, globals }) => {
    const t = translator(language(globals));
    const shown = await groups(canvasElement);
    await userEvent.click(
      within(shown[1]!.element).getByRole("button", {
        name: t("desktop.profile.household.remove_person", { number: 1 }),
      }),
    );
    const dialog = within(await within(document.body).findByRole("dialog"));
    await userEvent.click(
      dialog.getByRole("button", {
        name: t("desktop.profile.household.remove"),
      }),
    );
    await waitFor(() =>
      expect(
        within(canvasElement).getByRole("button", {
          name: t("desktop.profile.refresh"),
        }),
      ).toBeEnabled(),
    );
    for (const button of within(canvasElement).getAllByRole("button", {
      name: t("desktop.profile.household.add"),
    }))
      expect(button).toBeDisabled();
  },
};

/** Waits for the household to be read and returns the question it is asked. */
async function asked(canvasElement: HTMLElement) {
  await groups(canvasElement);
  return canvasElement.querySelector<HTMLElement>("[data-household-question]");
}

const PATH = "renta_family.convive_con_otro_progenitor";

export const QuestionUnknown: Story = {
  name: "Question unknown: a single parent has not said, which is not no",
  render: (_, { globals }) => (
    <Element scenario="single_parent_unstated" locale={language(globals)} />
  ),
  play: async ({ canvasElement, globals }) => {
    const locale = language(globals);
    const t = translator(locale);
    const question = (await asked(canvasElement))!;
    expect(question).toHaveAttribute("data-household-answer", "unknown");
    const served = servedQuestion("single_parent_unstated", locale);
    expect(within(question).getByRole("heading").textContent).toBe(
      served.prompt,
    );
    expect(question.querySelector("[data-household-mark]")!.textContent).toBe(
      t("desktop.profile.household.state.unknown"),
    );
    // Neither answer is chosen, and nothing is offered to take back.
    for (const choice of within(question).getAllByRole("radio"))
      expect(choice).toHaveAttribute("aria-checked", "false");
    expect(
      within(question).queryByRole("button", {
        name: t("desktop.profile.household.question.clear"),
      }),
    ).toBeNull();
    expect(
      within(question).getByText(
        t("desktop.profile.household.question.unknown_help"),
      ),
    ).toBeTruthy();
  },
};

export const QuestionYes: Story = {
  name: "Question yes: the answer states they live together",
  render: (_, { globals }) => (
    <Element scenario="single_parent_lives_with" locale={language(globals)} />
  ),
  play: async ({ canvasElement, globals }) => {
    const locale = language(globals);
    const question = (await asked(canvasElement))!;
    expect(question).toHaveAttribute("data-household-answer", "true");
    const served = servedQuestion("single_parent_lives_with", locale);
    const yes = served.choices!.find((choice) => choice.value === "true")!;
    expect(question.querySelector("[data-household-mark]")!.textContent).toBe(
      yes.label,
    );
    expect(
      within(question).getByRole("radio", { name: yes.label }),
    ).toHaveAttribute("aria-checked", "true");
  },
};

export const QuestionNo: Story = {
  name: "Question no: the answer states they do not, drawn apart from unknown",
  render: (_, { globals }) => (
    <Element scenario="single_parent_apart" locale={language(globals)} />
  ),
  play: async ({ canvasElement, globals }) => {
    const locale = language(globals);
    const t = translator(locale);
    const question = (await asked(canvasElement))!;
    expect(question).toHaveAttribute("data-household-answer", "false");
    const served = servedQuestion("single_parent_apart", locale);
    const no = served.choices!.find((choice) => choice.value === "false")!;
    const mark = question.querySelector("[data-household-mark]")!.textContent;
    expect(mark).toBe(no.label);
    expect(mark).not.toBe(t("desktop.profile.household.state.unknown"));
    expect(
      within(question).getByRole("radio", { name: no.label }),
    ).toHaveAttribute("aria-checked", "true");
  },
};

export const QuestionNotAsked: Story = {
  name: "Question not asked: a married unit is not served the single-parent question",
  render: (_, { globals }) => (
    <Element scenario="married" locale={language(globals)} />
  ),
  play: async ({ canvasElement }) => {
    await groups(canvasElement);
    expect(canvasElement.querySelector("[data-household-question]")).toBeNull();
  },
};

export const QuestionAnswered: Story = {
  name: "Answering: the answer is written to the profile fact and can be taken back",
  render: (_, { globals }) => (
    <Element scenario="single_parent_unstated" locale={language(globals)} />
  ),
  play: async ({ canvasElement, globals }) => {
    const locale = language(globals);
    const t = translator(locale);
    const question = (await asked(canvasElement))!;
    const served = servedQuestion("single_parent_unstated", locale);
    const yes = served.choices!.find((choice) => choice.value === "true")!;
    await userEvent.click(
      within(question).getByRole("radio", { name: yes.label }),
    );
    await waitFor(() =>
      expect(question).toHaveAttribute("data-household-answer", "true"),
    );
    await userEvent.click(
      within(question).getByRole("button", {
        name: t("desktop.profile.household.question.clear"),
      }),
    );
    await waitFor(() =>
      expect(question).toHaveAttribute("data-household-answer", "unknown"),
    );
    // Each write named the fact and the token of a served choice, or the
    // empty token that takes the statement back.
    expect(
      window.__scenarioHousehold!.writes().map((write) => write.edit),
    ).toEqual([
      { kind: "field", path: PATH, value: "true" },
      { kind: "field", path: PATH, value: "" },
    ]);
  },
};
