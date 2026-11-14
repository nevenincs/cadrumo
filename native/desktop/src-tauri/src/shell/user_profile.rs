//! Profile presentation over the held person's registered-operation relay.
//! No repository, credential or profile policy lives in the desktop host.
pub(crate) mod censo;
mod election;
mod household;
mod views;
mod wire;
use super::picked_files::{self, Files, Pick, Purpose};
use super::relay::{self, Failure, Result, lock, protocol};
use super::sign_in::{Presence, SignIn};
use crate::agent::person::{HeldPerson, PersonEvent};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::{
    sync::{
        Arc, Mutex,
        atomic::{AtomicBool, Ordering},
    },
    time::Duration,
};
use tauri::{
    State,
    ipc::{Channel, InvokeBody, Request},
};
use wire::{Overview, Pages};
use zeroize::Zeroizing;

// Bound the complete read, including admission, queueing and every page.
// A per-operation timeout alone leaves admission and queue waits unbounded.
const PROFILE_READ_LIMIT: Duration = Duration::from_secs(140);
// Queueing is not submission: refuse an edit promptly if another operation
// owns the relay, without inventing an uncertain mutation outcome.
const PROFILE_CHANGE_ADMISSION_LIMIT: Duration = Duration::from_secs(15);
/// The authentication facts a field edit may name. They are plain profile
/// facts, validated like any other; the sign-in method has its own edit and a
/// secret its own command.
const AUTH_FACT_PATHS: [&str; 3] = ["auth.dni_nie", "auth.numero_soporte", "auth.fecha_validez"];
const AUTH_METHOD: &str = "auth.provider.configure";
const CREDENTIAL_SAVE: &str = "auth.credential.save";
/// One window cue a command family holds: a later subscription replaces the
/// earlier one, and only the subscription held can end it.
#[derive(Default)]
pub(crate) struct Cue(Mutex<Option<(u32, tauri::async_runtime::JoinHandle<()>)>>);
impl Cue {
    /// Holds `updates` in place of the cue held before, sent to by the task
    /// `follow` makes; once the host closed nothing is followed.
    pub(crate) fn observe<F>(
        &self,
        closed: bool,
        updates: Channel<()>,
        follow: impl FnOnce(Channel<()>) -> F,
    ) -> u32
    where
        F: std::future::Future<Output = ()> + Send + 'static,
    {
        let mut held = lock(&self.0);
        if let Some((_, task)) = held.take() {
            task.abort();
        }
        let subscription = updates.id();
        if !closed {
            // Synchronous commands run on the webview thread, outside Tokio.
            // Spawn through the application's runtime rather than a
            // thread-local handle.
            *held = Some((subscription, tauri::async_runtime::spawn(follow(updates))));
        }
        subscription
    }
    /// Ends the cue `subscription`, if it is still the one held.
    pub(crate) fn unobserve(&self, subscription: u32) {
        let mut held = lock(&self.0);
        if held.as_ref().is_some_and(|(id, _)| *id == subscription)
            && let Some((_, task)) = held.take()
        {
            task.abort();
        }
    }
    pub(crate) fn end(&self) {
        if let Some((_, task)) = lock(&self.0).take() {
            task.abort();
        }
    }
    #[cfg(test)]
    pub(crate) fn held(&self) -> Option<u32> {
        lock(&self.0).as_ref().map(|(id, _)| *id)
    }
}

/// The providers whose secret is kept apart from the profile.
const CREDENTIAL_PROVIDERS: [&str; 2] = ["certificate", "clave_permanente"];
/// A credential's JSON-escaped body: the profile, the provider and a password.
const CREDENTIAL_BODY_LIMIT: usize = 8 * 1024;
/// What the dialog's filter calls the certificate file kinds: a format's name.
const CERTIFICATE_KINDS: &str = "PKCS #12";
/// The longest an edit's own members may be, as compact JSON.
const MEMBERS_LIMIT: usize = 10_000;
/// What the baseline names beside an edit's own members, as compact JSON,
/// with room to spare: the profile, the revision and the digest.
const BASELINE_ALLOWANCE: usize = 512;
/// The longest a family replacement's own members may be: the whole family is
/// one request, so it is bounded by the relay's payload and not by the small
/// edits' bound. The product validates every row and fact under the baseline.
const FAMILY_MEMBERS_LIMIT: usize = relay::PAYLOAD_LIMIT - BASELINE_ALLOWANCE;
/// The most people one family replacement may name, as the product bounds it.
const FAMILY_ROWS: usize = 256;
/// The most facts one person may state, as the product bounds it.
const FAMILY_FACTS: usize = 128;
/// The longest a fact's key is, and its value is, as the product bounds them.
const FAMILY_KEY_LIMIT: usize = 128;
const FAMILY_VALUE_LIMIT: usize = 4096;

pub struct ProfileHost {
    sign_in: Arc<SignIn>,
    operation: tokio::sync::Mutex<()>,
    observer: Cue,
    censo_observer: Cue,
    held: Mutex<Option<HeldPerson>>,
    closed: AtomicBool,
    censo: tokio::sync::Mutex<Option<censo::Session>>,
    /// The AEAT sync run, beside the census session it starts.
    aeat_sync: super::aeat_sync::SyncHost,
    /// The certificate files the person picked, for the signed-in session.
    files: Files,
}
impl ProfileHost {
    pub fn new(sign_in: Arc<SignIn>) -> Self {
        Self {
            sign_in,
            operation: tokio::sync::Mutex::new(()),
            observer: Cue::default(),
            censo_observer: Cue::default(),
            held: Mutex::new(None),
            closed: AtomicBool::new(false),
            censo: tokio::sync::Mutex::new(None),
            aeat_sync: super::aeat_sync::SyncHost::default(),
            files: Files::default(),
        }
    }
    /// Refuses every further operation of the window's profile, then waits until the one
    /// already submitted, if any, has its answer or `deadline` passes. Says whether one
    /// was still waiting for its answer then.
    pub async fn settle(&self, deadline: std::time::Instant) -> bool {
        self.closed.store(true, Ordering::Release);
        tokio::time::timeout_at(
            tokio::time::Instant::from_std(deadline),
            self.operation.lock(),
        )
        .await
        .is_err()
    }
    pub fn close(&self) {
        self.closed.store(true, Ordering::Release);
        self.observer.end();
        self.censo_observer.end();
        *lock(&self.held) = None;
        self.aeat_sync.close();
        self.files.clear();
    }
    pub(crate) fn aeat_sync(&self) -> &super::aeat_sync::SyncHost {
        &self.aeat_sync
    }
    /// Every profile operation, and each ledger operation, runs under this
    /// one lock: they share the held person and its relay.
    pub(crate) async fn serial(&self) -> tokio::sync::MutexGuard<'_, ()> {
        self.operation.lock().await
    }
    pub(crate) fn sign_in(&self) -> &Arc<SignIn> {
        &self.sign_in
    }
    pub(crate) fn is_closed(&self) -> bool {
        self.closed.load(Ordering::Acquire)
    }
    /// The held person for the window's signed-in profile, or for exactly
    /// `expected` where one is named.
    pub(crate) async fn person(&self, expected: Option<&str>) -> Result<HeldPerson> {
        if self.closed.load(Ordering::Acquire) {
            return Err(protocol());
        }
        let status = self.sign_in.read_status().await?;
        if status.state != Presence::Present || !status.runtime_ready() {
            *lock(&self.held) = None;
            return Err(Failure::new("not_signed_in"));
        }
        let label = status.active_profile.ok_or_else(protocol)?;
        let owner = self.sign_in.clone();
        let person = super::blocking(move || owner.person(&owner.profile_id(&label)?)).await?;
        if let Some(expected) = expected
            && Self::identity(&person).await?["profile_id"] != expected
        {
            return Err(Failure::new("not_signed_in"));
        }
        let mut held = lock(&self.held);
        if self.closed.load(Ordering::Acquire) {
            return Err(protocol());
        }
        *held = Some(person.clone());
        Ok(person)
    }
    async fn identity(person: &HeldPerson) -> Result<Value> {
        relay::identity(person).await
    }
    async fn call(person: &HeldPerson, request: Value) -> Result<Value> {
        relay::call(person, request).await
    }
    pub(crate) async fn run(
        &self,
        person: &HeldPerson,
        definition: &str,
        payload: Value,
        mutation: bool,
    ) -> Result<Value> {
        let mut events = self.sign_in.person_events();
        let subject = relay::subject(&relay::profile_of(person).await?);
        let operation = relay::submit(person, definition, &subject, payload, mutation)
            .await
            .map_err(code_alone)?;
        settle(
            &mut events,
            person,
            definition,
            subject,
            operation,
            mutation,
        )
        .await
    }
    async fn read(&self, language: String) -> Result<Overview> {
        self.read_with_budget(language, PROFILE_READ_LIMIT).await
    }
    async fn read_with_budget(&self, language: String, budget: Duration) -> Result<Overview> {
        tokio::time::timeout(budget, self.read_overview(language))
            .await
            .unwrap_or_else(|_| Err(protocol()))
    }
    async fn read_overview(&self, language: String) -> Result<Overview> {
        if !super::language::supported(&language) {
            return Err(protocol());
        }
        let _serial = self.operation.lock().await;
        let person = self.person(None).await?;
        let profile = Self::identity(&person).await?["profile_id"]
            .as_str()
            .ok_or_else(protocol)?
            .to_owned();
        let mut pages = Pages::new(profile.clone());
        loop {
            let result = self
                .run(
                    &person,
                    "user-profile.view",
                    pages.request(&language),
                    false,
                )
                .await?;
            if pages.accept(result)? {
                break;
            }
        }
        // Runtime disclosure already checks the exact session. Also reject a
        // result whose window switched accounts while pages were collected.
        let current = self.person(Some(&profile)).await?;
        let identity = Self::identity(&person).await?;
        if Self::identity(&current).await? != identity {
            return Err(Failure::new("not_signed_in"));
        }
        let overview = pages.finish()?;
        Ok(overview)
    }
    async fn change(&self, change: Change) -> Result<()> {
        self.change_with_admission_budget(change, PROFILE_CHANGE_ADMISSION_LIMIT)
            .await
    }
    async fn change_with_admission_budget(&self, change: Change, budget: Duration) -> Result<()> {
        let Change {
            profile_id,
            expected_revision,
            expected_content_digest,
            edit,
        } = change;
        if expected_revision == 0 || !super::setup::wire::is_hex64(&expected_content_digest) {
            return Err(protocol());
        }
        let mut prepared = edit.prepare(&Baseline {
            profile_id: &profile_id,
            revision: expected_revision,
            content_digest: &expected_content_digest,
        })?;
        let (_serial, person) = self.admitted(&profile_id, budget).await?;
        if prepared.certificate.is_some() {
            prepared.resolve(&self.files, &Self::identity(&person).await?)?;
        }
        self.change_on(&person, prepared, &profile_id, expected_revision)
            .await
    }
    /// Submits a prepared edit for the held person's profile. It counts as
    /// saved only where the settled result says so.
    async fn change_on(
        &self,
        person: &HeldPerson,
        prepared: Prepared,
        profile_id: &str,
        expected_revision: u64,
    ) -> Result<()> {
        let result = self
            .run(person, prepared.definition, prepared.payload, true)
            .await?;
        if !prepared
            .confirm
            .holds(&result, profile_id, expected_revision)
        {
            return Err(Failure::new("saved_unread"));
        }
        Ok(())
    }
    /// The serial lock and the held person for exactly `profile`, within
    /// `budget`.
    async fn admitted(
        &self,
        profile: &str,
        budget: Duration,
    ) -> Result<(tokio::sync::MutexGuard<'_, ()>, HeldPerson)> {
        tokio::time::timeout(budget, async {
            let serial = self.operation.lock().await;
            let person = self.person(Some(profile)).await?;
            Ok::<_, Failure>((serial, person))
        })
        .await
        .map_err(|_| protocol())?
    }
    async fn save_credential(&self, credential: Credential) -> Result<()> {
        let (_serial, person) = self
            .admitted(&credential.profile_id, PROFILE_CHANGE_ADMISSION_LIMIT)
            .await?;
        self.save_credential_on(&person, credential).await
    }
    /// Saves one credential for the held person's profile. The password
    /// reaches the runtime only on its secret frame, and a save whose outcome
    /// was not observed is `unknown`, never retried.
    async fn save_credential_on(&self, person: &HeldPerson, credential: Credential) -> Result<()> {
        let profile = relay::profile_of(person).await?;
        if profile != credential.profile_id {
            return Err(Failure::new("not_signed_in"));
        }
        let Credential {
            provider,
            mut secret,
            ..
        } = credential;
        let mut events = self.sign_in.person_events();
        let subject = relay::subject(&profile);
        let operation = relay::submit_secret(
            person,
            CREDENTIAL_SAVE,
            &subject,
            json!({ "provider": provider }),
            std::mem::take(&mut *secret),
        )
        .await
        .map_err(code_alone)?;
        let result = settle(
            &mut events,
            person,
            CREDENTIAL_SAVE,
            subject,
            operation,
            true,
        )
        .await?;
        if result["provider"] != provider || result["saved"] != true {
            return Err(Failure::new("saved_unread"));
        }
        Ok(())
    }
    async fn pick_certificate<R: tauri::Runtime>(
        &self,
        window: tauri::WebviewWindow<R>,
    ) -> Result<Option<Certificate>> {
        let picked = self
            .pick_one(window, Purpose::Certificate, CERTIFICATE_KINDS)
            .await?;
        Ok(picked.map(|picked| Certificate {
            token: picked.token,
            name: picked.name,
        }))
    }
    /// One file of `purpose` picked in the native dialog, as a token for the
    /// signed-in session; none when the dialog closed without a choice.
    pub(crate) async fn pick_one<R: tauri::Runtime>(
        &self,
        window: tauri::WebviewWindow<R>,
        purpose: Purpose,
        kinds: &str,
    ) -> Result<Option<picked_files::Picked>> {
        let identity = Self::identity(&self.person(None).await?).await?;
        let paths = picked_files::choose(window, Pick::File, purpose, kinds.into()).await?;
        // The person may have signed out while the dialog was open.
        if Self::identity(&self.person(None).await?).await? != identity {
            return Err(Failure::new("not_signed_in"));
        }
        self.files.issue_all(&identity, purpose, paths)?.single()
    }
    /// The path behind a token the signed-in session picked for `purpose`.
    pub(crate) async fn picked(
        &self,
        person: &HeldPerson,
        token: &str,
        purpose: Purpose,
    ) -> Result<std::path::PathBuf> {
        let identity = Self::identity(person).await?;
        self.files.path(&identity, token, purpose, false)
    }
}

