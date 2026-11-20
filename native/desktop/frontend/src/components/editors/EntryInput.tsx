import {
  useLayoutEffect,
  useRef,
  useState,
  type ChangeEvent,
  type FocusEvent,
} from "react";
import { flushSync } from "react-dom";
import type { EditorProps } from "@/components/editors/editorProps";
import { Input } from "@/components/ui/input";
import { useSuggestions } from "@/components/ui/suggestions";

export type EntryReading = {
  /** What a typed text holds, or null when it cannot be read: that text then
   * goes to the host as typed, so the host's refusal fires. */
  read(typed: string): string | null;
  /** How typed text is restyled in the box as it is typed, when it is: a
   * code is shown in capitals at once. Text it cannot restyle stays as typed. */
  echo?(typed: string): string;
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
  onPointerDown,
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
  // A value set while the box is not being typed in, by assistive technology
  // or an automation driver, is held at once and the box shows it as any held
  // value is shown: nothing typed remains to keep.
  const take = (typed: string, typing = true) => {
    const sent = lexeme ? typed : (reading.read(typed) ?? typed);
    setEntry(typing ? { text: typed, sent } : null);
    onChange(sent);
  };
  // Restyled text puts the caret at the end of the box; it goes back to where
  // the person was typing, and a selection of the whole text stays whole.
  const caret = useRef<{
    box: HTMLInputElement;
    from: number;
    to: number;
  } | null>(null);
  useLayoutEffect(() => {
    const held = caret.current;
    caret.current = null;
    if (held && document.activeElement === held.box)
      held.box.setSelectionRange(held.from, held.to);
  });
  const typedIn = (event: ChangeEvent<HTMLInputElement>) => {
    const typed = event.target.value;
    const typing = document.activeElement === event.target;
    const echoed = lexeme ? typed : (reading.echo?.(typed) ?? typed);
    if (typing && echoed !== typed) {
      const before = event.target.selectionStart ?? typed.length;
      const at = reading.echo!(typed.slice(0, before)).length;
      caret.current = { box: event.target, from: at, to: at };
    }
    take(echoed, typing);
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
  // Whether the focus under way comes from a press on the box.
  const pressed = useRef(false);
  const own = {
    ref,
    onKeyDown,
    onInput,
    onFocus: (event: FocusEvent<HTMLInputElement>) => {
      // Focus swaps the shown text for its typed form, and a new text in the
      // box drops the selection. Focus that no pointer placed, by the keyboard,
      // assistive technology or an automation driver's fill, takes the whole
      // typed form, so that what comes next replaces it; a press places its
      // own caret after the focus. The swap happens within the focus, so a
      // selection made just after it applies to the typed form.
      const box = event.currentTarget;
      if (!pressed.current && box.value !== typedForm)
        caret.current = { box, from: 0, to: typedForm.length };
      pressed.current = false;
      flushSync(() => setEntry({ text: typedForm, sent: value }));
      onFocus?.(event);
    },
    onBlur: (event: FocusEvent<HTMLInputElement>) => {
      pressed.current = false;
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
        onPointerDown={(event) => {
          if (document.activeElement !== event.currentTarget)
            pressed.current = true;
          onPointerDown?.(event);
        }}
        type={type}
        value={text}
        {...(suggestions === undefined ? own : offered.field(own))}
        onChange={typedIn}
        controlSize={controlSize}
        aria-invalid={invalid || undefined}
        aria-required={required || undefined}
        aria-describedby={describedBy}
      />
      {offered.list}
    </>
  );
}
