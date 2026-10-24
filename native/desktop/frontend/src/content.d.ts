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

/** Provider marks and their required upstream attribution, generated from the
 * checksummed agent wheel admitted by this build. */
declare module "virtual:desktop-provider-icons" {
  const artwork: {
    providers: Record<string, { mono: string; color?: string }>;
    attribution: {
      title: string;
      url: string;
      pin: string;
      licence: string;
      notice: string;
      trademarks: string;
    };
  };
  export default artwork;
}

/** The navigation register as the desktop reads it, generated from
 * `src/cadrumo_client/contracts/navigation.toml` through its validating
 * loader. An output of the build directory in use. */
declare module "virtual:desktop-navigation" {
  const register: import("./shell/navigation/register").NavigationRegister;
  export default register;
}

/** The documentation fixture's own port; null where no development server
 * runs it. */
declare module "virtual:docs-fixture" {
  export const port: number | null;
}