/// A refusal by its code alone: the profile pages map nothing else.
fn code_alone(mut refused: Failure) -> Failure {
    refused.reason = None;
    refused
}

/// Follows a submitted operation to its terminal receipt and answers its
/// result's projection. A mutation whose outcome could not be observed is
/// `unknown`, and one whose result could not be read is `saved_unread`.
async fn settle(
    events: &mut tokio::sync::broadcast::Receiver<PersonEvent>,
    person: &HeldPerson,
    definition: &str,
    subject: String,
    operation: String,
    mutation: bool,
) -> Result<Value> {
    let relayed = relay::Relayed {
        person,
        operation: operation.clone(),
        definition,
        subject,
    };
    let result = tokio::time::timeout(relay::SETTLE_LIMIT, async {
        let p = relay::follow(events, &relayed, |_| false).await?;
        if p["terminal_condition"] != "succeeded" {
            let mut failed = Failure::new(wire::mutation_failure(&p));
            if failed.code == "refused" {
                // A refusal that settled without effect may carry the
                // sentence the application worded for it; the read is
                // refused when its definition serves none.
                failed.refusal_words = relay::result(&relayed)
                    .await
                    .ok()
                    .and_then(|document| wire::refusal_words(&document["projection"]));
            }
            return Err(failed);
        }
        let document = relay::result(&relayed).await.map_err(|_| {
            Failure::new(if mutation {
                "saved_unread"
            } else {
                "unavailable"
            })
        })?;
        Ok(document["projection"].clone())
    })
    .await
    .unwrap_or_else(|_| {
        Err(Failure::new(if mutation {
            "unknown"
        } else {
            "unavailable"
        }))
    });
    result.map_err(|mut failure| {
        if mutation && failure.code == "unavailable" {
            failure.code = "unknown";
        }
        failure.operation_id = Some(operation);
        failure
    })
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Change {
    profile_id: String,
    expected_revision: u64,
    expected_content_digest: String,
    edit: Edit,
}
#[derive(Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct QuestionAnswer {
    question_id: String,
    value: String,
}
#[derive(Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
enum Edit {
    Field {
        path: String,
        value: String,
    },
    /// A detail stated per ejercicio, answered through its wizard questions so
    /// the answer for one year leaves the others standing.
    EjercicioAnswer {
        values: Vec<QuestionAnswer>,
    },
    AddRow {
        section_key: String,
        values: Vec<RowValue>,
    },
    UpdateRow {
        section_key: String,
        row_key: String,
        values: Vec<RowValue>,
        clear_fields: Vec<String>,
    },
    RemoveRow {
        section_key: String,
        row_key: String,
    },
    Complete,
    /// A change of the stated family, exactly one of: the whole family at once
    /// (`rows`: the product replaces every descendant and the count with
    /// exactly these people, so a person left out is removed), one person to
    /// add to the stored family (`add_row`), or one stored person to remove
    /// (`remove_row_index`, the `row_index` the household page served).
    Descendants {
        #[serde(default)]
        rows: Option<Vec<FamilyRow>>,
        #[serde(default)]
        add_row: Option<FamilyRow>,
        #[serde(default)]
        remove_row_index: Option<String>,
    },
    /// A change of the stated ascendants, as for the descendants: the whole
    /// set, one person to add or one stored person to remove, within the limit
    /// the declaration's design states.
    Ascendants {
        #[serde(default)]
        rows: Option<Vec<FamilyRow>>,
        #[serde(default)]
        add_row: Option<FamilyRow>,
        #[serde(default)]
        remove_row_index: Option<String>,
    },
    /// What one ejercicio's imputation election states: each answer is the
    /// token a served choice carries, an empty token clears the ejercicio's
    /// statement, and an answer left out is left as stated.
    ImputationElection {
        tax_year: u16,
        criterion: Option<String>,
        codigo_comercio_accounting: Option<String>,
    },
    /// The sign-in method with its Cl@ve Móvil route and certificate file:
    /// the one way to change `auth.provider` and `auth.clave_movil_route`.
    /// `certificate` is a token from `profile_aeat_certificate_pick`, never
    /// a path.
    AuthMethod {
        provider: String,
        clave_movil_route: Option<String>,
        certificate: Option<String>,
    },
}
#[derive(Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct RowValue {
    field_key: String,
    value: String,
}
/// One person of a family replacement: the facts it states, each under the
/// key the product's family vocabulary gives it.
#[derive(Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct FamilyRow {
    facts: Vec<FamilyFact>,
}
#[derive(Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct FamilyFact {
    field_key: String,
    value: String,
}
/// Whether `index` is a stored row index as the product writes it, which its
/// removal names: `0`, or a decimal of up to four digits without a leading
/// zero.
fn household_row_index(index: &str) -> bool {
    !index.is_empty()
        && index.len() <= 4
        && index.bytes().all(|byte| byte.is_ascii_digit())
        && (index == "0" || !index.starts_with('0'))
}
impl FamilyRow {
    /// Whether the person is within the product's bounds: some facts, each
    /// under a lower-case key of its token shape and with a bounded value,
    /// no key twice.
    fn bounded(&self) -> bool {
        let token = |key: &str| {
            let mut bytes = key.bytes();
            key.len() <= FAMILY_KEY_LIMIT
                && bytes.next().is_some_and(|first| first.is_ascii_lowercase())
                && bytes
                    .all(|byte| byte.is_ascii_lowercase() || byte.is_ascii_digit() || byte == b'_')
        };
        let keys: std::collections::BTreeSet<&str> = self
            .facts
            .iter()
            .map(|fact| fact.field_key.as_str())
            .collect();
        (1..=FAMILY_FACTS).contains(&self.facts.len())
            && keys.len() == self.facts.len()
            && self.facts.iter().all(|fact| {
                token(&fact.field_key) && (1..=FAMILY_VALUE_LIMIT).contains(&fact.value.len())
            })
    }
}

