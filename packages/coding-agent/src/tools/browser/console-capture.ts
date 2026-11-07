import { toError } from "@oh-my-pi/pi-utils";
import type { Protocol } from "devtools-protocol";
import type { CDPSession, ConsoleMessage, HTTPRequest, Page } from "puppeteer-core";

/** Console levels accepted by the browser console query. */
export type BrowserConsoleLevel = "log" | "info" | "warn" | "error" | "debug";

/** Options for reading captured page console messages. */
export interface BrowserConsoleOptions {
	/** Return only messages at this console level. */
	level?: BrowserConsoleLevel;
	/** Return entries whose sequence is greater than this cursor. */
	since?: number;
	/** Clear the shared capture buffer after reading. */
	clear?: boolean;
	/** Maximum number of entries to return. */
	limit?: number;
}

/** Options for reading captured page errors and failed requests. */
export interface BrowserErrorOptions {
	/** Return entries whose sequence is greater than this cursor. */
	since?: number;
	/** Clear the shared capture buffer after reading. */
	clear?: boolean;
	/** Maximum number of entries to return. */
	limit?: number;
}

/** One captured page console message. */
export interface BrowserConsoleEntry {
	/** Monotonically increasing capture sequence. */
	seq: number;
	/** Capture time as Unix milliseconds. */
	ts: number;
	/** Captured entry kind. */
	type: "console";
	/** Console message level. */
	level: BrowserConsoleLevel;
	/** Browser-rendered console text. */
	text: string;
	/** Source URL, line, and column when Chromium reports them. */
	location?: string;
	/** Best-effort JSON-safe console arguments. */
	args: unknown[];
}

/** One captured uncaught exception or failed request. */
export interface BrowserErrorEntry {
	/** Monotonically increasing capture sequence. */
	seq: number;
	/** Capture time as Unix milliseconds. */
	ts: number;
	/** Captured error kind. */
	type: "pageerror" | "requestfailed";
	/** Error severity. */
	level: "error";
	/** Exception or failed-request description. */
	text: string;
	/** Source location or failed-request URL when available. */
	location?: string;
	/** Exception stack when available. */
	stack?: string;
}

/** Result of a bounded capture-buffer query. */
export interface BrowserCaptureResult<T> {
	/** Matching captured entries in sequence order. */
	entries: T[];
	/** Sequence cursor for a subsequent `since` query. */
	nextSeq: number;
	/** Entries evicted by bounded-buffer overflow since the last clear. */
	dropped: number;
}

type BrowserCaptureEntry = BrowserConsoleEntry | BrowserErrorEntry;

interface RawPageConsoleRecord {
	kind: "console";
	ts: number;
	level: BrowserConsoleLevel;
	location?: string;
	args: unknown[];
}

interface RawPageErrorRecord {
	kind: "pageerror";
	ts: number;
	isNonError?: boolean;
	value?: unknown;
	text?: string;
	location?: string;
	stack?: string;
}

type RawPageCaptureRecord = RawPageConsoleRecord | RawPageErrorRecord;

interface DrainedConsoleBatch {
	entries: RawPageCaptureRecord[];
	dropped: number;
}

const DEFAULT_CAPTURE_LIMIT = 500;
const MAX_ARG_CHARS = 8_192;
const MAX_TEXT_CHARS = 16_384;
const MAX_STACK_CHARS = 32_768;
const UNDEFINED_SENTINEL_KEY = "__ompConsoleUndefined";

function boundedText(value: string, limit: number): string {
	return value.length <= limit ? value : `${value.slice(0, limit)}…`;
}

function decodePageArgument(value: unknown): unknown {
	if (
		value &&
		typeof value === "object" &&
		!Array.isArray(value) &&
		Object.keys(value).length === 1 &&
		(value as Record<string, unknown>)[UNDEFINED_SENTINEL_KEY] === true
	) {
		return undefined;
	}
	return value;
}

/**
 * Render one console argument as text without throwing.
 *
 * `String()` throws for objects whose `toString`/`valueOf` are not callable
 * (e.g. JSON payloads `{ toString: "x" }`); those fall back to JSON, then to
 * the object's `Object.prototype.toString` tag, then to a fixed marker (the tag
 * itself throws for revoked proxies). Mirrored page-side in
 * {@link CMUX_CONSOLE_CAPTURE_SCRIPT}.
 */
function consoleArgumentText(value: unknown): string {
	try {
		return String(value);
	} catch {
		try {
			const json = JSON.stringify(value);
			if (json !== undefined) return json;
		} catch {
			// Cyclic or otherwise unserializable; use the object tag below.
		}
		try {
			return Object.prototype.toString.call(value);
		} catch {
			return "[unserializable]";
		}
	}
}

