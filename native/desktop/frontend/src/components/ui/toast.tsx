import * as React from "react";
import { cn } from "@/components/ui/cn";

/**
 * A brief confirmation at the bottom of the window. The region is always
 * present, so assistive technology hears a message the moment it appears;
 * the owner decides how long it stays.
 */
function Toast({ className, children, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="toast"
      role="status"
      aria-live="polite"
      className={cn(
        "pointer-events-none fixed inset-x-0 bottom-6 z-(--layer-toast) flex justify-center px-4",
        className,
      )}
      {...props}
    >
      {children && (
        <span className="max-w-full animate-in truncate rounded-full bg-foreground px-3.5 py-1.5 text-base text-background shadow-overlay fade-in-0 slide-in-from-bottom-2">
          {children}
        </span>
      )}
    </div>
  );
}

export { Toast };
