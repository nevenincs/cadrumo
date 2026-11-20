//! The desktop Ledger page's channel to the ledger family's registered
//! operations, over the held person's relay. The window names one admitted
//! definition and a JSON object; the runtime decodes it against the
//! definition's registered contract, which this host does not restate. The
//! host fills the profile and the subject the contract declares, keeps paths
//! and secrets away from the window, and bounds the request. It keeps no ledger data: a result is passed on and
//! dropped. It remembers only which operations this window submitted, so the
//! window can follow, answer and cancel those and no other.
//!
//! Files reach a submission only as tokens the host issued for the person's
//! own picks, and an own account's number only in a raw body that is wiped
//! once sent.
//!
//! A background definition, a classification job's run, holds the serial
//! lock only while it is submitted. The window is answered where it stands
//! then, and the host follows it to its end without the lock, so a cancel or
//! any other ledger write is not held up behind it; each move of the run cues
//! the background-task channel.
mod admitted;

use super::background_tasks::BackgroundTasks;
use super::picked_files::{self, Files, Kinds, Pick, Picks, Purpose};
use super::relay::{self, Failure, Result, Wiped, lock, protocol};
use super::settle::{self, Decision, Operations, Outcome, ReviewDocument, Serial, Tracked};
use super::user_profile::ProfileHost;
use crate::agent::person::{HeldPerson, PersonEvent};
use admitted::{Definition, Subject, admitted};
use cadrumo_application::diagnostics::Diagnostics;
use serde::{Deserialize, Serialize};
use serde_json::{Map, Value, json};
use std::sync::{
    Arc, Mutex,
    atomic::{AtomicBool, Ordering},
};
use tauri::{
    State,
    ipc::{Channel, InvokeBody, Request},
};
use tokio::sync::broadcast::Receiver;

/// Fields the host fills itself. The window never names a profile or a
/// directory.
const HOST_FIELDS: [&str; 2] = ["profile_id", "source_directory"];
#[derive(Clone, Copy, PartialEq, Eq)]
enum Shape {
    One,
    Optional,
    Many,
    /// Where an export is written.
    Save,
}
/// A field that names a local file. The window puts a token there.
struct PathField {
    definition: &'static str,
    field: &'static str,
    purpose: Purpose,
    shape: Shape,
}
const PATH_FIELDS: [PathField; 9] = [
    PathField {
        definition: "ledger.evidence.add",
        field: "source_path",
        purpose: Purpose::Documents,
        shape: Shape::One,
    },
    PathField {
        definition: "ledger.evidence.batch",
        field: "sources",
        purpose: Purpose::Documents,
        shape: Shape::Many,
    },
    PathField {
        definition: "ledger.export",
        field: "output_path",
        purpose: Purpose::Export,
        shape: Shape::Save,
    },
    PathField {
        definition: "ledger.import",
        field: "files",
        purpose: Purpose::BankStatements,
        shape: Shape::Many,
    },
    PathField {
        definition: "ledger.import",
        field: "verify_source",
        purpose: Purpose::BankStatements,
        shape: Shape::Optional,
    },
    PathField {
        definition: "ledger.inventory.evidence.add",
        field: "source_path",
        purpose: Purpose::Documents,
        shape: Shape::One,
    },
    PathField {
        definition: "ledger.invoice.attach_document",
        field: "source_path",
        purpose: Purpose::Documents,
        shape: Shape::One,
    },
    PathField {
        definition: "ledger.invoice.import",
        field: "source_path",
        purpose: Purpose::InvoiceBooks,
        shape: Shape::One,
    },
    // A certificate already in custody is named by its fingerprint alone.
    PathField {
        definition: "ledger.retencion_soportada.record",
        field: "source_path",
        purpose: Purpose::Documents,
        shape: Shape::Optional,
    },
];
/// Definitions that also read the directory their sources are under.
const SOURCE_DIRECTORY: [&str; 5] = [
    "ledger.evidence.add",
    "ledger.evidence.batch",
    "ledger.inventory.evidence.add",
    "ledger.invoice.attach_document",
    "ledger.retencion_soportada.record",
];
const EXPORT: &str = "ledger.export";
/// An own account's change, JSON-escaped, within its contract's bounds.
const SECRET_BODY_LIMIT: usize = 8 * 1024;
/// An own account's number and bank block: private input that travels only
/// in a raw request body.
const OWN_ACCOUNT_SECRETS: [&str; 6] = [
    "iban",
    "swift_bic",
    "bank_name",
    "bank_address",
    "bank_city",
    "bank_country_code",
];
const OWN_ACCOUNT: &str = "ledger.own_account";

