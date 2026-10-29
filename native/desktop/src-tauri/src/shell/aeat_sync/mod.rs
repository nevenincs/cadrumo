//! The AEAT sync page's host side: named commands over the held person's
//! relay that bring AEAT data into the signed-in profile. Each command takes
//! the exact profile it was opened for and refuses a window that has switched
//! accounts. The host submits only the closed list of reads in [`admitted`];
//! it holds no tax rule, and nothing here submits a return.
//!
//! The window receives closed states and outcomes only, never an operation,
//! snapshot or row identifier, a refusal code or a path.
mod admitted;
mod outcome;
mod run;

use super::picked_files::Purpose;
use super::relay::{self, Failure, Result, lock, protocol};
use super::setup::{SetupHost, wire as setup_wire};
use super::user_profile::{Cue, ProfileHost, censo};
use crate::agent::person::{HeldPerson, PersonEvent};
use admitted::{Area, admitted};
use outcome::{Counts, Outcome, Reason};
use run::{Run, Settled, Snapshot, Step};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::sync::{Arc, Mutex};
use std::time::Duration;
use tauri::{State, ipc::Channel};

/// The most areas one request may name.
const SELECTION_LIMIT: usize = 64;
/// A modelo number: short, ASCII and alphanumeric.
const FORM_LENGTH: std::ops::RangeInclusive<usize> = 1..=5;
/// A calendar year as four digits; the years on offer are the backend's.
const YEARS: std::ops::RangeInclusive<u16> = 1000..=9999;
/// How many filing years the Borrador import offers where the backend serves
/// none, ending with the last calendar year.
const BORRADOR_FALLBACK_YEARS: u16 = 6;
/// The most served years one reply carries.
const YEAR_LIMIT: usize = 64;
/// How long the preflight waits for the setup engine's first quick read.
const PREPARE_LIMIT: Duration = Duration::from_secs(20);
/// The most filed declaration rows one reply carries.
const FILED_LIMIT: usize = 2000;
/// The most notification rows one reply carries.
const NOTIFICATION_LIMIT: usize = 500;
/// The longest text of a notification row the window is served.
const TEXT_LIMIT: usize = 512;
/// The Borrador 100 is an annual declaration: its one period.
const BORRADOR_PERIOD: &str = "0A";
/// What the dialog's filter calls a Borrador file: a format's name.
const BORRADOR_KINDS: &str = "PDF";

/// The areas the window asks to bring: every one for "Update from AEAT", one
/// for an area's own update. Each reads every year the backend serves.
#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub(crate) struct Selection {
    areas: Vec<Area>,
}

/// A request the host accepts: its areas in run order, once each, and every
/// definition they submit on the closed list.
#[derive(Debug, PartialEq, Eq)]
pub(crate) struct Plan {
    pub(crate) areas: Vec<Area>,
}
impl Selection {
    pub(crate) fn admit(self) -> Result<Plan> {
        if self.areas.len() > SELECTION_LIMIT {
            return Err(invalid());
        }
        let areas: Vec<Area> = Area::ORDER
            .into_iter()
            .filter(|area| self.areas.contains(area))
            .collect();
        let closed = areas
            .iter()
            .flat_map(|area| area.definitions())
            .all(|id| admitted(id).is_some());
        if areas.is_empty() || !closed {
            return Err(invalid());
        }
        Ok(Plan { areas })
    }
}

fn invalid() -> Failure {
    Failure::new("invalid")
}

/// A failure the window may read: its closed code, nothing else.
fn bare(code: &'static str) -> Failure {
    Failure::new(code)
}

/// The held person for exactly `profile`, or the refusal that the window's
/// account is not the one signed in.
async fn held(host: &ProfileHost, profile: &str) -> Result<HeldPerson> {
    host.person(Some(profile)).await
}

/// The run of one signed-in session.
struct Held {
    identity: Value,
    run: Arc<Mutex<Run>>,
    task: Option<tauri::async_runtime::JoinHandle<()>>,
}
impl Held {
    fn end(&mut self) {
        if let Some(task) = self.task.take() {
            task.abort();
        }
    }
}

