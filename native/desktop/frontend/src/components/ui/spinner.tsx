import * as React from "react";
import { Icon } from "@/components/ui/icon";
import { cn } from "@/components/ui/cn";

/**
 * A pending indicator. With a `label` it is a status of its own; without one
 * it is decoration beside text that already says what is pending.
 */
function Spinner({
  className,
  label,
  ...props
}: Omit<React.ComponentProps<"svg">, "ref" | "name"> & { label?: string }) {
  return (
    <Icon
      name="loader"
      data-slot="spinner"
      role={label ? "status" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      className={cn("animate-spin", className)}
      {...props}
    />
  );
}

export { Spinner };