function consoleLevel(message: ConsoleMessage): BrowserConsoleLevel {
	const type = message.type();
	switch (type) {
		case "debug":
		case "info":
		case "warn":
		case "error":
		case "log":
			return type;
		case "assert":
			return "error";
		default:
			return "log";
	}
}

function consoleLocation(message: ConsoleMessage): string | undefined {
	const location = message.location();
	if (!location.url) return undefined;
	const line = location.lineNumber;
	const column = location.columnNumber;
	return line === undefined ? location.url : `${location.url}:${line}:${column ?? 0}`;
}

function parseV8StackLineLocation(line: string): { url: string; line: string; col: string } | undefined {
	const trimmed = line.trim();
	if (!trimmed.startsWith("at ")) return undefined;
	let site = trimmed.slice(3).trim();
	if (site.endsWith(")")) {
		const openParen = site.indexOf(" (");
		if (openParen >= 0) {
			site = site.slice(openParen + 2, -1);
		} else if (site.startsWith("(")) {
			site = site.slice(1, -1);
		}
	}
	const match = /^(.+):(\d+):(\d+)$/.exec(site);
	if (!match?.[1] || !match[2] || !match[3]) return undefined;
	return { url: match[1], line: match[2], col: match[3] };
}

function errorLocation(error: Error): string | undefined {
	const stack = error.stack;
	if (!stack) return undefined;
	for (const line of stack.split("\n").slice(1)) {
		const parsed = parseV8StackLineLocation(line);
		if (parsed) return `${parsed.url}:${parsed.line}:${parsed.col}`;
	}
	return undefined;
}

function boundedArgument(value: unknown): unknown {
	const json = JSON.stringify(value);
	if (json === undefined) return boundedText(String(value), MAX_ARG_CHARS);
	if (json.length <= MAX_ARG_CHARS) return value;
	return `${json.slice(0, MAX_ARG_CHARS)}…`;
}

async function serializeArgument(message: ConsoleMessage, index: number): Promise<unknown> {
	const handle = message.args()[index];
	if (!handle) return undefined;
	const remote = handle.remoteObject();
	if ("value" in remote) return boundedArgument(remote.value);
	if (remote.unserializableValue) return remote.unserializableValue;
	try {
		return boundedArgument(await handle.jsonValue());
	} catch {
		return boundedText(handle.toString(), MAX_ARG_CHARS);
	}
}

/**
 * Text for a thrown or rejected non-Error value.
 * Mirrored page-side by `reasonText` in {@link CMUX_CONSOLE_CAPTURE_SCRIPT}.
 */
function exceptionValueText(value: unknown): string {
	return typeof value === "string" ? value : (JSON.stringify(value) ?? consoleArgumentText(value));
}

function buildIsolatedConsoleInitScript(eventName: string, limit: number): string {
	return `(() => {
	const KEY = "__ompConsoleBridge";
	let bridge = globalThis[KEY];
	if (!bridge) {
		bridge = {
			entries: [],
			dropped: 0,
			activeEvent: "",
			installedEvents: Object.create(null),
			drain() {
				const entries = bridge.entries;
				const dropped = bridge.dropped;
				bridge.entries = [];
				bridge.dropped = 0;
				return { entries, dropped };
			},
		};
		globalThis[KEY] = bridge;
	}
	const evtName = ${JSON.stringify(eventName)};
	bridge.activeEvent = evtName;
	if (!bridge.installedEvents[evtName]) {
		bridge.installedEvents[evtName] = true;
		addEventListener(
			evtName,
			event => {
				event.stopImmediatePropagation();
				if (bridge.activeEvent !== evtName) return;
				try {
					const parsed = JSON.parse(event.detail);
					if (parsed && typeof parsed === "object") {
						bridge.entries.push(parsed);
						while (bridge.entries.length > ${limit}) {
							bridge.entries.shift();
							bridge.dropped += 1;
						}
					}
				} catch {}
			},
			true,
		);
	}
	return true;
})()`;
}

const ISOLATED_CONSOLE_DRAIN_SCRIPT = `(() => {
	const bridge = globalThis.__ompConsoleBridge;
	return bridge ? bridge.drain() : { entries: [], dropped: 0 };
})()`;

/**
 * Main-world console and error capture hook that emits serialized records to the
 * isolated world via a capture-swallowed `CustomEvent` without `Runtime.enable`,
 * without adding any globals or symbols to `window`, and without invoking user
 * property getters or `Error.prepareStackTrace` traps.
 */
