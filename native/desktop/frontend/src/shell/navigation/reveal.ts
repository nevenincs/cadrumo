// A navigation's parameters, handed to the element that honours them. The
// element registers what it does with them under its register id, and the
// navigator asks once the navigation applies. The ask is answered when the
// element signals that it is mounted: at once if it is, or on its
// registration. Never after a delay.

import type { ViewParams } from "./register";

/** What an element does with the parameters of a navigation to it. */
export type ViewParamsHandler = (params: ViewParams) => void;

export class RevealRegister {
  private readonly handlers = new Map<string, ViewParamsHandler[]>();
  private wish: { readonly id: string; readonly params: ViewParams } | null =
    null;

  /** Adds `handler` under `id`; the latest registration under an id is
   * handed the parameters. The returned function removes exactly this one.
   * A registration is a mount signal, so a waiting ask is answered. */
  register(id: string, handler: ViewParamsHandler): () => void {
    const list = this.handlers.get(id) ?? [];
    list.push(handler);
    this.handlers.set(id, list);
    this.flush();
    return () => {
      const current = this.handlers.get(id);
      if (!current) return;
      const index = current.lastIndexOf(handler);
      if (index >= 0) current.splice(index, 1);
      if (current.length === 0) this.handlers.delete(id);
    };
  }

  /** Hands `params` to element `id`. Every navigation asks, so one without
   * parameters drops an ask still waiting from the one before. */
  request(id: string, params: ViewParams): void {
    this.wish = Object.keys(params).length > 0 ? { id, params } : null;
    this.flush();
  }

  /** Whether parameters wait for their element. */
  get waiting(): boolean {
    return this.wish !== null;
  }

  private flush(): void {
    const wish = this.wish;
    if (!wish) return;
    const handler = this.handlers.get(wish.id)?.at(-1);
    if (!handler) return;
    this.wish = null;
    handler(wish.params);
  }
}
