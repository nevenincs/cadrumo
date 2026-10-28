import { Button } from "@/components/ui/button";
import { cn } from "@/components/ui/cn";
import { Icon } from "@/components/ui/icon";
import { useProvisioning } from "../../shell/provisioning";
import { needsSetup } from "../../shell/setup";
import { useStrings } from "../../shell/strings";
import { actionWords, itemName, rowSentence } from "./setupWords";

/** Beside something that could not run for a component: the component by
 * its name and the way into the provisioning panel on it, when its row
 * says setup can act now. A row setup cannot change from here says so
 * instead, as the component's name and the row's own sentence, with nothing
 * to press. Nothing is shown for an action that is not about setup, while
 * the setup status is loading or cannot be read, or while the window offers
 * no setup. */
export function SetupOffer({
  action,
  className,
}: {
  /** The setup action the refusal or verdict names; null for none. */
  action: string | null;
  className?: string;
}) {
  const t = useStrings();
  const recovery = useProvisioning();
  if (action === null) return null;
  const target = recovery.targetOf(action);
  if (target === null) return null;
  if (target !== "general" && !needsSetup(target))
    return (
      <span
        className={cn("setup-held text-sm text-muted-foreground", className)}
        data-setup-held={target.item}
      >
        {`${itemName(t, target.item)}: ${rowSentence(t, target)}`}
      </span>
    );
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
          {itemName(t, target.item)}
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
