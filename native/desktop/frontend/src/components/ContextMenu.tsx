import { useRef, useState } from "react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuShortcut,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { IconName } from "@/components/ui/icon";
import type { ChordKeys } from "@/shared/chords";

/** Where a menu opens: a point, or with a height the edge of a row, which the
 * menu then opens under or over and never across. */
export type MenuAnchor = { x: number; y: number; height?: number };

/** One choice of a menu. */
export type MenuAction = {
  /** What `choose` is given when this item is chosen. */
  id: string;
  label: string;
  /** A disabled item is shown but can never be chosen. */
  enabled: boolean;
  icon?: IconName;
  /** The chord that does the same, taken from the declaration that binds it,
   * the registry's or the page's own, so that a shortcut shown is one a key
   * runs. */
  chord?: ChordKeys;
  /** What choosing it does, for a menu that settles its choice by id. */
  run?: () => void;
};

export type MenuSeparator = { separator: true };

export type MenuEntry = MenuAction | MenuSeparator;

/** Opens a menu at the anchor. */
export type OpenMenu = (items: MenuEntry[], at: MenuAnchor) => void;

// The shell's own drawing of every context menu, the same in the desktop
// application and the browser. It opens at a point, not from a control, so
// its anchor is an empty element placed there.
export function ContextMenu({
  label,
  items,
  at,
  choose,
}: {
  /** The menu's accessible name: it has no visible control to take one from. */
  label: string;
  items: MenuEntry[];
  at: MenuAnchor;
  choose: (id: string | null) => void;
}) {
  // Focus goes back where the menu came from, whichever way it is settled.
  const [returnTo] = useState(() => document.activeElement);
  // A press elsewhere closes the menu and keeps what it pressed: focus is
  // not taken back from it.
  const pressedElsewhere = useRef(false);
  return (
    <DropdownMenu
      open
      // Not modal: the rest of the window stays as it is, and a right-click
      // elsewhere closes this menu and opens that place's own.
      modal={false}
      onOpenChange={(open) => {
        if (!open) choose(null);
      }}
    >
      <DropdownMenuTrigger asChild>
        <span
          aria-hidden="true"
          className="pointer-events-none fixed w-0"
          style={{ left: at.x, top: at.y, height: at.height ?? 0 }}
        />
      </DropdownMenuTrigger>
      <DropdownMenuContent
        aria-label={label}
        align="start"
        sideOffset={0}
        onInteractOutside={() => {
          pressedElsewhere.current = true;
        }}
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          // A press in the documentation frame closes the menu without
          // being reported as a press outside; the frame has focus by then.
          if (
            !pressedElsewhere.current &&
            !(document.activeElement instanceof HTMLIFrameElement) &&
            returnTo instanceof HTMLElement
          )
            returnTo.focus();
        }}
      >
        {items.map((item, index) =>
          "separator" in item ? (
            <DropdownMenuSeparator key={`separator-${index}`} />
          ) : (
            <DropdownMenuItem
              key={item.id}
              icon={item.icon}
              disabled={!item.enabled}
              onSelect={() => choose(item.id)}
            >
              {item.label}
              {item.chord && <DropdownMenuShortcut chord={item.chord} />}
            </DropdownMenuItem>
          ),
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
