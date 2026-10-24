//! The desktop Modelo workspace's channel to the Modelo family's registered
//! operations, over the held person's relay. Three named reads serve the
//! declarations list, a declaration's form and a box's help card; beyond
//! them the window names one admitted definition and a JSON object, which
//! the runtime decodes against the definition's registered contract, not
//! restated here. The host fills the profile and the subject the contract
//! declares, keeps paths away from the window, and bounds the request. It
//! keeps no declaration data: a result is passed on and dropped. It
//! remembers only which operations this window submitted, so the window can
//! follow, answer and cancel those and no other.
//!
//! Files reach a submission only as tokens the host issued for the person's
//! own picks. An edit's amounts reach the relay only in a raw body, sent as
//! its transient financial operand and wiped once sent. Nothing here submits
//! to the AEAT: an export writes a local file and a filing is recorded
//! locally.
mod admitted;
mod files;

use super::relay::{self, Failure, Result, Wiped, protocol};
use super::settle::{self, Decision, Operations, Outcome, ReviewDocument, Tracked};
use super::user_profile::ProfileHost;
use crate::agent::person::{self, HeldPerson, PersonEvent};
use admitted::{Definition, Subject, admitted};
use files::{Files, Format, Picks, Purpose};
use serde_json::{Map, Value, json};
use std::{path::Path, sync::Arc, time::Duration};
use tauri::{
    State,
    ipc::{InvokeBody, Request},
};
use tokio::sync::broadcast::Receiver;

/// Bounds a whole read, including admission and queueing, beyond following.
const READ_LIMIT: Duration = Duration::from_secs(140);
/// A dialog's filter name or a suggested file name, as the window words it.
const LABEL_LIMIT: usize = 128;
/// The longest identifier the window names in a read: a box, a registry
/// revision or a calculation revision.
const REFERENCE_LIMIT: usize = 128;

/// Fields that name a profile. The host fills `profile_id` where the request
/// declares it, and the window never names either.
const HOST_FIELDS: [&str; 2] = ["profile_id", "bucket_id"];

/// How a request field names a local file.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum FileUse {
    /// A file the worker reads, picked in an open dialog for this purpose.
    Read(Purpose),
    /// Where the worker writes, chosen in the save dialog as one of these.
    Write(&'static [Format]),
}
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Shape {
    One,
    Optional,
}
/// A request field that names a local file. The window puts a token there.
struct PathField {
    definition: &'static str,
    field: &'static str,
    file: FileUse,
    shape: Shape,
}
const fn read(definition: &'static str, field: &'static str, purpose: Purpose) -> PathField {
    PathField {
        definition,
        field,
        file: FileUse::Read(purpose),
        shape: Shape::One,
    }
}
const fn write(
    definition: &'static str,
    field: &'static str,
    formats: &'static [Format],
) -> PathField {
    PathField {
        definition,
        field,
        file: FileUse::Write(formats),
        shape: Shape::One,
    }
}
const fn optional(field: PathField) -> PathField {
    PathField {
        shape: Shape::Optional,
        ..field
    }
}
/// An official filing file, as its export layout lays it out: the fichero
/// BOE of a fixed-width design, or the XML of a dictionary one.
const FILING_FILE: &[Format] = &[Format::Boe, Format::Xml];
const PATH_FIELDS: [PathField; 22] = [
    write("modelo.audit.export", "output", &[Format::Zip]),
    // Written as the format of the artefact it names: see `export_formats`.
    write("modelo.export", "output_path", &[]),
    optional(read(
        "modelo.filing_record.import",
        "source_path",
        Purpose::Evidence,
    )),
    write("modelo.quickfile", "output_path", FILING_FILE),
    write(
        "modelo.reconcile.export-xlsx",
        "output_path",
        &[Format::Xlsx],
    ),
    read("modelo.reconcile.import", "source_path", Purpose::Evidence),
    write("modelo.review_package.build", "output_path", &[Format::Zip]),
    write(
        "modelo.review_package.counter_sign",
        "output",
        &[Format::Sig],
    ),
    read(
        "modelo.review_package.counter_sign",
        "package",
        Purpose::Package,
    ),
    read(
        "modelo.review_package.counter_sign",
        "signature",
        Purpose::Signature,
    ),
    read(
        "modelo.review_package.decrypt",
        "envelope_path",
        Purpose::Envelope,
    ),
    write("modelo.review_package.decrypt", "output", &[Format::Zip]),
    write(
        "modelo.review_package.encrypt_feedback",
        "output",
        &[Format::Sealed],
    ),
    optional(read(
        "modelo.review_package.encrypt_feedback",
        "receipt",
        Purpose::Evidence,
    )),
    write(
        "modelo.review_package.encrypt_for_recipient",
        "output",
        &[Format::Sealed],
    ),
    read(
        "modelo.review_package.encrypt_for_recipient",
        "package",
        Purpose::Package,
    ),
    read(
        "modelo.review_package.import_feedback",
        "envelope_path",
        Purpose::Envelope,
    ),
    read(
        "modelo.review_package.import_feedback",
        "package",
        Purpose::Package,
    ),
    write("modelo.review_package.sign", "output", &[Format::Sig]),
    read("modelo.review_package.sign", "package", Purpose::Package),
    write("modelo.spreadsheet.export", "output_path", &[Format::Xlsx]),
    read("modelo.work.report_verify", "source_path", Purpose::Report),
];
const EXPORT: &str = "modelo.export";
/// Each artefact an export writes, as the formats the person may save it as.
/// The request's own default is the filing file.
fn export_formats(payload: &Map<String, Value>) -> Result<&'static [Format]> {
    let artefact = match payload.get("artefact") {
        None => "fichero_boe",
        Some(artefact) => artefact.as_str().ok_or_else(|| failure("invalid"))?,
    };
    Ok(match artefact {
        "fichero_boe" => FILING_FILE,
        "calculation_report_csv" => &[Format::Csv],
        "calculation_report_pdf" => &[Format::Pdf],
        "calculation_review_xlsx" => &[Format::Xlsx],
        _ => return Err(failure("invalid")),
    })
}

