import {
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type KeyboardEvent,
  type ReactNode,
  type RefObject,
} from "react";
import { cn } from "@/components/ui/cn";
import {
  Popover,
  PopoverAnchor,
  PopoverContent,
} from "@/components/ui/popover";
import { Spinner } from "@/components/ui/spinner";
import type { TriggerMatch, TriggerMatcher } from "./composerTrigger";

/**
 * One kind of suggestion the composer offers while a token is typed: what
 * starts it, where its items come from, how one is shown, and what choosing
 * one writes in place of the token.
 */
export type SuggestionSource<T> = {
  /** Unique among the sources of one field; it names the list's elements. */
  id: string;
  /** Finds the token this source answers in the text before the caret. */
  match: TriggerMatcher;
  /** Every item for what is typed of the token: all of them are shown, and
   * the list scrolls. A promise is waited on, and abandoned (its signal
   * aborts) once the token changes. */
  items(
    query: string,
    signal: AbortSignal,
  ): readonly T[] | Promise<readonly T[]>;
  key(item: T): string;
  /** The words of an item's option. */
  render(item: T): ReactNode;
  /** The heading of the run of items an item belongs to, if any. */
  section?(item: T): string | undefined;
  /** What replaces the token, from its start to the caret, when the item is
   * chosen; the caret is put after it. */
  accept(item: T, match: TriggerMatch): string;
  /** The list's accessible name. */
  label: string;
  /** Shown while no item matches. */
  empty: string;
  /** Shown while the items are read. */
  loading: string;
  /** Shown when the items could not be read. */
  failed: string;
};

/** Any source, whatever its items: the list hands an item back only to the
 * source that gave it. */
export type AnySource = SuggestionSource<unknown>;

type Active = { source: AnySource; match: TriggerMatch; end: number };

/** The items read for one source, which only that source may show. */
type Items =
  | { kind: "loading"; source?: AnySource }
  | { kind: "failed"; source: AnySource }
  | { kind: "ready"; source: AnySource; items: readonly unknown[] };

const sameActive = (a: Active | null, b: Active | null) =>
  a === b ||
  (a !== null &&
    b !== null &&
    a.source === b.source &&
    a.match.start === b.match.start &&
    a.match.query === b.match.query &&
    a.end === b.end);

/** What the field and its list share; made by `useComposerSuggestions`. */
export type ComposerSuggestionsState = {
  /** The attributes that tie the field to its list. The field stays a
   * text box, as a multi-line field must: it names the list it completes
   * from and the option highlighted in it, which assistive technology
   * reads while the focus stays in the field. */
  fieldProps: {
    "aria-autocomplete": "list";
    "aria-controls": string | undefined;
    "aria-activedescendant": string | undefined;
  };
  /** Call first from the field's keydown; true when the list took the key. */
  onKeyDown: (event: KeyboardEvent<HTMLTextAreaElement>) => boolean;
  /** Call when the text or the caret may have moved: on change, select and
   * click. */
  onCaret: () => void;
  open: boolean;
  /** For `ComposerSuggestions` alone. */
  view: {
    listId: string;
    optionId: (index: number) => string;
    active: Active | null;
    items: Items;
    highlight: number;
    setHighlight: (index: number) => void;
    choose: (index: number) => void;
    dismiss: () => void;
    field: RefObject<HTMLTextAreaElement | null>;
  };
};

/**
 * Suggestions for the token being typed in a text field, which keeps the
 * focus throughout: Arrow Up and Down move the highlight, Enter or Tab
 * choose it, Escape closes the list until the token changes, and a press on
 * an option chooses it. The first source whose token the caret is in is the
 * one shown.
 */
