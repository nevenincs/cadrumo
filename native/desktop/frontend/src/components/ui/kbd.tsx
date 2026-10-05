import * as React from "react";
import { cn } from "@/components/ui/cn";

/** A key or chord hint. Inside a tooltip it takes the tooltip's own contrast. */
function Kbd({ className, ...props }: React.ComponentProps<"kbd">) {
  return (
    <kbd
      data-slot="kbd"
      className={cn(
        "pointer-events-none inline-flex h-5 w-fit min-w-5 items-center justify-center gap-1 rounded-sm bg-muted px-1 font-sans text-xs font-medium whitespace-nowrap text-faint select-none",
        "[[data-slot=tooltip-content]_&]:bg-background/15 [[data-slot=tooltip-content]_&]:text-background",
        className,
      )}
      {...props}
    />
  );
}

export { Kbd };
