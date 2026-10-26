import { useId, type ReactElement, type ReactNode } from "react";
import { cn } from "@/components/ui/cn";
import {
  Field,
  FieldDescription,
  FieldError,
  FieldLabel,
} from "@/components/ui/field";
import { Icon } from "@/components/ui/icon";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

/** What a control inside a field is given: its id, its description and
 * whether its value was refused. */
export type ControlProps = {
  id: string;
  "aria-describedby"?: string;
  "aria-invalid"?: true;
  "aria-required"?: true;
};

/**
 * One labelled field of the invoice editor. The control is drawn by
 * `children` with the props it is handed, so its hint and its refusal are
 * read with it, and a refusal shows on the field it is about.
 */
export function FormField({
  label,
  hint,
  error,
  required,
  className,
  children,
}: {
  label: string;
  hint?: ReactNode;
  error?: string | null;
  required?: boolean;
  className?: string;
  children: (control: ControlProps) => ReactElement;
}) {
  const id = useId();
  const described = [hint ? `${id}-hint` : null, error ? `${id}-error` : null]
    .filter(Boolean)
    .join(" ");
  return (
    <Field data-invalid={error ? true : undefined} className={className}>
      <FieldLabel htmlFor={id}>{label}</FieldLabel>
      {children({
        id,
        ...(described ? { "aria-describedby": described } : {}),
        ...(error ? { "aria-invalid": true as const } : {}),
        ...(required ? { "aria-required": true as const } : {}),
      })}
      {hint && <FieldDescription id={`${id}-hint`}>{hint}</FieldDescription>}
      {error && <FieldError id={`${id}-error`}>{error}</FieldError>}
    </Field>
  );
}

/** A stored value that cannot be changed here, with why in its tooltip
 * and its accessible description. */
export function FixedField({
  label,
  value,
  reason,
  mono,
  className,
}: {
  label: string;
  value: ReactNode;
  reason: string;
  mono?: boolean;
  className?: string;
}) {
  const id = useId();
  return (
    <div
      role="group"
      aria-labelledby={`${id}-label`}
      aria-describedby={`${id}-reason`}
      className={cn("flex min-w-0 flex-col gap-1.5", className)}
      data-fixed=""
    >
      <span
        id={`${id}-label`}
        className="text-sm font-medium text-muted-foreground"
      >
        {label}
      </span>
      <Tooltip>
        <TooltipTrigger asChild>
          <span
            tabIndex={0}
            className={cn(
              "flex min-h-control-md w-fit max-w-full items-center gap-1.5 rounded-md text-base text-foreground",
              mono && "font-mono text-sm",
            )}
          >
            <span className="min-w-0 [overflow-wrap:anywhere]">{value}</span>
            <Icon
              name="lock"
              size="xs"
              className="shrink-0 text-muted-foreground"
            />
          </span>
        </TooltipTrigger>
        <TooltipContent>{reason}</TooltipContent>
      </Tooltip>
      <span id={`${id}-reason`} className="sr-only">
        {reason}
      </span>
    </div>
  );
}

/** A titled part of the editor. */
export function EditorSection({
  title,
  aside,
  children,
}: {
  title: string;
  aside?: ReactNode;
  children: ReactNode;
}) {
  const id = useId();
  return (
    <section aria-labelledby={id} className="flex flex-col gap-3">
      <h3
        id={id}
        className="flex items-center gap-2 text-xs font-medium tracking-wide text-muted-foreground uppercase"
      >
        {title}
        {aside && <span className="ml-auto normal-case">{aside}</span>}
      </h3>
      {children}
    </section>
  );
}
