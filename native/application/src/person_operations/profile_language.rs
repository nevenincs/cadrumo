use super::failure::{Failure, Outcome, RelayFailure};
use super::lifecycle::{
    await_terminal, describe, projected, read_result_document, result_request, result_success,
    settled, start, submit,
};
use super::protocol::{
    Contract, PROFILE_SETUP_STATES, PROFILE_VIEW_PAGE_KEYS, PROFILE_VIEW_PAGE_KINDS,
    PROFILE_VIEW_PAGE_REQUIRED, PROFILE_VIEW_REFUSALS, RESULT_REFUSALS, closed, count, flag, hex64,
    one_of, refusal_code, same_uuid, text, uuid_key,
};
use super::transport::{Held, remaining};
use crate::canonical_json::json_string;
use crate::runtime_client::{connection::SessionExchange, refusal::Refusal, session::Admitted};
use serde_json::{Value, json};
use std::time::{Duration, Instant};

/// The budget of one profile view read and of one profile mutation.
pub(super) const PROFILE_BUDGET: Duration = Duration::from_secs(60);
pub(super) const PROFILE_VIEW_EVENT_PAGE: u64 = 32;
pub(super) const PROFILE_MUTATION_EVENT_PAGE: u64 = 1;
pub(super) const PROFILE_VIEW: &str = "user-profile.view";
pub(super) const PROFILE_FIELD_MUTATION: &str = "user-profile.field-mutation";
pub(super) const PROFILE_FIELD_MUTATION_RESULT: &str = "user-profile.field-mutation.result";
pub(super) const OUTPUT_LANGUAGE_PATH: &str = "preferences.output_language";
pub(super) const OUTPUT_LANGUAGES: [&str; 4] = ["es", "en", "ca", "hu"];
pub(super) const PROFILE_VIEW_MAX_ITEMS: u64 = 128;
pub(super) const PROFILE_VIEW_MAX_PAGES: usize = 512;

/// The profile's saved output language and the revision it was read at.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ProfileLanguage {
    /// `es`, `en`, `ca` or `hu`; `None` when the profile saved none.
    pub language: Option<String>,
    pub record_revision: u64,
    pub content_digest: String,
}

/// Reads the profile's saved output language through the registered
/// exact-profile view, within `deadline` and the view's own budget.
pub fn read_profile_language(
    connection: &dyn SessionExchange,
    session: &Admitted,
    deadline: Instant,
) -> Result<ProfileLanguage, RelayFailure> {
    read_language(
        &Held {
            connection,
            session,
        },
        deadline,
    )
    .map_err(Failure::held)
}

/// Sets only the output language through the guarded field mutation at the
/// revision just read, then reads it again. `language` must be `es`, `en`,
/// `ca` or `hu`.
pub fn set_profile_language(
    connection: &dyn SessionExchange,
    session: &Admitted,
    language: &str,
    deadline: Instant,
) -> Result<ProfileLanguage, RelayFailure> {
    if !OUTPUT_LANGUAGES.contains(&language) {
        return Err(RelayFailure::Invalid);
    }
    let held = Held {
        connection,
        session,
    };
    set_language(&held, language, deadline).map_err(Failure::held)
}

/// The facts one profile view page pins: every page of a read must agree.
#[derive(Clone, Debug, PartialEq, Eq)]
pub(super) struct Pin {
    pub(super) record_revision: u64,
    pub(super) content_digest: String,
    pub(super) setup_state: String,
    pub(super) schema_version: u64,
    pub(super) valid: bool,
}

/// One page of the profile's preferences.
pub(super) struct ViewPage {
    pub(super) profile_id: String,
    pub(super) page_kind: String,
    pub(super) refusal_code: Option<String>,
    pub(super) pin: Pin,
    pub(super) cursor: u64,
    pub(super) next_cursor: Option<u64>,
    /// Each fact's path and value.
    pub(super) facts: Vec<(String, String)>,
}

