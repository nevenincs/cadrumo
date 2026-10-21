import type { ComponentProps } from "react";
import { cn } from "@/components/ui/cn";

/** Shared chrome and maximize gesture for workspace pane headers. */
export function PaneHeaderFrame({
  className,
  onToggleMaximize,
  ...props
}: Omit<ComponentProps<"div">, "onDoubleClick"> & {
  onToggleMaximize?: () => void;
}) {
  return (
    <div
      data-slot="pane-header"
      className={cn(
        "@container/head flex min-h-control-lg shrink-0 items-center gap-2 border-b bg-chrome py-1 pr-1.5 pl-3 text-muted-foreground select-none",
        className,
      )}
      onDoubleClick={(event) => {
        if (
          !(event.target as Element).closest(
            "button, input, select, textarea, a, [role='button'], [contenteditable='true']",
          )
        )
          onToggleMaximize?.();
      }}
      {...props}
    />
  );
}
