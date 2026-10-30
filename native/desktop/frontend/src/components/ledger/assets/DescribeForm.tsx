import { AssetForm, type ActProps } from "./AssetForm";

/**
 * The element's descriptive record: its name, serial number and register book
 * entry. Saving appends a description to its history; no revision is made and
 * no claim goes stale, so the line under the form says only that a
 * description was added.
 */
export function DescribeForm(props: ActProps & { assetId: string }) {
  return <AssetForm {...props} kind="descriptor" />;
}
