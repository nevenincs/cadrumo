//! Assemble only a complete, consistently pinned profile page stream.
use super::{Failure, Result, protocol};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::collections::BTreeSet;

#[derive(Clone, Deserialize, Serialize)]
pub struct Choice {
    value: String,
    label: String,
}
/// What one stored fact states for the ejercicio its window starts in.
#[derive(Clone, Deserialize, Serialize)]
pub struct EjercicioStatement {
    ejercicio: i64,
    value: String,
}
/// The wizard questions a field stated per ejercicio is answered through,
/// and what it states so far.
#[derive(Clone, Deserialize, Serialize)]
pub struct EjercicioAnswer {
    question_id: String,
    year_question_id: String,
    statements: Vec<EjercicioStatement>,
}
#[derive(Clone, Deserialize, Serialize)]
pub struct Field {
    pub path: String,
    label: String,
    value: Option<String>,
    masked: bool,
    required: bool,
    field_type: String,
    /// The country codes offered; any code of the field's shape stays allowed.
    #[serde(default)]
    country_options: Vec<String>,
    choices: Vec<Choice>,
    help: Option<Vec<String>>,
    about: String,
    #[serde(default)]
    ejercicio_answer: Option<EjercicioAnswer>,
    row_index: Option<String>,
}
#[derive(Serialize)]
pub struct Section {
    key: String,
    title: String,
    summary: String,
    repeatable: bool,
    fields: Vec<Field>,
}
/// The catalogue action a served notice offers; the window maps it to a door it already has.
#[derive(Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct NoticeAction {
    action_id: String,
    target_command_key: String,
}
#[derive(Serialize)]
pub struct Notice {
    severity: String,
    code: String,
    message: String,
    action: Option<NoticeAction>,
}
#[derive(Serialize)]
pub struct Overview {
    pub profile_id: String,
    record_revision: u64,
    content_digest: String,
    setup_state: String,
    valid: bool,
    sections: Vec<Section>,
    missing_required: Vec<String>,
    notices: Vec<Notice>,
    pub pages: usize,
}
#[derive(Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
enum Item {
    Section {
        key: String,
        title: String,
        summary: String,
        repeatable: bool,
    },
    Field {
        section_key: String,
        field: Box<Field>,
    },
    Missing {
        path: String,
    },
    Notice {
        severity: String,
        code: String,
        message: String,
        #[serde(default)]
        action: Option<NoticeAction>,
    },
}
/// One page of a `user-profile.view` stream, as the product serves it.
#[derive(Deserialize)]
pub(super) struct Page<I> {
    profile_id: String,
    page_kind: String,
    outcome: String,
    refusal_code: Option<String>,
    record_revision: u64,
    content_digest: String,
    setup_state: String,
    schema_version: u64,
    valid: bool,
    cursor: usize,
    next_cursor: Option<usize>,
    total_items: usize,
    pub(super) items: Vec<I>,
}

impl<I> Page<I> {
    /// Whether no page follows this one.
    pub(super) fn is_last(&self) -> bool {
        self.next_cursor.is_none()
    }
}

/// What the first page of a stream pins and every later page must repeat.
struct Pinned {
    record_revision: u64,
    content_digest: String,
    setup_state: String,
    valid: bool,
    schema_version: u64,
    total_items: usize,
}

