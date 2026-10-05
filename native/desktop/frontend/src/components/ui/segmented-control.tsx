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

function SegmentedControlItem({
  className,
  ...props
}: React.ComponentProps<typeof RadioGroupPrimitive.Item>) {
  return (
    <RadioGroupPrimitive.Item
      data-slot="segmented-control-item"
      className={cn(
        "h-control-sm min-w-0 flex-1 cursor-pointer truncate rounded-md px-2 text-base text-muted-foreground select-none",
        "transition-colors hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50",
        "data-[state=checked]:bg-card data-[state=checked]:text-foreground data-[state=checked]:shadow-raised",
        className,
      )}
      {...props}
    />
  );
}

export { SegmentedControl, SegmentedControlItem };