/// The profile and the revision and content digest of the page an edit was
/// made on.
struct Baseline<'a> {
    profile_id: &'a str,
    revision: u64,
    content_digest: &'a str,
}
impl Baseline<'_> {
    /// A family replacement: `rows` of people under `member`, saved only where
    /// the settled result counts exactly as many.
    fn family(
        &self,
        definition: &'static str,
        member: &str,
        rows: Vec<FamilyRow>,
    ) -> Result<Prepared> {
        if rows.len() > FAMILY_ROWS || !rows.iter().all(FamilyRow::bounded) {
            return Err(Failure::new("refused"));
        }
        let mut members = json!({});
        members[member] = json!(rows);
        if members.to_string().len() > FAMILY_MEMBERS_LIMIT {
            return Err(Failure::new("refused"));
        }
        let people = rows.len();
        self.record_as(definition, members, Confirm::Family(people))
    }
    /// A family change, which states exactly one of `rows` (the whole family
    /// under `member`), `add_row` and `remove_row_index`; any other mix, or
    /// none, is refused.
    fn family_change(
        &self,
        definition: &'static str,
        member: &str,
        change: (Option<Vec<FamilyRow>>, Option<FamilyRow>, Option<String>),
    ) -> Result<Prepared> {
        match change {
            (Some(rows), None, None) => self.family(definition, member, rows),
            (None, Some(row), None) => self.family_addition(definition, &row),
            (None, None, Some(index)) => self.family_removal(definition, &index),
            _ => Err(Failure::new("refused")),
        }
    }
    /// One person added to the stored family, saved only where the settled
    /// result says the family changed and counts at least that person.
    fn family_addition(&self, definition: &'static str, row: &FamilyRow) -> Result<Prepared> {
        if !row.bounded() {
            return Err(Failure::new("refused"));
        }
        let members = json!({"add_row":row});
        if members.to_string().len() > FAMILY_MEMBERS_LIMIT {
            return Err(Failure::new("refused"));
        }
        self.record_as(definition, members, Confirm::FamilyChange { added: true })
    }
    /// One stored person removed from the family, named by the index the
    /// household page served, saved only where the settled result says the
    /// family changed.
    fn family_removal(&self, definition: &'static str, index: &str) -> Result<Prepared> {
        if !household_row_index(index) {
            return Err(Failure::new("refused"));
        }
        self.record_as(
            definition,
            json!({"remove_row_index":index}),
            Confirm::FamilyChange { added: false },
        )
    }
    /// A user-profile operation's request: `members` under the page's
    /// baseline.
    fn record(&self, definition: &'static str, members: Value) -> Result<Prepared> {
        self.record_as(definition, members, Confirm::Record)
    }
    /// As [`Baseline::record`], saved only where the settled result says
    /// `confirm`.
    fn record_as(
        &self,
        definition: &'static str,
        members: Value,
        confirm: Confirm,
    ) -> Result<Prepared> {
        let Value::Object(members) = members else {
            return Err(protocol());
        };
        let mut payload = json!({"profile_id":self.profile_id, "expected_revision":self.revision,
            "expected_content_digest":self.content_digest});
        payload
            .as_object_mut()
            .ok_or_else(protocol)?
            .extend(members);
        Ok(Prepared {
            definition,
            payload,
            certificate: None,
            confirm,
        })
    }
    /// The sign-in method's request. The runtime names the profile by the
    /// operation's subject, and the baseline by its own members.
    fn method(
        &self,
        provider: String,
        route: Option<String>,
        certificate: Option<String>,
    ) -> Prepared {
        let mut payload = json!({"provider":provider, "expected_profile_revision":self.revision,
            "expected_profile_digest":self.content_digest});
        if let Some(route) = route {
            payload["clave_movil_route"] = json!(route);
        }
        Prepared {
            definition: AUTH_METHOD,
            payload,
            certificate,
            confirm: Confirm::Method(provider),
        }
    }
}

/// An edit as the registered operation that makes it.
struct Prepared {
    definition: &'static str,
    payload: Value,
    /// The picked certificate file's token, until [`Prepared::resolve`] puts
    /// its path in the request.
    certificate: Option<String>,
    confirm: Confirm,
}
impl Prepared {
    /// Puts the path behind the certificate token in the request. A token that
    /// is not a certificate this session picked is refused.
    fn resolve(&mut self, files: &Files, identity: &Value) -> Result<()> {
        if let Some(token) = self.certificate.take() {
            let path = files.path(identity, &token, Purpose::Certificate, false)?;
            self.payload["certificate_path"] = picked_files::path_text(&path)?;
        }
        Ok(())
    }
}

/// What a settled result must say for an edit to count as saved.
enum Confirm {
    /// The profile record, at a revision no older than the page's.
    Record,
    /// The profile record, and a family of exactly this many people.
    Family(usize),
    /// The profile record, changed by one person added (which leaves a family
    /// of at least one) or removed from the stored family. The settled result
    /// counts the resulting family, which the host does not know beforehand, so
    /// it is checked to be a count, not a number.
    FamilyChange { added: bool },
    /// The profile record, and the statement of exactly this ejercicio.
    Election(u16),
    /// The sign-in method configured, as the product reports it.
    Method(String),
}
/// Whether a settled result names the profile record at a revision no older
/// than the page's.
fn saved(result: &Value, expected_revision: u64) -> bool {
    result["record_revision"]
        .as_u64()
        .is_some_and(|revision| revision >= expected_revision)
}

impl Confirm {
    fn holds(&self, result: &Value, profile_id: &str, expected_revision: u64) -> bool {
        result["profile_id"] == profile_id
            && match self {
                Self::Record => saved(result, expected_revision),
                Self::Family(people) => {
                    saved(result, expected_revision) && result["total"] == *people
                }
                Self::FamilyChange { added } => {
                    saved(result, expected_revision)
                        && result["changed"] == true
                        && result["total"]
                            .as_u64()
                            .is_some_and(|total| !*added || total >= 1)
                }
                Self::Election(year) => {
                    saved(result, expected_revision) && result["tax_year"] == *year
                }
                Self::Method(provider) => {
                    result["provider"] == *provider
                        && ["changed", "certificate_file_provided", "complete"]
                            .iter()
                            .all(|flag| result[*flag].is_boolean())
                        && (result["result_version"].is_null() || result["result_version"] == 2)
                }
            }
    }
}

impl Edit {
    /// The registered operation this edit is. The product validates every
    /// path, value and row under the baseline; the host refuses only what has
    /// a command of its own: the sign-in method and the secrets.
    fn prepare(self, baseline: &Baseline) -> Result<Prepared> {
        let (definition, members) = match self {
            Self::Field { path, value }
                if (!path.starts_with("auth.") || AUTH_FACT_PATHS.contains(&path.as_str()))
                    && value.len() <= 4096 =>
            {
                (
                    "user-profile.field-mutation",
                    json!({"path":path,"value":value}),
                )
            }
            Self::EjercicioAnswer { values } if values.len() == 2 => {
                ("user-profile.patch", json!({"values":values}))
            }
            Self::AddRow {
                section_key,
                values,
            } if section_key != "auth" => (
                "user-profile.repeatable-row-mutation",
                json!({"section_key":section_key,"values":values}),
            ),
            Self::UpdateRow {
                section_key,
                row_key,
                values,
                clear_fields,
            } if section_key != "auth" => (
                "user-profile.repeatable-row-update",
                json!({"section_key":section_key,"row_key":row_key,"values":values,"clear_fields":clear_fields}),
            ),
            Self::RemoveRow {
                section_key,
                row_key,
            } if section_key != "auth" => (
                "user-profile.repeatable-row-remove",
                json!({"section_key":section_key,"row_key":row_key}),
            ),
            Self::Complete => ("user-profile.complete-setup", json!({})),
            Self::Descendants {
                rows,
                add_row,
                remove_row_index,
            } => {
                return baseline.family_change(
                    "user-profile.descendants",
                    "descendants",
                    (rows, add_row, remove_row_index),
                );
            }
            Self::Ascendants {
                rows,
                add_row,
                remove_row_index,
            } => {
                return baseline.family_change(
                    "user-profile.ascendants",
                    "ascendants",
                    (rows, add_row, remove_row_index),
                );
            }
            Self::ImputationElection {
                tax_year,
                criterion,
                codigo_comercio_accounting,
            } => {
                let bounded = |answer: &Option<String>, limit: usize| {
                    answer.as_ref().is_none_or(|token| token.len() <= limit)
                };
                if (criterion.is_none() && codigo_comercio_accounting.is_none())
                    || !bounded(&criterion, 64)
                    || !bounded(&codigo_comercio_accounting, 16)
                {
                    return Err(Failure::new("refused"));
                }
                let mut members = json!({"tax_year":tax_year});
                if let Some(criterion) = criterion {
                    members["criterion"] = json!(criterion);
                }
                if let Some(accounting) = codigo_comercio_accounting {
                    members["codigo_comercio_accounting"] = json!(accounting);
                }
                return baseline.record_as(
                    "user-profile.imputation-election.set",
                    members,
                    Confirm::Election(tax_year),
                );
            }
            Self::AuthMethod {
                provider,
                clave_movil_route,
                certificate,
            } => {
                let size = provider.len() + clave_movil_route.as_deref().map_or(0, str::len);
                if size > MEMBERS_LIMIT {
                    return Err(Failure::new("refused"));
                }
                return Ok(baseline.method(provider, clave_movil_route, certificate));
            }
            _ => return Err(Failure::new("refused")),
        };
        if members.to_string().len() > MEMBERS_LIMIT {
            return Err(Failure::new("refused"));
        }
        baseline.record(definition, members)
    }
}

/// The certificate file the person picked, as the window sees it: a token the
/// host resolves, and the file's name. The path never reaches the window.
#[derive(Debug, Serialize)]
pub struct Certificate {
    token: String,
    name: String,
}

