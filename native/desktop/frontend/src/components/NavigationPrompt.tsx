import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { NavigatorPrompt } from "../shell/navigation/useNavigator";
import { useStrings } from "../shell/strings";

/**
 * The navigator's own question, for owners that leave the asking to it:
 * whether to discard unsaved work and go, or stay; or, for the window's
 * close, whether to close over work still in flight. Dismissing it stays.
 */
export function NavigationPrompt({ prompt }: { prompt: NavigatorPrompt }) {
  const t = useStrings();
  const leave = prompt.kind === "leave";
  const go = leave ? prompt.discard : prompt.close;
  return (
    <Dialog open onOpenChange={(open) => !open && prompt.stay()}>
      <DialogContent
        // It hands on the very navigation it asks about.
        modalLayer={false}
        className="navigation-prompt w-dialog-md"
        closeLabel={t(
          leave
            ? "desktop.navigation.leave.stay"
            : "desktop.navigation.close_busy.stay",
        )}
      >
        <DialogHeader>
          <DialogTitle>
            {t(
              leave
                ? "desktop.navigation.leave.title"
                : "desktop.navigation.close_busy.title",
            )}
          </DialogTitle>
          <DialogDescription>
            {t(
              leave
                ? "desktop.navigation.leave.description"
                : "desktop.navigation.close_busy.description",
            )}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button
            autoFocus
            variant="ghost"
            className="navigation-prompt-stay"
            onClick={prompt.stay}
          >
            {t(
              leave
                ? "desktop.navigation.leave.stay"
                : "desktop.navigation.close_busy.stay",
            )}
          </Button>
          <Button
            variant="outline"
            className="navigation-prompt-go"
            onClick={go}
          >
            {t(
              leave
                ? "desktop.navigation.leave.discard"
                : "desktop.navigation.close_busy.close",
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
