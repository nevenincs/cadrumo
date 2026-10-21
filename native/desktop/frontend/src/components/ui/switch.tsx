import * as React from "react";
import { Switch as SwitchPrimitive } from "radix-ui";
import { cn } from "@/components/ui/cn";

/**
 * An on/off control for one setting that takes effect at once. Give it an
 * accessible name with `aria-label` or a `<label>`; its state is announced as
 * checked or not, so the name says what is turned on, not "on".
 */
function Switch({
  className,
  ...props
}: React.ComponentProps<typeof SwitchPrimitive.Root>) {
  return (
    <SwitchPrimitive.Root
      data-slot="switch"
      className={cn(
        "inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full border border-border-strong bg-secondary p-0.5 outline-none",
        "transition-colors focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50",
        "data-[state=checked]:border-transparent data-[state=checked]:bg-primary",
        "forced-colors:border-[CanvasText] forced-colors:data-[state=checked]:bg-[Highlight]",
        className,
      )}
      {...props}
    >
      <SwitchPrimitive.Thumb
        data-slot="switch-thumb"
        className={cn(
          "block size-3.5 rounded-full bg-muted-foreground transition-transform",
          "data-[state=checked]:translate-x-4 data-[state=checked]:bg-primary-foreground",
          "forced-colors:bg-[CanvasText] forced-colors:data-[state=checked]:bg-[HighlightText]",
        )}
      />
    </SwitchPrimitive.Root>
  );
}

export { Switch };
