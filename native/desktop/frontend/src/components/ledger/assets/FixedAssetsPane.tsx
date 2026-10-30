import { useEffect, useState } from "react";
import { Alert } from "@/components/ui/alert";
import { EmptyState } from "@/components/ui/empty";
import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import type { LedgerPort } from "../../../shell/ledger";
import type { ActivityAssetListResult } from "../../../shell/ledgerSetup";
import { useStrings } from "../../../shell/strings";
import { RightPanel } from "../inspector/RightPanel";
import { setupCall, type SetupCall } from "../setup/setupModel";
import { CallLine, Reading } from "../setup/SetupParts";
import { useWritePause, WriteHold } from "../WritePause";
import { AssetDetail } from "./AssetDetail";
import { AssetForm } from "./AssetForm";
import { BajaForm } from "./BajaForm";
import { ClaimFlow } from "./ClaimFlow";
import { CorrectForm } from "./CorrectForm";
import { DescribeForm } from "./DescribeForm";
import { AssetList, CountPill, callRefusal } from "./AssetList";
import { type FormKind } from "./assetFields";
import { openingYear } from "./assetWrites";
import { ASSET_KEYS, COUNT_KINDS, refusalText } from "./assetsWords";
import { FilingHandoffPanel } from "./FilingHandoffPanel";
import { YearStepper } from "./YearStepper";

/** An act asked for: a new element, or one on an element already listed. */
type AssetFormRequest = { kind: FormKind; assetId: string | null };

type ListResult = ActivityAssetListResult;

/** Reads the register's elements while the pane shows, again after a
 * `reload` or the page's re-read, and drops what it read with the profile.
 * The last answer stays while the next is read. `version` counts answers. */
function useAssetList(port: LedgerPort, reader: string | null) {
  const [call, setCall] = useState<SetupCall<ListResult> | null>(null);
  const [round, setRound] = useState(0);
  const [version, setVersion] = useState(0);
  const { round: reread } = useWritePause();
  useEffect(() => {
    setCall(null);
  }, [port, reader]);
  useEffect(() => {
    if (reader === null) return;
    let active = true;
    void (async () => {
      const answer = await setupCall(
        port,
        "ledger.actividad-asset.list",
        {},
        false,
      );
      if (!active) return;
      setCall(answer);
      setVersion((count) => count + 1);
    })();
    return () => {
      active = false;
    };
  }, [port, reader, round, reread]);
  return { call, version, reload: () => setRound((count) => count + 1) };
}

const noop = () => undefined;

/**
 * Assets › Fixed assets: the register's elements for a year, the detail of
 * the chosen one beside them, and the filing handoff under them. The list is
 * the backend's answer as it stands; an unread register, an empty one, a
 * refusal and a failure are each said apart, and none reads as the others.
 * The years on offer are the ones the list serves; the pane stands on the
 * latest of them that has begun, else the earliest.
 */
