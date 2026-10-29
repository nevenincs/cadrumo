//! The AEAT sync page's host side: named commands over the held person's
//! relay that bring AEAT data into the signed-in profile. Each command takes
//! the exact profile it was opened for and refuses a window that has switched
//! accounts. The host submits only the closed list of reads in [`admitted`];
//! it holds no tax rule, and nothing here submits a return.
//!
//! The window receives closed states and outcomes only, never an operation,
//! snapshot or row identifier.
mod admitted;

use super::relay::{Failure, Result, protocol};
use super::user_profile::ProfileHost;
use crate::agent::person::HeldPerson;
use admitted::{Area, admitted};
use serde::Deserialize;
use serde_json::Value;
use std::sync::Arc;
use tauri::{State, ipc::Channel};

/// The most areas, years and forms one selection may name.
const SELECTION_LIMIT: usize = 64;
/// A modelo number: short, ASCII and alphanumeric.
const FORM_LENGTH: std::ops::RangeInclusive<usize> = 1..=5;
/// A calendar year as four digits; the years on offer are the backend's.
const YEARS: std::ops::RangeInclusive<u16> = 1000..=9999;

/// What the person chose to bring, as the window sends it.
#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub(crate) struct Selection {
    areas: Vec<Area>,
    /// The years for filed declarations and the VAT balance carried forward.
    #[serde(default)]
    years: Vec<u16>,
    /// The forms to narrow filed declarations to; none means all discovered.
    #[serde(default)]
    forms: Vec<String>,
    /// Reads filed declarations from AEAT and saves nothing.
    #[serde(default)]
    dry_run: bool,
}

/// A selection the host accepts: its areas in run order, once each, and every
/// definition they submit on the closed list.
#[derive(Debug, PartialEq, Eq)]
pub(crate) struct Plan {
    pub(crate) areas: Vec<Area>,
    pub(crate) years: Vec<u16>,
    pub(crate) forms: Vec<String>,
    pub(crate) dry_run: bool,
}
impl Selection {
    pub(crate) fn admit(self) -> Result<Plan> {
        let Self {
            areas,
            mut years,
            mut forms,
            dry_run,
        } = self;
        if areas.len() > SELECTION_LIMIT
            || years.len() > SELECTION_LIMIT
            || forms.len() > SELECTION_LIMIT
            || !years.iter().all(|year| YEARS.contains(year))
            || !forms.iter().all(|form| {
                FORM_LENGTH.contains(&form.len()) && form.bytes().all(|b| b.is_ascii_alphanumeric())
            })
        {
            return Err(invalid());
        }
        // A dry run reads filed declarations only; every other area is left
        // out of it rather than refused.
        let mut areas: Vec<Area> = Area::ORDER
            .into_iter()
            .filter(|area| areas.contains(area) && (!dry_run || *area == Area::Filed))
            .collect();
        areas.dedup();
        years.sort_unstable();
        years.dedup();
        forms.sort_unstable();
        forms.dedup();
        let needs_years = areas
            .iter()
            .any(|area| matches!(area, Area::Vat | Area::Filed));
        let closed = areas
            .iter()
            .flat_map(|area| area.definitions())
            .all(|id| admitted(id).is_some());
        if areas.is_empty() || (needs_years && years.is_empty()) || !closed {
            return Err(invalid());
        }
        Ok(Plan {
            areas,
            years,
            forms,
            dry_run,
        })
    }
}

fn invalid() -> Failure {
    Failure::new("invalid")
}

/// The held person for exactly `profile`, or the refusal that the window's
/// account is not the one signed in.
async fn held(host: &ProfileHost, profile: &str) -> Result<HeldPerson> {
    host.person(Some(profile)).await
}

/// Not built yet: the commands below are named and admitted here and answer
/// `unavailable` until the run is attached to them.
fn unbuilt<T>() -> Result<T> {
    Err(protocol())
}

