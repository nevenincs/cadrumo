import type { Meta, StoryObj } from "@storybook/react-vite";
import type { ComponentProps } from "react";
import { userEvent } from "storybook/test";
import { APPEARANCE_NOTE, NOOP } from "./Composer.stories";
import { HistoryList } from "./HistoryList";
import { conversationGroups } from "../../shell/agentViews";
import type { AgentConversationRecord } from "../../shell/agentViews";
import type { ConversationGroup } from "./types";
import { fixtureInstant } from "@/dev/fixtureDates";

// Appearance only: fixed conversations under fixed headings. Archive,
// Restore and Delete do nothing here; the confirmation is opened by the
// story's own press.

// The conversations as the service lists them, grouped and worded by the same
// function the column uses, so headings and "ago" labels follow the language
// shown. The clock is fixed: the specimen never moves.
const NOW = new Date(fixtureInstant(10, 30, "12:00:00"));
const HOURS = 3_600_000;
const DAYS = 24 * HOURS;
const conversation = (
  id: string,
  title: string,
  before: number,
  archived = false,
): AgentConversationRecord => ({
  id,
  title,
  last_active_at: new Date(NOW.getTime() - before).toISOString(),
  archived,
});

const RECORDS: readonly AgentConversationRecord[] = [
  conversation("c1", "IVA del tercer trimestre", 2 * HOURS),
  conversation("c2", "Facturas de septiembre sin clasificar", 5 * HOURS),
  conversation("c3", "Plazo del modelo 130", 30 * HOURS),
  conversation(
    "c4",
    "Gastos deducibles del vehículo y kilometraje del segundo semestre",
    6 * DAYS,
  ),
  conversation("c5", "Retenciones de alquiler", 35 * DAYS),
  conversation("x1", "Renta 2025", 120 * DAYS, true),
  conversation("x2", "Alta en el censo", 210 * DAYS, true),
];
const DOCUMENT_COUNTS: Readonly<Record<string, number>> = {
  c1: 4,
  c2: 23,
  c3: 0,
  c4: 2,
  c5: 1,
  x1: 9,
  x2: 0,
};

/** The history's groups in a language, active or archived. */
export const historyGroups = (
  locale: string,
  archived = false,
): ConversationGroup[] =>
  conversationGroups(RECORDS, {
    locale,
    archived,
    currentId: "c1",
    untitled: "",
    now: NOW,
    documentCounts: DOCUMENT_COUNTS,
  });

// The groups come from the language shown, so a story says only whether the
// history has any.
type Args = Omit<ComponentProps<typeof HistoryList>, "groups"> & {
  empty?: boolean;
};

const meta = {
  title: "Shell/Agent/History list",
  excludeStories: /^(?:[A-Z][A-Z_]*|historyGroups)$/,
  parameters: {
    fill: true,
    docs: { description: { component: APPEARANCE_NOTE } },
  },
  args: {
    archivedCount: 2,
    onToggleArchived: NOOP,
    onOpen: NOOP,
    onArchive: NOOP,
    onRestore: NOOP,
    onDelete: NOOP,
  },
  render: ({ empty, ...args }: Args, { globals }) => (
    <div className="flex h-dvh w-(--agent-w) flex-col border-r bg-background">
      <p className="px-3 pt-3 text-xs text-faint">{APPEARANCE_NOTE}</p>
      <HistoryList
        {...args}
        groups={
          empty
            ? []
            : historyGroups(String(globals.locale), args.viewingArchived)
        }
      />
    </div>
  ),
} satisfies Meta<Args>;
export default meta;
type Story = StoryObj<typeof meta>;

export const Grouped: Story = {};

export const DeleteConfirmation: Story = {
  name: "Delete confirmation open",
  play: async ({ canvasElement }) => {
    const remove = canvasElement.querySelector<HTMLElement>(
      "[data-delete-for=c2]",
    );
    if (remove) await userEvent.click(remove);
  },
};

export const Archived: Story = {
  name: "Archived view",
  args: { viewingArchived: true },
};

export const Empty: Story = {
  args: { empty: true, archivedCount: 0 },
};

export const NoSearchResults: Story = {
  play: async ({ canvasElement }) => {
    const search =
      canvasElement.querySelector<HTMLElement>("input[type=search]");
    if (search) await userEvent.type(search, "modelo 720");
  },
};

export const EveryActionUnavailable: Story = {
  args: {
    onToggleArchived: undefined,
    onOpen: undefined,
    onArchive: undefined,
    onRestore: undefined,
    onDelete: undefined,
  },
};
