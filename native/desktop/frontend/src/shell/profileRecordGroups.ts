// The window's reading of the profile's record groups as
// `user-profile.record-groups` serves them: one paged stream per group kind,
// in which each group's head row comes first, then every row that names it,
// then the ledger rows that name any of them. The wire types are generated in
// `profileContract.ts`; this module only assembles the pages of one stream
// into groups. The window joins nothing: a member sits under the row its
// `parent_ref` names, and no summary, relation or concept word is composed
// here.
//
// The host does not relay this read yet, so nothing reads it from the host;
// the record groups element is drawn over the dev fixture until it does.

import type {
  OutputLanguage,
  ProfileRecordGroupItem,
  ProfileRecordGroupKind,
  ProfileRecordGroupsProjection,
  ProfileRecordGroupsRequest,
  ProfileRecordGroupStreamItem,
  ProfileRecordLedgerRowItem,
  ProfileRecordMemberItem,
} from "./profileContract";

type PinField =
  "expected_revision" | "expected_content_digest" | "expected_ledger_digest";

/** The revision and digests a stream's first page was read at; every
 * continuation names them, and the read refuses one that moved. */
export type RecordGroupsPin = {
  [Field in PinField]-?: NonNullable<ProfileRecordGroupsRequest[Field]>;
};

/** One member row and how many rows lie between it and its group's head. */
export type RecordGroupMember = {
  item: ProfileRecordMemberItem;
  depth: number;
};

/** One group as read so far. */
export type RecordGroupBlock = {
  group: ProfileRecordGroupItem;
  members: RecordGroupMember[];
  ledgerRows: ProfileRecordLedgerRowItem[];
};

/** A kind's groups as read so far, and whether and where the read continues.
 * `refusal` holds the read's own words when it refused the last page. */
export type RecordGroupStream = {
  kind: ProfileRecordGroupKind;
  blocks: RecordGroupBlock[];
  pin: RecordGroupsPin | null;
  read: number;
  nextCursor: number | null;
  refusal: { words: string; language: OutputLanguage | null } | null;
};

export const emptyStream = (
  kind: ProfileRecordGroupKind,
): RecordGroupStream => ({
  kind,
  blocks: [],
  pin: null,
  read: 0,
  nextCursor: 0,
  refusal: null,
});

/** A page that does not continue the stream it was read for. */
export class MalformedRecordGroupPage extends Error {}

function memberDepth(block: RecordGroupBlock, parentRef: string): number {
  if (parentRef === block.group.group_key) return 1;
  const parent = block.members.find(
    (member) => member.item.row_ref === parentRef,
  );
  if (!parent)
    throw new MalformedRecordGroupPage("member before the row it names");
  return parent.depth + 1;
}

function placed(
  blocks: RecordGroupBlock[],
  item: ProfileRecordGroupStreamItem,
  kind: ProfileRecordGroupKind,
): RecordGroupBlock[] {
  if (item.kind === "group") {
    if (
      item.payload_kind !== kind ||
      blocks.some((block) => block.group.group_key === item.group_key)
    )
      throw new MalformedRecordGroupPage(
        "group served twice or of another kind",
      );
    return [...blocks, { group: item, members: [], ledgerRows: [] }];
  }
  // The read serves every item of a group straight after its head row.
  const last = blocks.at(-1);
  if (!last || last.group.group_key !== item.group_key)
    throw new MalformedRecordGroupPage("item served outside its group");
  if (item.kind === "member") {
    const member = { item, depth: memberDepth(last, item.parent_ref) };
    return [
      ...blocks.slice(0, -1),
      { ...last, members: [...last.members, member] },
    ];
  }
  if (
    item.ledger_row_index !== last.ledgerRows.length ||
    item.ledger_row_total !== last.group.ledger_row_count
  )
    throw new MalformedRecordGroupPage("ledger row out of place");
  return [
    ...blocks.slice(0, -1),
    { ...last, ledgerRows: [...last.ledgerRows, item] },
  ];
}

/** The stream with the next page taken, or with the read's refusal of it.
 * Throws {@link MalformedRecordGroupPage} for a page that does not continue
 * the pages read before it. */
export function acceptRecordGroupsPage(
  stream: RecordGroupStream,
  page: ProfileRecordGroupsProjection,
): RecordGroupStream {
  if (page.group_kind !== stream.kind)
    throw new MalformedRecordGroupPage("page of another kind");
  if (page.outcome === "refused")
    return {
      ...stream,
      nextCursor: null,
      refusal:
        page.refusal_words === null
          ? null
          : {
              words: page.refusal_words,
              language: page.refusal_words_language,
            },
    };
  const pin: RecordGroupsPin = {
    expected_revision: page.record_revision,
    expected_content_digest: page.content_digest,
    expected_ledger_digest: page.ledger_digest,
  };
  const moved =
    stream.pin !== null &&
    (stream.pin.expected_revision !== pin.expected_revision ||
      stream.pin.expected_content_digest !== pin.expected_content_digest ||
      stream.pin.expected_ledger_digest !== pin.expected_ledger_digest);
  if (moved || page.cursor !== stream.read)
    throw new MalformedRecordGroupPage("page does not continue the stream");
  return {
    ...stream,
    blocks: page.items.reduce(
      (blocks, item) => placed(blocks, item, stream.kind),
      stream.blocks,
    ),
    pin,
    read: page.cursor + page.items.length,
    nextCursor: page.next_cursor,
    refusal: null,
  };
}
