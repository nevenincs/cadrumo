import { useRef, useState } from "react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuShortcut,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { ContextMenuItem } from "../ipc/contract";

/** Where a menu opens: a point, or with a height the edge of a row, which the
 * menu then opens under or over and never across. */
export type MenuAnchor = { x: number; y: number; height?: number };

// The shell's own drawing of a context menu, for where the host cannot show a
// native one. In the desktop application the host draws the same item list
// with the operating system's menu. It opens at a point, not from a control,
// so its anchor is an empty element placed there.
export function ContextMenu({
  label,
  items,
  at,
  choose,
}: {
  /** The menu's accessible name: it has no visible control to take one from. */
  label: string;
  items: ContextMenuItem[];
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
          if (!pressedElsewhere.current && returnTo instanceof HTMLElement)
            returnTo.focus();
        }}
      >
        {items.map((item, index) =>
          "separator" in item ? (
            <DropdownMenuSeparator key={`separator-${index}`} />
          ) : (
            <DropdownMenuItem
              key={item.id}
              disabled={!item.enabled}
              onSelect={() => choose(item.id)}
            >
              {item.label}
              {item.shortcut && (
                <DropdownMenuShortcut aria-hidden="true">
                  {item.shortcut}
                </DropdownMenuShortcut>
              )}
            </DropdownMenuItem>
          ),
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