/// What the signed-in profile holds per area, as the backend judged it:
/// `{ profile_id, areas: [{ area, state, captured_at, last_attempt, counts,
/// update }] }`, with the states never brought, current, possibly out of date
/// or unavailable.
#[tauri::command]
pub async fn aeat_sync_status(
    host: State<'_, Arc<ProfileHost>>,
    language: String,
) -> Result<Value> {
    if !super::language::supported(&language) {
        return Err(invalid());
    }
    host.person(None).await?;
    unbuilt()
}

/// Whether the secure browser and the AEAT access are ready to sign in.
#[tauri::command]
pub async fn aeat_sync_prepare(
    host: State<'_, Arc<ProfileHost>>,
    profile: String,
) -> Result<Value> {
    held(&host, &profile).await?;
    unbuilt()
}

/// Signs in to AEAT with the profile's configured method, reusing a valid
/// session.
#[tauri::command]
pub async fn aeat_sync_sign_in(
    host: State<'_, Arc<ProfileHost>>,
    profile: String,
) -> Result<Value> {
    held(&host, &profile).await?;
    unbuilt()
}

/// Starts the run for `request`, or reattaches to the one already running.
/// The request is read here, so a malformed one is refused with a code.
#[tauri::command]
pub async fn aeat_sync_start(
    host: State<'_, Arc<ProfileHost>>,
    profile: String,
    request: Value,
) -> Result<()> {
    let _plan = serde_json::from_value::<Selection>(request)
        .map_err(|_| invalid())?
        .admit()?;
    held(&host, &profile).await?;
    unbuilt()
}

/// Where the run stands: each area's items and their closed outcomes.
#[tauri::command]
pub async fn aeat_sync_progress(
    host: State<'_, Arc<ProfileHost>>,
    profile: String,
) -> Result<Value> {
    held(&host, &profile).await?;
    unbuilt()
}

/// Cues the window to read the run's progress again when it changes.
#[tauri::command]
pub fn aeat_sync_observe(updates: Channel<()>) -> u32 {
    updates.id()
}

/// Ends the cue `subscription`.
#[tauri::command]
pub fn aeat_sync_unobserve(subscription: u32) {
    let _ = subscription;
}

/// Lets the item in flight settle and starts nothing further.
#[tauri::command]
pub async fn aeat_sync_stop(host: State<'_, Arc<ProfileHost>>, profile: String) -> Result<Value> {
    held(&host, &profile).await?;
    unbuilt()
}

/// Runs one area again, or one of its items, on the person's request.
#[tauri::command]
pub async fn aeat_sync_retry(
    host: State<'_, Arc<ProfileHost>>,
    profile: String,
    area: Area,
    item: Option<u32>,
) -> Result<Value> {
    held(&host, &profile).await?;
    let _ = (area, item);
    unbuilt()
}

/// The notification rows with their read state, without identifiers.
#[tauri::command]
pub async fn aeat_sync_notifications(
    host: State<'_, Arc<ProfileHost>>,
    profile: String,
) -> Result<Value> {
    held(&host, &profile).await?;
    unbuilt()
}

/// Imports a Borrador 100 document the person picked, named by its file token.
#[tauri::command]
pub async fn aeat_sync_borrador_import(
    host: State<'_, Arc<ProfileHost>>,
    profile: String,
    file: String,
) -> Result<Value> {
    held(&host, &profile).await?;
    let _ = file;
    unbuilt()
}

pub fn commands<R: tauri::Runtime>() -> crate::app::Commands<R> {
    crate::app::commands![
        aeat_sync_status,
        aeat_sync_prepare,
        aeat_sync_sign_in,
        aeat_sync_start,
        aeat_sync_progress,
        aeat_sync_observe,
        aeat_sync_unobserve,
        aeat_sync_stop,
        aeat_sync_retry,
        aeat_sync_notifications,
        aeat_sync_borrador_import
    ]
}

#[cfg(test)]
mod tests;