/// One credential save, read from its raw body. The password is held only as
/// the exact text of the runtime's secret frame, which is overwritten when
/// this is dropped.
struct Credential {
    profile_id: String,
    provider: &'static str,
    secret: Zeroizing<String>,
}
/// Says that a credential is there, never what it holds.
impl std::fmt::Debug for Credential {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        formatter
            .debug_struct("Credential")
            .field("profile_id", &self.profile_id)
            .field("provider", &self.provider)
            .finish_non_exhaustive()
    }
}

/// The credential a raw body carries: exactly the profile, one of the
/// providers that keep a secret and a non-empty password, within the bound.
fn credential(body: &InvokeBody) -> Result<Credential> {
    #[derive(Serialize)]
    struct Frame<'a> {
        password: &'a str,
    }
    let invalid = || Failure::new("invalid");
    let read = relay::wiped_body(body, CREDENTIAL_BODY_LIMIT)?;
    let fields = read.0.as_object().ok_or_else(invalid)?;
    let text = |name: &str| fields.get(name).and_then(Value::as_str).ok_or_else(invalid);
    let (profile_id, named, password) = (text("profile_id")?, text("provider")?, text("password")?);
    let provider = CREDENTIAL_PROVIDERS
        .into_iter()
        .find(|known| *known == named)
        .ok_or_else(invalid)?;
    if fields.len() != 3 || password.is_empty() {
        return Err(invalid());
    }
    // Escaping at most sextuples a character, so the buffer never grows and
    // leaves an unwiped copy behind.
    let mut frame = Zeroizing::new(Vec::with_capacity(password.len() * 6 + 16));
    serde_json::to_writer(&mut *frame, &Frame { password }).map_err(|_| invalid())?;
    let secret = String::from_utf8(std::mem::take(&mut *frame)).map_err(|refused| {
        drop(Zeroizing::new(refused.into_bytes()));
        invalid()
    })?;
    Ok(Credential {
        profile_id: profile_id.to_owned(),
        provider,
        secret: Zeroizing::new(secret),
    })
}

