import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";

type ChatMessage = {
	role?: string;
	content?: unknown;
	reasoning_content?: unknown;
	reasoning?: unknown;
	tool_calls?: unknown;
	[key: string]: unknown;
};

type ChatPayload = {
	messages?: ChatMessage[];
	[key: string]: unknown;
};

const CAPS_WORD_LINE = /^[A-Z]{2,24}[.!?,:;]{0,3}$/;
const EMOJI_RE = /[\uD83C-\uDBFF][\uDC00-\uDFFF]|[🔥💥✅❌🎯🚀⚠❗💯✨🎉👍👎🔴🟢]/g;

function envOn(name: string): boolean {
	const value = process.env[name];
	return value !== "0" && value !== "false";
}

function countEmoji(text: string): number {
	return (text.match(EMOJI_RE) ?? []).length;
}

function isTelegraphLine(line: string): boolean {
	if (CAPS_WORD_LINE.test(line)) return true;
	if (countEmoji(line) === 0) return false;
	const stripped = line.replace(EMOJI_RE, "").replace(/\s+/g, " ").trim();
	return stripped.length === 0 || (stripped.length <= 8 && /^[A-Z.!? ]{0,8}$/.test(stripped));
}

/** True when thinking/reasoning text has collapsed into caps/emoji telegraph. */
export function isDegenerateThinking(text: unknown): boolean {
	if (typeof text !== "string") return false;
	if (text.length < 48) return false;
	const lines = text
		.split(/\r?\n/)
		.map((line) => line.trim())
		.filter(Boolean);
	let run = 0;
	let maxRun = 0;
	for (const line of lines) {
		if (isTelegraphLine(line)) {
			run += 1;
			if (run > maxRun) maxRun = run;
		} else {
			run = 0;
		}
	}
	if (maxRun >= 8) return true;
	if (countEmoji(text) >= 12) return true;
	const tail = lines.slice(-20);
	if (tail.length >= 10) {
		const bad = tail.filter(isTelegraphLine).length;
		if (bad / tail.length >= 0.7) return true;
	}
	return false;
}

function thinkingFromBlock(block: unknown): string {
	if (!block || typeof block !== "object") return "";
	const rec = block as Record<string, unknown>;
	const type = String(rec.type ?? "");
	if (type !== "thinking" && type !== "reasoning") return "";
	if (typeof rec.thinking === "string") return rec.thinking;
	if (typeof rec.text === "string") return rec.text;
	if (typeof rec.reasoning === "string") return rec.reasoning;
	return "";
}

export function stripDegenerateThinking(message: ChatMessage): boolean {
	let changed = false;
	if (isDegenerateThinking(message.reasoning_content)) {
		delete message.reasoning_content;
		changed = true;
	}
	if (isDegenerateThinking(message.reasoning)) {
		delete message.reasoning;
		changed = true;
	}
	if (!Array.isArray(message.content)) return changed;
	const next: unknown[] = [];
	for (const block of message.content) {
		const thinking = thinkingFromBlock(block);
		if (thinking && isDegenerateThinking(thinking)) {
			changed = true;
			continue;
		}
		next.push(block);
	}
	if (changed) message.content = next;
	return changed;
}

export function dropDegenerateFromPayload(payload: ChatPayload): ChatPayload {
	const messages = payload.messages;
	if (!Array.isArray(messages)) return payload;
	const next: ChatPayload = { ...payload, messages: messages.map((message) => ({ ...message })) };
	for (const message of next.messages ?? []) {
		if (message.role !== "assistant") continue;
		stripDegenerateThinking(message);
		if (message.reasoning_content === "" || message.reasoning_content == null) {
			delete message.reasoning_content;
		}
	}
	return next;
}

export default function (pi: ExtensionAPI) {
	pi.on("before_provider_request", (event) => {
		if (!envOn("DROP_DEGENERATE_THINKING")) return;
		if (!event.payload || typeof event.payload !== "object") return;
		return dropDegenerateFromPayload(event.payload as ChatPayload);
	});
}
