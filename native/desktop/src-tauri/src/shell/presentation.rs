//! Opens a register view in the person's own TUI. The held person session
//! asks the runtime, which passes the view to that person's signed-in TUIs on
//! the same profile; the TUI admits the view itself, as it would a keystroke.
//! Nothing here grants access to anything: a view is only where to look, and
//! its parameters only select what to show.
use super::sign_in::{Presence, SignIn};
use cadrumo_application::error::application::{ApplicationError, ErrorCode, Operation, Result};
use serde::{Deserialize, Serialize};
use serde_json::{Map, Value, json};
use std::collections::BTreeMap;
use std::sync::{Arc, Mutex, OnceLock};
use tauri::State;

/// The navigation register as the build projected it from its one declaration.
const NAVIGATION: &str = include_str!(concat!(env!("OUT_DIR"), "/navigation.json"));

#[derive(Deserialize)]
struct Projection {
    kinds: Vec<Kind>,
    elements: Vec<Element>,
}

#[derive(Deserialize)]
struct Kind {
    name: String,
    alphabet: String,
    length: usize,
}

#[derive(Deserialize)]
struct Element {
    id: String,
    surfaces: Vec<String>,
    params: BTreeMap<String, String>,
}

/// The views a TUI implements, each with the parameters it declares and the
/// exact shape of every value kind.
struct TuiViews {
    /// Value kind name to its alphabet and length.
    kinds: BTreeMap<String, (String, usize)>,
    /// TUI view id to its declared parameter names and their value kinds.
    views: BTreeMap<String, BTreeMap<String, String>>,
}

impl TuiViews {
    fn from_projection(text: &str) -> serde_json::Result<Self> {
        let projection: Projection = serde_json::from_str(text)?;
        Ok(Self {
            kinds: projection
                .kinds
                .into_iter()
                .map(|kind| (kind.name, (kind.alphabet, kind.length)))
                .collect(),
            views: projection
                .elements
                .into_iter()
                .filter(|element| element.surfaces.iter().any(|surface| surface == "tui"))
                .map(|element| (element.id, element.params))
                .collect(),
        })
    }

    /// Whether `view` is a TUI view and every one of `params` is a parameter
    /// it declares, with a value of exactly its kind's shape.
    fn admits(&self, view: &str, params: &BTreeMap<String, String>) -> bool {
        let Some(declared) = self.views.get(view) else {
            return false;
        };
        params.iter().all(|(name, value)| {
            declared
                .get(name)
                .and_then(|kind| self.kinds.get(kind))
                .is_some_and(|(alphabet, length)| {
                    value.chars().count() == *length && value.chars().all(|c| alphabet.contains(c))
                })
        })
    }
}

fn tui_views() -> &'static TuiViews {
    static VIEWS: OnceLock<TuiViews> = OnceLock::new();
    VIEWS.get_or_init(|| {
        TuiViews::from_projection(NAVIGATION)
            .expect("the build generates the navigation projection from the validated register")
    })
}

/// Whether a TUI may be asked to show `view` with `params`: a register view
/// whose surfaces include the TUI, with only its declared parameters.
pub(crate) fn admitted(view: &str, params: &BTreeMap<String, String>) -> bool {
    tui_views().admits(view, params)
}

/// The same check for parameters still in their wire form: an object of strings.
pub(crate) fn admitted_value(view: &str, params: &Value) -> bool {
    params_of(params).is_some_and(|params| admitted(view, &params))
}

/// The parameters of a request as names to values, or `None` when they are
/// not an object of strings.
pub(crate) fn params_of(params: &Value) -> Option<BTreeMap<String, String>> {
    params
        .as_object()?
        .iter()
        .map(|(name, value)| Some((name.clone(), value.as_str()?.to_owned())))
        .collect()
}

/// What became of a request to show a view.
#[derive(Debug, PartialEq, Eq, Serialize)]
#[serde(tag = "outcome", rename_all = "snake_case")]
pub enum Outcome {
    /// The runtime passed the view to this many TUIs; none is zero.
    Presented { delivered: u64 },
    /// Nobody is signed in here, so no session can carry the request.
    SignedOut,
}

fn lock<T>(value: &Mutex<T>) -> std::sync::MutexGuard<'_, T> {
    value.lock().unwrap_or_else(|error| error.into_inner())
}

pub fn commands<R: tauri::Runtime>() -> crate::app::Commands<R> {
    crate::app::commands![desktop_present_view]
}

