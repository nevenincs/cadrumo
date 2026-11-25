import type * as React from "react";
import { cn } from "@/components/ui/cn";

/** A native acknowledgement or form choice; its value takes effect on submit. */
function Checkbox({
  className,
  ...props
}: Omit<React.ComponentProps<"input">, "type">) {
  return (
    <input
      type="checkbox"
      data-slot="checkbox"
      className={cn("size-icon-sm shrink-0", className)}
      {...props}
    />
  );
}

export { Checkbox };
