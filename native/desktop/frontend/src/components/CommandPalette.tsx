import { useEffect, useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import {
  Command,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Icon } from "@/components/ui/icon";
import { Kbd } from "@/components/ui/kbd";
import { Spinner } from "@/components/ui/spinner";
import type { DocsResultKind, DocsSearchResult } from "../ipc/contract";
import { primaryChord, scoreAction, type Action } from "../shell/actions";
import { useStrings } from "../shell/strings";

/** Docs search provider; null until the documentation can answer queries. */
export type DocsSearch =
  ((query: string) => Promise<DocsSearchResult[]>) | null;

// Result kinds the shell names; an unknown kind shows without a label.
const KIND_LABELS: Record<string, string> = {
  concept: "desktop.palette.kind_term",
  casilla: "desktop.palette.kind_casilla",
  cli: "desktop.palette.kind_cli",
};

// Documentation results are grouped by kind, terms first and pages last; the
// docs search's own ranking holds within each group.
const KIND_ORDER = ["concept", "casilla", "cli", "page"];
const kindOrder = (kind: DocsResultKind) => {
  const at = KIND_ORDER.indexOf(kind);
  return at === -1 ? KIND_ORDER.length : at;
};

const SEARCH_DEBOUNCE_MS = 120;
const MIN_QUERY = 2;
const ACTIONS_WHEN_SEARCHING = 6;
const ACTIONS_WHEN_IDLE = 14;

function Highlighted({
  text,
  ranges,
}: {
  text: string;
  ranges: DocsSearchResult["ranges"];
}) {
  const parts: { text: string; mark: boolean }[] = [];
  let at = 0;
  for (const [start, end] of [...ranges].sort((x, y) => x[0] - y[0])) {
    if (start < at || end <= start || end > text.length) continue;
    if (start > at) parts.push({ text: text.slice(at, start), mark: false });
    parts.push({ text: text.slice(start, end), mark: true });
    at = end;
  }
  if (at < text.length) parts.push({ text: text.slice(at), mark: false });
  return (
    <>
      {parts.map((part, index) =>
        part.mark ? (
          <mark
            key={index}
            className="bg-transparent font-semibold text-foreground underline decoration-ring underline-offset-2"
          >
            {part.text}
          </mark>
        ) : (
          <span key={index}>{part.text}</span>
        ),
      )}
    </>
  );
}

const ROW_ICON = "text-faint in-data-[selected=true]:text-brand";

// One palette for the whole window: shell actions plus documentation search.
// It is a modal dialog over a command list: focus stays in the input, the
// arrow keys move the choice, Enter runs it, and closing it returns focus to
// where it was opened from.
export function CommandPalette({
  actions,
  searchDocs,
  openDoc,
  close,
}: {
  actions: readonly Action[];
  searchDocs: DocsSearch;
  openDoc: (url: string) => void;
  close: () => void;
}) {
  const t = useStrings();
  // Closing returns focus to where the palette was opened from, which may be
  // the documentation frame.
  const [returnTo] = useState(() => document.activeElement);
  const [query, setQuery] = useState("");
  const [docs, setDocs] = useState<{
    state: "idle" | "searching" | "done" | "unavailable";
    results: DocsSearchResult[];
  }>({ state: "idle", results: [] });
  const trimmed = query.trim();
  const searching = trimmed.length >= MIN_QUERY && searchDocs !== null;

  // Debounced; a newer query supersedes an older one.
  useEffect(() => {
    if (!searching || !searchDocs) return;
    let current = true;
    const timer = window.setTimeout(() => {
      setDocs((held) => ({ ...held, state: "searching" }));
      searchDocs(trimmed)
        .then((results) => current && setDocs({ state: "done", results }))
        .catch(() => current && setDocs({ state: "unavailable", results: [] }));
    }, SEARCH_DEBOUNCE_MS);
    return () => {
      current = false;
      window.clearTimeout(timer);
    };
  }, [trimmed, searching, searchDocs]);

  const matched = useMemo(
    () =>
      actions
        .filter(
          (action) => !action.hidden && (!action.enabled || action.enabled()),
        )
        .map((action) => [action, scoreAction(action, query)] as const)
        .filter(([, score]) => score > 0)
        .sort((x, y) => y[1] - x[1])
        .slice(0, trimmed ? ACTIONS_WHEN_SEARCHING : ACTIONS_WHEN_IDLE)
        .map(([action]) => action),
    [actions, query, trimmed],
  );
  const found = useMemo(
    () =>
      searching
        ? docs.results
            .map((result, rank) => ({ result, rank }))
            .sort(
              (x, y) =>
                kindOrder(x.result.kind) - kindOrder(y.result.kind) ||
                x.rank - y.rank,
            )
            .map(({ result }) => result)
        : [],
    [searching, docs.results],
  );

  const run = (action: () => void) => {
    close();
    action();
  };
  const kindLabel = (kind: DocsResultKind) => {
    const key = KIND_LABELS[kind];
    return key ? t(key) : null;
  };

  return (
    <Dialog open onOpenChange={(open) => !open && close()}>
      <DialogContent
        placement="top"
        className="palette flex w-palette flex-col gap-0 overflow-hidden rounded-2xl p-0"
        aria-describedby={undefined}
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          if (returnTo instanceof HTMLElement) returnTo.focus();
        }}
      >
        <DialogTitle className="sr-only">
          {t("desktop.palette.label")}
        </DialogTitle>
        <Command
          shouldFilter={false}
          loop
          label={t("desktop.palette.label")}
          className="max-h-palette-max"
        >
          <CommandInput
            value={query}
            onValueChange={setQuery}
            placeholder={t("desktop.palette.placeholder")}
            aria-label={t("desktop.palette.placeholder")}
          >
            <Kbd>Esc</Kbd>
          </CommandInput>
          <CommandList>
            <div className="palette-results grid gap-1">
              {searching && (
                <section>
                  <CommandGroup
                    heading={
                      <>
                        {t("desktop.palette.documentation")}
                        {docs.state === "searching" && (
                          <span className="flex items-center gap-1.5 font-normal tracking-normal normal-case">
                            <Spinner className="size-icon-xs" />
                            {t("desktop.palette.searching")}
                          </span>
                        )}
                      </>
                    }
                  >
                    {found.map((result, index) => (
                      <CommandItem
                        key={`${result.url}#${index}`}
                        value={`doc:${index}:${result.url}`}
                        onSelect={() => run(() => openDoc(result.url))}
                      >
                        <Icon
                          name={result.kind === "page" ? "page" : "term"}
                          size="md"
                          className={ROW_ICON}
                        />
                        <span className="grid min-w-0 flex-1 gap-0.5">
                          <span className="palette-title flex items-baseline gap-2 font-medium">
                            <span className="truncate">{result.title}</span>
                            {kindLabel(result.kind) && (
                              <Badge>{kindLabel(result.kind)}</Badge>
                            )}
                          </span>
                          {result.crumb && (
                            <span className="truncate text-xs text-muted-foreground">
                              {result.crumb}
                            </span>
                          )}
                          {result.excerpt && (
                            <span className="truncate text-sm text-muted-foreground">
                              <Highlighted
                                text={result.excerpt}
                                ranges={result.ranges}
                              />
                            </span>
                          )}
                        </span>
                      </CommandItem>
                    ))}
                  </CommandGroup>
                  {docs.state === "unavailable" && (
                    <p className="px-2.5 py-1.5 text-faint" role="status">
                      {t("desktop.palette.unavailable")}
                    </p>
                  )}
                  {docs.state === "done" && found.length === 0 && (
                    <p className="px-2.5 py-1.5 text-faint" role="status">
                      {t("desktop.palette.no_results", { query: trimmed })}
                    </p>
                  )}
                </section>
              )}
              {matched.length > 0 && (
                <section>
                  <CommandGroup heading={t("desktop.palette.actions")}>
                    {matched.map((action) => (
                      <CommandItem
                        key={action.id}
                        value={`action:${action.id}`}
                        onSelect={() => run(action.run)}
                      >
                        <Icon
                          name={action.icon}
                          size="md"
                          className={ROW_ICON}
                        />
                        <span className="palette-title min-w-0 flex-1 truncate font-medium">
                          {action.label}
                        </span>
                        {primaryChord(action) && (
                          <Kbd className="palette-chord">
                            {primaryChord(action)}
                          </Kbd>
                        )}
                      </CommandItem>
                    ))}
                  </CommandGroup>
                </section>
              )}
              {matched.length === 0 && !searching && (
                <p className="px-2.5 py-1.5 text-faint" role="status">
                  {t("desktop.palette.type_to_search")}
                </p>
              )}
            </div>
          </CommandList>
        </Command>
      </DialogContent>
    </Dialog>
  );
}
