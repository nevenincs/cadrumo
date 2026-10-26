import * as React from "react";
import { Command as CommandPrimitive } from "cmdk";
import { cn } from "@/components/ui/cn";
import { Icon } from "@/components/ui/icon";

/**
 * A filterable list of commands: one text input drives a listbox of grouped
 * options. Arrow keys, Home and End move the choice while focus stays in the
 * input, and Enter runs it.
 */
function Command({
  className,
  ...props
}: React.ComponentProps<typeof CommandPrimitive>) {
  return (
    <CommandPrimitive
      data-slot="command"
      className={cn(
        "flex size-full min-h-0 flex-col overflow-hidden bg-popover text-popover-foreground",
        className,
      )}
      {...props}
    />
  );
}

function CommandInput({
  className,
  children,
  ...props
}: React.ComponentProps<typeof CommandPrimitive.Input>) {
  return (
    <div
      data-slot="command-input-wrapper"
      className="flex shrink-0 items-center gap-2.5 border-b px-3.5 py-3 text-faint"
    >
      <Icon name="search" size="lg" />
      <CommandPrimitive.Input
        data-slot="command-input"
        className={cn(
          "h-control-md min-w-0 flex-1 bg-transparent text-md text-foreground outline-none placeholder:text-faint disabled:cursor-not-allowed disabled:opacity-50",
          className,
        )}
        {...props}
      />
      {children}
    </div>
  );
}

function CommandList({
  className,
  ...props
}: React.ComponentProps<typeof CommandPrimitive.List>) {
  return (
    <CommandPrimitive.List
      data-slot="command-list"
      className={cn(
        "min-h-0 scroll-py-1.5 overflow-x-hidden overflow-y-auto p-1.5 outline-none",
        className,
      )}
      {...props}
    />
  );
}

function CommandEmpty({
  className,
  ...props
}: React.ComponentProps<typeof CommandPrimitive.Empty>) {
  return (
    <CommandPrimitive.Empty
      data-slot="command-empty"
      className={cn("px-2.5 py-2 text-base text-faint", className)}
      {...props}
    />
  );
}

function CommandGroup({
  className,
  ...props
}: React.ComponentProps<typeof CommandPrimitive.Group>) {
  return (
    <CommandPrimitive.Group
      data-slot="command-group"
      className={cn(
        "text-foreground",
        "[&_[cmdk-group-heading]]:flex [&_[cmdk-group-heading]]:items-baseline [&_[cmdk-group-heading]]:gap-2 [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:pt-2 [&_[cmdk-group-heading]]:pb-1 [&_[cmdk-group-heading]]:text-xs [&_[cmdk-group-heading]]:font-semibold [&_[cmdk-group-heading]]:tracking-wider [&_[cmdk-group-heading]]:text-faint [&_[cmdk-group-heading]]:uppercase",
        className,
      )}
      {...props}
    />
  );
}

function CommandItem({
  className,
  ...props
}: React.ComponentProps<typeof CommandPrimitive.Item>) {
  return (
    <CommandPrimitive.Item
      data-slot="command-item"
      className={cn(
        "relative flex min-h-control-lg cursor-pointer items-center gap-2.5 rounded-lg px-2.5 py-2 text-base outline-none select-none",
        "data-[disabled=true]:pointer-events-none data-[disabled=true]:opacity-50",
        // The chosen row: a stronger surface and a bar on its edge, so the
        // choice is clear in either scheme and where colours are forced.
        "data-[selected=true]:bg-selected data-[selected=true]:text-accent-foreground",
        "before:absolute before:inset-y-2 before:left-0 before:w-0.5 before:rounded-xs before:bg-brand before:opacity-0 data-[selected=true]:before:opacity-100",
        "forced-colors:data-[selected=true]:bg-[Highlight] forced-colors:data-[selected=true]:text-[HighlightText]",
        "[&_svg]:pointer-events-none [&_svg]:shrink-0",
        className,
      )}
      {...props}
    />
  );
}

export {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
};
