import {
  useCallback,
  useEffect,
  useState,
  type RefObject,
  type SetStateAction,
} from "react";
import type { Layout } from "./layout";
import { mountedNow } from "./navigation/windowViews";
import type { useNavigator } from "./navigation/useNavigator";

/** What the profile page is asked to open once it has the profile, from any
 * page: the census pull and the AEAT access editor. Leaving the page
 * withdraws both asks. */
export function useProfilePageAsks({
  page,
  layoutNow,
  setLayout,
  guardNavigation,
}: {
  page: Layout["page"];
  layoutNow: RefObject<Layout>;
  setLayout: (update: SetStateAction<Layout>) => void;
  guardNavigation: ReturnType<typeof useNavigator>["guard"];
}) {
  // The census pull was asked for from any page: the profile page takes the
  // one census flow over once it has the profile, and starts it only when
  // none is running.
  const [censoAsked, setCensoAsked] = useState(false);
  const censoHandled = useCallback(() => setCensoAsked(false), []);
  const askCenso = useCallback(() => {
    const shown = layoutNow.current;
    const proceed = () => {
      setCensoAsked(true);
      setLayout((current) => ({
        ...current,
        page: "profile",
        maximized: null,
      }));
    };
    if (shown.page === "profile") proceed();
    else
      guardNavigation(
        {
          kind: "navigate",
          unmounted: mountedNow(shown.page, shown.ledgerView.section),
        },
        proceed,
      );
  }, [guardNavigation, setLayout, layoutNow]);
  // The AEAT access editor was asked for: the profile page opens it once it
  // has the profile.
  const [aeatAsked, setAeatAsked] = useState(false);
  const aeatHandled = useCallback(() => setAeatAsked(false), []);
  useEffect(() => {
    if (page !== "profile") {
      setAeatAsked(false);
      setCensoAsked(false);
    }
  }, [page]);
  return {
    censoAsked,
    censoHandled,
    askCenso,
    aeatAsked,
    setAeatAsked,
    aeatHandled,
  };
}
