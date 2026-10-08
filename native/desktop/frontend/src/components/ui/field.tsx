import * as React from "react";
import { cn } from "@/components/ui/cn";
import { Icon } from "@/components/ui/icon";
import { Label } from "@/components/ui/label";

/**
 * One labelled control with its description and error. Mark it invalid or
 * disabled here, with `data-invalid` or `data-disabled`, and its label follows.
 */
function Field({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      role="group"
      data-slot="field"
      className={cn("group/field flex w-full flex-col gap-1.5", className)}
      {...props}
    />
  );
}

function FieldLabel({
  className,
  ...props
}: React.ComponentProps<typeof Label>) {
  return (
    <Label
      data-slot="field-label"
      className={cn(
        "w-fit group-data-[invalid=true]/field:text-destructive",
        className,
      )}
      {...props}
    />
  );
}

function FieldDescription({ className, ...props }: React.ComponentProps<"p">) {
  return (
    <p
      data-slot="field-description"
      className={cn("text-sm text-muted-foreground", className)}
      {...props}
    />
  );
}

/**
 * The reason a field's value was not accepted, marked by an icon as well as
 * its colour. It renders nothing when empty.
 */
function FieldError({
  className,
  children,
  ...props
}: React.ComponentProps<"p">) {
  if (!children) return null;
  return (
    <p
      role="alert"
      data-slot="field-error"
      className={cn(
        "flex items-start gap-1.5 text-sm text-destructive",
        className,
      )}
      {...props}
    >
      <Icon name="alert" size="xs" className="mt-0.5" />
      <span>{children}</span>
    </p>
  );
}

export { Field, FieldDescription, FieldError, FieldLabel };
