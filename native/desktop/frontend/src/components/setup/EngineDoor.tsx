import { Button } from "@/components/ui/button";
import { cn } from "@/components/ui/cn";
import { engineDoorWords } from "../../shell/engineHealth";
import { useProvisioning } from "../../shell/provisioning";
import { useStrings } from "../../shell/strings";

/** Beside a local engine that does not run: the way on the service names,
 * where the window knows it. The local AI's setup door opens the
 * provisioning panel on the local AI's row, whose own recovery sets the
 * engine up again. A door the window does not know, or a window that offers
 * no setup, shows nothing, and no other way is offered in its place. */
export function EngineDoor({
  door,
  className,
}: {
  /** The door id the service names. */
  door: string;
  className?: string;
}) {
  const t = useStrings();
  const provisioning = useProvisioning();
  const words = engineDoorWords(t, door);
  if (words === null || !provisioning.offered) return null;
  return (
    <Button
      size="xs"
      variant="outline"
      className={cn("engine-door", className)}
      data-engine-door={door}
      onClick={() => provisioning.open(provisioning.localAiRow?.item ?? null)}
    >
      {words}
    </Button>
  );
}
