import { useMemo } from "react";
import { useFilingCalendar } from "./calendar";
import { useHome } from "./home";
import type { Host } from "./host";
import { useMessages } from "./messages";
import { useReference } from "./reference";
import { useUserProfile } from "./userProfile";

/** What the window itself reads of the reader's profile: Home while it
 * shows, the Reference search, made only when the person asks, the filing calendar and the profile beside it while the calendar
 * shows, and the notification count, withheld while nobody is signed in. */
export function useWindowReads({
  host,
  reader,
  homeVisible,
  calendarVisible,
  recheckAccount,
  locale,
}: {
  host: Host;
  reader: string | null;
  homeVisible: boolean;
  calendarVisible: boolean;
  recheckAccount: () => void;
  locale: string;
}) {
  const views = host.views;
  const home = useHome(views, reader, homeVisible, recheckAccount, locale);
  const reference = useReference(views, reader, recheckAccount, locale);
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
  return { home, reference, calendar, calendarProfile, messages };
}