#[tauri::command]
async fn desktop_present_view(
    state: State<'_, Arc<SignIn>>,
    view: String,
    params: BTreeMap<String, String>,
) -> Result<Outcome> {
    if !admitted(&view, &params) {
        return Err(ApplicationError::new(
            ErrorCode::InvalidArguments,
            Operation::Cli,
        ));
    }
    let sign_in = state.inner().clone();
    let status = sign_in.read_status().await?;
    if status.state != Presence::Present || !status.runtime_ready() {
        return Ok(Outcome::SignedOut);
    }
    let Some(label) = status.active_profile else {
        return Ok(Outcome::SignedOut);
    };
    super::blocking(move || {
        // The view goes to the profile signed in here: a link names none.
        let active = sign_in.profile_id(&label)?;
        let person = sign_in.person(&active)?;
        let params: Map<String, Value> = params
            .into_iter()
            .map(|(name, value)| (name, Value::String(value)))
            .collect();
        let reply = lock(&person).exchange(json!({
            "action": "present_destination",
            "destination": view,
            "params": params,
        }))?;
        Ok(Outcome::Presented {
            delivered: reply["delivered"].as_u64().unwrap_or(0),
        })
    })
    .await
}

#[cfg(test)]
mod tests {
    use super::*;

    const TRANSACTION: &str = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";

    fn params(pairs: &[(&str, &str)]) -> BTreeMap<String, String> {
        pairs
            .iter()
            .map(|(name, value)| ((*name).to_owned(), (*value).to_owned()))
            .collect()
    }

    #[test]
    fn the_generated_projection_admits_exactly_the_registers_tui_views() {
        for view in [
            "home",
            "ledger",
            "withholding",
            "declarations",
            "aeat-sync",
            "operations",
            "installation",
            "setup",
            "reference",
            "profile",
            "profile/aeat-access",
        ] {
            assert!(admitted(view, &params(&[])), "{view}");
        }
        assert_eq!(tui_views().views.len(), 11, "every TUI view, no other");
        // A view only the window implements, an unknown one and a malformed one.
        for view in [
            "calendar",
            "ledger/invoices",
            "ledger/movements",
            "panel/logs",
            "agent",
            "nowhere",
            "aeat_sync",
            "Ledger",
            "",
            "cadrumo://view/ledger",
        ] {
            assert!(!admitted(view, &params(&[])), "{view}");
        }
    }

    #[test]
    fn parameters_are_only_the_declared_ones_of_their_exact_kind() {
        assert!(admitted("ledger", &params(&[("select", TRANSACTION)])));
        for refused in [
            params(&[("select", &TRANSACTION[1..])]),
            params(&[("select", &TRANSACTION.to_uppercase())]),
            params(&[("select", "f-0001-2026")]),
            params(&[("select", "")]),
            params(&[("zoom", "2")]),
            params(&[("prefer", "tui")]),
            params(&[("select", TRANSACTION), ("zoom", "2")]),
        ] {
            assert!(!admitted("ledger", &refused), "{refused:?}");
        }
        // A view that declares no parameter takes none.
        assert!(!admitted("aeat-sync", &params(&[("select", TRANSACTION)])));
    }

    #[test]
    fn wire_parameters_must_be_an_object_of_strings() {
        assert!(admitted_value("ledger", &json!({})));
        assert!(admitted_value("ledger", &json!({"select": TRANSACTION})));
        for refused in [
            json!(null),
            json!([]),
            json!("select"),
            json!({"select": 1}),
            json!({"select": null}),
        ] {
            assert!(!admitted_value("ledger", &refused), "{refused}");
        }
    }

    #[test]
    fn a_projection_is_read_as_the_generator_writes_it() {
        let views = TuiViews::from_projection(
            r#"{"schema":1,"link":{},"surfaces":["gui","tui"],"retired":[],
            "kinds":[{"name":"row","alphabet":"ab","length":2}],
            "elements":[
              {"id":"one","parent":null,"label":"a.b","keywords":"","surfaces":["tui"],"params":{"pick":"row"}},
              {"id":"two","parent":null,"label":"a.c","keywords":"","surfaces":["gui"],"params":{}}
            ]}"#,
        )
        .unwrap();
        assert!(views.admits("one", &params(&[("pick", "ab")])));
        assert!(!views.admits("one", &params(&[("pick", "ac")])));
        assert!(!views.admits("one", &params(&[("pick", "aba")])));
        assert!(!views.admits("two", &params(&[])));
    }

    #[test]
    fn outcomes_serialize_as_the_window_reads_them() {
        assert_eq!(
            serde_json::to_value(Outcome::Presented { delivered: 2 }).unwrap(),
            json!({"outcome":"presented","delivered":2})
        );
        assert_eq!(
            serde_json::to_value(Outcome::SignedOut).unwrap(),
            json!({"outcome":"signed_out"})
        );
    }
}