fn failure(code: &'static str) -> Failure {
    Failure::new(code)
}

/// Refuses a payload the host must not pass on: one that names a field the
/// host fills, or carries an own account's secret outside its raw body.
fn admit_fields(definition: Definition, payload: &Map<String, Value>) -> Result<()> {
    let refused = HOST_FIELDS.iter().any(|field| payload.contains_key(*field))
        || (definition.id == OWN_ACCOUNT
            && OWN_ACCOUNT_SECRETS
                .iter()
                .any(|field| payload.contains_key(*field)));
    if refused {
        return Err(failure("invalid"));
    }
    Ok(())
}

/// Puts the path behind each token where the definition reads a file, and
/// fills the directory those files are under where it reads one. Anything
/// but a token this session issued for that purpose is refused. Answers the
/// folders those files are in, which the window is never shown.
fn substitute(
    files: &Files,
    identity: &Value,
    definition: Definition,
    payload: &mut Map<String, Value>,
) -> Result<Vec<String>> {
    let mut first: Option<std::path::PathBuf> = None;
    let mut folders = Vec::new();
    for field in PATH_FIELDS
        .iter()
        .filter(|field| field.definition == definition.id)
    {
        let Some(value) = payload.get_mut(field.field) else {
            continue;
        };
        let mut resolve = |token: &Value| -> Result<Value> {
            let token = token.as_str().ok_or_else(|| failure("invalid"))?;
            let path = files.path(identity, token, field.purpose, field.shape == Shape::Save)?;
            let text = picked_files::path_text(&path)?;
            let folder = if path.is_dir() {
                Some(path.as_path())
            } else {
                path.parent()
            };
            // A drive's root names no one.
            if let Some(folder) = folder.filter(|folder| folder.file_name().is_some())
                && let Some(folder) = folder.to_str()
                && !folders.iter().any(|known| known == folder)
            {
                folders.push(folder.to_owned());
            }
            first.get_or_insert(path);
            Ok(text)
        };
        let resolved = match (field.shape, &*value) {
            (Shape::Optional, Value::Null) => Value::Null,
            (Shape::Many, Value::Array(tokens)) if !tokens.is_empty() => Value::Array(
                tokens
                    .iter()
                    .map(&mut resolve)
                    .collect::<Result<Vec<_>>>()?,
            ),
            (Shape::Many, _) => return Err(failure("invalid")),
            (_, token) => resolve(token)?,
        };
        *value = resolved;
    }
    if let Some(first) = &first
        && SOURCE_DIRECTORY.contains(&definition.id)
    {
        let directory = if first.is_dir() {
            first.as_path()
        } else {
            first.parent().ok_or_else(|| failure("file_unavailable"))?
        };
        payload.insert(
            "source_directory".into(),
            picked_files::path_text(directory)?,
        );
    }
    if let Some(first) = &first
        && definition.id == EXPORT
    {
        // The person chose the file for this format in the save dialog.
        let format = match payload.get("export_format") {
            None => "csv",
            Some(format) => format.as_str().ok_or_else(|| failure("invalid"))?,
        };
        if picked_files::extension(first).as_deref() != Some(format) {
            return Err(failure("invalid"));
        }
    }
    Ok(folders)
}

/// Result fields that name a file the worker read or wrote.
const RESULT_PATH_KEYS: [&str; 10] = [
    "file_name",
    "files",
    "output_path",
    "path",
    "provider_locator",
    "source_directory",
    "source_name",
    "source_path",
    "source_reference",
    "verify_source",
];

/// The subject the definition's contract declares for this request: the
/// profile, or the value of the request field the contract names.
fn subject(definition: Definition, profile: &str, payload: &Map<String, Value>) -> Result<String> {
    let Subject::Field(path) = definition.subject else {
        return Ok(relay::subject(profile));
    };
    let (last, outer) = path.split_last().ok_or_else(protocol)?;
    let mut fields = payload;
    for name in outer {
        fields = fields
            .get(*name)
            .and_then(Value::as_object)
            .ok_or_else(|| failure("invalid"))?;
    }
    fields
        .get(*last)
        .and_then(Value::as_str)
        .filter(|text| !text.trim().is_empty())
        .map(str::to_owned)
        .ok_or_else(|| failure("invalid"))
}

