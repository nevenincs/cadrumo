import { useEffect, useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useStrings } from "../../shell/strings";
import type { UserProfile } from "../../shell/userProfile";
import {
  censoRequirementKeys,
  type CensoPort,
  type CensoReadiness,
  type CensoSnapshot,
  type CensoDecision,
} from "../../shell/profileCenso";

export function CensoDialog({
  port,
  profile,
  open,
  onClose,
  onSetup,
  onIdentity,
  onRefresh,
}: {
  port: CensoPort | undefined;
  profile: UserProfile;
  open: boolean;
  onClose(): void;
  onSetup(): void;
  onIdentity(): void;
  onRefresh(): void;
}) {
  const t = useStrings();
  const [readiness, setReadiness] = useState<CensoReadiness | null>(null);
  const [snapshot, setSnapshot] = useState<CensoSnapshot | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [reload, setReload] = useState(0);
  const operation = snapshot?.operation;
  const state = snapshot?.state;
  useEffect(() => {
    if (!open || !port || operation) return;
    let live = true;
    void port
      .readiness(profile.profile_id)
      .then((value) => {
        if (live) {
          setReadiness(value);
          setError(false);
        }
      })
      .catch(() => {
        if (live) setError(true);
      });
    return () => {
      live = false;
    };
  }, [
    open,
    port,
    profile.profile_id,
    profile.record_revision,
    operation,
    reload,
  ]);
  useEffect(() => {
    if (
      !open ||
      !port ||
      !operation ||
      state === "done" ||
      state === "stopped" ||
      busy
    )
      return;
    let live = true,
      fetching = false,
      queued = false;
    let stop: (() => void) | undefined;
    let timer: ReturnType<typeof setTimeout>;
    const refresh = async () => {
      if (!live) return;
      if (fetching) {
        queued = true;
        return;
      }
      fetching = true;
      clearTimeout(timer);
      try {
        const value = await port.status(profile.profile_id, operation);
        if (live) {
          setSnapshot(value);
          setError(false);
          setUncertain(false);
        }
      } catch {
        if (live) setError(true);
      } finally {
        fetching = false;
      }
      if (live) {
        const delay = queued ? 0 : 30000;
        queued = false;
        // Runtime pushes drive updates; this is a recovery check for lost cues.
        timer = setTimeout(() => {
          void refresh();
        }, delay);
      }
    };
    timer = setTimeout(() => {
      void refresh();
    }, 0);
    if (port.observe)
      void port
        .observe(() => {
          void refresh();
        })
        .then((unsubscribe) => {
          if (!live) unsubscribe();
          else {
            stop = unsubscribe;
            void refresh();
          }
        })
        .catch(() => {
          if (live) setError(true);
        });
    return () => {
      live = false;
      clearTimeout(timer);
      stop?.();
    };
  }, [open, port, profile.profile_id, operation, state, busy, reload]);
  const run = async (decision?: CensoDecision) => {
    if (!port || busy) return;
    setBusy(true);
    setError(false);
    try {
      const value =
        decision && snapshot
          ? await port.answer(
              profile.profile_id,
              snapshot.operation,
              snapshot.review_digest,
              decision,
            )
          : await port.start(profile.profile_id);
      setSnapshot(value);
    } catch (failure) {
      setError(true);
      if (
        typeof failure !== "object" ||
        !failure ||
        !("code" in failure) ||
        !["refused", "conflict", "not_signed_in"].includes(String(failure.code))
      )
        setUncertain(true);
    } finally {
      setBusy(false);
    }
  };
  const missing =
    readiness?.requirements.filter((item) => !item.satisfied) ?? [];
  const needsIdentity = missing.some(
    (item) => item.field === "identity.tax_id",
  );
  const finished = state === "done" || state === "stopped";
  const labels = new Map(
    profile.sections.flatMap((section) =>
      section.fields.map((field) => [field.path, field.label]),
    ),
  );
  const close = () => {
    if (snapshot) onRefresh();
    if (finished) {
      setSnapshot(null);
      setReadiness(null);
    }
    onClose();
  };
  return (
    <Dialog
      open={open}
      onOpenChange={(value) => {
        if (!value) close();
      }}
    >
      <DialogContent closeLabel={t("desktop.profile.censo.close")}>
        <DialogHeader>
          <DialogTitle>{t("desktop.profile.censo.title")}</DialogTitle>
          <DialogDescription>
            {t("desktop.profile.censo.scope")}
          </DialogDescription>
        </DialogHeader>
        {(!port || error) && (
          <Alert>
            {t(
              uncertain
                ? "desktop.profile.unknown"
                : "desktop.profile.censo.unavailable",
            )}
          </Alert>
        )}
        {!snapshot && port && !error && !readiness && <Spinner />}
        {!snapshot && readiness && (
          <>
            {!!missing.length && (
              <ul className="list-disc space-y-2 pl-5">
                {missing.map((item) => (
                  <li key={item.field}>
                    {t(
                      censoRequirementKeys[
                        item.reason as keyof typeof censoRequirementKeys
                      ] ?? "auth.sync.requirement.unavailable",
                    )}
                  </li>
                ))}
              </ul>
            )}
            {readiness.ready && <p>{t("desktop.profile.censo.ready")}</p>}
          </>
        )}
        {snapshot && (
          <>
            <p role="status">{t(`desktop.profile.censo.${snapshot.state}`)}</p>
            {snapshot.state === "review" && (
              <div className="space-y-4">
                {snapshot.fields.map((field) => (
                  <section key={field.path} className="rounded-md border p-3">
                    <h3 className="font-semibold">
                      {labels.get(field.path) ??
                        t("desktop.profile.censo.field")}
                    </h3>
                    <dl className="mt-2 grid grid-cols-2 gap-2 text-sm">
                      <dt className="text-muted-foreground">
                        {t("desktop.profile.censo.current")}
                      </dt>
                      <dd>{field.current ?? "—"}</dd>
                      <dt className="text-muted-foreground">
                        {t("desktop.profile.censo.incoming")}
                      </dt>
                      <dd>{field.incoming ?? "—"}</dd>
                    </dl>
                    <p className="mt-2 text-sm">
                      {t(
                        field.preserve
                          ? "desktop.profile.censo.preserve"
                          : field.incoming === null
                            ? "desktop.profile.censo.absent"
                            : "desktop.profile.censo.adopt",
                      )}
                    </p>
                  </section>
                ))}
              </div>
            )}
          </>
        )}
        <DialogFooter>
          {error && (
            <Button
              variant="outline"
              disabled={busy}
              onClick={() => {
                setReload((v) => v + 1);
              }}
            >
              {t("desktop.profile.refresh")}
            </Button>
          )}
          {!snapshot && readiness && !readiness.ready && (
            <>
              {needsIdentity && (
                <Button onClick={onIdentity}>
                  {t("desktop.profile.censo.identity")}
                </Button>
              )}
              <Button
                variant={needsIdentity ? "outline" : "primary"}
                onClick={onSetup}
              >
                {t("desktop.profile.censo.setup")}
              </Button>
            </>
          )}
          {!snapshot && readiness?.ready && (
            <Button disabled={busy || uncertain} onClick={() => void run()}>
              {busy && <Spinner />}
              {t("desktop.profile.censo.pull")}
            </Button>
          )}
          {snapshot?.state === "review" && (
            <>
              <Button
                variant="outline"
                disabled={busy || error || uncertain}
                onClick={() => void run("reject")}
              >
                {t("desktop.profile.censo.reject")}
              </Button>
              <Button
                disabled={busy || error || uncertain}
                onClick={() => void run("apply")}
              >
                {t("desktop.profile.censo.apply")}
              </Button>
            </>
          )}
          {snapshot?.can_cancel && snapshot.state !== "review" && (
            <Button
              variant="outline"
              disabled={busy}
              onClick={() => void run("cancel")}
            >
              {t("desktop.profile.censo.cancel")}
            </Button>
          )}
          <Button variant="outline" disabled={busy} onClick={close}>
            {t(
              finished
                ? "desktop.profile.censo.return"
                : "desktop.profile.censo.close",
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