export function useComposerSuggestions({
  field,
  value,
  onValueChange,
  sources,
}: {
  field: RefObject<HTMLTextAreaElement | null>;
  value: string;
  onValueChange: (value: string) => void;
  sources: readonly AnySource[];
}): ComposerSuggestionsState {
  const listId = useId();
  const [active, setActive] = useState<Active | null>(null);
  const [dismissed, setDismissed] = useState<Active | null>(null);
  const [items, setItems] = useState<Items>({ kind: "loading" });
  const [highlight, setHighlight] = useState(0);
  // The caret a choice puts after what it wrote, applied once the text has it.
  const caretAfter = useRef<number | null>(null);

  const evaluate = useCallback(() => {
    const el = field.current;
    if (!el || el.selectionStart !== el.selectionEnd) {
      setActive(null);
      return;
    }
    const end = el.selectionStart;
    const before = el.value.slice(0, end);
    let found: Active | null = null;
    for (const source of sources) {
      const match = source.match(before);
      if (match) {
        found = { source, match, end };
        break;
      }
    }
    setActive((held) => (sameActive(held, found) ? held : found));
  }, [field, sources]);

  useLayoutEffect(() => {
    const el = field.current;
    const caret = caretAfter.current;
    if (el && caret !== null && el.value === value) {
      caretAfter.current = null;
      el.setSelectionRange(caret, caret);
    }
    evaluate();
  }, [value, evaluate, field]);

  const source = active?.source;
  const query = active?.match.query;
  useEffect(() => {
    if (!source || query === undefined) return;
    const abort = new AbortController();
    let answer: readonly unknown[] | Promise<readonly unknown[]>;
    try {
      answer = source.items(query, abort.signal);
    } catch {
      setItems({ kind: "failed", source });
      return;
    }
    setHighlight(0);
    if (!(answer instanceof Promise)) {
      setItems({ kind: "ready", source, items: answer });
      return;
    }
    // What the source showed stays until its new items come.
    setItems((held) =>
      held.kind === "ready" && held.source === source
        ? held
        : { kind: "loading", source },
    );
    answer.then(
      (read) => {
        if (abort.signal.aborted) return;
        setItems({ kind: "ready", source, items: read });
        setHighlight(0);
      },
      () => {
        if (!abort.signal.aborted) setItems({ kind: "failed", source });
      },
    );
    return () => abort.abort();
  }, [source, query]);

  const open = active !== null && !sameActive(active, dismissed);
  // Items read for another source are never shown, even for the one render
  // before this source's own are read.
  const current: Items =
    active && items.source === active.source ? items : { kind: "loading" };
  const shown = open && current.kind === "ready" ? current.items : [];
  const optionId = useCallback(
    (index: number) => `${listId}-option-${index}`,
    [listId],
  );

  const choose = (index: number) => {
    if (!active) return;
    const item = shown[index];
    if (item === undefined) return;
    const written = active.source.accept(item, active.match);
    const next =
      value.slice(0, active.match.start) + written + value.slice(active.end);
    caretAfter.current = active.match.start + written.length;
    setDismissed(null);
    if (next === value) {
      // Nothing changed in the text, so no change will place the caret.
      const el = field.current;
      el?.setSelectionRange(caretAfter.current, caretAfter.current);
      caretAfter.current = null;
      evaluate();
    } else onValueChange(next);
  };
  const dismiss = () => setDismissed(active);

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (!open || event.nativeEvent.isComposing || event.keyCode === 229)
      return false;
    const count = shown.length;
    switch (event.key) {
      case "ArrowDown":
      case "ArrowUp":
        if (count === 0) return false;
        event.preventDefault();
        setHighlight((held) =>
          event.key === "ArrowDown"
            ? (held + 1) % count
            : (held - 1 + count) % count,
        );
        return true;
      case "Enter":
      case "Tab":
        if (event.shiftKey || count === 0) return false;
        event.preventDefault();
        choose(Math.min(highlight, count - 1));
        return true;
      case "Escape":
        event.preventDefault();
        event.stopPropagation();
        dismiss();
        return true;
      default:
        return false;
    }
  };

  return {
    fieldProps: {
      "aria-autocomplete": "list",
      "aria-controls": open ? listId : undefined,
      "aria-activedescendant":
        open && shown.length > 0
          ? optionId(Math.min(highlight, shown.length - 1))
          : undefined,
    },
    onKeyDown,
    onCaret: evaluate,
    open,
    view: {
      listId,
      optionId,
      active,
      items: current,
      highlight: Math.min(highlight, Math.max(shown.length - 1, 0)),
      setHighlight,
      choose,
      dismiss,
      field,
    },
  };
}