function buildMainWorldConsoleHookScript(eventName: string): string {
	return `(() => {
	const Reflect_apply = Reflect.apply;
	const Reflect_getOwnPropertyDescriptor = Reflect.getOwnPropertyDescriptor;
	const Reflect_getPrototypeOf = Reflect.getPrototypeOf;
	const Reflect_ownKeys = Reflect.ownKeys;
	const Object_prototype = Object.prototype;
	const Object_create = Object.create;
	const Object_defineProperty = Object.defineProperty;
	const Object_is = Object.is;
	const Object_toString = Object.prototype.toString;
	const Array_isArray = Array.isArray;
	const Error_ctor = Error;
	const Error_captureStackTrace = Error.captureStackTrace;
	const Native_ErrorStackGetter = Reflect_getOwnPropertyDescriptor(new Error_ctor(), "stack")?.get;
	const Date_now = Date.now;
	const Date_ctor = Date;
	const Date_toISOString = Date.prototype.toISOString;
	const RegExp_ctor = RegExp;
	const RegExp_toString = RegExp.prototype.toString;
	const RegExp_exec = RegExp.prototype.exec;
	const Symbol_toString = Symbol.prototype.toString;
	const String_slice = String.prototype.slice;
	const String_split = String.prototype.split;
	const String_trim = String.prototype.trim;
	const String_indexOf = String.prototype.indexOf;
	const String_startsWith = String.prototype.startsWith;
	const String_endsWith = String.prototype.endsWith;
	const Number_isFinite = Number.isFinite;
	const JSON_stringify = JSON.stringify;
	const Proxy_ctor = Proxy;
	const WeakSet_ctor = WeakSet;
	const WeakSet_add = WeakSet.prototype.add;
	const WeakSet_has = WeakSet.prototype.has;
	const CustomEvent_ctor = CustomEvent;
	const EventTarget_dispatchEvent = EventTarget.prototype.dispatchEvent;
	const EventTarget_addEventListener = EventTarget.prototype.addEventListener;
	const Node_ctor = typeof Node === "function" ? Node : undefined;
	const Function_prototype = Function.prototype;
	const EVENT_NAME = ${JSON.stringify(eventName)};
	const UNDEF_MARKER = { ${JSON.stringify(UNDEFINED_SENTINEL_KEY)}: true };
	const SITE_LOCATION_RE = /^(.+):(\\d+):(\\d+)$/;

	const emit = payload => {
		try {
			const json = JSON_stringify(payload);
			if (typeof json !== "string") return;
			const evt = new CustomEvent_ctor(EVENT_NAME, { detail: json });
			Reflect_apply(EventTarget_dispatchEvent, window, [evt]);
		} catch {}
	};

	const boundedStr = (str, max) =>
		str.length <= max ? str : Reflect_apply(String_slice, str, [0, max]) + "…";

	const hasCustomPrepareStackTrace = () => {
		try {
			const own = Reflect_getOwnPropertyDescriptor(Error_ctor, "prepareStackTrace");
			if (own && ("get" in own || "set" in own || own.value !== undefined)) return true;
			let proto = Reflect_getPrototypeOf(Error_ctor);
			while (proto && proto !== Object_prototype && proto !== Function_prototype) {
				const d = Reflect_getOwnPropertyDescriptor(proto, "prepareStackTrace");
				if (d && ("get" in d || "set" in d || d.value !== undefined)) return true;
				proto = Reflect_getPrototypeOf(proto);
			}
			const objDesc = Reflect_getOwnPropertyDescriptor(Object_prototype, "prepareStackTrace");
			if (objDesc && ("get" in objDesc || "set" in objDesc || objDesc.value !== undefined)) return true;
			return false;
		} catch {
			return true;
		}
	};

	const readSafeStringProp = (obj, key) => {
		try {
			let cur = obj;
			let depth = 0;
			while (cur && depth < 6) {
				const d = Reflect_getOwnPropertyDescriptor(cur, key);
				if (d) {
					return "value" in d && typeof d.value === "string" ? d.value : undefined;
				}
				cur = Reflect_getPrototypeOf(cur);
				depth += 1;
			}
		} catch {}
		return undefined;
	};

	const safeErrorSummary = err => {
		const name = readSafeStringProp(err, "name") || "Error";
		const msg = readSafeStringProp(err, "message") || "";
		return msg ? name + ": " + msg : name;
	};

	const safeReadStack = err => {
		if (!err || typeof err !== "object" || hasCustomPrepareStackTrace()) return undefined;
		try {
			const d = Reflect_getOwnPropertyDescriptor(err, "stack");
			if (!d) return undefined;
			if ("value" in d) {
				return typeof d.value === "string" ? boundedStr(d.value, ${MAX_STACK_CHARS}) : undefined;
			}
			if (Native_ErrorStackGetter && d.get === Native_ErrorStackGetter) {
				const raw = Reflect_apply(Native_ErrorStackGetter, err, []);
				return typeof raw === "string" ? boundedStr(raw, ${MAX_STACK_CHARS}) : undefined;
			}
		} catch {}
		return undefined;
	};

	const parseLocationFromStack = (stack, skipAnonymous) => {
		if (typeof stack !== "string") return undefined;
		const lines = Reflect_apply(String_split, stack, ["\\n"]);
		for (let i = 1; i < lines.length; i += 1) {
			const trimmed = Reflect_apply(String_trim, lines[i], []);
			if (!Reflect_apply(String_startsWith, trimmed, ["at "])) continue;
			let site = Reflect_apply(String_trim, Reflect_apply(String_slice, trimmed, [3]), []);
			if (Reflect_apply(String_endsWith, site, [")"])) {
				const openParen = Reflect_apply(String_indexOf, site, [" ("]);
				if (openParen >= 0) {
					site = Reflect_apply(String_slice, site, [openParen + 2, -1]);
				} else if (Reflect_apply(String_startsWith, site, ["("])) {
					site = Reflect_apply(String_slice, site, [1, -1]);
				}
			}
			const match = Reflect_apply(RegExp_exec, SITE_LOCATION_RE, [site]);
			if (!match) continue;
			const url = match[1];
			if (skipAnonymous && url === "<anonymous>") continue;
			return url + ":" + match[2] + ":" + match[3];
		}
		return undefined;
	};

	const captureCallerLocation = () => {
		if (!Native_ErrorStackGetter || hasCustomPrepareStackTrace()) return undefined;
		try {
			const probe = new Error_ctor();
			const stack = Reflect_apply(Native_ErrorStackGetter, probe, []);
			return parseLocationFromStack(stack, true);
		} catch {
			return undefined;
		}
	};

	const safeClone = (value, depth, seen) => {
		if (value === null || typeof value === "boolean" || typeof value === "string") return value;
		if (typeof value === "number") {
			if (!Number_isFinite(value)) return String(value);
			if (Object_is(value, -0)) return "-0";
			return value;
		}
		if (typeof value === "undefined") return "undefined";
		if (typeof value === "bigint") return value + "n";
		if (typeof value === "symbol") {
			try {
				return Reflect_apply(Symbol_toString, value, []);
			} catch {
				return "Symbol()";
			}
		}
		if (typeof value === "function") return "[Function]";
		try {
			Reflect_getPrototypeOf(value);
		} catch {
			return "[unserializable]";
		}
		try {
			if (value instanceof Error_ctor) return safeErrorSummary(value);
			if (value instanceof Date_ctor) {
				try {
					return Reflect_apply(Date_toISOString, value, []);
				} catch {
					return "Invalid Date";
				}
			}
			if (value instanceof RegExp_ctor) {
				try {
					return Reflect_apply(RegExp_toString, value, []);
				} catch {
					return "[object RegExp]";
				}
			}
			if (Node_ctor && value instanceof Node_ctor) {
				return Reflect_apply(Object_toString, value, []);
			}
		} catch {
			return "[unserializable]";
		}
		if (Reflect_apply(WeakSet_has, seen, [value])) return "[Circular]";
		if (depth >= 6) {
			try {
				return Reflect_apply(Object_toString, value, []);
			} catch {
				return "[Object]";
			}
		}
		Reflect_apply(WeakSet_add, seen, [value]);
		if (Array_isArray(value)) {
			const out = [];
			const len = value.length < 1000 ? value.length : 1000;
			for (let i = 0; i < len; i += 1) {
				const d = Reflect_getOwnPropertyDescriptor(value, i);
				if (d && "value" in d) {
					out[i] = safeClone(d.value, depth + 1, seen);
				} else {
					out[i] = null;
				}
			}
			return out;
		}
		const out = Object_create(null);
		let keys;
		try {
			keys = Reflect_ownKeys(value);
		} catch {
			return "[unserializable]";
		}
		const maxKeys = keys.length < 500 ? keys.length : 500;
		for (let i = 0; i < maxKeys; i += 1) {
			const key = keys[i];
			if (typeof key !== "string") continue;
			let d;
			try {
				d = Reflect_getOwnPropertyDescriptor(value, key);
			} catch {
				continue;
			}
			if (!d || !d.enumerable || !("value" in d)) continue;
			const propVal = d.value;
			if (propVal === undefined || typeof propVal === "function" || typeof propVal === "symbol") continue;
			Object_defineProperty(out, key, {
				value: safeClone(propVal, depth + 1, seen),
				enumerable: true,
				writable: true,
				configurable: true,
			});
		}
		return out;
	};

	const serializeConsoleArg = value => {
		if (value === undefined) return UNDEF_MARKER;
		const cloned = safeClone(value, 0, new WeakSet_ctor());
		try {
			const json = JSON_stringify(cloned);
			if (typeof json !== "string") return boundedStr(String(cloned), ${MAX_ARG_CHARS});
			if (json.length <= ${MAX_ARG_CHARS}) return cloned;
			return Reflect_apply(String_slice, json, [0, ${MAX_ARG_CHARS}]) + "…";
		} catch {
			return "[unserializable]";
		}
	};

	const consoleObj = globalThis.console;
	if (consoleObj && typeof consoleObj === "object") {
		const levels = ["log", "info", "warn", "error", "debug"];
		for (let i = 0; i < levels.length; i += 1) {
			const level = levels[i];
			const desc = Reflect_getOwnPropertyDescriptor(consoleObj, level);
			if (!desc || typeof desc.value !== "function" || desc.configurable === false) continue;
			const original = desc.value;
			const applyTrap = function apply(target, thisArg, args) {
				try {
					const serialized = [];
					for (let j = 0; j < args.length; j += 1) {
						serialized[j] = serializeConsoleArg(args[j]);
					}
					emit({
						kind: "console",
						ts: Date_now(),
						level,
						location: captureCallerLocation(),
						args: serialized,
					});
				} catch {}
				try {
					return Reflect_apply(target, thisArg, args);
				} catch (err) {
					if (err && (typeof err === "object" || typeof err === "function") && typeof Error_captureStackTrace === "function") {
						try {
							Error_captureStackTrace(err, applyTrap);
						} catch {}
					}
					throw err;
				}
			};
			const proxied = new Proxy_ctor(original, { apply: applyTrap });
			Object_defineProperty(consoleObj, level, {
				value: proxied,
				writable: desc.writable,
				enumerable: desc.enumerable,
				configurable: desc.configurable,
			});
		}
	}

	Reflect_apply(EventTarget_addEventListener, window, [
		"error",
		event => {
			try {
				const err = event ? event.error : undefined;
				const filename = event && typeof event.filename === "string" && event.filename ? event.filename : "";
				const loc = filename ? filename + ":" + (event.lineno || 0) + ":" + (event.colno || 0) : undefined;
				if (err !== undefined && !(err instanceof Error_ctor)) {
					emit({
						kind: "pageerror",
						ts: Date_now(),
						isNonError: true,
						value: serializeConsoleArg(err),
						location: loc,
					});
					return;
				}
				const stack = safeReadStack(err);
				const msg =
					(event && typeof event.message === "string" && event.message) ||
					(err instanceof Error_ctor ? safeErrorSummary(err) : "Uncaught error");
				emit({
					kind: "pageerror",
					ts: Date_now(),
					text: boundedStr(msg, ${MAX_TEXT_CHARS}),
					location: loc || parseLocationFromStack(stack, false),
					stack,
				});
			} catch {}
		},
		true,
	]);

	Reflect_apply(EventTarget_addEventListener, window, [
		"unhandledrejection",
		event => {
			try {
				const reason = event ? event.reason : undefined;
				if (reason instanceof Error_ctor) {
					const stack = safeReadStack(reason);
					emit({
						kind: "pageerror",
						ts: Date_now(),
						text: boundedStr(safeErrorSummary(reason), ${MAX_TEXT_CHARS}),
						location: parseLocationFromStack(stack, false),
						stack,
					});
					return;
				}
				emit({
					kind: "pageerror",
					ts: Date_now(),
					isNonError: true,
					value: serializeConsoleArg(reason),
				});
			} catch {}
		},
		true,
	]);
})()`;
}