export function FixedAssetsPane({
  port,
  reader,
  locale,
  onOpenLink,
}: {
  port: LedgerPort;
  /** Whose ledger; null while the account withholds it. */
  reader: string | null;
  locale: string;
  onOpenLink?: (url: string) => void;
}) {
  const t = useStrings();
  const { call, version, reload } = useAssetList(port, reader);
  const [selected, setSelected] = useState<string | null>(null);
  const [chosenYear, setYear] = useState<number | null>(null);
  const [request, setRequest] = useState<AssetFormRequest | null>(null);
  const [width, setWidth] = useState<number | null>(null);

  const answer = call?.kind === "done" ? call.result : null;
  const loaded = answer?.outcome === "succeeded" ? answer : null;
  const rows = loaded?.rows ?? [];
  // The years the registry carries official tables for, and the later years
  // some element is read in as an estimate.
  const official = loaded?.years ?? [];
  const estimated = [
    ...new Set(rows.flatMap((found) => found.projected_years)),
  ].sort((a, b) => a - b);
  const offered = [...official, ...estimated];
  const year = chosenYear ?? openingYear(offered, new Date().getFullYear());
  const row = rows.find((found) => found.asset_id === selected) ?? null;

  const form = () => {
    if (!request) return null;
    const act = {
      port,
      reader,
      locale,
      taxYear: year,
      onClose: () => setRequest(null),
      onWritten: reload,
    };
    const { kind, assetId } = request;
    if (assetId === null)
      return <AssetForm {...act} kind="element" assetId={null} />;
    if (kind === "descriptor")
      return <DescribeForm {...act} assetId={assetId} />;
    if (kind === "correction")
      return <CorrectForm {...act} assetId={assetId} />;
    if (kind === "baja") return <BajaForm {...act} assetId={assetId} />;
    return year === null ? null : (
      <ClaimFlow {...act} assetId={assetId} taxYear={year} />
    );
  };

  const body = () => {
    if (reader === null)
      return (
        <EmptyState
          icon="lock"
          heading={t("desktop.ledger.assets.list.unavailable")}
        />
      );
    if (call === null) return <Reading label={t("desktop.ledger.loading")} />;
    if (call.kind !== "done")
      return <CallLine call={call} refusal={callRefusal(t, call)} />;
    if (answer?.outcome === "refused" || loaded?.rows === null)
      return (
        <Alert
          tone="danger"
          role="alert"
          icon={<Icon name="refused" />}
          className="ledger-assets-refused"
        >
          {refusalText(t, answer?.refusal ?? null)}
        </Alert>
      );
    if (rows.length === 0)
      return (
        <EmptyState
          icon="book"
          heading={t(ASSET_KEYS.list.empty)}
          className="ledger-assets-empty"
        />
      );
    return (
      <AssetList
        rows={rows}
        selected={row?.asset_id ?? null}
        onSelect={setSelected}
        locale={locale}
      />
    );
  };

  return (
    <div className="ledger-assets-fixed flex min-h-0 flex-1">
      <div className="flex min-w-0 flex-1 flex-col gap-3 overflow-y-auto">
        <div className="flex flex-wrap items-center gap-2">
          <WriteHold>
            <IconButton
              label={t(ASSET_KEYS.action.add)}
              onClick={() => setRequest({ kind: "element", assetId: null })}
            >
              <Icon name="plus" />
            </IconButton>
          </WriteHold>
          <YearStepper
            value={year}
            years={offered}
            estimated={estimated}
            onChange={setYear}
          />
          {year !== null && estimated.includes(year) && (
            <span className="ledger-assets-estimated inline-flex items-center gap-1 text-xs text-muted-foreground">
              <Icon name="info" size="xs" />
              {t(ASSET_KEYS.year_estimated_note)}
            </span>
          )}
          <span className="flex-1" />
          <span
            role="group"
            aria-label={t("desktop.ledger.assets.list.summary")}
            className="flex flex-wrap items-center gap-1"
          >
            {COUNT_KINDS.map((kind) => {
              const count = rows.reduce(
                (sum, found) => sum + found.findings[kind],
                0,
              );
              return count > 0 ? (
                <CountPill key={kind} kind={kind} count={count} />
              ) : null;
            })}
          </span>
        </div>
        {form()}
        {body()}
        {loaded && (
          <FilingHandoffPanel
            port={port}
            reader={reader}
            locale={locale}
            year={year}
          />
        )}
      </div>
      {row && (
        <RightPanel
          mode="movement"
          onMode={noop}
          width={width}
          onWidth={setWidth}
          defaultRem={32}
          label={t("desktop.ledger.assets.detail.panel")}
        >
          <AssetDetail
            port={port}
            reader={reader}
            locale={locale}
            row={row}
            year={year}
            version={version}
            onOpenLink={onOpenLink}
            onAct={(kind) => setRequest({ kind, assetId: row.asset_id })}
            onClose={() => setSelected(null)}
          />
        </RightPanel>
      )}
    </div>
  );
}
