import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState, type ReactNode } from "react";
import { Specimen } from "@/dev/catalogue/Frame";
import type { Chord } from "@/shell/actions";
import { Button } from "./button";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuShortcut,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "./dropdown-menu";
import { Icon } from "./icon";

// Appearance only: each menu is held open so it can be seen; choosing an item
// changes nothing but the choices that are shown.

// The chords the action registry binds for these actions.
const SETTINGS: Chord = { mod: true, code: "Comma", key: ",", scope: "app" };
const PALETTE: Chord = { mod: true, code: "KeyK", key: "K", scope: "app" };
const ZOOM_IN: Chord = { mod: true, code: "Equal", key: "=", scope: "docs" };
const ZOOM_OUT: Chord = { mod: true, code: "Minus", key: "-", scope: "docs" };
const ZOOM_RESET: Chord = {
  mod: true,
  code: "Digit0",
  key: "0",
  scope: "docs",
};
const DOCS_BACK: Chord = {
  alt: true,
  code: "ArrowLeft",
  key: "←",
  scope: "docs",
};
const TUI: Chord = {
  mod: true,
  shift: true,
  code: "KeyT",
  key: "T",
  scope: "global",
};

const meta = {
  title: "Primitives/Menu",
  parameters: { surface: "chrome" },
} satisfies Meta;
export default meta;
type Story = StoryObj<typeof meta>;

/** A menu held open under its trigger, with room below for it to draw. */
function Open({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="h-80 w-72">
      <DropdownMenu open modal={false}>
        <DropdownMenuTrigger asChild>
          <Button variant="outline">
            {label}
            <Icon name="chevronDown" size="xs" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start">{children}</DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}

export const IconsAndShortcuts: Story = {
  name: "Icons and shortcuts",
  render: () => (
    <Specimen
      title="Items"
      note="An icon leads the label; a chord is shown in the platform's notation, from the same declaration the keymap binds. A disabled item stays in place."
    >
      <Open label="View">
        <DropdownMenuLabel>Window</DropdownMenuLabel>
        <DropdownMenuItem icon="search">
          Search
          <DropdownMenuShortcut chord={PALETTE} />
        </DropdownMenuItem>
        <DropdownMenuItem icon="back">
          Back
          <DropdownMenuShortcut chord={DOCS_BACK} />
        </DropdownMenuItem>
        <DropdownMenuItem icon="tui">
          Show the TUI
          <DropdownMenuShortcut chord={TUI} />
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem icon="zoomIn">
          Zoom in
          <DropdownMenuShortcut chord={ZOOM_IN} />
        </DropdownMenuItem>
        <DropdownMenuItem icon="zoomOut">
          Zoom out
          <DropdownMenuShortcut chord={ZOOM_OUT} />
        </DropdownMenuItem>
        <DropdownMenuItem icon="reset" disabled>
          Actual size
          <DropdownMenuShortcut chord={ZOOM_RESET} />
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem icon="settings">
          Settings
          <DropdownMenuShortcut chord={SETTINGS} />
        </DropdownMenuItem>
      </Open>
    </Specimen>
  ),
};

export const Alignment: Story = {
  render: () => (
    <div>
      <Specimen
        title="Some items with an icon"
        note="An item without one keeps the icon's column, so the labels line up."
      >
        <Open label="Row">
          <DropdownMenuItem icon="copy">
            Copy
            <DropdownMenuShortcut>Ctrl+C</DropdownMenuShortcut>
          </DropdownMenuItem>
          <DropdownMenuItem>Copy as text</DropdownMenuItem>
          <DropdownMenuItem icon="download">Export</DropdownMenuItem>
          <DropdownMenuItem>Export all…</DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem icon="trash">Remove</DropdownMenuItem>
        </Open>
      </Specimen>
      <Specimen
        title="No icons"
        note="A menu none of whose items has one takes no column."
      >
        <Open label="Sort">
          <DropdownMenuItem>Date</DropdownMenuItem>
          <DropdownMenuItem>Amount</DropdownMenuItem>
          <DropdownMenuItem>Counterparty</DropdownMenuItem>
        </Open>
      </Specimen>
    </div>
  ),
};

function Choices() {
  const [hidden, setHidden] = useState(false);
  const [sealed, setSealed] = useState(true);
  const [by, setBy] = useState("date");
  return (
    <Open label="Ledger">
      <DropdownMenuGroup label="Show">
        <DropdownMenuCheckboxItem checked={hidden} onCheckedChange={setHidden}>
          Hide rejected
        </DropdownMenuCheckboxItem>
        <DropdownMenuCheckboxItem checked={sealed} onCheckedChange={setSealed}>
          Sealed periods
        </DropdownMenuCheckboxItem>
      </DropdownMenuGroup>
      <DropdownMenuSeparator />
      <DropdownMenuGroup label="Sort by">
        <DropdownMenuRadioGroup value={by} onValueChange={setBy}>
          <DropdownMenuRadioItem value="date">Date</DropdownMenuRadioItem>
          <DropdownMenuRadioItem value="amount">Amount</DropdownMenuRadioItem>
          <DropdownMenuRadioItem value="party" disabled>
            Counterparty
            <DropdownMenuShortcut>Waits</DropdownMenuShortcut>
          </DropdownMenuRadioItem>
        </DropdownMenuRadioGroup>
      </DropdownMenuGroup>
      <DropdownMenuSeparator />
      <DropdownMenuSub defaultOpen>
        <DropdownMenuSubTrigger icon="download">Export</DropdownMenuSubTrigger>
        <DropdownMenuSubContent>
          <DropdownMenuItem icon="download">Visible rows</DropdownMenuItem>
          <DropdownMenuItem icon="downloadAll">All rows</DropdownMenuItem>
        </DropdownMenuSubContent>
      </DropdownMenuSub>
      <DropdownMenuItem>Fold all</DropdownMenuItem>
    </Open>
  );
}

export const ChoicesAndSubmenu: Story = {
  name: "Choices and submenu",
  render: () => (
    <Specimen
      title="Checkbox, radio and submenu"
      note="A choice keeps the menu open; its mark takes the icon column, so plain items beside it keep the column too. The right arrow opens a submenu, the left closes it."
    >
      <Choices />
    </Specimen>
  ),
};
