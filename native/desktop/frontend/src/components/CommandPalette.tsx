import { useEffect, useMemo, useRef, useState } from "react";
import type { DocsResultKind, DocsSearchResult } from "../ipc/contract";
import { primaryChord, scoreAction, type Action } from "../shell/actions";
import { useStrings } from "../shell/strings";
import { Icon } from "./Icon";

/** Docs search provider; null until the documentation can answer queries. */
export type DocsSearch =
  ((query: string) => Promise<DocsSearchResult[]>) | null;

// Result kinds the shell names; an unknown kind shows without a label.
const KIND_LABELS: Record<string, string> = {
  concept: "desktop.palette.kind_term",
  casilla: "desktop.palette.kind_casilla",
  cli: "desktop.palette.kind_cli",
};

type Row =
  | { type: "doc"; result: DocsSearchResult }
  | { type: "action"; action: Action };

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
          <mark key={index}>{part.text}</mark>
        ) : (
          <span key={index}>{part.text}</span>
        ),
      )}
    </>
  );
}

// One palette for the whole window: shell actions plus documentation search.
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
  const input = useRef<HTMLInputElement>(null);
  const list = useRef<HTMLDivElement>(null);
  const [query, setQuery] = useState("");
  const [docs, setDocs] = useState<{
    state: "idle" | "searching" | "done" | "unavailable";
    results: DocsSearchResult[];
  }>({
    state: "idle",
    results: [],
  });
  const [active, setActive] = useState(0);
  const trimmed = query.trim();
  const searching = trimmed.length >= 2;

  useEffect(() => input.current?.focus(), []);

  // Debounced; a newer query supersedes an older one.
  useEffect(() => {
    if (!searching || !searchDocs) return;
    let current = true;
    const timer = window.setTimeout(() => {
      setDocs((d) => ({ ...d, state: "searching" }));
      searchDocs(trimmed)
        .then((results) => current && setDocs({ state: "done", results }))
        .catch(() => current && setDocs({ state: "unavailable", results: [] }));
    }, 120);
    return () => {
      current = false;
      window.clearTimeout(timer);
    };
  }, [trimmed, searching, searchDocs]);

  const rows = useMemo<Row[]>(() => {
    const matched = actions
      .filter(
        (action) => !action.hidden && (!action.enabled || action.enabled()),
      )
      .map((action) => [action, scoreAction(action, query)] as const)
      .filter(([, score]) => score > 0)
      .sort((x, y) => y[1] - x[1])
      .slice(0, trimmed ? 6 : 14)
      .map(([action]): Row => ({ type: "action", action }));
    const docRows: Row[] =
      searching && searchDocs
        ? docs.results.map((result) => ({ type: "doc", result }))
        : [];
    return [...docRows, ...matched];
  }, [actions, query, trimmed, searching, searchDocs, docs.results]);

  useEffect(() => setActive(0), [query]);
  useEffect(() => {
    list.current
      ?.querySelector(`[data-index="${active}"]`)
      ?.scrollIntoView({ block: "nearest" });
  }, [active]);

  const choose = (row: Row | undefined) => {
    close();
    if (!row) return;
    if (row.type === "action") row.action.run();
    else openDoc(row.result.url);
  };

  const kindLabel = (kind: DocsResultKind) => {
    const key = KIND_LABELS[kind];
    return key ? t(key) : null;
  };
  const renderRow = (row: Row, index: number) => (
    <div
      key={row.type === "action" ? row.action.id : `${row.result.url}#${index}`}
      id={`palette-row-${index}`}
      data-index={index}
      role="option"
      aria-selected={index === active}
      className={`palette-row ${index === active ? "is-active" : ""}`}
      onMouseMove={() => setActive(index)}
      onClick={() => choose(row)}
    >
      <span className="palette-icon">
        <Icon
          name={
            row.type === "action"
              ? row.action.icon
              : row.result.kind === "page"
                ? "page"
                : "term"
          }
          size="m"
        />
      </span>
      <span className="palette-text">
        <span className="palette-title">
          {row.type === "action" ? row.action.label : row.result.title}
          {row.type === "doc" && kindLabel(row.result.kind) && (
            <span className="palette-kind">{kindLabel(row.result.kind)}</span>
          )}
        </span>
        {row.type === "doc" && row.result.excerpt && (
          <span className="palette-excerpt">
            <Highlighted text={row.result.excerpt} ranges={row.result.ranges} />
          </span>
        )}
      </span>
      {row.type === "action" && primaryChord(row.action) && (
        <kbd className="palette-chord">{primaryChord(row.action)}</kbd>
      )}
    </div>
  );

  const docCount = rows.filter((row) => row.type === "doc").length;

  return (
    <div
      className="palette-backdrop"
      onPointerDown={(event) => event.target === event.currentTarget && close()}
    >
      <div
        className="palette"
        role="dialog"
        aria-modal="true"
        aria-label={t("desktop.palette.label")}
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            event.stopPropagation();
            close();
          } else if (event.key === "ArrowDown") {
            event.preventDefault();
            setActive((index) => Math.min(rows.length - 1, index + 1));
          } else if (event.key === "ArrowUp") {
            event.preventDefault();
            setActive((index) => Math.max(0, index - 1));
          } else if (event.key === "Enter") {
            event.preventDefault();
            choose(rows[active]);
          }
        }}
      >
        <div className="palette-input">
          <Icon name="search" />
          <input
            ref={input}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={t("desktop.palette.placeholder")}
            aria-label={t("desktop.palette.placeholder")}
            role="combobox"
            aria-expanded="true"
            aria-controls="palette-results"
            aria-activedescendant={
              rows.length ? `palette-row-${active}` : undefined
            }
          />
          <kbd>Esc</kbd>
        </div>
        <div
          className="palette-results"
          id="palette-results"
          role="listbox"
          ref={list}
        >
          {searching && searchDocs && (
            <section>
              <h3>
                {t("desktop.palette.documentation")}
                {docs.state === "searching" && (
                  <span className="palette-status">
                    {t("desktop.palette.searching")}
                  </span>
                )}
              </h3>
              {docs.state === "unavailable" && (
                <p className="palette-empty">
                  {t("desktop.palette.unavailable")}
                </p>
              )}
              {docs.state === "done" && docCount === 0 && (
                <p className="palette-empty">
                  {t("desktop.palette.no_results", { query: trimmed })}
                </p>
              )}
              {rows
                .slice(0, docCount)
                .map((row, index) => renderRow(row, index))}
            </section>
          )}
          {rows.length > docCount && (
            <section>
              <h3>{t("desktop.palette.actions")}</h3>
              {rows
                .slice(docCount)
                .map((row, index) => renderRow(row, docCount + index))}
            </section>
          )}
          {rows.length === 0 && !searching && (
            <p className="palette-empty">
              {t("desktop.palette.type_to_search")}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
