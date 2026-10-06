declare module "virtual:desktop-content" {
  export const identity: {
    name: string;
    application_id: string;
    version: string;
  };
}

/** The chrome strings generated from the locale catalogues, by locale and
 * key. An output of the build directory in use. */
declare module "virtual:desktop-strings" {
  const catalogue: Record<string, Record<string, string>>;
  export default catalogue;
}

/** The palette generated from the documentation theme: the colour authority.
 * An output of the build directory in use. */
declare module "virtual:desktop-palette.css";

/** The documentation fixture's own port; null where no development server
 * runs it. */
declare module "virtual:docs-fixture" {
  export const port: number | null;
}
