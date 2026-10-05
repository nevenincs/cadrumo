import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/components/ui/cn";

const inputVariants = cva(
  [
    "w-full min-w-0 rounded-md border border-input bg-card text-base text-foreground",
    "transition-colors placeholder:text-faint",
    "selection:bg-primary selection:text-primary-foreground",
    "disabled:cursor-not-allowed disabled:opacity-50",
    "aria-invalid:border-destructive aria-invalid:outline-destructive",
  ],
  {
    variants: {
      /** `md` in a dialog or form, `sm` in a toolbar. */
      controlSize: {
        sm: "h-control-sm px-2",
        md: "h-control-md px-2.5",
      },
    },
    defaultVariants: { controlSize: "md" },
  },
);

function Input({
  className,
  controlSize,
  type = "text",
  ...props
}: React.ComponentProps<"input"> & VariantProps<typeof inputVariants>) {
  return (
    <input
      data-slot="input"
      type={type}
      className={cn(inputVariants({ controlSize }), className)}
      {...props}
    />
  );
}

export { Input, inputVariants };
