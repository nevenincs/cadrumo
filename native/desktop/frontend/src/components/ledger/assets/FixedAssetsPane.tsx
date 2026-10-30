import { useEffect, useState, type ReactNode } from "react";
import { Alert } from "@/components/ui/alert";
import { EmptyState } from "@/components/ui/empty";
import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import type { LedgerPort } from "../../../shell/ledger";
import { useStrings } from "../../../shell/strings";
import { RightPanel } from "../inspector/RightPanel";
import { callFailure, callOutcome, type SetupCall } from "../setup/setupModel";
import { CallLine, Reading } from "../setup/SetupParts";
import { useWritePause, WriteHold } from "../WritePause";
import { AssetDetail, type AssetView } from "./AssetDetail";
import { AssetList, CountPill, callRefusal, refusalText } from "./AssetList";
import {
  submitProvisional,
  type FormKind,
  type ProvisionalResults,
} from "./assetsContract";
import { ASSET_KEYS, COUNT_KINDS } from "./assetsWords";
import { FilingHandoffPanel } from "./FilingHandoffPanel";
import { YearStepper } from "./YearStepper";

/** An act asked for: a new element, or one on an element already listed. */
export type AssetFormRequest = { kind: FormKind; assetId: string | null };

/** What a form is given to write, and how it says it is done. */
export type AssetFormArgs = {
  port: LedgerPort;
  locale: string;
  year: number | null;
  request: AssetFormRequest;
  onClose: () => void;
  /** The form wrote: the list is read again. */
  onWritten: () => void;
};

/** The parts of the pane that other parts draw. Without them the pane
 * offers no act and its detail tabs stay empty. */
export type AssetSlots = {
  planView?: AssetView;
  timelineView?: AssetView;
  forms?: (args: AssetFormArgs) => ReactNode;
};

type ListResult = ProvisionalResults["ledger.actividad-asset.list"];

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
      let answer: SetupCall<ListResult>;
      try {
        answer = callOutcome(
          await submitProvisional(port, "ledger.actividad-asset.list", {}),
          false,
        );
      } catch (error) {
        answer = callFailure(error);
      }
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
 */
export function FixedAssetsPane({
  port,
  reader,
  locale,
  slots = {},
}: {
  port: LedgerPort;
  /** Whose ledger; null while the account withholds it. */
  reader: string | null;
  locale: string;
  slots?: AssetSlots;
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
  const years = loaded?.years ?? [];
  const year = chosenYear ?? (years.length > 0 ? Math.max(...years) : null);
  const row = rows.find((found) => found.asset_id === selected) ?? null;
  const { forms, planView, timelineView } = slots;

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
    if (answer?.outcome === "refused")
      return (
        <Alert
          tone="danger"
          role="alert"
          icon={<Icon name="refused" />}
          className="ledger-assets-refused"
        >
          {refusalText(t, answer.refusal)}
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
          {forms && (
            <WriteHold>
              <IconButton
                label={t(ASSET_KEYS.action.add)}
                onClick={() => setRequest({ kind: "element", assetId: null })}
              >
                <Icon name="plus" />
              </IconButton>
            </WriteHold>
          )}
          <YearStepper value={year} years={years} onChange={setYear} />
          <span className="flex-1" />
          <span
            role="group"
            aria-label={t("desktop.ledger.assets.list.summary")}
            className="flex flex-wrap items-center gap-1"
          >
            {COUNT_KINDS.map((kind) => {
              const count = rows.reduce(
                (sum, found) => sum + found.counts[kind],
                0,
              );
              return count > 0 ? (
                <CountPill key={kind} kind={kind} count={count} />
              ) : null;
            })}
          </span>
        </div>
        {forms &&
          request &&
          forms({
            port,
            locale,
            year,
            request,
            onClose: () => setRequest(null),
            onWritten: reload,
          })}
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
        >
          <AssetDetail
            port={port}
            locale={locale}
            row={row}
            year={year}
            version={version}
            {...(planView ? { planView } : {})}
            {...(timelineView ? { timelineView } : {})}
            {...(forms
              ? {
                  onAct: (kind: FormKind) =>
                    setRequest({ kind, assetId: row.asset_id }),
                }
              : {})}
            onClose={() => setSelected(null)}
          />
        </RightPanel>
      )}
    </div>
  );
}
