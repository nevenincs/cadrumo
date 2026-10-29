import { useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import type { SetupRow } from "../../ipc/contract";
import { useProvisioning } from "../../shell/provisioning";
import { useStrings } from "../../shell/strings";
import { refusalWords } from "./setupWords";

// The browser row's removal: a person who no longer wants the browser for
// the tax agency website on this computer deletes it here, after saying so
// twice. The engine refuses while the browser sets up, and a later check or
// setup puts it back.

/** Whether the row has a browser, or a part of one, that a removal deletes. */
function removable(row: SetupRow): boolean {
  return (
    row.state === "ready" ||
    row.state === "stale" ||
    row.state === "failed" ||
    row.state === "unknown"
  );
}

export function BrowserRemoval({ row }: { row: SetupRow }) {
  const t = useStrings();
  const store = useProvisioning();
  const [asking, setAsking] = useState(false);
  const [removing, setRemoving] = useState(false);
  const [refusal, setRefusal] = useState<string | null>(null);
  const live = store.runOf(row.item)?.stage;
  if (!removable(row) || (live !== undefined && live !== "settled"))
    return null;

  const remove = () => {
    setRemoving(true);
    store.control.removeBrowser().then((code) => {
      setRemoving(false);
      setRefusal(code);
      if (code !== null) setAsking(false);
    });
  };

  return (
    <div className="grid gap-1.5" data-setup-removal={row.item}>
      {refusal !== null && (
        <Alert role="alert">{refusalWords(t, refusal)}</Alert>
      )}
      {asking ? (
        <>
          <p className="text-sm text-foreground">
            {t("desktop.setup.remove_confirm")}
          </p>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              size="xs"
              disabled={removing}
              onClick={remove}
            >
              {t("desktop.setup.remove_confirm_yes")}
            </Button>
            <Button
              variant="ghost"
              size="xs"
              disabled={removing}
              onClick={() => setAsking(false)}
            >
              {t("desktop.setup.remove_keep")}
            </Button>
          </div>
        </>
      ) : (
        <Button
          variant="ghost"
          size="xs"
          className="justify-self-start"
          disabled={store.control.pending}
          onClick={() => {
            setRefusal(null);
            setAsking(true);
          }}
        >
          {t("desktop.setup.remove")}
        </Button>
      )}
    </div>
  );
}
