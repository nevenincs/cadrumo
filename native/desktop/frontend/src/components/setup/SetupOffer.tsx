import { Button } from "@/components/ui/button";
import { cn } from "@/components/ui/cn";
import { Icon } from "@/components/ui/icon";
import { useProvisioningRecovery } from "../../shell/provisioningRecovery";
import { needsSetup } from "../../shell/setup";
import { useStrings } from "../../shell/strings";
import { actionWords, itemName } from "./setupWords";

/** Beside something that could not run for a component this computer can
 * set up: the component by its name and the way into the window's setup
 * prompt on it. Its state is the prompt's to say. Nothing is shown for an
 * action that is not about setup, for a component setup cannot change, or
 * while the window offers no setup. */
export function SetupOffer({
  action,
  className,
}: {
  /** The setup action the refusal or verdict names; null for none. */
  action: string | null;
  className?: string;
}) {
  const t = useStrings();
  const recovery = useProvisioningRecovery();
  if (action === null) return null;
  const target = recovery.targetOf(action);
  if (target === null || (target !== "general" && !needsSetup(target)))
    return null;
  return (
    <span
      className={cn(
        "setup-offer inline-flex flex-wrap items-center gap-2",
        className,
      )}
      data-setup-offer={target === "general" ? "general" : target.item}
    >
      {target !== "general" && (
        <span className="font-medium text-foreground">
          {itemName(t, target.kind)}
        </span>
      )}
      <Button
        size="xs"
        variant="outline"
        onClick={() => recovery.offer(action)}
      >
        <Icon name="download" />
        {target === "general"
          ? t("desktop.setup.open")
          : (actionWords(t, target.recovery) ?? t("desktop.setup.open"))}
      </Button>
    </span>
  );
}
