import { useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { NativeSelect } from "@/components/ui/native-select";
import { aeatSyncFailure } from "../../shell/aeatSync";
import type {
  AeatSyncResultsPort,
  BorradorImportResult,
} from "../../shell/aeatSyncResults";
import { useStrings } from "../../shell/strings";

/** How many filing years the person can choose from. */
const YEARS_OFFERED = 6;

/** The filing years on offer, latest first. The Borrador 100 for a year is
 * downloaded the year after, so the latest is the previous calendar year; the
 * status the host serves names no year. */
export function borradorYears(today: Date = new Date()): number[] {
  const latest = today.getFullYear() - 1;
  return Array.from({ length: YEARS_OFFERED }, (_, i) => latest - i);
}

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
  const years = borradorYears();
  const [year, setYear] = useState(years[0]);
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
      const result = await port.importBorrador(profile, file.token, year);
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
        <NativeSelect
          controlSize="sm"
          className="w-24"
          aria-label={t("desktop.aeat_sync.results.borrador.year")}
          value={year}
          disabled={busy}
          onChange={(event) => setYear(Number(event.target.value))}
        >
          {years.map((value) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </NativeSelect>
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
