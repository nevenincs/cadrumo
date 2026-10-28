use super::token::constant_time_equal;
use crate::app::Commands;
use cadrumo_application::{
    diagnostics::Diagnostics,
    error::application::{ApplicationError, ErrorCode, Operation, Result},
};
use std::{
    collections::{BTreeSet, VecDeque},
    fmt::Write,
    sync::{Arc, Mutex, MutexGuard},
};
use tauri::{
    Manager, Runtime, State, Webview,
    ipc::{CallbackFn, InvokeResponseBody, Response},
};
use zeroize::Zeroizing;

/// How many raw frames may wait for their fetch at once, over every channel.
/// A frame beyond this pushes out the oldest, whose channel is then marked as
/// failed.
const PARKED_LIMIT: usize = 8;
/// CSPRNG bytes in a parked frame's identifier, which travels as hex.
const FRAME_ID_BYTES: usize = 16;

fn lock<T>(mutex: &Mutex<T>) -> MutexGuard<'_, T> {
    mutex.lock().unwrap_or_else(|e| e.into_inner())
}

/// Channels whose frames could not be delivered to their webview, and the raw
/// frames waiting for the shell document to fetch them.
///
/// The interceptor consumes every frame, so a channel's `send` succeeds even
/// when evaluating the frame in the webview failed. A failure is recorded here
/// under the webview label and the channel's callback id, which is
/// `Channel::id()` on the Rust side. The shell plugin manages one instance;
/// any thread can query it.
#[derive(Default)]
pub struct Deliveries {
    failed: Mutex<BTreeSet<(String, u32)>>,
    fetched: Mutex<Fetched>,
}

#[derive(Default)]
struct Fetched {
    /// The channels whose raw frames are fetched rather than evaluated.
    channels: BTreeSet<(String, u32)>,
    /// Oldest first.
    frames: VecDeque<Parked>,
}

/// One raw frame waiting for its fetch. The bytes are wiped when it drops;
/// the copy handed to the webview cannot be.
struct Parked {
    webview: String,
    callback: u32,
    id: String,
    bytes: Zeroizing<Vec<u8>>,
}

impl Deliveries {
    pub(crate) fn record(&self, webview: &str, callback: u32) {
        lock(&self.failed).insert((webview.to_owned(), callback));
    }

    /// Whether a frame for channel `callback` of webview `webview` failed to
    /// be delivered since the previous query for that channel. The query
    /// clears the mark, so a channel's owner asks once per check.
    pub fn failed(&self, webview: &str, callback: u32) -> bool {
        lock(&self.failed).remove(&(webview.to_owned(), callback))
    }

    fn fetch_raw(&self, webview: &str, callback: u32) {
        lock(&self.fetched)
            .channels
            .insert((webview.to_owned(), callback));
    }

    /// Ends fetching for a channel and drops the frames it left waiting.
    fn release(&self, webview: &str, callback: u32) {
        let mut fetched = lock(&self.fetched);
        fetched.channels.remove(&(webview.to_owned(), callback));
        fetched
            .frames
            .retain(|frame| frame.webview != webview || frame.callback != callback);
    }

    /// Drops every fetching channel and waiting frame of `webview`, whose
    /// document was replaced and can no longer ask for them.
    pub(crate) fn forget(&self, webview: &str) {
        let mut fetched = lock(&self.fetched);
        fetched.channels.retain(|(label, _)| label != webview);
        fetched.frames.retain(|frame| frame.webview != webview);
    }

    /// Keeps a raw frame of a fetching channel until the shell document asks
    /// for it, and names it. `None` for a channel that does not fetch.
    fn park(&self, webview: &str, callback: u32, bytes: &[u8]) -> Result<Option<String>> {
        let mut fetched = lock(&self.fetched);
        if !fetched.channels.contains(&(webview.to_owned(), callback)) {
            return Ok(None);
        }
        let id = frame_id()?;
        fetched.frames.push_back(Parked {
            webview: webview.to_owned(),
            callback,
            id: id.clone(),
            bytes: Zeroizing::new(bytes.to_vec()),
        });
        let mut evicted = Vec::new();
        while fetched.frames.len() > PARKED_LIMIT {
            evicted.extend(fetched.frames.pop_front());
        }
        drop(fetched);
        for frame in evicted {
            self.record(&frame.webview, frame.callback);
        }
        Ok(Some(id))
    }

