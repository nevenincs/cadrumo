import { memo, useCallback, useRef, useState, type RefObject } from "react";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Icon, type IconName } from "@/components/ui/icon";
import { Spinner } from "@/components/ui/spinner";
import {
  AEAT_SYNC_AREAS,
  aeatSyncFailure,
  useAeatSync,
  type AeatSyncArea,
  type AeatSyncBringArea,
  type AeatSyncAreaId,
  type AeatSyncCountKind,
  type AeatSyncPort,
  type AeatSyncState,
} from "../../shell/aeatSync";
import type { AeatSyncPreparePort } from "../../shell/aeatSyncPrepare";
import type { AeatSyncResultsPort } from "../../shell/aeatSyncResults";
import {
  aeatSyncRunProblems,
  useAeatSyncRun,
  type AeatSyncRunPort,
} from "../../shell/aeatSyncRun";
import { dateFormats } from "../../shared/dateFormats";
import { useStrings, type Translate } from "../../shell/strings";
import { AeatSyncFlow } from "./AeatSyncFlow";
import { AeatSyncRunView } from "./AeatSyncProgress";
import { BorradorImport } from "./BorradorImport";
import { Results } from "./Results";

// An icon and a token colour for each standing, so the state reads at a glance.
const STATE_LOOK: Record<AeatSyncState, { icon: IconName; tone: string }> = {
  never_brought: { icon: "pending", tone: "text-muted-foreground" },
  current: { icon: "check", tone: "text-success" },
  possibly_stale: { icon: "alert", tone: "text-warning" },
  unavailable: { icon: "unknown", tone: "text-destructive" },
};

// Only the counts that ask for something: the rest are in the results.
const COUNT_KEYS: Partial<Record<AeatSyncCountKind, string>> = {
  unread_notifications: "desktop.aeat_sync.count.unread_notifications",
  filed_aeat_only: "desktop.aeat_sync.count.filed_aeat_only",
  filed_differing: "desktop.aeat_sync.count.filed_differing",
};

/** The area's standing in words: only what the host served, with its date. */
function standing(t: Translate, locale: string, area: AeatSyncArea): string {
  const day = area.captured_at
    ? dateFormats(locale).medium.format(new Date(area.captured_at))
    : null;
  switch (area.state) {
    case "current":
      return day
        ? t("desktop.aeat_sync.state.current", { date: day })
        : t("desktop.aeat_sync.state.current_undated");
    case "possibly_stale":
      return day
        ? t("desktop.aeat_sync.state.possibly_stale", { date: day })
        : t("desktop.aeat_sync.state.possibly_stale_undated");
    case "never_brought":
      return t("desktop.aeat_sync.state.never_brought");
    case "unavailable":
      return t("desktop.aeat_sync.state.unavailable");
  }
}

/** How the last try ended, only where it failed or could not be confirmed. */
function lastTry(t: Translate, locale: string, area: AeatSyncArea) {
  const attempt = area.last_attempt;
  if (!attempt) return null;
  if (attempt.outcome !== "failed" && attempt.outcome !== "unknown")
    return null;
  const date = dateFormats(locale).medium.format(new Date(attempt.at));
  return t(`desktop.aeat_sync.attempt.${attempt.outcome}`, { date });
}

// Where the page stands: the overview of what was brought, the checks before
// an update, or the update itself and then its results.
type Stage = { kind: "overview" } | { kind: "before" } | { kind: "update" };

/**
 * What the person has from AEAT, area by area: whether it was ever brought,
 * how current it is and the counts the host serves, with a way to bring it
 * again. An update checks what it needs (saying so only when something
 * blocks), runs in view and ends in its results; an update still going is
 * shown again when the page is. It draws served values only; the host owns
 * what is current. `results` carries the Borrador import and the results;
 * without `prepare` and `run` an update is only asked of the host.
 */
