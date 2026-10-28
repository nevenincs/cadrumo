import { useId, useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { formatViewLink } from "../../shell/navigation/links";
import { NAVIGATION } from "../../shell/navigation/projection";
import { useStrings } from "../../shell/strings";
import type { UserProfile } from "../../shell/userProfile";
import type { CalendarWarning } from "../../shell/views";

/** The profile's own completion state and independently reported calendar
 * evidence, kept compact until the person asks to read the details. */
export function ProfileCompletionNotice({
  profile,
  warnings = [],
  onNavigate,
  className,
}: {
  profile: UserProfile | null;
  warnings?: CalendarWarning[];
  onNavigate?: (url: string) => void;
  className?: string;
}) {
  const t = useStrings();
  const detailsId = useId();
  const [expanded, setExpanded] = useState(false);
  const incomplete = profile?.setup_state === "incomplete";
  const missing = new Set(profile?.missing_required ?? []);
  const attention = profile !== null && (!profile.valid || missing.size > 0);
  const profileAttention = attention || (profile?.notices.length ?? 0) > 0;
  const labels =
    profile?.sections.flatMap((section) =>
      section.fields
        .filter((field) => missing.has(field.path))
        .map((field) => field.label),
    ) ?? [];
  const messages = [
    ...new Set([
      ...(profile?.notices.map((notice) => notice.message) ?? []),
      ...warnings.map((warning) => warning.message),
    ]),
  ];
  if (!incomplete && !attention && messages.length === 0) return null;
  const hasDetails = labels.length > 0 || messages.length > 0;
  const href = formatViewLink(NAVIGATION, "profile");
  return (
    <Alert tone="warning" icon={<Icon name="alert" />} className={className}>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="font-medium">
          {t(
            incomplete
              ? "desktop.profile.notice.incomplete"
              : profileAttention
                ? "desktop.profile.notice.attention"
                : "desktop.calendar.notice.attention",
          )}
        </span>
        {hasDetails && (
          <Button
            variant="link"
            className="min-h-control-xs"
            aria-expanded={expanded}
            aria-controls={expanded ? detailsId : undefined}
            onClick={() => setExpanded(!expanded)}
          >
            {t(
              expanded
                ? "desktop.profile.notice.hide_details"
                : "desktop.profile.notice.show_details",
            )}
          </Button>
        )}
        {onNavigate && (
          <Button variant="link" className="min-h-control-xs" asChild>
            <a
              href={href}
              onClick={(event) => {
                event.preventDefault();
                onNavigate(href);
              }}
              onAuxClick={(event) => event.preventDefault()}
            >
              {t("desktop.profile.notice.open_profile")}
            </a>
          </Button>
        )}
      </div>
      {hasDetails && expanded && (
        <div id={detailsId} className="mt-1 grid gap-1 text-sm">
          {labels.length > 0 && (
            <div>
              <p>{t("desktop.profile.notice.missing_fields")}</p>
              <ul className="list-inside list-disc">
                {labels.map((label, index) => (
                  <li key={index}>{label}</li>
                ))}
              </ul>
            </div>
          )}
          {messages.length > 0 && (
            <ul className="grid gap-0.5">
              {messages.map((message) => (
                <li key={message}>{message}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </Alert>
  );
}
