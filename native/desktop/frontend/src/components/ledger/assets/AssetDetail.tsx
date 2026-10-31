import { useState, type ReactNode } from "react";
import { IconButton } from "@/components/ui/icon-button";
import { Icon, type IconName } from "@/components/ui/icon";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { LedgerPort } from "../../../shell/ledger";
import { useStrings } from "../../../shell/strings";
import { WriteHold } from "../WritePause";
import { dateText } from "../movements/movementWords";
import { AmortizationPlan } from "./AmortizationPlan";
import { AssetTimeline } from "./AssetTimeline";
import { NotApplicable, NotKnown } from "./AssetList";
import { figureText } from "./planWords";
import type { AssetListRow } from "../../../shell/ledgerSetup";
import type { FormKind } from "./assetFields";
import {
  ASSET_KEYS,
  bajaText,
  fieldWord,
  openingRemedy,
  tokenWord,
  wordOfKey,
} from "./assetsWords";

/** The acts on one element, each a form of its own kind. */
const ACTS = [
  { kind: "descriptor", word: "describe", icon: "page" },
  { kind: "correction", word: "correct", icon: "edit" },
  { kind: "claim", word: "claim", icon: "tick" },
  { kind: "baja", word: "dispose", icon: "archive" },
] as const satisfies readonly {
  kind: FormKind;
  word: keyof typeof ASSET_KEYS.action;
  icon: IconName;
}[];

type DetailTab = "plan" | "timeline" | "record";
const TABS: readonly DetailTab[] = ["plan", "timeline", "record"];

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="min-w-0 [overflow-wrap:anywhere]">{children}</dd>
    </>
  );
}

/**
 * One element's detail: its name and serial number, one icon button per act,
 * and the tabs Plan, Timeline and the read-only record. The record shows what
 * the list states and nothing more.
 */
export function AssetDetail({
  port,
  reader,
  locale,
  row,
  year,
  version,
  onOpenLink,
  onAct,
  onCorrectClaim,
  onClose,
}: {
  port: LedgerPort;
  reader: string | null;
  locale: string;
  row: AssetListRow;
  year: number | null;
  /** Counts the list's reads, so a view reads again after each one. */
  version: number;
  onOpenLink?: (url: string) => void;
  onAct: (kind: FormKind) => void;
  /** Asks to correct one claim of a year; the plan offers it on each claim in
   * effect. */
  onCorrectClaim?: (claimId: string, year: number) => void;
  onClose: () => void;
}) {
  const t = useStrings();
  const [tab, setTab] = useState<DetailTab>("plan");
  const title = row.name ?? t(ASSET_KEYS.list.no_name);
  return (
    <section
      aria-label={title}
      className="ledger-assets-detail flex min-h-0 flex-1 flex-col"
    >
      <header className="flex items-start gap-2 border-b px-3 py-2">
        <div className="min-w-0 flex-1">
          <h3 className="flex items-center gap-1.5 font-medium [overflow-wrap:anywhere]">
            {title}
          </h3>
          {row.serial_number && (
            <p className="text-xs text-muted-foreground [overflow-wrap:anywhere]">
              {row.serial_number}
            </p>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-0.5">
          {ACTS.map((act) => (
            <WriteHold key={act.kind}>
              <IconButton
                label={
                  act.kind === "baja" && row.disposal !== null
                    ? t("desktop.ledger.assets.action.change_baja")
                    : t(ASSET_KEYS.action[act.word])
                }
                onClick={() => onAct(act.kind)}
              >
                <Icon name={act.icon} />
              </IconButton>
            </WriteHold>
          ))}
          <IconButton
            label={t("desktop.ledger.assets.detail.close")}
            onClick={onClose}
          >
            <Icon name="close" />
          </IconButton>
        </div>
      </header>
      <Tabs
        value={tab}
        onValueChange={(next) => setTab(next as DetailTab)}
        className="flex min-h-0 flex-1 flex-col"
      >
        <TabsList
          aria-label={t("desktop.ledger.assets.detail.tabs")}
          className="h-control-md shrink-0 px-3"
        >
          {TABS.map((value) => (
            <TabsTrigger key={value} value={value} className="text-sm">
              {t(ASSET_KEYS.detail[value])}
            </TabsTrigger>
          ))}
        </TabsList>
        <TabsContent value="plan" className="overflow-y-auto">
          <AmortizationPlan
            key={version}
            port={port}
            reader={reader}
            assetId={row.asset_id}
            locale={locale}
            year={year}
            disposal={row.disposal}
            onOpenLink={onOpenLink}
            onCorrectClaim={onCorrectClaim}
          />
        </TabsContent>
        <TabsContent value="timeline" className="overflow-y-auto">
          <AssetTimeline
            key={version}
            port={port}
            reader={reader}
            assetId={row.asset_id}
            locale={locale}
          />
        </TabsContent>
        <TabsContent value="record" className="overflow-y-auto p-3">
          <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1.5 text-sm">
            <Fact label={fieldWord(t, "name")}>
              {row.name ?? t(ASSET_KEYS.list.no_name)}
            </Fact>
            <Fact label={fieldWord(t, "serial_number")}>
              {row.serial_number ?? (
                <NotKnown why={t(ASSET_KEYS.list.serial_missing)} />
              )}
            </Fact>
            <Fact label={fieldWord(t, "asset_kind")}>
              {tokenWord(t, "asset_kind", row.asset_kind)}
            </Fact>
            <Fact label={fieldWord(t, "amortization.method")}>
              {tokenWord(t, "method", row.method)}
            </Fact>
            <Fact label={fieldWord(t, "in_service_date")}>
              {dateText(locale, row.in_service_date, true)}
            </Fact>
            <Fact label={t(ASSET_KEYS.list.column.state)}>
              {tokenWord(t, "register_state", row.state)}
            </Fact>
            {row.disposal !== null && (
              <>
                <Fact label={fieldWord(t, "disposal.disposal_date")}>
                  {dateText(locale, row.disposal.disposal_date, true)}
                </Fact>
                <Fact label={t(ASSET_KEYS.detail.baja_reason)}>
                  {wordOfKey(t, row.disposal.reason_key) ??
                    tokenWord(t, "disposal_reason", row.disposal.reason)}
                </Fact>
              </>
            )}
            <Fact label={fieldWord(t, "basis.basis_amount")}>
              {figureText(locale, row.basis)}
            </Fact>
            <Fact label={t(ASSET_KEYS.list.column.accumulated)}>
              {figureText(locale, row.accumulated) ?? (
                <NotKnown why={openingRemedy(t)} />
              )}
            </Fact>
            <Fact label={t(ASSET_KEYS.list.column.pending)}>
              {!row.pending_applies ? (
                <NotApplicable
                  why={
                    row.disposal === null
                      ? null
                      : bajaText(t, locale, row.disposal)
                  }
                />
              ) : (
                (figureText(locale, row.pending) ?? (
                  <NotKnown why={openingRemedy(t)} />
                ))
              )}
            </Fact>
          </dl>
        </TabsContent>
      </Tabs>
    </section>
  );
}
