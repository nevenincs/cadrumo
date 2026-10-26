import { EmptyState } from "@/components/ui/empty";
import { useStrings } from "../shell/strings";

/** A non-interactive placeholder; readiness still comes from the desktop host. */
export function AccountLoading({
  starting = false,
  quiet = false,
  recovering = false,
}: {
  starting?: boolean;
  quiet?: boolean;
  recovering?: boolean;
}) {
  const t = useStrings();
  return (
    <EmptyState
      data-slot="account-loading"
      aria-busy="true"
      role={quiet ? undefined : "status"}
      description={t(
        recovering
          ? "desktop.signin.recovering_services"
          : starting
            ? "desktop.signin.starting_services"
            : "desktop.signin.checking",
      )}
    >
      <div
        aria-hidden="true"
        className="grid w-full max-w-80 gap-4 motion-safe:animate-pulse"
      >
        <div className="h-5 w-2/3 rounded bg-muted" />
        <div className="h-10 rounded bg-muted" />
        <div className="h-5 w-1/3 rounded bg-muted" />
        <div className="h-10 rounded bg-muted" />
        <div className="mt-2 h-10 rounded bg-muted" />
      </div>
    </EmptyState>
  );
}
