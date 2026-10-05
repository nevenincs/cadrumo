import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/components/ui/cn";

// Inline feedback: a quiet surface whose icon carries the tone. The tone sets
// the current colour of the icon and of a progress bar inside, never of the
// text, which stays readable ink.
const alertVariants = cva(
  "flex w-full items-start gap-2 rounded-md bg-accent px-3 py-2 text-base [&>svg]:mt-0.5 [&>svg]:size-icon-sm [&>svg]:shrink-0",
  {
    variants: {
      tone: {
        neutral: "text-muted-foreground",
        success: "text-success",
        warning: "text-warning",
        danger: "text-destructive",
      },
    },
    defaultVariants: { tone: "neutral" },
  },
);

/**
 * `role="status"` by default, announced politely; pass `role="alert"` for a
 * failure the person must hear at once. `icon` leads the text. The children
 * are the message: plain text for one line, or a title and a description.
 */
function Alert({
  className,
  tone,
  icon,
  role = "status",
  children,
  ...props
}: React.ComponentProps<"div"> &
  VariantProps<typeof alertVariants> & { icon?: React.ReactNode }) {
  return (
    <div
      data-slot="alert"
      data-tone={tone ?? "neutral"}
      role={role}
      className={cn(alertVariants({ tone }), className)}
      {...props}
    >
      {icon}
      <div className="grid min-w-0 flex-1 gap-0.5 text-foreground">
        {children}
      </div>
    </div>
  );
}

function AlertTitle({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="alert-title"
      className={cn("font-medium", className)}
      {...props}
    />
  );
}

function AlertDescription({
  className,
  ...props
}: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="alert-description"
      className={cn("text-sm text-muted-foreground", className)}
      {...props}
    />
  );
}

export { Alert, AlertDescription, AlertTitle };
