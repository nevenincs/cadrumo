import type { Meta, StoryObj } from "@storybook/react-vite";
import { useRef } from "react";
import { expect, userEvent, waitFor, within } from "storybook/test";
import {
  householdFixture,
  type HouseholdFixture,
  type HouseholdRefusal,
  type HouseholdScenario,
} from "@/dev/householdFixture";
import fixtures from "@fixtures/desktop-household/household.json" with { type: "json" };
import { translator } from "../../shell/strings";
import { Household } from "./Household";

// The household element on what the application served for synthetic profiles
// through the `family_rows` stream of `user-profile.view`: every group, state,
// leaf, limit, add and remove control and refusal sentence is its served text
// in the story's language. Which leaves a person is asked is the product's ask
// for each, served with the group or the person and, after an answer changes,
// read again for the answers typed so far (the fixture answers the draft
// read). A write lands in the fixture and the element reads it again.

type ServedGroup = {
  kind: string;
  leaves?: {
    leaf: string;
    label: string;
    choices: { value: string; label: string }[];
    shown_when: { leaf: string; equals: string | null }[];
  }[];
  add_row_action?: { action_words: string } | null;
  remove_row_action?: { action_words: string } | null;
};

/** Distinct birth dates the product served for its descendants in the `rows`
 * scenario, in the order served: dates to type that need no year of their own. */
const servedDates = (
  fixtures.reads.rows.items.en as unknown as {
    kind: string;
    group_key: string;
    facts?: { leaf: string; value: string }[];
  }[]
)
  .filter((item) => item.kind === "family_row")
  .map((row) => row.facts?.find((fact) => fact.leaf === "birth_date")?.value)
  .filter(
    (date, index, dates): date is string =>
      date !== undefined && dates.indexOf(date) === index,
  );

/** The group the product serves at `group` of a scenario, in a language. */
function servedGroup(
  scenario: HouseholdScenario,
  locale: string,
  group: number,
): ServedGroup {
  const byLanguage = fixtures.reads[scenario].items as unknown as Record<
    string,
    ServedGroup[]
  >;
  return (byLanguage[locale] ?? byLanguage.en!).filter(
    (item) => item.kind === "family_group",
  )[group]!;
}

/** The label the product serves for a leaf of a group, in a language. */
function servedLabel(
  scenario: HouseholdScenario,
  locale: string,
  group: number,
  leaf: string,
): string {
  return servedGroup(scenario, locale, group).leaves!.find(
    (entry) => entry.leaf === leaf,
  )!.label;
}

/** The words of a group's served add control, in a language. */
const addWords = (scenario: HouseholdScenario, locale: string, group: number) =>
  servedGroup(scenario, locale, group).add_row_action!.action_words;

/** The words of a group's served remove control, in a language. */
const removeWords = (
  scenario: HouseholdScenario,
  locale: string,
  group: number,
) => servedGroup(scenario, locale, group).remove_row_action!.action_words;

/** The edits the changes sent so far stated, in order. */
const sentEdits = () =>
  window.__scenarioHousehold!.writes().map((write) => write.edit);

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

/** Whether the story's reads fail, to show a read that cannot be made. */
let readsFail = false;