/// Submits a payload the host already admitted, for the profile of the held
/// session `identity` names, and follows it. `events` must be subscribed
/// before this is called. The request's text is overwritten once it is sent,
/// or when it is refused here.
async fn submit_on(
    operations: &Operations,
    person: &HeldPerson,
    identity: Value,
    events: &mut Receiver<PersonEvent>,
    definition: Definition,
    mut payload: Wiped,
    folders: Vec<String>,
) -> Result<Outcome> {
    let profile = identity["profile_id"]
        .as_str()
        .ok_or_else(protocol)?
        .to_owned();
    let fields = payload
        .0
        .as_object_mut()
        .ok_or_else(|| failure("invalid"))?;
    fields.insert("profile_id".into(), json!(profile));
    let subject = subject(definition, &profile, fields)?;
    let request = relay::submission(definition.id, &subject, std::mem::take(&mut payload.0));
    relay::admit_size(&request.0)?;
    operations.room(&identity)?;
    let operation = relay::submit_wiping(person, request, definition.mutation()).await?;
    let tracked = operations.timed(Tracked::new(
        operation,
        definition.settling(),
        subject,
        identity,
        folders,
    ));
    operations.track(tracked.clone());
    settle::settle(events, &tracked, person).await
}

/// Submits a background definition's payload, already admitted, for the
/// profile of the held session `identity` names, holding `serial` only until
/// the runtime has taken it, and tracks it for the window to observe and
/// cancel. Its text is overwritten once sent, or when it is refused here.
async fn start_on(
    serial: &impl Serial,
    operations: &Operations,
    person: &HeldPerson,
    identity: Value,
    definition: Definition,
    mut payload: Wiped,
) -> Result<Tracked> {
    let profile = identity["profile_id"]
        .as_str()
        .ok_or_else(protocol)?
        .to_owned();
    let fields = payload
        .0
        .as_object_mut()
        .ok_or_else(|| failure("invalid"))?;
    fields.insert("profile_id".into(), json!(profile));
    let subject = subject(definition, &profile, fields)?;
    let request = relay::submission(definition.id, &subject, std::mem::take(&mut payload.0));
    relay::admit_size(&request.0)?;
    operations.room(&identity)?;
    let operation = {
        let _serial = serial.serial().await;
        relay::submit_wiping(person, request, definition.mutation()).await?
    };
    let tracked = operations.timed(Tracked::new(
        operation,
        definition.settling(),
        subject,
        identity,
        Vec::new(),
    ));
    operations.track(tracked.clone());
    Ok(tracked)
}

/// Where a drop on the window goes: the Ledger page's current drop target.
struct Dropping {
    subscription: u32,
    purpose: Purpose,
    kinds: Kinds,
    updates: Channel<DropSignal>,
}

/// A drag over the window, as the page that accepts drops sees it.
#[derive(Debug, Serialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum DropSignal {
    Over,
    Left,
    Dropped(Picks),
}

#[derive(Clone, Copy, Debug, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ExportFormat {
    Csv,
    Jsonl,
    Xlsx,
}
impl ExportFormat {
    fn extension(self) -> &'static str {
        match self {
            Self::Csv => "csv",
            Self::Jsonl => "jsonl",
            Self::Xlsx => "xlsx",
        }
    }
}

/// The own account's change from its raw body: the complete registered
/// request without the profile, for adding an account or changing its
/// details. Its text is overwritten when it is dropped.
fn own_account_body(body: &InvokeBody) -> Result<Wiped> {
    let request = relay::wiped_body(body, SECRET_BODY_LIMIT)?;
    let fields = request.0.as_object().ok_or_else(|| failure("invalid"))?;
    if !matches!(
        fields.get("action").and_then(Value::as_str),
        Some("add" | "update")
    ) || HOST_FIELDS.iter().any(|field| fields.contains_key(*field))
    {
        return Err(failure("invalid"));
    }
    Ok(request)
}