/** Persistent bounded capture of page console messages, uncaught exceptions, and failed requests. */
export class PageConsoleCapture {
	readonly #limit: number;
	#entries: BrowserCaptureEntry[] = [];
	#nextSeq = 1;
	#dropped = 0;
	#pending: Promise<void> = Promise.resolve();
	#generation = 0;
	#page?: Page;
	#cdp?: CDPSession;
	#hookInstalled = false;
	#isolatedScriptId?: string;
	#mainScriptId?: string;
	#consoleHandler?: (message: ConsoleMessage) => void;
	#pageErrorHandler?: (error: unknown) => void;
	#requestFailedHandler?: (request: HTTPRequest) => void;
	#protocolRequestHandler?: (event: Protocol.Network.RequestWillBeSentEvent) => void;
	#protocolRequestFinishedHandler?: (event: Protocol.Network.LoadingFinishedEvent) => void;
	#protocolRequestFailedHandler?: (event: Protocol.Network.LoadingFailedEvent) => void;
	#protocolNavigationSyncHandler?: () => void;
	readonly #requests = new Map<Protocol.Network.RequestId, { method: string; url: string }>();

	constructor(limit = DEFAULT_CAPTURE_LIMIT) {
		this.#limit = Math.max(1, Math.floor(limit));
	}

