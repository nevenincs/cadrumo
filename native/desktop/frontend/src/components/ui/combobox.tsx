import * as React from "react";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { cn } from "@/components/ui/cn";
import { commitKeyOf, type CommitKey } from "@/components/ui/dataGridModel";
import { Icon } from "@/components/ui/icon";
import {
  Popover,
  PopoverAnchor,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";

type ComboboxOption = {
  value: string;
  label: string;
  /** The heading of the group it is listed under. */
  group?: string;
  /** A second line: what the option means, or why it cannot be chosen. */
  note?: string;
  disabled?: boolean;
  /** Why it cannot be chosen; shown in place of the note. */
  reason?: string;
};

type ComboboxProps = {
  /** Names the search field and the list. */
  label: string;
  value: string | null;
  options: readonly ComboboxOption[];
  /** The value chosen, and how: Enter, Tab either way, or the pointer. */
  onCommit: (value: string, via: CommitKey) => void;
  /** Left by Escape, or by a press outside it. */
  onCancel?: (via: "escape" | "outside") => void;
  /** Shown when no option matches what was typed. */
  emptyLabel: string;
  /** What was typed to open it, as the first search. */
  initialQuery?: string;
  placeholder?: string;
  hint?: React.ReactNode;
  error?: React.ReactNode;
  footer?: React.ReactNode;
  /** The trigger. Without one the list opens at once, over the positioned
   * element it is placed in, as a cell editor does. */
  children?: React.ReactElement;
  className?: string;
};

/**
 * A searchable choice: a list of options, grouped under headings, filtered
 * by what is typed. Arrow keys move through it, Enter chooses, Tab and
 * Shift+Tab choose and move on, and Escape leaves the value as it was.
 * The hint and the error are read with the field.
 */
/**
 * How well an option's words answer what was typed: a word that starts with
 * it first, then a word that holds it, and only then the letters scattered in
 * order, so a typed word never loses to a chance spelling. Zero hides it.
 */
export function optionScore(
  _value: string,
  search: string,
  keywords: readonly string[] = [],
): number {
  const query = search.trim().toLocaleLowerCase();
  if (query === "") return 1;
  const text = keywords.join(" ").toLocaleLowerCase();
  const words = text.split(/[^\p{L}\p{N}]+/u).filter(Boolean);
  if (words.some((word) => word.startsWith(query))) return 1;
  if (text.includes(query)) return 0.6;
  let at = 0;
  for (const letter of text) if (letter === query[at]) at += 1;
  return at === query.length ? 0.1 : 0;
}

function Combobox({
  label,
  value,
  options,
  onCommit,
  onCancel,
  emptyLabel,
  initialQuery,
  placeholder,
  hint,
  error,
  footer,
  children,
  className,
}: ComboboxProps) {
  const id = React.useId();
  const triggered = children !== undefined;
  const [open, setOpen] = React.useState(!triggered);
  const [highlight, setHighlight] = React.useState(value ?? "");
  const [query, setQuery] = React.useState(initialQuery ?? "");
  const pressed = React.useRef<CommitKey | null>(null);
  const escaped = React.useRef(false);
  // The popover closes on Escape before the key reaches the list, so the
  // key is noted on its way down, at the document.
  React.useEffect(() => {
    if (!open) return;
    const note = (event: KeyboardEvent) => {
      if (event.key === "Escape") escaped.current = true;
    };
    document.addEventListener("keydown", note, true);
    return () => document.removeEventListener("keydown", note, true);
  }, [open]);

  const groups = React.useMemo(() => {
    const out: { heading: string | undefined; options: ComboboxOption[] }[] =
      [];
    for (const option of options) {
      const last = out.find((group) => group.heading === option.group);
      if (last) last.options.push(option);
      else out.push({ heading: option.group, options: [option] });
    }
    return out;
  }, [options]);

  const close = () => {
    if (triggered) setOpen(false);
  };
  const choose = (chosen: string, via: CommitKey) => {
    const option = options.find((entry) => entry.value === chosen);
    if (!option || option.disabled) return;
    close();
    setQuery("");
    onCommit(option.value, via);
  };
  const cancel = () => {
    close();
    setQuery("");
    onCancel?.(escaped.current ? "escape" : "outside");
    escaped.current = false;
  };

  const described = [hint ? `${id}-hint` : null, error ? `${id}-error` : null]
    .filter(Boolean)
    .join(" ");

  return (
    <Popover
      open={open}
      onOpenChange={(next) => {
        if (next) setOpen(true);
        else cancel();
      }}
    >
      {triggered ? (
        <PopoverTrigger asChild>{children}</PopoverTrigger>
      ) : (
        <PopoverAnchor asChild>
          <span aria-hidden="true" className="absolute inset-0" />
        </PopoverAnchor>
      )}
      <PopoverContent
        align="start"
        sideOffset={4}
        data-slot="combobox"
        // Never narrower than the field that opened it.
        className={cn(
          "flex w-field min-w-(--radix-popover-trigger-width) flex-col overflow-hidden p-0",
          className,
        )}
        // A cell editor hands focus back to its grid, which chooses the cell.
        onCloseAutoFocus={(event) => {
          if (!triggered) event.preventDefault();
        }}
      >
        <Command
          label={label}
          value={highlight}
          onValueChange={setHighlight}
          // Its Control-letter movement keys would take the shell's chords.
          vimBindings={false}
          filter={optionScore}
          className="min-h-0"
          onKeyDownCapture={(event) => {
            const how = commitKeyOf(event);
            // Only the press that chooses an option names how it was chosen:
            // an Enter on an empty list is forgotten at the next key.
            pressed.current = how === "enter" ? "enter" : null;
            if (how !== "tab" && how !== "shift-tab") return;
            event.preventDefault();
            event.stopPropagation();
            choose(highlight, how);
          }}
        >
          <CommandInput
            autoFocus
            value={query}
            onValueChange={setQuery}
            placeholder={placeholder}
            aria-describedby={described || undefined}
            aria-invalid={error ? true : undefined}
          />
          {(hint || error) && (
            <div className="grid gap-1 border-b px-3.5 py-2 text-sm">
              {error && (
                <p
                  id={`${id}-error`}
                  className="flex items-center gap-1.5 text-foreground"
                >
                  <Icon name="alert" size="xs" className="text-destructive" />
                  {error}
                </p>
              )}
              {hint && (
                <p id={`${id}-hint`} className="text-muted-foreground">
                  {hint}
                </p>
              )}
            </div>
          )}
          <CommandList label={label} className="max-h-72">
            <CommandEmpty>{emptyLabel}</CommandEmpty>
            {groups.map((group) => (
              <CommandGroup key={group.heading ?? ""} heading={group.heading}>
                {group.options.map((option) => (
                  <CommandItem
                    key={option.value}
                    value={option.value}
                    keywords={[option.label, option.note ?? ""]}
                    disabled={option.disabled}
                    onPointerDown={() => {
                      pressed.current = null;
                    }}
                    onSelect={(chosen) => {
                      const via = pressed.current ?? "pointer";
                      pressed.current = null;
                      choose(chosen, via);
                    }}
                    className="min-h-control-md py-1.5"
                  >
                    <span className="grid min-w-0 flex-1">
                      <span className="[overflow-wrap:anywhere]">
                        {option.label}
                      </span>
                      {(option.reason ?? option.note) && (
                        <span className="text-sm text-muted-foreground">
                          {option.reason ?? option.note}
                        </span>
                      )}
                    </span>
                    {option.value === value && (
                      <Icon name="tick" size="sm" className="text-foreground" />
                    )}
                  </CommandItem>
                ))}
              </CommandGroup>
            ))}
          </CommandList>
          {footer && <div className="border-t p-1.5">{footer}</div>}
        </Command>
      </PopoverContent>
    </Popover>
  );
}

export { Combobox, type ComboboxOption, type ComboboxProps };
