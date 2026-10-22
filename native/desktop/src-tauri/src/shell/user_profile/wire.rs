//! Assemble only a complete, consistently pinned overview stream.
use super::{Failure, Result, protocol};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::collections::BTreeSet;

#[derive(Clone, Deserialize, Serialize)]
pub struct Choice {
    value: String,
    label: String,
}
#[derive(Clone, Deserialize, Serialize)]
pub struct Field {
    pub path: String,
    label: String,
    value: Option<String>,
    masked: bool,
    required: bool,
    field_type: String,
    choices: Vec<Choice>,
    help: Option<Vec<String>>,
    about: String,
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
#[derive(Serialize)]
pub struct Notice {
    severity: String,
    message: String,
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
        field: Field,
    },
    Missing {
        path: String,
    },
    Notice {
        severity: String,
        message: String,
    },
}
#[derive(Deserialize)]
struct Page {
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
    items: Vec<Item>,
}
pub struct Pages {
    overview: Overview,
    cursor: usize,
    total: Option<usize>,
    schema: u64,
    paths: BTreeSet<String>,
    keys: BTreeSet<String>,
    trailing: bool,
}
impl Pages {
    pub fn new(profile_id: String) -> Self {
        Self {
            overview: Overview {
                profile_id,
                record_revision: 0,
                content_digest: String::new(),
                setup_state: String::new(),
                valid: false,
                sections: vec![],
                missing_required: vec![],
                notices: vec![],
                pages: 0,
            },
            cursor: 0,
            total: None,
            schema: 0,
            paths: BTreeSet::new(),
            keys: BTreeSet::new(),
            trailing: false,
        }
    }
    pub fn request(&self, language: &str) -> Value {
        let mut request = json!({"profile_id":self.overview.profile_id,"page_kind":"overview","cursor":self.cursor,"limit":128,"output_language":language});
        if self.total.is_some() {
            request["expected_revision"] = self.overview.record_revision.into();
            request["expected_content_digest"] = self.overview.content_digest.clone().into();
        }
        request
    }
    pub fn accept(&mut self, value: Value) -> Result<bool> {
        let page: Page = serde_json::from_value(value).map_err(|_| protocol())?;
        if page.outcome == "refused" {
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
            || page.page_kind != "overview"
            || page.profile_id != self.overview.profile_id
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
            || self.overview.pages >= 256
        {
            return Err(protocol());
        }
        if let Some(total) = self.total {
            if page.record_revision != self.overview.record_revision
                || page.content_digest != self.overview.content_digest
                || page.setup_state != self.overview.setup_state
                || page.valid != self.overview.valid
                || page.schema_version != self.schema
                || total != page.total_items
            {
                return Err(protocol());
            }
        } else {
            self.overview.record_revision = page.record_revision;
            self.overview.content_digest = page.content_digest;
            self.overview.setup_state = page.setup_state;
            self.overview.valid = page.valid;
            self.total = Some(page.total_items);
            self.schema = page.schema_version;
        }
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
                    section.fields.push(field);
                }
                Item::Missing { path } if !self.overview.missing_required.contains(&path) => {
                    self.trailing = true;
                    self.overview.missing_required.push(path);
                }
                Item::Notice { severity, message } => {
                    self.trailing = true;
                    self.overview.notices.push(Notice { severity, message });
                }
                _ => return Err(protocol()),
            }
        }
        self.cursor = next;
        self.overview.pages += 1;
        Ok(page.next_cursor.is_none())
    }
    pub fn finish(self) -> Result<Overview> {
        if self.total != Some(self.cursor)
            || self.overview.sections.is_empty()
            || self
                .overview
                .missing_required
                .iter()
                .any(|path| !self.paths.contains(path))
        {
            return Err(protocol());
        }
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

#[cfg(test)]
mod tests {
    use super::*;
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
