//! Named read-only views of the signed-in profile: the filing calendar and
//! the counts of the last notifications capture. Each runs fixed registered
//! reads over the held person's relay; the window names no operation. Nothing
//! read here is kept, logged or written: it is passed on and dropped.
use super::{Failure, PROFILE_READ_LIMIT, ProfileHost, Result, protocol};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};

#[derive(Debug, Serialize)]
pub struct NotificationsSummary {
    captured_at: Option<String>,
    row_count: u64,
    unread: u64,
}

#[derive(Deserialize)]
struct Latest {
    snapshot_id: Option<String>,
    captured_at: Option<String>,
    row_count: Option<u64>,
}
#[derive(Deserialize)]
struct Shown {
    snapshot_id: String,
    captured_at: String,
    row_count: u64,
    rows: Vec<Row>,
}
// The rows also carry names and tax numbers. Only whether each was read is
// taken from them.
#[derive(Deserialize)]
struct Row {
    leida: Option<bool>,
}

#[derive(Debug, Deserialize, Serialize, PartialEq)]
#[serde(rename_all = "snake_case")]
enum UserState {
    Due,
    Late,
    Filed,
    Unknown,
}
#[derive(Debug, Deserialize, Serialize, PartialEq)]
#[serde(rename_all = "snake_case")]
enum LocalFilingState {
    NotReadyToFile,
    ReadyToFile,
    ExternalBaselineImported,
}
#[derive(Debug, Deserialize, Serialize, PartialEq)]
#[serde(rename_all = "snake_case")]
enum AeatSubmissionState {
    NotObserved,
    SubmittedObserved,
    Accepted,
    JustificanteVerified,
}
#[derive(Debug, Deserialize, Serialize, PartialEq)]
#[serde(rename_all = "snake_case")]
enum EventType {
    Filing,
    Message,
}
#[derive(Debug, Deserialize, Serialize, PartialEq)]
#[serde(rename_all = "snake_case")]
enum AdviceReason {
    ApplicableWindowMissing,
    ApplicabilityUndetermined,
    RegistryUnmodeled,
}

#[derive(Debug, Deserialize, Serialize, PartialEq)]
struct Range {
    from_date: String,
    to_date: String,
}
#[derive(Deserialize)]
struct Evidence {
    local_filing_state: LocalFilingState,
    aeat_submission_state: AeatSubmissionState,
    justificante_verified: bool,
}
#[derive(Deserialize)]
struct EntryIn {
    modelo: String,
    period: String,
    opens_on: String,
    closes_on: String,
    adjusted_closes_on: String,
    shift_reason: String,
    payment_cutoff_on: Option<String>,
    evaluated_on: String,
    days_overdue: Option<u64>,
    user_state: UserState,
    filing_evidence: Evidence,
}
#[derive(Debug, Serialize)]
struct Entry {
    modelo: String,
    period: String,
    opens_on: Option<String>,
    closes_on: String,
    adjusted_closes_on: String,
    shift_reason: String,
    payment_cutoff_on: Option<String>,
    evaluated_on: String,
    days_overdue: Option<u64>,
    user_state: UserState,
    local_filing_state: LocalFilingState,
    aeat_submission_state: AeatSubmissionState,
    justificante_verified: bool,
}
#[derive(Debug, Deserialize, Serialize)]
struct Event {
    event_type: EventType,
    event_date: String,
    source: String,
    summary: String,
    reference_id: String,
    status: Option<String>,
    aeat_submission_state: Option<AeatSubmissionState>,
    aeat_submitted_at: Option<String>,
    justificante_verified: Option<bool>,
}
#[derive(Deserialize)]
struct WarningIn {
    code: String,
    // The product's sentence in the read's language; `message` is its key.
    text: String,
    affected_modelos: Vec<String>,
}
#[derive(Debug, Serialize)]
struct Warning {
    code: String,
    message: String,
    affected_modelos: Vec<String>,
}
#[derive(Debug, Deserialize, Serialize)]
struct Advised {
    modelo: String,
    reason: AdviceReason,
}
#[derive(Debug, Deserialize, Serialize)]
struct Coverage {
    surfaced: Vec<String>,
    confidently_excluded: Vec<String>,
    advised: Vec<Advised>,
    out_of_scope: Vec<String>,
}
#[derive(Deserialize)]
struct Snapshot {
    range: Range,
    entries: Vec<EntryIn>,
    events: Vec<Event>,
    warnings: Vec<WarningIn>,
    generated_at: String,
    taxpayer_model_declared: bool,
    incomplete_reason: Option<String>,
    coverage: Coverage,
}
#[derive(Deserialize)]
struct CalendarRead {
    kind: String,
    calendar: Option<Snapshot>,
}
#[derive(Deserialize)]
struct Projection {
    profile_id: String,
    payload: CalendarRead,
}