export const AeatSyncPage = memo(function AeatSyncPage({
  port,
  reader,
  language,
  shown,
  page,
  results,
  run: runPort,
  prepare,
  onOpenAccess,
  onOpenAeat,
  onReviewCensus,
}: {
  port: AeatSyncPort;
  reader: string;
  language: string;
  shown: boolean;
  /** The page's own element, for whoever sends focus to it. */
  page: RefObject<HTMLElement | null>;
  results?: AeatSyncResultsPort;
  run?: AeatSyncRunPort;
  prepare?: AeatSyncPreparePort;
  /** Opens the existing AEAT access editor in the profile. */
  onOpenAccess(): void;
  /** Opens the in-app AEAT browser. */
  onOpenAeat(): void;
  /** Goes to the one review of the census against the profile. */
  onReviewCensus(): void;
}) {
  const t = useStrings();
  const status = useAeatSync(port, reader, language, shown);
  const [starting, setStarting] = useState(false);
  const [failure, setFailure] = useState<"failed" | "unknown" | null>(null);
  const [stage, setStage] = useState<Stage>({ kind: "overview" });
  // A paused update the person chose to leave for now.
  const [parked, setParked] = useState(false);
  const wanted = useRef<AeatSyncAreaId[]>([]);
  const { refresh } = status;
  const profile = status.data?.profile_id;
  const connected = prepare !== undefined && runPort !== undefined;
  const run = useAeatSyncRun(
    connected ? runPort : undefined,
    profile ?? null,
    shown,
  );
  const snapshot = run.snapshot;
  const going =
    snapshot !== null &&
    (snapshot.state === "running" ||
      snapshot.state === "stopping" ||
      snapshot.state === "paused");
  // An update going on is followed to its results, also when the page came
  // upon it already going.
  if (connected && going && !parked && stage.kind === "overview")
    setStage({ kind: "update" });
  const request = useCallback(
    async (areas: AeatSyncAreaId[]) => {
      if (profile === undefined) return;
      await port.start(profile, {
        areas: areas.filter(
          (area): area is AeatSyncBringArea => area !== "borrador",
        ),
      });
    },
    [port, profile],
  );
  const start = useCallback(
    async (areas: AeatSyncAreaId[]) => {
      if (profile === undefined) return;
      setFailure(null);
      if (connected) {
        wanted.current = areas;
        setParked(false);
        setStage({ kind: "before" });
        return;
      }
      setStarting(true);
      try {
        await request(areas);
      } catch (error) {
        setFailure(aeatSyncFailure(error) === "unknown" ? "unknown" : "failed");
      } finally {
        setStarting(false);
        refresh();
      }
    },
    [connected, profile, refresh, request],
  );
  // The checks passed and the person is signed in: the update is asked of
  // the host, and the page follows it.
  const checked = useCallback(async () => {
    try {
      await request(wanted.current);
      setStage({ kind: "update" });
    } catch (error) {
      setFailure(aeatSyncFailure(error) === "unknown" ? "unknown" : "failed");
      setStage({ kind: "overview" });
    } finally {
      refresh();
    }
  }, [request, refresh]);
  const leave = useCallback(() => setStage({ kind: "overview" }), []);
  const park = useCallback(() => {
    setParked(true);
    setStage({ kind: "overview" });
  }, []);
  const finish = useCallback(() => {
    setStage({ kind: "overview" });
    refresh();
  }, [refresh]);
  const { resume } = run;
  const signedBackIn = useCallback(() => void resume(), [resume]);

  const served = new Map(status.data?.areas.map((a) => [a.area, a]));
  const rows = AEAT_SYNC_AREAS.map((id) => ({ id, area: served.get(id) }));
  const bringable = (status.data?.areas ?? [])
    .filter((area) => area.update === "bring")
    .map((area) => area.area);

  const shell =
    "aeat-sync-page @container/aeat relative flex min-h-0 flex-1 flex-col overflow-y-auto outline-none";
  const ended = snapshot?.state === "done" || snapshot?.state === "stopped";
  if (prepare && connected && stage.kind === "before")
    return (
      <section
        ref={page}
        tabIndex={-1}
        aria-label={t("desktop.aeat_sync.title")}
        className={shell}
      >
        <div className="mx-auto flex w-full max-w-3xl flex-col gap-4 p-4">
          <AeatSyncFlow
            port={prepare}
            locale={language}
            onReady={checked}
            onClose={leave}
            onOpenAccess={onOpenAccess}
          />
        </div>
      </section>
    );
  if (prepare && connected && snapshot !== null && stage.kind === "update")
    return (
      <section
        ref={page}
        tabIndex={-1}
        aria-label={t("desktop.aeat_sync.title")}
        className={shell}
      >
        <div className="mx-auto flex w-full max-w-3xl flex-col gap-4 p-4">
          {ended && (
            <div className="flex justify-end">
              <Button onClick={finish}>
                {t("desktop.aeat_sync.progress.done_all")}
              </Button>
            </div>
          )}
          {/* A finished update with every part in order is told by its
              results alone. */}
          {(!ended ||
            snapshot.state === "stopped" ||
            aeatSyncRunProblems(snapshot) > 0) && (
            <AeatSyncRunView
              run={run}
              paused={
                <AeatSyncFlow
                  port={prepare}
                  locale={language}
                  reason="session_ended"
                  onReady={signedBackIn}
                  onClose={park}
                  onOpenAccess={onOpenAccess}
                />
              }
            />
          )}
          {ended && results && profile !== undefined && (
            <Results
              port={results}
              profile={profile}
              language={language}
              onOpenAeat={onOpenAeat}
              onReviewCensus={onReviewCensus}
            />
          )}
        </div>
      </section>
    );

  return (
    <section
      ref={page}
      tabIndex={-1}
      aria-label={t("desktop.aeat_sync.title")}
      className={shell}
    >
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-4 p-4">
        <div className="flex justify-end">
          <Button
            disabled={starting || going || bringable.length === 0}
            onClick={() => void start(bringable)}
          >
            {starting ? <Spinner /> : <Icon name="sync" size="sm" />}
            {t("desktop.aeat_sync.bring_all")}
          </Button>
        </div>
        {failure && (
          <Alert role="alert" tone="danger" icon={<Icon name="alert" />}>
            {t(
              failure === "unknown"
                ? "desktop.aeat_sync.start_unknown"
                : "desktop.aeat_sync.start_failed",
            )}
          </Alert>
        )}
        {status.error && (
          <Alert
            role="alert"
            tone="danger"
            icon={<Icon name="alert" />}
            data-testid="aeat-sync-error"
          >
            {t("desktop.aeat_sync.unavailable")}
            <span>
              <Button size="xs" variant="outline" onClick={refresh}>
                {t("desktop.aeat_sync.retry")}
              </Button>
            </span>
          </Alert>
        )}
        {status.loading && !status.data && (
          <div
            role="status"
            className="flex items-center gap-2 text-muted-foreground"
          >
            <Spinner />
            {t("desktop.aeat_sync.loading")}
          </div>
        )}
        {status.data && (
          <ul
            aria-label={t("desktop.aeat_sync.areas")}
            className="grid gap-3 @2xl/aeat:grid-cols-2"
          >
            {rows.map(({ id, area }) => {
              const state = area?.state ?? "unavailable";
              const name = t(`desktop.aeat_sync.area.${id}.name`);
              const attempt = area ? lastTry(t, language, area) : null;
              const importing = area?.update === "import";
              const look = STATE_LOOK[state];
              const counts = (area?.counts ?? []).filter(
                (count) => COUNT_KEYS[count.kind] && count.value > 0,
              );
              return (
                <li
                  key={id}
                  data-area={id}
                  data-state={state}
                  className="flex flex-col gap-1.5 rounded-lg border bg-card p-3"
                >
                  <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1.5">
                    <h3 className="max-w-full min-w-0 text-base font-semibold [overflow-wrap:anywhere] text-foreground">
                      {name}
                    </h3>
                    {!importing && (
                      <Button
                        size="xs"
                        variant="outline"
                        className="shrink-0"
                        aria-label={t("desktop.aeat_sync.update_area", {
                          area: name,
                        })}
                        disabled={starting || going || !area}
                        onClick={() => void start([id])}
                      >
                        {t("desktop.aeat_sync.update")}
                      </Button>
                    )}
                  </div>
                  <p className="flex items-center gap-2 text-sm text-foreground">
                    <Icon
                      name={look.icon}
                      size="sm"
                      className={`shrink-0 ${look.tone}`}
                    />
                    <span className="min-w-0">
                      {area
                        ? standing(t, language, area)
                        : t("desktop.aeat_sync.state.unavailable")}
                    </span>
                  </p>
                  {attempt && (
                    <p className="text-sm text-muted-foreground">{attempt}</p>
                  )}
                  {counts.length > 0 && (
                    <ul className="flex flex-wrap gap-1.5">
                      {counts.map((count) => (
                        <li key={count.kind}>
                          <Badge>
                            {t(COUNT_KEYS[count.kind] ?? "", {
                              count: count.value,
                            })}
                          </Badge>
                        </li>
                      ))}
                    </ul>
                  )}
                  {importing &&
                    (results && profile !== undefined ? (
                      <BorradorImport
                        port={results}
                        profile={profile}
                        years={status.data?.borrador_years ?? []}
                        onImported={refresh}
                      />
                    ) : (
                      <div>
                        <Button size="xs" variant="outline" disabled>
                          <Icon name="upload" size="xs" />
                          {t("desktop.aeat_sync.results.borrador.import")}
                        </Button>
                      </div>
                    ))}
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </section>
  );
});
