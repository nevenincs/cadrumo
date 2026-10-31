/**
 * What every data-entry editor takes. An editor is a controlled text control:
 * it holds canonical text, or the raw lexeme while that is unread, and it draws
 * no error. Its host puts the words in `FieldError` and passes `invalid` and
 * `describedBy`.
 */
export type EditorProps = {
  value: string;
  onChange(value: string): void;
  id?: string;
  invalid?: boolean;
  describedBy?: string;
  disabled?: boolean;
  controlSize?: "sm" | "md";
  /** `lexeme` sends what was typed, for a backend that does the reading. */
  mode?: "normalise" | "lexeme";
};
