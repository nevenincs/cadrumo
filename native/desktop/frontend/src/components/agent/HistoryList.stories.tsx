import type { Meta, StoryObj } from "@storybook/react-vite";
import type { ComponentProps } from "react";
import { userEvent } from "storybook/test";
import { APPEARANCE_NOTE, NOOP } from "./Composer.stories";
import { HistoryList } from "./HistoryList";
import type { ConversationGroup } from "./types";

// Appearance only: fixed conversations under fixed headings. Archive,
// Restore and Delete do nothing here; the confirmation is opened by the
// story's own press.

export const ACTIVE_GROUPS: ConversationGroup[] = [
  {
    heading: "Today",
    conversations: [
      {
        id: "c1",
        title: "IVA del tercer trimestre",
        lastActivityLabel: "2 hours ago",
        documentCount: 4,
        archived: false,
        current: true,
      },
      {
        id: "c2",
        title: "Facturas de septiembre sin clasificar",
        lastActivityLabel: "5 hours ago",
        documentCount: 23,
        archived: false,
      },
    ],
  },
  {
    heading: "Previous 7 days",
    conversations: [
      {
        id: "c3",
        title: "Plazo del modelo 130",
        lastActivityLabel: "3 days ago",
        documentCount: 0,
        archived: false,
      },
      {
        id: "c4",
        title:
          "Gastos deducibles del vehículo y kilometraje del segundo semestre",
        lastActivityLabel: "6 days ago",
        documentCount: 2,
        archived: false,
      },
    ],
  },
  {
    heading: "Earlier",
    conversations: [
      {
        id: "c5",
        title: "Retenciones de alquiler",
        lastActivityLabel: "5 weeks ago",
        documentCount: 1,
        archived: false,
      },
    ],
  },
];

const ARCHIVED_GROUPS: ConversationGroup[] = [
  {
    heading: "Earlier",
    conversations: [
      {
        id: "x1",
        title: "Renta 2025",
        lastActivityLabel: "4 months ago",
        documentCount: 9,
        archived: true,
      },
      {
        id: "x2",
        title: "Alta en el censo",
        lastActivityLabel: "7 months ago",
        documentCount: 0,
        archived: true,
      },
    ],
  },
];

type Args = ComponentProps<typeof HistoryList>;

const meta = {
  title: "Shell/Agent/History list",
  excludeStories: /^[A-Z][A-Z_]*$/,
  parameters: {
    fill: true,
    docs: { description: { component: APPEARANCE_NOTE } },
  },
  args: {
    groups: ACTIVE_GROUPS,
    archivedCount: 2,
    onToggleArchived: NOOP,
    onOpen: NOOP,
    onArchive: NOOP,
    onRestore: NOOP,
    onDelete: NOOP,
  },
  render: (args: Args) => (
    <div className="flex h-dvh w-(--agent-w) flex-col border-r bg-background">
      <p className="px-3 pt-3 text-xs text-faint">{APPEARANCE_NOTE}</p>
      <HistoryList {...args} />
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
  args: { groups: ARCHIVED_GROUPS, viewingArchived: true },
};

export const Empty: Story = {
  args: { groups: [], archivedCount: 0 },
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
