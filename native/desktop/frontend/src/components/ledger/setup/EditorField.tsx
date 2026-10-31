import { useId, type ReactNode } from "react";
import {
  Field,
  FieldDescription,
  FieldError,
  FieldLabel,
} from "@/components/ui/field";

/** What a typed editor needs from the field around it. */
export type EditorControl = {
  id: string;
  invalid: boolean;
  describedBy: string | undefined;
};

/** A labelled field around a typed editor: the label names the fact, the
 * reason it was refused sits under it, and the editor gets the wiring that
 * joins them. */
export function EditorField({
  label,
  hint,
  error,
  className,
  children,
}: {
  label: string;
  hint?: string;
  error?: string | null;
  className?: string;
  children(control: EditorControl): ReactNode;
}) {
  const id = useId();
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  return (
    <Field data-invalid={error ? true : undefined} className={className}>
      <FieldLabel htmlFor={id}>{label}</FieldLabel>
      {children({
        id,
        invalid: Boolean(error),
        describedBy:
          [hint ? hintId : null, error ? errorId : null]
            .filter(Boolean)
            .join(" ") || undefined,
      })}
      {hint && <FieldDescription id={hintId}>{hint}</FieldDescription>}
      <FieldError id={errorId}>{error}</FieldError>
    </Field>
  );
}
