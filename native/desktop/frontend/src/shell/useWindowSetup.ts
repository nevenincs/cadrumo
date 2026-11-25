import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  type Dispatch,
  type SetStateAction,
} from "react";
import { outcomeToast } from "../components/setup/setupWords";
import type { AgentToolRefusal } from "./agentSession";
import type { Host } from "./host";
import { useLedgerPeriodsReader } from "./ledgerPeriods";
import { useProvisioningStore } from "./provisioning";
import {
  provisionActionOf,
  routeCensoRefusals,
  routeProvisioningRefusals,
} from "./provisioningRecovery";
import { liveRuns, runOf, startOf, useSetup } from "./setup";
import type { Translate } from "./strings";

export function useWindowSetup({
  host,
  reader,
  signedIn,
  locale,
  held,
  setSettingsOpen,
  say,
  t,
}: {
  host: Host;
  reader: string | null;
  signedIn: boolean;
  locale: string;
  held: boolean;
  setSettingsOpen: Dispatch<SetStateAction<boolean>>;
  say: (text: string) => void;
  t: Translate;
}) {
  // Component setup, this installation's whether or not anyone is signed
  // in; only the profile's Google account and its person's model list wait
  // for a sign-in. Setup incomplete is never treated as optional, but it
  // never holds the window either: the dialog opens once per launch and
  // closes at any time.
  const setup = useSetup(host.setup, reader);
  const setupOffered = setup.offered;
  const setupSnapshot = setup.snapshot;
  const google = signedIn && setupOffered ? setupSnapshot?.google : null;
  const driveFolder = google?.drive_folder_id;
  const driveUrl =
    signedIn &&
    google?.state === "signed_in" &&
    google.stage !== "signing_in" &&
    google.stage !== "signing_out" &&
    driveFolder &&
    /^[A-Za-z0-9_-]{1,256}$/.test(driveFolder)
      ? `https://drive.google.com/drive/folders/${driveFolder}`
      : null;
  const setupRuns = setupSnapshot?.runs;
  const setupLive = useMemo(() => liveRuns(setupSnapshot), [setupSnapshot]);
  // The items the palette sets up again: each whose setup ended short of
  // done, or whose row failed, while it is not setting up now.
  const setupRetryable = useMemo(
    () =>
      (setupSnapshot?.rows ?? []).flatMap((row) => {
        const run = runOf(setupSnapshot, row.item);
        if (run && run.stage !== "settled") return [];
        const ended = run?.outcome ?? null;
        const again =
          ended === "failed" ||
          ended === "interrupted" ||
          ended === "cancelled" ||
          ended === "not_enough_space" ||
          ended === "plan_changed" ||
          row.state === "failed";
        return again
          ? [
              {
                item: row.item,
                // An interrupted setup resumes; any other runs the row's
                // served button.
                start:
                  ended === "interrupted"
                    ? { resume: true }
                    : { ...startOf(row.recovery), resume: false },
              },
            ]
          : [];
      }),
    [setupSnapshot],
  );
  const setupCancellable = useMemo(
    () => setupLive.filter((run) => run.cancellable && !run.cancel_requested),
    [setupLive],
  );
  // Changes whenever another setup settles, so what depends on a component
  // reads again.
  const settledSetups = useMemo(() => {
    const settled = (setupRuns ?? [])
      .filter((run) => run.stage === "settled")
      .map((run) => run.operation_id);
    return settled.length > 0 ? settled.join(" ") : null;
  }, [setupRuns]);
  // The one provisioning store every surface reads, and the one panel it
  // opens: once per launch while setup is not complete, and on every
  // recovery, on the element the recovery names.
  // The launch's own opening waits while the sign-in dialog, or the profiles
  // it leads to, owns the window; it opens as that closes.
  const provisioning = useProvisioningStore(
    setup,
    reader,
    () => setSettingsOpen(false),
    held,
  );
  const setupIncomplete = provisioning.incomplete;
  const openSetup = provisioning.open;
  // One toast for each setup this window watched run, once it settles.
  const setupWatched = useRef(new Set<string>());
  useEffect(() => {
    for (const run of setupRuns ?? []) {
      if (run.stage !== "settled") {
        setupWatched.current.add(run.operation_id);
        continue;
      }
      if (!setupWatched.current.delete(run.operation_id) || !run.outcome)
        continue;
      const text = outcomeToast(t, run.outcome);
      if (text) say(text);
    }
  }, [setupRuns, say, t]);
  // Something the product refused for a component that is not set up opens
  // the panel on that component; an action that is not about setup opens
  // nothing. The refusal's code is never shown.
  const raiseSetup = provisioning.raise;
  // A tool call's refusal opens it once per refusal: each new call that is
  // refused opens it again, and a conversation read again raises none twice.
  const toolRefusalsSeen = useRef(new Set<string>());
  const onToolRefused = useCallback(
    (key: string, refusal: AgentToolRefusal) => {
      if (toolRefusalsSeen.current.has(key)) return;
      toolRefusalsSeen.current.add(key);
      const action = provisionActionOf(refusal);
      if (action !== null) raiseSetup(action);
    },
    [raiseSetup],
  );
  // A ledger operation's refusal opens it once per operation, and the page
  // still shows the refusal itself.
  const routedLedger = useMemo(
    () => host.ledger && routeProvisioningRefusals(host.ledger, raiseSetup),
    [host.ledger, raiseSetup],
  );
  // The filing periods any part of the window shows are read through it.
  useLedgerPeriodsReader(routedLedger, reader, locale);
  // So does a Censo pull that stopped for want of a component.
  const profileHost = useMemo(
    () =>
      host.censo
        ? { ...host, censo: routeCensoRefusals(host.censo, raiseSetup) }
        : host,
    [host, raiseSetup],
  );
  return {
    setup,
    setupOffered,
    setupSnapshot,
    driveUrl,
    setupLive,
    setupRetryable,
    setupCancellable,
    settledSetups,
    provisioning,
    setupIncomplete,
    openSetup,
    onToolRefused,
    routedLedger,
    profileHost,
  };
}
