import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { Slot } from "radix-ui";
import { cn } from "@/components/ui/cn";
import { Spinner } from "@/components/ui/spinner";

// Heights are the density tokens; the square sizes are for icon-only buttons.
// A toggle button says so with `aria-pressed`, which is also what styles it:
// a pressed button takes the selected surface, a step stronger than hover.
const buttonVariants = cva(
  [
    "inline-flex shrink-0 cursor-pointer items-center justify-center gap-1.5 rounded-md font-medium whitespace-nowrap select-none",
    "transition-colors disabled:pointer-events-none disabled:opacity-50",
    // Disabled in name only, so that it keeps focus: it looks disabled all
    // the same, unless it is busy, which its spinner says.
    "aria-disabled:cursor-default aria-disabled:not-aria-busy:opacity-50",
    "aria-busy:cursor-progress",
    "forced-colors:aria-pressed:bg-[Highlight] forced-colors:aria-pressed:text-[HighlightText]",
    "[&_svg]:pointer-events-none [&_svg]:shrink-0",
  ],
  {
    variants: {
      variant: {
        primary:
          "bg-primary text-primary-foreground hover:bg-primary/90 active:bg-primary/80 forced-colors:border forced-colors:border-[ButtonBorder]",
        secondary:
          "bg-secondary text-secondary-foreground hover:bg-selected active:bg-selected forced-colors:border forced-colors:border-[ButtonBorder]",
        outline:
          "border border-input bg-card text-foreground hover:bg-accent active:bg-selected aria-pressed:border-ring aria-pressed:bg-selected",
        ghost:
          "text-muted-foreground hover:bg-accent hover:text-accent-foreground active:bg-selected aria-pressed:bg-selected aria-pressed:text-accent-foreground",
        destructive:
          "bg-destructive text-primary-foreground hover:bg-destructive/90 active:bg-destructive/80 forced-colors:border forced-colors:border-[ButtonBorder]",
        link: "text-foreground underline underline-offset-4 hover:decoration-2",
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
    // A link sits in a line of text: it takes no height or padding of its own.
    compoundVariants: [{ variant: "link", className: "h-auto px-0" }],
    defaultVariants: { variant: "primary", size: "md" },
  },
);

type ButtonProps = React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & {
    /** Render the child element as the button, keeping these styles. */
    asChild?: boolean;
    /** Work this button started is in flight: it shows a spinner and reports
     * itself busy. It stays focusable, so focus is not lost while the answer
     * is awaited, and takes no further activation. */
    pending?: boolean;
  };

function Button({
  className,
  variant = "primary",
  size = "md",
  asChild = false,
  pending = false,
  type = "button",
  onClick,
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
      aria-busy={pending || undefined}
      aria-disabled={pending || undefined}
      className={cn(buttonVariants({ variant, size }), className)}
      onClick={
        pending
          ? (event: React.MouseEvent<HTMLButtonElement>) =>
              event.preventDefault()
          : onClick
      }
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