	/** Sequence cursor immediately after the latest allocated capture entry. */
	get nextSequence(): number {
		return this.#nextSeq;
	}

	/** Attach capture listeners to a page once without enabling CDP `Runtime`. */
	async install(page: Page): Promise<void> {
		await this.detach();
		this.#page = page;
		const generation = this.#generation;
		this.#consoleHandler = message => {
			if (this.#hookInstalled) return;
			const seq = this.#allocateSequence();
			const ts = Date.now();
			this.#pending = this.#pending.then(async () => {
				const args = await Promise.all(message.args().map((_, index) => serializeArgument(message, index)));
				if (this.#generation !== generation) return;
				this.#push({
					seq,
					ts,
					type: "console",
					level: consoleLevel(message),
					text: boundedText(message.text(), MAX_TEXT_CHARS),
					location: consoleLocation(message),
					args,
				});
			});
		};
		this.#pageErrorHandler = error => {
			if (this.#hookInstalled) return;
			const normalized = toError(error);
			this.#push({
				seq: this.#allocateSequence(),
				ts: Date.now(),
				type: "pageerror",
				level: "error",
				text: boundedText(normalized.message || String(error), MAX_TEXT_CHARS),
				location: errorLocation(normalized),
				stack: normalized.stack ? boundedText(normalized.stack, MAX_STACK_CHARS) : undefined,
			});
		};
		this.#requestFailedHandler = request => {
			if (this.#cdp) return;
			const failure = request.failure()?.errorText ?? "Request failed";
			const url = request.url();
			this.#push({
				seq: this.#allocateSequence(),
				ts: Date.now(),
				type: "requestfailed",
				level: "error",
				text: boundedText(`${request.method()} ${url}: ${failure}`, MAX_TEXT_CHARS),
				location: url,
			});
		};
		page.on("console", this.#consoleHandler);
		page.on("pageerror", this.#pageErrorHandler);
		page.on("requestfailed", this.#requestFailedHandler);

		try {
			const eventName = `__omp_cc_${crypto.randomUUID()}`;
			const isolatedBody = buildIsolatedConsoleInitScript(eventName, this.#limit);
			const mainBody = buildMainWorldConsoleHookScript(eventName);
			const isoReg = await page.evaluateOnNewDocument(`//!world=isolated\n${isolatedBody}`);
			this.#isolatedScriptId = isoReg.identifier;
			const mainReg = await page.evaluateOnNewDocument(mainBody);
			this.#mainScriptId = mainReg.identifier;
			await page
				.mainFrame()
				.isolatedRealm()
				.evaluate(isolatedBody)
				.catch(() => undefined);
			await page
				.mainFrame()
				.mainRealm()
				.evaluate(mainBody)
				.catch(() => undefined);
			this.#hookInstalled = true;
		} catch {
			this.#hookInstalled = false;
		}

		let session: CDPSession | undefined;
		try {
			const activeSession = await page.createCDPSession();
			session = activeSession;
			this.#protocolRequestHandler = event => {
				this.#requests.set(event.requestId, { method: event.request.method, url: event.request.url });
			};
			this.#protocolRequestFinishedHandler = event => {
				this.#requests.delete(event.requestId);
			};
			this.#protocolRequestFailedHandler = event => {
				const request = this.#requests.get(event.requestId);
				this.#requests.delete(event.requestId);
				if (!request) return;
				this.#push({
					seq: this.#allocateSequence(),
					ts: Date.now(),
					type: "requestfailed",
					level: "error",
					text: boundedText(`${request.method} ${request.url}: ${event.errorText}`, MAX_TEXT_CHARS),
					location: request.url,
				});
			};
			this.#protocolNavigationSyncHandler = () => {
				void this.sync(150);
			};
			activeSession.on("Network.requestWillBeSent", this.#protocolRequestHandler);
			activeSession.on("Network.loadingFinished", this.#protocolRequestFinishedHandler);
			activeSession.on("Network.loadingFailed", this.#protocolRequestFailedHandler);
			activeSession.on("Page.frameRequestedNavigation", this.#protocolNavigationSyncHandler);
			activeSession.on("Page.domContentLoadedEventFired", this.#protocolNavigationSyncHandler);
			activeSession.on("Page.loadEventFired", this.#protocolNavigationSyncHandler);
			await Promise.all([activeSession.send("Network.enable"), activeSession.send("Page.enable")]);
			this.#cdp = activeSession;
		} catch {
			await session?.detach().catch(() => undefined);
			this.#protocolRequestHandler = undefined;
			this.#protocolRequestFinishedHandler = undefined;
			this.#protocolRequestFailedHandler = undefined;
			this.#protocolNavigationSyncHandler = undefined;
		}
	}

	/** Drain any buffered console and pageerror entries from the isolated world into memory. */
	async sync(timeoutMs = 1_000): Promise<void> {
		if (!this.#hookInstalled) {
			await this.#pending;
			return;
		}
		const generation = this.#generation;
		const runSync = async () => {
			const page = this.#page;
			if (this.#generation !== generation || !page || page.isClosed()) return;
			const { promise: timeoutPromise, resolve: resolveTimeout } = Promise.withResolvers<undefined>();
			const timer = setTimeout(() => resolveTimeout(undefined), timeoutMs);
			try {
				const drained = await Promise.race([
					page
						.mainFrame()
						.isolatedRealm()
						.evaluate(ISOLATED_CONSOLE_DRAIN_SCRIPT)
						.catch(() => undefined),
					timeoutPromise,
				]);
				if (this.#generation !== generation || !drained || typeof drained !== "object") return;
				const batch = drained as DrainedConsoleBatch;
				if (typeof batch.dropped === "number" && batch.dropped > 0) {
					this.#dropped += batch.dropped;
				}
				if (Array.isArray(batch.entries)) {
					const fallbackUrl = page.url();
					for (const record of batch.entries) {
						this.#ingestPageRecord(record, fallbackUrl);
					}
				}
			} finally {
				clearTimeout(timer);
			}
		};
		this.#pending = this.#pending.then(runSync, runSync);
		await this.#pending;
	}

	/** Read captured console messages after an optional sequence cursor. */
	async console(options: BrowserConsoleOptions = {}): Promise<BrowserCaptureResult<BrowserConsoleEntry>> {
		await this.sync();
		const entries = this.#query(
			entry => entry.type === "console" && (!options.level || entry.level === options.level),
			options.since,
			options.limit,
		) as BrowserConsoleEntry[];
		const result = this.#result(entries);
		if (options.clear) this.clear();
		return result;
	}

	/** Read captured uncaught exceptions and failed requests after an optional sequence cursor. */
	async errors(options: BrowserErrorOptions = {}): Promise<BrowserCaptureResult<BrowserErrorEntry>> {
		await this.sync();
		const entries = this.#query(
			entry => entry.type !== "console",
			options.since,
			options.limit,
		) as BrowserErrorEntry[];
		const result = this.#result(entries);
		if (options.clear) this.clear();
		return result;
	}

	/** Count captured page errors and failed requests at or after a sequence cursor. */
	errorCountSince(sequence: number): number {
		return this.#entries.filter(entry => entry.type !== "console" && entry.seq >= sequence).length;
	}

	/** Drain pending page entries and clear all captured entries while preserving sequence monotonicity. */
	async clearAsync(): Promise<void> {
		await this.sync(250);
		this.clear();
	}

	/** Clear captured entries and the overflow counter while preserving sequence monotonicity. */
	clear(): void {
		this.#entries = [];
		this.#dropped = 0;
	}

	/** Detach listeners and clear all captured state. */
	async detach(): Promise<void> {
		this.#generation += 1;
		if (this.#page && this.#consoleHandler) this.#page.off("console", this.#consoleHandler);
		if (this.#page && this.#pageErrorHandler) this.#page.off("pageerror", this.#pageErrorHandler);
		if (this.#page && this.#requestFailedHandler) this.#page.off("requestfailed", this.#requestFailedHandler);
		if (this.#page && !this.#page.isClosed()) {
			if (this.#isolatedScriptId) {
				await this.#page.removeScriptToEvaluateOnNewDocument(this.#isolatedScriptId).catch(() => undefined);
			}
			if (this.#mainScriptId) {
				await this.#page.removeScriptToEvaluateOnNewDocument(this.#mainScriptId).catch(() => undefined);
			}
		}
		if (this.#cdp && this.#protocolRequestHandler) {
			this.#cdp.off("Network.requestWillBeSent", this.#protocolRequestHandler);
		}
		if (this.#cdp && this.#protocolRequestFinishedHandler) {
			this.#cdp.off("Network.loadingFinished", this.#protocolRequestFinishedHandler);
		}
		if (this.#cdp && this.#protocolRequestFailedHandler) {
			this.#cdp.off("Network.loadingFailed", this.#protocolRequestFailedHandler);
		}
		if (this.#cdp && this.#protocolNavigationSyncHandler) {
			this.#cdp.off("Page.frameRequestedNavigation", this.#protocolNavigationSyncHandler);
			this.#cdp.off("Page.domContentLoadedEventFired", this.#protocolNavigationSyncHandler);
			this.#cdp.off("Page.loadEventFired", this.#protocolNavigationSyncHandler);
		}
		await this.#cdp?.detach().catch(() => undefined);
		this.#page = undefined;
		this.#cdp = undefined;
		this.#hookInstalled = false;
		this.#isolatedScriptId = undefined;
		this.#mainScriptId = undefined;
		this.#consoleHandler = undefined;
		this.#pageErrorHandler = undefined;
		this.#requestFailedHandler = undefined;
		this.#protocolRequestHandler = undefined;
		this.#protocolRequestFinishedHandler = undefined;
		this.#protocolRequestFailedHandler = undefined;
		this.#protocolNavigationSyncHandler = undefined;
		this.#requests.clear();
		this.clear();
	}

	#ingestPageRecord(record: RawPageCaptureRecord, fallbackUrl: string): void {
		if (!record || typeof record !== "object") return;
		if (record.kind === "console") {
			const args = Array.isArray(record.args) ? record.args.map(decodePageArgument) : [];
			const text = args.map(consoleArgumentText).join(" ");
			this.#push({
				seq: this.#allocateSequence(),
				ts: typeof record.ts === "number" ? record.ts : Date.now(),
				type: "console",
				level: record.level,
				text: boundedText(text, MAX_TEXT_CHARS),
				location: record.location || fallbackUrl || undefined,
				args,
			});
			return;
		}
		if (record.kind === "pageerror") {
			const text = record.isNonError
				? exceptionValueText(decodePageArgument(record.value))
				: (record.text ?? "Uncaught error");
			this.#push({
				seq: this.#allocateSequence(),
				ts: typeof record.ts === "number" ? record.ts : Date.now(),
				type: "pageerror",
				level: "error",
				text: boundedText(text, MAX_TEXT_CHARS),
				location: record.location || fallbackUrl || undefined,
				stack: record.stack ? boundedText(record.stack, MAX_STACK_CHARS) : undefined,
			});
		}
	}

	#allocateSequence(): number {
		const sequence = this.#nextSeq;
		this.#nextSeq += 1;
		return sequence;
	}

	#push(entry: BrowserCaptureEntry): void {
		const last = this.#entries.at(-1);
		if (!last || last.seq < entry.seq) {
			this.#entries.push(entry);
		} else {
			const index = this.#entries.findIndex(existing => existing.seq > entry.seq);
			this.#entries.splice(index < 0 ? this.#entries.length : index, 0, entry);
		}
		while (this.#entries.length > this.#limit) {
			this.#entries.shift();
			this.#dropped += 1;
		}
	}

	#query(predicate: (entry: BrowserCaptureEntry) => boolean, since?: number, limit?: number): BrowserCaptureEntry[] {
		const cursor = Number.isFinite(since) ? Math.floor(since ?? 0) : 0;
		const maximum = Number.isFinite(limit) ? Math.max(0, Math.floor(limit ?? this.#limit)) : this.#limit;
		return this.#entries.filter(entry => entry.seq > cursor && predicate(entry)).slice(0, maximum);
	}

	#result<T extends BrowserCaptureEntry>(entries: T[]): BrowserCaptureResult<T> {
		return {
			entries,
			nextSeq: entries.at(-1)?.seq ?? this.#nextSeq - 1,
			dropped: this.#dropped,
		};
	}
}

