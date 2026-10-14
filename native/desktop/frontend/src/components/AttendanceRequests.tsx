import { useEffect, useState } from "react";
import type { Attendance, AttendanceCandidate } from "../shell/host";
import { failureCode } from "../errors";
import { useStrings } from "../shell/strings";
import { ApprovalPrompt } from "./agent/ApprovalPrompt";

/** Exact runtime peer requests; passive polling never extends person activity. */
export function AttendanceRequests({
  attendance,
  profile,
}: {
  attendance?: Attendance;
  profile: string | null;
}) {
  const t = useStrings();
  const [state, setState] = useState<{
    profile: string | null;
    candidates: AttendanceCandidate[];
    failure: string | null;
    busy: string | null;
  }>({ profile: null, candidates: [], failure: null, busy: null });
  const candidates = state.profile === profile ? state.candidates : [];
  useEffect(() => {
    if (!attendance || !profile) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const reply = await attendance.inventory();
        if (active)
          setState((previous) => ({
            ...previous,
            profile,
            candidates: reply.candidates,
            failure: null,
          }));
      } catch {
        if (active)
          setState((previous) => ({ ...previous, profile, candidates: [] }));
      }
      if (active) timer = setTimeout(() => void poll(), 2000);
    };
    void poll();
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [attendance, profile]);
  const decide = async (candidate: AttendanceCandidate, approve: boolean) => {
    if (!attendance || state.busy) return;
    setState((previous) => ({
      ...previous,
      busy: candidate.attendance_id,
      failure: null,
    }));
    try {
      await attendance.decide(candidate.attendance_id, approve);
      setState((previous) => ({
        ...previous,
        candidates: previous.candidates.filter(
          (row) => row.attendance_id !== candidate.attendance_id,
        ),
      }));
    } catch (error) {
      setState((previous) => ({ ...previous, failure: failureCode(error) }));
    } finally {
      setState((previous) => ({ ...previous, busy: null }));
    }
  };
  if (!candidates.length) return null;
  const words = (items: unknown[]) =>
    items.length
      ? items
          .map((item) =>
            typeof item === "string" ? item : JSON.stringify(item),
          )
          .join(", ")
      : t("desktop.attendance.none");
  return (
    <aside
      className="fixed right-4 bottom-4 z-(--layer-toast) grid max-h-[calc(100%-var(--overlay-gutter))] w-dialog max-w-[calc(100%-var(--overlay-gutter))] gap-3 overflow-y-auto"
      aria-label={t("desktop.attendance.title")}
    >
      {candidates
        .filter((row) => Date.parse(row.expires_at) > Date.now())
        .map((candidate) => {
          const scope = candidate.scope;
          const description = [
            `${t("desktop.attendance.process")}: ${candidate.process_id ?? t("desktop.attendance.none")}`,
            `${t("desktop.attendance.executable")}: ${candidate.image_path ?? t("desktop.attendance.none")}`,
            `${t("desktop.attendance.expires")}: ${candidate.expires_at}`,
            `${t("desktop.attendance.operations")}: ${words(scope.operations)}`,
            `${t("desktop.attendance.actions")}: ${words(scope.actions)}`,
            `${t("desktop.attendance.periods")}: ${scope.periods === null ? t("desktop.attendance.all_periods") : words(scope.periods)}`,
            ...(
              [
                "network",
                "changes",
                "delegation",
                "period_independent",
              ] as const
            ).map((label) => {
              const field = {
                network: scope.allow_network,
                changes: scope.allow_changes_records,
                delegation: scope.allow_delegation,
                period_independent: scope.allow_period_independent,
              }[label];
              return `${t(`desktop.attendance.${label}`)}: ${t(field ? "desktop.attendance.yes" : "desktop.attendance.no")}`;
            }),
            `${t("desktop.attendance.disclosures")}: ${words([...scope.disclosures, ...scope.disclosure_categories])}`,
          ].join("\n");
          return (
            <ApprovalPrompt
              key={`${profile}:${candidate.attendance_id}`}
              source="cadrumo_review"
              title={t("desktop.attendance.title")}
              description={description}
              options={[
                { option_id: "reject", kind: "reject_once", name: "" },
                { option_id: "approve", kind: "allow_once", name: "" },
              ]}
              onDecide={
                state.busy
                  ? undefined
                  : (option) => void decide(candidate, option === "approve")
              }
            />
          );
        })}
      {state.failure && (
        <p role="alert">
          {t("desktop.attendance.failed", { code: state.failure })}
        </p>
      )}
    </aside>
  );
}
