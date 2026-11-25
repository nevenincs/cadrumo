import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { useModelList } from "../../../shell/agentModelList";
import { remedyAction, type ConsentStep } from "./modelRefusal";

/** The two remedies a refusal for want of off-host consent serves, as
 * controls labelled with the backend's words. Switching to a model on this
 * computer opens the agent's model picker; where the window has no door to a
 * remedy, choosing it says with the served words where the person goes.
 * Where the surface can record the grant, `onAuthorise` is that door. */
export function ConsentRemedies({
  step,
  onAuthorise,
}: {
  step: ConsentStep;
  onAuthorise?: () => void;
}) {
  const picker = useModelList();
  const [notice, setNotice] = useState<string | null>(null);
  return (
    <div className="ledger-consent-remedies grid gap-1.5">
      <span className="flex flex-wrap gap-2">
        {step.remedies.map((remedy) => (
          <Button
            key={remedy.kind}
            size="xs"
            variant="outline"
            className={`ledger-consent-${remedy.kind}`}
            onClick={() => {
              if (remedy.kind === "authorise_off_host" && onAuthorise) {
                setNotice(null);
                onAuthorise();
                return;
              }
              const action = remedyAction(remedy, picker);
              if (action.kind === "open_model_picker") {
                setNotice(null);
                picker?.open();
              } else setNotice(action.words);
            }}
          >
            <Icon
              name={
                remedy.kind === "switch_to_local_lane" ? "settings" : "agent"
              }
            />
            {remedy.words}
          </Button>
        ))}
      </span>
      {notice !== null && (
        <span role="status" className="text-sm text-muted-foreground">
          {notice}
        </span>
      )}
    </div>
  );
}
