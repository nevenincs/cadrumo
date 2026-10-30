import { Fragment, useState, type ReactNode } from "react";
import { IconButton } from "@/components/ui/icon-button";
import { Icon, type IconName } from "@/components/ui/icon";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { LedgerPort } from "../../../shell/ledger";
import { useStrings } from "../../../shell/strings";
import { GlyphMark } from "../../modelo/workspace/Marks";
import { WriteHold } from "../WritePause";
import { dateText } from "../movements/movementWords";
import { tokenWord } from "./AssetList";
import type { AssetListRow, FormKind } from "./assetsContract";
import { ASSET_KEYS, fieldWord } from "./assetsWords";

/** What a view in the detail's tabs is given to read the element. */
export type AssetViewArgs = {
  port: LedgerPort;
  assetId: string;
  locale: string;
  /** The year the pane stands on, where it has one. */
  year: number | null;
};
export type AssetView = (args: AssetViewArgs) => ReactNode;

/** The acts on one element, each a form of its own kind. */
const ACTS = [
  { kind: "descriptor", word: "describe", icon: "edit" },
  { kind: "correction", word: "correct", icon: "reset" },
  { kind: "claim", word: "claim", icon: "tick" },
  { kind: "baja", word: "dispose", icon: "archive" },
] as const satisfies readonly {
  kind: FormKind;
  word: keyof typeof ASSET_KEYS.action;
  icon: IconName;
}[];

type DetailTab = "plan" | "timeline" | "record";
const TABS: readonly DetailTab[] = ["plan", "timeline", "record"];

const DASH = "—";

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="min-w-0 [overflow-wrap:anywhere]">{children}</dd>
    </>
  );
}

/**
 * One element's detail: its name and serial, a baja mark where it has one,
 * one icon button per act, and the tabs Plan, Timeline and the read-only
 * record. The plan and the timeline are other parts' views, drawn in the
 * tabs; the record shows what the list states and nothing more.
 */
export function AssetDetail({
  port,
  locale,
  row,
  year,
  version,
  planView,
  timelineView,
  onAct,
  onClose,
}: {
  port: LedgerPort;
  locale: string;
  row: AssetListRow;
  year: number | null;
  /** Counts the list's reads, so a view reads again after each one. */
  version: number;
  planView?: AssetView;
  timelineView?: AssetView;
  /** Where the acts lead; without it the detail offers none. */
  onAct?: (kind: FormKind) => void;
  onClose: () => void;
}) {
  const t = useStrings();
  const [tab, setTab] = useState<DetailTab>("plan");
  const title = row.name ?? t(ASSET_KEYS.list.no_name);
  const args: AssetViewArgs = { port, assetId: row.asset_id, locale, year };
  const view = (draw: AssetView | undefined) =>
    draw ? <Fragment key={version}>{draw(args)}</Fragment> : null;
  return (
    <section
      aria-label={title}
      className="ledger-assets-detail flex min-h-0 flex-1 flex-col"
    >
      <header className="flex items-start gap-2 border-b px-3 py-2">
        <div className="min-w-0 flex-1">
          <h3 className="flex items-center gap-1.5 font-medium [overflow-wrap:anywhere]">
            {title}
            {row.baja && (
              <GlyphMark
                icon="archive"
                words={t(ASSET_KEYS.list.disposed, {
                  date: dateText(locale, row.baja.date, true),
                })}
                className="shrink-0 text-muted-foreground"
              />
            )}
          </h3>
          {row.serial && (
            <p className="text-xs text-muted-foreground [overflow-wrap:anywhere]">
              {row.serial}
            </p>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-0.5">
          {onAct &&
            ACTS.map((act) => (
              <WriteHold key={act.kind}>
                <IconButton
                  label={t(ASSET_KEYS.action[act.word])}
                  onClick={() => onAct(act.kind)}
                >
                  <Icon name={act.icon} />
                </IconButton>
              </WriteHold>
            ))}
          <IconButton label={t("desktop.ledger.close")} onClick={onClose}>
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
          {view(planView)}
        </TabsContent>
        <TabsContent value="timeline" className="overflow-y-auto">
          {view(timelineView)}
        </TabsContent>
        <TabsContent value="record" className="overflow-y-auto p-3">
          <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1.5 text-sm">
            <Fact label={fieldWord(t, "name")}>
              {row.name ?? t(ASSET_KEYS.list.no_name)}
            </Fact>
            <Fact label={fieldWord(t, "serial")}>{row.serial ?? DASH}</Fact>
            <Fact label={fieldWord(t, "kind")}>
              {tokenWord(t, "kind", row.kind_key)}
            </Fact>
            <Fact label={fieldWord(t, "method")}>
              {tokenWord(t, "method", row.method_key)}
            </Fact>
            <Fact label={fieldWord(t, "in_service_date")}>
              {dateText(locale, row.in_service_date, true)}
            </Fact>
            <Fact label={t(ASSET_KEYS.plan.column.revision)}>
              <span className="tabular-nums">{row.revision_number}</span>
            </Fact>
            {row.baja && (
              <>
                <Fact label={fieldWord(t, "baja_date")}>
                  {dateText(locale, row.baja.date, true)}
                </Fact>
                <Fact label={fieldWord(t, "baja_reason")}>
                  {tokenWord(t, "reason", row.baja.reason_key)}
                </Fact>
              </>
            )}
          </dl>
        </TabsContent>
      </Tabs>
    </section>
  );
}
