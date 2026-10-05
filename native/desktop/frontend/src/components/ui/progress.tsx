import * as React from "react";
import { Progress as ProgressPrimitive } from "radix-ui";
import { cn } from "@/components/ui/cn";

/** Determinate progress, 0 to `max`. Name it with `aria-label`. */
function Progress({
  className,
  value,
  max = 100,
  ...props
}: React.ComponentProps<typeof ProgressPrimitive.Root>) {
  const share = Math.max(0, Math.min(1, (value ?? 0) / max));
  return (
    <ProgressPrimitive.Root
      data-slot="progress"
      value={value}
      max={max}
      className={cn(
        "relative h-1 w-full overflow-hidden rounded-full bg-foreground/10",
        className,
      )}
      {...props}
    >
      <ProgressPrimitive.Indicator
        data-slot="progress-indicator"
        className="size-full origin-left bg-brand transition-transform duration-(--motion-base) ease-linear"
        style={{ transform: `scaleX(${share})` }}
      />
    </ProgressPrimitive.Root>
  );
}

export { Progress };
