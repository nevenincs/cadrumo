import { useState, type FocusEvent } from "react";
import type { EditorProps } from "@/components/editors/editorProps";
import { Input } from "@/components/ui/input";
import { useSuggestions } from "@/components/ui/suggestions";

export type EntryReading = {
  /** What a typed text holds, or null when it cannot be read: that text then
   * goes to the host as typed, so the host's refusal fires. */
  read(typed: string): string | null;
  /** How a held value looks when the field is not being typed in. */
  shown(value: string): string;
  /** How a held value looks once the person starts typing in it. */
  typed(value: string): string;
};

/** For text with nothing to read: the value is what was typed. */
export const PLAIN_READING: EntryReading = {
  read: (typed) => typed,
  shown: (value) => value,
  typed: (value) => value,
};

/**
 * The control under every text editor: it shows the held value in the window's
 * language and hands back canonical text at each keystroke, so a host that
 * commits on Enter has the same value as one that commits on blur. In `lexeme`
 * mode nothing is read or restyled: the text goes as typed for a backend to
 * read.
 */
export function EntryInput({
  value,
  onChange,
  onFocus,
  onBlur,
  invalid,
  required,
  describedBy,
  controlSize,
  mode = "normalise",
  suggestions,
  onPick,
  onSuggestionsWanted,
  opensEmpty,
  commitsOnPick,
  reading,
  type,
  ref,
  onKeyDown,
  onInput,
  ...native
}: EditorProps & {
  reading: EntryReading;
  type?: "text" | "email" | "tel" | "url" | "password";
}) {
  const [entry, setEntry] = useState<{ text: string; sent: string } | null>(
    null,
  );
  const lexeme = mode === "lexeme";
  const typedForm = lexeme ? value : reading.typed(value);
  // A value that changes from outside while typing replaces what was typed.
  if (entry && entry.sent !== value) setEntry({ text: typedForm, sent: value });
  const text = entry?.text ?? (lexeme ? value : reading.shown(value));
  const take = (typed: string) => {
    const sent = lexeme ? typed : (reading.read(typed) ?? typed);
    setEntry({ text: typed, sent });
    onChange(sent);
  };
  const offered = useSuggestions({
    value: text,
    options: suggestions ?? null,
    onPick: (picked, via) => {
      take(picked.value);
      onPick?.(picked, via);
    },
    onWanted: onSuggestionsWanted,
    opensEmpty,
    commitsOnPick,
  });
  const own = {
    ref,
    onKeyDown,
    onInput,
    onFocus: (event: FocusEvent<HTMLInputElement>) => {
      setEntry({ text: typedForm, sent: value });
      onFocus?.(event);
    },
    onBlur: (event: FocusEvent<HTMLInputElement>) => {
      setEntry(null);
      onBlur?.(event);
    },
  };
  return (
    <>
      <Input
        autoComplete="off"
        spellCheck={false}
        {...native}
        type={type}
        value={text}
        {...(suggestions === undefined ? own : offered.field(own))}
        onChange={(event) => take(event.target.value)}
        controlSize={controlSize}
        aria-invalid={invalid || undefined}
        aria-required={required || undefined}
        aria-describedby={describedBy}
      />
      {offered.list}
    </>
  );
}