/// The calendar as the shell's `FilingCalendar` type has it.
#[derive(Debug, Serialize)]
pub struct FilingCalendar {
    range: Range,
    entries: Vec<Entry>,
    events: Vec<Event>,
    warnings: Vec<Warning>,
    generated_at: Option<String>,
    coverage: Coverage,
}

/// A calendar day as the product writes it, `YYYY-MM-DD`, as its year.
fn iso_year(day: &str) -> Option<u32> {
    let bytes = day.as_bytes();
    let digits = |range: std::ops::Range<usize>| bytes[range].iter().all(u8::is_ascii_digit);
    if bytes.len() != 10 || bytes[4] != b'-' || bytes[7] != b'-' {
        return None;
    }
    if !digits(0..4) || !digits(5..7) || !digits(8..10) {
        return None;
    }
    let month: u32 = day[5..7].parse().ok()?;
    let date: u32 = day[8..10].parse().ok()?;
    if !(1..=12).contains(&month) || !(1..=31).contains(&date) {
        return None;
    }
    day[..4].parse().ok()
}

/// The window asks for about a year around today; a longer range is refused
/// rather than read, so the answer stays bounded.
fn admit_range(from: &str, to: &str) -> Result<()> {
    match (iso_year(from), iso_year(to)) {
        (Some(start), Some(end)) if from <= to && end - start <= 1 => Ok(()),
        _ => Err(Failure::new("refused")),
    }
}

fn notifications_summary(latest: Value, shown: Option<Value>) -> Result<NotificationsSummary> {
    let latest: Latest = serde_json::from_value(latest).map_err(|_| protocol())?;
    let Some(snapshot_id) = latest.snapshot_id else {
        // Never captured: not the same as nothing unread.
        return Ok(NotificationsSummary {
            captured_at: None,
            row_count: 0,
            unread: 0,
        });
    };
    let shown: Shown =
        serde_json::from_value(shown.ok_or_else(protocol)?).map_err(|_| protocol())?;
    if shown.snapshot_id != snapshot_id
        || Some(&shown.captured_at) != latest.captured_at.as_ref()
        || Some(shown.row_count) != latest.row_count
        || shown.rows.len() as u64 != shown.row_count
    {
        return Err(protocol());
    }
    Ok(NotificationsSummary {
        captured_at: Some(shown.captured_at),
        row_count: shown.row_count,
        // A row whose read mark was not captured is not counted as unread.
        unread: shown
            .rows
            .iter()
            .filter(|row| row.leida == Some(false))
            .count() as u64,
    })
}

fn filing_calendar(
    projection: Value,
    profile: &str,
    from: &str,
    to: &str,
) -> Result<FilingCalendar> {
    let projection: Projection = serde_json::from_value(projection).map_err(|_| protocol())?;
    let snapshot = match projection.payload {
        CalendarRead {
            kind,
            calendar: Some(snapshot),
        } if kind == "calendar" && projection.profile_id == profile => snapshot,
        _ => return Err(protocol()),
    };
    if snapshot.range.from_date != from || snapshot.range.to_date != to {
        return Err(protocol());
    }
    let mut warnings: Vec<Warning> = snapshot
        .warnings
        .into_iter()
        .map(|warning| Warning {
            code: warning.code,
            message: warning.text,
            affected_modelos: warning.affected_modelos,
        })
        .collect();
    // Without the taxpayer's model the product places no obligation: say so,
    // in its own words, rather than show an empty calendar.
    if !snapshot.taxpayer_model_declared {
        warnings.insert(
            0,
            Warning {
                code: "taxpayer_model_undeclared".into(),
                message: snapshot.incomplete_reason.ok_or_else(protocol)?,
                affected_modelos: Vec::new(),
            },
        );
    }
    Ok(FilingCalendar {
        range: snapshot.range,
        entries: snapshot
            .entries
            .into_iter()
            .map(|entry| Entry {
                modelo: entry.modelo,
                period: entry.period,
                opens_on: Some(entry.opens_on),
                closes_on: entry.closes_on,
                adjusted_closes_on: entry.adjusted_closes_on,
                shift_reason: entry.shift_reason,
                payment_cutoff_on: entry.payment_cutoff_on,
                evaluated_on: entry.evaluated_on,
                days_overdue: entry.days_overdue,
                user_state: entry.user_state,
                local_filing_state: entry.filing_evidence.local_filing_state,
                aeat_submission_state: entry.filing_evidence.aeat_submission_state,
                justificante_verified: entry.filing_evidence.justificante_verified,
            })
            .collect(),
        events: snapshot.events,
        warnings,
        generated_at: Some(snapshot.generated_at),
        coverage: snapshot.coverage,
    })
}

