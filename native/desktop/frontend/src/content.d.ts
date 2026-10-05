declare module "virtual:desktop-content" {
  export const identity: {
    name: string;
    application_id: string;
    version: string;
  };
}

/** The documentation fixture's own port; null where no development server
 * runs it. */
declare module "virtual:docs-fixture" {
  export const port: number | null;
}