pub struct LedgerHost {
    profile: Arc<ProfileHost>,
    operations: Operations,
    files: Files,
    dropping: Mutex<Option<Dropping>>,
    listening: AtomicBool,
    /// Cued each time a background run this window started moves.
    tasks: Arc<BackgroundTasks>,
    /// The follows of the background runs this window started.
    runs: Mutex<Vec<tauri::async_runtime::JoinHandle<()>>>,
}
impl LedgerHost {
    pub fn new(
        profile: Arc<ProfileHost>,
        tasks: Arc<BackgroundTasks>,
        diagnostics: Arc<Diagnostics>,
    ) -> Self {
        Self {
            profile,
            operations: Operations::measured(diagnostics),
            files: Files::default(),
            dropping: Mutex::new(None),
            listening: AtomicBool::new(false),
            tasks,
            runs: Mutex::default(),
        }
    }
    pub fn close(&self) {
        // A run goes on in the profile's worker: only the window's follow of it ends.
        for run in lock(&self.runs).drain(..) {
            run.abort();
        }
        self.operations.clear();
        self.files.clear();
        *lock(&self.dropping) = None;
    }
    /// The identity of the session the window holds now.
    async fn identity(&self) -> Result<Value> {
        let person = self.profile.person(None).await?;
        relay::identity(&person).await
    }
    async fn submit(&self, definition: &str, payload: Value) -> Result<Outcome> {
        let payload = Wiped(payload);
        let definition = admitted(definition).ok_or_else(|| failure("not_admitted"))?;
        admit_fields(
            definition,
            payload.0.as_object().ok_or_else(|| failure("invalid"))?,
        )?;
        self.relay(definition, payload).await
    }
    /// Submits an admitted payload for the window's signed-in profile, with
    /// the path behind each of its file tokens.
    async fn relay(&self, definition: Definition, mut payload: Wiped) -> Result<Outcome> {
        if self.profile.is_closed() {
            return Err(protocol());
        }
        if definition.background() {
            return self.start(definition, payload).await;
        }
        let _serial = self.profile.serial().await;
        let person = self.profile.person(None).await?;
        let identity = relay::identity(&person).await?;
        let folders = substitute(
            &self.files,
            &identity,
            definition,
            payload
                .0
                .as_object_mut()
                .ok_or_else(|| failure("invalid"))?,
        )?;
        let mut events = self.profile.sign_in().person_events();
        let outcome = submit_on(
            &self.operations,
            &person,
            identity,
            &mut events,
            definition,
            payload,
            folders,
        )
        .await?;
        settle::still_held(&self.profile, &person, outcome, definition.mutation()).await
    }
    /// Starts a background definition for the window's signed-in profile and
    /// answers where it stands now; the host follows it from there, outside
    /// the serial lock. It names no file.
    async fn start(&self, definition: Definition, payload: Wiped) -> Result<Outcome> {
        let person = self.profile.person(None).await?;
        let identity = relay::identity(&person).await?;
        let events = self.profile.sign_in().person_events();
        let tracked = start_on(
            self.profile.as_ref(),
            &self.operations,
            &person,
            identity,
            definition,
            payload,
        )
        .await?;
        let standing = settle::observe_on(&tracked, &person).await;
        let tasks = self.tasks.clone();
        let follow = tauri::async_runtime::spawn(settle::follow_detached(
            events,
            tracked,
            person.clone(),
            move || tasks.changed(),
        ));
        {
            let mut runs = lock(&self.runs);
            runs.retain(|run| !run.inner().is_finished());
            runs.push(follow);
        }
        settle::still_held(&self.profile, &person, standing?, definition.mutation()).await
    }
    /// Tokens for what the person dropped on the page that takes drops.
    fn dropped(self: &Arc<Self>, event: &tauri::DragDropEvent) {
        let Some((purpose, kinds, updates)) = lock(&self.dropping)
            .as_ref()
            .map(|target| (target.purpose, target.kinds.clone(), target.updates.clone()))
        else {
            return;
        };
        match event {
            tauri::DragDropEvent::Enter { .. } => {
                let _ = updates.send(DropSignal::Over);
            }
            tauri::DragDropEvent::Leave => {
                let _ = updates.send(DropSignal::Left);
            }
            tauri::DragDropEvent::Drop { paths, .. } => {
                let host = self.clone();
                let paths = paths.clone();
                tauri::async_runtime::spawn(async move {
                    let count = paths.len();
                    let picks = match host.identity().await {
                        Ok(identity) => host
                            .files
                            .issue_kinds(&identity, purpose, &kinds, paths)
                            .unwrap_or_else(|_| Picks::none(count)),
                        Err(_) => Picks::none(count),
                    };
                    let _ = updates.send(DropSignal::Dropped(picks));
                });
            }
            _ => {}
        }
    }
    async fn observe(&self, operation: &str) -> Result<Outcome> {
        let tracked = self.operations.find(operation)?;
        let person = settle::holding(&self.profile, &tracked).await?;
        settle::observe_on(&tracked, &person).await
    }
    async fn review(&self, operation: &str) -> Result<ReviewDocument> {
        let tracked = self.operations.find(operation)?;
        let person = settle::holding(&self.profile, &tracked).await?;
        let document = settle::review_on(&self.operations, &tracked, &person).await?;
        settle::still_holding(&self.profile, &person).await?;
        Ok(document)
    }
    async fn answer(
        &self,
        operation: &str,
        review_digest: &str,
        decision: Decision,
    ) -> Result<Outcome> {
        let _serial = self.profile.serial().await;
        let tracked = self.operations.find(operation)?;
        let person = settle::holding(&self.profile, &tracked).await?;
        let mut events = self.profile.sign_in().person_events();
        settle::answer_on(
            self.profile.as_ref(),
            &self.operations,
            &tracked,
            &person,
            &mut events,
            review_digest,
            decision,
        )
        .await
    }
    async fn cancel(&self, operation: &str, revision: u64) -> Result<Outcome> {
        let _serial = self.profile.serial().await;
        let tracked = self.operations.find(operation)?;
        let person = settle::holding(&self.profile, &tracked).await?;
        settle::cancel_on(&tracked, &person, revision).await
    }
}

