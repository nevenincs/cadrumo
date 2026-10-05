import { useState } from "react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuShortcut,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { ContextMenuItem } from "../ipc/contract";

// The shell's own drawing of a context menu, for where the host cannot show a
// native one. In the desktop application the host draws the same item list
// with the operating system's menu. It opens at a point, not from a control,
// so its anchor is an empty element placed there.
export function ContextMenu({
  items,
  at,
  choose,
}: {
  items: ContextMenuItem[];
  at: { x: number; y: number };
  choose: (id: string | null) => void;
}) {
  // Focus goes back where the menu came from, whichever way it is settled.
  const [returnTo] = useState(() => document.activeElement);
  return (
    <DropdownMenu
      open
      onOpenChange={(open) => {
        if (!open) choose(null);
      }}
    >
      <DropdownMenuTrigger asChild>
        <span
          aria-hidden="true"
          className="pointer-events-none fixed size-0"
          style={{ left: at.x, top: at.y }}
        />
      </DropdownMenuTrigger>
      <DropdownMenuContent
        className="native-menu"
        align="start"
        sideOffset={0}
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          if (returnTo instanceof HTMLElement) returnTo.focus();
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