/// The AEAT sync run and its window cue, held by the profile host beside the
/// census session. A sign-out, a profile change or the window's close
/// discards the run.
pub(crate) struct SyncHost {
    held: Mutex<Option<Held>>,
    observer: Cue,
    changes: tokio::sync::watch::Sender<u64>,
    /// Stops the sign-in waiting on the person's phone.
    sign_in: Mutex<Option<Arc<tokio::sync::Notify>>>,
}
impl Default for SyncHost {
    fn default() -> Self {
        Self {
            held: Mutex::new(None),
            observer: Cue::default(),
            changes: tokio::sync::watch::Sender::new(0),
            sign_in: Mutex::new(None),
        }
    }
}
impl SyncHost {
    fn changed(&self) {
        self.changes
            .send_modify(|revision| *revision = revision.wrapping_add(1));
    }
    pub(crate) fn close(&self) {
        if let Some(mut held) = lock(&self.held).take() {
            held.end();
        }
        self.observer.end();
        if let Some(waiting) = lock(&self.sign_in).take() {
            waiting.notify_one();
        }
    }
    /// The run of the session `identity` names. A run of another session is
    /// discarded: its person signed out or switched profile.
    fn current(&self, identity: &Value) -> Option<Arc<Mutex<Run>>> {
        let mut held = lock(&self.held);
        if held.as_ref().is_some_and(|h| h.identity != *identity) {
            if let Some(mut stale) = held.take() {
                stale.end();
            }
            drop(held);
            self.changed();
            return None;
        }
        held.as_ref().map(|h| h.run.clone())
    }
    /// Holds a fresh run of `plan` for the session `identity` names, under one
    /// hold of the lock: a run of that session that still moves is kept and
    /// none answered; a run it replaces is ended. The fresh run is claimed,
    /// and answered for a driver to follow.
    fn begin(&self, identity: &Value, plan: &Plan) -> Option<Arc<Mutex<Run>>> {
        let mut held = lock(&self.held);
        if let Some(current) = held.as_ref()
            && current.identity == *identity
            && run::lock(&current.run).active()
        {
            return None;
        }
        if let Some(mut replaced) = held.take() {
            replaced.end();
        }
        let mut fresh = Run::new(plan);
        fresh.claim();
        let fresh = Arc::new(Mutex::new(fresh));
        *held = Some(Held {
            identity: identity.clone(),
            run: fresh.clone(),
            task: None,
        });
        Some(fresh)
    }
    /// Follows `claimed`, a run whose queue the caller claimed, with a driver
    /// loop over the relay for `person`.
    fn drive(
        &self,
        host: &Arc<ProfileHost>,
        person: HeldPerson,
        profile: String,
        identity: Value,
        claimed: &Arc<Mutex<Run>>,
    ) {
        let driver = Arc::new(RelayDriver {
            host: host.clone(),
            person,
            profile,
            identity,
        });
        self.follow(claimed, driver);
    }
    /// Spawns `driver` over `claimed` while it is still the held run. A run a
    /// start replaced since it was claimed is released instead, so a retry
    /// racing a start leaves the fresh run and its driver alone. A previous
    /// loop of the same run released its claim before this one was made and
    /// ends by itself, so it is not aborted. True when a driver follows it.
    fn follow<D: run::Driver>(&self, claimed: &Arc<Mutex<Run>>, driver: Arc<D>) -> bool {
        let mut held = lock(&self.held);
        let Some(current) = held.as_mut().filter(|h| Arc::ptr_eq(&h.run, claimed)) else {
            drop(held);
            run::lock(claimed).release();
            return false;
        };
        current.task = Some(tauri::async_runtime::spawn(run::drive(
            claimed.clone(),
            driver,
        )));
        true
    }
}

/// How the terminal projection `p` settles its item when it did not succeed;
/// none for a success, whose result is read.
fn unsucceeded(p: &Value) -> Option<Settled> {
    outcome::terminal(p).map(|outcome| Settled {
        outcome,
        session_ended: outcome::session_ended(p),
        ..Settled::default()
    })
}

/// The relay side of the run: each item submitted, followed and read through
/// the one closed outcome table.
struct RelayDriver {
    host: Arc<ProfileHost>,
    person: HeldPerson,
    profile: String,
    identity: Value,
}
impl RelayDriver {
    /// Submits one admitted capture and follows it to its settlement, with no
    /// limit of its own: a lost reply or an unknown effect is unknown.
    async fn capture(&self, definition: &'static str, payload: Value) -> (Settled, Option<Value>) {
        if admitted(definition).is_none() {
            return (Settled::of(Outcome::Failed(Reason::Other)), None);
        }
        let mut events = self.host.sign_in().person_events();
        let subject = relay::subject(&self.profile);
        let submitted = {
            let _serial = self.host.serial().await;
            relay::submit(&self.person, definition, &subject, payload, true).await
        };
        let operation = match submitted {
            Ok(operation) => operation,
            Err(refused) if refused.code == "refused" => {
                let reason = outcome::reason(refused.reason.as_deref());
                return (Settled::of(Outcome::Failed(reason)), None);
            }
            Err(_) => return (Settled::of(Outcome::Unknown), None),
        };
        let relayed = relay::Relayed {
            person: &self.person,
            operation,
            definition,
            subject,
        };
        let Ok(p) = relay::follow(&mut events, &relayed, |_| false).await else {
            return (Settled::of(Outcome::Unknown), None);
        };
        if let Some(settled) = unsucceeded(&p) {
            return (settled, None);
        }
        let Ok(document) = relay::result(&relayed).await else {
            return (Settled::of(Outcome::Unknown), None);
        };
        let projection = document["projection"].clone();
        let (outcome, counts) = outcome::succeeded(definition, &projection);
        (
            Settled {
                outcome,
                counts,
                ..Settled::default()
            },
            Some(projection),
        )
    }