/// The pagination of one `user-profile.view` page stream over one profile
/// revision: the request that asks for the next page, and the checks that a
/// page is the one asked for and the stream stays on the revision it began on.
/// What a page's items mean is the stream's own.
pub(super) struct Pin {
    kind: &'static str,
    profile_id: String,
    pinned: Option<Pinned>,
    cursor: usize,
    pages: usize,
}
impl Pin {
    pub(super) fn new(kind: &'static str, profile_id: String) -> Self {
        Self {
            kind,
            profile_id,
            pinned: None,
            cursor: 0,
            pages: 0,
        }
    }
    pub(super) fn request(&self, language: &str) -> Value {
        let mut request = json!({"profile_id":self.profile_id,"page_kind":self.kind,"cursor":self.cursor,"limit":128,"output_language":language});
        if let Some(pinned) = &self.pinned {
            request["expected_revision"] = pinned.record_revision.into();
            request["expected_content_digest"] = pinned.content_digest.clone().into();
        }
        request
    }
    /// Checks `page` against the request and the pages before it, pins the
    /// stream on its first page, and answers the cursor after it. The caller
    /// takes the items, then calls [`Pin::advance`] with that cursor.
    pub(super) fn check<I>(&mut self, page: &Page<I>) -> Result<usize> {
        if page.outcome == "refused" {
            if page.refusal_code.as_deref() == Some("invalid_household_draft") {
                // The window renders the served code as served.
                let mut refused = Failure::new("refused");
                refused.reason = page.refusal_code.clone();
                return Err(refused);
            }
            return Err(Failure::new(
                if page.refusal_code.as_deref() == Some("stale_revision") {
                    "conflict"
                } else {
                    "unavailable"
                },
            ));
        }
        let next = self
            .cursor
            .checked_add(page.items.len())
            .ok_or_else(protocol)?;
        if page.outcome != "page"
            || page.page_kind != self.kind
            || page.profile_id != self.profile_id
            || page.cursor != self.cursor
            || page.record_revision == 0
            || page.schema_version == 0
            || !matches!(page.setup_state.as_str(), "complete" | "incomplete")
            || !super::super::setup::wire::is_hex64(&page.content_digest)
            || page.items.len() > 128
            || page.total_items > 16_384
            || next > page.total_items
            || (page.cursor < page.total_items && page.items.is_empty())
            || page.next_cursor != (next < page.total_items).then_some(next)
            || self.pages >= 256
        {
            return Err(protocol());
        }
        if let Some(pinned) = &self.pinned {
            if page.record_revision != pinned.record_revision
                || page.content_digest != pinned.content_digest
                || page.setup_state != pinned.setup_state
                || page.valid != pinned.valid
                || page.schema_version != pinned.schema_version
                || page.total_items != pinned.total_items
            {
                return Err(protocol());
            }
        } else {
            self.pinned = Some(Pinned {
                record_revision: page.record_revision,
                content_digest: page.content_digest.clone(),
                setup_state: page.setup_state.clone(),
                valid: page.valid,
                schema_version: page.schema_version,
                total_items: page.total_items,
            });
        }
        Ok(next)
    }
    pub(super) fn advance(&mut self, next: usize) {
        self.cursor = next;
        self.pages += 1;
    }
    /// Whether every item the first page counted has been taken.
    pub(super) fn complete(&self) -> bool {
        self.pinned
            .as_ref()
            .is_some_and(|pinned| pinned.total_items == self.cursor)
    }
    pub(super) fn pages(&self) -> usize {
        self.pages
    }
    pub(super) fn record_revision(&self) -> u64 {
        self.pinned
            .as_ref()
            .map_or(0, |pinned| pinned.record_revision)
    }
    pub(super) fn content_digest(&self) -> String {
        self.pinned
            .as_ref()
            .map_or_else(String::new, |pinned| pinned.content_digest.clone())
    }
    pub(super) fn setup_state(&self) -> String {
        self.pinned
            .as_ref()
            .map_or_else(String::new, |pinned| pinned.setup_state.clone())
    }
    pub(super) fn valid(&self) -> bool {
        self.pinned.as_ref().is_some_and(|pinned| pinned.valid)
    }
}
pub struct Pages {
    overview: Overview,
    pin: Pin,
    paths: BTreeSet<String>,
    keys: BTreeSet<String>,
    trailing: bool,
}
impl Pages {
    pub fn new(profile_id: String) -> Self {
        Self {
            overview: Overview {
                profile_id: profile_id.clone(),
                record_revision: 0,
                content_digest: String::new(),
                setup_state: String::new(),
                valid: false,
                sections: vec![],
                missing_required: vec![],
                notices: vec![],
                pages: 0,
            },
            pin: Pin::new("overview", profile_id),
            paths: BTreeSet::new(),
            keys: BTreeSet::new(),
            trailing: false,
        }
    }
    pub fn request(&self, language: &str) -> Value {
        self.pin.request(language)
    }
    pub fn accept(&mut self, value: Value) -> Result<bool> {
        let page: Page<Item> = serde_json::from_value(value).map_err(|_| protocol())?;
        let next = self.pin.check(&page)?;
        let last = page.is_last();
        for item in page.items {
            match item {
                Item::Section {
                    key,
                    title,
                    summary,
                    repeatable,
                } if !self.trailing && self.keys.insert(key.clone()) => {
                    self.overview.sections.push(Section {
                        key,
                        title,
                        summary,
                        repeatable,
                        fields: vec![],
                    })
                }
                Item::Field {
                    section_key,
                    mut field,
                } if !self.trailing && self.paths.insert(field.path.clone()) => {
                    let section = self.overview.sections.last_mut().ok_or_else(protocol)?;
                    if section.key != section_key
                        || !field.path.starts_with(&format!("{section_key}."))
                    {
                        return Err(protocol());
                    }
                    if field.masked && field.value.is_some() {
                        field.value = Some("••••••••".into());
                    }
                    section.fields.push(*field);
                }
                Item::Missing { path } if !self.overview.missing_required.contains(&path) => {
                    self.trailing = true;
                    self.overview.missing_required.push(path);
                }
                Item::Notice {
                    severity,
                    code,
                    message,
                    action,
                } => {
                    self.trailing = true;
                    self.overview.notices.push(Notice {
                        severity,
                        code,
                        message,
                        action,
                    });
                }
                _ => return Err(protocol()),
            }
        }
        self.pin.advance(next);
        Ok(last)
    }
    pub fn finish(mut self) -> Result<Overview> {
        if !self.pin.complete()
            || self.overview.sections.is_empty()
            || self
                .overview
                .missing_required
                .iter()
                .any(|path| !self.paths.contains(path))
        {
            return Err(protocol());
        }
        self.overview.record_revision = self.pin.record_revision();
        self.overview.content_digest = self.pin.content_digest();
        self.overview.setup_state = self.pin.setup_state();
        self.overview.valid = self.pin.valid();
        self.overview.pages = self.pin.pages();
        Ok(self.overview)
    }
}

