import { useMemo, useState } from "react";
import type { ITheme } from "@xterm/xterm";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { Host } from "../../shell/host";
import { useStrings } from "../../shell/strings";
import { TerminalPane, type TerminalStatus } from "../TerminalPane";

export function AeatSetupDialog({
  host,
  profile,
  theme,
  fontSize,
  onClose,
  onDone,
}: {
  host: Host;
  profile: string;
  theme: ITheme;
  fontSize: number;
  onClose: () => void;
  onDone: () => void;
}) {
  const t = useStrings();
  const [status, setStatus] = useState<TerminalStatus>({ phase: "starting" });
  const target = useMemo(
    () => ({ aeat_setup: { profile_id: profile } }),
    [profile],
  );
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent
        className="w-[95vw]"
        closeLabel={t("desktop.agent.cancel")}
      >
        <DialogHeader>
          <DialogTitle>{t("desktop.agent.aeat_setup_title")}</DialogTitle>
          <DialogDescription>
            {t("desktop.agent.aeat_setup_help")}
          </DialogDescription>
        </DialogHeader>
        <div className="relative flex h-[65vh] min-h-80 flex-col">
          <TerminalPane
            host={host}
            kind="tui"
            target={target}
            shown
            theme={theme}
            fontSize={fontSize}
            label={t("desktop.agent.aeat_setup_title")}
            isShellChord={() => false}
            onStatus={(_, next) => setStatus(next)}
            onMenu={() => undefined}
            onAppearanceToggle={() => undefined}
            register={(_, api) => api.focus()}
          />
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            {t("desktop.agent.cancel")}
          </Button>
          <Button
            disabled={status.phase !== "exited" || status.code !== 0}
            onClick={onDone}
          >
            {t("desktop.agent.aeat_setup_return")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