/// Result fields that name a file the worker read or wrote.
const RESULT_PATH_KEYS: [&str; 9] = [
    "envelope_path",
    "output",
    "output_path",
    "package",
    "path",
    "receipt",
    "receipt_path",
    "signature",
    "source_path",
];

fn failure(code: &'static str) -> Failure {
    Failure::new(code)
}

/// Refuses a payload the host must not pass on: one that names a profile, or
/// an edit's amounts outside their raw body.
fn admit_fields(definition: Definition, payload: &Map<String, Value>) -> Result<()> {
    if definition.financial() || HOST_FIELDS.iter().any(|field| payload.contains_key(*field)) {
        return Err(failure("invalid"));
    }
    Ok(())
}

/// A work unit's identity, as the product spells it.
fn work_unit_admitted(id: &str) -> bool {
    super::setup::wire::is_hex64(id)
}

/// The subject the definition's contract declares for this request. Only a
/// stored record's owning work unit comes from the window, which read it
/// with the record; every other form is derived and the window names none.
fn subject(
    definition: Definition,
    profile: &str,
    payload: &Map<String, Value>,
    work_unit: Option<&str>,
) -> Result<String> {
    let field = |path: &[&str]| {
        let (last, outer) = path.split_last()?;
        let mut fields = payload;
        for name in outer {
            fields = fields.get(*name)?.as_object()?;
        }
        fields.get(*last)
    };
    let text = |value: &Value| {
        value
            .as_str()
            .filter(|text| !text.trim().is_empty())
            .map(str::to_owned)
            .ok_or_else(|| failure("invalid"))
    };
    match (definition.subject, work_unit) {
        (Subject::StoredWorkUnit(_), Some(id)) if work_unit_admitted(id) => Ok(id.to_owned()),
        (Subject::StoredWorkUnit(_), _) | (_, Some(_)) => Err(failure("invalid")),
        (Subject::Profile, None) => Ok(relay::subject(profile)),
        (Subject::Field(path), None) => text(field(path).ok_or_else(|| failure("invalid"))?),
        (Subject::FieldOrProfile(path), None) => match field(path) {
            None | Some(Value::Null) => Ok(relay::subject(profile)),
            Some(value) => text(value),
        },
    }
}

fn path_text(path: &Path) -> Result<Value> {
    path.to_str()
        .map(|text| json!(text))
        .ok_or_else(|| failure("file_unavailable"))
}

