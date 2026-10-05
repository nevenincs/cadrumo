import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { Slot } from "radix-ui";
import { cn } from "@/components/ui/cn";
import { Spinner } from "@/components/ui/spinner";

// Heights are the density tokens; the square sizes are for icon-only buttons.
// A toggle button says so with `aria-pressed`, which is also what styles it.
const buttonVariants = cva(
  [
    "inline-flex shrink-0 cursor-pointer items-center justify-center gap-1.5 rounded-md font-medium whitespace-nowrap select-none",
    "transition-colors disabled:pointer-events-none disabled:opacity-50",
    "aria-busy:pointer-events-none",
    "[&_svg]:pointer-events-none [&_svg]:shrink-0",
  ],
  {
    variants: {
      variant: {
        primary:
          "bg-primary text-primary-foreground hover:bg-primary/90 active:bg-primary/80",
        secondary:
          "bg-secondary text-secondary-foreground hover:bg-secondary/70 active:bg-secondary",
        outline:
          "border border-input bg-card text-foreground hover:bg-accent active:bg-secondary aria-pressed:border-ring aria-pressed:bg-accent",
        ghost:
          "text-muted-foreground hover:bg-accent hover:text-accent-foreground active:bg-secondary aria-pressed:bg-accent aria-pressed:text-accent-foreground",
        destructive:
          "bg-destructive text-primary-foreground hover:bg-destructive/90 active:bg-destructive/80",
        link: "h-auto px-0 text-brand underline-offset-4 hover:underline",
      },
      size: {
        xs: "h-control-xs px-2 text-sm",
        sm: "h-control-sm px-2.5 text-base",
        md: "h-control-md px-3 text-base",
        lg: "h-control-lg px-4 text-base",
        "icon-xs": "size-control-xs",
        "icon-sm": "size-control-sm",
        "icon-md": "size-control-md",
        "icon-lg": "size-control-lg rounded-lg",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);

type ButtonProps = React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & {
    /** Render the child element as the button, keeping these styles. */
    asChild?: boolean;
    /** Work this button started is in flight: it shows a spinner, reports
     * itself busy and takes no further activation. */
    pending?: boolean;
  };

function Button({
  className,
  variant = "primary",
  size = "md",
  asChild = false,
  pending = false,
  disabled,
  type = "button",
  children,
  ...props
}: ButtonProps) {
  const Comp = asChild ? Slot.Root : "button";
  return (
    <Comp
      data-slot="button"
      data-variant={variant}
      data-size={size}
      type={asChild ? undefined : type}
      disabled={disabled || pending}
      aria-busy={pending || undefined}
      className={cn(buttonVariants({ variant, size }), className)}
      {...props}
    >
      {pending && !asChild ? (
        <>
          <Spinner />
          {children}
        </>
      ) : (
        children
      )}
    </Comp>
  );
}

export { Button, buttonVariants, type ButtonProps };
