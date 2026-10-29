import { memo, useCallback, useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Spinner } from "@/components/ui/spinner";
import {
  AEAT_SYNC_AREAS,
  aeatSyncFailure,
  type AeatSyncAreaId,
} from "../../shell/aeatSync";
import {
  useAeatSyncResults,
  type AeatSyncFailedPart,
  type AeatSyncResult,
  type AeatSyncResultsPort,
} from "../../shell/aeatSyncResults";
import { dateFormats } from "../../shared/dateFormats";
import { useStrings, type Translate } from "../../shell/strings";
import { BorradorImport } from "./BorradorImport";
import { FiledResults } from "./FiledResults";
import { NotificationResults } from "./NotificationResults";
import { OUTCOME_ICONS } from "./outcomeIcons";
import { UnknownWarning } from "./UnknownWarning";

/** A count's sentence, in its singular or plural form. */
function counted(t: Translate, key: string, count: number): string {
  return t(`${key}.${count === 1 ? "one" : "other"}`, { count });
}

/** What was new and what differs, in the words of the area. */
function news(t: Translate, result: AeatSyncResult): string[] {
  const lines: string[] = [];
  const { area, new_count: added, changed_count: changed } = result;
  const kind = area === "filed" || area === "notifications" ? area : "other";
  if (area !== "census" && added > 0)
    lines.push(counted(t, `desktop.aeat_sync.results.new.${kind}`, added));
  if (changed > 0)
    lines.push(
      counted(
        t,
        `desktop.aeat_sync.results.changed.${area === "census" || area === "filed" ? area : "other"}`,
        changed,
      ),
    );
  return lines;
}

/** How the last update of the area ended, in a sentence. */
function ending(t: Translate, result: AeatSyncResult): string {
  switch (result.outcome) {
    case "failed":
      return t(
        result.failed.length > 0 && news(t, result).length > 0
          ? "desktop.aeat_sync.results.partly"
          : "desktop.aeat_sync.results.failed",
      );
    case "unknown":
      return t("desktop.aeat_sync.results.unknown");
    case "nothing_found":
      return result.area === "borrador"
        ? ""
        : t("desktop.aeat_sync.results.nothing_found");
    case "brought":
      return news(t, result).length === 0
        ? t("desktop.aeat_sync.results.nothing_new")
        : "";
  }
}

function partName(t: Translate, part: AeatSyncFailedPart): string | null {
  if (part.year !== null)
    return t("desktop.aeat_sync.results.part.year", { year: part.year });
  return null;
}

/**
 * What came back from AEAT, one summary for each kind of data: what is new,
 * what differs from the profile, and what could not be updated and why, with
 * a way to try again. Each summary carries the detail that belongs to it. It
 * only reads: nothing here files or sends anything.
 */
