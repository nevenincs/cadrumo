import { useRef, useState, type ReactNode, type RefObject } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { cn } from "@/components/ui/cn";
import { EmptyState } from "@/components/ui/empty";
import { Icon } from "@/components/ui/icon";
import { Spinner } from "@/components/ui/spinner";
import { useScrolls } from "@/components/ui/useScrolls";
import type {
  OperationsListing,
  OperationsMore,
  OperationsState,
} from "../../shell/operations";
import { useStrings } from "../../shell/strings";
import { PaneHeader, type PaneControl } from "../PaneHeader";
import { OperationRun } from "./OperationRun";

/** What the journal could not account for, told whenever it is not zero and
 * never folded into the list: a damaged journal does not read as a shorter
 * history. */
function Unaccounted({ listing }: { listing: OperationsListing }) {
  const t = useStrings();
  return (
    <>
      {listing.unreadable > 0 && (
        <Alert
          role="status"
          tone="warning"
          icon={<Icon name="alert" />}
          data-operations-unreadable={listing.unreadable}
        >
          {t("desktop.operations.unreadable", { count: listing.unreadable })}
        </Alert>
      )}
      {listing.unverifiable > 0 && (
        <Alert
          role="status"
          tone="warning"
          icon={<Icon name="alert" />}
          data-operations-unverifiable={listing.unverifiable}
        >
          {t("desktop.operations.unverifiable", {
            count: listing.unverifiable,
          })}
        </Alert>
      )}
    </>
  );
}

/** The way to more runs: only when the last page served a continuation, and
 * only read when the person asks. A failed request says so by its code and
 * leaves what is listed standing. */
function More({
  more,
  attempt,
  onMore,
}: {
  more: OperationsMore;
  attempt: number;
  onMore: () => void;
}) {
  const t = useStrings();
  return (
    <div className="flex flex-col items-start gap-2">
      {more.kind === "failed" && (
        <Alert role="alert" tone="danger" icon={<Icon name="refused" />}>
          <span key={attempt} data-operations-more-failed={more.code}>
            {t("desktop.operations.more_failed", { code: more.code })}
          </span>
        </Alert>
      )}
      <Button
        variant="outline"
        size="sm"
        className="operations-more"
        disabled={more.kind === "loading"}
        onClick={onMore}
      >
        {more.kind === "loading" ? <Spinner /> : null}
        {more.kind === "loading"
          ? t("desktop.operations.loading_more")
          : more.kind === "failed"
            ? t("desktop.operations.read_again")
            : t("desktop.operations.show_more")}
      </Button>
    </div>
  );
}

function Listed({
  listing,
  more,
  attempt,
  locale,
  onMore,
  onOpen,
}: {
  listing: OperationsListing;
  more: OperationsMore;
  attempt: number;
  locale: string;
  onMore: () => void;
  onOpen: (destination: string) => void;
}) {
  const t = useStrings();
  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-3 p-4">
      <p
        data-operations-orientation=""
        className="text-sm text-muted-foreground"
      >
        {t("desktop.operations.orientation")}
      </p>
      <Unaccounted listing={listing} />
      {listing.runs.length === 0 ? (
        <p data-operations-empty="" className="text-sm text-muted-foreground">
          {t("desktop.operations.empty")}
        </p>
      ) : (
        <>
          <p data-operations-count="" className="text-xs text-muted-foreground">
            {t("desktop.operations.count", {
              shown: listing.runs.length,
              total: listing.total,
            })}
          </p>
          <ul
            className="flex flex-col gap-2"
            aria-label={t("desktop.operations.title")}
          >
            {listing.runs.map((run) => (
              <OperationRun
                key={run.operation_id}
                run={run}
                locale={locale}
                onOpen={onOpen}
              />
            ))}
          </ul>
        </>
      )}
      {listing.next !== null && (
        <More more={more} attempt={attempt} onMore={onMore} />
      )}
    </div>
  );
}

