import type { Meta, StoryObj } from "@storybook/react-vite";
import type { ReactNode } from "react";
import {
  DataGridHarness,
  DataTableHarness,
} from "@/dev/primitives/DataGridHarness";

const meta = {
  title: "Primitives/Data grid",
  parameters: { fill: true },
} satisfies Meta;
export default meta;
type Story = StoryObj<typeof meta>;

const Frame = ({ children }: { children: ReactNode }) => (
  <div className="flex h-dvh min-h-0 flex-col p-4">{children}</div>
);

/** Made-up movements: arrows move, Space selects, Enter or a typed key
 * edits, Shift and the arrows draw a range, ArrowUp from the first row
 * reaches the headers. */
export const Grid: Story = {
  render: () => (
    <Frame>
      <DataGridHarness count={200} />
    </Frame>
  ),
};

/** The same rows under month sections that fold with Left, Right or Enter. */
export const Sections: Story = {
  render: () => (
    <Frame>
      <DataGridHarness count={120} grouped />
    </Frame>
  ),
};

/** Ten thousand rows: only those in view are drawn. */
export const Windowed: Story = {
  render: () => (
    <Frame>
      <DataGridHarness count={10000} />
    </Frame>
  ),
};

export const Empty: Story = {
  render: () => (
    <Frame>
      <DataGridHarness count={0} />
    </Frame>
  ),
};

/** The plain table: sortable headers, sections as row groups, one row open
 * elsewhere, rows opened with Enter or a click. */
export const PlainTable: Story = {
  parameters: { fill: false },
  render: () => <DataTableHarness />,
};