/**
 * The composer, with the list of suggestions for its token above it, or
 * below where there is no room above. `children` is the composer itself: the
 * list is as wide as it.
 */
export function ComposerSuggestions({
  state,
  children,
}: {
  state: ComposerSuggestionsState;
  children: ReactNode;
}) {
  const { open, view } = state;
  const anchor = useRef<HTMLDivElement>(null);
  const list = useRef<HTMLDivElement>(null);
  const { active, items, highlight, optionId } = view;

  // The highlighted option is kept in view as the arrows move it.
  useLayoutEffect(() => {
    if (!open) return;
    list.current
      ?.querySelector(`[id="${optionId(highlight)}"]`)
      ?.scrollIntoView({ block: "nearest" });
  }, [open, highlight, optionId, items]);

  const source = active?.source;
  let body: ReactNode = null;
  if (source && items.kind === "loading")
    body = (
      <p className="flex items-center gap-2 px-2.5 py-2 text-base text-faint">
        <Spinner />
        {source.loading}
      </p>
    );
  else if (source && items.kind === "failed")
    body = <p className="px-2.5 py-2 text-base text-faint">{source.failed}</p>;
  else if (source && items.kind === "ready" && items.items.length === 0)
    body = <p className="px-2.5 py-2 text-base text-faint">{source.empty}</p>;

  const rows: ReactNode[] = [];
  if (source && items.kind === "ready") {
    let heading: string | undefined;
    items.items.forEach((item, index) => {
      const section = source.section?.(item);
      if (section !== undefined && section !== heading) {
        heading = section;
        rows.push(
          <div
            key={`section-${section}`}
            role="presentation"
            className="px-2 pt-2 pb-1 text-xs font-semibold tracking-wider text-faint uppercase"
          >
            {section}
          </div>,
        );
      }
      const selected = index === highlight;
      rows.push(
        <div
          key={source.key(item)}
          id={optionId(index)}
          role="option"
          aria-selected={selected}
          data-selected={selected}
          // The field keeps the focus: a press only chooses.
          onMouseDown={(event) => event.preventDefault()}
          onMouseMove={() => {
            if (!selected) view.setHighlight(index);
          }}
          onClick={() => view.choose(index)}
          className={cn(
            "relative flex min-h-control-lg cursor-pointer items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-base outline-none select-none",
            "data-[selected=true]:bg-selected data-[selected=true]:text-accent-foreground",
            "before:absolute before:inset-y-2 before:left-0 before:w-0.5 before:rounded-xs before:bg-brand before:opacity-0 data-[selected=true]:before:opacity-100",
            "forced-colors:data-[selected=true]:bg-[Highlight] forced-colors:data-[selected=true]:text-[HighlightText]",
          )}
        >
          {source.render(item)}
        </div>,
      );
    });
  }

  return (
    <Popover
      open={open}
      onOpenChange={(next) => {
        if (!next) view.dismiss();
      }}
    >
      <PopoverAnchor asChild>
        <div ref={anchor}>{children}</div>
      </PopoverAnchor>
      <PopoverContent
        side="top"
        align="start"
        sideOffset={6}
        role="presentation"
        data-slot="composer-suggestions"
        data-source={source?.id}
        onOpenAutoFocus={(event) => event.preventDefault()}
        onCloseAutoFocus={(event) => event.preventDefault()}
        // A press in the composer moves the caret; it never closes the list.
        onInteractOutside={(event) => {
          if (anchor.current?.contains(event.target as Node))
            event.preventDefault();
        }}
        className="flex w-(--radix-popover-trigger-width) min-w-64 flex-col overflow-hidden p-0"
      >
        <div
          ref={list}
          id={view.listId}
          role="listbox"
          aria-label={source?.label}
          className="min-h-0 flex-1 scroll-py-1.5 overflow-x-hidden overflow-y-auto p-1.5"
        >
          {rows}
        </div>
        {body}
      </PopoverContent>
    </Popover>
  );
}
