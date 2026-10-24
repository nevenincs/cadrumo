//! The desktop Ledger page's channel to the ledger family's registered
//! operations, over the held person's relay. The window names one admitted
//! definition and a JSON object; the runtime decodes it against the
//! definition's registered contract, which this host does not restate. The
//! host fills the profile, keeps paths and secrets away from the window, and
//! bounds the request. It keeps no ledger data: a result is passed on and
//! dropped. It remembers only which operations this window submitted, so the
//! window can follow, answer and cancel those and no other.
//!
//! Files reach a submission only as tokens the host issued for the person's
//! own picks, and an own account's number only in a raw body that is wiped
//! once sent.
mod admitted;
mod files;

use super::relay::{self, Failure, Result, Wiped, lock, protocol};
use super::settle::{self, Decision, Operations, Outcome, ReviewDocument, Tracked};
use super::user_profile::ProfileHost;
use crate::agent::person::{HeldPerson, PersonEvent};
use admitted::{Definition, admitted};
use files::{Files, Pick, Picks, Purpose};
use serde::{Deserialize, Serialize};
use serde_json::{Map, Value, json};
use std::{
    path::Path,
    sync::{
        Arc, Mutex,
        atomic::{AtomicBool, Ordering},
    },
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
const PATH_FIELDS: [PathField; 6] = [
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
        definition: "ledger.invoice.import",
        field: "source_path",
        purpose: Purpose::InvoiceBooks,
        shape: Shape::One,
    },
];
/// Definitions that also read the directory their sources are under.
const SOURCE_DIRECTORY: [&str; 2] = ["ledger.evidence.add", "ledger.evidence.batch"];
const EXPORT: &str = "ledger.export";
/// An own account's change, JSON-escaped, within its contract's bounds.
const SECRET_BODY_LIMIT: usize = 8 * 1024;
/// A dialog's filter name or a suggested file name, as the window words it.
const LABEL_LIMIT: usize = 128;
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

fn path_text(path: &Path) -> Result<Value> {
    path.to_str()
        .map(|text| json!(text))
        .ok_or_else(|| failure("file_unavailable"))
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
            let text = path_text(&path)?;
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
        payload.insert("source_directory".into(), path_text(directory)?);
    }
    if let Some(first) = &first
        && definition.id == EXPORT
    {
        // The person chose the file for this format in the save dialog.
        let format = match payload.get("export_format") {
            None => "csv",
            Some(format) => format.as_str().ok_or_else(|| failure("invalid"))?,
        };
        if files::extension(first).as_deref() != Some(format) {
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
    payload
        .0
        .as_object_mut()
        .ok_or_else(|| failure("invalid"))?
        .insert("profile_id".into(), json!(profile));
    let subject = relay::subject(&profile);
    let request = relay::submission(definition.id, &subject, std::mem::take(&mut payload.0));
    relay::admit_size(&request.0)?;
    let operation = relay::submit_wiping(person, request, definition.mutation()).await?;
    let tracked = Tracked::new(operation, definition.settling(), subject, identity, folders);
    operations.track(tracked.clone());
    settle::settle(events, &tracked, person).await
}

/// Where a drop on the window goes: the Ledger page's current drop target.
struct Dropping {
    subscription: u32,
    purpose: Purpose,
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

/// Words the window shows in a native dialog: a filter's name or a file name.
fn label_admitted(label: &str) -> bool {
    !label.is_empty()
        && label.chars().count() <= LABEL_LIMIT
        && !label.chars().any(char::is_control)
}
fn file_name_admitted(name: &str) -> bool {
    label_admitted(name) && !name.contains(['/', '\\', ':']) && !name.starts_with('.')
}

/// The own account's change from its raw body: the complete registered
/// request without the profile, for adding an account or changing its
/// details. Its text is overwritten when it is dropped.
fn own_account_body(body: &InvokeBody) -> Result<Wiped> {
    let InvokeBody::Raw(bytes) = body else {
        return Err(failure("invalid"));
    };
    if bytes.len() > SECRET_BODY_LIMIT || bytes.trim_ascii_start().first() != Some(&b'{') {
        return Err(failure("invalid"));
    }
    let request = Wiped(serde_json::from_slice(bytes).map_err(|_| failure("invalid"))?);
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
}
impl LedgerHost {
    pub fn new(profile: Arc<ProfileHost>) -> Self {
        Self {
            profile,
            operations: Operations::default(),
            files: Files::default(),
            dropping: Mutex::new(None),
            listening: AtomicBool::new(false),
        }
    }
    pub fn close(&self) {
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
    /// Tokens for what the person dropped on the page that takes drops.
    fn dropped(self: &Arc<Self>, event: &tauri::DragDropEvent) {
        let Some((purpose, updates)) = lock(&self.dropping)
            .as_ref()
            .map(|target| (target.purpose, target.updates.clone()))
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
                            .issue_all(&identity, purpose, paths)
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
) -> Result<Picks> {
    use tauri_plugin_dialog::DialogExt;
    if purpose == Purpose::Export || !label_admitted(&filter_label) {
        return Err(failure("invalid"));
    }
    let identity = host.identity().await?;
    let paths = super::blocking(move || {
        let dialog = window.dialog().file().set_parent(&window);
        let chosen: Vec<_> = match pick {
            Pick::File => dialog
                .add_filter(filter_label, purpose.extensions())
                .blocking_pick_file()
                .into_iter()
                .collect(),
            Pick::Files => dialog
                .add_filter(filter_label, purpose.extensions())
                .blocking_pick_files()
                .unwrap_or_default(),
            Pick::Folder => dialog.blocking_pick_folder().into_iter().collect(),
        };
        Ok(chosen
            .into_iter()
            .filter_map(|picked| picked.into_path().ok())
            .collect())
    })
    .await?;
    // The person may have signed out while the dialog was open.
    if host.identity().await? != identity {
        return Err(failure("not_signed_in"));
    }
    host.files.issue_all(&identity, purpose, paths)
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
    use tauri_plugin_dialog::DialogExt;
    if !label_admitted(&filter_label)
        || suggested_name
            .as_deref()
            .is_some_and(|name| !file_name_admitted(name))
    {
        return Err(failure("invalid"));
    }
    let identity = host.identity().await?;
    let path = super::blocking(move || {
        let mut dialog = window
            .dialog()
            .file()
            .set_parent(&window)
            .add_filter(filter_label, &[format.extension()]);
        if let Some(name) = suggested_name {
            dialog = dialog.set_file_name(name);
        }
        Ok(dialog
            .blocking_save_file()
            .and_then(|picked| picked.into_path().ok()))
    })
    .await?;
    if host.identity().await? != identity {
        return Err(failure("not_signed_in"));
    }
    match path {
        Some(path) => host.files.issue_save(&identity, format.extension(), path),
        None => Ok(Picks::none(0)),
    }
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
    updates: Channel<DropSignal>,
) -> u32 {
    let subscription = updates.id();
    if host.profile.is_closed() {
        return subscription;
    }
    *lock(&host.dropping) = Some(Dropping {
        subscription,
        purpose,
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
    subscription
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
        ledger_files_forget,
        ledger_drop_observe,
        ledger_drop_unobserve,
        ledger_own_account
    ]
}

#[cfg(test)]
mod tests;
