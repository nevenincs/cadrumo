import * as React from "react";
import { cn } from "@/components/ui/cn";
import { rankOptions, type ComboboxOption } from "@/components/ui/combobox";
import { commandItemClass } from "@/components/ui/command";
import type { CommitKey } from "@/components/ui/dataGridModel";
import { Input } from "@/components/ui/input";
import {
  Popover,
  PopoverAnchor,
  PopoverContent,
} from "@/components/ui/popover";

export type Suggestion = ComboboxOption & {
  /** What a pick offers the fields beside this one, by the host's field key.
   * The host fills only what the person left empty. */
  fills?: Readonly<Record<string, string>>;
};

/** The most a list shows at once. */
const SHOWN = 8;

/** What the list shows for `value`: the best answers, best first, and nothing
 * where the one answer is what the field already holds. */
export function shownSuggestions(
  options: readonly Suggestion[],
  value: string,
): Suggestion[] {
  const ranked = rankOptions(options, value)
    .flatMap((group) => group.options)
    .filter((option) => !option.disabled)
    .slice(0, SHOWN);
  const only = ranked[0];
  return ranked.length === 1 && only?.value === value ? [] : ranked;
}

type OwnField = Pick<
  React.ComponentProps<"input">,
  "ref" | "onFocus" | "onBlur" | "onInput" | "onKeyDown"
>;

export type SuggestionsInput = {
  value: string;
  /** Null while unread or failed: no list, and the field stays free. */
  options: readonly Suggestion[] | null;
  /** Called once a pick is made; the host writes the value and any fills. */
  onPick(picked: Suggestion, via: CommitKey): void;
  /** Called at each focus, so a read happens only when wanted. */
  onWanted?(): void;
  /** Opens on focus with nothing typed, for a short list such as series. */
  opensEmpty?: boolean;
  /** The host moves on by itself when a pick is made, as a grid cell does, so
   * Tab must not also move focus. */
  commitsOnPick?: boolean;
};

/**
 * Offers text for any input while the input stays the field: focus never
 * leaves it and what was typed is kept unless an option is chosen. Nothing is
 * highlighted until an arrow key is pressed, so Enter and Tab keep what was
 * typed; with a highlight, Enter and Tab choose it. Escape closes the list and
 * stops there. Spread `field(own)` on the input, passing the handlers it has,
 * and render `list` beside it.
 */
export function useSuggestions({
  value,
  options,
  onPick,
  onWanted,
  opensEmpty = false,
  commitsOnPick = false,
}: SuggestionsInput) {
  const id = React.useId();
  const anchor = React.useRef<HTMLInputElement | null>(null);
  const [open, setOpen] = React.useState(false);
  const [highlight, setHighlight] = React.useState(-1);
  const shown = React.useMemo(
    () => (options ? shownSuggestions(options, value) : []),
    [options, value],
  );
  const showing = open && shown.length > 0;
  const at = showing && highlight < shown.length ? highlight : -1;

  const close = () => {
    setOpen(false);
    setHighlight(-1);
  };
  const pick = (picked: Suggestion, via: CommitKey) => {
    close();
    onPick(picked, via);
  };

  const takeKey = (event: React.KeyboardEvent<HTMLInputElement>): boolean => {
    if (event.nativeEvent.isComposing) return false;
    const plain =
      !event.altKey && !event.ctrlKey && !event.metaKey && !event.shiftKey;
    if ((event.key === "ArrowDown" || event.key === "ArrowUp") && plain) {
      if (shown.length === 0) return false;
      event.preventDefault();
      event.stopPropagation();
      setOpen(true);
      setHighlight(
        event.key === "ArrowDown"
          ? (at + 1) % shown.length
          : at <= 0
            ? shown.length - 1
            : at - 1,
      );
      return true;
    }
    if (!showing) return false;
    if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      close();
      return true;
    }
    const chosen = at >= 0 ? shown[at] : undefined;
    if (!chosen) return false;
    if (event.key === "Enter" && plain) {
      event.preventDefault();
      event.stopPropagation();
      pick(chosen, "enter");
      return true;
    }
    if (event.key === "Tab" && !event.altKey && !event.ctrlKey) {
      if (commitsOnPick) event.preventDefault();
      event.stopPropagation();
      pick(chosen, event.shiftKey ? "shift-tab" : "tab");
      return true;
    }
    return false;
  };

  /** What to spread on the input, with the handlers it already has. */
  const field = (own: OwnField = {}) => ({
    role: "combobox" as const,
    "aria-autocomplete": "list" as const,
    "aria-expanded": showing,
    "aria-controls": showing ? id : undefined,
    "aria-activedescendant": at >= 0 ? `${id}-${at}` : undefined,
    ref: (node: HTMLInputElement | null) => {
      anchor.current = node;
      const { ref } = own;
      if (typeof ref === "function") ref(node);
      else if (ref) ref.current = node;
    },
    onFocus: (event: React.FocusEvent<HTMLInputElement>) => {
      onWanted?.();
      if (opensEmpty && value === "") setOpen(true);
      own.onFocus?.(event);
    },
    onBlur: (event: React.FocusEvent<HTMLInputElement>) => {
      close();
      own.onBlur?.(event);
    },
    onInput: (event: React.InputEvent<HTMLInputElement>) => {
      setOpen(opensEmpty || event.currentTarget.value !== "");
      setHighlight(-1);
      own.onInput?.(event);
    },
    onKeyDown: (event: React.KeyboardEvent<HTMLInputElement>) => {
      if (!takeKey(event)) own.onKeyDown?.(event);
    },
  });

  const list = showing ? (
    <Popover open onOpenChange={(next) => !next && close()}>
      <PopoverAnchor virtualRef={anchor as React.RefObject<HTMLElement>} />
      <PopoverContent
        align="start"
        sideOffset={2}
        data-slot="suggestions"
        className="w-auto max-w-prose min-w-(--radix-popover-trigger-width) p-0"
        onOpenAutoFocus={(event) => event.preventDefault()}
        onCloseAutoFocus={(event) => event.preventDefault()}
        // The field's own keys decide Escape, so it closes this and no more.
        onEscapeKeyDown={(event) => event.preventDefault()}
        onInteractOutside={(event) => {
          if (event.target === anchor.current) event.preventDefault();
        }}
      >
        <SuggestionList
          id={id}
          field={anchor}
          shown={shown}
          at={at}
          onHover={setHighlight}
          onChoose={(option) => pick(option, "pointer")}
        />
      </PopoverContent>
    </Popover>
  ) : null;

  return { field, takeKey, list };
}

