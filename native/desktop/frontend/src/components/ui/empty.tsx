import * as React from "react";
import { cn } from "@/components/ui/cn";

/**
 * What an area shows when it has nothing to show, and why: empty, loading,
 * unavailable or failed. It fills the area and centres a short message.
 */
function Empty({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="empty"
      className={cn(
        "flex min-h-0 min-w-0 flex-1 flex-col items-center justify-center gap-3 p-6 text-center text-balance",
        className,
      )}
      {...props}
    />
  );
}

function EmptyMedia({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="empty-media"
      className={cn(
        "flex size-control-lg shrink-0 items-center justify-center rounded-lg bg-accent text-muted-foreground [&_svg]:size-icon-lg",
        className,
      )}
      {...props}
    />
  );
}

function EmptyTitle({ className, ...props }: React.ComponentProps<"p">) {
  return (
    <p
      data-slot="empty-title"
      className={cn("text-base font-medium text-foreground", className)}
      {...props}
    />
  );
}

function EmptyDescription({ className, ...props }: React.ComponentProps<"p">) {
  return (
    <p
      data-slot="empty-description"
      className={cn("max-w-80 text-sm text-muted-foreground", className)}
      {...props}
    />
  );
}

export { Empty, EmptyDescription, EmptyMedia, EmptyTitle };