    /// The census item: the existing census session, followed until its
    /// comparison waits for the person or it settles.
    async fn census(&self) -> Settled {
        let mut events = self.host.sign_in().person_events();
        let mut state = match censo::begin(&self.host, self.profile.clone()).await {
            Ok(snapshot) => snapshot.state(),
            Err(failure) => {
                return Settled::of(match failure.code {
                    "refused" => Outcome::Failed(Reason::NoAccess),
                    "unknown" => Outcome::Unknown,
                    _ => Outcome::Failed(Reason::Unavailable),
                });
            }
        };
        loop {
            match census_outcome(state) {
                Some(settled) => return settled,
                None => loop {
                    match events.recv().await {
                        Ok(PersonEvent::OperationChanged)
                        | Err(tokio::sync::broadcast::error::RecvError::Lagged(_)) => break,
                        Ok(PersonEvent::Retired)
                        | Err(tokio::sync::broadcast::error::RecvError::Closed) => {
                            return Settled::of(Outcome::Unknown);
                        }
                        _ => {}
                    }
                },
            }
            state = match censo::standing(&self.host, &self.profile).await {
                Ok(state) => state,
                Err(_) => return Settled::of(Outcome::Unknown),
            };
        }
    }

    async fn vat(&self) -> Settled {
        let Some(years) = self.served_years("iva_wallet_years").await else {
            return Settled::of(Outcome::Failed(Reason::Unavailable));
        };
        let (Some(from), Some(to)) = (years.iter().min(), years.iter().max()) else {
            return Settled::of(Outcome::NothingFound);
        };
        let payload = json!({"profile_id": self.profile, "year_from": from, "year_to": to});
        self.capture("live.iva-wallet.history-capture", payload)
            .await
            .0
    }

    /// The years the backend serves for an area, from the status read.
    async fn served_years(&self, key: &str) -> Option<Vec<u16>> {
        let status = read_status(&self.host, &self.person, &self.profile)
            .await
            .ok()?;
        served_years(&status, key)
    }
}

/// The years `key` of a status read lists; none where it does not read as a
/// bounded list of four-digit years.
fn served_years(status: &Value, key: &str) -> Option<Vec<u16>> {
    let years = status["status"][key].as_array()?;
    if years.len() > YEAR_LIMIT {
        return None;
    }
    years
        .iter()
        .map(|year| {
            year.as_u64()
                .and_then(|y| u16::try_from(y).ok())
                .filter(|y| YEARS.contains(y))
        })
        .collect()
}

/// The calendar year, in UTC, of the instant `seconds` after the Unix epoch.
fn calendar_year(seconds: u64) -> u16 {
    // The civil-from-days conversion of the proleptic Gregorian calendar,
    // counted in 400-year eras from 0000-03-01.
    let days = i64::try_from(seconds / 86_400).unwrap_or(i64::MAX / 2) + 719_468;
    let era = days.div_euclid(146_097);
    let day_of_era = days.rem_euclid(146_097);
    let year_of_era =
        (day_of_era - day_of_era / 1_460 + day_of_era / 36_524 - day_of_era / 146_096) / 365;
    let day_of_year = day_of_era - (365 * year_of_era + year_of_era / 4 - year_of_era / 100);
    let month_index = (5 * day_of_year + 2) / 153;
    let year = year_of_era + era * 400 + i64::from(month_index >= 10);
    u16::try_from(year).unwrap_or(u16::MAX)
}

/// The filing years the Borrador import offers, latest first: the years the
/// backend serves, or, where it serves none, the last few calendar years up
/// to the last one, since a year's Borrador is downloaded the year after.
fn borrador_years(status: &Value, now: std::time::SystemTime) -> Vec<u16> {
    let mut years = served_years(status, "filed_declaration_years").unwrap_or_default();
    if years.is_empty() {
        let seconds = now
            .duration_since(std::time::UNIX_EPOCH)
            .map_or(0, |since| since.as_secs());
        let latest = calendar_year(seconds).saturating_sub(1);
        years = (0..BORRADOR_FALLBACK_YEARS)
            .map(|back| latest.saturating_sub(back))
            .collect();
    }
    years.sort_unstable_by(|a, b| b.cmp(a));
    years.dedup();
    years
}

/// How the census session's state settles its item; none while it reads.
fn census_outcome(state: &str) -> Option<Settled> {
    Some(match state {
        "review" => Settled {
            outcome: Outcome::Brought,
            review_pending: true,
            ..Settled::default()
        },
        "done" => Settled::of(Outcome::Brought),
        "stopped" => Settled::of(Outcome::NothingFound),
        "failed" | "unsupported" => Settled::of(Outcome::Failed(Reason::Other)),
        "unknown" => Settled::of(Outcome::Unknown),
        _ => return None,
    })
}

impl run::Driver for RelayDriver {
    async fn run(&self, step: Step) -> Settled {
        let profile = json!({ "profile_id": self.profile });
        match step {
            Step::Census => self.census().await,
            Step::Verify(definition) => self.capture(definition, profile).await.0,
            Step::Notifications => self.capture("live.notifications.capture", profile).await.0,
            Step::Vat => self.vat().await,
            Step::Discover => {
                let (mut settled, document) = self.capture("live.filed-discover", profile).await;
                settled.discovered = document.as_ref().and_then(outcome::discovered);
                settled
            }
            Step::Filed { year, forms } => {
                let payload = json!({"profile_id": self.profile, "year_from": year,
                    "year_to": year, "modelos": forms});
                self.capture("live.filed-capture.bulk", payload).await.0
            }
        }
    }
    async fn current(&self) -> bool {
        let Ok(person) = self.host.person(Some(&self.profile)).await else {
            return false;
        };
        relay::identity(&person)
            .await
            .is_ok_and(|identity| identity == self.identity)
    }
    fn changed(&self) {
        self.host.aeat_sync().changed();
    }
}

