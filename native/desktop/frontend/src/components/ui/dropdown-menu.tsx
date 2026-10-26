import * as React from "react";
import { DropdownMenu as DropdownMenuPrimitive } from "radix-ui";
import { cn } from "@/components/ui/cn";
import { Icon, type IconName } from "@/components/ui/icon";
import { Kbd } from "@/components/ui/kbd";
import { chordParts, type ChordKeys } from "@/shared/chords";

// Every menu in the window is drawn from this module: the context menu, the
// account menu and each dropdown share one surface, one row and one set of
// states, so none carries a look of its own.

const SURFACE = cn(
  "z-(--layer-menu) max-h-(--radix-dropdown-menu-content-available-height) max-w-(--radix-dropdown-menu-content-available-width) min-w-menu overflow-x-hidden overflow-y-auto rounded-lg border bg-popover p-1 text-popover-foreground shadow-overlay outline-none",
  "data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:animate-in data-[state=open]:fade-in-0",
);

const ROW = cn(
  "relative flex min-h-control-sm cursor-pointer items-center gap-2 rounded-sm px-2.5 text-base outline-none select-none",
  "data-[disabled]:pointer-events-none data-[disabled]:opacity-50",
  // The item the keyboard or the pointer is on: the chosen-row surface
  // and bar, as a command row has.
  "data-[highlighted]:bg-selected data-[highlighted]:text-accent-foreground",
  "before:absolute before:inset-y-1.5 before:left-0 before:w-0.5 before:rounded-xs before:bg-brand before:opacity-0 data-[highlighted]:before:opacity-100",
  "forced-colors:data-[highlighted]:bg-[Highlight] forced-colors:data-[highlighted]:text-[HighlightText]",
  "[&_svg]:pointer-events-none [&_svg]:shrink-0",
);

// The leading column of a row: its icon, or the mark of a checked choice.
// Where any row of the menu has one, every row keeps the column, so the
// labels stay in line.
const LEADING =
  "flex size-icon-sm shrink-0 items-center justify-center text-muted-foreground in-data-[highlighted]:text-accent-foreground";

function Leading({ icon }: { icon?: IconName }) {
  return icon ? (
    <span data-leading="" aria-hidden="true" className={LEADING}>
      <Icon name={icon} />
    </span>
  ) : (
    <span
      aria-hidden="true"
      className="hidden size-icon-sm shrink-0 group-has-[[data-leading]]/menu:block"
    />
  );
}

function Indicator() {
  return (
    <span data-leading="" aria-hidden="true" className={LEADING}>
      <DropdownMenuPrimitive.ItemIndicator>
        <Icon name="tick" />
      </DropdownMenuPrimitive.ItemIndicator>
    </span>
  );
}

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
          SURFACE,
          "group/menu origin-(--radix-dropdown-menu-content-transform-origin)",
          className,
        )}
        {...props}
      />
    </DropdownMenuPrimitive.Portal>
  );
}

/**
 * One action. An icon from the shell's set leads it; the menu's other items
 * then leave the same column, so labels line up whether or not each has one.
 */
function DropdownMenuItem({
  className,
  icon,
  children,
  ...props
}: React.ComponentProps<typeof DropdownMenuPrimitive.Item> & {
  icon?: IconName;
}) {
  return (
    <DropdownMenuPrimitive.Item
      data-slot="dropdown-menu-item"
      className={cn(ROW, className)}
      {...props}
    >
      <Leading icon={icon} />
      {children}
    </DropdownMenuPrimitive.Item>
  );
}

/** One on-or-off choice. Choosing it keeps the menu open, so several can be
 * made in one visit. */
function DropdownMenuCheckboxItem({
  className,
  children,
  onSelect,
  ...props
}: React.ComponentProps<typeof DropdownMenuPrimitive.CheckboxItem>) {
  return (
    <DropdownMenuPrimitive.CheckboxItem
      data-slot="dropdown-menu-checkbox-item"
      onSelect={(event) => {
        event.preventDefault();
        onSelect?.(event);
      }}
      className={cn(ROW, className)}
      {...props}
    >
      <Indicator />
      {children}
    </DropdownMenuPrimitive.CheckboxItem>
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
      className={cn(ROW, className)}
      {...props}
    >
      <Indicator />
      {children}
    </DropdownMenuPrimitive.RadioItem>
  );
}

