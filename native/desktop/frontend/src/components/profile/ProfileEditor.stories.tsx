import type { Meta, StoryObj } from "@storybook/react-vite";
import type { ComponentProps } from "react";
import { expect, screen, userEvent, waitFor } from "storybook/test";
import profiles from "@fixtures/desktop-profile/userProfile.json" with { type: "json" };
import type {
  ProfileField,
  ProfileSection,
  UserProfile,
} from "../../shell/userProfile";
import { translator } from "../../shell/strings";
import { ProfileEditor, type ProfileDraft } from "./ProfileEditor";
import { fixtureDay } from "@/dev/fixtureDates";

// Appearance and entry only: a made-up activity entry with a detail of each
// kind the profile edits. Each detail is the profile's own, worded as the
// backend serves it in the window's language. Saving does nothing here.

const ROW = "main";

type Served = Record<string, UserProfile>;

/** The detail the profile serves at `source`, in `locale`, held at `value` as
 * an entry of the activities row, or as a lone detail where `row` is false. */
const detail = (
  locale: string,
  source: string,
  key: string,
  value: string | null,
  { row = true }: { row?: boolean } = {},
): ProfileField => {
  const served = (profiles as unknown as Served)[locale] ?? profiles.en;
  const found = served.sections
    .flatMap((section) => section.fields)
    .find((field) => field.path === source);
  if (!found) throw new Error(`the profile serves no detail ${source}`);
  return {
    ...found,
    path: row ? `activities.${ROW}.${key}` : source,
    value,
    row_index: row ? ROW : null,
  };
};

/** One detail of each kind, and a masked one, as an activities entry holds. */
const fieldsIn = (locale: string): ProfileField[] => {
  const regime = detail(locale, "auth.provider", "regime", null);
  return [
    detail(locale, "activities.description", "description", "Carpentry"),
    detail(locale, "identity.email", "contact_email", "taller@example.com"),
    detail(
      locale,
      "censo.activity_start_date",
      "start_date",
      fixtureDay(3, 15),
    ),
    detail(locale, "irpf.pagadores_count", "employees", "4"),
    detail(
      locale,
      "taxpayer_type.tributacion_estado_porcentaje",
      "weekly_hours",
      "37.5",
    ),
    detail(
      locale,
      "attribution_entity_socios.reduccion",
      "annual_income",
      "12500.5",
    ),
    { ...regime, value: regime.choices[0]?.value ?? null },
    detail(locale, "auth.numero_soporte", "access_code", null),
  ];
};

const sectionIn = (locale: string, fields: ProfileField[]): ProfileSection => ({
  ...((profiles as unknown as Served)[locale] ?? profiles.en).sections.find(
    (section) => section.key === "activities",
  )!,
  fields,
});

const baseIn = (section: ProfileSection): UserProfile => ({
  profile_id: "story",
  record_revision: 1,
  content_digest: "0".repeat(64),
  setup_state: "complete",
  valid: true,
  sections: [section],
  missing_required: [],
  notices: [],
  pages: 1,
});

type Args = Omit<ComponentProps<typeof ProfileEditor>, "draft"> & {
  /** What the editor opens for. */
  kind: ProfileDraft["kind"];
  /** Only the start date, where the story is about that one detail. */
  startDateOnly?: boolean;
  /** Only the detail the profile serves at this path, as a lone detail. */
  onlyPath?: string;
};

const draftOf = (
  {
    kind,
    startDateOnly,
    onlyPath,
  }: Pick<Args, "kind" | "startDateOnly" | "onlyPath">,
  locale: string,
): ProfileDraft => {
  const fields = onlyPath
    ? [detail(locale, onlyPath, "choice", null, { row: false })]
    : startDateOnly
      ? [
          detail(
            locale,
            "censo.activity_start_date",
            "start_date",
            fixtureDay(3, 15),
            {
              row: false,
            },
          ),
        ]
      : fieldsIn(locale);
  const section = sectionIn(locale, fields);
  return { base: baseIn(section), fields, section, kind };
};

const meta = {
  title: "Shell/Profile/Profile editor",
  render: ({ kind, startDateOnly, onlyPath, ...args }, { globals }) => (
    <ProfileEditor
      {...args}
      draft={draftOf(
        { kind, startDateOnly, onlyPath },
        String(globals.locale ?? "en"),
      )}
    />
  ),
  parameters: { surface: "chrome" },
  args: {
    kind: "update_row",
    busy: false,
    changed: false,
    blocked: false,
    error: null,
    onRefresh: () => undefined,
    onSave: async () => false,
    onClose: () => undefined,
  },
} satisfies Meta<Args>;
export default meta;
type Story = StoryObj<typeof meta>;

export const Entry: Story = { name: "An entry of every kind" };

export const NewEntry: Story = {
  name: "A new entry",
  args: { kind: "add_row" },
};

export const SingleDate: Story = {
  name: "One date",
  args: { kind: "field", startDateOnly: true },
};

export const UnfinishedDate: Story = {
  name: "A date left unfinished",
  args: { kind: "field", startDateOnly: true },
  play: async ({ globals }) => {
    const locale = String(globals.locale ?? "en");
    const date = detail(
      locale,
      "censo.activity_start_date",
      "start_date",
      null,
    );
    const field = await screen.findByRole("textbox", { name: date.label });
    await userEvent.clear(field);
    await userEvent.type(field, "15/03");
    await userEvent.click(
      screen.getByRole("button", {
        name: translator(locale)("desktop.profile.save"),
      }),
    );
    await waitFor(() => screen.getByRole("alert"));
  },
};

export const ServedChoices: Story = {
  name: "A detail the profile serves as a choice: the declaration type, its answers as served",
  args: { kind: "field", onlyPath: "renta_filing.declaration_type" },
  play: async ({ globals }) => {
    const locale = String(globals.locale ?? "en");
    const served = detail(
      locale,
      "renta_filing.declaration_type",
      "choice",
      null,
      { row: false },
    );
    // The profile serves the answers; the editor offers exactly those.
    if (served.choices.length === 0)
      throw new Error("the profile serves no answers for the declaration type");
    const offered = (await screen.findAllByRole("option")).map(
      (option) => option.textContent,
    );
    for (const choice of served.choices)
      expect(offered).toContain(choice.label);
  },
};

export const Busy: Story = { args: { busy: true } };

export const Conflict: Story = { args: { changed: true } };
