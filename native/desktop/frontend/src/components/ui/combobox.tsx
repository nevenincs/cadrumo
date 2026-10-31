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
  /** More words it is found by, never shown: such as the words a bank
   * statement uses for it. */
  keywords?: readonly string[];
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
/** Text as it is compared: lower case, without accents, so "telefono"
 * finds "Teléfono". */
const folded = (text: string) =>
  text.normalize("NFD").replace(/\p{M}/gu, "").toLocaleLowerCase();

/** The score of a scattered-letter match, which counts only where nothing
 * matches better. */
const SCATTERED = 0.1;

/**
 * How well an option answers what was typed: its name starting with it
 * first, then any of its words starting with it, then its words holding
 * it, and only then its letters scattered in order. Case and accents are
 * ignored. Zero hides it. `words` are its name first, then the rest.
 */
export function optionScore(
  search: string,
  words: readonly string[] = [],
): number {
  const query = folded(search.trim());
  if (query === "") return 1;
  const name = folded(words[0] ?? "");
  const text = words.map(folded).join(" ");
  if (name.startsWith(query)) return 1;
  const parts = text.split(/[^\p{L}\p{N}]+/u).filter(Boolean);
  if (parts.some((part) => part.startsWith(query))) return 0.8;
  if (text.includes(query)) return 0.6;
  let at = 0;
  for (const letter of text) if (letter === query[at]) at += 1;
  return at === query.length ? SCATTERED : 0;
}

/**
 * The options that answer `search`, best first: a scattered-letter match
 * is dropped where any option matches better, the groups follow their best
 * option, and within a group the options follow their score. Ties keep
 * their given order.
 */
export function rankOptions<Option extends ComboboxOption>(
  options: readonly Option[],
  search: string,
): { heading: string | undefined; options: Option[] }[] {
  const scored = options
    .map((option, at) => ({
      option,
      at,
      score: optionScore(search, [
        option.label,
        option.note ?? "",
        ...(option.keywords ?? []),
      ]),
    }))
    .filter((entry) => entry.score > 0);
  const better = scored.some((entry) => entry.score > SCATTERED);
  const kept = better
    ? scored.filter((entry) => entry.score > SCATTERED)
    : scored;
  const groups: {
    heading: string | undefined;
    best: number;
    first: number;
    entries: typeof kept;
  }[] = [];
  for (const entry of kept) {
    const group = groups.find((found) => found.heading === entry.option.group);
    if (group) {
      group.entries.push(entry);
      group.best = Math.max(group.best, entry.score);
    } else
      groups.push({
        heading: entry.option.group,
        best: entry.score,
        first: entry.at,
        entries: [entry],
      });
  }
  return groups
    .sort((left, right) => right.best - left.best || left.first - right.first)
    .map((group) => ({
      heading: group.heading,
      options: group.entries
        .sort((left, right) => right.score - left.score || left.at - right.at)
        .map((entry) => entry.option),
    }));
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

  // The list is ranked here, not by the command list, so a scattered
  // match can give way to a better one elsewhere in the list.
  const groups = React.useMemo(
    () => rankOptions(options, query),
    [options, query],
  );
  const first =
    groups.flatMap((group) => group.options).find((option) => !option.disabled)
      ?.value ?? "";
  // What is typed moves the highlight to the best answer.
  React.useEffect(() => {
    if (query.trim() !== "") setHighlight(first);
  }, [query, first]);

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
          shouldFilter={false}
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
