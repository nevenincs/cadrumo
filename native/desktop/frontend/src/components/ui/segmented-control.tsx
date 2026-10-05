import * as React from "react";
import { RadioGroup as RadioGroupPrimitive } from "radix-ui";
import { cn } from "@/components/ui/cn";

/**
 * A radio group drawn as one segmented row: a choice among a few short,
 * mutually exclusive options. It is one tab stop, and arrow keys move the
 * choice. Give it an accessible name with `aria-label` or `aria-labelledby`.
 */
function SegmentedControl({
  className,
  ...props
}: React.ComponentProps<typeof RadioGroupPrimitive.Root>) {
  return (
    <RadioGroupPrimitive.Root
      data-slot="segmented-control"
      orientation="horizontal"
      className={cn("flex rounded-lg bg-secondary p-0.5", className)}
      {...props}
    />
  );
}

// The chosen segment lifts above the track: a lighter surface with an edge,
// stronger text, and the system's own highlight where colours are forced.
function SegmentedControlItem({
  className,
  onFocus,
  ...props
}: React.ComponentProps<typeof RadioGroupPrimitive.Item>) {
  return (
    <RadioGroupPrimitive.Item
      data-slot="segmented-control-item"
      onFocus={(event) => {
        onFocus?.(event);
        // An arrow key moves the choice along with the focus. The foundation
        // checks the radio only while it still sees the key held down, which
        // a key sent by software may no longer be. Keyboard focus arriving on
        // an unchecked segment of a group that has a choice is that move.
        const item = event.currentTarget;
        if (
          item.getAttribute("aria-checked") === "false" &&
          item.matches(":focus-visible") &&
          item.parentElement?.querySelector('[aria-checked="true"]')
        )
          item.click();
      }}
      className={cn(
        // A segment is as wide as its words need, sharing what is left over;
        // a name too long for the row wraps instead of being cut.
        "min-h-control-sm min-w-0 flex-auto cursor-pointer rounded-md px-2 py-0.5 text-base leading-tight text-balance text-muted-foreground select-none",
        "transition-colors hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50",
        "data-[state=checked]:bg-raised data-[state=checked]:font-medium data-[state=checked]:text-foreground data-[state=checked]:shadow-raised",
        "forced-colors:data-[state=checked]:bg-[Highlight] forced-colors:data-[state=checked]:text-[HighlightText]",
        className,
      )}
      {...props}
    />
  );
}

export { SegmentedControl, SegmentedControlItem };
