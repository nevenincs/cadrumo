import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/components/ui/cn";

// Inline feedback: a quiet surface whose icon and title carry the tone.
const alertVariants = cva(
  "flex w-full items-start gap-2 rounded-md bg-accent px-3 py-2 text-base text-foreground [&>svg]:mt-0.5 [&>svg]:size-icon-sm [&>svg]:shrink-0",
  {
    variants: {
      tone: {
        neutral: "[&>svg]:text-muted-foreground",
        success: "[&>svg]:text-success",
        warning: "[&>svg]:text-warning",
        danger:
          "[&>svg]:text-destructive **:data-[slot=alert-title]:text-destructive",
      },
    },
    defaultVariants: { tone: "neutral" },
  },
);

/**
 * `role="status"` by default, announced politely; pass `role="alert"` for a
 * failure the person must hear at once. `icon` leads the text.
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
      <div className="grid min-w-0 flex-1 gap-0.5">{children}</div>
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
