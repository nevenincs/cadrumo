import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/components/ui/cn";

// Every pill uses an opaque surface, with text paired to that palette role.
// `count` is the compact counter and `soft` the roomier name label.
const badgeVariants = cva(
  "inline-flex w-fit max-w-full shrink-0 items-center justify-center gap-1 rounded-full border-0 px-2 text-xs font-medium whitespace-nowrap forced-colors:bg-[CanvasText] forced-colors:text-[Canvas] forced-colors:forced-color-adjust-none [&>svg]:pointer-events-none [&>svg]:shrink-0",
  {
    variants: {
      variant: {
        count:
          "h-badge min-w-badge bg-destructive px-1 text-2xs leading-none font-bold text-primary-foreground",
        soft: "gap-1.5 bg-secondary py-1 pr-3 pl-2 text-sm text-secondary-foreground",
        neutral: "bg-secondary text-secondary-foreground",
        success: "bg-success text-primary-foreground",
        warning: "bg-warning text-primary-foreground",
        danger: "bg-destructive text-primary-foreground",
        inverse: "bg-primary text-primary-foreground",
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
