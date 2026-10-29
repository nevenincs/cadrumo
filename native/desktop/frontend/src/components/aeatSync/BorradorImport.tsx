import { useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { aeatSyncFailure } from "../../shell/aeatSync";
import type {
  AeatSyncResultsPort,
  BorradorImportResult,
} from "../../shell/aeatSyncResults";
import { useStrings } from "../../shell/strings";

/**
 * The Borrador 100 is not read from AEAT: the person downloads it there and
 * imports the PDF here. The file is chosen in the system dialog and only its
 * name reaches the window.
 */
export function BorradorImport({
  port,
  profile,
  onImported,
}: {
  port: AeatSyncResultsPort;
  profile: string;
  onImported(): void;
}) {
  const t = useStrings();
  const [busy, setBusy] = useState(false);
  const [name, setName] = useState<string | null>(null);
  const [outcome, setOutcome] = useState<
    BorradorImportResult | "unknown" | null
  >(null);
  const choose = async () => {
    setBusy(true);
    setOutcome(null);
    try {
      const file = await port.pickBorrador();
      if (!file) return;
      setName(file.name);
      const result = await port.importBorrador(profile, file.token);
      setOutcome(result);
      if (result === "imported") onImported();
    } catch (error) {
      setOutcome(aeatSyncFailure(error) === "unknown" ? "unknown" : "failed");
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-3">
        <Button
          size="xs"
          variant="outline"
          pending={busy}
          onClick={() => void choose()}
        >
          <Icon name="upload" size="xs" />
          {t("desktop.aeat_sync.results.borrador.import")}
        </Button>
      </div>
      {outcome && (
        <Alert
          role={outcome === "imported" ? "status" : "alert"}
          tone={
            outcome === "imported"
              ? "success"
              : outcome === "nothing_found"
                ? "neutral"
                : "danger"
          }
          icon={
            <Icon
              name={
                outcome === "imported"
                  ? "check"
                  : outcome === "nothing_found"
                    ? "info"
                    : "alert"
              }
            />
          }
        >
          {t(`desktop.aeat_sync.results.borrador.${outcome}`, {
            name: name ?? "",
          })}
        </Alert>
      )}
    </div>
  );
}
