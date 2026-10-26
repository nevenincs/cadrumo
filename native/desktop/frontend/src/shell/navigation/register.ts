// The navigation register as the window reads it: the generated projection
// of `src/cadrumo_client/contracts/navigation.toml`. Everything here is pure
// and takes the register as an argument, so the same functions run in the
// window and against the projection read from disk in a test.

/** An interface that can open a register element. */
export type Surface = "gui" | "tui";

/** A kind of link parameter value: opaque record ids of an exact shape. */
export type ValueKind = {
  readonly name: string;
  readonly alphabet: string;
  readonly length: number;
};

/** One navigable element, as the register declares it. */
export type NavigationElement = {
  readonly id: string;
  readonly parent: string | null;
  /** The locale key every palette shows. */
  readonly label: string;
  readonly keywords: string;
  readonly surfaces: readonly Surface[];
  /** Parameter name to value kind name. */
  readonly params: Readonly<Record<string, string>>;
};

/** The whole projection: the link grammar's limits, value kinds, retired
 * ids and the elements in declaration order. */
export type NavigationRegister = {
  readonly schema: number;
  readonly link: {
    readonly prefix: string;
    readonly max_length: number;
    readonly max_segments: number;
    readonly prefer_key: string;
  };
  readonly surfaces: readonly Surface[];
  readonly kinds: readonly ValueKind[];
  readonly retired: readonly string[];
  readonly elements: readonly NavigationElement[];
};

/** Link parameters by name. */
export type ViewParams = Readonly<Record<string, string>>;

/** The element `id` names, or undefined when it names none. */
export function elementOf(
  register: NavigationRegister,
  id: string,
): NavigationElement | undefined {
  return register.elements.find((element) => element.id === id);
}

/** Every id whose element `surface` implements, by the register alone. */
export function idsFor(
  register: NavigationRegister,
  surface: Surface,
): ReadonlySet<string> {
  return new Set(
    register.elements
      .filter((element) => element.surfaces.includes(surface))
      .map((element) => element.id),
  );
}

/** The element and then its ancestors, nearest first. Empty for an id the
 * register does not declare. */
export function lineage(
  register: NavigationRegister,
  id: string,
): NavigationElement[] {
  const chain: NavigationElement[] = [];
  let current: string | null = id;
  while (current !== null) {
    const element = elementOf(register, current);
    if (!element) return [];
    chain.push(element);
    current = element.parent;
  }
  return chain;
}

/** Whether `value` has exactly the shape of the kind named `kind`. */
export function admitsValue(
  register: NavigationRegister,
  kind: string,
  value: string,
): boolean {
  const declared = register.kinds.find((each) => each.name === kind);
  return (
    declared !== undefined &&
    value.length === declared.length &&
    [...value].every((character) => declared.alphabet.includes(character))
  );
}

/** Whether a TUI may be asked to show `view` with `params`: a register view
 * whose surfaces include the TUI, with only parameters it declares, each a
 * value of its kind. The host admits a request by the same rule. */
export function admitsTuiView(
  register: NavigationRegister,
  view: string,
  params: ViewParams,
): boolean {
  const element = elementOf(register, view);
  return (
    element !== undefined &&
    element.surfaces.includes("tui") &&
    Object.entries(params).every(([name, value]) => {
      const kind = Object.hasOwn(element.params, name)
        ? element.params[name]
        : undefined;
      return kind !== undefined && admitsValue(register, kind, value);
    })
  );
}