async fn read_status(host: &ProfileHost, person: &HeldPerson, profile: &str) -> Result<Value> {
    host.run(
        person,
        "live.sync.status",
        json!({ "profile_id": profile }),
        false,
    )
    .await
    .map_err(|failure| {
        bare(if failure.code == "not_signed_in" {
            "not_signed_in"
        } else {
            "unavailable"
        })
    })
}

/// One area as the overview shows it.
#[derive(Debug, PartialEq, Serialize)]
struct StatusArea {
    area: &'static str,
    state: &'static str,
    captured_at: Option<String>,
    last_attempt: Option<Attempt>,
    counts: Vec<CountValue>,
    update: &'static str,
}
#[derive(Debug, PartialEq, Serialize)]
struct Attempt {
    at: String,
    outcome: &'static str,
}
#[derive(Debug, PartialEq, Serialize)]
struct CountValue {
    kind: &'static str,
    value: u64,
}
#[derive(Debug, PartialEq, Serialize)]
pub struct Status {
    profile_id: String,
    areas: Vec<StatusArea>,
    /// The filing years the Borrador import offers, latest first.
    borrador_years: Vec<u16>,
}

/// The window's name for a backend area.
fn window_area(area: &str) -> Option<&'static str> {
    Some(match area {
        "census" => "census",
        "identity_checks" => "identity",
        "notifications" => "notifications",
        "iva_wallet" => "vat",
        "filed_declarations" => "filed",
        "borrador_100" => "borrador",
        _ => return None,
    })
}

fn instant(value: &Value) -> Result<Option<String>> {
    match value {
        Value::Null => Ok(None),
        Value::String(text) if (1..=64).contains(&text.len()) => Ok(Some(text.clone())),
        _ => Err(protocol()),
    }
}

/// The status read's result as the overview's areas: served states, instants
/// and counts only; its refusal names stay here.
fn status_reply(profile: &str, result: &Value, now: std::time::SystemTime) -> Result<Status> {
    let areas = result["status"]["areas"].as_array().ok_or_else(protocol)?;
    let areas = areas
        .iter()
        .map(|entry| {
            let backend = entry["area"].as_str().ok_or_else(protocol)?;
            let area = window_area(backend).ok_or_else(protocol)?;
            let state = match entry["state"].as_str() {
                Some("never_brought") => "never_brought",
                Some("current") => "current",
                Some("possibly_stale") => "possibly_stale",
                Some("unavailable") => "unavailable",
                _ => return Err(protocol()),
            };
            let last_attempt = match instant(&entry["last_attempt_at"])? {
                Some(at) => Some(Attempt {
                    at,
                    outcome: match entry["last_attempt_succeeded"].as_bool() {
                        Some(true) => "brought",
                        Some(false) => "failed",
                        None => return Err(protocol()),
                    },
                }),
                None => None,
            };
            let mut counts = Vec::new();
            if let Some(unread) = entry["unread_notification_count"].as_u64() {
                counts.push(CountValue {
                    kind: "unread_notifications",
                    value: unread,
                });
            }
            let periods = &entry["filed_periods"];
            if periods.is_object() {
                for (kind, key) in [
                    ("filed_matched", "matched"),
                    ("filed_aeat_only", "aeat_only"),
                    ("filed_local_only", "local_only"),
                    ("filed_differing", "differing"),
                ] {
                    let value = periods[key].as_u64().ok_or_else(protocol)?;
                    counts.push(CountValue { kind, value });
                }
            }
            Ok(StatusArea {
                area,
                state,
                captured_at: instant(&entry["last_brought_at"])?,
                last_attempt,
                counts,
                update: if area == "borrador" {
                    "import"
                } else {
                    "bring"
                },
            })
        })
        .collect::<Result<Vec<_>>>()?;
    Ok(Status {
        profile_id: profile.to_owned(),
        areas,
        borrador_years: borrador_years(result, now),
    })
}

/// What the profile holds per area, as the backend judged it, with states
/// never brought, current, possibly out of date or unavailable.
#[tauri::command]
pub async fn aeat_sync_status(
    host: State<'_, Arc<ProfileHost>>,
    language: String,
) -> Result<Status> {
    if !super::language::supported(&language) {
        return Err(invalid());
    }
    let person = host.person(None).await?;
    let profile = relay::profile_of(&person).await?;
    let result = read_status(&host, &person, &profile).await?;
    status_reply(&profile, &result, std::time::SystemTime::now())
}

