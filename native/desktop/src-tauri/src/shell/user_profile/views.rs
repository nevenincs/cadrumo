//! Named read-only views of the signed-in profile: the filing calendar, the
//! counts of the last notifications capture and Home. Each runs fixed
//! registered reads over the held person's relay; the window names no
//! operation. Nothing
//! read here is kept, logged or written: it is passed on and dropped. The
//! calendar is passed on as the product served it, under the product's names,
//! so the window's types are generated from the product's schema alone; the
//! one thing the host takes out is where an observed event was read from.
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

// Only what the host checks before passing the calendar on: whose it is,
// which read it is, and that it covers exactly the requested range. The
// snapshot itself stays the product's value.
#[derive(Deserialize)]
struct Range {
    from_date: String,
    to_date: String,
}
#[derive(Deserialize)]
struct CalendarRead {
    kind: String,
    calendar: Option<Value>,
}
#[derive(Deserialize)]
struct Projection {
    profile_id: String,
    payload: CalendarRead,
}

/// The calendar snapshot of the product's `overview.calendar` read, unchanged.
#[derive(Debug, Serialize)]
#[serde(transparent)]
pub struct FilingCalendar(Value);

// Only what the host checks before passing Home on: whose generation it is
// and that its `home` state is a state. The rest of the generation, which
// carries the declarations, ledger, AEAT sync and search states, is read
// into this and dropped; the window is never sent it.
#[derive(Deserialize)]
struct GenerationRead {
    profile_id: String,
    generation: HomeGeneration,
}
#[derive(Deserialize)]
struct HomeGeneration {
    home: Value,
}

/// The `home` state of the product's `workbench.generation` read, unchanged:
/// its availability, observed time, refusal and Home projection.
#[derive(Debug, Serialize)]
#[serde(transparent)]
pub struct HomeState(Value);

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
    let calendar = match projection.payload {
        CalendarRead {
            kind,
            calendar: Some(calendar),
        } if kind == "calendar" && projection.profile_id == profile => calendar,
        _ => return Err(protocol()),
    };
    let range = calendar
        .get("range")
        .and_then(|range| Range::deserialize(range).ok())
        .ok_or_else(protocol)?;
    if range.from_date != from || range.to_date != to {
        return Err(protocol());
    }
    Ok(FilingCalendar(without_event_sources(calendar)))
}

/// The host's own disclosure policy: an observed event reaches the window
/// without the address it was read from.
fn without_event_sources(mut calendar: Value) -> Value {
    if let Some(events) = calendar.get_mut("events").and_then(Value::as_array_mut) {
        for event in events.iter_mut().filter_map(Value::as_object_mut) {
            event.remove("source_url");
        }
    }
    calendar
}

/// The registered read Home comes from. It serves the whole workbench
/// generation; only its `home` state is passed on.
pub(super) const HOME_DEFINITION: &str = "workbench.generation";

/// The generation read, for the held profile and the language the window
/// shows its words in: nothing else is asked.
fn home_request(profile: &str, language: &str) -> Value {
    json!({"profile_id":profile, "output_language":language})
}

/// Passes on only the `home` state of a generation read for `profile`. A
/// generation naming another profile, or a `home` that is not a state with
/// an availability, is refused rather than shown.
fn home_state(projection: Value, profile: &str) -> Result<HomeState> {
    let read: GenerationRead = serde_json::from_value(projection).map_err(|_| protocol())?;
    if read.profile_id != profile
        || read
            .generation
            .home
            .get("availability")
            .and_then(Value::as_str)
            .is_none()
    {
        return Err(protocol());
    }
    Ok(HomeState(read.generation.home))
}

/// The registered read the record groups come from.
pub(super) const RECORD_GROUPS_DEFINITION: &str = "user-profile.record-groups";

fn names_profile(value: &Value, profile: &str) -> bool {
    value
        .as_object()
        .and_then(|fields| fields.get("profile_id"))
        .and_then(Value::as_str)
        == Some(profile)
}

/// The request goes to the product unchanged, but only for the held profile.
fn admit_record_groups_request(request: &Value, profile: &str) -> Result<()> {
    if names_profile(request, profile) {
        Ok(())
    } else {
        Err(Failure::new("refused"))
    }
}

/// The page comes back unchanged, but only if it is the held profile's.
fn admit_record_groups_result(result: Value, profile: &str) -> Result<Value> {
    if names_profile(&result, profile) {
        Ok(result)
    } else {
        Err(protocol())
    }
}

/// The overview calendar read, which also asks for the rows it holds off the
/// schedule so the window can say what it left out.
fn calendar_request(profile: &str, language: &str, from: &str, to: &str) -> Value {
    json!({"profile_id":profile, "kind":"calendar", "output_language":language,
        "from_date":from, "to_date":to, "show_suppressed":true})
}

