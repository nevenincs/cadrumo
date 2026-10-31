import { useId, useState } from "react";
import type { EditorProps } from "@/components/editors/editorProps";
import { Input } from "@/components/ui/input";

export type EntryReading = {
  /** What a typed text holds, or null when it cannot be read: that text then
   * goes to the host as typed, so the host's refusal fires. */
  read(typed: string): string | null;
  /** How a held value looks when the field is not being typed in. */
  shown(value: string): string;
  /** How a held value looks once the person starts typing in it. */
  typed(value: string): string;
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
  reading,
  type,
  ...native
}: EditorProps & {
  reading: EntryReading;
  type?: "text" | "email" | "tel" | "url";
}) {
  const list = useId();
  const [entry, setEntry] = useState<{ text: string; sent: string } | null>(
    null,
  );
  const lexeme = mode === "lexeme";
  const typedForm = lexeme ? value : reading.typed(value);
  // A value that changes from outside while typing replaces what was typed.
  if (entry && entry.sent !== value) setEntry({ text: typedForm, sent: value });
  const text = entry?.text ?? (lexeme ? value : reading.shown(value));
  return (
    <>
      <Input
        autoComplete="off"
        spellCheck={false}
        {...native}
        type={type}
        value={text}
        onFocus={(event) => {
          setEntry({ text: typedForm, sent: value });
          onFocus?.(event);
        }}
        onBlur={(event) => {
          setEntry(null);
          onBlur?.(event);
        }}
        onChange={(event) => {
          const typed = event.target.value;
          const sent = lexeme ? typed : (reading.read(typed) ?? typed);
          setEntry({ text: typed, sent });
          onChange(sent);
        }}
        controlSize={controlSize}
        aria-invalid={invalid || undefined}
        aria-required={required || undefined}
        aria-describedby={describedBy}
        list={suggestions ? list : undefined}
      />
      {suggestions && (
        <datalist id={list}>
          {suggestions.map((suggestion) => (
            <option key={suggestion} value={suggestion} />
          ))}
        </datalist>
      )}
    </>
  );
}