    /// Hands over the frame `id` names, once, and only to the webview it was
    /// parked for.
    fn take(&self, webview: &str, id: &str) -> Option<Zeroizing<Vec<u8>>> {
        let mut fetched = lock(&self.fetched);
        let position = fetched.frames.iter().position(|frame| {
            frame.webview == webview && constant_time_equal(frame.id.as_bytes(), id.as_bytes())
        })?;
        fetched.frames.remove(position).map(|frame| frame.bytes)
    }
}

fn frame_id() -> Result<String> {
    let mut bytes = [0; FRAME_ID_BYTES];
    getrandom::fill(&mut bytes)
        .map_err(|e| failure().caused_by(std::io::Error::other(e.to_string())))?;
    let mut id = String::with_capacity(FRAME_ID_BYTES * 2);
    for byte in bytes {
        write!(id, "{byte:02x}").map_err(|e| failure().caused_by(std::io::Error::other(e)))?;
    }
    Ok(id)
}

/// While it lives, the raw frames of one channel reach the shell document as
/// binary: each becomes a `{"raw_frame": id}` message, and the document takes
/// the bytes with `shell_channel_frame`. Dropping it drops the frames the
/// channel left waiting. Without a managed [`Deliveries`] the frames are
/// evaluated as byte arrays instead.
pub struct RawFetch<R: Runtime> {
    webview: Webview<R>,
    callback: u32,
}

impl<R: Runtime> RawFetch<R> {
    pub fn new(webview: Webview<R>, callback: u32) -> Self {
        if let Some(deliveries) = webview.try_state::<Deliveries>() {
            deliveries.fetch_raw(webview.label(), callback);
        }
        Self { webview, callback }
    }

    /// Whether a frame of this channel failed to reach its webview since the
    /// previous query, as [`Deliveries::failed`] says.
    pub fn failed(&self) -> bool {
        self.webview
            .try_state::<Deliveries>()
            .is_some_and(|deliveries| deliveries.failed(self.webview.label(), self.callback))
    }
}

impl<R: Runtime> Drop for RawFetch<R> {
    fn drop(&mut self) {
        if let Some(deliveries) = self.webview.try_state::<Deliveries>() {
            deliveries.release(self.webview.label(), self.callback);
        }
    }
}

/// Delivers every channel frame by evaluating it in the shell document.
///
/// Tauri otherwise parks large frames in a per-webview queue that any frame of
/// the webview can drain with the ACL-exempt channel fetch command, using
/// sequential ids. Consuming every frame here keeps that queue empty, even
/// when evaluation fails: such a frame is reported to diagnostics and marked
/// in the managed [`Deliveries`] rather than parked for a fetch.
///
/// A raw frame of a channel under [`RawFetch`] is kept in [`Deliveries`]
/// instead, under an unguessable id, and only the id is evaluated; the shell
/// document then takes the bytes through the token-checked
/// `shell_channel_frame` command, whose answer is binary. Any other raw frame
/// is evaluated as a byte array, about 3.6 bytes of script per byte.
pub fn interceptor<R: Runtime>(
    diagnostics: Arc<Diagnostics>,
) -> impl Fn(&Webview<R>, CallbackFn, usize, &InvokeResponseBody) -> bool + Send + Sync + 'static {
    move |webview, callback, index, body| {
        deliver(
            webview.try_state::<Deliveries>().as_deref(),
            &diagnostics,
            webview.label(),
            callback,
            index,
            body,
            |script| webview.eval(script),
        );
        true
    }
}

/// Evaluates one frame's script and records a failure against its channel.
/// A frame parked for the script is dropped again when evaluation fails.
fn deliver<E: std::error::Error + Send + Sync + 'static>(
    deliveries: Option<&Deliveries>,
    diagnostics: &Diagnostics,
    webview: &str,
    callback: CallbackFn,
    index: usize,
    body: &InvokeResponseBody,
    evaluate: impl FnOnce(String) -> std::result::Result<(), E>,
) {
    let delivered = message(deliveries, webview, callback, body).and_then(|(message, parked)| {
        evaluate(script(callback, index, &message)).map_err(|e| {
            if let (Some(deliveries), Some(id)) = (deliveries, parked) {
                deliveries.take(webview, &id);
            }
            failure().caused_by(e)
        })
    });
    if let Err(error) = delivered {
        if let Some(deliveries) = deliveries {
            deliveries.record(webview, callback.0);
        }
        diagnostics.failure(error);
    }
}

