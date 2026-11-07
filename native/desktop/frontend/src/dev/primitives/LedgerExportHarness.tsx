import { useMemo, useState } from "react";
import { ExportDialog } from "@/components/ledger/transfer/ExportDialog";
import type { LedgerExportFormat } from "@/shell/ledger";
import { SCENARIO_TODAY } from "../assetsRegister";
import { ledgerFixture } from "../ledgerFixture";

/** The scenario's tax year: the one of its day. */
const scenarioYear = Number(SCENARIO_TODAY.slice(0, 4));

declare global {
  interface Window {
    /** What the export dialog asked of its page, in order. */
    __exportEvents?: string[];
  }
}

/** The Ledger page's Export dialog alone, over the scenario's made-up
 * ledger, with as many staged changes as the address names: the state a
 * page with unsaved edits opens it in. */
export function LedgerExportHarness({ staged }: { staged: number }) {
  const port = useMemo(
    () =>
      ledgerFixture({
        say: () => {},
        wait: () => Promise.resolve(),
        signedIn: () => true,
        shape: "fixture",
      }),
    [],
  );
  const [format, setFormat] = useState<LedgerExportFormat>("csv");
  const [open, setOpen] = useState(true);
  const record = (event: string) => {
    window.__exportEvents = [...(window.__exportEvents ?? []), event];
  };
  if (!open) return <p>Closed</p>;
  return (
    <ExportDialog
      port={port}
      locale="en"
      period={{ year: scenarioYear, code: "4T" }}
      years={[scenarioYear]}
      fallbackYear={scenarioYear}
      format={format}
      onFormat={setFormat}
      staged={staged}
      onReviewStaged={() => record("review")}
      copy={async (text) => record(`copy:${text.split("\n").length}`)}
      onClose={() => {
        record("close");
        setOpen(false);
      }}
    />
  );
}
