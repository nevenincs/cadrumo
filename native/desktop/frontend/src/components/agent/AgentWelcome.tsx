import { useStrings } from "../../shell/strings";

/** What a conversation with nothing in it yet shows above the composer. */
export function AgentWelcome() {
  const t = useStrings();
  return (
    <div className="flex min-h-0 flex-1 flex-col justify-end gap-2 px-4 pb-4 text-balance">
      <h2 className="font-serif text-lg text-foreground">
        {t("desktop.agent.welcome_title")}
      </h2>
      <p className="text-base text-muted-foreground">
        {t("desktop.agent.welcome_lead")}
      </p>
    </div>
  );
}
