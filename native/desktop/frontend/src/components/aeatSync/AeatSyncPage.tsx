import { memo, useCallback, useState, type RefObject } from "react";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Icon, type IconName } from "@/components/ui/icon";
import { Spinner } from "@/components/ui/spinner";
import {
  AEAT_SYNC_AREAS,
  aeatSyncDay,
  aeatSyncFailure,
  useAeatSync,
  type AeatSyncArea,
  type AeatSyncBringArea,
  type AeatSyncAreaId,
  type AeatSyncCountKind,
  type AeatSyncPort,
  type AeatSyncState,
} from "../../shell/aeatSync";
import type { AeatSyncResultsPort } from "../../shell/aeatSyncResults";
import { useStrings, type Translate } from "../../shell/strings";
import { BorradorImport } from "./BorradorImport";

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
  const day = area.captured_at ? aeatSyncDay(locale, area.captured_at) : null;
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
  const date = aeatSyncDay(locale, attempt.at);
  if (!date) return null;
  return t(`desktop.aeat_sync.attempt.${attempt.outcome}`, { date });
}

/**
 * What the person has from AEAT, area by area: whether it was ever brought,
 * how current it is and the counts the host serves, with a way to bring it
 * again. It draws served values only; the host owns what is current.
 * `results` carries the Borrador import; without it the import is off.
 */
export const AeatSyncPage = memo(function AeatSyncPage({
  port,
  reader,
  language,
  shown,
  page,
  results,
}: {
  port: AeatSyncPort;
  reader: string;
  language: string;
  shown: boolean;
  /** The page's own element, for whoever sends focus to it. */
  page: RefObject<HTMLElement | null>;
  results?: AeatSyncResultsPort;
}) {
  const t = useStrings();
  const status = useAeatSync(port, reader, language, shown);
  const [starting, setStarting] = useState(false);
  const [failure, setFailure] = useState<"failed" | "unknown" | null>(null);
  const { refresh } = status;
  const profile = status.data?.profile_id;
  const start = useCallback(
    async (areas: AeatSyncAreaId[]) => {
      if (profile === undefined) return;
      setStarting(true);
      setFailure(null);
      try {
        await port.start(profile, {
          areas: areas.filter(
            (area): area is AeatSyncBringArea => area !== "borrador",
          ),
          dry_run: false,
        });
      } catch (error) {
        setFailure(aeatSyncFailure(error) === "unknown" ? "unknown" : "failed");
      } finally {
        setStarting(false);
        refresh();
      }
    },
    [port, profile, refresh],
  );

  const served = new Map(status.data?.areas.map((a) => [a.area, a]));
  const rows = AEAT_SYNC_AREAS.map((id) => ({ id, area: served.get(id) }));
  const bringable = (status.data?.areas ?? [])
    .filter((area) => area.update === "bring")
    .map((area) => area.area);

  return (
    <section
      ref={page}
      tabIndex={-1}
      aria-label={t("desktop.aeat_sync.title")}
      className="aeat-sync-page @container/aeat relative flex min-h-0 flex-1 flex-col overflow-y-auto outline-none"
    >
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-4 p-4">
        <div className="flex justify-end">
          <Button
            disabled={starting || bringable.length === 0}
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
                        disabled={starting || !area}
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