fn failure() -> ApplicationError {
    ApplicationError::new(ErrorCode::WriteFailed, Operation::Webview)
}

/// The JavaScript value a frame becomes, and the id of the frame it parked.
fn message(
    deliveries: Option<&Deliveries>,
    webview: &str,
    callback: CallbackFn,
    body: &InvokeResponseBody,
) -> Result<(String, Option<String>)> {
    let bytes = match body {
        InvokeResponseBody::Json(json) => return Ok((json.clone(), None)),
        InvokeResponseBody::Raw(bytes) => bytes,
    };
    let parked = match deliveries {
        Some(deliveries) => deliveries.park(webview, callback.0, bytes)?,
        None => None,
    };
    Ok(match parked {
        Some(id) => (format!("{{\"raw_frame\":\"{id}\"}}"), Some(id)),
        None => (
            format!(
                "new Uint8Array({}).buffer",
                serde_json::to_string(bytes).map_err(|e| failure().caused_by(e))?
            ),
            None,
        ),
    })
}

/// The callback invocation Tauri itself evaluates for a directly delivered frame.
fn script(callback: CallbackFn, index: usize, message: &str) -> String {
    format!(
        "window.__TAURI_INTERNALS__.runCallback({}, {{ message: {message}, index: {index} }})",
        callback.0
    )
}

/// The bytes of the raw frame a channel message named `frame`, answered as
/// binary. A frame is handed over once, and only to the webview it was sent
/// to; an unknown, taken or dropped frame is refused.
#[tauri::command]
fn shell_channel_frame<R: Runtime>(
    webview: Webview<R>,
    deliveries: State<'_, Deliveries>,
    frame: String,
) -> Result<Response> {
    let mut bytes = deliveries
        .take(webview.label(), &frame)
        .ok_or_else(|| ApplicationError::new(ErrorCode::InvalidArguments, Operation::Webview))?;
    // Moved, not copied: the buffer left behind is empty.
    Ok(Response::new(std::mem::take(&mut *bytes)))
}