/// The secure browser as the setup engine's row reads it.
#[derive(Debug, PartialEq, Serialize)]
#[serde(tag = "state", rename_all = "snake_case")]
enum Browser {
    Ready,
    Missing { bytes: Option<u64> },
    Attention,
}
#[derive(Debug, PartialEq, Serialize)]
pub struct Prepared {
    browser: Browser,
    access: &'static str,
}
/// The browser row as the preflight words it: what setup can install or
/// update is missing; anything else needs the row's own recovery.
fn browser(row: Option<&setup_wire::Row>) -> Browser {
    match row.map(|row| row.state) {
        Some(setup_wire::State::Ready) => Browser::Ready,
        Some(setup_wire::State::Absent | setup_wire::State::Stale) => Browser::Missing {
            bytes: row.and_then(|row| row.size_bytes),
        },
        _ => Browser::Attention,
    }
}

/// Whether the secure browser and the AEAT access are ready to sign in. It
/// reaches no network.
#[tauri::command]
pub async fn aeat_sync_prepare(
    host: State<'_, Arc<ProfileHost>>,
    setup: State<'_, Arc<SetupHost>>,
) -> Result<Prepared> {
    let person = host.person(None).await?;
    let profile = relay::profile_of(&person).await?;
    if admitted(admitted::READINESS).is_none() {
        return Err(bare("unavailable"));
    }
    let ready = {
        let _serial = host.serial().await;
        censo::readiness(&host, &person, &profile)
            .await
            .map_err(|_| bare("unavailable"))?
            .ready
    };
    let row = setup.browser_row(PREPARE_LIMIT).await;
    Ok(Prepared {
        browser: browser(row.as_ref()),
        access: if ready { "ready" } else { "needs_access" },
    })
}

/// What a sign-in waits on, while it does.
#[derive(Clone, Copy, Debug, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum SignInStage {
    WaitingForPhone,
}

/// How a settled sign-in reads for the window.
fn signed_in(p: &Value, result: Option<&Value>) -> Result<()> {
    match outcome::terminal(p) {
        None => match result {
            Some(result) if result["result"]["authenticated"] == true => Ok(()),
            Some(_) => Err(bare("refused")),
            None => Err(bare("unavailable")),
        },
        Some(Outcome::Failed(Reason::NoAccess)) => Err(bare("needs_access")),
        Some(Outcome::Failed(_)) => Err(bare("refused")),
        Some(_) => Err(bare("unavailable")),
    }
}

/// Signs in to AEAT with the profile's configured method, reusing a valid
/// session, including one made in the in-app browser. `progress` is told
/// when it waits on the person's phone.
#[tauri::command]
pub async fn aeat_sync_sign_in(
    host: State<'_, Arc<ProfileHost>>,
    progress: Channel<SignInStage>,
) -> Result<()> {
    let person = host.person(None).await?;
    let profile = relay::profile_of(&person).await?;
    let waiting = Arc::new(tokio::sync::Notify::new());
    *lock(&host.aeat_sync().sign_in) = Some(waiting.clone());
    let definition = "auth.session.acquire";
    let mut events = host.sign_in().person_events();
    let subject = relay::subject(&profile);
    let (readiness, submitted) = {
        let _serial = host.serial().await;
        let readiness = censo::readiness(&host, &person, &profile)
            .await
            .map_err(|_| bare("unavailable"))?;
        if !readiness.ready {
            return Err(bare("needs_access"));
        }
        let submitted = relay::submit(&person, definition, &subject, json!({}), true).await;
        (readiness, submitted)
    };
    let operation = match submitted {
        Ok(operation) => operation,
        Err(refused) if refused.code == "refused" => {
            return Err(match outcome::reason(refused.reason.as_deref()) {
                Reason::NoAccess => bare("needs_access"),
                _ => bare("refused"),
            });
        }
        Err(_) => return Err(bare("unavailable")),
    };
    if readiness.provider == "clave_movil" {
        let _ = progress.send(SignInStage::WaitingForPhone);
    }
    let relayed = relay::Relayed {
        person: &person,
        operation,
        definition,
        subject,
    };
    // The acquisition itself cannot be cancelled: a stop ends this wait, and
    // the session it may still make is reused by the next sign-in.
    let followed = tokio::select! {
        followed = relay::follow(&mut events, &relayed, |_| false) => followed,
        () = waiting.notified() => return Err(bare("cancelled")),
    };
    lock(&host.aeat_sync().sign_in).take();
    let p = followed.map_err(|_| bare("unavailable"))?;
    let result = if outcome::terminal(&p).is_none() {
        relay::result(&relayed)
            .await
            .ok()
            .map(|document| document["projection"].clone())
    } else {
        None
    };
    signed_in(&p, result.as_ref())
}

/// Stops a sign-in that waits on the person's phone.
#[tauri::command]
pub fn aeat_sync_sign_in_cancel(host: State<'_, Arc<ProfileHost>>) {
    if let Some(waiting) = lock(&host.aeat_sync().sign_in).take() {
        waiting.notify_one();
    }
}

/// Starts the run for `request`, or reattaches to the one still going on.
/// The request is read here, so a malformed one is refused with a code.
#[tauri::command]
pub async fn aeat_sync_start(
    host: State<'_, Arc<ProfileHost>>,
    profile: String,
    request: Value,
) -> Result<()> {
    let plan = serde_json::from_value::<Selection>(request)
        .map_err(|_| invalid())?
        .admit()?;
    let person = held(&host, &profile).await?;
    let identity = relay::identity(&person).await?;
    let sync = host.aeat_sync();
    if let Some(fresh) = sync.begin(&identity, &plan) {
        sync.drive(&host, person, profile, identity, &fresh);
        sync.changed();
    }
    Ok(())
}

