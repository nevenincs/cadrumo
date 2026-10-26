import * as React from "react";
import { cn } from "@/components/ui/cn";
import { Icon } from "@/components/ui/icon";

/**
 * The platform's own select, drawn like the other fields. Its list is the
 * operating system's, so it works by keyboard, touch and screen reader as
 * every other select on the machine does.
 */
function NativeSelect({
  className,
  controlSize = "md",
  ...props
}: Omit<React.ComponentProps<"select">, "size"> & {
  controlSize?: "sm" | "md";
}) {
  return (
    <div
      data-slot="native-select-wrapper"
      className="relative min-w-0 has-[select:disabled]:opacity-50"
    >
      <select
        data-slot="native-select"
        className={cn(
          "w-full min-w-0 cursor-pointer appearance-none rounded-md border border-input bg-card pr-7 text-base text-foreground transition-colors disabled:cursor-not-allowed",
          controlSize === "sm" ? "h-control-sm pl-2" : "h-control-md pl-2.5",
          className,
        )}
        {...props}
      />
      <Icon
        name="chevronDown"
        className="pointer-events-none absolute top-1/2 right-2 -translate-y-1/2 text-faint"
      />
    </div>
  );
}

export { NativeSelect };