function DropdownMenuSub(
  props: React.ComponentProps<typeof DropdownMenuPrimitive.Sub>,
) {
  return <DropdownMenuPrimitive.Sub data-slot="dropdown-menu-sub" {...props} />;
}

/** The item that opens a submenu: the right arrow opens it, the left closes
 * it. */
function DropdownMenuSubTrigger({
  className,
  icon,
  children,
  ...props
}: React.ComponentProps<typeof DropdownMenuPrimitive.SubTrigger> & {
  icon?: IconName;
}) {
  return (
    <DropdownMenuPrimitive.SubTrigger
      data-slot="dropdown-menu-sub-trigger"
      className={cn(ROW, "data-[state=open]:bg-selected", className)}
      {...props}
    >
      <Leading icon={icon} />
      {children}
      <Icon name="forward" size="xs" className="ml-auto text-faint" />
    </DropdownMenuPrimitive.SubTrigger>
  );
}

function DropdownMenuSubContent({
  className,
  collisionPadding = 8,
  ...props
}: React.ComponentProps<typeof DropdownMenuPrimitive.SubContent>) {
  return (
    <DropdownMenuPrimitive.Portal>
      <DropdownMenuPrimitive.SubContent
        data-slot="dropdown-menu-sub-content"
        collisionPadding={collisionPadding}
        className={cn(
          SURFACE,
          "group/menu origin-(--radix-dropdown-menu-content-transform-origin)",
          className,
        )}
        {...props}
      />
    </DropdownMenuPrimitive.Portal>
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

/** A caption for the items that follow it. */
function DropdownMenuLabel({
  className,
  ...props
}: React.ComponentProps<typeof DropdownMenuPrimitive.Label>) {
  return (
    <DropdownMenuPrimitive.Label
      data-slot="dropdown-menu-label"
      className={cn(
        "px-2.5 pt-1.5 pb-1 text-xs font-medium text-faint",
        className,
      )}
      {...props}
    />
  );
}

/** A sentence of explanation between items. */
function DropdownMenuNote({ className, ...props }: React.ComponentProps<"p">) {
  return (
    <p
      data-slot="dropdown-menu-note"
      className={cn("mx-2.5 my-2 text-sm text-muted-foreground", className)}
      {...props}
    />
  );
}

/**
 * The items of a panel that holds more than a menu, such as notes or a
 * status beside them. The panel then names itself as a dialog, and this
 * names the part that is the menu.
 */
function DropdownMenuList(props: React.ComponentProps<"div">) {
  return <div data-slot="dropdown-menu-list" role="menu" {...props} />;
}

/**
 * A titled set of items, or of choices.
 */
function DropdownMenuGroup({
  label,
  children,
  ...props
}: React.ComponentProps<typeof DropdownMenuPrimitive.Group> & {
  label?: React.ReactNode;
}) {
  return (
    <DropdownMenuPrimitive.Group data-slot="dropdown-menu-group" {...props}>
      {label !== undefined && <DropdownMenuLabel>{label}</DropdownMenuLabel>}
      {children}
    </DropdownMenuPrimitive.Group>
  );
}

/**
 * Display-only accelerator beside an item; it binds nothing. A chord is drawn
 * in the platform's notation, a key to a keycap, from the registry's own
 * declaration, so the shortcut shown is the one that works. Without a chord
 * its children are the text. Hidden from assistive technology: the item is
 * named by its label alone.
 */
function DropdownMenuShortcut({
  className,
  chord,
  children,
  ...props
}: React.ComponentProps<"span"> & { chord?: ChordKeys }) {
  return (
    <span
      data-slot="dropdown-menu-shortcut"
      aria-hidden="true"
      // On the highlighted item the surface is tinted, which faint text has
      // no contrast to spare for.
      className={cn(
        "ml-auto flex items-center gap-1 pl-6 text-sm text-faint in-data-[highlighted]:text-muted-foreground",
        className,
      )}
      {...props}
    >
      {chord
        ? chordParts(chord).map((part, at) => <Kbd key={at}>{part}</Kbd>)
        : children}
    </span>
  );
}

export {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuList,
  DropdownMenuNote,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuShortcut,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
};