/// The run of the window's session and its person.
/// The window's session: its person, their identity and their run.
type Session = (HeldPerson, Value, Option<Arc<Mutex<Run>>>);

async fn session(host: &ProfileHost, profile: &str) -> Result<Session> {
    let person = held(host, profile).await?;
    let identity = relay::identity(&person).await?;
    let run = host.aeat_sync().current(&identity);
    Ok((person, identity, run))
}

/// The run now going on or last ended: each area's items and their closed
/// outcomes; null before any.
#[tauri::command]
pub async fn aeat_sync_progress(
    host: State<'_, Arc<ProfileHost>>,
    profile: String,
) -> Result<Option<Snapshot>> {
    let (_, _, run) = session(&host, &profile).await?;
    Ok(run.map(|run| run::lock(&run).snapshot()))
}

/// Cues the window to read the run, its results and the overview again.
#[tauri::command]
pub fn aeat_sync_observe(host: State<'_, Arc<ProfileHost>>, updates: Channel<()>) -> u32 {
    let sync = host.aeat_sync();
    let mut changes = sync.changes.subscribe();
    let mut events = host.sign_in().person_events();
    sync.observer
        .observe(host.is_closed(), updates, |updates| async move {
            loop {
                tokio::select! {
                    changed = changes.changed() => if changed.is_err() { break },
                    event = events.recv() => match event {
                        Ok(PersonEvent::RecordsChanged | PersonEvent::Retired)
                        | Err(tokio::sync::broadcast::error::RecvError::Lagged(_)) => {}
                        Err(tokio::sync::broadcast::error::RecvError::Closed) => break,
                        _ => continue,
                    },
                }
                if updates.send(()).is_err() {
                    break;
                }
            }
        })
}

/// Ends the cue `subscription`.
#[tauri::command]
pub fn aeat_sync_unobserve(host: State<'_, Arc<ProfileHost>>, subscription: u32) {
    host.aeat_sync().observer.unobserve(subscription);
}

/// Lets the item in flight settle and starts nothing further.
#[tauri::command]
pub async fn aeat_sync_stop(host: State<'_, Arc<ProfileHost>>, profile: String) -> Result<()> {
    let (_, _, run) = session(&host, &profile).await?;
    if let Some(run) = run {
        run::lock(&run).stop();
        host.aeat_sync().changed();
    }
    Ok(())
}

fn refusal(refused: run::Refusal) -> Failure {
    bare(match refused {
        run::Refusal::Invalid => "invalid",
        run::Refusal::Refused => "refused",
        run::Refusal::Unknown => "unknown",
    })
}

/// Reads one area again, or one of its items, on the person's request. An
/// item whose outcome is unknown is read again only once the person was told
/// it may already have been brought.
#[tauri::command]
pub async fn aeat_sync_retry(
    host: State<'_, Arc<ProfileHost>>,
    profile: String,
    area: Area,
    item: Option<u32>,
    acknowledged_unknown: Option<bool>,
) -> Result<()> {
    let (person, identity, run) = session(&host, &profile).await?;
    let run = run.ok_or_else(invalid)?;
    let follow = run::lock(&run)
        .retry(area, item, acknowledged_unknown == Some(true))
        .map_err(refusal)?;
    if follow {
        host.aeat_sync()
            .drive(&host, person, profile, identity, &run);
    }
    host.aeat_sync().changed();
    Ok(())
}

/// Carries a paused run on from the first item not brought, once the person
/// signed in again.
#[tauri::command]
pub async fn aeat_sync_resume(host: State<'_, Arc<ProfileHost>>, profile: String) -> Result<()> {
    let (person, identity, run) = session(&host, &profile).await?;
    let run = run.ok_or_else(|| bare("refused"))?;
    let follow = run::lock(&run).resume().map_err(refusal)?;
    if follow {
        host.aeat_sync()
            .drive(&host, person, profile, identity, &run);
    }
    host.aeat_sync().changed();
    Ok(())
}

/// One failed part, by its retry address.
#[derive(Debug, PartialEq, Serialize)]
struct FailedPart {
    part: u32,
    year: Option<u16>,
    reason: Reason,
}
/// What the run brought for one area.
#[derive(Debug, PartialEq, Serialize)]
struct AreaResult {
    area: Area,
    outcome: &'static str,
    at: Option<String>,
    new_count: u64,
    changed_count: u64,
    failed: Vec<FailedPart>,
    review_pending: bool,
}
#[derive(Debug, PartialEq, Serialize)]
pub struct Results {
    areas: Vec<AreaResult>,
    /// The filed declarations set against the profile's own records, as the
    /// status read classified them.
    filed: Vec<FiledRow>,
    /// The filing years the Borrador import offers, latest first.
    borrador_years: Vec<u16>,
}

