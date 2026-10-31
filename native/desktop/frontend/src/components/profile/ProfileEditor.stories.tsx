import type { Meta, StoryObj } from "@storybook/react-vite";
import { screen, userEvent, waitFor } from "storybook/test";
import type {
  ProfileField,
  ProfileSection,
  UserProfile,
} from "../../shell/userProfile";
import { ProfileEditor, type ProfileDraft } from "./ProfileEditor";

// Appearance and entry only: a made-up activity entry with a detail of each
// kind the profile edits. Saving does nothing here.

const ROW = "main";

const detail = (
  key: string,
  label: string,
  field_type: string,
  value: string | null,
  extra: Partial<ProfileField> = {},
): ProfileField => ({
  path: `activities.${ROW}.${key}`,
  label,
  value,
  masked: false,
  required: false,
  field_type,
  choices: [],
  help: null,
  about: "",
  row_index: ROW,
  ...extra,
});

const FIELDS: ProfileField[] = [
  detail("description", "Activity", "string", "Carpentry", { required: true }),
  detail("contact_email", "Contact email", "email", "taller@example.com"),
  detail("start_date", "Start date", "date", "2026-03-15"),
  detail("employees", "Employees", "integer", "4"),
  detail("weekly_hours", "Weekly hours", "decimal", "37.5"),
  detail("annual_income", "Annual income", "money", "12500.5"),
  detail("regime", "Regime", "enum", "simplified", {
    choices: [
      { value: "simplified", label: "Simplified" },
      { value: "normal", label: "Normal" },
    ],
  }),
  detail("access_code", "Access code", "string", null, { masked: true }),
];

const SECTION: ProfileSection = {
  key: "activities",
  title: "Activities",
  summary: "",
  repeatable: true,
  fields: FIELDS,
};

const BASE: UserProfile = {
  profile_id: "story",
  record_revision: 1,
  content_digest: "0".repeat(64),
  setup_state: "complete",
  valid: true,
  sections: [SECTION],
  missing_required: [],
  notices: [],
  pages: 1,
};

const draft = (kind: ProfileDraft["kind"], fields = FIELDS): ProfileDraft => ({
  base: BASE,
  fields,
  section: SECTION,
  kind,
});

const meta = {
  title: "Shell/Profile/Profile editor",
  component: ProfileEditor,
  parameters: { surface: "chrome" },
  args: {
    draft: draft("update_row"),
    busy: false,
    changed: false,
    blocked: false,
    error: null,
    onRefresh: () => undefined,
    onSave: async () => false,
    onClose: () => undefined,
  },
} satisfies Meta<typeof ProfileEditor>;
export default meta;
type Story = StoryObj<typeof meta>;

export const Entry: Story = { name: "An entry of every kind" };

export const NewEntry: Story = {
  name: "A new entry",
  args: { draft: draft("add_row") },
};

export const SingleDate: Story = {
  name: "One date",
  args: {
    draft: draft("field", [
      detail("start_date", "Start date", "date", "2026-03-15"),
    ]),
  },
};

export const UnfinishedDate: Story = {
  name: "A date left unfinished",
  args: {
    draft: draft("field", [
      detail("start_date", "Start date", "date", "2026-03-15"),
    ]),
  },
  play: async () => {
    const field = await screen.findByRole("textbox", { name: "Start date" });
    await userEvent.clear(field);
    await userEvent.type(field, "15/03");
    await userEvent.click(screen.getByRole("button", { name: /^save$/i }));
    await waitFor(() => screen.getByRole("alert"));
  },
};

export const Busy: Story = { args: { busy: true } };

export const Conflict: Story = { args: { changed: true } };
