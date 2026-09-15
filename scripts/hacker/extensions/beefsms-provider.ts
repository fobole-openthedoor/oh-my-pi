import type { ExtensionAPI, ProviderModelConfig } from "@oh-my-pi/pi-coding-agent";

const BASE_URL = "http://openai.beefsms.com:38888/v1";
const PROVIDER = "beefsms";

const ZERO_COST = { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 };

const MODELS: ProviderModelConfig[] = [
	{
		id: "happy/kimi-k3",
		name: "Kimi K3",
		reasoning: true,
		input: ["text"],
		contextWindow: 1_048_576,
		maxTokens: 131_072,
		cost: ZERO_COST,
		compat: {
			supportsDeveloperRole: false,
			supportsReasoningEffort: true,
			supportsStore: false,
			supportsStrictMode: false,
			maxTokensField: "max_tokens",
			thinkingFormat: "openai",
			streamMarkupHealingPattern: "kimi",
		},
	},
	{
		id: "happy/glm-5.3",
		name: "GLM-5.3",
		reasoning: true,
		input: ["text"],
		contextWindow: 1_048_576,
		maxTokens: 131_072,
		cost: ZERO_COST,
		compat: {
			supportsReasoningEffort: true,
			thinkingFormat: "zai",
			requiresReasoningContentForToolCalls: true,
		},
	},
	{
		id: "happy/qwen-3.8-fast",
		name: "Qwen 3.8 Fast",
		reasoning: true,
		input: ["text"],
		contextWindow: 1_048_576,
		maxTokens: 131_072,
		cost: ZERO_COST,
		compat: {
			supportsReasoningEffort: true,
			thinkingFormat: "qwen",
			requiresReasoningContentForToolCalls: true,
		},
	},
];

function stripKey(raw: string): string {
	return raw.trim().replace(/^bearer\b\s*/i, "").trim();
}

async function validateKey(apiKey: string, signal?: AbortSignal): Promise<void> {
	const response = await fetch(`${BASE_URL}/models`, {
		headers: { Authorization: `Bearer ${apiKey}` },
		signal,
	});
	if (response.status === 401 || response.status === 403) {
		throw new Error("Invalid beefsms API key (401/403 from /v1/models)");
	}
	if (!response.ok) {
		const body = await response.text().catch(() => "");
		throw new Error(
			`beefsms key check failed (HTTP ${response.status})${body ? `: ${body.slice(0, 200)}` : ""}`,
		);
	}
}

export default function (pi: ExtensionAPI) {
	pi.registerProvider(PROVIDER, {
		baseUrl: BASE_URL,
		api: "openai-completions",
		authHeader: true,
		models: MODELS,
		oauth: {
			name: "beefsms",
			async login(callbacks) {
				callbacks.onAuth({
					url: BASE_URL,
					instructions:
						"Gateway is already http://openai.beefsms.com:38888/v1. Paste your beefsms API key — no URL to edit.",
				});
				const answer = await callbacks.onPrompt({
					message: "Paste your beefsms API key",
					placeholder: "sk-...",
				});
				if (callbacks.signal?.aborted) {
					throw new Error("Login cancelled");
				}
				const key = stripKey(answer);
				if (!key) {
					throw new Error("API key is empty");
				}
				callbacks.onProgress?.("Checking key against beefsms /v1/models…");
				await validateKey(key, callbacks.signal);
				return key;
			},
		},
	});
}