/// Submits one admitted ledger operation with `payload`, a JSON object of its
/// registered request without the profile, and follows it until it settles
/// or waits on the person. One attempt: nothing is retried.
#[tauri::command]
async fn ledger_submit(
    host: State<'_, Arc<LedgerHost>>,
    definition: String,
    payload: Value,
) -> Result<Outcome> {
    host.submit(&definition, payload).await
}
/// Where an operation this window submitted stands now, without waiting.
#[tauri::command]
async fn ledger_observe(host: State<'_, Arc<LedgerHost>>, operation: String) -> Result<Outcome> {
    host.observe(&operation).await
}
#[tauri::command]
async fn ledger_review(
    host: State<'_, Arc<LedgerHost>>,
    operation: String,
) -> Result<ReviewDocument> {
    host.review(&operation).await
}
#[tauri::command]
async fn ledger_answer(
    host: State<'_, Arc<LedgerHost>>,
    operation: String,
    review_digest: String,
    decision: Decision,
) -> Result<Outcome> {
    host.answer(&operation, &review_digest, decision).await
}
/// Opens the native dialog for files of `purpose` over the window and
/// answers a token for each one picked. A dialog closed without a pick picks
/// nothing.
#[tauri::command]
async fn ledger_files_pick<R: tauri::Runtime>(
    host: State<'_, Arc<LedgerHost>>,
    window: tauri::WebviewWindow<R>,
    purpose: Purpose,
    pick: Pick,
    filter_label: String,
    kinds: Option<Vec<String>>,
) -> Result<Picks> {
    // An export is saved, not picked, and a certificate is the profile
    // page's, with its own tokens.
    if matches!(purpose, Purpose::Export | Purpose::Certificate)
        || !picked_files::label_admitted(&filter_label)
    {
        return Err(failure("invalid"));
    }
    let kinds = Kinds::narrowed(purpose, kinds)?;
    let identity = host.identity().await?;
    let paths = picked_files::choose_kinds(window, pick, kinds.clone(), filter_label).await?;
    // The person may have signed out while the dialog was open.
    if host.identity().await? != identity {
        return Err(failure("not_signed_in"));
    }
    host.files.issue_kinds(&identity, purpose, &kinds, paths)
}
/// Opens the native save dialog for an export in `format` and answers a
/// token for where to write it. The dialog asks before replacing a file.
#[tauri::command]
async fn ledger_files_save<R: tauri::Runtime>(
    host: State<'_, Arc<LedgerHost>>,
    window: tauri::WebviewWindow<R>,
    format: ExportFormat,
    filter_label: String,
    suggested_name: Option<String>,
) -> Result<Picks> {
    if !picked_files::label_admitted(&filter_label)
        || suggested_name
            .as_deref()
            .is_some_and(|name| !picked_files::file_name_admitted(name))
    {
        return Err(failure("invalid"));
    }
    let identity = host.identity().await?;
    let path =
        picked_files::choose_save(window, format.extension(), filter_label, suggested_name).await?;
    if host.identity().await? != identity {
        return Err(failure("not_signed_in"));
    }
    match path {
        Some(path) => host
            .files
            .issue_save(&identity, Purpose::Export, format.extension(), path),
        None => Ok(Picks::none(0)),
    }
}
/// Shows an exported file selected in the system file manager, so the person
/// can check a file whose export outcome is unknown. The window names it by
/// its save token; the path never reaches it.
#[tauri::command]
async fn ledger_files_reveal(host: State<'_, Arc<LedgerHost>>, token: String) -> Result<()> {
    let identity = host.identity().await?;
    let path = host.files.saved(&identity, &token, Purpose::Export)?;
    super::blocking(move || Ok(super::external::reveal(&path)))
        .await?
        .map_err(|_| failure("unavailable"))
}
/// Forgets tokens the page no longer shows.
#[tauri::command]
fn ledger_files_forget(host: State<'_, Arc<LedgerHost>>, tokens: Vec<String>) {
    host.files.forget(&tokens);
}
/// Sends what is dragged over and dropped on the window, as tokens for files
/// of `purpose`, to the page until it unobserves. A later observer replaces
/// an earlier one.
#[tauri::command]
fn ledger_drop_observe<R: tauri::Runtime>(
    host: State<'_, Arc<LedgerHost>>,
    window: tauri::WebviewWindow<R>,
    purpose: Purpose,
    kinds: Option<Vec<String>>,
    updates: Channel<DropSignal>,
) -> Result<u32> {
    let kinds = Kinds::narrowed(purpose, kinds)?;
    let subscription = updates.id();
    if host.profile.is_closed() {
        return Ok(subscription);
    }
    *lock(&host.dropping) = Some(Dropping {
        subscription,
        purpose,
        kinds,
        updates,
    });
    if !host.listening.swap(true, Ordering::AcqRel) {
        let owner = host.inner().clone();
        window.on_window_event(move |event| {
            if let tauri::WindowEvent::DragDrop(drag) = event {
                owner.dropped(drag);
            }
        });
    }
    Ok(subscription)
}
#[tauri::command]
fn ledger_drop_unobserve(host: State<'_, Arc<LedgerHost>>, subscription: u32) {
    let mut dropping = lock(&host.dropping);
    if dropping
        .as_ref()
        .is_some_and(|target| target.subscription == subscription)
    {
        *dropping = None;
    }
}
/// Adds an own account or changes its details, with its number and bank
/// block, from the raw body: the one route for them. The body is overwritten
/// once it is sent and never logged.
#[tauri::command]
async fn ledger_own_account(
    host: State<'_, Arc<LedgerHost>>,
    request: Request<'_>,
) -> Result<Outcome> {
    let payload = own_account_body(request.body())?;
    let definition = admitted(OWN_ACCOUNT).ok_or_else(protocol)?;
    host.relay(definition, payload).await
}
#[tauri::command]
async fn ledger_cancel(
    host: State<'_, Arc<LedgerHost>>,
    operation: String,
    revision: u64,
) -> Result<Outcome> {
    host.cancel(&operation, revision).await
}

pub fn commands<R: tauri::Runtime>() -> crate::app::Commands<R> {
    crate::app::commands![
        ledger_submit,
        ledger_observe,
        ledger_review,
        ledger_answer,
        ledger_cancel,
        ledger_files_pick,
        ledger_files_save,
        ledger_files_reveal,
        ledger_files_forget,
        ledger_drop_observe,
        ledger_drop_unobserve,
        ledger_own_account
    ]
}

#[cfg(test)]
mod tests;