function Element({
  scenario,
  locale,
  refuse,
  lose,
  refuseDraft,
}: {
  scenario: HouseholdScenario;
  locale: string;
  refuse?: HouseholdRefusal;
  lose?: boolean;
  /** The first draft read is refused as the product refuses an invalid
   * draft. */
  refuseDraft?: boolean;
}) {
  const fixture = useRef<HouseholdFixture | null>(null);
  if (fixture.current === null) {
    readsFail = false;
    fixture.current = householdFixture(scenario, locale);
    if (refuse) fixture.current.refuseNext(refuse);
    if (lose) fixture.current.loseNextAnswer();
    if (refuseDraft) fixture.current.refuseNextDraft();
  }
  const served = fixture.current.reads;
  const reads: typeof served = {
    household: (...asked) => {
      if (readsFail) return Promise.reject({ code: "unavailable" });
      return served.household(...asked);
    },
    householdDraft: served.householdDraft,
  };
  return (
    <div className="max-w-3xl">
      <Household
        reads={reads}
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
  name: "Masked: a hidden value stays hidden, its people are not edited here, and one can still be added or removed",
  render: (_, { globals }) => (
    <Element scenario="masked" locale={language(globals)} />
  ),
  play: async ({ canvasElement, globals }) => {
    const locale = language(globals);
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
    // An edit would have to state the hidden values again, so the group that
    // holds them offers no edit; the group without them still does.
    const t = translator(locale);
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
    // Adding or removing one person resends nobody, so a hidden value stops
    // neither; each control is the product's own words.
    expect(
      canvas.getByRole("button", { name: addWords("masked", locale, 0) }),
    ).toBeEnabled();
    for (const remove of canvas.getAllByRole("button", {
      name: removeWords("masked", locale, 0),
    }))
      expect(remove).toBeEnabled();
  },
};

export const AtTheCap: Story = {
  name: "At the cap: the design's limit is served, and no add control is",
  render: (_, { globals }) => (
    <Element scenario="at_cap" locale={language(globals)} />
  ),
  play: async ({ canvasElement, globals }) => {
    const shown = await groups(canvasElement);
    const t = translator(language(globals));
    for (const group of shown) {
      expect(group.element.querySelector("[data-household-add]")).toBeNull();
      expect(
        within(group.element).getByText(
          t("desktop.profile.household.cap_reached"),
        ),
      ).toBeTruthy();
    }
    expect(
      canvasElement.querySelectorAll("[data-household-person]"),
    ).toHaveLength(19);
  },
};

/** The leaves a dialog asks now, in the order drawn. */
const askedIn = (dialog: HTMLElement) =>
  [...dialog.querySelectorAll("[data-household-leaf]")].map((field) =>
    field.getAttribute("data-household-leaf"),
  );

/** The leaves a dialog holds back until an answer is given, as it notes
 * them. */
const awaitingIn = (dialog: HTMLElement) =>
  dialog
    .querySelector("[data-household-awaiting]")
    ?.getAttribute("data-household-awaiting")
    ?.split(" ") ?? [];

/** The household a scenario serves, read from a fixture of its own so the
 * controls of the story's fixture stay as they are. */
async function servedHousehold(scenario: HouseholdScenario, locale: string) {
  const controls = window.__scenarioHousehold;
  const household = await householdFixture(scenario, locale).reads.household(
    locale,
  );
  window.__scenarioHousehold = controls;
  return household;
}

/** The asks the product serves for a blank descendant. */
async function servedAsks(scenario: HouseholdScenario, locale: string) {
  const household = await servedHousehold(scenario, locale);
  return household.groups.find((group) =>
    group.group_key.endsWith("descendiente"),
  )!.new_row_leaves;
}

async function openNewDescendant(
  canvasElement: HTMLElement,
  scenario: HouseholdScenario,
  locale: string,
) {
  const shown = await groups(canvasElement);
  await userEvent.click(
    within(shown[0]!.element).getByRole("button", {
      name: addWords(scenario, locale, 0),
    }),
  );
  return within(document.body).findByRole("dialog");
}

export const NewPersonForm: Story = {
  name: "New person: a leaf is shown only while its served ask is asked",
  render: (_, { globals }) => (
    <Element scenario="unknown" locale={language(globals)} />
  ),
  play: async ({ canvasElement, globals }) => {
    const locale = language(globals);
    const dialog = await openNewDescendant(canvasElement, "unknown", locale);
    // The dialog is titled by the served add control.
    expect(
      within(dialog).getByRole("heading", {
        name: addWords("unknown", locale, 0),
      }),
    ).toBeTruthy();
    const asks = await servedAsks("unknown", locale);
    const asked = asks.filter((entry) => entry.ask === "asked");
    expect(asked.length).toBeGreaterThan(0);
    expect(asks.length).toBeGreaterThan(asked.length);
    // Exactly the leaves served as asked are drawn, in served order, and no
    // draft was read for them.
    expect(askedIn(dialog)).toEqual(asked.map((entry) => entry.leaf));
    expect(window.__scenarioHousehold!.drafts()).toHaveLength(0);
  },
};

export const AnswerAsksALeaf: Story = {
  name: "Answer: an answer is read by the product and the leaf it asks appears; taking it back hides it",
  render: (_, { globals }) => (
    <Element scenario="unknown" locale={language(globals)} />
  ),
  play: async ({ canvasElement, globals }) => {
    const locale = language(globals);
    const dialog = await openNewDescendant(canvasElement, "unknown", locale);
    const served = servedGroup("unknown", locale, 0);
    const relation = served.leaves!.find((entry) => entry.leaf === "relacion")!;
    const adopted = relation.choices.find(
      (entry) => entry.value === "adoptado",
    )!;
    const select = () =>
      within(dialog).getByRole("combobox", { name: relation.label });
    expect(askedIn(dialog)).not.toContain("inscripcion_registro_civil");
    await userEvent.selectOptions(select(), adopted.label);
    await waitFor(() =>
      expect(askedIn(dialog)).toContain("inscripcion_registro_civil"),
    );
    // The product was asked once, with the answer typed and nothing else.
    expect(window.__scenarioHousehold!.drafts()).toEqual([
      {
        group: "renta_family.descendiente",
        facts: [{ leaf: "relacion", value: "adoptado" }],
      },
    ]);
    // Taking the answer back asks it no more.
    await userEvent.selectOptions(
      select(),
      translator(locale)("desktop.profile.not_set"),
    );
    await waitFor(() =>
      expect(askedIn(dialog)).not.toContain("inscripcion_registro_civil"),
    );
  },
};

export const LeafNotAsked: Story = {
  name: "Not asked: an answered leaf the product no longer asks after is not drawn",
  render: (_, { globals }) => (
    <Element scenario="unknown" locale={language(globals)} />
  ),
  play: async ({ canvasElement, globals }) => {
    const locale = language(globals);
    const dialog = await openNewDescendant(canvasElement, "unknown", locale);
    const served = servedGroup("unknown", locale, 0);
    const lives = served.leaves!.find((entry) => entry.leaf === "convivencia")!;
    const no = lives.choices.find((entry) => entry.value === "false")!;
    const yes = lives.choices.find((entry) => entry.value === "true")!;
    const select = () =>
      within(dialog).getByRole("combobox", { name: lives.label });
    await userEvent.selectOptions(select(), no.label);
    await waitFor(() =>
      expect(askedIn(dialog)).toContain("dependencia_economica"),
    );
    await userEvent.selectOptions(select(), yes.label);
    await waitFor(() =>
      expect(askedIn(dialog)).not.toContain("dependencia_economica"),
    );
    // The product served it as not asked, not as waiting for an answer.
    expect(awaitingIn(dialog)).not.toContain("dependencia_economica");
  },
};

export const LeafAwaitsAnswer: Story = {
  name: "Awaits answer: a leaf whose governing answer is missing shows nothing, and is noted",
  render: (_, { globals }) => (
    <Element scenario="unknown" locale={language(globals)} />
  ),
  play: async ({ canvasElement, globals }) => {
    const locale = language(globals);
    const dialog = await openNewDescendant(canvasElement, "unknown", locale);
    const awaiting = (await servedAsks("unknown", locale))
      .filter((entry) => entry.ask === "awaits_answer")
      .map((entry) => entry.leaf);
    expect(awaiting.length).toBeGreaterThan(0);
    // No field and no words are drawn for them; the dialog only notes them.
    for (const leaf of awaiting)
      expect(
        dialog.querySelector(`[data-household-leaf="${leaf}"]`),
      ).toBeNull();
    expect(awaitingIn(dialog)).toEqual(awaiting);
  },
};

export const StoredPersonAsks: Story = {
  name: "Stored person: the form starts from the asks served with the person, without a read",
  render: (_, { globals }) => (
    <Element scenario="rows" locale={language(globals)} />
  ),
  play: async ({ canvasElement, globals }) => {
    const locale = language(globals);
    const t = translator(locale);
    const shown = await groups(canvasElement);
    const household = await servedHousehold("rows", locale);
    const first = household.groups[0]!.rows[0]!.leaf_asks;
    await userEvent.click(
      within(shown[0]!.element).getAllByRole("button", {
        name: t("desktop.profile.household.edit_person", { number: 1 }),
      })[0]!,
    );
    const dialog = await within(document.body).findByRole("dialog");
    expect(askedIn(dialog)).toEqual(
      first.filter((entry) => entry.ask === "asked").map((entry) => entry.leaf),
    );
    // This person is served a leaf as not asked, which stays out.
    expect(first.some((entry) => entry.ask === "not_asked")).toBe(true);
    expect(window.__scenarioHousehold!.drafts()).toHaveLength(0);
  },
};

export const SubmitsOnlyAskedLeaves: Story = {
  name: "Saved: a leaf typed and then no longer asked is not sent",
  render: (_, { globals }) => (
    <Element scenario="unknown" locale={language(globals)} />
  ),
  play: async ({ canvasElement, globals }) => {
    const locale = language(globals);
    const t = translator(locale);
    const node = await openNewDescendant(canvasElement, "unknown", locale);
    const dialog = within(node);
    const served = servedGroup("unknown", locale, 0);
    const leaf = (key: string) =>
      served.leaves!.find((entry) => entry.leaf === key)!;
    const relation = leaf("relacion");
    const choose = (value: string) =>
      userEvent.selectOptions(
        dialog.getByRole("combobox", { name: relation.label }),
        relation.choices.find((entry) => entry.value === value)!.label,
      );
    await userEvent.type(
      dialog.getByRole("textbox", {
        name: new RegExp(servedLabel("unknown", locale, 0, "birth_date")),
      }),
      servedDates[0]!,
    );
    await choose("adoptado");
    await waitFor(() =>
      expect(askedIn(node)).toContain("inscripcion_registro_civil"),
    );
    await userEvent.type(
      dialog.getByRole("textbox", {
        name: new RegExp(leaf("inscripcion_registro_civil").label),
      }),
      servedDates[1]!,
    );
    await choose("tutela");
    await waitFor(() =>
      expect(askedIn(node)).not.toContain("inscripcion_registro_civil"),
    );
    const save = dialog.getByRole("button", {
      name: t("desktop.profile.save"),
    });
    await waitFor(() => expect(save).toBeEnabled());
    await userEvent.click(save);
    await waitFor(() => expect(sentEdits()).toHaveLength(1));
    expect(sentEdits()[0]).toEqual({
      kind: "descendants",
      add_row: {
        facts: [
          { field_key: "birth_date", value: servedDates[0]! },
          { field_key: "relacion", value: "tutela" },
        ],
      },
    });
  },
};

export const InvalidDraftRefused: Story = {
  name: "Invalid draft: the refusal is shown in the product's words, Save waits, and the next answer reads again",
  render: (_, { globals }) => (
    <Element scenario="unknown" locale={language(globals)} refuseDraft />
  ),
  play: async ({ canvasElement, globals }) => {
    const locale = language(globals);
    const t = translator(locale);
    const node = await openNewDescendant(canvasElement, "unknown", locale);
    const dialog = within(node);
    const served = servedGroup("unknown", locale, 0);
    const relation = served.leaves!.find((entry) => entry.leaf === "relacion")!;
    const choose = (value: string) =>
      userEvent.selectOptions(
        dialog.getByRole("combobox", { name: relation.label }),
        relation.choices.find((entry) => entry.value === value)!.label,
      );
    await userEvent.type(
      dialog.getByRole("textbox", {
        name: new RegExp(servedLabel("unknown", locale, 0, "birth_date")),
      }),
      servedDates[0]!,
    );
    // The sentence is the one the draft read was refused with, in the
    // existing refusal alert; every required answer is given, so only the
    // refused read holds Save.
    const refusal = await within(document.body).findByRole("alert");
    expect(refusal).toHaveAttribute("data-household-refusal");
    expect(refusal.textContent ?? "").not.toBe("");
    const save = dialog.getByRole("button", {
      name: t("desktop.profile.save"),
    });
    expect(save).toBeDisabled();
    // The next answer asks the product again; its answer clears the refusal.
    await choose("tutela");
    await waitFor(() =>
      expect(node.querySelector("[data-household-refusal]")).toBeNull(),
    );
    await waitFor(() => expect(save).toBeEnabled());
    expect(window.__scenarioHousehold!.drafts()).toHaveLength(2);
  },
};

export const AddsAPerson: Story = {
  name: "Added: one person is sent through the served add control and the household is read again",
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
        name: addWords("unknown", locale, 1),
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
    expect(
      within(canvasElement).getByText(t("desktop.profile.household.saved")),
    ).toBeTruthy();
    // Only the person added was sent, and the other group states nothing
    // more than it did.
    expect(sentEdits()).toEqual([
      {
        kind: "ascendants",
        add_row: { facts: [{ field_key: "birth_date", value: "1950-02-03" }] },
      },
    ]);
    expect(
      canvasElement.querySelector(
        "[data-household-group='renta_family.descendiente']",
      ),
    ).toHaveAttribute("data-household-state", "unknown");
  },
};