/// Puts the path behind each token where the definition reads or writes a
/// file. Anything but a token this session issued for that use is refused,
/// and a file to write must have been saved as a format the field takes.
fn substitute(
    files: &Files,
    identity: &Value,
    definition: Definition,
    payload: &mut Map<String, Value>,
) -> Result<()> {
    let export = if definition.id == EXPORT {
        Some(export_formats(payload)?)
    } else {
        None
    };
    for field in PATH_FIELDS
        .iter()
        .filter(|field| field.definition == definition.id)
    {
        let Some(value) = payload.get_mut(field.field) else {
            continue;
        };
        if field.shape == Shape::Optional && value.is_null() {
            continue;
        }
        let token = value.as_str().ok_or_else(|| failure("invalid"))?;
        let path = match field.file {
            FileUse::Read(purpose) => files.path(identity, token, purpose, false)?,
            FileUse::Write(formats) => {
                let path = files.path(identity, token, Purpose::Export, true)?;
                let formats = export.unwrap_or(formats);
                let kind = files::extension(&path);
                if !formats
                    .iter()
                    .any(|format| kind.as_deref() == Some(format.extension()))
                {
                    return Err(failure("invalid"));
                }
                path
            }
        };
        *value = path_text(&path)?;
    }
    Ok(())
}

/// The edit's amounts from its raw body: a complete `ModeloEditOperatorInputV2`
/// whose baseline is the one the form admitted for this profile. Answers the
/// operand, overwritten when it is dropped, and the work unit it edits.
fn financial_body(body: &InvokeBody, profile: &str) -> Result<(Wiped, String)> {
    let InvokeBody::Raw(bytes) = body else {
        return Err(failure("invalid"));
    };
    if bytes.len() > person::REQUEST_LIMIT || bytes.trim_ascii_start().first() != Some(&b'{') {
        return Err(failure("invalid"));
    }
    let input = Wiped(serde_json::from_slice(bytes).map_err(|_| failure("invalid"))?);
    let fields = input.0.as_object().ok_or_else(|| failure("invalid"))?;
    let baseline = &input.0["submission"]["baseline"];
    let work_unit = baseline["work_unit_id"]
        .as_str()
        .filter(|id| work_unit_admitted(id))
        .ok_or_else(|| failure("invalid"))?
        .to_owned();
    if !fields.contains_key("input_version")
        || baseline["bucket_id"] != profile
        || HOST_FIELDS.iter().any(|field| fields.contains_key(*field))
    {
        return Err(failure("invalid"));
    }
    Ok((input, work_unit))
}

