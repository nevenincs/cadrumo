import {
  useCallback,
  useEffect,
  useState,
  type RefObject,
  type SetStateAction,
} from "react";
import type { LedgerProfileStep } from "./ledger";
import type { Layout } from "./layout";
import { mountedNow } from "./navigation/windowViews";
import type { useNavigator } from "./navigation/useNavigator";

/** What the profile page is asked to open once it has the profile, from any
 * page: the census pull, the AEAT access editor, and the step a refusal
 * elsewhere served for putting an unready profile right. Leaving the page
 * withdraws every ask. */
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
  // A refusal on another page served one step for putting the profile right.
  // The step is held as the backend served it, so the page answers its kind
  // and nothing here interprets what the refusal meant.
  const [profileStep, setProfileStep] = useState<LedgerProfileStep | null>(
    null,
  );
  const profileStepHandled = useCallback(() => setProfileStep(null), []);
  const askProfileStep = useCallback(
    (step: LedgerProfileStep) => {
      const shown = layoutNow.current;
      const proceed = () => {
        setProfileStep(step);
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
    },
    [guardNavigation, setLayout, layoutNow],
  );
  useEffect(() => {
    if (page !== "profile") {
      setAeatAsked(false);
      setCensoAsked(false);
      setProfileStep(null);
    }
  }, [page]);
  return {
    censoAsked,
    censoHandled,
    askCenso,
    aeatAsked,
    setAeatAsked,
    aeatHandled,
    profileStep,
    profileStepHandled,
    askProfileStep,
  };
}
