import { useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import type { SetupRemoval, SetupRow } from "../../ipc/componentSetup";
import { useProvisioning } from "../../shell/provisioning";
import { useStrings } from "../../shell/strings";
import { refusalWords } from "./setupWords";

// An item row's removals: a person who no longer wants the browser for the
// tax agency website, or the local AI, on this computer deletes it here,
// after saying so twice. The engine serves which removals a row offers: the
// browser's one; the local AI's two, all of it with the models on the
// person's lists, or its program alone with every model kept; and none where
// removing would repair nothing. The engine refuses while the item sets up,
// and a later check or setup puts it back.

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

type ItemRemovalProps = {
  row: SetupRow;
  /** Of the removals the row serves, those this place lists; signed out, the
   * local AI has no person's model list for a removal to take. */
  removals: readonly SetupRemoval[];
  /** Told once a removal is made, for what else shows what it took away. */
  onRemoved?: () => void;
};

// The question and the answer to it belong to a stretch in which the row has
// something to remove. The offer is mounted only for that stretch, so a row
// that stops having it -- the removal itself, a setup under way -- takes the
// question with it, and a row that has it again starts without one.
export function ItemRemoval(props: ItemRemovalProps) {
  const store = useProvisioning();
  const live = store.runOf(props.row.item)?.stage;
  const removals = props.row.removals.filter((removal) =>
    props.removals.includes(removal),
  );
  if (removals.length === 0 || (live !== undefined && live !== "settled"))
    return null;
  return <ItemRemovalOffer {...props} removals={removals} />;
}

function ItemRemovalOffer({ row, removals, onRemoved }: ItemRemovalProps) {
  const t = useStrings();
  const store = useProvisioning();
  const [asking, setAsking] = useState<SetupRemoval | null>(null);
  const [removing, setRemoving] = useState(false);
  const [refusal, setRefusal] = useState<string | null>(null);

  const remove = (removal: SetupRemoval) => {
    setRemoving(true);
    store.control.remove(removal).then((code) => {
      setRemoving(false);
      setRefusal(code);
      // Asked and answered, refused or done: the question is not asked again.
      setAsking(null);
      if (code === null) onRemoved?.();
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
              disabled={store.control.busy(row.item)}
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
