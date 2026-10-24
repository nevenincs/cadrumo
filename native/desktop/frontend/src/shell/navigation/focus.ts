// Focus after a navigation: each element that can take the keyboard
// registers its focus target under its register id, and the navigator asks
// for an element once its navigation applies. The wish is granted when the
// element signals that it is mounted and laid out: on its registration, or
// on a commit of the window after the layout change. Never after a delay.

/** The element itself, once mounted; null while it is not. */
export type FocusTarget = () => HTMLElement | null;

export class FocusRegister {
  private readonly targets = new Map<string, FocusTarget[]>();
  private wish: {
    readonly ids: readonly string[];
    readonly since: number;
  } | null = null;

  /** Adds `target` under `id`. The latest registration under an id is
   * asked first; the returned function removes exactly this one. A
   * registration is a mount signal, so a waiting wish may be granted. */
  register(id: string, target: FocusTarget): () => void {
    const list = this.targets.get(id) ?? [];
    list.push(target);
    this.targets.set(id, list);
    this.flush();
    return () => {
      const current = this.targets.get(id);
      if (!current) return;
      const index = current.lastIndexOf(target);
      if (index >= 0) current.splice(index, 1);
      if (current.length === 0) this.targets.delete(id);
    };
  }

  /** Asks for the first of `ids` (the element, then its ancestors) whose
   * target is laid out. The window flushes on its next commit. */
  request(ids: readonly string[], since: number): void {
    this.wish = ids.length > 0 ? { ids, since } : null;
  }

  /** Drops a wish older than the person's own input at `at`. */
  dropBefore(at: number): void {
    if (this.wish && this.wish.since < at) this.wish = null;
  }

  /** Whether a wish waits for its element. */
  get waiting(): boolean {
    return this.wish !== null;
  }

  /** Grants the wish if its element, or the nearest ancestor that has one,
   * has a target that is mounted and laid out. */
  flush(): boolean {
    const wish = this.wish;
    if (!wish) return false;
    for (const id of wish.ids) {
      for (const target of [...(this.targets.get(id) ?? [])].reverse()) {
        const element = target();
        // Laid out means shown: a hidden pane's content has no offset parent.
        if (!element?.isConnected || element.offsetParent === null) continue;
        this.wish = null;
        element.focus();
        return true;
      }
    }
    return false;
  }
}
