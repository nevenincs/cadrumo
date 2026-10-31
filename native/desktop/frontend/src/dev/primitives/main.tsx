// The development entry for one primitive at a time: the data grid, the
// plain table or the grid's companions over made-up rows, or the ledger's
// export dialog over the scenario ledger, on the shell's own theme, in the
// scheme the address asks for. Only primitives.html loads this module.

import { StrictMode } from "react";
import ReactDOM from "react-dom/client";
import { TooltipProvider } from "@/components/ui/tooltip";
import "../index.css";
import { CompanionsHarness } from "./CompanionsHarness";
import { DataGridHarness, DataTableHarness } from "./DataGridHarness";
import { EditorHarness } from "./EditorHarness";
import { LedgerExportHarness } from "./LedgerExportHarness";

import "virtual:desktop-palette.css";

const params = new URLSearchParams(window.location.search);
const scheme = params.get("scheme") === "dark" ? "dark" : "light";
document.documentElement.dataset.scheme = scheme;
const count = Math.max(0, Math.trunc(Number(params.get("rows") ?? 40) || 0));
const harness = params.get("harness");

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <StrictMode>
    <TooltipProvider>
      <main className="flex h-dvh min-h-0 flex-col bg-background p-4 text-foreground">
        <h1 className="sr-only">{harness ?? "grid"}</h1>
        {harness === "table" ? (
          <DataTableHarness />
        ) : harness === "companions" ? (
          <CompanionsHarness />
        ) : harness === "editor" ? (
          <EditorHarness params={params} />
        ) : harness === "ledger-export" ? (
          <LedgerExportHarness
            staged={Math.max(0, Math.trunc(Number(params.get("staged")) || 0))}
          />
        ) : (
          <DataGridHarness count={count} grouped={params.has("grouped")} />
        )}
      </main>
    </TooltipProvider>
  </StrictMode>,
);