pub fn commands<R: Runtime>() -> Commands<R> {
    crate::app::commands![shell_channel_frame]
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::{
        str::FromStr,
        time::{Duration, Instant},
    };
    use tauri::{
        WebviewWindowBuilder,
        ipc::{InvokeBody, JavaScriptChannelId},
        test::{
            INVOKE_KEY, MockRuntime, get_ipc_response, mock_builder, mock_context, noop_assets,
        },
        webview::InvokeRequest,
    };

    /// Evaluates one frame through `deliver` and returns the script it built.
    fn delivered(
        deliveries: &Deliveries,
        callback: u32,
        index: usize,
        body: &InvokeResponseBody,
    ) -> String {
        let mut evaluated = None;
        deliver(
            Some(deliveries),
            &Diagnostics::default(),
            "main",
            CallbackFn(callback),
            index,
            body,
            |script| {
                evaluated = Some(script);
                Ok::<(), std::io::Error>(())
            },
        );
        evaluated.expect("a script")
    }

    /// The id a `{"raw_frame": id}` script names.
    fn named(script: &str) -> String {
        let start = script.find("\"raw_frame\":\"").expect("a parked frame") + 13;
        script[start..start + FRAME_ID_BYTES * 2].to_owned()
    }

    /// JPEG-like bytes: no run or digit pattern a byte array would compress.
    fn jpeg_like(length: usize, seed: u64) -> Vec<u8> {
        let mut state = seed | 1;
        (0..length)
            .map(|_| {
                state ^= state << 13;
                state ^= state >> 7;
                state ^= state << 17;
                state.to_le_bytes()[0]
            })
            .collect()
    }

    #[test]
    fn frames_become_callback_invocations() {
        let deliveries = Deliveries::default();
        assert_eq!(
            delivered(&deliveries, 7, 3, &InvokeResponseBody::Raw(vec![0, 255])),
            "window.__TAURI_INTERNALS__.runCallback(7, { message: new Uint8Array([0,255]).buffer, index: 3 })"
        );
        assert_eq!(
            delivered(
                &deliveries,
                7,
                4,
                &InvokeResponseBody::Json("{\"a\":1}".into())
            ),
            "window.__TAURI_INTERNALS__.runCallback(7, { message: {\"a\":1}, index: 4 })"
        );
    }

    #[test]
    fn a_fetching_channels_raw_frame_is_named_and_taken_once_by_its_webview() {
        let deliveries = Deliveries::default();
        deliveries.fetch_raw("main", 7);
        let frame = jpeg_like(4096, 1);
        let script = delivered(&deliveries, 7, 5, &InvokeResponseBody::Raw(frame.clone()));
        let id = named(&script);
        assert!(is_lower_hex(&id), "{script}");
        assert_eq!(
            script,
            format!(
                "window.__TAURI_INTERNALS__.runCallback(7, {{ message: {{\"raw_frame\":\"{id}\"}}, index: 5 }})"
            )
        );
        // Another channel of the same webview still evaluates its bytes.
        assert!(
            delivered(&deliveries, 8, 0, &InvokeResponseBody::Raw(vec![1]))
                .contains("Uint8Array([1])")
        );
        assert!(
            deliveries.take("other", &id).is_none(),
            "only the webview it was sent to"
        );
        assert!(deliveries.take("main", &"0".repeat(32)).is_none());
        assert_eq!(*deliveries.take("main", &id).unwrap(), frame);
        assert!(deliveries.take("main", &id).is_none(), "taken once");
        // Ids are not sequential.
        let next = named(&delivered(
            &deliveries,
            7,
            6,
            &InvokeResponseBody::Raw(vec![2]),
        ));
        assert_ne!(next, id);
        assert!(!deliveries.failed("main", 7));
    }

    fn is_lower_hex(id: &str) -> bool {
        id.len() == FRAME_ID_BYTES * 2
            && id
                .bytes()
                .all(|byte| matches!(byte, b'0'..=b'9' | b'a'..=b'f'))
    }

    #[test]
    fn a_frame_beyond_the_limit_pushes_out_the_oldest_and_marks_its_channel() {
        let deliveries = Deliveries::default();
        deliveries.fetch_raw("main", 1);
        deliveries.fetch_raw("main", 2);
        let oldest = named(&delivered(
            &deliveries,
            1,
            0,
            &InvokeResponseBody::Raw(vec![1]),
        ));
        let waiting: Vec<_> = (0..PARKED_LIMIT)
            .map(|index| {
                named(&delivered(
                    &deliveries,
                    2,
                    index,
                    &InvokeResponseBody::Raw(vec![2]),
                ))
            })
            .collect();
        assert!(deliveries.take("main", &oldest).is_none());
        assert!(
            deliveries.failed("main", 1),
            "the channel that lost a frame is told"
        );
        assert!(!deliveries.failed("main", 2));
        for id in waiting {
            assert_eq!(*deliveries.take("main", &id).unwrap(), [2]);
        }
    }

    #[test]
    fn a_released_or_forgotten_channel_leaves_no_frame_behind() {
        let deliveries = Deliveries::default();
        deliveries.fetch_raw("main", 1);
        deliveries.fetch_raw("main", 2);
        let released = named(&delivered(
            &deliveries,
            1,
            0,
            &InvokeResponseBody::Raw(vec![1]),
        ));
        let kept = named(&delivered(
            &deliveries,
            2,
            0,
            &InvokeResponseBody::Raw(vec![2]),
        ));
        deliveries.release("main", 1);
        assert!(deliveries.take("main", &released).is_none());
        assert!(
            delivered(&deliveries, 1, 1, &InvokeResponseBody::Raw(vec![1])).contains("Uint8Array")
        );
        deliveries.forget("main");
        assert!(deliveries.take("main", &kept).is_none());
        assert!(
            delivered(&deliveries, 2, 1, &InvokeResponseBody::Raw(vec![2])).contains("Uint8Array")
        );
    }

    #[test]
    fn a_failed_evaluation_marks_its_channel_once_and_is_reported() {
        let diagnostics = Diagnostics::default();
        let deliveries = Deliveries::default();
        let body = InvokeResponseBody::Raw(vec![1]);
        let mut evaluated = None;
        deliver(
            Some(&deliveries),
            &diagnostics,
            "main",
            CallbackFn(9),
            2,
            &body,
            |script| {
                evaluated = Some(script);
                Err(std::io::Error::other("the webview is gone"))
            },
        );
        assert_eq!(
            evaluated.as_deref(),
            Some(delivered(&Deliveries::default(), 9, 2, &body).as_str())
        );
        assert_eq!(diagnostics.snapshot(0).events.len(), 1);
        assert!(!deliveries.failed("main", 8));
        assert!(!deliveries.failed("other", 9));
        assert!(deliveries.failed("main", 9));
        assert!(!deliveries.failed("main", 9), "the query clears the mark");
        // A delivered frame marks nothing and reports nothing.
        deliver(
            Some(&deliveries),
            &diagnostics,
            "main",
            CallbackFn(9),
            3,
            &body,
            |_| Ok::<(), std::io::Error>(()),
        );
        assert!(!deliveries.failed("main", 9));
        assert_eq!(diagnostics.snapshot(0).events.len(), 1);
        // Without a managed record the failure still reaches diagnostics.
        deliver(None, &diagnostics, "main", CallbackFn(9), 4, &body, |_| {
            Err(std::io::Error::other("the webview is gone"))
        });
        assert_eq!(diagnostics.snapshot(0).events.len(), 2);
        // A parked frame whose script did not run is not left waiting.
        deliveries.fetch_raw("main", 9);
        let mut script = None;
        deliver(
            Some(&deliveries),
            &diagnostics,
            "main",
            CallbackFn(9),
            5,
            &body,
            |evaluated| {
                script = Some(evaluated);
                Err(std::io::Error::other("the webview is gone"))
            },
        );
        assert!(deliveries.take("main", &named(&script.unwrap())).is_none());
        assert!(deliveries.failed("main", 9));
    }

    fn webview_url() -> tauri::Url {
        if cfg!(windows) {
            "http://tauri.localhost"
        } else {
            "tauri://localhost"
        }
        .parse()
        .unwrap()
    }

    fn fetch_first_queued(
        builder: tauri::Builder<MockRuntime>,
    ) -> std::result::Result<(), serde_json::Value> {
        let app = builder.build(mock_context(noop_assets())).unwrap();
        let window = WebviewWindowBuilder::new(&app, "main", Default::default())
            .build()
            .unwrap();
        let webview: &Webview<MockRuntime> = window.as_ref();
        let channel = JavaScriptChannelId::from_str("__CHANNEL__:7")
            .unwrap()
            .channel_on::<MockRuntime, Response>(webview.clone());
        // Larger than every size Tauri delivers directly, so without an
        // interceptor the frame waits in the fetch queue.
        channel.send(Response::new(vec![0x5a; 65536])).unwrap();
        let mut headers = tauri::http::HeaderMap::new();
        headers.insert(
            "Tauri-Channel-Id",
            tauri::http::HeaderValue::from_static("0"),
        );
        get_ipc_response(
            &window,
            InvokeRequest {
                cmd: "plugin:__TAURI_CHANNEL__|fetch".into(),
                callback: CallbackFn(0),
                error: CallbackFn(1),
                url: webview_url(),
                body: Default::default(),
                headers,
                invoke_key: INVOKE_KEY.to_owned(),
            },
        )
        .map(|_| ())
    }

    #[test]
    fn intercepted_frames_never_reach_the_fetch_queue() {
        let diagnostics = Arc::new(Diagnostics::default());
        let intercepted = fetch_first_queued(
            mock_builder().channel_interceptor(interceptor(diagnostics.clone())),
        );
        assert_eq!(intercepted, Err(serde_json::Value::from("data not found")));
        assert!(diagnostics.snapshot(0).events.is_empty());
        // Control: the same frame without the interceptor is fetchable.
        assert_eq!(fetch_first_queued(mock_builder()), Ok(()));
    }

    fn take_frame(
        window: &tauri::WebviewWindow<MockRuntime>,
        frame: &str,
    ) -> std::result::Result<InvokeResponseBody, serde_json::Value> {
        get_ipc_response(
            window,
            InvokeRequest {
                cmd: "shell_channel_frame".into(),
                callback: CallbackFn(0),
                error: CallbackFn(1),
                url: webview_url(),
                body: InvokeBody::Json(serde_json::json!({ "frame": frame })),
                headers: Default::default(),
                invoke_key: INVOKE_KEY.to_owned(),
            },
        )
    }

    /// The parked frames of the app's `Deliveries`, oldest first.
    fn parked_ids(app: &tauri::App<MockRuntime>) -> Vec<String> {
        lock(&app.state::<Deliveries>().fetched)
            .frames
            .iter()
            .map(|frame| frame.id.clone())
            .collect()
    }

    /// A Sede view image travels the real channel and command path, and the
    /// measured script and transfer sizes are printed with the test output.
    #[test]
    fn a_fetching_channel_delivers_view_images_as_binary_at_a_fraction_of_the_script() {
        const FRAMES: usize = 15;
        const IMAGE: usize = 160 * 1024;
        let diagnostics = Arc::new(Diagnostics::default());
        let app = mock_builder()
            .channel_interceptor(interceptor(diagnostics.clone()))
            .manage(Deliveries::default())
            .invoke_handler(tauri::generate_handler![shell_channel_frame])
            .build(mock_context(noop_assets()))
            .unwrap();
        let window = WebviewWindowBuilder::new(&app, "main", Default::default())
            .build()
            .unwrap();
        let webview: &Webview<MockRuntime> = window.as_ref();
        let channel = JavaScriptChannelId::from_str("__CHANNEL__:7")
            .unwrap()
            .channel_on::<MockRuntime, InvokeResponseBody>(webview.clone());
        let images: Vec<_> = (0..FRAMES)
            .map(|seed| jpeg_like(IMAGE, seed as u64 + 1))
            .collect();

        // Before: an unregistered channel evaluates each image as a byte array.
        let evaluated = Deliveries::default();
        let started = Instant::now();
        let before: usize = images
            .iter()
            .enumerate()
            .map(|(index, image)| {
                delivered(
                    &evaluated,
                    7,
                    index,
                    &InvokeResponseBody::Raw(image.clone()),
                )
                .len()
            })
            .sum();
        let before_time = started.elapsed();

        // After: the channel fetches, so each image is named and taken as binary.
        let fetch = RawFetch::new(webview.clone(), channel.id());
        let deliveries = app.state::<Deliveries>();
        let started = Instant::now();
        let mut after_script = 0;
        let mut after_bytes = 0;
        for (index, image) in images.iter().enumerate() {
            let script = delivered(
                &deliveries,
                channel.id(),
                index,
                &InvokeResponseBody::Raw(image.clone()),
            );
            after_script += script.len();
            let InvokeResponseBody::Raw(bytes) = take_frame(&window, &named(&script)).unwrap()
            else {
                panic!("a binary answer");
            };
            assert_eq!(&bytes, image, "the exact bytes, as binary");
            after_bytes += bytes.len();
        }
        let after_time = started.elapsed();
        assert!(!fetch.failed());
        assert!(diagnostics.snapshot(0).events.is_empty());

        let per_frame = |total: usize| total / FRAMES;
        let per_frame_time = |total: Duration| total / u32::try_from(FRAMES).unwrap();
        eprintln!(
            "view image delivery, {FRAMES} frames of {IMAGE} bytes: byte array {} script bytes and {:?} per frame; \
             fetched {} script bytes plus {} binary bytes and {:?} per frame",
            per_frame(before),
            per_frame_time(before_time),
            per_frame(after_script),
            per_frame(after_bytes),
            per_frame_time(after_time),
        );
        assert!(
            per_frame(before) > 3 * IMAGE,
            "a byte array costs over three script bytes per byte"
        );
        assert!(
            per_frame(after_script) < 160,
            "only the frame's name is script"
        );
        assert_eq!(per_frame(after_bytes), IMAGE);

        // Sent through the channel, the interceptor parks it the same way.
        channel
            .send(InvokeResponseBody::Raw(images[0].clone()))
            .unwrap();
        let [id] = &parked_ids(&app)[..] else {
            panic!("one waiting frame");
        };
        let id = id.clone();
        assert!(
            matches!(take_frame(&window, &id), Ok(InvokeResponseBody::Raw(bytes)) if bytes == images[0])
        );
        assert!(take_frame(&window, &id).is_err(), "a frame is taken once");
        drop(fetch);
        channel.send(InvokeResponseBody::Raw(vec![1])).unwrap();
        assert!(
            parked_ids(&app).is_empty(),
            "a released channel parks nothing"
        );
    }
}
