import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState } from "react";
import { Specimen } from "@/dev/catalogue/Frame";
import { ResizablePane, type PaneEdge } from "./resizable-pane";

const meta = {
  title: "Primitives/Resizable pane",
} satisfies Meta;
export default meta;
type Story = StoryObj<typeof meta>;

const REM = 16;

function Pane({ edge }: { edge: PaneEdge }) {
  const [size, setSize] = useState<number | null>(null);
  const across = edge === "top" || edge === "bottom";
  const leads = edge === "start" || edge === "top";
  const pane = (
    <ResizablePane
      edge={edge}
      aria-label={`${edge} pane`}
      handleLabel={`Resize the ${edge} pane`}
      size={size}
      onSize={setSize}
      defaultSize={(across ? 6 : 12) * REM}
      min={(across ? 4 : 8) * REM}
      max={(across ? 12 : 20) * REM}
      maxShare={0.5}
      className="bg-chrome p-3 text-sm"
    >
      {size === null ? "default size" : `${size} px`}
    </ResizablePane>
  );
  return (
    <div
      className={`flex h-72 w-full min-w-0 rounded-md border border-border ${across ? "flex-col" : "flex-row"}`}
    >
      {leads && pane}
      <div className="min-h-0 min-w-0 flex-1 p-3 text-sm text-muted-foreground">
        The area beside the pane keeps at least half of the box.
      </div>
      {!leads && pane}
    </div>
  );
}

export const Edges: Story = {
  render: () => (
    <div>
      <Specimen
        className="flex-col items-stretch"
        title="At the start, at the end, above, under"
        note="Drag the line, or focus it: arrow keys move it, Home and End go to the least and the most, Enter or a double click returns the default."
      >
        <Pane edge="start" />
        <Pane edge="end" />
        <Pane edge="top" />
        <Pane edge="bottom" />
      </Specimen>
    </div>
  ),
};