/// One filed declaration as the window lists it, without identifiers: the
/// profile's own record, what AEAT showed and the receipt stay apart.
#[derive(Debug, PartialEq, Serialize)]
pub struct FiledRow {
    form: String,
    year: u16,
    period: Option<String>,
    #[serde(rename = "match")]
    group: &'static str,
    record: Option<FiledRecord>,
    aeat: Option<FiledSeen>,
    receipt: &'static str,
    differences: Vec<&'static str>,
}
#[derive(Debug, PartialEq, Serialize)]
struct FiledRecord {
    status: &'static str,
    on: String,
}
#[derive(Debug, PartialEq, Serialize)]
struct FiledSeen {
    seen_on: String,
}

/// One served filed row in the window's closed words.
fn filed_row(row: &Value) -> Result<FiledRow> {
    let form = row["modelo"]
        .as_str()
        .filter(|form| {
            FORM_LENGTH.contains(&form.len()) && form.bytes().all(|b| b.is_ascii_alphanumeric())
        })
        .ok_or_else(protocol)?
        .to_owned();
    let year = row["filing_year"]
        .as_u64()
        .and_then(|year| u16::try_from(year).ok())
        .filter(|year| YEARS.contains(year))
        .ok_or_else(protocol)?;
    let period = match &row["period"] {
        Value::Null => None,
        Value::String(period)
            if (1..=8).contains(&period.len())
                && period.bytes().all(|b| b.is_ascii_alphanumeric()) =>
        {
            Some(period.clone())
        }
        _ => return Err(protocol()),
    };
    let group = match row["match"].as_str() {
        Some("matched") => "matched",
        Some("aeat_only") => "aeat_only",
        Some("local_only") => "local_only",
        Some("differing") => "differing",
        _ => return Err(protocol()),
    };
    let record = match (
        row["local_record"].as_str(),
        instant(&row["local_record_at"])?,
    ) {
        (Some("none"), None) => None,
        (Some("draft"), Some(on)) => Some(FiledRecord {
            status: "draft",
            on,
        }),
        (Some("marked_filed"), Some(on)) => Some(FiledRecord {
            status: "marked_filed",
            on,
        }),
        _ => return Err(protocol()),
    };
    let aeat = instant(&row["aeat_shown_at"])?.map(|seen_on| FiledSeen { seen_on });
    let receipt = match row["receipt_confirmed"].as_bool() {
        Some(true) if aeat.is_some() => "confirmed",
        Some(false) => "not_confirmed",
        _ => return Err(protocol()),
    };
    let differences = row["differences"]
        .as_array()
        .ok_or_else(protocol)?
        .iter()
        .map(|difference| match difference.as_str() {
            Some("status") => Ok("status"),
            _ => Err(protocol()),
        })
        .collect::<Result<Vec<_>>>()?;
    Ok(FiledRow {
        form,
        year,
        period,
        group,
        record,
        aeat,
        receipt,
        differences,
    })
}

/// The status read's filed rows; none while filed declarations were never
/// read from AEAT.
fn filed_rows(result: &Value) -> Result<Vec<FiledRow>> {
    let areas = result["status"]["areas"].as_array().ok_or_else(protocol)?;
    let area = areas
        .iter()
        .find(|entry| entry["area"] == "filed_declarations")
        .ok_or_else(protocol)?;
    match &area["filed_rows"] {
        Value::Null => Ok(Vec::new()),
        Value::Array(rows) if rows.len() <= FILED_LIMIT => rows.iter().map(filed_row).collect(),
        _ => Err(protocol()),
    }
}

/// The run's settled areas, each at the instant the status read last saw it
/// brought, beside the served filed rows and Borrador years.
fn results_reply(run: Option<&Run>, status: Status, filed: Vec<FiledRow>) -> Results {
    let Some(run) = run else {
        return Results {
            areas: Vec::new(),
            filed,
            borrador_years: status.borrador_years,
        };
    };
    let areas = run
        .areas
        .iter()
        .filter_map(|area| {
            let worst = area.outcome()?;
            let settled: Vec<_> = area
                .items
                .iter()
                .filter_map(|item| item.outcome().map(|o| (item, o)))
                .collect();
            let name = serde_json::to_value(area.area).ok()?;
            let at = status
                .areas
                .iter()
                .find(|entry| name == entry.area)
                .and_then(|entry| entry.captured_at.clone());
            let total = settled
                .iter()
                .fold(Counts::default(), |sum, (item, _)| Counts {
                    new: sum.new + item.counts.new,
                    changed: sum.changed + item.counts.changed,
                });
            Some(AreaResult {
                area: area.area,
                outcome: worst.word(),
                at,
                new_count: total.new,
                changed_count: total.changed,
                failed: settled
                    .iter()
                    .filter_map(|(item, outcome)| match outcome {
                        Outcome::Failed(reason) => Some(FailedPart {
                            part: item.id,
                            year: item.year,
                            reason: *reason,
                        }),
                        _ => None,
                    })
                    .collect(),
                review_pending: settled.iter().any(|(item, _)| item.review_pending),
            })
        })
        .collect();
    Results {
        areas,
        filed,
        borrador_years: status.borrador_years,
    }
}

