import { Icon } from "@/components/ui/icon";

/** What the agent served of the conversation's newest reply beside its words:
 * a run state the transcript draws no indicator for, the messages queued behind
 * it, what the replies ran with and the tokens they used. Each is said only
 * where the agent served it. */
export function ReplyFacts({
  state,
  queued,
  ranWith,
  usage,
}: {
  state: string | null;
  queued: string | null;
  ranWith: string | null;
  usage: string | null;
}) {
  return (
    <>
      {[state, queued].map(
        (words) =>
          words && (
            <p
              key={words}
              role="status"
              className="agent-reply-state flex items-start gap-2 text-sm text-muted-foreground"
            >
              <Icon name="info" className="mt-0.5" />
              <span>{words}</span>
            </p>
          ),
      )}
      {[ranWith, usage].map(
        (words) =>
          words && (
            <p
              key={words}
              className="agent-reply-facts text-xs text-muted-foreground"
            >
              {words}
            </p>
          ),
      )}
    </>
  );
}
