import { beforeAll, describe, expect, it } from "bun:test";
import { stripVTControlCharacters } from "node:util";
import type { AssistantMessage } from "@oh-my-pi/pi-ai";
import { renderSegment } from "@oh-my-pi/pi-tui/status-line/segments";
import type { SegmentContext } from "@oh-my-pi/pi-tui/status-line/types";
import { initTheme } from "@oh-my-pi/pi-tui/theme";
import { calculateTokensPerSecond, calculateTtftMs } from "@oh-my-pi/pi-coding-agent/utils/token-rate";

beforeAll(async () => {
	await initTheme();
});

function assistantMessage(overrides?: Partial<AssistantMessage>): AssistantMessage {
	return {
		role: "assistant",
		content: [{ type: "text", text: "ok" }],
		api: "anthropic-messages",
		provider: "anthropic",
		model: "claude-sonnet-4.5",
		usage: {
			input: 10,
			output: 50,
			cacheRead: 0,
			cacheWrite: 0,
			totalTokens: 60,
			cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 },
		},
		stopReason: "stop",
		timestamp: 1_000,
		...overrides,
	};
}

function ctxWithTokenRate(tokensPerSecond: number | null, ttftMs: number | null = null): SegmentContext {
	return {
		usageStats: {
			input: 0,
			output: 0,
			cacheRead: 0,
			cacheWrite: 0,
			premiumRequests: 0,
			cost: 0,
			tokensPerSecond,
			ttftMs,
		},
	} as unknown as SegmentContext;
}

describe("token_rate status-line segment", () => {
	it("renders per-second throughput without a numeric slash path", () => {
		const rendered = renderSegment("token_rate", ctxWithTokenRate(35.5));
		const content = stripVTControlCharacters(rendered.content);

		expect(rendered.visible).toBe(true);
		expect(content).toContain("35.5");
		expect(content).toMatch(/\bts\b/i);
		expect(content).not.toContain("35.5/s");
		expect(content).not.toMatch(/\b\d+(?:\.\d+)?\/s\b/);
	});
});

describe("token rate calculation", () => {
	it("computes from completed message duration metadata", () => {
		const base = assistantMessage();
		const rate = calculateTokensPerSecond(
			[assistantMessage({ usage: { ...base.usage, output: 120 }, duration: 2_000 })],
			false,
		);
		expect(rate).toBe(60);
	});

	it("computes from elapsed time while streaming when duration metadata is missing", () => {
		const base = assistantMessage();
		const rate = calculateTokensPerSecond(
			[assistantMessage({ timestamp: 10_000, duration: undefined, usage: { ...base.usage, output: 45 } })],
			true,
			13_000,
		);
		expect(rate).toBe(15);
	});

	it("returns null for near-zero durations to avoid unstable spikes", () => {
		const base = assistantMessage();
		const rate = calculateTokensPerSecond(
			[assistantMessage({ duration: 50, usage: { ...base.usage, output: 5 } })],
			false,
		);
		expect(rate).toBeNull();
	});

	it("returns null when stream is interrupted and duration metadata is unavailable", () => {
		const rate = calculateTokensPerSecond([assistantMessage({ stopReason: "aborted", duration: undefined })], false);
		expect(rate).toBeNull();
	});

	it("returns null when usage metadata has no output tokens", () => {
		const base = assistantMessage();
		const rate = calculateTokensPerSecond(
			[assistantMessage({ usage: { ...base.usage, output: 0, totalTokens: 10 } })],
			false,
		);
		expect(rate).toBeNull();
	});
});

describe("ttft status-line segment", () => {
	it("renders milliseconds under one second", () => {
		const rendered = renderSegment("ttft", ctxWithTokenRate(null, 340));
		const content = stripVTControlCharacters(rendered.content);
		expect(rendered.visible).toBe(true);
		expect(content).toMatch(/ttft/i);
		expect(content).toContain("340ms");
	});

	it("renders seconds with one decimal above one second", () => {
		const rendered = renderSegment("ttft", ctxWithTokenRate(null, 1240));
		const content = stripVTControlCharacters(rendered.content);
		expect(rendered.visible).toBe(true);
		expect(content).toContain("1.2s");
	});

	it("is hidden when ttft is missing", () => {
		const rendered = renderSegment("ttft", ctxWithTokenRate(null, null));
		expect(rendered.visible).toBe(false);
	});
});

describe("ttft calculation", () => {
	it("uses provider-reported ttft when present", () => {
		expect(calculateTtftMs([assistantMessage({ ttft: 880, duration: 2_000 })], false)).toBe(880);
	});

	it("uses live wait while streaming with no output yet", () => {
		const base = assistantMessage();
		expect(
			calculateTtftMs(
				[assistantMessage({ timestamp: 10_000, ttft: undefined, usage: { ...base.usage, output: 0 } })],
				true,
				10_450,
			),
		).toBe(450);
	});
});
