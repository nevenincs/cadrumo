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

/**
 * The Borrador 100 is not read from AEAT: the person downloads it there and
 * imports the PDF here. The file is chosen in the system dialog and only its
 * name reaches the window.
 */
export function BorradorImport({
  port,
  profile,
  years,
  onImported,
}: {
  port: AeatSyncResultsPort;
  profile: string;
  /** The filing years on offer, latest first, as the host serves them. */
  years: readonly number[];
  onImported(): void;
}) {
  const t = useStrings();
  const [picked, setPicked] = useState<number | null>(null);
  // The latest year until the person picks one the host still offers.
  const year = picked !== null && years.includes(picked) ? picked : years[0];
  const [busy, setBusy] = useState(false);
  const [name, setName] = useState<string | null>(null);
  const [outcome, setOutcome] = useState<
    BorradorImportResult["outcome"] | "unknown" | null
  >(null);
  const [unowned, setUnowned] = useState(0);
  const choose = async () => {
    setBusy(true);
    setOutcome(null);
    setUnowned(0);
    try {
      if (year === undefined) return;
      const file = await port.pickBorrador();
      if (!file) return;
      setName(file.name);
      const result = await port.importBorrador(profile, file.token, year);
      setOutcome(result.outcome);
      setUnowned(result.unowned);
      if (result.outcome !== "nothing_found" && result.outcome !== "failed")
        onImported();
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
          value={year ?? ""}
          disabled={busy || year === undefined}
          onChange={(event) => setPicked(Number(event.target.value))}
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
          disabled={year === undefined}
          onClick={() => void choose()}
        >
          <Icon name="upload" size="xs" />
          {t("desktop.aeat_sync.results.borrador.import")}
        </Button>
      </div>
      {outcome && (
        <Alert
          role={
            outcome === "failed" || outcome === "unknown" ? "alert" : "status"
          }
          tone={
            outcome === "captured"
              ? "success"
              : outcome === "failed" || outcome === "unknown"
                ? "danger"
                : "neutral"
          }
          icon={
            <Icon
              name={
                outcome === "captured"
                  ? "check"
                  : outcome === "failed" || outcome === "unknown"
                    ? "alert"
                    : "info"
              }
            />
          }
        >
          <p>
            {t(`desktop.aeat_sync.results.borrador.${outcome}`, {
              name: name ?? "",
            })}
          </p>
          {unowned > 0 && (
            <p>
              {t(
                `desktop.aeat_sync.results.borrador.unowned.${unowned === 1 ? "one" : "other"}`,
                { count: unowned },
              )}
            </p>
          )}
        </Alert>
      )}
    </div>
  );
}
