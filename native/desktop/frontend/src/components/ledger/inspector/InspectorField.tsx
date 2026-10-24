import { useId, useRef, useState, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Combobox, type ComboboxOption } from "@/components/ui/combobox";
import { Icon } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useStrings } from "../../../shell/strings";

/** What a typed value stages: a value, a clear, or why it is refused. */
export type FieldParse =
  | { kind: "value"; value: string }
  | { kind: "clear" }
  | {
      kind: "refused";
      message: string;
      /** The value the refusal names as meant, which the person can take
       * in one press; it is never taken for them. */
      suggestion?: string;
    };

export type FieldEditor =
  | {
      kind: "input";
      /** The text the editor opens with: the value in its canonical
       * spelling. */
      initial: string;
      parse: (raw: string) => FieldParse;
      hint?: string;
      inputMode?: "decimal" | "text";
    }
  | {
      kind: "choice";
      value: string | null;
      options: readonly ComboboxOption[];
      /** The choice that clears the field, where it can be cleared. */
      clear?: string;
    };

/** The value the clear choice is listed under; no option takes it. */
const CLEAR = "\u0000clear";

/**
 * One fact of a movement in the inspector: its name, and its value as a
 * button that edits it. A list opens as a combobox, which moves without
 * choosing and hands focus back to the value once chosen; anything else
 * is typed in place, Enter stages it and Escape leaves it. A value that
 * cannot change says why. What it stages is not saved.
 */
export function InspectorField({
  label,
  field,
  shown,
  was,
  note,
  lock,
  editor,
  onCommit,
}: {
  label: string;
  field: string;
  /** The value as it will be once saved, as text. */
  shown: ReactNode;
  /** The stored value, where a staged change replaces it. */
  was?: string | null;
  /** A line under the value: a staged change's consequence. */
  note?: ReactNode;
  /** Why the value cannot change, or null where it can. */
  lock?: string | null;
  editor?: FieldEditor;
  onCommit?: (value: string | null) => void;
}) {
  const t = useStrings();
  const id = useId();
  const button = useRef<HTMLButtonElement>(null);
  const [typing, setTyping] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [suggestion, setSuggestion] = useState<string | null>(null);
  const editable = !lock && editor !== undefined && onCommit !== undefined;
  const changed = was !== undefined;

  const refocus = () => window.setTimeout(() => button.current?.focus(), 0);
  const commitTyped = (raw: string) => {
    if (!editor || editor.kind !== "input" || !onCommit) return;
    if (raw === editor.initial) {
      setTyping(null);
      setError(null);
      refocus();
      return;
    }
    const parsed = editor.parse(raw);
    if (parsed.kind === "refused") {
      setError(parsed.message);
      setSuggestion(parsed.suggestion ?? null);
      return;
    }
    setSuggestion(null);
    setTyping(null);
    setError(null);
    onCommit(parsed.kind === "clear" ? null : parsed.value);
    refocus();
  };

  const value = (
    <span className="grid min-w-0 text-left">
      {changed && (
        <span className="text-sm text-muted-foreground line-through">
          {was ?? t("desktop.ledger.inspector.empty")}
        </span>
      )}
      <span className={changed ? "font-medium break-words" : "break-words"}>
        {shown}
      </span>
    </span>
  );
  const trigger = (
    <Button
      ref={button}
      variant="ghost"
      size="sm"
      data-field={field}
      aria-labelledby={`${id}-label ${id}-value`}
      aria-describedby={lock ? `${id}-lock` : undefined}
      aria-disabled={editable ? undefined : true}
      aria-haspopup={
        editable && editor?.kind === "choice" ? "listbox" : undefined
      }
      className="ledger-field-value h-auto min-h-control-sm w-full justify-start px-1.5 py-0.5 text-foreground whitespace-normal aria-disabled:cursor-default aria-disabled:hover:bg-transparent"
      onClick={(event) => {
        if (!editable) {
          event.preventDefault();
          return;
        }
        if (editor!.kind === "input") {
          setTyping(editor!.initial);
          setError(null);
        }
      }}
      onKeyDown={(event) => {
        // F2 types a new value, as it does in the grid.
        if (
          editable &&
          editor?.kind === "input" &&
          event.key === "F2" &&
          !event.altKey
        ) {
          event.preventDefault();
          setTyping(editor.initial);
        }
      }}
    >
      <span id={`${id}-value`} className="contents">
        {value}
      </span>
      {lock && (
        <Icon name="lock" size="xs" className="ml-auto text-muted-foreground" />
      )}
    </Button>
  );

  let body: ReactNode;
  if (typing !== null && editor?.kind === "input")
    body = (
      <div className="grid gap-1">
        <Input
          controlSize="sm"
          autoFocus
          value={typing}
          inputMode={editor.inputMode}
          aria-labelledby={`${id}-label`}
          aria-invalid={error ? true : undefined}
          aria-describedby={error || editor.hint ? `${id}-hint` : undefined}
          onChange={(event) => {
            setTyping(event.target.value);
            setError(null);
          }}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              commitTyped(typing);
            } else if (event.key === "Escape") {
              event.preventDefault();
              event.stopPropagation();
              setTyping(null);
              setError(null);
              refocus();
            }
          }}
          onBlur={() => {
            if (typing === editor.initial) setTyping(null);
            else commitTyped(typing);
          }}
        />
        {(error || editor.hint) && (
          <span
            id={`${id}-hint`}
            className={
              error
                ? "text-sm text-foreground"
                : "text-xs text-muted-foreground"
            }
          >
            {error && (
              <Icon
                name="alert"
                size="xs"
                className="mr-1 inline text-destructive"
              />
            )}
            {error ?? editor.hint}
          </span>
        )}
        {error && suggestion !== null && (
          <Button
            type="button"
            variant="outline"
            size="xs"
            className="ledger-field-suggestion w-fit"
            // The field keeps focus, so leaving it does not try the
            // refused text again.
            onPointerDown={(event) => event.preventDefault()}
            onClick={() => {
              setTyping(suggestion);
              commitTyped(suggestion);
            }}
          >
            {t("desktop.ledger.edit.refusal.use", { suggestion })}
          </Button>
        )}
      </div>
    );
  else if (editable && editor?.kind === "choice")
    body = (
      <Combobox
        label={label}
        value={editor.value}
        options={
          editor.clear
            ? [{ value: CLEAR, label: editor.clear }, ...editor.options]
            : editor.options
        }
        emptyLabel={t("desktop.ledger.inspector.no_match")}
        onCommit={(chosen) => {
          const next = chosen === CLEAR ? null : chosen;
          if (next !== editor.value) onCommit!(next);
        }}
      >
        {trigger}
      </Combobox>
    );
  else if (lock)
    body = (
      <Tooltip>
        <TooltipTrigger asChild>{trigger}</TooltipTrigger>
        <TooltipContent>{lock}</TooltipContent>
      </Tooltip>
    );
  else body = trigger;

  return (
    <>
      <dt id={`${id}-label`} className="pt-1 text-sm text-muted-foreground">
        {label}
      </dt>
      <dd className="min-w-0">
        {body}
        {lock && (
          <span id={`${id}-lock`} className="sr-only">
            {lock}
          </span>
        )}
        {note && (
          <div className="px-1.5 text-xs text-muted-foreground">{note}</div>
        )}
      </dd>
    </>
  );
}
