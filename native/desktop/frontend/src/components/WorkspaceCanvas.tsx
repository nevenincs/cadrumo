import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty";
import { Icon } from "@/components/ui/icon";
import type { Translate } from "../shell/strings";

/** Nothing open above the bottom panel: the main area says so, and offers
 * each column back. */
export function WorkspaceCanvas({
  t,
  offersAgent,
  runAction,
}: {
  t: Translate;
  offersAgent: boolean;
  runAction: (id: string) => void;
}) {
  return (
    <EmptyState
      className="canvas bg-background"
      icon="canvas"
      heading={t("desktop.canvas.title")}
      description={t("desktop.canvas.lead")}
    >
      <div className="flex flex-wrap justify-center gap-2">
        {(
          [
            ["agent.toggle", "agent", "desktop.agent.show", offersAgent],
            ["tui.toggle", "tui", "desktop.tui.show", true],
            ["docs.toggle", "book", "desktop.docs.show", true],
          ] as const
        ).map(
          ([id, icon, labelKey, offered]) =>
            offered && (
              <Button key={id} variant="outline" onClick={() => runAction(id)}>
                <Icon name={icon} />
                {t(labelKey)}
              </Button>
            ),
        )}
      </div>
    </EmptyState>
  );
}
