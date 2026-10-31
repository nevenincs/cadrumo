import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/components/ui/cn";
import { inputVariants } from "@/components/ui/input";

// A text control's surface and size come from `inputVariants`; a textarea only
// gives up the fixed height for its rows.
const textareaVariants = cva("block h-auto resize-y", {
  variants: {
    controlSize: {
      sm: "py-1",
      md: "py-1.5",
    },
  },
  defaultVariants: { controlSize: "md" },
});

function Textarea({
  className,
  controlSize,
  rows = 3,
  ...props
}: React.ComponentProps<"textarea"> & VariantProps<typeof inputVariants>) {
  return (
    <textarea
      data-slot="textarea"
      rows={rows}
      className={cn(
        inputVariants({ controlSize }),
        textareaVariants({ controlSize }),
        className,
      )}
      {...props}
    />
  );
}

export { Textarea, textareaVariants };
