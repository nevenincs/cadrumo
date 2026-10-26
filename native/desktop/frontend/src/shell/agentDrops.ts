import { useEffect, useRef, useState } from "react";
import type { AgentDropSignal, AgentSession } from "./agentSession";

/** Routes native drags only to the visible conversation. The native host
 * supplies Shift on Windows because Explorer drags withhold DOM key events. */
export function useAgentDrops({
  session,
  enabled,
  reader,
  conversationId,
  onDrop,
}: {
  session: AgentSession | undefined;
  enabled: boolean;
  reader: string | null;
  conversationId: string | null;
  onDrop: (id: string) => void;
}) {
  const target = useRef<HTMLDivElement>(null);
  const receive = useRef(onDrop);
  receive.current = onDrop;
  const [drag, setDrag] = useState<{ count: number; armed: boolean } | null>(
    null,
  );
  useEffect(() => {
    setDrag(null);
    if (!enabled || !session?.observeDrops) return;
    let active = true;
    let shift = false;
    let stop: (() => void) | undefined;
    const key = (event: KeyboardEvent) => {
      shift = event.shiftKey;
      setDrag((held) => (held ? { ...held, armed: shift } : held));
    };
    const blur = () => {
      shift = false;
      setDrag(null);
    };
    window.addEventListener("keydown", key);
    window.addEventListener("keyup", key);
    window.addEventListener("blur", blur);
    const listener = (signal: AgentDropSignal) => {
      if (!active) return;
      if (signal.kind === "left") {
        setDrag(null);
        return;
      }
      const rect = target.current?.getBoundingClientRect();
      const inside =
        rect &&
        signal.x >= rect.left &&
        signal.x < rect.right &&
        signal.y >= rect.top &&
        signal.y < rect.bottom;
      const armed = signal.shift ?? shift;
      if (signal.kind === "over")
        setDrag(inside ? { count: signal.count, armed } : null);
      else {
        setDrag(null);
        if (inside && armed) receive.current(signal.drop_id);
      }
    };
    void session
      .observeDrops(listener)
      .then((cleanup) => {
        if (active) stop = cleanup;
        else cleanup();
      })
      .catch(() => {
        if (active) setDrag(null);
      });
    return () => {
      active = false;
      stop?.();
      window.removeEventListener("keydown", key);
      window.removeEventListener("keyup", key);
      window.removeEventListener("blur", blur);
    };
  }, [session, enabled, reader]);
  useEffect(() => {
    setDrag(null);
  }, [conversationId]);
  return { target, drag: enabled ? drag : null };
}