export const RemovesAPerson: Story = {
  name: "Removed: one person is named by its served index and the household is read again",
  render: (_, { globals }) => (
    <Element scenario="rows" locale={language(globals)} />
  ),
  play: async ({ canvasElement, globals }) => {
    const locale = language(globals);
    const t = translator(locale);
    const shown = await groups(canvasElement);
    const ascendants = shown[1]!;
    const first = ascendants.element.querySelector<HTMLElement>(
      "[data-household-person]",
    )!;
    const index = first.getAttribute("data-household-person")!;
    await userEvent.click(
      within(first).getByRole("button", {
        name: removeWords("rows", locale, 1),
      }),
    );
    const dialog = within(await within(document.body).findByRole("dialog"));
    await userEvent.click(
      dialog.getByRole("button", { name: removeWords("rows", locale, 1) }),
    );
    await waitFor(() =>
      expect(
        canvasElement.querySelectorAll(
          "[data-household-group='renta_family.ascendiente'] [data-household-person]",
        ),
      ).toHaveLength(1),
    );
    expect(
      within(canvasElement).getByText(t("desktop.profile.household.saved")),
    ).toBeTruthy();
    expect(sentEdits()).toEqual([
      { kind: "ascendants", remove_row_index: index },
    ]);
  },
};

export const RefusedAdd: Story = {
  name: "Refused: adding a person is refused in the application's own sentence, and what was typed stays",
  render: (_, { globals }) => (
    <Element
      scenario="masked"
      locale={language(globals)}
      refuse="ascendants_second_nif_invalid"
    />
  ),
  play: async ({ canvasElement, globals }) => {
    const locale = language(globals);
    const t = translator(locale);
    const shown = await groups(canvasElement);
    await userEvent.click(
      within(shown[1]!.element).getByRole("button", {
        name: addWords("masked", locale, 1),
      }),
    );
    const dialog = within(await within(document.body).findByRole("dialog"));
    const born = dialog.getByRole("textbox", {
      name: new RegExp(servedLabel("masked", locale, 1, "birth_date")),
    });
    await userEvent.type(born, "1950-02-03");
    await userEvent.tab();
    await userEvent.click(
      dialog.getByRole("button", { name: t("desktop.profile.save") }),
    );
    const refusal = await within(document.body).findByRole("alert");
    const words = (
      fixtures.refusals.ascendants_second_nif_invalid as Record<
        string,
        { refusal_words: string }
      >
    )[locale]!.refusal_words;
    expect(refusal.textContent).toBe(words);
    // The person typed stays for another try, and nothing was stored.
    expect(within(document.body).getByRole("dialog")).toBeTruthy();
    expect(born.isConnected).toBe(true);
    expect(
      shown[1]!.element.querySelectorAll("[data-household-person]"),
    ).toHaveLength(1);
  },
};