function SuggestionList({
  id,
  field,
  shown,
  at,
  onHover,
  onChoose,
}: {
  id: string;
  field: React.RefObject<HTMLInputElement | null>;
  shown: readonly Suggestion[];
  at: number;
  onHover(at: number): void;
  onChoose(option: Suggestion): void;
}) {
  const [name, setName] = React.useState<string>();
  // The list takes the name of the field it serves, however that is named.
  React.useLayoutEffect(() => {
    const input = field.current;
    const labelledBy = input?.getAttribute("aria-labelledby");
    setName(
      input?.getAttribute("aria-label") ??
        (labelledBy
          ? document.getElementById(labelledBy.split(" ")[0]!)?.textContent
          : input?.labels?.[0]?.textContent) ??
        undefined,
    );
  }, [field]);
  // A press in the list must not take focus from the field: a cell editor
  // keeps its entry on blur, and a scrollbar counts as a press too.
  const keepFocus = (event: React.SyntheticEvent) => {
    event.preventDefault();
    event.stopPropagation();
  };
  return (
    <ul
      id={id}
      role="listbox"
      aria-label={name}
      className="max-h-72 overflow-y-auto p-1.5"
      onPointerDown={keepFocus}
      onMouseDown={keepFocus}
    >
      {shown.map((option, index) => (
        <li
          // Two options can write one text: a name held under two tax ids.
          key={`${option.value}:${option.note ?? ""}`}
          id={`${id}-${index}`}
          role="option"
          aria-selected={index === at}
          data-selected={index === at}
          className={cn(commandItemClass, "min-h-control-md py-1.5")}
          onPointerMove={() => {
            if (index !== at) onHover(index);
          }}
          onClick={(event) => {
            event.stopPropagation();
            onChoose(option);
          }}
        >
          <span className="grid min-w-0 flex-1">
            <span className="[overflow-wrap:anywhere]">{option.label}</span>
            {option.note && (
              <span className="text-sm text-muted-foreground">
                {option.note}
              </span>
            )}
          </span>
        </li>
      ))}
    </ul>
  );
}

/** An `Input` that offers text as it is typed in. */
export function SuggestedInput({
  value,
  suggestions,
  onPick,
  onSuggestionsWanted,
  opensEmpty,
  ref,
  onFocus,
  onBlur,
  onInput,
  onKeyDown,
  ...input
}: Omit<React.ComponentProps<typeof Input>, "value"> & {
  value: string;
  suggestions: readonly Suggestion[] | null;
  onPick(picked: Suggestion, via: CommitKey): void;
  onSuggestionsWanted?(): void;
  opensEmpty?: boolean;
}) {
  const { field, list } = useSuggestions({
    value,
    options: suggestions,
    onPick,
    onWanted: onSuggestionsWanted,
    opensEmpty,
  });
  return (
    <>
      <Input
        {...input}
        value={value}
        {...field({ ref, onFocus, onBlur, onInput, onKeyDown })}
      />
      {list}
    </>
  );
}
