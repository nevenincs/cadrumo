//! The household the profile states, assembled from the `family_rows` page
//! stream of `user-profile.view`: each group of people with the leaves its
//! rows can state and the rows stored, in the product's words. Only a
//! complete stream pinned to one profile revision is released, and an item
//! outside the three kinds the stream serves, an unknown member or a row that
//! does not belong to the group before it is refused. The host holds no
//! family rule: which leaves exist, which questions are asked now, their
//! words and their answer sets are the product's.
use super::wire::{Page, Pin};
use super::{Failure, PROFILE_READ_LIMIT, ProfileHost, Result, protocol};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::BTreeSet;

/// The page stream the household is read from.
const PAGE_KIND: &str = "family_rows";
/// What a masked fact shows in place of its value.
const MASK: &str = "••••••••";

/// What the profile says about one group of rows. `unknown` means nothing was
/// stated and no row is stored, `none_declared` that the profile states a
/// count of zero, and `incomplete` that it states more people than it records
/// (the recorded rows are still held); no two are the same state.
#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
enum GroupState {
    Rows,
    Incomplete,
    NoneDeclared,
    Unknown,
    NotServed,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct Choice {
    value: String,
    label: String,
}

/// One answer of another leaf of the same row that a leaf is asked under.
/// Exactly one of `equals` (the leaf's answer is the token) and `contains`
/// (the token is one of the comma-joined tokens of that answer) is stated; the
/// absent one is released as null.
#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct Condition {
    leaf: String,
    #[serde(default)]
    equals: Option<String>,
    #[serde(default)]
    contains: Option<String>,
}

/// One fact a row can state: its stored key, its words and its answer set.
/// The leaf is asked only where one of its `shown_when` conditions holds; none
/// means it is always asked.
#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct Leaf {
    leaf: String,
    label: String,
    help: Option<String>,
    field_type: String,
    required: bool,
    choices: Vec<Choice>,
    #[serde(default)]
    shown_when: Vec<Condition>,
}

/// A control that changes a group's rows: its words and the registered
/// operations it submits.
#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct RowAction {
    action_words: String,
    target_operation_ids: Vec<String>,
}

/// One stored fact of a row. A leaf the row does not state is absent from it,
/// never zero.
#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct Fact {
    leaf: String,
    path: String,
    value: String,
    masked: bool,
}

/// The answers a question can state. A question the profile states nothing
/// for carries none, which is neither of the two.
const STATED_ANSWERS: [&str; 2] = ["true", "false"];

#[derive(Debug, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
enum Item {
    #[serde(rename = "family_group")]
    Group {
        group_key: String,
        label: String,
        state: GroupState,
        stated_count: Option<String>,
        row_count: usize,
        incomplete_words: Option<String>,
        max_rows: Option<usize>,
        leaves: Vec<Leaf>,
        #[serde(default)]
        add_row_action: Option<RowAction>,
        #[serde(default)]
        remove_row_action: Option<RowAction>,
    },
    #[serde(rename = "family_row")]
    Row {
        group_key: String,
        row_index: String,
        facts: Vec<Fact>,
    },
    #[serde(rename = "family_question")]
    Question {
        question_id: String,
        path: String,
        prompt: String,
        help: Option<String>,
        saved_value: Option<String>,
        choices: Vec<Choice>,
    },
}

/// A household question the product asks of this profile now, with the answer
/// the profile states for it. A profile that states nothing has no
/// `saved_value`; the window draws that apart from a stated "no".
#[derive(Debug, Serialize)]
pub struct Question {
    question_id: String,
    path: String,
    prompt: String,
    help: Option<String>,
    saved_value: Option<String>,
    choices: Vec<Choice>,
}

#[derive(Debug, Serialize)]
pub struct Row {
    row_index: String,
    facts: Vec<Fact>,
}

#[derive(Debug, Serialize)]
pub struct Group {
    group_key: String,
    label: String,
    state: GroupState,
    stated_count: Option<String>,
    row_count: usize,
    incomplete_words: Option<String>,
    /// The most people the declaration's design lets the group hold.
    max_rows: Option<usize>,
    leaves: Vec<Leaf>,
    /// Adds one row built from `leaves`; none where the group takes no more.
    add_row_action: Option<RowAction>,
    /// Removes one served row named by its `row_index`; none where no row is
    /// stored.
    remove_row_action: Option<RowAction>,
    rows: Vec<Row>,
}

