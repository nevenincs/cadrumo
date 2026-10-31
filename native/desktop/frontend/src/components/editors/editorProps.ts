import type { ComponentPropsWithRef } from "react";

/** The native attributes an editor hands to its text control, and its ref. */
type NativeProps<Tag extends "input" | "textarea"> = Omit<
  ComponentPropsWithRef<Tag>,
  "value" | "defaultValue" | "onChange" | "type" | "size" | "list"
>;

type HeldText = {
  value: string;
  onChange(value: string): void;
  invalid?: boolean;
  describedBy?: string;
  controlSize?: "sm" | "md";
  /** `lexeme` sends what was typed, for a backend that does the reading. */
  mode?: "normalise" | "lexeme";
};

/**
 * What every data-entry editor takes. An editor is a controlled text control:
 * it holds canonical text, or the raw lexeme while that is unread, and it draws
 * no error. Its host puts the words in `FieldError` and passes `invalid` and
 * `describedBy`. Any other input attribute, such as `aria-label`, `autoFocus`,
 * `onBlur`, `onKeyDown`, `className`, `data-*` or a ref, goes to the text box;
 * `required` is said to assistive technology and the host still checks it.
 */
export type EditorProps = HeldText &
  NativeProps<"input"> & {
    /** Text the person may pick instead of typing; picking is the same as
     * typing it. */
    suggestions?: readonly string[];
  };

/** The same, over several lines. */
export type NotesEditorProps = Omit<HeldText, "mode"> & NativeProps<"textarea">;