/** Page-side console capture hook used by the cmux backend. */
export const CMUX_CONSOLE_CAPTURE_SCRIPT = String.raw`(() => {
	if (globalThis.__ompConsoleCapture) return true;
	const state = { entries: [], nextSeq: 1, dropped: 0 };
	const push = entry => {
		state.entries.push({ seq: state.nextSeq++, ts: Date.now(), ...entry });
		while (state.entries.length > 500) { state.entries.shift(); state.dropped++; }
	};
	const text = value => {
		try { return String(value); } catch {
			try { const json = JSON.stringify(value); if (json !== undefined) return json; } catch {}
			try { return Object.prototype.toString.call(value); } catch { return "[unserializable]"; }
		}
	};
	const safe = value => {
		try {
			const json = JSON.stringify(value);
			return json && json.length > 8192 ? json.slice(0, 8192) + "…" : value;
		} catch { return text(value); }
	};
	const reasonText = value => {
		if (value instanceof Error) return text(value.message || value);
		const bounded = safe(value);
		return typeof bounded === "string" ? bounded : (JSON.stringify(bounded) ?? text(value));
	};
	for (const level of ["log", "info", "warn", "error", "debug"]) {
		const original = console[level].bind(console);
		console[level] = (...args) => {
			push({ type: "console", level, text: args.map(text).join(" ").slice(0, 16384), args: args.map(safe) });
			return original(...args);
		};
	}
	addEventListener("error", event => push({
		type: "pageerror", level: "error", text: String(event.message || event.error || "Uncaught error").slice(0, 16384),
		location: event.filename ? event.filename + ":" + event.lineno + ":" + event.colno : undefined,
		stack: event.error && event.error.stack ? String(event.error.stack).slice(0, 32768) : undefined,
	}));
	addEventListener("unhandledrejection", event => {
		const reason = event.reason;
		push({ type: "pageerror", level: "error", text: reasonText(reason).slice(0, 16384), stack: reason && reason.stack ? String(reason.stack).slice(0, 32768) : undefined });
	});
	globalThis.__ompConsoleCapture = state;
	return true;
})()`;