/// What the last reads came to, per area, from the run and the profile's own
/// records; it reaches no network.
#[tauri::command]
pub async fn aeat_sync_results(
    host: State<'_, Arc<ProfileHost>>,
    profile: String,
    language: String,
) -> Result<Results> {
    if !super::language::supported(&language) {
        return Err(invalid());
    }
    let (person, _, run) = session(&host, &profile).await?;
    let result = read_status(&host, &person, &profile).await?;
    let status = status_reply(&profile, &result, std::time::SystemTime::now())?;
    let filed = filed_rows(&result)?;
    Ok(match run {
        Some(run) => results_reply(Some(&run::lock(&run)), status, filed),
        None => results_reply(None, status, filed),
    })
}

/// One notification as the window lists it, without identifiers.
#[derive(Debug, PartialEq, Serialize)]
pub struct NotificationRow {
    subject: String,
    sender: &'static str,
    received_on: String,
    read: bool,
    read_on: Option<String>,
}

fn text(value: &Value) -> Result<String> {
    value
        .as_str()
        .filter(|text| text.len() <= TEXT_LIMIT)
        .map(str::to_owned)
        .ok_or_else(protocol)
}

/// The rows of the latest notifications capture, with read state only. The
/// notifications listed are those of AEAT's own mailbox.
fn notification_rows(shown: &Value) -> Result<Vec<NotificationRow>> {
    let rows = shown["rows"].as_array().ok_or_else(protocol)?;
    rows.iter()
        .take(NOTIFICATION_LIMIT)
        .map(|row| {
            let read = row["leida"] == true;
            Ok(NotificationRow {
                subject: text(&row["concepto"])?,
                sender: "AEAT",
                received_on: text(&row["fecha_emision"])?,
                read,
                read_on: if read && row["fecha_notificacion"].is_string() {
                    Some(text(&row["fecha_notificacion"])?)
                } else {
                    None
                },
            })
        })
        .collect()
}

/// The notification rows with their read state, without identifiers: the
/// profile views' own read of the latest capture.
#[tauri::command]
pub async fn aeat_sync_notifications(
    host: State<'_, Arc<ProfileHost>>,
    profile: String,
) -> Result<Vec<NotificationRow>> {
    let (_, shown) = host
        .notifications_read(Some(&profile))
        .await
        .map_err(|failure| {
            bare(if failure.code == "not_signed_in" {
                "not_signed_in"
            } else {
                "unavailable"
            })
        })?;
    match shown {
        Some(shown) => notification_rows(&shown),
        None => Ok(Vec::new()),
    }
}

/// A Borrador PDF picked in the native dialog: its token and file name.
#[derive(Debug, Serialize)]
pub struct BorradorFile {
    token: String,
    name: String,
}

/// Opens the native dialog for a Borrador 100 PDF; null when it closes
/// without a choice. The path stays in the host.
#[tauri::command]
pub async fn aeat_sync_borrador_pick<R: tauri::Runtime>(
    host: State<'_, Arc<ProfileHost>>,
    window: tauri::WebviewWindow<R>,
) -> Result<Option<BorradorFile>> {
    let picked = host
        .pick_one(window, Purpose::Borrador, BORRADOR_KINDS)
        .await?;
    Ok(picked.map(|picked| BorradorFile {
        token: picked.token,
        name: picked.name,
    }))
}

/// Imports a Borrador 100 document the person picked, named by its file
/// token, for the filing year the person chose.
#[tauri::command]
pub async fn aeat_sync_borrador_import(
    host: State<'_, Arc<ProfileHost>>,
    profile: String,
    file: String,
    year: Option<u16>,
) -> Result<&'static str> {
    let year = year
        .filter(|year| YEARS.contains(year))
        .ok_or_else(invalid)?;
    let person = held(&host, &profile).await?;
    let path = host.picked(&person, &file, Purpose::Borrador).await?;
    let payload = json!({
        "profile_id": profile,
        "source_path": super::picked_files::path_text(&path)?,
        "filing_year": year,
        "period": {"filing_year": year, "code": BORRADOR_PERIOD},
    });
    let imported = {
        let _serial = host.serial().await;
        host.run(&person, "live.borrador.100.import", payload, true)
            .await
    };
    Ok(match imported {
        Ok(result) if result["snapshot"]["binding_count"].as_u64() == Some(0) => "nothing_found",
        Ok(result) if result["snapshot"].is_object() => "imported",
        Ok(_) => return Err(bare("unknown")),
        Err(failure) if failure.code == "unknown" || failure.code == "saved_unread" => {
            return Err(bare("unknown"));
        }
        Err(_) => "failed",
    })
}

pub fn commands<R: tauri::Runtime>() -> crate::app::Commands<R> {
    crate::app::commands![
        aeat_sync_status,
        aeat_sync_prepare,
        aeat_sync_sign_in,
        aeat_sync_sign_in_cancel,
        aeat_sync_start,
        aeat_sync_progress,
        aeat_sync_observe,
        aeat_sync_unobserve,
        aeat_sync_stop,
        aeat_sync_retry,
        aeat_sync_resume,
        aeat_sync_results,
        aeat_sync_notifications,
        aeat_sync_borrador_pick,
        aeat_sync_borrador_import
    ]
}

#[cfg(test)]
mod tests;