pub(super) fn view_page(value: &Value) -> Outcome<ViewPage> {
    let document = value
        .as_object()
        .filter(|page| closed(page, &PROFILE_VIEW_PAGE_KEYS, &PROFILE_VIEW_PAGE_REQUIRED))
        .ok_or_else(Failure::frame)?;
    let refusal_code = match document.get("refusal_code") {
        None | Some(Value::Null) => None,
        Some(_) => Some(one_of(document, "refusal_code", &PROFILE_VIEW_REFUSALS)?.to_owned()),
    };
    let next_cursor = match document.get("next_cursor") {
        None | Some(Value::Null) => None,
        Some(_) => Some(count(document, "next_cursor")?),
    };
    let facts = match document.get("items") {
        None => Vec::new(),
        Some(Value::Array(items)) => items
            .iter()
            .map(|item| {
                let item = item.as_object()?;
                let keys = ["kind", "path", "value"];
                (closed(item, &keys, &keys) && text(item, "kind") == Some("fact")).then_some(())?;
                Some((
                    text(item, "path")?.to_owned(),
                    text(item, "value")?.to_owned(),
                ))
            })
            .collect::<Option<Vec<_>>>()
            .ok_or_else(Failure::frame)?,
        Some(_) => return Err(Failure::frame()),
    };
    let page = ViewPage {
        profile_id: text(document, "profile_id")
            .filter(|id| uuid_key(id).is_some())
            .ok_or_else(Failure::frame)?
            .to_owned(),
        page_kind: one_of(document, "page_kind", &PROFILE_VIEW_PAGE_KINDS)?.to_owned(),
        refusal_code,
        pin: Pin {
            record_revision: count(document, "record_revision")?,
            content_digest: hex64(document, "content_digest")?.to_owned(),
            setup_state: one_of(document, "setup_state", &PROFILE_SETUP_STATES)?.to_owned(),
            schema_version: count(document, "schema_version")?,
            valid: flag(document, "valid")?,
        },
        cursor: count(document, "cursor")?,
        next_cursor,
        facts,
    };
    let total = count(document, "total_items")?;
    let listed = page.facts.len() as u64;
    let shaped = page.pin.record_revision >= 1
        && page.pin.schema_version >= 1
        && match one_of(document, "outcome", &["page", "refused"])? {
            "refused" => page.refusal_code.is_some() && listed == 0 && page.next_cursor.is_none(),
            _ => {
                let next = page.cursor + listed;
                page.refusal_code.is_none()
                    && next <= total
                    && (page.cursor >= total || listed > 0)
                    && page.next_cursor == (next < total).then_some(next)
                    // Only preferences carry facts alone, and they disclose only the language.
                    && page.page_kind == "preferences"
                    && total <= 1
                    && page.facts.iter().all(|(path, _)| path == OUTPUT_LANGUAGE_PATH)
            }
        };
    if !shaped {
        return Err(Failure::frame());
    }
    Ok(page)
}

/// The view request, spelled as the product's request model serializes it.
pub(super) fn view_request(profile_id: &str, cursor: u64, pin: Option<&Pin>) -> String {
    let (revision, digest) = match pin {
        Some(pin) => (
            pin.record_revision.to_string(),
            json_string(&pin.content_digest),
        ),
        None => ("null".to_owned(), "null".to_owned()),
    };
    format!(
        "{{\"profile_id\":{},\"page_kind\":\"preferences\",\"cursor\":{cursor},\"limit\":{PROFILE_VIEW_MAX_ITEMS},\"expected_revision\":{revision},\"expected_content_digest\":{digest},\"output_language\":\"es\"}}",
        json_string(profile_id)
    )
}

/// Pins the first page, or refuses a page from another revision.
pub(super) fn next_pin(pin: Option<Pin>, page: &Pin) -> Outcome<Pin> {
    match pin {
        None => Ok(page.clone()),
        Some(pin) if pin == *page => Ok(pin),
        Some(_) => Err(Failure::code("stale_revision")),
    }
}

/// Reads one preferences page as its own registered view operation.
pub(super) fn read_view_page(
    held: &Held,
    contract: &Contract,
    payload: &str,
    cursor: u64,
    deadline: Instant,
) -> Outcome<ViewPage> {
    let subject = held.subject();
    let submitted = submit(held, PROFILE_VIEW, &subject, payload, deadline)?;
    if submitted.secret_requirement.is_some() {
        return Err(Failure::frame());
    }
    let operation_id = submitted.operation_id;
    start(held, &operation_id, deadline)?;
    let projection = await_terminal(
        held,
        &operation_id,
        PROFILE_VIEW_EVENT_PAGE,
        deadline,
        |state| {
            if state.operation_id != operation_id
                || state.definition_id != PROFILE_VIEW
                || state.subject_ref != subject
            {
                return Err(Failure::frame());
            }
            Ok(())
        },
    )?;
    settled(&projection)?;
    let schema = contract
        .result_schema
        .clone()
        .filter(|_| contract.definition_id == PROFILE_VIEW)
        .ok_or_else(Failure::frame)?;
    let reply = held.exchange(
        "operation_result",
        json!({"result": {
            "result_projection_version": 1,
            "operation_id": operation_id,
            "terminal_revision": projection.revision,
            "definition_contract_digest": contract.digest,
            "result_schema": schema,
        }}),
        deadline,
    )?;
    let projected = projected(&reply)?;
    // The product client checks a refused envelope with a strict Python-mode
    // model whose enum code a plain string never satisfies, so it surfaces as
    // a malformed reply rather than as its code.
    if projected.operation_id != operation_id
        || projected.projection_kind != "result"
        || text(&projected.document, "outcome") == Some("refused")
    {
        return Err(Failure::frame());
    }
    let (result_schema, digest, projection) = result_success(&projected.document)?;
    let page = view_page(projection)?;
    if *result_schema != schema || digest != contract.digest {
        return Err(Failure::frame());
    }
    if !same_uuid(&page.profile_id, &held.session.profile_id)
        || page.page_kind != "preferences"
        || page.cursor != cursor
    {
        return Err(Failure::frame());
    }
    if let Some(code) = &page.refusal_code {
        return Err(Failure::code(code));
    }
    Ok(page)
}