impl ProfileHost {
    pub(super) async fn profile_of(person: &crate::agent::person::HeldPerson) -> Result<String> {
        Ok(Self::identity(person).await?["profile_id"]
            .as_str()
            .ok_or_else(protocol)?
            .to_owned())
    }
    /// Rejects an answer read while the window's account changed underneath.
    pub(super) async fn still_held(
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
    /// One page of the record groups, relayed as the product serialises its
    /// request and result. The request is refused before submission where it
    /// names another profile than the one held; so is a result that does.
    pub(super) async fn record_groups(&self, request: Value) -> Result<Value> {
        tokio::time::timeout(PROFILE_READ_LIMIT, async {
            let _serial = self.operation.lock().await;
            let person = self.person(None).await?;
            let profile = Self::profile_of(&person).await?;
            admit_record_groups_request(&request, &profile)?;
            let result = self
                .run(&person, RECORD_GROUPS_DEFINITION, request, false)
                .await?;
            self.still_held(&person, &profile).await?;
            admit_record_groups_result(result, &profile)
        })
        .await
        .unwrap_or_else(|_| Err(protocol()))
    }
    /// Home for the signed-in profile: one `workbench.generation` read, of
    /// which only its `home` state is returned. The read is local to the
    /// profile and never reaches the tax agency.
    pub(super) async fn home(&self, language: String) -> Result<HomeState> {
        if !super::super::language::supported(&language) {
            return Err(protocol());
        }
        tokio::time::timeout(PROFILE_READ_LIMIT, async {
            let _serial = self.operation.lock().await;
            let person = self.person(None).await?;
            let profile = Self::profile_of(&person).await?;
            let projection = self
                .run(
                    &person,
                    HOME_DEFINITION,
                    home_request(&profile, &language),
                    false,
                )
                .await?;
            self.still_held(&person, &profile).await?;
            home_state(projection, &profile)
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
                    calendar_request(&profile, &language, &from, &to),
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
#[path = "views_calendar_contract_tests.rs"]
mod calendar_contract_tests;

#[cfg(test)]
mod tests {
    use super::*;

    const PROFILE: &str = "0b4f6c2e-8f0a-4a8e-9a43-5b1a6e0d7c11";

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

    fn generation(profile: &str, home: Value) -> Value {
        json!({"profile_id":profile,
            "generation":{"contract_version":1, "assembled_at":"2026-10-20T09:00:00Z",
                "home":home,
                "ledger":{"availability":"available", "projection":{"bucket_id":profile}},
                "declarations":{"availability":"available", "projection":{"bucket_id":profile}},
                "aeat_sync":{"availability":"available", "projection":{"notifications":[{"titular_nif":"00000000T"}]}},
                "search":{"availability":"available"}}})
    }

    #[test]
    fn home_asks_for_the_held_profile_and_the_language_and_nothing_else() {
        assert_eq!(HOME_DEFINITION, "workbench.generation");
        assert_eq!(
            home_request(PROFILE, "hu"),
            json!({"profile_id":PROFILE, "output_language":"hu"})
        );
    }

    #[test]
    fn only_the_home_state_of_the_generation_reaches_the_window() {
        let home = json!({"availability":"available", "observed_at":"2026-10-20T09:00:00Z",
            "refusal":null, "projection":{"actions":[], "agenda":[]}});
        let sent =
            serde_json::to_value(home_state(generation(PROFILE, home.clone()), PROFILE).unwrap())
                .unwrap();
        assert_eq!(sent, home);
        for withheld in [
            "ledger",
            "declarations",
            "aeat_sync",
            "search",
            "bucket_id",
            "00000000T",
        ] {
            assert!(
                !sent.to_string().contains(withheld),
                "{withheld} was passed on"
            );
        }
    }

    #[test]
    fn an_unavailable_or_refused_home_is_passed_on_as_the_product_served_it() {
        let refused = json!({"availability":"unavailable", "observed_at":null,
            "refusal":"workbench.home.unavailable", "projection":null});
        let sent = serde_json::to_value(
            home_state(generation(PROFILE, refused.clone()), PROFILE).unwrap(),
        )
        .unwrap();
        assert_eq!(sent, refused);
    }

    #[test]
    fn a_generation_of_another_profile_or_without_a_home_state_is_refused() {
        let home = json!({"availability":"available", "projection":null});
        assert!(home_state(generation("another", home.clone()), PROFILE).is_err());
        assert!(home_state(generation(PROFILE, json!({"projection":null})), PROFILE).is_err());
        assert!(home_state(generation(PROFILE, json!("available")), PROFILE).is_err());
        let mut headless = generation(PROFILE, home.clone());
        headless.as_object_mut().unwrap().remove("profile_id");
        assert!(home_state(headless, PROFILE).is_err());
        let mut homeless = generation(PROFILE, home);
        homeless["generation"]
            .as_object_mut()
            .unwrap()
            .remove("home");
        assert!(home_state(homeless, PROFILE).is_err());
        assert!(home_state(json!(null), PROFILE).is_err());
    }

    #[test]
    fn a_record_groups_request_for_the_held_profile_goes_unchanged() {
        assert_eq!(RECORD_GROUPS_DEFINITION, "user-profile.record-groups");
        let request = json!({"profile_id":PROFILE, "group_kind":"rental_property", "cursor":0,
            "limit":128, "expected_revision":null, "expected_content_digest":null,
            "expected_ledger_digest":null, "output_language":"es"});
        assert!(admit_record_groups_request(&request, PROFILE).is_ok());
        assert_eq!(request["limit"], 128);
        assert_eq!(request["group_kind"], "rental_property");
    }

    #[test]
    fn a_record_groups_request_for_another_profile_is_refused_before_submission() {
        let foreign = json!({"profile_id":"another", "group_kind":"rental_property"});
        assert_eq!(
            admit_record_groups_request(&foreign, PROFILE)
                .unwrap_err()
                .code,
            "refused"
        );
        for bad in [
            json!({"group_kind":"rental_property"}),
            json!("x"),
            json!(null),
        ] {
            assert!(admit_record_groups_request(&bad, PROFILE).is_err());
        }
    }

    #[test]
    fn a_record_groups_result_for_another_profile_is_refused() {
        let page = json!({"profile_id":PROFILE, "outcome":"page", "items":[{"kind":"future"}]});
        assert_eq!(
            admit_record_groups_result(page.clone(), PROFILE).unwrap(),
            page
        );
        let other = json!({"profile_id":"another", "outcome":"page"});
        assert!(admit_record_groups_result(other, PROFILE).is_err());
        assert!(admit_record_groups_result(json!({"outcome":"page"}), PROFILE).is_err());
    }
}