export const RefusedWrite: Story = {
  name: "Refused edit: the application's own sentence, the person kept in the dialog",
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
  name: "Unknown outcome: a removal that may have landed keeps writes closed until the person refreshes",
  render: (_, { globals }) => (
    <Element scenario="rows" locale={language(globals)} lose />
  ),
  play: async ({ canvasElement, globals }) => {
    const locale = language(globals);
    const t = translator(locale);
    const shown = await groups(canvasElement);
    await userEvent.click(
      within(shown[1]!.element).getAllByRole("button", {
        name: removeWords("rows", locale, 1),
      })[0]!,
    );
    const dialog = within(await within(document.body).findByRole("dialog"));
    await userEvent.click(
      dialog.getByRole("button", { name: removeWords("rows", locale, 1) }),
    );
    await waitFor(() =>
      expect(
        within(canvasElement).getByRole("button", {
          name: t("desktop.profile.refresh"),
        }),
      ).toBeEnabled(),
    );
    // Neither landed nor refused: the product's outcome is not known.
    expect(
      canvasElement.querySelector("[data-household-failure]")!.textContent,
    ).toBe(t("desktop.profile.unknown"));
    for (const add of canvasElement.querySelectorAll("[data-household-add]"))
      expect(add).toBeDisabled();
    for (const remove of canvasElement.querySelectorAll(
      "[data-household-remove]",
    ))
      expect(remove).toBeDisabled();
  },
};