pub(super) fn set_language(
    held: &Held,
    language: &str,
    deadline: Instant,
) -> Outcome<ProfileLanguage> {
    let current = read_language(held, deadline)?;
    mutate_language(held, &current, language, deadline)?;
    read_language(held, deadline)
}

pub(super) fn read_language(held: &Held, deadline: Instant) -> Outcome<ProfileLanguage> {
    let deadline = deadline.min(Instant::now() + PROFILE_BUDGET);
    let contract = describe(held, PROFILE_VIEW, deadline)?;
    let mut pin: Option<Pin> = None;
    let mut pages = 0;
    let mut cursor = 0;
    let mut saved: Option<String> = None;
    loop {
        remaining(deadline)?;
        if pages >= PROFILE_VIEW_MAX_PAGES {
            return Err(Failure::Runtime(Refusal::Timeout));
        }
        let payload = view_request(&held.session.profile_id, cursor, pin.as_ref());
        let page = read_view_page(held, &contract, &payload, cursor, deadline)?;
        pin = Some(next_pin(pin, &page.pin)?);
        pages += 1;
        if saved.is_none() {
            saved = page
                .facts
                .iter()
                .find(|(path, _)| path == OUTPUT_LANGUAGE_PATH)
                .map(|(_, value)| value.clone());
        }
        match page.next_cursor {
            None => break,
            Some(next) if next <= cursor => return Err(Failure::frame()),
            Some(next) => cursor = next,
        }
    }
    let pin = pin.ok_or_else(Failure::frame)?;
    if saved
        .as_deref()
        .is_some_and(|language| !OUTPUT_LANGUAGES.contains(&language))
    {
        return Err(Failure::Invalid);
    }
    Ok(ProfileLanguage {
        language: saved,
        record_revision: pin.record_revision,
        content_digest: pin.content_digest,
    })
}

/// Writes the language through the field mutation guarded by `current`'s revision.
pub(super) fn mutate_language(
    held: &Held,
    current: &ProfileLanguage,
    language: &str,
    deadline: Instant,
) -> Outcome<()> {
    let deadline = deadline.min(Instant::now() + PROFILE_BUDGET);
    let contract = describe(held, PROFILE_FIELD_MUTATION, deadline)?;
    let schema = contract
        .result_schema
        .clone()
        .filter(|schema| {
            schema.get("schema_id").and_then(Value::as_str) == Some(PROFILE_FIELD_MUTATION_RESULT)
        })
        .ok_or_else(Failure::frame)?;
    let subject = held.subject();
    let payload = format!(
        "{{\"profile_id\":{},\"expected_revision\":{},\"expected_content_digest\":{},\"path\":{},\"value\":{}}}",
        json_string(&held.session.profile_id),
        current.record_revision,
        json_string(&current.content_digest),
        json_string(OUTPUT_LANGUAGE_PATH),
        json_string(language),
    );
    let submitted = submit(held, &contract.definition_id, &subject, &payload, deadline)?;
    if submitted.secret_requirement.is_some() {
        return Err(Failure::frame());
    }
    let operation_id = submitted.operation_id;
    start(held, &operation_id, deadline)?;
    let projection = await_terminal(
        held,
        &operation_id,
        PROFILE_MUTATION_EVENT_PAGE,
        deadline,
        |state| {
            if state.operation_id != operation_id
                || state.definition_id != contract.definition_id
                || state.subject_ref != subject
                || state.contract.normalized != contract.normalized
            {
                return Err(Failure::frame());
            }
            Ok(())
        },
    )?;
    settled(&projection)?;
    let document = read_result_document(held, &result_request(&projection, &schema), deadline)?;
    if text(&document, "outcome") == Some("refused") {
        let code = refusal_code(&document, "result_projection_version", &RESULT_REFUSALS)?;
        return Err(Failure::code(&code));
    }
    let (result_schema, digest, projection) = result_success(&document)?;
    // Only the field mutation's own projection has exactly these members.
    let keys = ["profile_id", "record_revision"];
    let accepted = projection
        .as_object()
        .filter(|projection| closed(projection, &keys, &keys))
        .ok_or_else(Failure::frame)?;
    let revision = count(accepted, "record_revision")?;
    let profile_id = text(accepted, "profile_id").ok_or_else(Failure::frame)?;
    if *result_schema != schema
        || digest != contract.digest
        || !same_uuid(profile_id, &held.session.profile_id)
        || revision < 1
        || revision < current.record_revision
    {
        return Err(Failure::frame());
    }
    Ok(())
}
