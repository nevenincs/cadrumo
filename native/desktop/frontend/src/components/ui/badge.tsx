import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/components/ui/cn";

// `count` is the small solid counter on a rail button or a tab, and `soft` a
// quiet filled label for a name. The rest are outlines in a status colour,
// with the same names an alert's tone takes.
const badgeVariants = cva(
  "inline-flex w-fit max-w-full shrink-0 items-center justify-center gap-1 rounded-full font-medium whitespace-nowrap [&>svg]:pointer-events-none [&>svg]:shrink-0",
  {
    variants: {
      variant: {
        count:
          "h-badge min-w-badge bg-destructive px-1 text-2xs leading-none font-bold text-primary-foreground",
        soft: "gap-1.5 bg-accent py-1 pr-3 pl-2 text-sm text-foreground [&>svg]:text-muted-foreground",
        neutral:
          "border border-border-strong px-2 text-xs text-muted-foreground",
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
