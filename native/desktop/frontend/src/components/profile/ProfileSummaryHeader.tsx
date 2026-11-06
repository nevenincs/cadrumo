import type { ReactNode } from "react";
import { cn } from "@/components/ui/cn";
import { Icon, type IconName } from "@/components/ui/icon";
import { Progress } from "@/components/ui/progress";
import { initials, shownValue } from "../../shell/profileRows";
import { useStrings } from "../../shell/strings";
import type { ProfileField } from "../../shell/userProfile";
import { Unset } from "./ProfileMarks";

/** Who the profile is, its key details, how complete it is, and the page's
 * actions menu. */
export function ProfileSummaryHeader({
  name,
  full,
  facts,
  missing,
  filled,
  total,
  missingCount,
  onMissing,
  actions,
}: {
  name: string;
  full: boolean;
  /** Icon, field and, where it differs from the field's, the value shown. */
  facts: [IconName, ProfileField | undefined, string?][];
  missing: Set<string>;
  filled: number;
  total: number;
  missingCount: number;
  onMissing(): void;
  actions: ReactNode;
}) {
  const t = useStrings();
  const letters = initials(name);
  return (
    <header
      className={cn(
        "flex items-start gap-3 border-b px-4",
        full ? "gap-4 py-4" : "py-3",
      )}
    >
      <div
        aria-hidden="true"
        className={cn(
          "flex shrink-0 items-center justify-center rounded-full border border-border-strong bg-secondary font-semibold text-foreground select-none",
          full ? "size-16 text-lg" : "size-10 text-base",
        )}
      >
        {letters || <Icon name="person" size={full ? "lg" : "md"} />}
      </div>
      <div className="min-w-0 flex-1">
        <h3
          className={cn(
            "truncate font-semibold text-foreground",
            full ? "text-lg" : "text-md",
          )}
        >
          {name || t("desktop.profile.unnamed")}
        </h3>
        <dl
          className={cn(
            "mt-0.5 flex min-w-0 flex-wrap gap-x-4 gap-y-0.5 text-sm text-muted-foreground",
            !full && "gap-x-3",
          )}
        >
          {facts.map(([icon, field, shown], at) => {
            if (!field) return null;
            const value = shown || shownValue(field);
            if (!full && at >= 2 && !value) return null;
            return (
              <div
                key={field.path}
                className="flex min-w-0 items-center gap-1.5"
                title={field.label}
              >
                <dt className="flex items-center">
                  <Icon name={icon} />
                  <span className="sr-only">{field.label}</span>
                </dt>
                <dd className="min-w-0 truncate text-foreground">
                  {value ||
                    (missing.has(field.path) ? (
                      <span className="font-medium italic">
                        {t("desktop.profile.missing")}
                      </span>
                    ) : (
                      <Unset />
                    ))}
                </dd>
              </div>
            );
          })}
        </dl>
        <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
          <span className="flex items-center gap-2">
            <Progress
              value={filled}
              max={total || 1}
              aria-label={t("desktop.profile.progress", { filled, total })}
              className="w-24 text-foreground"
            />
            <span className="tabular-nums">
              {t("desktop.profile.progress", { filled, total })}
            </span>
          </span>
          {missingCount ? (
            <button
              type="button"
              className="cursor-pointer font-medium text-foreground underline-offset-2 hover:underline"
              onClick={onMissing}
            >
              <span aria-hidden="true">* </span>
              {t("desktop.profile.required_missing", { count: missingCount })}
            </button>
          ) : (
            <span className="flex items-center gap-1">
              <Icon name="tick" size="xs" />
              {t("desktop.profile.required_done")}
            </span>
          )}
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-1">{actions}</div>
    </header>
  );
}
