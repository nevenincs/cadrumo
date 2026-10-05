declare module "virtual:desktop-content" {
  export const identity: {
    name: string;
    application_id: string;
    version: string;
  };
}

/** Development server only: the documentation fixture's own port. */
declare module "virtual:docs-fixture" {
  export const port: number;
}