/** Removes the first ascendant of the "rows" scenario with an answer that is
 * lost, and waits for the unknown outcome to be told. */
async function loseARemoval(
  canvasElement: HTMLElement,
  locale: string,
  refreshName: string,
) {
  const shown = await groups(canvasElement);
  await userEvent.click(
    within(shown[1]!.element).getAllByRole("button", {
      name: removeWords("rows", locale, 1),
    })[0]!,
  );
  const dialog = within(await within(document.body).findByRole("dialog"));
  await userEvent.click(
    dialog.getByRole("button", { name: removeWords("rows", locale, 1) }),
  );
  await waitFor(() =>
    expect(
      within(canvasElement).getByRole("button", { name: refreshName }),
    ).toBeEnabled(),
  );
}

export const UnknownOutcomeRead: Story = {
  name: "Unknown outcome read again: a successful read clears the notice and opens the controls",
  render: (_, { globals }) => (
    <Element scenario="rows" locale={language(globals)} lose />
  ),
  play: async ({ canvasElement, globals }) => {
    const locale = language(globals);
    const t = translator(locale);
    const refresh = t("desktop.profile.refresh");
    await loseARemoval(canvasElement, locale, refresh);
    expect(
      canvasElement.querySelector("[data-household-failure]")!.textContent,
    ).toBe(t("desktop.profile.unknown"));
    await userEvent.click(
      within(canvasElement).getByRole("button", { name: refresh }),
    );
    await waitFor(() =>
      expect(
        canvasElement.querySelector("[data-household-failure]"),
      ).toBeNull(),
    );
    expect(
      within(canvasElement).queryByRole("button", { name: refresh }),
    ).toBeNull();
    for (const add of canvasElement.querySelectorAll("[data-household-add]"))
      expect(add).toBeEnabled();
  },
};

export const UnknownOutcomeReadFails: Story = {
  name: "Unknown outcome, read fails: the notice and the closed controls stay",
  render: (_, { globals }) => (
    <Element scenario="rows" locale={language(globals)} lose />
  ),
  play: async ({ canvasElement, globals }) => {
    const locale = language(globals);
    const t = translator(locale);
    const refresh = t("desktop.profile.refresh");
    await loseARemoval(canvasElement, locale, refresh);
    readsFail = true;
    await userEvent.click(
      within(canvasElement).getByRole("button", { name: refresh }),
    );
    // Give the failed read time to settle, then see nothing was cleared.
    await new Promise((done) => setTimeout(done, 200));
    expect(
      canvasElement.querySelector("[data-household-failure]")!.textContent,
    ).toBe(t("desktop.profile.unknown"));
    expect(
      within(canvasElement).getByRole("button", { name: refresh }),
    ).toBeEnabled();
    for (const add of canvasElement.querySelectorAll("[data-household-add]"))
      expect(add).toBeDisabled();
    readsFail = false;
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
