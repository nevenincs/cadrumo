import { Alert } from "@/components/ui/alert";
import type { SetupPlanEntry, SetupReview } from "../../ipc/contract";
import { useStrings, type Translate } from "../../shell/strings";
import { formatSize } from "../agent/files";
import { itemName, partName } from "./setupWords";

// A setup plan as a person approves it: what it downloads in all and the
// free space it needs, then each entry's parts, sources and destination.
// The panel shows it inside the row it sets up.

/** What the plan downloads in all, said once above the detail. A plan whose
 * only sizes are unknown says so, never that it downloads nothing. */
function planSize(t: Translate, review: SetupReview, locale: string): string {
  const size = formatSize(locale, review.known_download_bytes);
  if (review.has_unknown_size)
    return review.known_download_bytes > 0
      ? t("desktop.setup.plan_size_at_least", { size })
      : t("desktop.setup.size_unknown");
  return review.known_download_bytes > 0
    ? t("desktop.setup.plan_size", { size })
    : t("desktop.setup.plan_nothing");
}

export function PlanSummary({
  review,
  locale,
}: {
  review: SetupReview;
  locale: string;
}) {
  const t = useStrings();
  const size = (bytes: number) => formatSize(locale, bytes);
  return (
    <div className="grid gap-2 text-sm text-foreground">
      <p data-setup-plan-size>{planSize(t, review, locale)}</p>
      <p>
        {review.free_bytes === null
          ? t("desktop.setup.space_unread", {
              required: size(review.required_bytes),
            })
          : t("desktop.setup.space", {
              required: size(review.required_bytes),
              free: size(review.free_bytes),
            })}
      </p>
      {review.installs_outside_program && (
        <p>{t("desktop.setup.plan_outside_program")}</p>
      )}
      {!review.space_sufficient && (
        <Alert role="alert">{t("desktop.setup.space_short")}</Alert>
      )}
    </div>
  );
}

/** One entry's parts, sources and destination; named and sized where it
 * stands beside other entries, and not where its row already names it. */
export function PlanEntry({
  entry,
  locale,
  named,
}: {
  entry: SetupPlanEntry;
  locale: string;
  named: boolean;
}) {
  const t = useStrings();
  const size = (bytes: number | null) =>
    bytes === null
      ? t("desktop.setup.size_unknown")
      : formatSize(locale, bytes);
  return (
    <li
      data-setup-plan={entry.item}
      className="grid gap-0.5 rounded-lg bg-accent p-3 text-sm"
    >
      {named && (
        <div className="flex flex-wrap items-baseline justify-between gap-x-2">
          <span className="font-medium text-foreground">
            {itemName(t, entry.item)}
          </span>
          <span className="text-muted-foreground">
            {size(entry.download_bytes)}
          </span>
        </div>
      )}
      {entry.parts.length > 0 && (
        <ul className="grid gap-0.5 text-muted-foreground">
          {entry.parts.map((part) => (
            <li
              key={part.model ? `${part.part}:${part.model}` : part.part}
              data-setup-part={part.part}
              className="flex flex-wrap justify-between gap-x-2"
            >
              <span>
                {partName(t, part.part)}
                {part.model && <>: {part.model}</>}
              </span>
              {part.download_bytes !== 0 && (
                <span>{size(part.download_bytes)}</span>
              )}
            </li>
          ))}
        </ul>
      )}
      {entry.source_hosts.length > 0 && (
        <p className="text-muted-foreground wrap-anywhere">
          {t("desktop.setup.plan_from", {
            hosts: entry.source_hosts.join(", "),
          })}
        </p>
      )}
      {entry.destination !== null && (
        <p className="text-muted-foreground wrap-anywhere">
          {t("desktop.setup.plan_destination", {
            folder: entry.destination,
          })}
        </p>
      )}
      {entry.shares_download_with !== null && (
        <p className="text-muted-foreground">
          {t("desktop.setup.plan_shared", {
            name: itemName(t, entry.shares_download_with),
          })}
        </p>
      )}
    </li>
  );
}

export function approveLabel(
  t: Translate,
  review: SetupReview,
  locale: string,
) {
  if (review.known_download_bytes <= 0) return t("desktop.setup.approve");
  const size = formatSize(locale, review.known_download_bytes);
  return review.has_unknown_size
    ? t("desktop.setup.approve_at_least", { size })
    : t("desktop.setup.approve_size", { size });
}
