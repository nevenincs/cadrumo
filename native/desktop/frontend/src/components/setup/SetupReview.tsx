import { useId, useState, useSyncExternalStore } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  browserPlan,
  browserVersion,
  reviewFailureKey,
  type SetupReviewSession,
} from "../../shell/setupReview";
import { PlanSummary, PlanDetail } from "./SetupDialog";
import { useStrings } from "../../shell/strings";

/** A person supplies a known registered operation; reading it grants no authority. */
export function SetupReview({
  session,
  locale,
  onCheckStatus,
}: {
  session: SetupReviewSession;
  locale: string;
  onCheckStatus: () => void;
}) {
  const t = useStrings();
  const id = useId();
  const state = useSyncExternalStore(session.subscribe, session.getSnapshot);
  const [operationId, setOperationId] = useState(
    () => state.review?.operation_id ?? state.unknownOperationIds[0] ?? "",
  );
  const plan = state.review
    ? browserPlan(
        state.review.document,
        t("desktop.setup_review.destination_browser"),
      )
    : null;
  const version = state.review ? browserVersion(state.review.document) : null;
  return (
    <section className="grid min-w-0 gap-2" aria-labelledby={`${id}-title`}>
      <h3 id={`${id}-title`} className="text-sm font-medium">
        {t("desktop.setup_review.title")}
      </h3>
      <label htmlFor={id}>{t("desktop.setup_review.operation_id")}</label>
      <Input
        id={id}
        disabled={state.busy}
        value={operationId}
        onChange={(event) => {
          session.resetReview();
          setOperationId(event.target.value);
        }}
      />
      <Button
        variant="outline"
        disabled={state.busy || !/^[a-f0-9]{64}$/.test(operationId)}
        onClick={() => void session.read(operationId)}
      >
        {t("desktop.setup_review.read")}
      </Button>
      {state.review && (
        <>
          <p className="break-all text-xs">
            {t("desktop.setup_review.review_digest")}:{" "}
            {state.review.review_digest}
          </p>
          {state.review.expires_at && (
            <p className="text-xs">
              {t("desktop.setup_review.expires_at")}: {state.review.expires_at}
            </p>
          )}
          {plan ? (
            <>
              <PlanSummary review={plan} locale={locale} />
              <PlanDetail review={plan} locale={locale} />
              {version && (
                <p className="text-sm">
                  {t("desktop.setup_review.target_version", { version })}
                </p>
              )}
            </>
          ) : (
            <p role="alert">{t("desktop.setup_review.failed")}</p>
          )}
          {!state.claimed ? (
            <Button
              disabled={
                state.busy ||
                !plan ||
                state.unknownOperationIds.includes(state.review.operation_id)
              }
              onClick={() => void session.claim()}
            >
              {t("desktop.setup_review.claim")}
            </Button>
          ) : (
            <>
              <p role="status">{t("desktop.setup_review.claimed")}</p>
              <div className="flex gap-2">
                <Button
                  disabled={
                    state.busy ||
                    !plan ||
                    state.unknownOperationIds.includes(
                      state.review.operation_id,
                    )
                  }
                  onClick={() => void session.answer("apply")}
                >
                  {t("desktop.setup_review.apply")}
                </Button>
                <Button
                  variant="outline"
                  disabled={
                    state.busy ||
                    !plan ||
                    state.unknownOperationIds.includes(
                      state.review.operation_id,
                    )
                  }
                  onClick={() => void session.answer("reject")}
                >
                  {t("desktop.setup_review.reject")}
                </Button>
              </div>
            </>
          )}
        </>
      )}
      {state.unknownOperationIds.length > 0 && (
        <div role="alert" className="grid gap-2">
          {state.unknownOperationIds.map((operationId) => (
            <p key={operationId} className="break-words">
              {t("desktop.setup_review.answer_unknown", {
                operation_id: operationId,
              })}
            </p>
          ))}
          <Button variant="outline" onClick={onCheckStatus}>
            {t("desktop.setup.action.check_again")}
          </Button>
        </div>
      )}
      {state.failed && (
        <p role="alert">{t(reviewFailureKey(state.failureCode))}</p>
      )}
    </section>
  );
}
