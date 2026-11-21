import { useEffect, useId, useState } from "react";
import { PercentEditor } from "@/components/editors/PercentEditor";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Icon } from "@/components/ui/icon";
import { Spinner } from "@/components/ui/spinner";
import {
  proposalOf,
  useBackgroundTasks,
  type BackgroundTasks,
} from "../../../shell/backgroundTasks";
import type {
  LedgerClassifyJobAcceptedProposal,
  LedgerClassifyJobApplyItemResult,
  LedgerClassifyJobLaneProjection,
  LedgerClassifyJobProjection,
  LedgerClassifyJobProposalProjection,
} from "../../../shell/ledgerClassificationJobContract";
import { takesBusinessShare } from "../../../shell/ledgerClassifications";
import { parseFractionPercent } from "../../../shell/ledgerGrammar";
import type { LedgerTransactionReviewProjection } from "../../../shell/ledgerReadContract";
import { useStrings } from "../../../shell/strings";
import { formatPercent, heldDecimal } from "../../../shared/numbers";
import { APPLY_REFUSAL_WORDS } from "../../shell/backgroundTaskWords";
import { NoticeLine } from "../../shell/BackgroundTasks";
import { fieldName, refusalText, valueText } from "../editing/editingWords";
import { useWritePause, WriteHold } from "../WritePause";

// A background job's proposal for a movement, as the person reviews it: what
// the model proposed and which lane read it, accepted through the job's apply
// at the revision the person saw, or set aside for the manual editors. Nothing
// is applied that the person did not accept here.

/** What a job's model proposed for one movement, and who read it. */
function ProposalFacts({
  proposal,
  lane,
  locale,
}: {
  proposal: LedgerClassifyJobProposalProjection;
  lane: LedgerClassifyJobLaneProjection;
  locale: string;
}) {
  const t = useStrings();
  const rows = (
    [
      ["business_classification", proposal.classification],
      ["category_id", proposal.category],
      ["iva_category", proposal.iva_category],
      ...(proposal.business_pct !== null
        ? [["business_pct", proposal.business_pct] as const]
        : []),
    ] as const
  ).map(([field, value]) => (
    <div key={field} className="contents">
      <dt className="text-muted-foreground">{fieldName(t, field)}</dt>
      <dd data-proposed={field}>{valueText(t, locale, field, value)}</dd>
    </div>
  ));
  return (
    <>
      <p className="flex flex-wrap items-center gap-x-2 text-sm">
        <Icon name="agent" size="xs" />
        <span className="font-medium">
          {t("desktop.background_tasks.proposal.title")}
        </span>
        <span className="text-muted-foreground tabular-nums">
          {t("desktop.ledger.inspector.model.confidence", {
            value: formatPercent(locale, proposal.confidence, {
              unit: "fraction",
            }),
          })}
        </span>
      </p>
      <span className="text-xs text-muted-foreground" data-lane>
        {lane.reads_off_host
          ? t("desktop.background_tasks.off_host", { model: lane.model })
          : t("desktop.background_tasks.proposal.read_by", {
              model: lane.model,
            })}
      </span>
      <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-0.5 text-sm">
        {rows}
      </dl>
    </>
  );
}

/** What became of one accepted proposal: applied, or not with its cause. */
function ApplyResultLine({
  result,
}: {
  result: LedgerClassifyJobApplyItemResult;
}) {
  const t = useStrings();
  return (
    <span
      role="status"
      data-apply-result={result.outcome}
      data-apply-refusal={result.refusal ?? undefined}
      className={
        result.outcome === "refused"
          ? "text-sm text-warning"
          : "text-sm text-muted-foreground"
      }
    >
      {result.outcome === "applied"
        ? t("desktop.background_tasks.proposal.item_applied")
        : t("desktop.background_tasks.proposal.item_refused", {
            cause: result.refusal
              ? t(APPLY_REFUSAL_WORDS[result.refusal])
              : t("desktop.background_tasks.refused"),
          })}
    </span>
  );
}

/** What the last apply on `job` came to as a whole, where it was refused,
 * did not answer, or applied some of what was accepted. */
function JobApplyNotice({
  tasks,
  job,
}: {
  tasks: BackgroundTasks;
  job: string | null;
}) {
  const notice = job === null ? null : (tasks.notices.get(job) ?? null);
  if (
    notice === null ||
    (notice.kind !== "applied" &&
      notice.kind !== "refused" &&
      notice.kind !== "failed")
  )
    return null;
  return <NoticeLine notice={notice} />;
}

