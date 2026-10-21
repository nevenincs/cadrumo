import type { Meta, StoryObj } from "@storybook/react-vite";
import { AgentWelcome } from "./AgentWelcome";
import { APPEARANCE_NOTE } from "./Composer.stories";
import { DropOverlay } from "./DropOverlay";

// Appearance only: the overlay in each of its states over an empty column.
// No drag is watched and no file is taken.

type Args = { armed: boolean; fileCount?: number };

const ACCEPTED = ["PDF", "JPG", "PNG", "HEIC", "XLSX", "CSV", "XML", "ZIP"];

const meta = {
  title: "Shell/Agent/Drop overlay",
  parameters: {
    fill: true,
    docs: { description: { component: APPEARANCE_NOTE } },
  },
  args: { armed: false, fileCount: 3 },
  render: (args: Args, { globals }) => (
    <div className="relative flex h-dvh w-(--agent-w) flex-col border-r bg-background">
      <p className="px-4 pt-4 text-xs text-faint">{APPEARANCE_NOTE}</p>
      <AgentWelcome />
      <DropOverlay
        visible
        armed={args.armed}
        fileCount={args.fileCount}
        acceptedTypes={ACCEPTED}
        locale={String(globals.locale)}
      />
    </div>
  ),
} satisfies Meta<Args>;
export default meta;
type Story = StoryObj<typeof meta>;

export const Idle: Story = { name: "Idle: hold Shift" };

export const Armed: Story = {
  name: "Armed: release to add",
  args: { armed: true },
};

export const ArmedOneFile: Story = {
  name: "Armed: one file",
  args: { armed: true, fileCount: 1 },
};

export const ArmedCountUnknown: Story = {
  name: "Armed: count not known",
  args: { armed: true, fileCount: undefined },
};
