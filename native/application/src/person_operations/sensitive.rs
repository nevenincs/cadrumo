use serde_json::{Number, Value};
use zeroize::Zeroize;

/// Sends `request` through `send` and then overwrites every value it held,
/// whether or not it was sent.
pub(super) fn sent_then_wiped<R>(request: &mut Value, send: impl FnOnce(&Value) -> R) -> R {
    let reply = send(request);
    wipe(request);
    *request = Value::Null;
    reply
}

/// Overwrites every text, number and flag in `value` in place, for a request
/// that carried private input. Member names are the contract's, never input.
pub fn wipe(value: &mut Value) {
    match value {
        Value::String(text) => text.zeroize(),
        Value::Number(number) => {
            // A number is held inline: overwriting it overwrites its bits.
            *number = Number::from(0u8);
            std::hint::black_box(&*number);
        }
        Value::Bool(flag) => {
            *flag = false;
            std::hint::black_box(&*flag);
        }
        Value::Array(items) => items.iter_mut().for_each(wipe),
        Value::Object(members) => members.values_mut().for_each(wipe),
        Value::Null => {}
    }
}
