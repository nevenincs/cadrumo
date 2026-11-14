//! The RIRPF art. 7 imputation election for one ejercicio, read from
//! `user-profile.imputation-election.read`: what the profile states for the
//! ejercicio, what each ejercicio states, and the setup wizard's own questions
//! and words for it. The host decides nothing about the election. It checks
//! that the answer is the one asked for, in the language asked for, and that
//! an answer carries a value exactly when it is declared, so an undeclared or
//! contradictory ejercicio is never read as a choice. Changing it is the
//! profile edit `imputation_election`.
use super::{Failure, PROFILE_READ_LIMIT, ProfileHost, Result, protocol};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};

#[derive(Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
enum State {
    Declared,
    Undeclared,
    Contradictory,
}

/// What the profile states for one question: a value only when declared.
#[derive(Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct Answer {
    state: State,
    value: Option<String>,
}

#[derive(Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct Choice {
    value: String,
    label: String,
    description: Option<String>,
}

/// One setup question in the words the setup wizard asks it.
#[derive(Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct Question {
    question_id: String,
    path: Option<String>,
    prompt: String,
    help: Option<String>,
    choices: Vec<Choice>,
}

/// What one ejercicio's criterion states.
#[derive(Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct Statement {
    ejercicio: u16,
    value: String,
}

/// The election as the window is served it. The revision and digest are the
/// baseline a change of it names.
#[derive(Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Election {
    profile_id: String,
    record_revision: u64,
    content_digest: String,
    tax_year: u16,
    criterion: Answer,
    codigo_comercio_accounting: Answer,
    criterion_statements: Vec<Statement>,
    criterion_question: Question,
    year_question: Question,
    accounting_question: Question,
    accounting_asked_for_criteria: Vec<String>,
    words_language: String,
}

impl Answer {
    fn consistent(&self) -> bool {
        (self.state == State::Declared) == self.value.is_some()
    }
}

/// The projection the read settled to, as the election of exactly `profile`,
/// `tax_year` and `language`.
fn election(projection: Value, profile: &str, tax_year: u16, language: &str) -> Result<Election> {
    let election: Election = serde_json::from_value(projection).map_err(|_| protocol())?;
    let years: Vec<u16> = election
        .criterion_statements
        .iter()
        .map(|statement| statement.ejercicio)
        .collect();
    if election.profile_id != profile
        || election.tax_year != tax_year
        || election.words_language != language
        || election.record_revision == 0
        || !super::super::setup::wire::is_hex64(&election.content_digest)
        || !election.criterion.consistent()
        || !election.codigo_comercio_accounting.consistent()
        || !years.windows(2).all(|pair| pair[0] < pair[1])
    {
        return Err(protocol());
    }
    Ok(election)
}

impl ProfileHost {
    pub(super) async fn imputation_election(
        &self,
        profile: String,
        tax_year: u16,
        language: String,
    ) -> Result<Election> {
        if !super::super::language::supported(&language) {
            return Err(protocol());
        }
        tokio::time::timeout(PROFILE_READ_LIMIT, async {
            let _serial = self.operation.lock().await;
            let person = self.person(Some(&profile)).await?;
            let projection = self
                .run(
                    &person,
                    "user-profile.imputation-election.read",
                    json!({"profile_id":profile, "tax_year":tax_year, "output_language":language}),
                    false,
                )
                .await?;
            self.still_held(&person, &profile).await?;
            election(projection, &profile, tax_year, &language)
        })
        .await
        .unwrap_or_else(|_| Err(Failure::new("unavailable")))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const PROFILE: &str = "0b4f6c2e-8f0a-4a8e-9a43-5b1a6e0d7c11";

    fn question(id: &str) -> Value {
        json!({"question_id":id,"path":null,"prompt":"Words","help":null,
            "choices":[{"value":"a","label":"A","description":null}]})
    }
    fn projection() -> Value {
        json!({"profile_id":PROFILE,"record_revision":4,"content_digest":"a".repeat(64),
            "tax_year":2025,
            "criterion":{"state":"declared","value":"devengo"},
            "codigo_comercio_accounting":{"state":"undeclared","value":null},
            "criterion_statements":[{"ejercicio":2023,"value":"caja"},{"ejercicio":2025,"value":"devengo"}],
            "criterion_question":question("criterion"),"year_question":question("year"),
            "accounting_question":question("accounting"),
            "accounting_asked_for_criteria":["devengo"],"words_language":"en"})
    }
    fn read(projection: Value) -> Result<Election> {
        election(projection, PROFILE, 2025, "en")
    }

    #[test]
    fn the_election_keeps_what_the_profile_states_and_the_products_words() {
        let shown = serde_json::to_value(read(projection()).unwrap()).unwrap();
        assert_eq!(
            shown["criterion"],
            json!({"state":"declared","value":"devengo"})
        );
        assert_eq!(shown["codigo_comercio_accounting"]["state"], "undeclared");
        assert_eq!(shown["criterion_statements"][1]["ejercicio"], 2025);
        assert_eq!(shown["criterion_question"]["choices"][0]["label"], "A");
        assert_eq!(shown["record_revision"], 4);
        assert_eq!(shown["content_digest"], "a".repeat(64));
    }

    #[test]
    fn an_undeclared_or_contradictory_ejercicio_is_never_read_as_a_choice() {
        for state in ["undeclared", "contradictory"] {
            let mut stated = projection();
            stated["criterion"] = json!({"state":state,"value":"devengo"});
            assert!(read(stated).is_err(), "{state} with a value");
            let mut open = projection();
            open["criterion"] = json!({"state":state,"value":null});
            assert!(read(open).is_ok(), "{state} without one");
        }
        let mut valueless = projection();
        valueless["criterion"] = json!({"state":"declared","value":null});
        assert!(read(valueless).is_err());
        let mut accounting = projection();
        accounting["codigo_comercio_accounting"] = json!({"state":"declared","value":null});
        assert!(read(accounting).is_err());
    }

    #[test]
    fn an_answer_for_another_profile_year_or_language_is_refused() {
        for (member, value) in [
            ("profile_id", json!("another")),
            ("tax_year", json!(2024)),
            ("words_language", json!("es")),
            ("record_revision", json!(0)),
            ("content_digest", json!("short")),
        ] {
            let mut wrong = projection();
            wrong[member] = value;
            assert!(read(wrong).is_err(), "{member}");
        }
    }

    #[test]
    fn an_unknown_member_or_an_unordered_statement_is_refused() {
        let mut extra = projection();
        extra["advice"] = "x".into();
        assert!(read(extra).is_err());
        let mut asked = projection();
        asked["criterion_question"]["tip"] = "x".into();
        assert!(read(asked).is_err());
        let mut absent = projection();
        absent.as_object_mut().unwrap().remove("year_question");
        assert!(read(absent).is_err());
        let mut unordered = projection();
        unordered["criterion_statements"] =
            json!([{"ejercicio":2025,"value":"devengo"},{"ejercicio":2023,"value":"caja"}]);
        assert!(read(unordered).is_err());
        let mut repeated = projection();
        repeated["criterion_statements"] =
            json!([{"ejercicio":2025,"value":"devengo"},{"ejercicio":2025,"value":"caja"}]);
        assert!(read(repeated).is_err());
        let mut outside = projection();
        outside["criterion_statements"] = json!([{"ejercicio":"2025","value":"caja"}]);
        assert!(read(outside).is_err());
    }
}
