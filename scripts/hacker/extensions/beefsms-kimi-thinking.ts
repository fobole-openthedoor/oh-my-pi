import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";

type ChatMessage = {
	role?: string;
	content?: unknown;
	reasoning_content?: unknown;
	tool_calls?: unknown;
	[key: string]: unknown;
};

type ChatPayload = {
	model?: unknown;
	messages?: ChatMessage[];
	reasoning_effort?: unknown;
	thinking?: unknown;
	[key: string]: unknown;
};

function isBeefsmsKimiK3(model: { provider?: string; id?: string } | undefined): boolean {
	if (!model) return false;
	if (model.provider !== "beefsms") return false;
	return typeof model.id === "string" && model.id.includes("kimi-k3");
}

function hasToolCalls(message: ChatMessage): boolean {
	return Array.isArray(message.tool_calls) && message.tool_calls.length > 0;
}

function rewriteKimiPayload(payload: ChatPayload, effort: string): ChatPayload {
	const next: ChatPayload = { ...payload, messages: payload.messages?.map((message) => ({ ...message })) };
	next.reasoning_effort = effort;
	// K3 rejects the K2.x `thinking` object; effort is top-level only.
	delete next.thinking;

	for (const message of next.messages ?? []) {
		if (message.role !== "assistant") continue;

		// Official K3: replay real reasoning_content as-is. Never invent an
		// empty string — that locks this relay into a no-think prefix for the
		// rest of the tool loop. Collapsed caps/emoji thinking is stripped by
		// drop-degenerate-thinking.ts (runs after this rewrite).
		if (message.reasoning_content === "" || message.reasoning_content == null) {
			delete message.reasoning_content;
		}

		if (hasToolCalls(message) && (message.content == null || message.content === "")) {
			delete message.content;
		}
	}

	return next;
}

export default function (pi: ExtensionAPI) {
	pi.on("before_provider_request", (event, ctx) => {
		if (!isBeefsmsKimiK3(ctx.model)) return;
		if (!event.payload || typeof event.payload !== "object") return;

		const level = ctx.thinkingLevel;
		const effort = level === "low" || level === "high" || level === "max" ? level : "max";
		return rewriteKimiPayload(event.payload as ChatPayload, effort);
	});
}
