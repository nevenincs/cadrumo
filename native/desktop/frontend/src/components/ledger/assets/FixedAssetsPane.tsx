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
import { ASSET_KEYS, COUNT_KINDS, refusalText } from "./assetsWords";
import { FilingHandoffPanel } from "./FilingHandoffPanel";
import { YearStepper } from "./YearStepper";

/** An act asked for: a new element, or one on an element already listed. A
 * dotación asked for may correct one recorded, in a year of the plan. */
type AssetFormRequest = {
  kind: FormKind;
  assetId: string | null;
  supersedes?: string;
  year?: number;
};

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
 * Assets › Fixed assets: the register's elements, the detail of the chosen
 * one beside them, and the filing handoff under them. The list is the
 * backend's answer as it stands, for all years; an unread register, an empty
 * one, a refusal and a failure are each said apart, and none reads as the
 * others. The year chosen above the handoff is the year its amounts go to.
 * The years on offer are the ones the list serves; the pane stands on the
 * year the register says it opens on. A form on an element
 * opens at the top of its panel, and closes when another element is chosen.
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
  const [asked, setAsked] = useState(0);
  const [added, setAdded] = useState(false);
  const [width, setWidth] = useState<number | null>(null);

  const ask = (next: AssetFormRequest | null) => {
    setRequest(next);
    setAsked((count) => count + 1);
    setAdded(false);
  };
  // Another element, or none, takes down a form on the one that was chosen.
  const select = (assetId: string | null) => {
    setSelected(assetId);
    if (
      request !== null &&
      request.assetId !== null &&
      request.assetId !== assetId
    )
      ask(null);
  };

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
  const year = chosenYear ?? loaded?.default_year ?? null;
  const row = rows.find((found) => found.asset_id === selected) ?? null;
  // The names the list holds; an element not yet described has none, and is
  // never said by its id.
  const names = new Map(
    rows.flatMap((found) =>
      found.name !== null && found.name.trim() !== ""
        ? [[found.asset_id, found.name] as const]
        : [],
    ),
  );

  const form = () => {
    if (!request) return null;
    const act = {
      port,
      reader,
      locale,
      taxYear: year,
      onClose: () => ask(null),
      onWritten: reload,
    };
    const { kind, assetId } = request;
    if (assetId === null)
      return (
        <AssetForm
          {...act}
          kind="element"
          assetId={null}
          onAdded={(id) => {
            ask(null);
            setAdded(true);
            setSelected(id);
          }}
        />
      );
    if (kind === "descriptor")
      return <DescribeForm {...act} assetId={assetId} />;
    if (kind === "correction")
      return <CorrectForm {...act} assetId={assetId} />;
    if (kind === "baja") return <BajaForm {...act} assetId={assetId} />;
    return year === null ? null : (
      <ClaimFlow
        {...act}
        assetId={assetId}
        taxYear={year}
        initialYear={request.year ?? null}
        supersedes={request.supersedes ?? null}
        onCorrectElement={() => ask({ kind: "correction", assetId })}
      />
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
        onSelect={select}
        locale={locale}
      />
    );
  };

  const onElement = request !== null && request.assetId !== null;
  return (
    <div className="ledger-assets-fixed flex min-h-0 flex-1">
      <div className="flex min-w-0 flex-1 flex-col gap-3 overflow-y-auto">
        <div className="flex flex-wrap items-center gap-2">
          <WriteHold>
            <IconButton
              label={t(ASSET_KEYS.action.add)}
              onClick={() => ask({ kind: "element", assetId: null })}
            >
              <Icon name="plus" />
            </IconButton>
          </WriteHold>
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
        {added && (
          <Alert
            tone="success"
            icon={<Icon name="check" />}
            className="ledger-asset-added"
          >
            {t("desktop.ledger.assets.write.element_added")}
          </Alert>
        )}
        {!onElement && <div key={asked}>{form()}</div>}
        {body()}
        {loaded && (
          <div className="ledger-assets-filing flex flex-col gap-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm text-muted-foreground">
                {t("desktop.ledger.assets.handoff_year")}
              </span>
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
            </div>
            <FilingHandoffPanel
              port={port}
              reader={reader}
              locale={locale}
              year={year}
              assetKind={rows[0]?.asset_kind ?? null}
              names={names}
            />
          </div>
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
          <div className="flex min-h-0 flex-1 flex-col">
            {onElement && request.assetId === row.asset_id && (
              <div
                key={asked}
                className="ledger-assets-form-slot max-h-[70%] shrink-0 overflow-y-auto border-b p-3 [&_form_.grid]:grid-cols-1"
              >
                {form()}
              </div>
            )}
            <AssetDetail
              port={port}
              reader={reader}
              locale={locale}
              row={row}
              year={year}
              version={version}
              onOpenLink={onOpenLink}
              onAct={(kind) => ask({ kind, assetId: row.asset_id })}
              onCorrectClaim={(claimId, claimYear) =>
                ask({
                  kind: "claim",
                  assetId: row.asset_id,
                  supersedes: claimId,
                  year: claimYear,
                })
              }
              onClose={() => select(null)}
            />
          </div>
        </RightPanel>
      )}
    </div>
  );
}