export const Results = memo(function Results({
  port,
  profile,
  language,
  onOpenAeat,
  onReviewCensus,
}: {
  port: AeatSyncResultsPort;
  profile: string;
  language: string;
  /** Opens the in-app AEAT browser at its start page. */
  onOpenAeat(): void;
  /** Goes to the profile's comparison of its details with AEAT's. */
  onReviewCensus(): void;
}) {
  const t = useStrings();
  const results = useAeatSyncResults(port, profile, language);
  const { refresh } = results;
  const [trying, setTrying] = useState<string | null>(null);
  // The area or part whose outcome is unknown, awaiting the person's word to
  // read it again.
  const [confirming, setConfirming] = useState<string | null>(null);
  const [trouble, setTrouble] = useState<
    Partial<Record<AeatSyncAreaId, "failed" | "unknown">>
  >({});
  const retry = useCallback(
    async (
      area: AeatSyncAreaId,
      part: number | null,
      acknowledgedUnknown: boolean,
    ) => {
      const key = `${area}:${part ?? "all"}`;
      setConfirming(null);
      setTrying(key);
      setTrouble((now) => {
        const next = { ...now };
        delete next[area];
        return next;
      });
      try {
        await port.retry(profile, area, part, acknowledgedUnknown);
      } catch (error) {
        setTrouble((now) => ({
          ...now,
          [area]: aeatSyncFailure(error) === "unknown" ? "unknown" : "failed",
        }));
      } finally {
        setTrying(null);
        refresh();
      }
    },
    [port, profile, refresh],
  );

  if (results.failed && !results.data)
    return (
      <Alert role="alert" tone="danger" icon={<Icon name="alert" />}>
        {t("desktop.aeat_sync.results.unavailable")}
        <span>
          <Button size="xs" variant="outline" onClick={refresh}>
            {t("desktop.aeat_sync.results.retry")}
          </Button>
        </span>
      </Alert>
    );
  if (!results.data)
    return (
      <div
        role="status"
        className="flex items-center gap-2 text-muted-foreground"
      >
        <Spinner />
        {t("desktop.aeat_sync.results.loading")}
      </div>
    );

  const { data } = results;
  const served = new Map(data.areas.map((result) => [result.area, result]));
  return (
    <div
      className="@container/aeat flex flex-col gap-3"
      data-testid="aeat-sync-results"
    >
      <ul
        aria-label={t("desktop.aeat_sync.results.title")}
        className="flex flex-col gap-3"
      >
        {AEAT_SYNC_AREAS.flatMap((id) => {
          const result = served.get(id);
          return result ? [result] : [];
        }).map((result) => {
          const name = t(`desktop.aeat_sync.area.${result.area}.name`);
          const lines = news(t, result);
          const sentence = ending(t, result);
          const day =
            result.at && (result.outcome !== "failed" || lines.length > 0)
              ? dateFormats(language).medium.format(new Date(result.at))
              : null;
          const busy = trying?.startsWith(`${result.area}:`) ?? false;
          const problem = trouble[result.area];
          return (
            <li
              key={result.area}
              data-area={result.area}
              data-outcome={result.outcome}
              className="flex flex-col gap-3 rounded-lg border bg-card p-3"
            >
              <div className="flex items-start gap-2">
                <Icon
                  name={OUTCOME_ICONS[result.outcome]}
                  size="sm"
                  className="mt-1 shrink-0 text-muted-foreground"
                />
                <span className="min-w-0 flex-1">
                  <h3 className="text-base font-semibold text-foreground">
                    {name}
                  </h3>
                  {day && (
                    <p className="text-sm text-muted-foreground">
                      {t("desktop.aeat_sync.results.updated", { date: day })}
                    </p>
                  )}
                </span>
                {result.area === "census" && result.review_pending && (
                  <Button size="xs" onClick={onReviewCensus}>
                    {t("desktop.aeat_sync.results.census_review")}
                  </Button>
                )}
                {result.outcome === "failed" && result.failed.length > 1 && (
                  <Button
                    size="xs"
                    variant="outline"
                    pending={busy}
                    aria-label={t("desktop.aeat_sync.results.retry_named", {
                      name,
                    })}
                    onClick={() => void retry(result.area, null, false)}
                  >
                    {t("desktop.aeat_sync.results.retry")}
                  </Button>
                )}
              </div>
              {(lines.length > 0 || sentence) && (
                <ul className="flex flex-col gap-0.5 text-base text-foreground">
                  {lines.map((line) => (
                    <li key={line}>{line}</li>
                  ))}
                  {sentence && <li>{sentence}</li>}
                </ul>
              )}
              {result.failed.length > 0 && (
                <ul
                  aria-label={t("desktop.aeat_sync.results.problems", { name })}
                  className="flex flex-col gap-2"
                >
                  {result.failed.map((part) => {
                    const label = partName(t, part);
                    return (
                      <li
                        key={part.part}
                        className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-md bg-accent px-3 py-2"
                      >
                        <span className="min-w-0 flex-1 basis-56">
                          {label && (
                            <span className="block text-sm font-medium text-foreground">
                              {label}
                            </span>
                          )}
                          <span
                            className={
                              label
                                ? "block text-sm text-muted-foreground"
                                : "block text-sm text-foreground"
                            }
                          >
                            {t(
                              `desktop.aeat_sync.results.reason.${part.reason}`,
                            )}
                          </span>
                        </span>
                        <Button
                          size="xs"
                          variant="outline"
                          pending={trying === `${result.area}:${part.part}`}
                          aria-label={t(
                            "desktop.aeat_sync.results.retry_named",
                            {
                              name: label ?? name,
                            },
                          )}
                          onClick={() =>
                            void retry(result.area, part.part, false)
                          }
                        >
                          {t("desktop.aeat_sync.results.retry")}
                        </Button>
                      </li>
                    );
                  })}
                </ul>
              )}
              {result.outcome === "unknown" &&
                (confirming === `${result.area}:all` ? (
                  <UnknownWarning
                    busy={busy}
                    onProceed={() => void retry(result.area, null, true)}
                    onCancel={() => setConfirming(null)}
                  />
                ) : (
                  <div>
                    <Button
                      size="xs"
                      variant="outline"
                      pending={busy}
                      onClick={() => setConfirming(`${result.area}:all`)}
                    >
                      {t("desktop.aeat_sync.results.retry")}
                    </Button>
                  </div>
                ))}
              {problem && (
                <Alert role="alert" tone="danger" icon={<Icon name="alert" />}>
                  {t(
                    problem === "unknown"
                      ? "desktop.aeat_sync.results.retry_unknown"
                      : "desktop.aeat_sync.results.retry_failed",
                  )}
                </Alert>
              )}
              {result.area === "filed" && (
                <FiledResults rows={data.filed} language={language} />
              )}
              {result.area === "notifications" && (
                <NotificationResults
                  rows={data.notifications}
                  language={language}
                  onOpenAeat={onOpenAeat}
                />
              )}
              {result.area === "borrador" && (
                <BorradorImport
                  port={port}
                  profile={profile}
                  years={data.borrador_years}
                  onImported={refresh}
                />
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
});
