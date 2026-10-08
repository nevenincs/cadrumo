import { useStrings } from "../shell/strings";

/** A non-interactive placeholder; readiness still comes from the desktop host. */
export function AccountLoading({
  starting = false,
  quiet = false,
}: {
  starting?: boolean;
  quiet?: boolean;
}) {
  const t = useStrings();
  return (
    <div
      data-slot="account-loading"
      aria-busy="true"
      className="flex flex-1 flex-col items-center justify-center gap-5 p-6"
    >
      <p
        role={quiet ? undefined : "status"}
        className="text-sm text-muted-foreground"
      >
        {t(
          starting
            ? "desktop.signin.starting_services"
            : "desktop.signin.checking",
        )}
      </p>
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
    </div>
  );
}
