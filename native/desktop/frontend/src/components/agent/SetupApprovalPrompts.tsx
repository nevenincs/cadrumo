import { useSyncExternalStore } from "react";
import { Button } from "@/components/ui/button";
import { browserPlan, type SetupApprovals } from "../../shell/setupApprovals";
import { useStrings } from "../../shell/strings";
import { approveLabel, PlanDetail, PlanSummary } from "../setup/SetupDialog";
import { ApprovalPrompt } from "./ApprovalPrompt";

/**
 * Setup that waits on the person, beside the agent's other approvals: what
 * it would download, how much, from where and where it goes, and the choice
 * to approve or reject. Nothing that identifies the request is shown. A plan
 * Cadrumo cannot show can only be rejected.
 */
export function SetupApprovalPrompts({
  approvals,
  locale,
  onCheckSetup,
}: {
  approvals: SetupApprovals;
  locale: string;
  onCheckSetup: () => void;
}) {
  const t = useStrings();
  const state = useSyncExternalStore(
    approvals.subscribe,
    approvals.getSnapshot,
  );
  return (
    <>
      {state.reviews.map((review) => {
        const plan = browserPlan(
          review.document,
          t("desktop.setup_review.destination_browser"),
        );
        const options = [
          {
            option_id: "reject",
            kind: "reject_once" as const,
            name: t("desktop.setup_review.reject"),
          },
          ...(plan && plan.space_sufficient
            ? [
                {
                  option_id: "apply",
                  kind: "allow_once" as const,
                  name: approveLabel(t, plan, locale),
                },
              ]
            : []),
        ];
        return (
          <ApprovalPrompt
            key={review.operation_id}
            source="cadrumo_review"
            title={t("desktop.setup_review.title")}
            description={
              plan
                ? t("desktop.setup_review.lead")
                : t("desktop.setup_review.unreadable")
            }
            options={options}
            onDecide={
              state.busy
                ? undefined
                : (option) =>
                    void approvals.decide(
                      review,
                      option === "apply" ? "apply" : "reject",
                    )
            }
          >
            {plan && (
              <div className="grid gap-2" data-setup-approval>
                <PlanSummary review={plan} locale={locale} />
                <PlanDetail review={plan} locale={locale} />
              </div>
            )}
          </ApprovalPrompt>
        );
      })}
      {state.failure && (
        <p role="alert" className="text-sm">
          {state.failure === "changed"
            ? t("desktop.setup_review.changed")
            : state.failure === "held_elsewhere"
              ? t("desktop.setup_review.held_elsewhere")
              : t("desktop.setup_review.unavailable")}
        </p>
      )}
      {state.uncertain && (
        <div role="alert" className="grid gap-2 text-sm">
          <p>{t("desktop.setup_review.uncertain")}</p>
          <Button
            variant="outline"
            className="justify-self-start"
            onClick={onCheckSetup}
          >
            {t("desktop.setup_review.check_setup")}
          </Button>
        </div>
      )}
    </>
  );
}
