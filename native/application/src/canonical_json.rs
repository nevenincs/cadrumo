//! The product's canonical JSON: sorted keys, compact separators, unescaped UTF-8 and
//! numbers as Python spells them, so a digest computed here equals the product's
//! `content_hash_hex` of the same document.

use serde_json::Value;
use std::collections::BTreeMap;

/// The canonical spelling: members sorted by key.
pub(crate) fn canonical_json(value: &Value) -> String {
    let mut out = String::new();
    write_json(value, true, &mut out);
    out
}

/// Compact JSON in the document's own member order, as Python's
/// `json.dumps(..., ensure_ascii=False, separators=(",", ":"))` writes it.
#[cfg(feature = "platform")]
pub(crate) fn compact_json(value: &Value) -> String {
    let mut out = String::new();
    write_json(value, false, &mut out);
    out
}

#[cfg(feature = "platform")]
pub(crate) fn json_string(value: &str) -> String {
    let mut out = String::new();
    write_string(value, &mut out);
    out
}

fn write_json(value: &Value, sorted: bool, out: &mut String) {
    match value {
        Value::Null => out.push_str("null"),
        Value::Bool(flag) => out.push_str(if *flag { "true" } else { "false" }),
        Value::Number(number) => {
            if let Some(integer) = number.as_i64() {
                out.push_str(&integer.to_string());
            } else if let Some(integer) = number.as_u64() {
                out.push_str(&integer.to_string());
            } else {
                write_float(number.as_f64().unwrap_or_default(), out);
            }
        }
        Value::String(text) => write_string(text, out),
        Value::Array(items) => {
            out.push('[');
            for (index, item) in items.iter().enumerate() {
                if index > 0 {
                    out.push(',');
                }
                write_json(item, sorted, out);
            }
            out.push(']');
        }
        Value::Object(members) => {
            let ordered: Vec<(&String, &Value)> = if sorted {
                members
                    .iter()
                    .collect::<BTreeMap<_, _>>()
                    .into_iter()
                    .collect()
            } else {
                members.iter().collect()
            };
            out.push('{');
            for (index, (key, item)) in ordered.into_iter().enumerate() {
                if index > 0 {
                    out.push(',');
                }
                write_string(key, out);
                out.push(':');
                write_json(item, sorted, out);
            }
            out.push('}');
        }
    }
}

/// Escapes as Python's encoder does without ASCII escaping: quotes,
/// backslashes and control characters only.
fn write_string(text: &str, out: &mut String) {
    out.push('"');
    for character in text.chars() {
        match character {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            '\u{8}' => out.push_str("\\b"),
            '\u{c}' => out.push_str("\\f"),
            control if u32::from(control) < 0x20 => {
                out.push_str(&format!("\\u{:04x}", u32::from(control)));
            }
            other => out.push(other),
        }
    }
    out.push('"');
}

/// A finite float as Python's `repr`: the shortest digits that round-trip,
/// positional from 1e-4 up to below 1e16, else `d.ddde±XX`.
fn write_float(value: f64, out: &mut String) {
    if value == 0.0 {
        out.push_str(if value.is_sign_negative() {
            "-0.0"
        } else {
            "0.0"
        });
        return;
    }
    if value.is_sign_negative() {
        out.push('-');
    }
    let scientific = format!("{:e}", value.abs());
    let (mantissa, exponent) = scientific.split_once('e').unwrap_or((&scientific, "0"));
    let digits: String = mantissa.chars().filter(|digit| *digit != '.').collect();
    let exponent: i32 = exponent.parse().unwrap_or_default();
    let point = exponent + 1;
    let count = digits.len() as i32;
    if !(-3..=16).contains(&point) {
        out.push_str(&digits[..1]);
        if digits.len() > 1 {
            out.push('.');
            out.push_str(&digits[1..]);
        }
        out.push_str(&format!(
            "e{}{:02}",
            if exponent < 0 { '-' } else { '+' },
            exponent.abs()
        ));
    } else if point <= 0 {
        out.push_str("0.");
        out.push_str(&"0".repeat((-point) as usize));
        out.push_str(&digits);
    } else if point >= count {
        out.push_str(&digits);
        out.push_str(&"0".repeat((point - count) as usize));
        out.push_str(".0");
    } else {
        out.push_str(&digits[..point as usize]);
        out.push('.');
        out.push_str(&digits[point as usize..]);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn canonical_json_spells_documents_as_the_product_does() {
        let sample = "{\"z\": [1, -2, 3.5, 1e16, 1e-05, 0.0001, 123456789.125, -0.0, 1e300, 0.1, 1e15, 2.5e-07, 100.0], \"\u{e9}\": \"\u{f1}and\u{fa} \\\"quoted\\\" \\\\ \\n\\t\\u0001 \\u007f \u{1f600}\", \"A\": {\"nested\": {\"b\": true, \"a\": null, \"\u{ffff}\": [], \"\u{1f600}\": {}}}, \"\u{3a9}\": 18446744073709551615, \"neg\": -9223372036854775808}";
        let document: Value = serde_json::from_str(sample).unwrap();
        // The product's `canonical_json_bytes` of `sample`.
        assert_eq!(
            canonical_json(&document),
            "{\"A\":{\"nested\":{\"a\":null,\"b\":true,\"\u{ffff}\":[],\"\u{1f600}\":{}}},\"neg\":-9223372036854775808,\"z\":[1,-2,3.5,1e+16,1e-05,0.0001,123456789.125,-0.0,1e+300,0.1,1000000000000000.0,2.5e-07,100.0],\"\u{e9}\":\"\u{f1}and\u{fa} \\\"quoted\\\" \\\\ \\n\\t\\u0001 \u{7f} \u{1f600}\",\"\u{3a9}\":18446744073709551615}"
        );
    }
}