/// The household at the revision it was read at, which an edit of it names
/// as its baseline.
#[derive(Debug, Serialize)]
pub struct Household {
    pub profile_id: String,
    record_revision: u64,
    content_digest: String,
    groups: Vec<Group>,
    questions: Vec<Question>,
    pages: usize,
}

/// A row index as the product writes it: a canonical decimal.
fn canonical_index(index: &str) -> bool {
    !index.is_empty()
        && index.bytes().all(|byte| byte.is_ascii_digit())
        && (index == "0" || !index.starts_with('0'))
        && index.len() <= 9
}

pub struct Family {
    profile_id: String,
    pin: Pin,
    groups: Vec<Group>,
    questions: Vec<Question>,
    keys: BTreeSet<String>,
}
impl Family {
    pub fn new(profile_id: String) -> Self {
        Self {
            pin: Pin::new(PAGE_KIND, profile_id.clone()),
            profile_id,
            groups: vec![],
            questions: vec![],
            keys: BTreeSet::new(),
        }
    }
    pub fn request(&self, language: &str) -> Value {
        self.pin.request(language)
    }
    /// Takes the next page; says whether it was the last.
    pub fn accept(&mut self, value: Value) -> Result<bool> {
        let page: Page<Item> = serde_json::from_value(value).map_err(|_| protocol())?;
        let next = self.pin.check(&page)?;
        let last = page.is_last();
        for item in page.items {
            match item {
                Item::Group {
                    group_key,
                    label,
                    state,
                    stated_count,
                    row_count,
                    incomplete_words,
                    max_rows,
                    leaves,
                    add_row_action,
                    remove_row_action,
                } if self.keys.insert(group_key.clone()) => {
                    let leaf_keys: BTreeSet<_> = leaves.iter().map(|leaf| &leaf.leaf).collect();
                    if leaf_keys.len() != leaves.len()
                        || leaves
                            .iter()
                            .flat_map(|leaf| &leaf.shown_when)
                            .any(|condition| {
                                condition.equals.is_some() == condition.contains.is_some()
                            })
                        || (state == GroupState::NotServed
                            && (!leaves.is_empty() || row_count != 0 || stated_count.is_some()))
                        || max_rows == Some(0)
                        || (state == GroupState::Incomplete)
                            != incomplete_words
                                .as_deref()
                                .is_some_and(|words| !words.is_empty())
                    {
                        return Err(protocol());
                    }
                    self.groups.push(Group {
                        group_key,
                        label,
                        state,
                        stated_count,
                        row_count,
                        incomplete_words,
                        max_rows,
                        leaves,
                        add_row_action,
                        remove_row_action,
                        rows: vec![],
                    });
                }
                Item::Row {
                    group_key,
                    row_index,
                    mut facts,
                } => {
                    let group = self.groups.last_mut().ok_or_else(protocol)?;
                    let leaves: BTreeSet<_> = group.leaves.iter().map(|leaf| &leaf.leaf).collect();
                    let mut stated = BTreeSet::new();
                    if group.group_key != group_key
                        || !canonical_index(&row_index)
                        || group.rows.iter().any(|row| row.row_index == row_index)
                        || facts.is_empty()
                        || !facts.iter().all(|fact| {
                            leaves.contains(&fact.leaf)
                                && stated.insert(&fact.leaf)
                                && fact.path == format!("{group_key}.{row_index}.{}", fact.leaf)
                        })
                    {
                        return Err(protocol());
                    }
                    for fact in &mut facts {
                        if fact.masked {
                            fact.value = MASK.into();
                        }
                    }
                    group.rows.push(Row { row_index, facts });
                }
                Item::Question {
                    question_id,
                    path,
                    prompt,
                    help,
                    saved_value,
                    choices,
                } => {
                    let answers: BTreeSet<_> = choices.iter().map(|choice| &choice.value).collect();
                    if question_id.is_empty()
                        || path.is_empty()
                        || prompt.is_empty()
                        || self
                            .questions
                            .iter()
                            .any(|question| question.question_id == question_id)
                        || choices.is_empty()
                        || answers.len() != choices.len()
                        || saved_value.as_ref().is_some_and(|stated| {
                            !STATED_ANSWERS.contains(&stated.as_str()) || !answers.contains(stated)
                        })
                    {
                        return Err(protocol());
                    }
                    self.questions.push(Question {
                        question_id,
                        path,
                        prompt,
                        help,
                        saved_value,
                        choices,
                    });
                }
                Item::Group { .. } => return Err(protocol()),
            }
        }
        self.pin.advance(next);
        Ok(last)
    }
    /// The household, once every item was taken. A group's stated state must
    /// agree with the rows it holds: `rows` has them, `incomplete` may hold any
    /// number of them, and no other state holds one.
    pub fn finish(self) -> Result<Household> {
        if !self.pin.complete()
            || self.groups.is_empty()
            || self.groups.iter().any(|group| {
                group.row_count != group.rows.len()
                    || match group.state {
                        GroupState::Rows => group.rows.is_empty(),
                        GroupState::Incomplete => false,
                        _ => !group.rows.is_empty(),
                    }
            })
        {
            return Err(protocol());
        }
        Ok(Household {
            profile_id: self.profile_id,
            record_revision: self.pin.record_revision(),
            content_digest: self.pin.content_digest(),
            groups: self.groups,
            questions: self.questions,
            pages: self.pin.pages(),
        })
    }
}

