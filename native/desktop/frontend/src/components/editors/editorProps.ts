import type { ComponentPropsWithRef } from "react";
import type { Suggestion } from "@/components/ui/suggestions";
import type { CommitKey } from "@/components/ui/dataGridModel";

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

/** Text the person may pick instead of typing. A pick reaches `onChange` the
 * way typing does; a secret field takes none of this. */
export type SuggestionProps = {
  /** Null while unread or failed: no list, and the field stays free. */
  suggestions?: readonly Suggestion[] | null;
  /** Called after `onChange`, so the host can fill the fields beside this. */
  onPick?(picked: Suggestion, via: CommitKey): void;
  /** Called at each focus, so a read happens only when wanted. */
  onSuggestionsWanted?(): void;
  /** Opens on focus with nothing typed, for a short list. */
  opensEmpty?: boolean;
  /** The host moves on by itself when a pick is made, as a grid cell does, so
   * Tab must not also move focus. */
  commitsOnPick?: boolean;
};

/**
 * What every data-entry editor takes. An editor is a controlled text control:
 * it holds canonical text, or the raw lexeme while that is unread, and it draws
 * no error. Its host puts the words in `FieldError` and passes `invalid` and
 * `describedBy`. Any other input attribute, such as `aria-label`, `autoFocus`,
 * `onBlur`, `onKeyDown`, `className`, `data-*` or a ref, goes to the text box;
 * `required` is said to assistive technology and the host still checks it.
 */
export type EditorProps = HeldText & NativeProps<"input"> & SuggestionProps;

/** The same, over several lines. */
export type NotesEditorProps = Omit<HeldText, "mode"> & NativeProps<"textarea">;