pub(super) fn mutation_failure(projection: &serde_json::Value) -> &'static str {
    if projection["effect"] != "none" {
        return "unknown";
    }
    if projection["terminal_condition"] == "failed"
        && projection["failure_error_code"] == "FAIL_PROFILE_RECORD_CONFLICT"
    {
        return "conflict";
    }
    "refused"
}

/// The longest sentence a refusal is relayed with.
const REFUSAL_WORDS_LIMIT: usize = 1024;

/// The finished sentence a registered error detail carries for the refusal,
/// where it carries one within the bound. The host words nothing itself.
pub(super) fn refusal_words(detail: &serde_json::Value) -> Option<String> {
    detail["refusal_words"]
        .as_str()
        .map(str::trim)
        .filter(|words| !words.is_empty() && words.chars().count() <= REFUSAL_WORDS_LIMIT)
        .map(str::to_owned)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn a_refusal_is_relayed_with_only_a_bounded_sentence_the_application_served() {
        let served = json!({"detail_version":1,"kind":"registered_error","refusal_words":" Row 2 needs a date of birth. "});
        assert_eq!(
            refusal_words(&served).as_deref(),
            Some("Row 2 needs a date of birth.")
        );
        for unserved in [
            json!({"kind":"registered_error"}),
            json!({"refusal_words":""}),
            json!({"refusal_words":"   "}),
            json!({"refusal_words":7}),
            json!({"refusal_words":"a".repeat(REFUSAL_WORDS_LIMIT + 1)}),
            json!(null),
        ] {
            assert_eq!(refusal_words(&unserved), None, "{unserved}");
        }
    }
    #[test]
    fn only_a_settled_no_effect_conflict_is_safe_to_correct() {
        let mut projection = json!({
            "terminal_condition": "failed",
            "effect": "none",
            "failure_error_code": "FAIL_PROFILE_RECORD_CONFLICT"
        });
        assert_eq!(mutation_failure(&projection), "conflict");
        projection["effect"] = "unknown".into();
        assert_eq!(mutation_failure(&projection), "unknown");
        projection["effect"] = "none".into();
        projection["failure_error_code"] = "OTHER_FAILURE".into();
        assert_eq!(mutation_failure(&projection), "refused");
    }
    fn page() -> Value {
        json!({"profile_id":"p","page_kind":"overview","outcome":"page","record_revision":1,"content_digest":"a".repeat(64),"setup_state":"incomplete","schema_version":1,"valid":true,"cursor":0,"next_cursor":null,"total_items":1,"items":[{"kind":"section","key":"identity","title":"Identity","summary":"","repeatable":false}]})
    }
    #[test]
    fn a_field_keeps_the_country_codes_and_the_ejercicio_answer_it_is_served_with() {
        let served = json!({
            "path": "irpf.activity_income_imputation_criterion",
            "label": "Criterion",
            "value": null,
            "masked": false,
            "required": false,
            "field_type": "code",
            "country_options": ["ES", "PT"],
            "choices": [],
            "help": null,
            "about": "",
            "ejercicio_answer": {
                "question_id": "q",
                "year_question_id": "y",
                "statements": [{"ejercicio": 2025, "value": "devengo"}]
            },
            "row_index": null
        });
        let field: Field = serde_json::from_value(served.clone()).unwrap();
        assert_eq!(serde_json::to_value(&field).unwrap(), served);
        let mut bare = served;
        bare.as_object_mut().unwrap().remove("country_options");
        bare.as_object_mut().unwrap().remove("ejercicio_answer");
        let field: Field = serde_json::from_value(bare).unwrap();
        let held = serde_json::to_value(&field).unwrap();
        assert_eq!(held["country_options"], json!([]));
        assert_eq!(held["ejercicio_answer"], Value::Null);
    }
    #[test]
    fn only_complete_pinned_streams_are_released() {
        let mut pages = Pages::new("p".into());
        assert!(pages.accept(page()).unwrap());
        assert!(pages.finish().is_ok());
        for key in ["profile_id", "page_kind", "content_digest"] {
            let mut wrong = page();
            wrong[key] = "wrong".into();
            assert!(Pages::new("p".into()).accept(wrong).is_err());
        }
    }
    #[test]
    fn continuation_must_have_the_same_revision_and_exact_cursor() {
        let mut first = page();
        first["total_items"] = 2.into();
        first["next_cursor"] = 1.into();
        for changed in ["record_revision", "cursor"] {
            let mut pages = Pages::new("p".into());
            assert!(!pages.accept(first.clone()).unwrap());
            assert_eq!(pages.request("en")["expected_revision"], 1);
            let mut next = page();
            next["cursor"] = 1.into();
            next["total_items"] = 2.into();
            next[changed] = 3.into();
            assert!(pages.accept(next).is_err());
        }
    }
}