/**
 * The proposal a background job holds for one movement, in its inspector:
 * accepted with the share the person may edit first, or discarded, which
 * leaves the manual editors as the way to classify it.
 */
export function MovementJobProposal({
  row,
  locked,
  locale,
  say,
}: {
  row: LedgerTransactionReviewProjection;
  /** Why the movement takes no change now, or null where it does. */
  locked: string | null;
  locale: string;
  say: (text: string) => void;
}) {
  const t = useStrings();
  const tasks = useBackgroundTasks();
  const shareId = useId();
  const { held: paused } = useWritePause();
  const id = row.transaction.transaction_id;
  const found = proposalOf(tasks.jobs, tasks.rows, id);
  const result = tasks.applied.get(id) ?? null;
  const proposal = found?.item.proposal ?? null;
  // The proposal set aside, by the job and the revision it was made on.
  const shownKey = found
    ? `${found.job.job_id}:${proposal!.movement_revision_id}`
    : null;
  const [discarded, setDiscarded] = useState<string | null>(null);
  const [accepted, setAccepted] = useState<string | null>(null);
  const [share, setShare] = useState("");
  const [shareError, setShareError] = useState<string | null>(null);
  const proposedShare = proposal?.business_pct ?? null;
  useEffect(() => {
    setShare(proposedShare ? heldDecimal(proposedShare) : "");
    setShareError(null);
  }, [shownKey, proposedShare]);
  if (!found && !result) return null;
  const takesShare =
    proposal !== null &&
    (proposal.business_pct !== null ||
      takesBusinessShare(proposal.classification) === true);
  const busy = found ? tasks.busy.has(found.job.job_id) : false;

  const accept = () => {
    if (!found || paused !== null) return;
    const entry: LedgerClassifyJobAcceptedProposal = {
      movement_id: id,
      movement_revision_id: found.item.proposal.movement_revision_id,
    };
    if (takesShare) {
      const parsed = parseFractionPercent(share);
      if (parsed.kind === "refused") {
        setShareError(refusalText(t, parsed.refusal));
        return;
      }
      if (parsed.kind === "value") entry.business_pct = parsed.value;
    }
    setAccepted(found.job.job_id);
    tasks.apply(found.job, [entry]);
  };

  return (
    <div className="ledger-job-proposal grid gap-2" data-movement={id}>
      {found && shownKey !== discarded && (
        <div className="grid gap-2 rounded-md bg-accent p-2.5">
          <ProposalFacts
            proposal={found.item.proposal}
            lane={found.job.lane}
            locale={locale}
          />
          {takesShare && (
            <div className="grid gap-1">
              <label htmlFor={shareId} className="text-sm">
                {t("desktop.ledger.inspector.share")}
              </label>
              <div className="w-24">
                <PercentEditor
                  unit="fraction"
                  id={shareId}
                  controlSize="sm"
                  value={share}
                  invalid={shareError !== null}
                  describedBy={shareError ? `${shareId}-error` : undefined}
                  onChange={(next) => {
                    setShare(next);
                    setShareError(null);
                  }}
                />
              </div>
              {shareError && (
                <span id={`${shareId}-error`} className="text-sm">
                  {shareError}
                </span>
              )}
            </div>
          )}
          <span className="flex flex-wrap items-center gap-2">
            {busy && <Spinner className="size-icon-xs" />}
            <WriteHold>
              <Button
                size="sm"
                data-proposal-action="accept"
                disabled={locked !== null || busy}
                aria-description={locked ?? undefined}
                onClick={accept}
              >
                {t("desktop.background_tasks.proposal.accept")}
              </Button>
            </WriteHold>
            <Button
              variant="ghost"
              size="sm"
              data-proposal-action="discard"
              disabled={busy}
              onClick={() => {
                setDiscarded(shownKey);
                say(t("desktop.background_tasks.proposal.discarded"));
              }}
            >
              {t("desktop.background_tasks.proposal.discard")}
            </Button>
          </span>
        </div>
      )}
      {found && shownKey === discarded && (
        <p className="text-sm text-muted-foreground" data-proposal-discarded>
          {t("desktop.background_tasks.proposal.discarded")}
        </p>
      )}
      {result && <ApplyResultLine result={result} />}
      <JobApplyNotice tasks={tasks} job={accepted} />
    </div>
  );
}

/**
 * The proposals background jobs hold for the selected movements, each
 * marked by the person to be applied, and applied together: one apply for
 * each job they came from.
 */
