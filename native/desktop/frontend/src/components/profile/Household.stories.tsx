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
    for (const fact of hidden) {
      expect(fact.textContent).toContain("••••");
      expect(fact.textContent).not.toMatch(/12345678Z|2012-01-01/);
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
      refuse="second_nif_invalid"
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
