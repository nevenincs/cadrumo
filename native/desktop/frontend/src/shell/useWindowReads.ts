import { useMemo } from "react";
import { useFilingCalendar } from "./calendar";
import type { Host } from "./host";
import { useMessages } from "./messages";
import { useUserProfile } from "./userProfile";

/** What the window itself reads of the reader's profile: the filing
 * calendar and the profile beside it while the calendar shows, and the
 * notification count, withheld while nobody is signed in. */
export function useWindowReads({
  host,
  reader,
  calendarVisible,
  recheckAccount,
  locale,
}: {
  host: Host;
  reader: string | null;
  calendarVisible: boolean;
  recheckAccount: () => void;
  locale: string;
}) {
  const views = host.views;
  const calendar = useFilingCalendar(
    views,
    reader,
    calendarVisible,
    recheckAccount,
    locale,
  );
  const calendarProfile = useUserProfile(
    host.userProfile,
    reader,
    locale,
    calendarVisible,
  );
  const observedMessages = useMessages(views, reader, recheckAccount, locale);
  // Withhold private counts in the same render as the account gate. The
  // existing hook settles old reads and clears its cache in its effect.
  const messages = useMemo(
    () => (reader === null ? { kind: "unknown" as const } : observedMessages),
    [reader, observedMessages],
  );
  return { calendar, calendarProfile, messages };
}