impl ProfileHost {
    async fn profile_of(person: &crate::agent::person::HeldPerson) -> Result<String> {
        Ok(Self::identity(person).await?["profile_id"]
            .as_str()
            .ok_or_else(protocol)?
            .to_owned())
    }
    /// Rejects an answer read while the window's account changed underneath.
    async fn still_held(
        &self,
        person: &crate::agent::person::HeldPerson,
        profile: &str,
    ) -> Result<()> {
        let current = self.person(Some(profile)).await?;
        if Self::identity(&current).await? != Self::identity(person).await? {
            return Err(Failure::new("not_signed_in"));
        }
        Ok(())
    }
    pub(super) async fn notifications(&self) -> Result<NotificationsSummary> {
        let (latest, shown) = self.notifications_read(None).await?;
        notifications_summary(latest, shown)
    }
    /// The latest notifications capture and, where there is one, its shown
    /// rows, for exactly `profile` or the signed-in one. It reads under the
    /// serial lock within the read limit, and refuses an answer read while
    /// the window's account changed underneath.
    pub(crate) async fn notifications_read(
        &self,
        profile: Option<&str>,
    ) -> Result<(Value, Option<Value>)> {
        tokio::time::timeout(PROFILE_READ_LIMIT, async {
            let _serial = self.operation.lock().await;
            let person = self.person(profile).await?;
            let profile = Self::profile_of(&person).await?;
            let latest = self
                .run(
                    &person,
                    "live.notifications.latest",
                    json!({"profile_id":profile}),
                    false,
                )
                .await?;
            let shown = match latest["snapshot_id"].as_str() {
                Some(snapshot_id) => Some(
                    self.run(
                        &person,
                        "live.notifications.show",
                        json!({"profile_id":profile, "snapshot_id":snapshot_id}),
                        false,
                    )
                    .await?,
                ),
                None => None,
            };
            self.still_held(&person, &profile).await?;
            Ok((latest, shown))
        })
        .await
        .unwrap_or_else(|_| Err(protocol()))
    }
    pub(super) async fn filing_calendar(
        &self,
        from: String,
        to: String,
        language: String,
    ) -> Result<FilingCalendar> {
        if !super::super::language::supported(&language) {
            return Err(protocol());
        }
        admit_range(&from, &to)?;
        tokio::time::timeout(PROFILE_READ_LIMIT, async {
            let _serial = self.operation.lock().await;
            let person = self.person(None).await?;
            let profile = Self::profile_of(&person).await?;
            let projection = self
                .run(
                    &person,
                    "overview.calendar",
                    json!({"profile_id":profile, "kind":"calendar", "output_language":language,
                        "from_date":from, "to_date":to}),
                    false,
                )
                .await?;
            self.still_held(&person, &profile).await?;
            filing_calendar(projection, &profile, &from, &to)
        })
        .await
        .unwrap_or_else(|_| Err(protocol()))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const PROFILE: &str = "0b4f6c2e-8f0a-4a8e-9a43-5b1a6e0d7c11";

    fn entry() -> Value {
        json!({
            "modelo":"303", "period":"3T", "opens_on":"2026-10-01", "closes_on":"2026-10-20",
            "adjusted_closes_on":"2026-10-20", "shift_reason":"none", "payment_cutoff_on":"2026-10-15",
            "evaluated_on":"2026-10-22", "days_overdue":2, "status":"overdue", "user_state":"late",
            "holiday_refs":[], "filing_evidence":{"local_filing_state":"ready_to_file",
            "aeat_submission_state":"not_observed", "justificante_verified":false,
            "justificante_required":true}
        })
    }
    fn projection(declared: bool) -> Value {
        json!({
            "profile_id": PROFILE,
            "request": {"kind":"calendar"},
            "payload": {
                "kind":"calendar",
                "calendar": {
                    "range":{"from_date":"2026-07-01","to_date":"2027-06-30"},
                    "evaluated_on":"2026-10-22",
                    "entries":[entry()],
                    "generated_at":"2026-10-22T08:00:00Z",
                    "warnings":[{"code":"iva.regime","message":"cli.overview.warning.x",
                        "text":"Tu perfil no indica el régimen","fix_action":{},
                        "affected_modelos":["303"]}],
                    "taxpayer_model_declared":declared,
                    "incomplete_reason": if declared { Value::Null } else { json!("Falta el modelo del contribuyente") },
                    "events":[{"event_type":"message","event_date":"2026-09-01","source":"aeat_sede_notifications",
                        "summary":"Notificación","reference_id":"A1","status":null,"aeat_submission_state":null,
                        "aeat_submitted_at":null,"justificante_verified":null,"source_url":"https://example.invalid"}],
                    "coverage":{"surfaced":["303"],"confidently_excluded":[],"advised":[
                        {"modelo":"190","reason":"applicable_window_missing"}],"out_of_scope":[]}
                }
            }
        })
    }

    #[test]
    fn the_calendar_keeps_the_products_states_and_opening_days() {
        let calendar =
            filing_calendar(projection(true), PROFILE, "2026-07-01", "2027-06-30").unwrap();
        let shown = serde_json::to_value(&calendar).unwrap();
        let entry = &shown["entries"][0];
        assert_eq!(entry["opens_on"], "2026-10-01");
        assert_eq!(entry["user_state"], "late");
        assert_eq!(entry["local_filing_state"], "ready_to_file");
        assert_eq!(entry["aeat_submission_state"], "not_observed");
        assert_eq!(entry["days_overdue"], 2);
        assert!(entry.get("status").is_none());
        assert_eq!(
            shown["warnings"][0]["message"],
            "Tu perfil no indica el régimen"
        );
        assert_eq!(
            shown["coverage"]["advised"][0]["reason"],
            "applicable_window_missing"
        );
        assert!(shown["events"][0].get("source_url").is_none());
    }

    #[test]
    fn an_undeclared_taxpayer_model_is_said_not_drawn_as_nothing_due() {
        let calendar =
            filing_calendar(projection(false), PROFILE, "2026-07-01", "2027-06-30").unwrap();
        assert_eq!(calendar.warnings[0].code, "taxpayer_model_undeclared");
        assert_eq!(
            calendar.warnings[0].message,
            "Falta el modelo del contribuyente"
        );
    }

    #[test]
    fn a_calendar_for_another_profile_range_or_state_is_refused() {
        assert!(filing_calendar(projection(true), "another", "2026-07-01", "2027-06-30").is_err());
        assert!(filing_calendar(projection(true), PROFILE, "2026-07-02", "2027-06-30").is_err());
        let mut unknown = projection(true);
        unknown["payload"]["calendar"]["entries"][0]["user_state"] = json!("maybe");
        assert!(filing_calendar(unknown, PROFILE, "2026-07-01", "2027-06-30").is_err());
        let mut untranslated = projection(true);
        untranslated["payload"]["calendar"]["warnings"][0]
            .as_object_mut()
            .unwrap()
            .remove("text");
        assert!(filing_calendar(untranslated, PROFILE, "2026-07-01", "2027-06-30").is_err());
    }

    #[test]
    fn only_a_bounded_range_of_real_days_is_read() {
        assert!(admit_range("2026-07-01", "2027-06-30").is_ok());
        for (from, to) in [
            ("2027-06-30", "2026-07-01"),
            ("2026-07-01", "2028-01-01"),
            ("2026-13-01", "2027-01-01"),
            ("2026-7-01", "2027-01-01"),
            ("2026-07-01", "2027-06-30; drop"),
        ] {
            assert_eq!(admit_range(from, to).unwrap_err().code, "refused");
        }
    }

    #[test]
    fn notifications_reach_the_window_as_counts_only() {
        let latest = json!({"bucket_id":PROFILE, "snapshot_id":"ab", "captured_at":"2026-10-20T09:00:00Z",
            "source_url":"https://example.invalid", "row_count":3});
        let row =
            |leida: Value| json!({"titular_nif":"00000000T","titular_nombre":"Name","leida":leida});
        let shown = json!({"bucket_id":PROFILE, "snapshot_id":"ab", "captured_at":"2026-10-20T09:00:00Z",
            "source_url":"https://example.invalid", "row_count":3,
            "rows":[row(json!(false)), row(json!(true)), row(Value::Null)]});
        let summary = notifications_summary(latest.clone(), Some(shown.clone())).unwrap();
        let sent = serde_json::to_value(&summary).unwrap();
        assert_eq!(
            sent,
            json!({"captured_at":"2026-10-20T09:00:00Z","row_count":3,"unread":1})
        );
        let mut other = shown;
        other["snapshot_id"] = json!("cd");
        assert!(notifications_summary(latest.clone(), Some(other)).is_err());
        assert!(notifications_summary(latest, None).is_err());
    }

    #[test]
    fn never_captured_notifications_are_not_none_unread() {
        let summary =
            notifications_summary(json!({"bucket_id":PROFILE, "snapshot_id":null}), None).unwrap();
        assert_eq!(summary.captured_at, None);
    }
}