#[tauri::command]
async fn user_profile_read(
    host: State<'_, Arc<ProfileHost>>,
    language: String,
) -> Result<Overview> {
    host.read(language).await
}
/// The household the profile states: each group of people with the leaves
/// its rows can state and the rows stored, in the product's words, at one
/// profile revision.
#[tauri::command]
async fn user_profile_household(
    host: State<'_, Arc<ProfileHost>>,
    language: String,
) -> Result<household::Household> {
    host.household(language).await
}
/// Which leaves one unsaved household row is asked, as the product resolves
/// them from the answers typed so far. Nothing is stored.
#[tauri::command]
async fn user_profile_household_draft(
    host: State<'_, Arc<ProfileHost>>,
    language: String,
    draft: household::Draft,
) -> Result<household::DraftAsks> {
    host.household_draft(language, draft).await
}
/// What `profile` states for the imputation election of `tax_year`, with the
/// setup wizard's own questions and words in `language`.
#[tauri::command]
async fn user_profile_imputation_election(
    host: State<'_, Arc<ProfileHost>>,
    profile: String,
    tax_year: u16,
    language: String,
) -> Result<election::Election> {
    host.imputation_election(profile, tax_year, language).await
}
#[tauri::command]
async fn user_profile_change(host: State<'_, Arc<ProfileHost>>, change: Change) -> Result<()> {
    host.change(change).await
}
/// Opens the native dialog for the AEAT electronic certificate (a PKCS #12
/// file) and answers a token and the file's name, or nothing where the dialog
/// is closed without a pick. The token names the file in an `auth_method`
/// edit of the same session; the path stays in the host.
#[tauri::command]
async fn profile_aeat_certificate_pick<R: tauri::Runtime>(
    host: State<'_, Arc<ProfileHost>>,
    window: tauri::WebviewWindow<R>,
) -> Result<Option<Certificate>> {
    host.pick_certificate(window).await
}
/// Saves a certificate passphrase or a Cl@ve permanente password for the
/// window's signed-in profile, from the raw body: a JSON object of exactly
/// `profile_id`, `provider` and `password`. The password reaches the runtime
/// only on its secret frame and is overwritten once sent. One attempt:
/// nothing is retried, and a save whose outcome was not observed is `unknown`.
#[tauri::command]
async fn profile_aeat_credential_save(
    host: State<'_, Arc<ProfileHost>>,
    request: Request<'_>,
) -> Result<()> {
    let credential = credential(request.body())?;
    host.save_credential(credential).await
}
#[tauri::command]
async fn profile_views_notifications(
    host: State<'_, Arc<ProfileHost>>,
) -> Result<views::NotificationsSummary> {
    host.notifications().await
}
#[tauri::command]
async fn profile_views_calendar(
    host: State<'_, Arc<ProfileHost>>,
    from: String,
    to: String,
    language: String,
) -> Result<views::FilingCalendar> {
    host.filing_calendar(from, to, language).await
}
#[tauri::command]
async fn profile_views_record_groups(
    host: State<'_, Arc<ProfileHost>>,
    request: Value,
) -> Result<Value> {
    host.record_groups(request).await
}
#[tauri::command]
fn user_profile_observe(host: State<'_, Arc<ProfileHost>>, updates: Channel<()>) -> u32 {
    let owner = host.sign_in.clone();
    let mut events = owner.person_events();
    host.observer.observe(host.is_closed(), updates, |updates| async move {
        loop {
            tokio::select! {
                () = owner.observation_changed() => {},
                event = events.recv() => match event {
                    Ok(PersonEvent::RecordsChanged | PersonEvent::LanguageChanged | PersonEvent::Retired) |
                    Err(tokio::sync::broadcast::error::RecvError::Lagged(_)) => {},
                    Err(tokio::sync::broadcast::error::RecvError::Closed) => break,
                    _ => continue,
                }
            }
            if updates.send(()).is_err() {
                break;
            }
        }
    })
}
#[tauri::command]
fn user_profile_unobserve(host: State<'_, Arc<ProfileHost>>, subscription: u32) {
    host.observer.unobserve(subscription);
}
pub fn commands<R: tauri::Runtime>() -> crate::app::Commands<R> {
    crate::app::commands![
        user_profile_read,
        user_profile_household,
        user_profile_household_draft,
        user_profile_imputation_election,
        user_profile_change,
        user_profile_observe,
        user_profile_unobserve,
        profile_aeat_certificate_pick,
        profile_aeat_credential_save,
        profile_views_notifications,
        profile_views_calendar,
        profile_views_record_groups
    ]
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn a_queued_profile_change_expires_before_submission() {
        let host = ProfileHost::new(Arc::new(
            SignIn::new(&crate::terminal::tests::unit_launch()),
        ));
        let serial = host.operation.lock().await;
        let change = Change {
            profile_id: "profile".into(),
            expected_revision: 1,
            expected_content_digest: "a".repeat(64),
            edit: Edit::Field {
                path: "identity.email".into(),
                value: "person@example.com".into(),
            },
        };
        let result = host
            .change_with_admission_budget(change, Duration::from_millis(1))
            .await;
        let failure = result.unwrap_err();
        assert_eq!(failure.code, "unavailable");
        assert!(failure.operation_id.is_none());
        drop(serial);
        assert!(host.operation.try_lock().is_ok());
        host.close();
    }

    #[tokio::test]
    async fn a_queued_profile_read_expires_without_waiting_for_the_previous_operation() {
        let host = ProfileHost::new(Arc::new(
            SignIn::new(&crate::terminal::tests::unit_launch()),
        ));
        let serial = host.operation.lock().await;
        let result = host
            .read_with_budget("en".into(), Duration::from_millis(1))
            .await;
        assert!(matches!(
            result,
            Err(Failure {
                code: "unavailable",
                ..
            })
        ));
        drop(serial);
        assert!(host.operation.try_lock().is_ok());
        host.close();
    }

    #[test]
    fn profile_observation_from_the_webview_thread_owns_and_replaces_its_task() {
        use tauri::{
            WebviewWindowBuilder,
            ipc::{CallbackFn, InvokeBody},
            test::{INVOKE_KEY, get_ipc_response, mock_builder, mock_context, noop_assets},
            webview::InvokeRequest,
        };

        // No #[tokio::test] or entered handle: that hid the main-thread panic.
        assert!(tokio::runtime::Handle::try_current().is_err());
        let host = Arc::new(ProfileHost::new(Arc::new(SignIn::new(
            &crate::terminal::tests::unit_launch(),
        ))));
        let app = mock_builder()
            .manage(host.clone())
            .invoke_handler(tauri::generate_handler![
                user_profile_observe,
                user_profile_unobserve
            ])
            .build(mock_context(noop_assets()))
            .unwrap();
        let window = WebviewWindowBuilder::new(&app, "main", Default::default())
            .build()
            .unwrap();
        let invoke = |cmd: &str, body: Value| {
            get_ipc_response(
                &window,
                InvokeRequest {
                    cmd: cmd.into(),
                    callback: CallbackFn(0),
                    error: CallbackFn(1),
                    url: if cfg!(windows) {
                        "http://tauri.localhost"
                    } else {
                        "tauri://localhost"
                    }
                    .parse()
                    .unwrap(),
                    body: InvokeBody::Json(body),
                    headers: Default::default(),
                    invoke_key: INVOKE_KEY.to_owned(),
                },
            )
            .unwrap()
            .deserialize::<Value>()
            .unwrap()
        };
        let first = invoke("user_profile_observe", json!({"updates":"__CHANNEL__:7"}));
        assert_eq!(first, 7);
        let second = invoke("user_profile_observe", json!({"updates":"__CHANNEL__:8"}));
        assert_eq!(second, 8);
        invoke("user_profile_unobserve", json!({"subscription":first}));
        assert_eq!(host.observer.held(), Some(8));
        invoke("user_profile_unobserve", json!({"subscription":second}));
        assert_eq!(host.observer.held(), None);
        invoke("user_profile_observe", json!({"updates":"__CHANNEL__:9"}));
        host.close();
        assert_eq!(host.observer.held(), None);
        invoke("user_profile_observe", json!({"updates":"__CHANNEL__:10"}));
        assert_eq!(host.observer.held(), None);
    }

    const PROFILE_ID: &str = "11111111-1111-4111-8111-111111111111";

    #[cfg(windows)]
    fn host() -> ProfileHost {
        ProfileHost::new(Arc::new(
            SignIn::new(&crate::terminal::tests::unit_launch()),
        ))
    }
    fn prepared(edit: Value) -> Result<Prepared> {
        let digest = "a".repeat(64);
        serde_json::from_value::<Edit>(edit)
            .unwrap()
            .prepare(&Baseline {
                profile_id: PROFILE_ID,
                revision: 3,
                content_digest: &digest,
            })
    }
    fn refusal(edit: Value) -> &'static str {
        prepared(edit).err().expect("the edit is refused").code
    }

    #[test]
    fn a_field_edit_names_an_authentication_fact_but_never_the_method_or_a_secret() {
        let digest = "a".repeat(64);
        for path in AUTH_FACT_PATHS.into_iter().chain(["identity.name"]) {
            let request = prepared(json!({"kind":"field","path":path,"value":"x"})).unwrap();
            assert_eq!(request.definition, "user-profile.field-mutation");
            assert_eq!(
                request.payload,
                json!({"profile_id":PROFILE_ID,"expected_revision":3,
                    "expected_content_digest":digest,"path":path,"value":"x"})
            );
            assert!(request.certificate.is_none());
        }
        for path in [
            "auth.provider",
            "auth.clave_movil_route",
            "auth.clave.password",
            "auth.password",
            "auth.dni_nie.extra",
            "auth.dni_nie ",
            "auth.",
        ] {
            assert_eq!(
                refusal(json!({"kind":"field","path":path,"value":"x"})),
                "refused",
                "{path}"
            );
        }
        for path in ["auth.dni_nie", "identity.name"] {
            assert_eq!(
                refusal(json!({"kind":"field","path":path,"value":"a".repeat(4097)})),
                "refused"
            );
        }
    }

    #[test]
    fn a_detail_stated_per_ejercicio_is_answered_through_its_two_questions() {
        let digest = "a".repeat(64);
        let values = json!([
            {"question_id":"criterion","value":"devengo"},
            {"question_id":"year","value":"2024"}
        ]);
        let request = prepared(json!({"kind":"ejercicio_answer","values":values})).unwrap();
        assert_eq!(request.definition, "user-profile.patch");
        assert_eq!(
            request.payload,
            json!({"profile_id":PROFILE_ID,"expected_revision":3,
                "expected_content_digest":digest,"values":values})
        );
        assert_eq!(
            refusal(json!({"kind":"ejercicio_answer",
                "values":[{"question_id":"criterion","value":"devengo"}]})),
            "refused"
        );
    }

    fn people(count: usize) -> Value {
        Value::Array(
            (0..count)
                .map(|_| json!({"facts":[{"field_key":"nombre","value":"Ana"}]}))
                .collect(),
        )
    }

    #[test]
    fn a_family_is_replaced_whole_under_its_baseline_and_saved_only_when_counted() {
        let digest = "a".repeat(64);
        let rows = json!([
            {"facts":[{"field_key":"fecha_nacimiento","value":"2020-05-01"},
                {"field_key":"discapacidad_grado","value":"0"}]},
            {"facts":[{"field_key":"fecha_nacimiento","value":"2022-01-09"}]}
        ]);
        let request = prepared(json!({"kind":"descendants","rows":rows})).unwrap();
        assert_eq!(request.definition, "user-profile.descendants");
        assert_eq!(
            request.payload,
            json!({"profile_id":PROFILE_ID,"expected_revision":3,
                "expected_content_digest":digest,"descendants":rows})
        );
        let settled = json!({"profile_id":PROFILE_ID,"record_revision":4,"total":2,"changed":true});
        assert!(request.confirm.holds(&settled, PROFILE_ID, 3));
        for unread in [
            json!({"profile_id":PROFILE_ID,"record_revision":4,"total":1}),
            json!({"profile_id":PROFILE_ID,"record_revision":4}),
            json!({"profile_id":PROFILE_ID,"record_revision":2,"total":2}),
            json!({"profile_id":"another","record_revision":4,"total":2}),
        ] {
            assert!(!request.confirm.holds(&unread, PROFILE_ID, 3), "{unread}");
        }
        // No people at all is a stated family of none, not a refusal.
        let none = prepared(json!({"kind":"descendants","rows":[]})).unwrap();
        assert_eq!(none.payload["descendants"], json!([]));
        assert!(none.confirm.holds(
            &json!({"profile_id":PROFILE_ID,"record_revision":3,"total":0}),
            PROFILE_ID,
            3
        ));
    }

    #[test]
    fn a_family_beyond_the_products_bounds_is_refused_before_it_is_submitted() {
        assert!(prepared(json!({"kind":"descendants","rows":people(FAMILY_ROWS)})).is_ok());
        let fact = |key: &str, value: &str| json!({"field_key":key,"value":value});
        for rows in [
            people(FAMILY_ROWS + 1),
            json!([{"facts":[]}]),
            json!([{"facts":[fact("nombre","")]}]),
            json!([{"facts":[fact("nombre",&"a".repeat(FAMILY_VALUE_LIMIT + 1))]}]),
            json!([{"facts":[fact("Nombre","x")]}]),
            json!([{"facts":[fact("1nombre","x")]}]),
            json!([{"facts":[fact("nombre-x","x")]}]),
            json!([{"facts":[fact("","x")]}]),
            json!([{"facts":[fact(&format!("a{}", "b".repeat(FAMILY_KEY_LIMIT)),"x")]}]),
            json!([{"facts":[fact("nombre","x"),fact("nombre","y")]}]),
            json!([{"facts":(0..=FAMILY_FACTS).map(|n| fact(&format!("k{n}"),"x")).collect::<Vec<_>>()}]),
        ] {
            assert_eq!(
                refusal(json!({"kind":"descendants","rows":rows.clone()})),
                "refused",
                "{rows:.80}"
            );
        }
        // A family that fits no request is the window's to make smaller, and the
        // bound is the relay's payload, which the small edits' bound is not.
        let full = json!({"facts":(0..FAMILY_FACTS)
            .map(|n| json!({"field_key":format!("k{n}"),"value":"a".repeat(FAMILY_VALUE_LIMIT)}))
            .collect::<Vec<_>>()});
        let needed = FAMILY_MEMBERS_LIMIT / full.to_string().len() + 1;
        assert!((3..=FAMILY_ROWS).contains(&needed), "{needed}");
        assert_eq!(
            refusal(json!({"kind":"descendants","rows":vec![full.clone(); needed]})),
            "refused"
        );
        let fits = prepared(json!({"kind":"descendants","rows":vec![full; needed - 2]}));
        assert!(fits.is_ok());
        const {
            assert!(FAMILY_MEMBERS_LIMIT > MEMBERS_LIMIT);
        }
        for edit in [
            json!({"kind":"descendants","rows":[],"extra":1}),
            json!({"kind":"descendants","rows":[{"facts":[],"extra":1}]}),
            json!({"kind":"descendants","rows":[{"facts":[{"field_key":"nombre","value":"x","masked":false}]}]}),
            json!({"kind":"descendants","rows":null,"add_row":{"facts":[],"extra":1}}),
            json!({"kind":"descendants","add_row":{"facts":[{"field_key":"nombre","value":"x","masked":false}]}}),
            json!({"kind":"descendants","remove_row_index":0}),
            json!({"kind":"descendants","remove_row":"0"}),
        ] {
            assert!(serde_json::from_value::<Edit>(edit).is_err());
        }
        // A change that states nothing decodes and is refused by the host.
        assert_eq!(refusal(json!({"kind":"descendants"})), "refused");
    }

    #[test]
    fn ascendants_are_replaced_whole_under_their_own_operation_and_saved_only_when_counted() {
        let digest = "a".repeat(64);
        let rows = json!([
            {"facts":[{"field_key":"nif","value":"12345678Z"},
                {"field_key":"birth_date","value":"1948-03-04"},
                {"field_key":"convivientes","value":"2"}]},
            {"facts":[{"field_key":"birth_date","value":"1951-11-30"}]}
        ]);
        let request = prepared(json!({"kind":"ascendants","rows":rows})).unwrap();
        assert_eq!(request.definition, "user-profile.ascendants");
        assert_eq!(
            request.payload,
            json!({"profile_id":PROFILE_ID,"expected_revision":3,
                "expected_content_digest":digest,"ascendants":rows})
        );
        let settled = json!({"profile_id":PROFILE_ID,"record_revision":4,"total":2,"changed":true});
        assert!(request.confirm.holds(&settled, PROFILE_ID, 3));
        for unread in [
            json!({"profile_id":PROFILE_ID,"record_revision":4,"total":1}),
            json!({"profile_id":PROFILE_ID,"record_revision":4}),
            json!({"profile_id":PROFILE_ID,"record_revision":2,"total":2}),
            json!({"profile_id":"another","record_revision":4,"total":2}),
        ] {
            assert!(!request.confirm.holds(&unread, PROFILE_ID, 3), "{unread}");
        }
        // No ascendants at all is a stated zero, not a refusal.
        let none = prepared(json!({"kind":"ascendants","rows":[]})).unwrap();
        assert_eq!(none.definition, "user-profile.ascendants");
        assert_eq!(none.payload["ascendants"], json!([]));
        assert!(none.payload.get("descendants").is_none());
        assert!(none.confirm.holds(
            &json!({"profile_id":PROFILE_ID,"record_revision":3,"total":0}),
            PROFILE_ID,
            3
        ));
    }

    #[test]
    fn ascendants_beyond_the_products_bounds_are_refused_before_they_are_submitted() {
        assert!(prepared(json!({"kind":"ascendants","rows":people(FAMILY_ROWS)})).is_ok());
        let fact = |key: &str, value: &str| json!({"field_key":key,"value":value});
        for rows in [
            people(FAMILY_ROWS + 1),
            json!([{"facts":[]}]),
            json!([{"facts":[fact("birth_date","")]}]),
            json!([{"facts":[fact("birth_date",&"a".repeat(FAMILY_VALUE_LIMIT + 1))]}]),
            json!([{"facts":[fact("Birth_date","x")]}]),
            json!([{"facts":[fact("birth-date","x")]}]),
            json!([{"facts":[fact("birth_date","x"),fact("birth_date","y")]}]),
        ] {
            assert_eq!(
                refusal(json!({"kind":"ascendants","rows":rows.clone()})),
                "refused",
                "{rows:.80}"
            );
        }
        // The two replacements never answer to each other's member.
        for edit in [
            json!({"kind":"ascendants","rows":[],"extra":1}),
            json!({"kind":"ascendants","rows":[{"facts":[],"extra":1}]}),
            json!({"kind":"ascendants","rows":[{"facts":[{"field_key":"nif","value":"x","masked":false}]}]}),
            json!({"kind":"ascendants","ascendants":[]}),
            json!({"kind":"ascendants","add_row":{"facts":[],"extra":1}}),
            json!({"kind":"ascendants","remove_row_index":0}),
        ] {
            assert!(serde_json::from_value::<Edit>(edit).is_err());
        }
        // A change that states nothing decodes and is refused by the host.
        assert_eq!(refusal(json!({"kind":"ascendants"})), "refused");
    }

    fn person(key: &str, value: &str) -> Value {
        json!({"facts":[{"field_key":key,"value":value}]})
    }

    #[test]
    fn one_person_added_to_a_family_is_its_own_member_and_saved_only_when_it_changed_the_family() {
        let digest = "a".repeat(64);
        for (kind, definition) in [
            ("descendants", "user-profile.descendants"),
            ("ascendants", "user-profile.ascendants"),
        ] {
            let row = json!({"facts":[{"field_key":"fecha_nacimiento","value":"2020-05-01"},
                {"field_key":"discapacidad_grado","value":"0"}]});
            let request = prepared(json!({"kind":kind,"add_row":row})).unwrap();
            assert_eq!(request.definition, definition);
            assert_eq!(
                request.payload,
                json!({"profile_id":PROFILE_ID,"expected_revision":3,
                    "expected_content_digest":digest,"add_row":row})
            );
            assert!(request.certificate.is_none());
            let settled =
                json!({"profile_id":PROFILE_ID,"record_revision":4,"total":1,"changed":true});
            assert!(request.confirm.holds(&settled, PROFILE_ID, 3));
            let grown =
                json!({"profile_id":PROFILE_ID,"record_revision":4,"total":7,"changed":true});
            assert!(request.confirm.holds(&grown, PROFILE_ID, 3));
            for unread in [
                json!({"profile_id":PROFILE_ID,"record_revision":4,"total":0,"changed":true}),
                json!({"profile_id":PROFILE_ID,"record_revision":4,"total":1,"changed":false}),
                json!({"profile_id":PROFILE_ID,"record_revision":4,"total":1}),
                json!({"profile_id":PROFILE_ID,"record_revision":4,"changed":true}),
                json!({"profile_id":PROFILE_ID,"record_revision":4,"total":"1","changed":true}),
                json!({"profile_id":PROFILE_ID,"record_revision":2,"total":1,"changed":true}),
                json!({"profile_id":"another","record_revision":4,"total":1,"changed":true}),
            ] {
                assert!(!request.confirm.holds(&unread, PROFILE_ID, 3), "{unread}");
            }
        }
    }

    #[test]
    fn one_stored_person_removed_from_a_family_is_named_by_the_index_the_page_served() {
        let digest = "a".repeat(64);
        for (kind, definition) in [
            ("descendants", "user-profile.descendants"),
            ("ascendants", "user-profile.ascendants"),
        ] {
            for index in ["0", "3", "10", "9999"] {
                let request = prepared(json!({"kind":kind,"remove_row_index":index})).unwrap();
                assert_eq!(request.definition, definition);
                assert_eq!(
                    request.payload,
                    json!({"profile_id":PROFILE_ID,"expected_revision":3,
                        "expected_content_digest":digest,"remove_row_index":index})
                );
            }
            let request = prepared(json!({"kind":kind,"remove_row_index":"0"})).unwrap();
            // Removing the last person leaves a family of none, which is still a saved change.
            for total in [0, 1, 5] {
                let settled = json!({"profile_id":PROFILE_ID,"record_revision":4,
                    "total":total,"changed":true});
                assert!(request.confirm.holds(&settled, PROFILE_ID, 3), "{total}");
            }
            for unread in [
                json!({"profile_id":PROFILE_ID,"record_revision":4,"total":1,"changed":false}),
                json!({"profile_id":PROFILE_ID,"record_revision":4,"total":1}),
                json!({"profile_id":PROFILE_ID,"record_revision":4,"changed":true}),
                json!({"profile_id":PROFILE_ID,"record_revision":4,"total":-1,"changed":true}),
                json!({"profile_id":PROFILE_ID,"record_revision":2,"total":1,"changed":true}),
                json!({"profile_id":"another","record_revision":4,"total":1,"changed":true}),
            ] {
                assert!(!request.confirm.holds(&unread, PROFILE_ID, 3), "{unread}");
            }
        }
    }

    #[test]
    fn a_family_change_states_exactly_one_of_the_set_one_person_to_add_or_one_to_remove() {
        for kind in ["descendants", "ascendants"] {
            let row = person("nombre", "Ana");
            let rows = json!([row.clone()]);
            for edit in [
                json!({"kind":kind}),
                json!({"kind":kind,"rows":null,"add_row":null,"remove_row_index":null}),
                json!({"kind":kind,"rows":rows,"add_row":row}),
                json!({"kind":kind,"rows":rows,"remove_row_index":"0"}),
                json!({"kind":kind,"add_row":row,"remove_row_index":"0"}),
                json!({"kind":kind,"rows":rows,"add_row":row,"remove_row_index":"0"}),
                json!({"kind":kind,"rows":[],"remove_row_index":"0"}),
            ] {
                assert_eq!(refusal(edit.clone()), "refused", "{edit}");
            }
            // Each statement alone is taken, an empty set included, and a null is no statement.
            for edit in [
                json!({"kind":kind,"rows":rows}),
                json!({"kind":kind,"rows":[]}),
                json!({"kind":kind,"add_row":row}),
                json!({"kind":kind,"remove_row_index":"2"}),
                json!({"kind":kind,"rows":null,"add_row":row,"remove_row_index":null}),
                json!({"kind":kind,"rows":null,"add_row":null,"remove_row_index":"2"}),
            ] {
                assert!(prepared(edit.clone()).is_ok(), "{edit}");
            }
        }
    }

    #[test]
    fn a_person_to_add_or_an_index_to_remove_beyond_the_products_bounds_is_refused() {
        let fact = |key: &str, value: &str| json!({"field_key":key,"value":value});
        for kind in ["descendants", "ascendants"] {
            for row in [
                json!({"facts":[]}),
                json!({"facts":[fact("nombre","")]}),
                json!({"facts":[fact("nombre",&"a".repeat(FAMILY_VALUE_LIMIT + 1))]}),
                json!({"facts":[fact("Nombre","x")]}),
                json!({"facts":[fact("1nombre","x")]}),
                json!({"facts":[fact("nombre","x"),fact("nombre","y")]}),
                json!({"facts":(0..=FAMILY_FACTS).map(|n| fact(&format!("k{n}"),"x")).collect::<Vec<_>>()}),
            ] {
                assert_eq!(
                    refusal(json!({"kind":kind,"add_row":row.clone()})),
                    "refused",
                    "{row:.80}"
                );
            }
            for index in [
                "", "00", "01", "-1", "+1", "1.0", "a", " 1", "1 ", "1\n", "10000", "99999", "١",
                "0x1",
            ] {
                assert_eq!(
                    refusal(json!({"kind":kind,"remove_row_index":index})),
                    "refused",
                    "{index:?}"
                );
            }
        }
        // The index is the served text, never a number.
        assert!(
            serde_json::from_value::<Edit>(json!({"kind":"descendants","remove_row_index":1}))
                .is_err()
        );
        // One person is bounded like the relay's payload, as a whole family is.
        let full = json!({"facts":(0..FAMILY_FACTS)
            .map(|n| json!({"field_key":format!("k{n}"),"value":"a".repeat(FAMILY_VALUE_LIMIT)}))
            .collect::<Vec<_>>()});
        assert!(full.to_string().len() < FAMILY_MEMBERS_LIMIT);
        assert!(prepared(json!({"kind":"descendants","add_row":full})).is_ok());
    }

    #[test]
    fn an_election_names_its_ejercicio_and_only_the_answers_it_changes() {
        let digest = "a".repeat(64);
        let both = prepared(json!({"kind":"imputation_election","tax_year":2025,
            "criterion":"devengo","codigo_comercio_accounting":"yes"}))
        .unwrap();
        assert_eq!(both.definition, "user-profile.imputation-election.set");
        assert_eq!(
            both.payload,
            json!({"profile_id":PROFILE_ID,"expected_revision":3,"expected_content_digest":digest,
                "tax_year":2025,"criterion":"devengo","codigo_comercio_accounting":"yes"})
        );
        // A left-out answer stays as stated, and an empty token clears.
        let one = prepared(json!({"kind":"imputation_election","tax_year":2025,
            "criterion":null,"codigo_comercio_accounting":""}))
        .unwrap();
        assert!(one.payload.get("criterion").is_none());
        assert_eq!(one.payload["codigo_comercio_accounting"], "");
        let settled =
            json!({"profile_id":PROFILE_ID,"record_revision":4,"tax_year":2025,"changed":true});
        assert!(both.confirm.holds(&settled, PROFILE_ID, 3));
        for unread in [
            json!({"profile_id":PROFILE_ID,"record_revision":4,"tax_year":2024}),
            json!({"profile_id":PROFILE_ID,"record_revision":4}),
            json!({"profile_id":PROFILE_ID,"record_revision":2,"tax_year":2025}),
        ] {
            assert!(!both.confirm.holds(&unread, PROFILE_ID, 3), "{unread}");
        }
        for edit in [
            json!({"kind":"imputation_election","tax_year":2025,"criterion":null,"codigo_comercio_accounting":null}),
            json!({"kind":"imputation_election","tax_year":2025,"criterion":"a".repeat(65),"codigo_comercio_accounting":null}),
            json!({"kind":"imputation_election","tax_year":2025,"criterion":null,"codigo_comercio_accounting":"a".repeat(17)}),
        ] {
            assert_eq!(refusal(edit.clone()), "refused", "{edit}");
        }
        for year in [999, 10000] {
            let forwarded = prepared(json!({"kind":"imputation_election","tax_year":year,
                "criterion":"devengo","codigo_comercio_accounting":null}))
            .unwrap();
            assert_eq!(forwarded.payload["tax_year"], year);
        }
        for edit in [
            json!({"kind":"imputation_election","tax_year":-1,"criterion":"x","codigo_comercio_accounting":null}),
            json!({"kind":"imputation_election","tax_year":"2025","criterion":"x","codigo_comercio_accounting":null}),
            json!({"kind":"imputation_election","tax_year":2025,"criterion":"x","codigo_comercio_accounting":null,"extra":1}),
        ] {
            assert!(serde_json::from_value::<Edit>(edit).is_err());
        }
    }

    #[test]
    fn the_authentication_section_has_no_row_edits() {
        for edit in [
            json!({"kind":"add_row","section_key":"auth","values":[]}),
            json!({"kind":"update_row","section_key":"auth","row_key":"0","values":[],"clear_fields":[]}),
            json!({"kind":"remove_row","section_key":"auth","row_key":"0"}),
        ] {
            assert_eq!(refusal(edit), "refused");
        }
        let removed =
            prepared(json!({"kind":"remove_row","section_key":"children","row_key":"0"})).unwrap();
        assert_eq!(removed.definition, "user-profile.repeatable-row-remove");
        assert_eq!(removed.payload["section_key"], "children");
        assert!(
            serde_json::from_value::<Edit>(json!({"kind":"execute","command":"anything"})).is_err()
        );
    }

    #[test]
    fn the_sign_in_method_is_the_provider_operation_under_its_own_baseline_names() {
        let digest = "a".repeat(64);
        let movil = prepared(json!({"kind":"auth_method","provider":"clave_movil",
            "clave_movil_route":"qr","certificate":null}))
        .unwrap();
        assert_eq!(movil.definition, "auth.provider.configure");
        assert_eq!(
            movil.payload,
            json!({"provider":"clave_movil","clave_movil_route":"qr",
                "expected_profile_revision":3,"expected_profile_digest":digest})
        );
        assert!(movil.certificate.is_none());
        let certificate = prepared(json!({"kind":"auth_method","provider":"certificate",
            "clave_movil_route":null,"certificate":"file-0123"}))
        .unwrap();
        assert_eq!(
            certificate.payload,
            json!({"provider":"certificate",
                "expected_profile_revision":3,"expected_profile_digest":digest}),
            "no route, and no path until the token is resolved"
        );
        assert_eq!(certificate.certificate.as_deref(), Some("file-0123"));
        let bare = prepared(json!({"kind":"auth_method","provider":"clave_permanente"})).unwrap();
        assert_eq!(
            bare.payload,
            json!({"provider":"clave_permanente",
                "expected_profile_revision":3,"expected_profile_digest":digest})
        );
        for request in [&movil, &certificate, &bare] {
            for member in [
                "profile_id",
                "expected_revision",
                "expected_content_digest",
                "certificate_path",
            ] {
                assert!(request.payload.get(member).is_none(), "{member}");
            }
        }
        for window_input in [
            json!({"kind":"auth_method","provider":"certificate","certificate_path":"C:\\a.pfx"}),
            json!({"kind":"auth_method","provider":"certificate","profile_id":"another"}),
            json!({"kind":"auth_method"}),
        ] {
            assert!(serde_json::from_value::<Edit>(window_input).is_err());
        }
        assert_eq!(
            refusal(json!({"kind":"auth_method","provider":"x".repeat(MEMBERS_LIMIT + 1)})),
            "refused"
        );
    }

    #[test]
    fn a_method_is_saved_only_when_the_provider_operation_reports_it() {
        let configured = |provider: &str| {
            json!({"result_version":2,"profile_id":PROFILE_ID,"provider":provider,
                "changed":true,"certificate_file_provided":false,"complete":true,
                "profile_tax_id_present":true,"provider_identity_present":true,
                "identity_alignment":"matches"})
        };
        let method = Confirm::Method("certificate".into());
        assert!(method.holds(&configured("certificate"), PROFILE_ID, 3));
        let mut unversioned = configured("certificate");
        unversioned
            .as_object_mut()
            .unwrap()
            .remove("result_version");
        assert!(method.holds(&unversioned, PROFILE_ID, 3));
        assert!(!method.holds(&configured("clave_movil"), PROFILE_ID, 3));
        assert!(!method.holds(&configured("certificate"), "another", 3));
        for broken in [
            json!({"result_version":3}),
            json!({"changed":"yes"}),
            json!({"complete":null}),
            json!({"certificate_file_provided":1}),
        ] {
            let mut result = configured("certificate");
            result
                .as_object_mut()
                .unwrap()
                .extend(broken.as_object().unwrap().clone());
            assert!(!method.holds(&result, PROFILE_ID, 3), "{broken}");
        }
        let record = Confirm::Record;
        let saved = json!({"profile_id":PROFILE_ID,"record_revision":4});
        assert!(record.holds(&saved, PROFILE_ID, 4));
        assert!(!record.holds(&saved, PROFILE_ID, 5));
        assert!(!record.holds(&configured("certificate"), PROFILE_ID, 3));
    }

    #[test]
    fn the_certificate_token_becomes_its_path_only_for_a_certificate_of_the_session() {
        let root = std::env::temp_dir().join(format!(
            "cadrumo-profile-certificate-{}",
            std::process::id()
        ));
        let _ = std::fs::remove_dir_all(&root);
        std::fs::create_dir_all(&root).unwrap();
        for file in ["identity.p12", "statement.csv"] {
            std::fs::write(root.join(file), b"x").unwrap();
        }
        let files = Files::default();
        let one = json!({"session_id":"one"});
        let token = |purpose: Purpose, file: &str| {
            files
                .issue_all(&one, purpose, vec![root.join(file)])
                .unwrap()
                .single()
                .unwrap()
                .unwrap()
                .token
        };
        let method = |token: &str| {
            prepared(json!({"kind":"auth_method","provider":"certificate",
                "clave_movil_route":null,"certificate":token}))
            .unwrap()
        };
        let mut chosen = method(&token(Purpose::Certificate, "identity.p12"));
        chosen.resolve(&files, &one).unwrap();
        assert_eq!(
            chosen.payload["certificate_path"],
            json!(root.join("identity.p12").to_str().unwrap())
        );
        assert!(chosen.certificate.is_none());
        let mut ledger = method(&token(Purpose::BankStatements, "statement.csv"));
        assert_eq!(ledger.resolve(&files, &one).unwrap_err().code, "invalid");
        assert!(ledger.payload.get("certificate_path").is_none());
        let mut path = method(root.join("identity.p12").to_str().unwrap());
        assert_eq!(path.resolve(&files, &one).unwrap_err().code, "invalid");
        let mut other = method(&token(Purpose::Certificate, "identity.p12"));
        assert_eq!(
            other
                .resolve(&files, &json!({"session_id":"two"}))
                .unwrap_err()
                .code,
            "file_unavailable"
        );
        let mut none = prepared(json!({"kind":"auth_method","provider":"clave_movil"})).unwrap();
        none.resolve(&files, &one).unwrap();
        assert!(none.payload.get("certificate_path").is_none());
        std::fs::remove_dir_all(root).unwrap();
    }

    fn raw(text: &str) -> InvokeBody {
        InvokeBody::Raw(text.as_bytes().to_vec())
    }
    fn credential_body(password: &str) -> String {
        json!({"profile_id":PROFILE_ID,"provider":"certificate","password":password}).to_string()
    }

    #[test]
    fn a_credential_is_read_only_from_one_exact_bounded_raw_object() {
        let password = "pa\"ss\\word\n\u{e9}\u{1}";
        let read = credential(&raw(&credential_body(password))).unwrap();
        assert_eq!(read.profile_id, PROFILE_ID);
        assert_eq!(read.provider, "certificate");
        // The secret frame holds the password and nothing else, escaped by
        // the JSON encoder.
        let frame: Value = serde_json::from_str(&read.secret).unwrap();
        assert_eq!(frame, json!({ "password": password }));
        assert_eq!(*read.secret, frame.to_string());
        let permanente = credential(&raw(
            &json!({"profile_id":PROFILE_ID,"provider":"clave_permanente","password":"x"})
                .to_string(),
        ))
        .unwrap();
        assert_eq!(permanente.provider, "clave_permanente");

        let padded = |extra: usize| {
            let overhead = credential_body("").len();
            credential_body(&"a".repeat(CREDENTIAL_BODY_LIMIT - overhead + extra))
        };
        assert_eq!(padded(0).len(), CREDENTIAL_BODY_LIMIT);
        assert!(credential(&raw(&padded(0))).is_ok());
        let not_utf8 = InvokeBody::Raw(
            [
                &b"{\"profile_id\":\""[..],
                PROFILE_ID.as_bytes(),
                b"\",\"provider\":\"certificate\",\"password\":\"\xff\xfe\"}",
            ]
            .concat(),
        );
        let object = |members: Value| raw(&members.to_string());
        let refused = [
            (
                "not raw",
                InvokeBody::Json(json!({"profile_id":PROFILE_ID,"provider":"certificate",
                    "password":"x"})),
            ),
            ("over the limit", raw(&padded(1))),
            ("not utf-8", not_utf8),
            ("not json", raw("{")),
            (
                "an array",
                raw(&format!(r#"["{PROFILE_ID}","certificate","x"]"#)),
            ),
            (
                "an extra key",
                object(json!({"profile_id":PROFILE_ID,"provider":"certificate",
                    "password":"x","extra":"y"})),
            ),
            (
                "no password",
                object(json!({"profile_id":PROFILE_ID,"provider":"certificate","other":"y"})),
            ),
            (
                "no profile",
                object(json!({"provider":"certificate","password":"x","other":"y"})),
            ),
            ("an empty password", raw(&credential_body(""))),
            (
                "a password that is not text",
                object(json!({"profile_id":PROFILE_ID,"provider":"certificate","password":12})),
            ),
        ];
        for (reason, body) in refused {
            assert_eq!(credential(&body).unwrap_err().code, "invalid", "{reason}");
        }
        for provider in ["clave_movil", "Certificate", "", "certificate "] {
            let body = object(json!({"profile_id":PROFILE_ID,"provider":provider,"password":"x"}));
            assert_eq!(credential(&body).unwrap_err().code, "invalid", "{provider}");
        }
    }

    #[test]
    fn a_credential_shows_neither_its_password_nor_its_frame() {
        let read = credential(&raw(&credential_body("hunter2 \"quoted\""))).unwrap();
        let shown = format!("{read:?}");
        assert!(shown.contains("certificate") && shown.contains(PROFILE_ID));
        assert!(!shown.contains("hunter2") && !shown.contains("password"));
        let failure = credential(&raw(&credential_body(""))).unwrap_err();
        assert!(!format!("{failure:?}").contains("password"));
        assert!(
            !serde_json::to_string(&failure)
                .unwrap()
                .contains("password")
        );
    }

    #[cfg(windows)]
    mod relayed {
        use super::super::super::scripted::{OPERATION, PROFILE, holder, observed, resulted, step};
        use super::*;

        fn subject() -> String {
            format!("profile:{PROFILE}")
        }
        fn saved(provider: &str) -> Value {
            json!({"provider": provider, "saved": true})
        }
        fn credential_for(profile: &str, password: &str) -> Credential {
            let body = json!({"profile_id":profile,"provider":"certificate","password":password});
            credential(&raw(&body.to_string())).unwrap()
        }
        fn terminal(definition: &str, extra: Value) -> Value {
            observed(definition, &subject(), "terminal", extra)
        }

        #[tokio::test]
        async fn a_credential_goes_to_the_runtime_on_its_secret_frame_and_is_saved_on_its_receipt()
        {
            let frame = json!({ "password": "pa\"ss\\word" }).to_string();
            let held = holder(|_| {
                vec![
                    step(
                        "operation_secret_submit",
                        json!([
                            ["definition_id", CREDENTIAL_SAVE],
                            ["subject_ref", subject()],
                            ["payload.provider", "certificate"],
                            ["secret", frame]
                        ]),
                        json!({"kind":"operation_submitted","operation_id":OPERATION}),
                        false,
                    ),
                    step(
                        "operation_observe",
                        json!([["operation_id", OPERATION]]),
                        terminal(
                            CREDENTIAL_SAVE,
                            json!({"terminal_condition":"succeeded","effect":"updated"}),
                        ),
                        false,
                    ),
                    step(
                        "operation_result",
                        json!([["operation_id", OPERATION]]),
                        resulted(CREDENTIAL_SAVE, saved("certificate")),
                        false,
                    ),
                ]
            });
            let host = host();
            host.save_credential_on(&held.person, credential_for(PROFILE, "pa\"ss\\word"))
                .await
                .unwrap();
            host.close();
        }

        async fn credential_failure(steps: Vec<Value>, profile: &str) -> Failure {
            let held = holder(move |_| steps.clone());
            let host = host();
            let failure = host
                .save_credential_on(&held.person, credential_for(profile, "x"))
                .await
                .unwrap_err();
            host.close();
            failure
        }

        #[tokio::test]
        async fn a_credential_save_is_refused_unknown_or_unread_by_what_the_runtime_settled() {
            let submitted = || json!({"kind":"operation_submitted","operation_id":OPERATION});
            let secret = |reply: Value| step("operation_secret_submit", json!([]), reply, false);
            let observe = |extra: Value| {
                step(
                    "operation_observe",
                    json!([]),
                    terminal(CREDENTIAL_SAVE, extra),
                    false,
                )
            };

            let refused = credential_failure(
                vec![secret(
                    json!({"kind":"operation_refused","code":"profile_mismatch"}),
                )],
                PROFILE,
            )
            .await;
            assert_eq!((refused.code, refused.reason), ("refused", None));

            let lost = credential_failure(
                vec![secret(
                    json!({"kind":"operation_refused","code":"unavailable"}),
                )],
                PROFILE,
            )
            .await;
            assert_eq!(lost.code, "unknown");
            assert!(lost.operation_id.is_none());

            let interrupted = credential_failure(
                vec![
                    secret(submitted()),
                    observe(json!({"terminal_condition":"failed","effect":"unknown"})),
                ],
                PROFILE,
            )
            .await;
            assert_eq!(interrupted.code, "unknown");
            assert_eq!(interrupted.operation_id.as_deref(), Some(OPERATION));

            let stopped = credential_failure(
                vec![
                    secret(submitted()),
                    observe(json!({"terminal_condition":"refused","effect":"none"})),
                ],
                PROFILE,
            )
            .await;
            assert_eq!(stopped.code, "refused");

            for result in [
                saved("clave_permanente"),
                json!({"provider":"certificate","saved":false}),
                json!({"provider":"certificate"}),
            ] {
                let unread = credential_failure(
                    vec![
                        secret(submitted()),
                        observe(json!({"terminal_condition":"succeeded","effect":"updated"})),
                        step(
                            "operation_result",
                            json!([]),
                            resulted(CREDENTIAL_SAVE, result.clone()),
                            false,
                        ),
                    ],
                    PROFILE,
                )
                .await;
                assert_eq!(unread.code, "saved_unread", "{result}");
            }
        }

        #[tokio::test]
        async fn a_credential_for_another_profile_is_never_sent() {
            let other = "22222222-2222-4222-8222-222222222222";
            // The holder answers nothing: any request would end the test.
            let refused = credential_failure(vec![], other).await;
            assert_eq!(refused.code, "not_signed_in");
        }

        #[tokio::test]
        async fn a_method_change_settles_on_the_provider_operations_own_result() {
            let digest = "a".repeat(64);
            let configured = |provider: &str| {
                json!({"result_version":2,"profile_id":PROFILE,"provider":provider,
                    "changed":true,"certificate_file_provided":false,"complete":true,
                    "profile_tax_id_present":true,"provider_identity_present":true,
                    "identity_alignment":"matches"})
            };
            let change = |result: Value| {
                let digest = digest.clone();
                async move {
                    let held = holder(move |_| {
                        vec![
                            step(
                                "operation_submit",
                                json!([
                                    ["definition_id", AUTH_METHOD],
                                    ["subject_ref", subject()],
                                    ["payload.provider", "clave_movil"],
                                    ["payload.clave_movil_route", "qr"],
                                    ["payload.expected_profile_revision", 3],
                                    ["payload.expected_profile_digest", digest]
                                ]),
                                json!({"kind":"operation_submitted","operation_id":OPERATION}),
                                false,
                            ),
                            step(
                                "operation_observe",
                                json!([["operation_id", OPERATION]]),
                                terminal(
                                    AUTH_METHOD,
                                    json!({"terminal_condition":"succeeded","effect":"updated"}),
                                ),
                                false,
                            ),
                            step(
                                "operation_result",
                                json!([["operation_id", OPERATION]]),
                                resulted(AUTH_METHOD, result.clone()),
                                false,
                            ),
                        ]
                    });
                    let host = host();
                    let outcome = host
                        .change_on(
                            &held.person,
                            prepared(json!({"kind":"auth_method","provider":"clave_movil",
                                "clave_movil_route":"qr","certificate":null}))
                            .unwrap(),
                            PROFILE,
                            3,
                        )
                        .await;
                    host.close();
                    outcome
                }
            };
            change(configured("clave_movil")).await.unwrap();
            let unread = change(configured("certificate")).await.unwrap_err();
            assert_eq!(unread.code, "saved_unread");
        }

        const DESCENDANTS: &str = "user-profile.descendants";

        /// A family replacement the runtime stopped, followed to its settlement;
        /// `detail` is what the runtime serves as that stop's result, if anything.
        async fn stopped_replacement(stop: Value, detail: Option<Value>) -> Failure {
            let held = holder(move |_| {
                let mut steps = vec![step(
                    "operation_observe",
                    json!([]),
                    terminal(DESCENDANTS, stop.clone()),
                    false,
                )];
                if let Some(detail) = detail.clone() {
                    steps.push(step(
                        "operation_result",
                        json!([["operation_id", OPERATION]]),
                        resulted(DESCENDANTS, detail),
                        false,
                    ));
                }
                steps
            });
            let mut events = held.events.subscribe();
            settle(
                &mut events,
                &held.person,
                DESCENDANTS,
                subject(),
                OPERATION.into(),
                true,
            )
            .await
            .unwrap_err()
        }

        #[tokio::test]
        async fn a_refused_replacement_carries_the_sentence_the_application_served_for_it() {
            let none = json!({"terminal_condition":"refused","effect":"none"});
            let served = json!({"detail_version":1,"kind":"registered_error",
                "refusal_words":"  Descendant 2 has no date of birth, and every descendant needs one. ",
                "refusal_words_language":"en"});
            let refused = stopped_replacement(none.clone(), Some(served)).await;
            assert_eq!(refused.code, "refused");
            assert_eq!(
                refused.refusal_words.as_deref(),
                Some("Descendant 2 has no date of birth, and every descendant needs one.")
            );
            assert_eq!(refused.operation_id.as_deref(), Some(OPERATION));

            // A stop whose definition recorded no sentence carries none.
            let unworded = json!({"detail_version":1,"kind":"registered_error"});
            let silent = stopped_replacement(none.clone(), Some(unworded)).await;
            assert_eq!((silent.code, silent.refusal_words), ("refused", None));
            let unread = stopped_replacement(none, None).await;
            assert_eq!((unread.code, unread.refusal_words), ("refused", None));
        }

        #[tokio::test]
        async fn a_conflict_or_an_unknown_effect_is_relayed_by_its_code_alone() {
            // Nothing is scripted after the observation: a result read would end the test.
            let conflict = stopped_replacement(
                json!({"terminal_condition":"failed","effect":"none",
                    "failure_error_code":"FAIL_PROFILE_RECORD_CONFLICT"}),
                None,
            )
            .await;
            assert_eq!((conflict.code, conflict.refusal_words), ("conflict", None));
            let unknown = stopped_replacement(
                json!({"terminal_condition":"failed","effect":"unknown"}),
                None,
            )
            .await;
            assert_eq!((unknown.code, unknown.refusal_words), ("unknown", None));
        }
    }
}
