import * as React from "react";
import { cn } from "@/components/ui/cn";
import { Icon, type IconName } from "@/components/ui/icon";
import { Spinner } from "@/components/ui/spinner";

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

/** Shared presentation for a pane's pending, empty or unavailable content. */
function EmptyState({
  icon,
  busy = false,
  heading,
  description,
  descriptionClassName,
  children,
  ...props
}: React.ComponentProps<typeof Empty> & {
  icon?: IconName;
  busy?: boolean;
  heading?: React.ReactNode;
  description?: React.ReactNode;
  descriptionClassName?: string;
}) {
  return (
    <Empty aria-busy={busy || undefined} {...props}>
      {busy ? (
        <Spinner />
      ) : icon ? (
        <EmptyMedia>
          <Icon name={icon} />
        </EmptyMedia>
      ) : null}
      {(heading || description) && (
        <div className="grid gap-1">
          {heading && <EmptyTitle>{heading}</EmptyTitle>}
          {description && (
            <EmptyDescription className={descriptionClassName}>
              {description}
            </EmptyDescription>
          )}
        </div>
      )}
      {children}
    </Empty>
  );
}

export { Empty, EmptyDescription, EmptyMedia, EmptyState, EmptyTitle };