impl ProfileHost {
    pub(super) async fn household(&self, language: String) -> Result<Household> {
        if !super::super::language::supported(&language) {
            return Err(protocol());
        }
        tokio::time::timeout(PROFILE_READ_LIMIT, async {
            let _serial = self.operation.lock().await;
            let person = self.person(None).await?;
            let profile = Self::profile_of(&person).await?;
            let mut family = Family::new(profile.clone());
            loop {
                let page = self
                    .run(
                        &person,
                        "user-profile.view",
                        family.request(&language),
                        false,
                    )
                    .await?;
                if family.accept(page)? {
                    break;
                }
            }
            self.still_held(&person, &profile).await?;
            family.finish()
        })
        .await
        .unwrap_or_else(|_| Err(Failure::new("unavailable")))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    const PROFILE: &str = "0b4f6c2e-8f0a-4a8e-9a43-5b1a6e0d7c11";
    const GROUP: &str = "renta_family.descendiente";

    fn leaf(key: &str) -> Value {
        json!({"leaf":key,"label":"Words","help":null,"field_type":"string","required":false,"choices":[]})
    }
    fn group(state: &str, rows: usize) -> Value {
        json!({"kind":"family_group","group_key":GROUP,"label":"Descendants","state":state,
            "stated_count":null,"row_count":rows,"incomplete_words":null,
            "leaves":[leaf("nombre"),leaf("fecha_nacimiento")]})
    }
    fn incomplete(rows: usize) -> Value {
        let mut stated = group("incomplete", rows);
        stated["stated_count"] = "3".into();
        stated["incomplete_words"] = "3 stated, 1 recorded".into();
        stated
    }
    fn row(index: &str, leaf: &str) -> Value {
        json!({"kind":"family_row","group_key":GROUP,"row_index":index,
            "facts":[{"leaf":leaf,"path":format!("{GROUP}.{index}.{leaf}"),"value":"x","masked":false}]})
    }
    fn not_served() -> Value {
        json!({"kind":"family_group","group_key":"renta_family.ascendiente","label":"Ascendants",
            "state":"not_served","stated_count":null,"row_count":0,"incomplete_words":null,"leaves":[]})
    }
    fn question(saved: Value) -> Value {
        json!({"kind":"family_question","question_id":"family-convive-con-otro-progenitor",
            "path":"renta_family.convive_con_otro_progenitor","prompt":"Do you live with them?",
            "help":null,"saved_value":saved,
            "choices":[{"value":"true","label":"Yes"},{"value":"false","label":"No"}]})
    }
    fn page(items: Vec<Value>, cursor: usize, total: usize) -> Value {
        let next = cursor + items.len();
        json!({"profile_id":PROFILE,"page_kind":"family_rows","outcome":"page","record_revision":4,
            "content_digest":"a".repeat(64),"setup_state":"incomplete","schema_version":1,"valid":true,
            "cursor":cursor,"next_cursor":(next < total).then_some(next),"total_items":total,"items":items})
    }
    fn read(items: Vec<Value>) -> Result<Household> {
        let total = items.len();
        let mut family = Family::new(PROFILE.into());
        assert!(family.accept(page(items, 0, total))?);
        family.finish()
    }

    #[test]
    fn the_household_is_asked_for_as_the_family_rows_stream_under_its_pin() {
        let mut family = Family::new(PROFILE.into());
        let first = family.request("hu");
        assert_eq!(first["page_kind"], "family_rows");
        assert_eq!(first["output_language"], "hu");
        assert!(first.get("expected_revision").is_none());
        assert!(
            !family
                .accept(page(vec![group("rows", 2), row("0", "nombre")], 0, 4))
                .unwrap()
        );
        let second = family.request("hu");
        assert_eq!(second["cursor"], 2);
        assert_eq!(second["expected_revision"], 4);
        assert_eq!(second["expected_content_digest"], "a".repeat(64));
    }

    #[test]
    fn groups_keep_the_state_the_product_stated_and_their_rows_in_order() {
        let household = read(vec![
            group("rows", 2),
            row("0", "nombre"),
            row("3", "fecha_nacimiento"),
            not_served(),
        ])
        .unwrap();
        let shown = serde_json::to_value(&household).unwrap();
        assert_eq!(shown["record_revision"], 4);
        assert_eq!(shown["groups"][0]["state"], "rows");
        assert_eq!(shown["groups"][0]["rows"][1]["row_index"], "3");
        assert_eq!(shown["groups"][1]["state"], "not_served");
        assert_eq!(shown["groups"][1]["rows"], json!([]));
        for state in ["unknown", "none_declared"] {
            let household = read(vec![group(state, 0)]).unwrap();
            let shown = serde_json::to_value(&household).unwrap();
            assert_eq!(shown["groups"][0]["state"], state);
            assert_eq!(shown["groups"][0]["row_count"], 0);
        }
    }

    #[test]
    fn an_incomplete_group_holds_its_recorded_rows_and_says_the_two_numbers() {
        let household = read(vec![incomplete(1), row("0", "nombre")]).unwrap();
        let shown = serde_json::to_value(&household).unwrap();
        assert_eq!(shown["groups"][0]["state"], "incomplete");
        assert_eq!(shown["groups"][0]["stated_count"], "3");
        assert_eq!(shown["groups"][0]["row_count"], 1);
        assert_eq!(
            shown["groups"][0]["incomplete_words"],
            "3 stated, 1 recorded"
        );
        assert_eq!(shown["groups"][0]["rows"][0]["row_index"], "0");
        // Nothing recorded under a stated count is still an incomplete group, not an unknown one.
        let none = read(vec![incomplete(0)]).unwrap();
        assert_eq!(
            serde_json::to_value(&none).unwrap()["groups"][0]["rows"],
            json!([])
        );
    }

    #[test]
    fn only_an_incomplete_group_carries_words_for_it_and_it_must_carry_them() {
        let mut worded = group("rows", 1);
        worded["incomplete_words"] = "3 stated, 1 recorded".into();
        assert!(read(vec![worded, row("0", "nombre")]).is_err());
        let mut silent = incomplete(1);
        silent["incomplete_words"] = Value::Null;
        assert!(read(vec![silent, row("0", "nombre")]).is_err());
        let mut blank = incomplete(1);
        blank["incomplete_words"] = "".into();
        assert!(read(vec![blank, row("0", "nombre")]).is_err());
        // The count of rows it holds must still be the number it states.
        assert!(read(vec![incomplete(2), row("0", "nombre")]).is_err());
    }

    #[test]
    fn a_group_keeps_the_most_people_the_design_holds_and_refuses_a_cap_of_none() {
        let mut capped = group("rows", 1);
        capped["max_rows"] = 4.into();
        let shown = serde_json::to_value(read(vec![capped, row("0", "nombre")]).unwrap()).unwrap();
        assert_eq!(shown["groups"][0]["max_rows"], 4);
        let shown = serde_json::to_value(read(vec![group("unknown", 0)]).unwrap()).unwrap();
        assert_eq!(shown["groups"][0]["max_rows"], Value::Null);
        let mut empty = group("unknown", 0);
        empty["max_rows"] = 0.into();
        assert!(read(vec![empty]).is_err());
    }

    #[test]
    fn a_masked_fact_is_never_released_with_its_value() {
        let mut secret = row("0", "nombre");
        secret["facts"][0]["masked"] = true.into();
        secret["facts"][0]["value"] = "private".into();
        let shown = serde_json::to_value(read(vec![group("rows", 1), secret]).unwrap()).unwrap();
        assert_eq!(
            shown["groups"][0]["rows"][0]["facts"][0]["value"],
            "••••••••"
        );
    }

    #[test]
    fn a_question_keeps_the_answer_the_profile_states_and_never_makes_one_up() {
        for (saved, expected) in [
            (json!("true"), json!("true")),
            (json!("false"), json!("false")),
            (Value::Null, Value::Null),
        ] {
            let shown =
                serde_json::to_value(read(vec![group("unknown", 0), question(saved)]).unwrap())
                    .unwrap();
            assert_eq!(shown["questions"].as_array().unwrap().len(), 1);
            assert_eq!(shown["questions"][0]["saved_value"], expected);
            assert_eq!(shown["questions"][0]["choices"][1]["label"], "No");
        }
        // A household with no question to ask carries none, not an empty answer.
        let shown = serde_json::to_value(read(vec![group("unknown", 0)]).unwrap()).unwrap();
        assert_eq!(shown["questions"], json!([]));
    }

    #[test]
    fn a_question_that_states_an_answer_outside_its_choices_is_refused() {
        for saved in [json!("yes"), json!(""), json!("TRUE"), json!(true)] {
            assert!(read(vec![group("unknown", 0), question(saved)]).is_err());
        }
        let mut offered = question(json!("true"));
        offered["choices"] = json!([{"value":"false","label":"No"}]);
        assert!(read(vec![group("unknown", 0), offered]).is_err());
        let mut bare = question(Value::Null);
        bare["choices"] = json!([]);
        assert!(read(vec![group("unknown", 0), bare]).is_err());
        let mut repeated = question(Value::Null);
        repeated["choices"] =
            json!([{"value":"true","label":"Yes"},{"value":"true","label":"Yes"}]);
        assert!(read(vec![group("unknown", 0), repeated]).is_err());
        let mut unnamed = question(Value::Null);
        unnamed["prompt"] = "".into();
        assert!(read(vec![group("unknown", 0), unnamed]).is_err());
        let mut extra = question(Value::Null);
        extra["advice"] = "x".into();
        assert!(read(vec![group("unknown", 0), extra]).is_err());
        assert!(
            read(vec![
                group("unknown", 0),
                question(Value::Null),
                question(Value::Null)
            ])
            .is_err()
        );
    }

    #[test]
    fn only_the_three_item_kinds_of_the_stream_are_taken() {
        for foreign in [
            json!({"kind":"section","key":"identity","title":"T","summary":"","repeatable":false}),
            json!({"kind":"field","section_key":"identity","field":{}}),
            json!({"kind":"missing","path":"identity.name"}),
            json!({"kind":"notice","severity":"warning","message":"m"}),
            json!({"kind":"question"}),
            json!({"kind":"fact","path":"identity.name","value":"x"}),
        ] {
            assert!(read(vec![group("unknown", 0), foreign.clone()]).is_err());
            assert!(read(vec![foreign]).is_err());
        }
    }

    #[test]
    fn an_unknown_member_of_an_item_is_refused() {
        let mut extra = group("unknown", 0);
        extra["advice"] = "x".into();
        assert!(read(vec![extra]).is_err());
        let mut leafy = group("unknown", 0);
        leafy["leaves"][0]["tip"] = "x".into();
        assert!(read(vec![leafy]).is_err());
        let mut stated = row("0", "nombre");
        stated["facts"][0]["origin"] = "x".into();
        assert!(read(vec![group("rows", 1), stated]).is_err());
        let mut unnamed = group("unknown", 0);
        unnamed["leaves"][0]
            .as_object_mut()
            .unwrap()
            .remove("label");
        assert!(read(vec![unnamed]).is_err());
        let mut stateless = group("unknown", 0);
        stateless["state"] = "empty".into();
        assert!(read(vec![stateless]).is_err());
    }

    const OPERATION: &str = "user-profile.descendants";

    fn action(words: &str) -> Value {
        json!({"action_words":words,"target_operation_ids":[OPERATION]})
    }

    #[test]
    fn a_leaf_keeps_the_conditions_it_is_asked_under_and_one_without_any_is_always_asked() {
        let mut conditional = group("unknown", 0);
        conditional["leaves"][0]["shown_when"] = json!([
            {"leaf":"fecha_nacimiento","equals":"true"},
            {"leaf":"fecha_nacimiento","contains":"a","equals":null},
            {"leaf":"fecha_nacimiento","equals":null,"contains":"b,c"}
        ]);
        let shown = serde_json::to_value(read(vec![conditional]).unwrap()).unwrap();
        assert_eq!(
            shown["groups"][0]["leaves"][0]["shown_when"],
            json!([
                {"leaf":"fecha_nacimiento","equals":"true","contains":null},
                {"leaf":"fecha_nacimiento","equals":null,"contains":"a"},
                {"leaf":"fecha_nacimiento","equals":null,"contains":"b,c"}
            ])
        );
        // A leaf that states none, or an empty list, is asked always.
        assert_eq!(shown["groups"][0]["leaves"][1]["shown_when"], json!([]));
        let mut empty = group("unknown", 0);
        empty["leaves"][0]["shown_when"] = json!([]);
        let shown = serde_json::to_value(read(vec![empty]).unwrap()).unwrap();
        assert_eq!(shown["groups"][0]["leaves"][0]["shown_when"], json!([]));
    }

    #[test]
    fn a_condition_states_exactly_one_answer_and_nothing_else() {
        for condition in [
            json!({"leaf":"nombre","equals":"a","contains":"b"}),
            json!({"leaf":"nombre"}),
            json!({"leaf":"nombre","equals":null,"contains":null}),
            json!({"leaf":"nombre","equals":"a","tip":"x"}),
            json!({"equals":"a"}),
            json!({"leaf":"nombre","equals":1}),
        ] {
            let mut stated = group("unknown", 0);
            stated["leaves"][1]["shown_when"] = json!([condition.clone()]);
            assert!(read(vec![stated]).is_err(), "{condition}");
        }
        let mut listless = group("unknown", 0);
        listless["leaves"][0]["shown_when"] = Value::Null;
        assert!(read(vec![listless]).is_err());
    }

    #[test]
    fn a_group_carries_the_row_controls_the_product_serves_and_none_where_it_serves_none() {
        let mut both = group("rows", 1);
        both["add_row_action"] = action("Add a person");
        both["remove_row_action"] = action("Remove a person");
        let shown = serde_json::to_value(read(vec![both, row("0", "nombre")]).unwrap()).unwrap();
        assert_eq!(shown["groups"][0]["add_row_action"], action("Add a person"));
        assert_eq!(
            shown["groups"][0]["remove_row_action"],
            action("Remove a person")
        );
        // Absent and null are the same statement: no such control.
        let mut nulls = group("unknown", 0);
        nulls["add_row_action"] = action("Add a person");
        nulls["remove_row_action"] = Value::Null;
        let shown = serde_json::to_value(read(vec![nulls]).unwrap()).unwrap();
        assert_eq!(
            shown["groups"][0]["add_row_action"]["action_words"],
            "Add a person"
        );
        assert_eq!(shown["groups"][0]["remove_row_action"], Value::Null);
        let shown = serde_json::to_value(read(vec![group("unknown", 0)]).unwrap()).unwrap();
        assert_eq!(shown["groups"][0]["add_row_action"], Value::Null);
        assert_eq!(shown["groups"][0]["remove_row_action"], Value::Null);
        let mut nulled = group("unknown", 0);
        nulled["add_row_action"] = Value::Null;
        nulled["remove_row_action"] = Value::Null;
        let shown = serde_json::to_value(read(vec![nulled]).unwrap()).unwrap();
        assert_eq!(shown["groups"][0]["add_row_action"], Value::Null);
        assert_eq!(shown["groups"][0]["remove_row_action"], Value::Null);
    }

    #[test]
    fn a_row_control_with_an_unknown_or_missing_member_is_refused() {
        for member in ["add_row_action", "remove_row_action"] {
            let mut extra = group("unknown", 0);
            extra[member] = action("Add a person");
            extra[member]["advice"] = "x".into();
            assert!(read(vec![extra]).is_err(), "{member}");
            let mut unworded = group("unknown", 0);
            unworded[member] = action("Add a person");
            unworded[member]
                .as_object_mut()
                .unwrap()
                .remove("action_words");
            assert!(read(vec![unworded]).is_err(), "{member}");
            let mut untargeted = group("unknown", 0);
            untargeted[member] = action("Add a person");
            untargeted[member]
                .as_object_mut()
                .unwrap()
                .remove("target_operation_ids");
            assert!(read(vec![untargeted]).is_err(), "{member}");
            let mut mistyped = group("unknown", 0);
            mistyped[member] = json!({"action_words":"Add","target_operation_ids":OPERATION});
            assert!(read(vec![mistyped]).is_err(), "{member}");
        }
    }

    #[test]
    fn a_row_belongs_to_the_group_before_it_and_to_one_of_its_leaves() {
        assert!(read(vec![row("0", "nombre")]).is_err());
        let mut other = row("0", "nombre");
        other["group_key"] = "renta_family.ascendiente".into();
        assert!(read(vec![group("rows", 1), other]).is_err());
        assert!(read(vec![group("rows", 1), row("0", "peso")]).is_err());
        let mut elsewhere = row("0", "nombre");
        elsewhere["facts"][0]["path"] = format!("{GROUP}.1.nombre").into();
        assert!(read(vec![group("rows", 1), elsewhere]).is_err());
        let mut twice = row("0", "nombre");
        let fact = twice["facts"][0].clone();
        twice["facts"].as_array_mut().unwrap().push(fact);
        assert!(read(vec![group("rows", 1), twice]).is_err());
        let mut empty = row("0", "nombre");
        empty["facts"] = json!([]);
        assert!(read(vec![group("rows", 1), empty]).is_err());
        for index in ["", "01", "-1", "a", "1234567890"] {
            assert!(
                read(vec![group("rows", 1), row(index, "nombre")]).is_err(),
                "{index:?}"
            );
        }
        assert!(
            read(vec![
                group("rows", 2),
                row("0", "nombre"),
                row("0", "nombre")
            ])
            .is_err()
        );
    }

    #[test]
    fn a_groups_state_agrees_with_its_rows_and_an_unserved_group_is_bare() {
        // A count that no stored row matches, rows under a state that has none,
        // and the other way round, are an unreadable stream, never an empty one.
        assert!(read(vec![group("rows", 2), row("0", "nombre")]).is_err());
        assert!(read(vec![group("rows", 0)]).is_err());
        assert!(read(vec![group("unknown", 1), row("0", "nombre")]).is_err());
        assert!(read(vec![group("none_declared", 0), row("0", "nombre")]).is_err());
        let mut served = not_served();
        served["row_count"] = 1.into();
        assert!(read(vec![served]).is_err());
        let mut worded = not_served();
        worded["leaves"] = json!([leaf("nombre")]);
        assert!(read(vec![worded]).is_err());
        let mut counted = not_served();
        counted["stated_count"] = "0".into();
        assert!(read(vec![counted]).is_err());
        let mut repeated = group("unknown", 0);
        repeated["leaves"] = json!([leaf("nombre"), leaf("nombre")]);
        assert!(read(vec![repeated]).is_err());
        assert!(read(vec![group("unknown", 0), group("unknown", 0)]).is_err());
    }

    #[test]
    fn a_stream_for_another_profile_kind_or_revision_is_refused() {
        let items = || vec![group("unknown", 0)];
        for (member, value) in [
            ("profile_id", json!("another")),
            ("page_kind", json!("overview")),
            ("cursor", json!(1)),
            ("record_revision", json!(0)),
        ] {
            let mut wrong = page(items(), 0, 1);
            wrong[member] = value;
            assert!(
                Family::new(PROFILE.into()).accept(wrong).is_err(),
                "{member}"
            );
        }
        let mut family = Family::new(PROFILE.into());
        assert!(
            !family
                .accept(page(vec![group("unknown", 0)], 0, 2))
                .unwrap()
        );
        let mut moved = page(vec![not_served()], 1, 2);
        moved["record_revision"] = 5.into();
        assert!(family.accept(moved).is_err());
        let mut unfinished = Family::new(PROFILE.into());
        assert!(
            !unfinished
                .accept(page(vec![group("unknown", 0)], 0, 2))
                .unwrap()
        );
        assert!(unfinished.finish().is_err());
    }

    #[test]
    fn a_refused_stream_is_a_conflict_only_for_a_stale_revision() {
        let refused = |code: &str| {
            let mut page = page(vec![], 0, 0);
            page["outcome"] = "refused".into();
            page["refusal_code"] = code.into();
            Family::new(PROFILE.into()).accept(page).unwrap_err().code
        };
        assert_eq!(refused("stale_revision"), "conflict");
        assert_eq!(refused("projection_unavailable"), "unavailable");
    }
}