/// The relay's financial-operand request for `input`, which is moved into
/// it, not copied.
fn financial_submission(definition: &str, subject: &str, mut input: Wiped) -> Result<Wiped> {
    let mut request = Wiped(
        json!({"action":"operation_financial_submit", "definition_id":definition,
        "subject_ref":subject, "input":null}),
    );
    request.0["input"] = std::mem::take(&mut input.0);
    if !person::request_fits(&request.0) {
        return Err(failure("too_large"));
    }
    Ok(request)
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
/// An identifier the window read from a form and names back in a read.
fn reference_admitted(reference: &str) -> bool {
    !reference.trim().is_empty()
        && reference.len() <= REFERENCE_LIMIT
        && !reference.chars().any(char::is_control)
}

/// Checks that a named read answered for this profile, declaration and
/// language, then passes it on unchanged.
fn read_answer(
    projection: Value,
    profile: &str,
    work_unit: Option<&str>,
    language: Option<&str>,
) -> Result<Value> {
    let bound = projection["result_version"] == 1
        && projection["profile_id"] == profile
        && work_unit.is_none_or(|id| projection["work_unit_id"] == id)
        && language.is_none_or(|language| projection["output_language"] == language);
    if !bound {
        return Err(protocol());
    }
    Ok(projection)
}

/// Submits an admitted request, already holding the profile's own fields,
/// and follows it. `events` must be subscribed before this is called. The
/// request's text is overwritten once it is sent, or when it is refused here.
async fn submit_on(
    operations: &Operations,
    person: &HeldPerson,
    identity: Value,
    events: &mut Receiver<PersonEvent>,
    definition: Definition,
    subject: String,
    request: Wiped,
) -> Result<Outcome> {
    let operation = relay::submit_wiping(person, request, definition.mutation()).await?;
    let tracked = Tracked::new(
        operation,
        definition.settling(),
        subject,
        identity,
        Vec::new(),
    );
    operations.track(tracked.clone());
    settle::settle(events, &tracked, person).await
}

/// Builds the plain submission for `payload`: the profile where the request
/// names it, and the subject its contract declares.
fn plain_submission(
    definition: Definition,
    profile: &str,
    mut payload: Wiped,
    work_unit: Option<&str>,
) -> Result<(Wiped, String)> {
    let fields = payload
        .0
        .as_object_mut()
        .ok_or_else(|| failure("invalid"))?;
    if definition.profile {
        fields.insert("profile_id".into(), json!(profile));
    }
    let subject = subject(definition, profile, fields, work_unit)?;
    let request = relay::submission(definition.id, &subject, std::mem::take(&mut payload.0));
    relay::admit_size(&request.0)?;
    Ok((request, subject))
}

pub struct ModeloHost {
    profile: Arc<ProfileHost>,
    operations: Operations,
    files: Files,
}
impl ModeloHost {
    pub fn new(profile: Arc<ProfileHost>) -> Self {
        Self {
            profile,
            operations: Operations::default(),
            files: Files::default(),
        }
    }
    pub fn close(&self) {
        self.operations.clear();
        self.files.clear();
    }
    /// The identity of the session the window holds now.
    async fn identity(&self) -> Result<Value> {
        let person = self.profile.person(None).await?;
        relay::identity(&person).await
    }
    /// The held person and its identity, for one serialised exchange.
    async fn held(&self) -> Result<(HeldPerson, Value, String)> {
        if self.profile.is_closed() {
            return Err(protocol());
        }
        let person = self.profile.person(None).await?;
        let identity = relay::identity(&person).await?;
        let profile = identity["profile_id"]
            .as_str()
            .ok_or_else(protocol)?
            .to_owned();
        Ok((person, identity, profile))
    }
    async fn submit(
        &self,
        definition: &str,
        payload: Value,
        work_unit: Option<String>,
    ) -> Result<Outcome> {
        let mut payload = Wiped(payload);
        let definition = admitted(definition).ok_or_else(|| failure("not_admitted"))?;
        admit_fields(
            definition,
            payload.0.as_object().ok_or_else(|| failure("invalid"))?,
        )?;
        let _serial = self.profile.serial().await;
        let (person, identity, profile) = self.held().await?;
        substitute(
            &self.files,
            &identity,
            definition,
            payload
                .0
                .as_object_mut()
                .ok_or_else(|| failure("invalid"))?,
        )?;
        let (request, subject) =
            plain_submission(definition, &profile, payload, work_unit.as_deref())?;
        let mut events = self.profile.sign_in().person_events();
        let outcome = submit_on(
            &self.operations,
            &person,
            identity,
            &mut events,
            definition,
            subject,
            request,
        )
        .await?;
        settle::still_held(&self.profile, &person, outcome, definition.mutation()).await
    }
    /// Submits an edit's amounts as the relay's financial operand.
    async fn submit_financial(&self, definition: &str, body: &InvokeBody) -> Result<Outcome> {
        let definition = admitted(definition)
            .filter(|definition| definition.financial())
            .ok_or_else(protocol)?;
        let _serial = self.profile.serial().await;
        let (person, identity, profile) = self.held().await?;
        let (input, work_unit) = financial_body(body, &profile)?;
        let request = financial_submission(definition.id, &work_unit, input)?;
        let mut events = self.profile.sign_in().person_events();
        let outcome = submit_on(
            &self.operations,
            &person,
            identity,
            &mut events,
            definition,
            work_unit,
            request,
        )
        .await?;
        settle::still_held(&self.profile, &person, outcome, definition.mutation()).await
    }
    /// Runs one of the workspace's named reads to its answer.
    async fn read(
        &self,
        definition: &'static str,
        payload: Value,
        work_unit: Option<&str>,
        language: &str,
    ) -> Result<Value> {
        if !super::language::supported(language) {
            return Err(protocol());
        }
        let definition = admitted(definition).ok_or_else(protocol)?;
        tokio::time::timeout(READ_LIMIT, async {
            let _serial = self.profile.serial().await;
            let (person, identity, profile) = self.held().await?;
            let (request, subject) = plain_submission(definition, &profile, Wiped(payload), None)?;
            let mut events = self.profile.sign_in().person_events();
            let operation = relay::submit_wiping(&person, request, false).await?;
            // A named read is followed here, never by the window.
            let tracked = Tracked::new(
                operation,
                definition.settling(),
                subject,
                identity,
                Vec::new(),
            );
            let answered = settle::settle(&mut events, &tracked, &person).await?;
            settle::still_holding(&self.profile, &person).await?;
            match answered {
                Outcome::Settled { result, .. } => {
                    let list = definition.id == "modelo.declarations.list";
                    read_answer(result, &profile, work_unit, list.then_some(language))
                }
                Outcome::Refused { reason, .. } => {
                    let mut refused = failure("refused");
                    refused.reason = reason;
                    Err(refused)
                }
                Outcome::Review { .. } | Outcome::Running { .. } => Err(protocol()),
            }
        })
        .await
        .unwrap_or_else(|_| Err(protocol()))
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

/// The profile's declarations list, every row said in `output_language`.
#[tauri::command]
async fn modelo_declarations(
    host: State<'_, Arc<ModeloHost>>,
    output_language: String,
) -> Result<Value> {
    host.read(
        "modelo.declarations.list",
        json!({"output_language":output_language}),
        None,
        &output_language,
    )
    .await
}
/// One declaration's form, with the edit baseline it admits or why not.
#[tauri::command]
async fn modelo_form(
    host: State<'_, Arc<ModeloHost>>,
    work_unit_id: String,
    output_language: String,
) -> Result<Value> {
    if !work_unit_admitted(&work_unit_id) {
        return Err(failure("invalid"));
    }
    host.read(
        "modelo.work.form",
        json!({"work_unit_id":work_unit_id, "output_language":output_language}),
        Some(&work_unit_id),
        &output_language,
    )
    .await
}
/// One box's help card, for the revisions the form was read at.
#[tauri::command]
async fn modelo_casilla_help(
    host: State<'_, Arc<ModeloHost>>,
    work_unit_id: String,
    casilla_id: String,
    registry_revision_id: String,
    calculation_revision_id: Option<String>,
    output_language: String,
) -> Result<Value> {
    let references = [
        Some(&casilla_id),
        Some(&registry_revision_id),
        calculation_revision_id.as_ref(),
    ]
    .into_iter()
    .flatten()
    .all(|reference| reference_admitted(reference));
    if !work_unit_admitted(&work_unit_id) || !references {
        return Err(failure("invalid"));
    }
    host.read(
        "modelo.work.casilla_help",
        json!({"work_unit_id":work_unit_id, "casilla_id":casilla_id,
            "registry_revision_id":registry_revision_id,
            "calculation_revision_id":calculation_revision_id, "output_language":output_language}),
        Some(&work_unit_id),
        &output_language,
    )
    .await
}
/// Submits one admitted Modelo operation with `payload`, a JSON object of its
/// registered request without the profile, and follows it until it settles
/// or waits on the person. `work_unit` names the work unit owning the stored
/// record the request names, where the contract's subject is that, and is
/// absent otherwise. One attempt: nothing is retried.
#[tauri::command]
async fn modelo_submit(
    host: State<'_, Arc<ModeloHost>>,
    definition: String,
    payload: Value,
    work_unit: Option<String>,
) -> Result<Outcome> {
    host.submit(&definition, payload, work_unit).await
}
/// Checks an edit's typed entries against the admitted baseline, from the raw
/// body: the one route for its amounts. The body is overwritten once it is
/// sent and never logged.
#[tauri::command]
async fn modelo_edit_preflight(
    host: State<'_, Arc<ModeloHost>>,
    request: Request<'_>,
) -> Result<Outcome> {
    host.submit_financial("modelo.edit.preflight", request.body())
        .await
}
/// Applies an edit's typed values, from the raw body, as
/// [`modelo_edit_preflight`] takes them.
#[tauri::command]
async fn modelo_edit_apply(
    host: State<'_, Arc<ModeloHost>>,
    request: Request<'_>,
) -> Result<Outcome> {
    host.submit_financial("modelo.edit.apply", request.body())
        .await
}
/// Where an operation this window submitted stands now, without waiting.
#[tauri::command]
async fn modelo_observe(host: State<'_, Arc<ModeloHost>>, operation: String) -> Result<Outcome> {
    host.observe(&operation).await
}
#[tauri::command]
async fn modelo_review(
    host: State<'_, Arc<ModeloHost>>,
    operation: String,
) -> Result<ReviewDocument> {
    host.review(&operation).await
}
#[tauri::command]
async fn modelo_answer(
    host: State<'_, Arc<ModeloHost>>,
    operation: String,
    review_digest: String,
    decision: Decision,
) -> Result<Outcome> {
    host.answer(&operation, &review_digest, decision).await
}
#[tauri::command]
async fn modelo_cancel(
    host: State<'_, Arc<ModeloHost>>,
    operation: String,
    revision: u64,
) -> Result<Outcome> {
    host.cancel(&operation, revision).await
}
/// Opens the native dialog for one file of `purpose` over the window and
/// answers a token for it. A dialog closed without a pick picks nothing.
#[tauri::command]
async fn modelo_files_pick<R: tauri::Runtime>(
    host: State<'_, Arc<ModeloHost>>,
    window: tauri::WebviewWindow<R>,
    purpose: Purpose,
    filter_label: String,
) -> Result<Picks> {
    use tauri_plugin_dialog::DialogExt;
    if purpose == Purpose::Export || !label_admitted(&filter_label) {
        return Err(failure("invalid"));
    }
    let identity = host.identity().await?;
    let paths = super::blocking(move || {
        Ok(window
            .dialog()
            .file()
            .set_parent(&window)
            .add_filter(filter_label, purpose.extensions())
            .blocking_pick_file()
            .and_then(|picked| picked.into_path().ok())
            .into_iter()
            .collect())
    })
    .await?;
    // The person may have signed out while the dialog was open.
    if host.identity().await? != identity {
        return Err(failure("not_signed_in"));
    }
    host.files.issue_all(&identity, purpose, paths)
}
/// Opens the native save dialog for a file in `format` and answers a token
/// for where to write it. The dialog asks before replacing a file.
#[tauri::command]
async fn modelo_files_save<R: tauri::Runtime>(
    host: State<'_, Arc<ModeloHost>>,
    window: tauri::WebviewWindow<R>,
    format: Format,
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
        Some(path) => host.files.issue_save(&identity, format, path),
        None => Ok(Picks::none(0)),
    }
}
/// Shows a file the host saved for the window, selected in the system file
/// manager. The window names it by its save token; the path never reaches it.
#[tauri::command]
async fn modelo_files_reveal(host: State<'_, Arc<ModeloHost>>, token: String) -> Result<()> {
    let identity = host.identity().await?;
    let path = host.files.saved(&identity, &token)?;
    super::blocking(move || Ok(reveal(&path)))
        .await?
        .map_err(|_| failure("unavailable"))
}
#[cfg(windows)]
fn reveal(path: &Path) -> std::io::Result<()> {
    use std::os::windows::process::CommandExt;
    // Explorer reads its own command line: the path is quoted after the
    // switch, never as one argument with it. It can answer a failing status
    // even when it showed the file, so only a failure to start it counts.
    std::process::Command::new("explorer.exe")
        .raw_arg(format!("/select,\"{}\"", path.display()))
        .spawn()
        .map(drop)
}
/// No portable call selects a file, so the folder holding it is opened.
#[cfg(not(windows))]
fn reveal(path: &Path) -> std::io::Result<()> {
    let folder = path.parent().ok_or(std::io::ErrorKind::NotFound)?;
    opener::open(folder).map_err(std::io::Error::other)
}
/// Forgets tokens the page no longer shows.
#[tauri::command]
fn modelo_files_forget(host: State<'_, Arc<ModeloHost>>, tokens: Vec<String>) {
    host.files.forget(&tokens);
}

pub fn commands<R: tauri::Runtime>() -> crate::app::Commands<R> {
    crate::app::commands![
        modelo_declarations,
        modelo_form,
        modelo_casilla_help,
        modelo_submit,
        modelo_edit_preflight,
        modelo_edit_apply,
        modelo_observe,
        modelo_review,
        modelo_answer,
        modelo_cancel,
        modelo_files_pick,
        modelo_files_save,
        modelo_files_reveal,
        modelo_files_forget
    ]
}

#[cfg(test)]
mod tests;