export function SelectionJobProposals({
  ids,
  rows,
  locale,
  onShow,
}: {
  ids: readonly string[];
  rows: ReadonlyMap<string, LedgerTransactionReviewProjection>;
  locale: string;
  onShow: (id: string) => void;
}) {
  const t = useStrings();
  const tasks = useBackgroundTasks();
  const { held: paused } = useWritePause();
  const [marked, setMarked] = useState<ReadonlySet<string>>(() => new Set());
  const [appliedFrom, setAppliedFrom] = useState<readonly string[]>([]);
  const proposals = ids.flatMap((id) => {
    const found = proposalOf(tasks.jobs, tasks.rows, id);
    return found ? [{ id, ...found }] : [];
  });
  const results = ids.flatMap((id) => {
    const result = tasks.applied.get(id);
    return result && !proposals.some((entry) => entry.id === id)
      ? [{ id, result }]
      : [];
  });
  if (proposals.length === 0 && results.length === 0) return null;
  const chosen = proposals.filter((entry) => marked.has(entry.id));
  const busy = proposals.some((entry) => tasks.busy.has(entry.job.job_id));

  const applyMarked = () => {
    if (paused !== null || chosen.length === 0) return;
    const byJob = new Map<
      string,
      {
        job: LedgerClassifyJobProjection;
        accepted: LedgerClassifyJobAcceptedProposal[];
      }
    >();
    for (const entry of chosen) {
      const held = byJob.get(entry.job.job_id) ?? {
        job: entry.job,
        accepted: [],
      };
      const accepted: LedgerClassifyJobAcceptedProposal = {
        movement_id: entry.id,
        movement_revision_id: entry.item.proposal.movement_revision_id,
      };
      if (entry.item.proposal.business_pct !== null)
        accepted.business_pct = entry.item.proposal.business_pct;
      held.accepted.push(accepted);
      byJob.set(entry.job.job_id, held);
    }
    setAppliedFrom([...byJob.keys()]);
    setMarked(new Set());
    for (const { job, accepted } of byJob.values()) tasks.apply(job, accepted);
  };

  const describe = (id: string) =>
    rows.get(id)?.transaction.description ?? id.slice(0, 12);

  return (
    <div className="ledger-job-proposals grid gap-2">
      {proposals.length > 0 && (
        <p className="text-sm">
          {t("desktop.background_tasks.proposal.list", {
            count: proposals.length,
          })}
        </p>
      )}
      <ul className="grid gap-1.5">
        {proposals.map((entry) => {
          const box = `ledger-job-proposal-${entry.id}`;
          const result = tasks.applied.get(entry.id) ?? null;
          return (
            <li
              key={entry.id}
              data-movement={entry.id}
              className="grid gap-1 rounded-md bg-accent p-2 text-sm"
            >
              <span className="flex items-start gap-2">
                <Checkbox
                  id={box}
                  className="mt-0.5"
                  checked={marked.has(entry.id)}
                  disabled={busy}
                  onChange={(event) => {
                    const next = new Set(marked);
                    if (event.target.checked) next.add(entry.id);
                    else next.delete(entry.id);
                    setMarked(next);
                  }}
                />
                <label htmlFor={box} className="font-medium break-words">
                  {describe(entry.id)}
                </label>
              </span>
              <ProposalFacts
                proposal={entry.item.proposal}
                lane={entry.job.lane}
                locale={locale}
              />
              {result && <ApplyResultLine result={result} />}
              <span>
                <Button
                  variant="ghost"
                  size="xs"
                  onClick={() => onShow(entry.id)}
                >
                  {t("desktop.ledger.inspector.show")}
                </Button>
              </span>
            </li>
          );
        })}
        {results.map(({ id, result }) => (
          <li
            key={id}
            data-movement={id}
            className="grid gap-1 rounded-md p-2 text-sm"
          >
            <span className="font-medium break-words">{describe(id)}</span>
            <ApplyResultLine result={result} />
          </li>
        ))}
      </ul>
      {proposals.length > 0 && (
        <span className="flex flex-wrap items-center gap-2">
          {busy && <Spinner className="size-icon-xs" />}
          <WriteHold>
            <Button
              size="sm"
              className="w-fit"
              data-proposal-action="apply_marked"
              disabled={busy || chosen.length === 0}
              onClick={applyMarked}
            >
              {t("desktop.background_tasks.proposal.apply_marked")}
            </Button>
          </WriteHold>
        </span>
      )}
      {appliedFrom.map((job) => (
        <JobApplyNotice key={job} tasks={tasks} job={job} />
      ))}
    </div>
  );
}
