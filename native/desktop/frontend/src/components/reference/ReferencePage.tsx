import {
  useId,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
  type RefObject,
} from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { cn } from "@/components/ui/cn";
import { EmptyState } from "@/components/ui/empty";
import { Icon } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { useScrolls } from "@/components/ui/useScrolls";
import {
  REFERENCE_QUERY_MAX,
  type ReferenceState,
} from "../../shell/reference";
import { useStrings } from "../../shell/strings";
import { PaneHeader, type PaneControl } from "../PaneHeader";
import { ReferenceResults } from "./ReferenceResults";

/** What stands for a search that failed: its code, said as it came, and the
 * way to ask again. It is never drawn as an answer that found nothing. */
function Failed({
  code,
  attempt,
  onAgain,
}: {
  code: string;
  attempt: number;
  onAgain: () => void;
}) {
  const t = useStrings();
  return (
    <Alert role="alert" tone="danger" icon={<Icon name="refused" />}>
      <span key={attempt} data-reference-failed={code}>
        {t("desktop.reference.failed", { code })}{" "}
        <Button variant="link" size="xs" onClick={onAgain}>
          {t("desktop.reference.search_again")}
        </Button>
      </span>
    </Alert>
  );
}

function Standing({
  state,
  attempt,
  onSearch,
}: {
  state: Exclude<ReferenceState, { kind: "withheld" }>;
  attempt: number;
  onSearch: (query: string) => void;
}) {
  const t = useStrings();
  switch (state.kind) {
    case "idle":
      return (
        <p data-reference-idle="" className="text-sm text-muted-foreground">
          {t("desktop.reference.idle")}
        </p>
      );
    case "searching":
      return (
        <p
          role="status"
          data-reference-searching=""
          className="flex items-center gap-2 text-sm text-muted-foreground"
        >
          <Spinner />
          {t("desktop.reference.searching")}
        </p>
      );
    case "failed":
      return (
        <Failed
          code={state.code}
          attempt={attempt}
          onAgain={() => onSearch(state.query)}
        />
      );
    case "ready":
      return <ReferenceResults served={state.served} />;
  }
}

/**
 * Reference: a search of the sources bundled with the product, drawn from
 * what the corpus read serves and nothing else. Nothing is searched until the
 * person asks, and each standing the search can be in is kept apart: never
 * searched, searching, unavailable with its code (searched again only on
 * request) and an answer, which may hold no result. The answers are
 * orientation from bundled sources, not verified current law, and the page
 * says so.
 */
export function ReferencePage({
  state,
  attempt = 0,
  page,
  pane,
  withheld,
  onSearch,
}: {
  state: ReferenceState;
  /** Which search this is. A failure is announced again when a new search
   * fails the same way. */
  attempt?: number;
  /** The page's own element, for whoever sends focus to it. */
  page?: RefObject<HTMLElement | null>;
  /** The pane's controls, which the page's header carries. */
  pane: { controls: PaneControl[]; onToggleMaximize: () => void };
  /** What stands in the page while the account withholds it: the account's
   * own account of why, and the ways on. */
  withheld?: ReactNode;
  onSearch: (query: string) => void;
}) {
  const t = useStrings();
  const own = useRef<HTMLElement>(null);
  const root = page ?? own;
  const [bodyEl, setBodyEl] = useState<HTMLElement | null>(null);
  const scrolls = useScrolls(bodyEl);
  const field = useId();
  // The text last searched stays in the field when the page is shown again.
  const [text, setText] = useState(
    state.kind === "withheld" || state.kind === "idle" ? "" : state.query,
  );
  const blocked = state.kind === "withheld";
  const searching = state.kind === "searching";
  const ask = (event: FormEvent) => {
    event.preventDefault();
    if (!blocked && !searching && text.trim() !== "") onSearch(text);
  };
  return (
    <section
      ref={root}
      tabIndex={-1}
      aria-label={t("desktop.reference.title")}
      aria-busy={searching || undefined}
      className="reference-page @container/reference relative flex min-h-0 flex-1 flex-col bg-background outline-none"
    >
      <PaneHeader
        title={t("desktop.reference.title")}
        controls={pane.controls}
        onToggleMaximize={pane.onToggleMaximize}
      />
      <div
        ref={setBodyEl}
        tabIndex={scrolls ? 0 : undefined}
        role={scrolls ? "group" : undefined}
        aria-label={scrolls ? t("desktop.reference.title") : undefined}
        className={cn(
          "flex min-h-0 flex-1 flex-col overflow-y-auto",
          scrolls &&
            "outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset",
        )}
      >
        {state.kind === "withheld" ? (
          (withheld ?? (
            <EmptyState
              icon="lock"
              heading={t("desktop.account.signed_out")}
              description={t("desktop.reference.signed_out")}
            />
          ))
        ) : (
          <div className="mx-auto flex w-full max-w-4xl flex-col gap-3 p-4">
            <p
              data-reference-orientation=""
              className="text-sm text-muted-foreground"
            >
              {t("desktop.reference.orientation")}
            </p>
            <form className="flex items-center gap-2" onSubmit={ask}>
              <label htmlFor={field} className="sr-only">
                {t("desktop.reference.query_label")}
              </label>
              <Input
                id={field}
                type="search"
                controlSize="sm"
                value={text}
                maxLength={REFERENCE_QUERY_MAX}
                placeholder={t("desktop.reference.query_placeholder")}
                onChange={(event) => setText(event.target.value)}
              />
              <Button
                type="submit"
                variant="outline"
                size="sm"
                className="reference-search"
                disabled={searching || text.trim() === ""}
              >
                {searching ? <Spinner /> : <Icon name="search" size="sm" />}
                {t("desktop.reference.search")}
              </Button>
            </form>
            <Standing state={state} attempt={attempt} onSearch={onSearch} />
          </div>
        )}
      </div>
    </section>
  );
}