function Body({
  state,
  attempt,
  locale,
  refreshing,
  withheld,
  onRefresh,
  onMore,
  onOpen,
}: {
  state: OperationsState;
  attempt: number;
  locale: string;
  refreshing: boolean;
  withheld?: ReactNode;
  onRefresh: () => void;
  onMore: () => void;
  onOpen: (destination: string) => void;
}) {
  const t = useStrings();
  switch (state.kind) {
    case "loading":
      return (
        <EmptyState
          role="status"
          busy
          description={t("desktop.operations.loading")}
        />
      );
    case "withheld":
      return (
        withheld ?? (
          <EmptyState
            icon="lock"
            heading={t("desktop.account.signed_out")}
            description={t("desktop.operations.signed_out")}
          />
        )
      );
    case "failed":
      return (
        <EmptyState
          icon="alert"
          description={
            <span
              key={attempt}
              role="alert"
              data-operations-failed={state.code}
            >
              {t("desktop.operations.failed", { code: state.code })}
            </span>
          }
        >
          <Button variant="outline" pending={refreshing} onClick={onRefresh}>
            {t("desktop.operations.read_again")}
          </Button>
        </EmptyState>
      );
    case "ready":
      return (
        <Listed
          listing={state.listing}
          more={state.more}
          attempt={attempt}
          locale={locale}
          onMore={onMore}
          onOpen={onOpen}
        />
      );
  }
}

/**
 * Operations of the signed-in profile: the runs its operation journal holds,
 * newest first, drawn from what the product served and nothing else. It lists
 * and shows; it never runs, retries or cancels anything. Each standing is kept
 * apart: reading, unavailable with its code (read again only when the person
 * asks), no runs and a list, which says how many records the journal could
 * not read or attribute whenever there are any. A settling run and an unknown
 * effect are said as themselves.
 */
export function OperationsPage({
  state,
  attempt = 0,
  locale,
  refreshing = false,
  page,
  pane,
  withheld,
  onRefresh,
  onMore,
  onOpen,
}: {
  state: OperationsState;
  /** Which read this is. A failure is announced again when a new read fails
   * the same way. */
  attempt?: number;
  /** The chrome language, for dates. */
  locale: string;
  /** A newer read is in flight over what is shown. */
  refreshing?: boolean;
  /** The page's own element, for whoever sends focus to it. */
  page?: RefObject<HTMLElement | null>;
  /** The pane's controls, which the page's header carries. */
  pane: { controls: PaneControl[]; onToggleMaximize: () => void };
  /** What stands in the page while the account withholds it: the account's
   * own account of why, and the ways on. */
  withheld?: ReactNode;
  onRefresh: () => void;
  onMore: () => void;
  /** Opens the view of the register that a run names. */
  onOpen: (destination: string) => void;
}) {
  const t = useStrings();
  const own = useRef<HTMLElement>(null);
  const root = page ?? own;
  const [bodyEl, setBodyEl] = useState<HTMLElement | null>(null);
  const scrolls = useScrolls(bodyEl);
  return (
    <section
      ref={root}
      tabIndex={-1}
      aria-label={t("desktop.operations.title")}
      aria-busy={refreshing || undefined}
      className="operations-page @container/operations relative flex min-h-0 flex-1 flex-col bg-background outline-none"
    >
      <PaneHeader
        title={t("desktop.operations.title")}
        controls={pane.controls}
        onToggleMaximize={pane.onToggleMaximize}
      >
        <span className="flex-1" />
        <Button
          variant="outline"
          size="sm"
          className="operations-refresh"
          disabled={state.kind === "withheld" || state.kind === "loading"}
          onClick={onRefresh}
        >
          {refreshing ? <Spinner /> : <Icon name="sync" size="sm" />}
          {t("desktop.operations.refresh")}
        </Button>
      </PaneHeader>
      <div
        ref={setBodyEl}
        tabIndex={scrolls ? 0 : undefined}
        role={scrolls ? "group" : undefined}
        aria-label={scrolls ? t("desktop.operations.title") : undefined}
        className={cn(
          "flex min-h-0 flex-1 flex-col overflow-y-auto",
          scrolls &&
            "outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset",
        )}
      >
        <Body
          state={state}
          attempt={attempt}
          locale={locale}
          refreshing={refreshing}
          withheld={withheld}
          onRefresh={onRefresh}
          onMore={onMore}
          onOpen={onOpen}
        />
      </div>
    </section>
  );
}
