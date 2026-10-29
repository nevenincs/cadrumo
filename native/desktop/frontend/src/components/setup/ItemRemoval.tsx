import { useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import type { SetupRemoval, SetupRow } from "../../ipc/contract";
import { useProvisioning } from "../../shell/provisioning";
import { useStrings } from "../../shell/strings";
import { refusalWords } from "./setupWords";

// An item row's removals: a person who no longer wants the browser for the
// tax agency website, or the local AI, on this computer deletes it here,
// after saying so twice. The browser has one removal; the local AI has two,
// all of it with the models on the person's lists, or its program alone with
// every model kept. The engine refuses while the item sets up, and a later
// check or setup puts it back.

const WORDS = {
  browser: {
    ask: "desktop.setup.remove",
    confirm: "desktop.setup.remove_confirm",
  },
  local_ai: {
    ask: "desktop.setup.remove_local_ai",
    confirm: "desktop.setup.remove_local_ai_confirm",
  },
  local_ai_program: {
    ask: "desktop.setup.remove_local_ai_program",
    confirm: "desktop.setup.remove_local_ai_program_confirm",
  },
} as const;

/** Whether the row has something, or a part of something, a removal deletes. */
function removable(row: SetupRow): boolean {
  return (
    row.state === "ready" ||
    row.state === "stale" ||
    row.state === "failed" ||
    row.state === "unknown"
  );
}

export function ItemRemoval({
  row,
  removals,
  onRemoved,
}: {
  row: SetupRow;
  /** The removals this row offers, in the order they are listed. */
  removals: readonly SetupRemoval[];
  /** Told once a removal is made, for what else shows what it took away. */
  onRemoved?: () => void;
}) {
  const t = useStrings();
  const store = useProvisioning();
  const [asking, setAsking] = useState<SetupRemoval | null>(null);
  const [removing, setRemoving] = useState(false);
  const [refusal, setRefusal] = useState<string | null>(null);
  const live = store.runOf(row.item)?.stage;
  if (!removable(row) || (live !== undefined && live !== "settled"))
    return null;

  const remove = (removal: SetupRemoval) => {
    setRemoving(true);
    store.control.remove(removal).then((code) => {
      setRemoving(false);
      setRefusal(code);
      if (code !== null) setAsking(null);
      else onRemoved?.();
    });
  };

  return (
    <div className="grid gap-1.5" data-setup-removal={row.item}>
      {refusal !== null && (
        <Alert role="alert">{refusalWords(t, refusal)}</Alert>
      )}
      {asking !== null ? (
        <>
          <p className="text-sm text-foreground">{t(WORDS[asking].confirm)}</p>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              size="xs"
              disabled={removing}
              onClick={() => remove(asking)}
            >
              {t("desktop.setup.remove_confirm_yes")}
            </Button>
            <Button
              variant="ghost"
              size="xs"
              disabled={removing}
              onClick={() => setAsking(null)}
            >
              {t("desktop.setup.remove_keep")}
            </Button>
          </div>
        </>
      ) : (
        <div className="flex flex-wrap gap-2">
          {removals.map((removal) => (
            <Button
              key={removal}
              variant="ghost"
              size="xs"
              disabled={store.control.pending}
              onClick={() => {
                setRefusal(null);
                setAsking(removal);
              }}
            >
              {t(WORDS[removal].ask)}
            </Button>
          ))}
        </div>
      )}
    </div>
  );
}
