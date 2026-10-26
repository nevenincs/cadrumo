import * as React from "react";
import { DropdownMenu as DropdownMenuPrimitive } from "radix-ui";
import { cn } from "@/components/ui/cn";
import { Icon } from "@/components/ui/icon";

function DropdownMenu(
  props: React.ComponentProps<typeof DropdownMenuPrimitive.Root>,
) {
  return <DropdownMenuPrimitive.Root data-slot="dropdown-menu" {...props} />;
}

function DropdownMenuTrigger(
  props: React.ComponentProps<typeof DropdownMenuPrimitive.Trigger>,
) {
  return (
    <DropdownMenuPrimitive.Trigger
      data-slot="dropdown-menu-trigger"
      {...props}
    />
  );
}

/**
 * A menu of actions. Arrow keys, Home, End and typing move through the items,
 * Enter or Space chooses, and Escape or a press outside closes it. It stays
 * inside the window: a long menu scrolls.
 */
function DropdownMenuContent({
  className,
  sideOffset = 4,
  collisionPadding = 8,
  ...props
}: React.ComponentProps<typeof DropdownMenuPrimitive.Content>) {
  return (
    <DropdownMenuPrimitive.Portal>
      <DropdownMenuPrimitive.Content
        data-slot="dropdown-menu-content"
        sideOffset={sideOffset}
        collisionPadding={collisionPadding}
        className={cn(
          "z-(--layer-menu) max-h-(--radix-dropdown-menu-content-available-height) min-w-menu origin-(--radix-dropdown-menu-content-transform-origin) overflow-x-hidden overflow-y-auto rounded-lg border bg-popover p-1 text-popover-foreground shadow-overlay outline-none",
          "data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:animate-in data-[state=open]:fade-in-0",
          className,
        )}
        {...props}
      />
    </DropdownMenuPrimitive.Portal>
  );
}

function DropdownMenuItem({
  className,
  ...props
}: React.ComponentProps<typeof DropdownMenuPrimitive.Item>) {
  return (
    <DropdownMenuPrimitive.Item
      data-slot="dropdown-menu-item"
      className={cn(
        "relative flex min-h-control-sm cursor-pointer items-center gap-2 rounded-sm px-2.5 text-base outline-none select-none",
        "data-[disabled]:pointer-events-none data-[disabled]:opacity-50",
        // The item the keyboard or the pointer is on: the chosen-row surface
        // and bar, as a command row has.
        "data-[highlighted]:bg-selected data-[highlighted]:text-accent-foreground",
        "before:absolute before:inset-y-1.5 before:left-0 before:w-0.5 before:rounded-xs before:bg-brand before:opacity-0 data-[highlighted]:before:opacity-100",
        "forced-colors:data-[highlighted]:bg-[Highlight] forced-colors:data-[highlighted]:text-[HighlightText]",
        "[&_svg]:pointer-events-none [&_svg]:shrink-0",
        className,
      )}
      {...props}
    />
  );
}

function DropdownMenuSeparator({
  className,
  ...props
}: React.ComponentProps<typeof DropdownMenuPrimitive.Separator>) {
  return (
    <DropdownMenuPrimitive.Separator
      data-slot="dropdown-menu-separator"
      className={cn("-mx-1 my-1 h-px bg-border", className)}
      {...props}
    />
  );
}

/** Display-only accelerator text beside an item; it binds nothing. */
function DropdownMenuShortcut({
  className,
  ...props
}: React.ComponentProps<"span">) {
  return (
    <span
      data-slot="dropdown-menu-shortcut"
      // On the highlighted item the surface is tinted, which faint text has
      // no contrast to spare for.
      className={cn(
        "ml-auto pl-6 text-sm text-faint in-data-[highlighted]:text-muted-foreground",
        className,
      )}
      {...props}
    />
  );
}

/** A titled set of items, or of choices. */
function DropdownMenuGroup({
  label,
  children,
  ...props
}: React.ComponentProps<typeof DropdownMenuPrimitive.Group> & {
  label?: React.ReactNode;
}) {
  return (
    <DropdownMenuPrimitive.Group data-slot="dropdown-menu-group" {...props}>
      {label !== undefined && (
        <DropdownMenuPrimitive.Label className="px-2.5 pt-1.5 pb-1 text-xs font-medium text-faint">
          {label}
        </DropdownMenuPrimitive.Label>
      )}
      {children}
    </DropdownMenuPrimitive.Group>
  );
}

function DropdownMenuRadioGroup(
  props: React.ComponentProps<typeof DropdownMenuPrimitive.RadioGroup>,
) {
  return (
    <DropdownMenuPrimitive.RadioGroup
      data-slot="dropdown-menu-radio-group"
      {...props}
    />
  );
}

/** One choice of a radio group. Choosing it keeps the menu open, so several
 * choices can be made in one visit. */
function DropdownMenuRadioItem({
  className,
  children,
  onSelect,
  ...props
}: React.ComponentProps<typeof DropdownMenuPrimitive.RadioItem>) {
  return (
    <DropdownMenuPrimitive.RadioItem
      data-slot="dropdown-menu-radio-item"
      onSelect={(event) => {
        event.preventDefault();
        onSelect?.(event);
      }}
      className={cn(
        "relative flex min-h-control-sm cursor-pointer items-center gap-2 rounded-sm px-2.5 text-base outline-none select-none",
        "data-[disabled]:pointer-events-none data-[disabled]:opacity-50",
        "data-[highlighted]:bg-selected data-[highlighted]:text-accent-foreground",
        "forced-colors:data-[highlighted]:bg-[Highlight] forced-colors:data-[highlighted]:text-[HighlightText]",
        className,
      )}
      {...props}
    >
      <span className="flex size-icon-sm items-center justify-center">
        <DropdownMenuPrimitive.ItemIndicator>
          <Icon name="tick" />
        </DropdownMenuPrimitive.ItemIndicator>
      </span>
      {children}
    </DropdownMenuPrimitive.RadioItem>
  );
}

export {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuShortcut,
  DropdownMenuTrigger,
};
