import { useRef, useState, type ReactNode, type RefObject } from "react";
import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/alert";
import { EmptyState } from "@/components/ui/empty";
import { Icon } from "@/components/ui/icon";
import { Spinner } from "@/components/ui/spinner";
import { useScrolls } from "@/components/ui/useScrolls";
import { cn } from "@/components/ui/cn";
import { formatTime } from "../../shared/dateFormats";
import type { HomeState } from "../../shell/home";
import type { HomeServed } from "../../shell/homeContract";
import { useStrings } from "../../shell/strings";
import { PaneHeader, type PaneControl } from "../PaneHeader";
import { HomeZones, type HomeDestination } from "./HomeZones";

/** What stands in the page in place of the zones, where Home itself could not
 * be drawn: it is never drawn as an empty Home. */
function Unavailable({ home, locale }: { home: HomeServed; locale: string }) {
  const t = useStrings();
  const standing = {
    locked: "desktop.home.availability_locked",
    stale: "desktop.home.availability_stale",
    never_captured: "desktop.home.availability_never_captured",
    unavailable: "desktop.home.availability_unavailable",
    available: "desktop.home.availability_unavailable",
  } as const;
  return (
    <Alert role="status" tone="warning" icon={<Icon name="alert" />}>
      <span data-home-unavailable={home.availability}>
        {t(standing[home.availability])}
        {home.refusal ? (
          <>
            {" "}
            <code>{home.refusal}</code>
          </>
        ) : null}
        {home.observed_at
          ? ` ${t("desktop.home.observed", { date: formatTime(locale, home.observed_at) })}`
          : null}
      </span>
    </Alert>
  );
}

function Body({
  state,
  attempt,
  locale,
  refreshing,
  withheld,
  onRefresh,
  onOpen,
}: {
  state: HomeState;
  attempt: number;
  locale: string;
  refreshing: boolean;
  withheld: ReactNode;
  onRefresh: () => void;
  onOpen: (destination: HomeDestination) => void;
}) {
  const t = useStrings();
  if (state.kind === "loading")
    return (
      <EmptyState role="status" busy description={t("desktop.home.loading")} />
    );
  if (state.kind === "withheld")
    return (
      withheld ?? (
        <EmptyState
          icon="lock"
          heading={t("desktop.account.signed_out")}
          description={t("desktop.home.signed_out")}
        />
      )
    );
  if (state.kind === "failed")
    return (
      <EmptyState
        icon="alert"
        description={
          <span key={attempt} role="alert" data-home-failed={state.code}>
            {t("desktop.home.failed", { code: state.code })}
          </span>
        }
      >
        <Button variant="outline" pending={refreshing} onClick={onRefresh}>
          {t("desktop.home.refresh")}
        </Button>
      </EmptyState>
    );
  const { home } = state;
  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-3 p-4">
      {home.availability !== "available" && (
        <Unavailable home={home} locale={locale} />
      )}
      {home.projection && (
        <HomeZones
          projection={home.projection}
          locale={locale}
          onOpen={onOpen}
        />
      )}
    </div>
  );
}

/**
 * Home of the signed-in profile, drawn from what the product served and
 * nothing else: its sentences, its states and its counts. Every zone keeps
 * its own standing, a failed read says so with its code and is never tried
 * again but by the person, and a row that names a view of the window opens
 * it through the window's navigator.
 */
export function HomePage({
  state,
  attempt = 0,
  locale,
  refreshing = false,
  page,
  pane,
  withheld,
  onRefresh,
  onOpen,
}: {
  state: HomeState;
  /** Which read this is. A failure is announced again when a new read fails
   * the same way. */
  attempt?: number;
  /** The chrome language, for dates. */
  locale: string;
  /** A newer read is in flight over what is shown. */
  refreshing?: boolean;
  /** The page's own element, for whoever sends focus to it. */
  page?: RefObject<HTMLElement | null>;
  /** The pane's title and controls, which the page's header carries. */
  pane: { controls: PaneControl[]; onToggleMaximize: () => void };
  /** What stands in the page while the account withholds Home: the account's
   * own account of why, and the ways on. */
  withheld?: ReactNode;
  onRefresh: () => void;
  onOpen: (destination: HomeDestination) => void;
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
      aria-label={t("desktop.home.title")}
      aria-busy={refreshing || undefined}
      className="home-page @container/home relative flex min-h-0 flex-1 flex-col bg-background outline-none"
    >
      <PaneHeader
        title={t("desktop.home.title")}
        controls={pane.controls}
        onToggleMaximize={pane.onToggleMaximize}
      >
        <span className="flex-1" />
        <Button
          variant="outline"
          size="sm"
          disabled={state.kind === "withheld" || state.kind === "loading"}
          onClick={onRefresh}
        >
          {refreshing ? <Spinner /> : <Icon name="sync" size="sm" />}
          {t("desktop.home.refresh")}
        </Button>
      </PaneHeader>
      <div
        ref={setBodyEl}
        tabIndex={scrolls ? 0 : undefined}
        role={scrolls ? "group" : undefined}
        aria-label={scrolls ? t("desktop.home.title") : undefined}
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
          onOpen={onOpen}
        />
      </div>
    </section>
  );
}
