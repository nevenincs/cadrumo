import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/components/ui/cn";

// `count` is the small solid counter on a rail button or a tab. The others
// are quiet labels: an outline in a status colour, never a filled block.
const badgeVariants = cva(
  "inline-flex w-fit shrink-0 items-center justify-center gap-1 rounded-full font-medium whitespace-nowrap [&>svg]:pointer-events-none [&>svg]:size-icon-xs",
  {
    variants: {
      variant: {
        count:
          "h-badge min-w-badge bg-destructive px-1 text-2xs leading-none font-bold text-primary-foreground",
        neutral:
          "border border-border-strong px-2 text-xs text-muted-foreground",
        brand: "border border-brand/40 px-2 text-xs text-brand",
        success: "border border-success/40 px-2 text-xs text-success",
        warning: "border border-warning/40 px-2 text-xs text-warning",
        danger: "border border-destructive/40 px-2 text-xs text-destructive",
      },
    },
    defaultVariants: { variant: "neutral" },
  },
);

function Badge({
  className,
  variant,
  ...props
}: React.ComponentProps<"span"> & VariantProps<typeof badgeVariants>) {
  return (
    <span
      data-slot="badge"
      data-variant={variant ?? "neutral"}
      className={cn(badgeVariants({ variant }), className)}
      {...props}
    />
  );
}

export { Badge, badgeVariants };
