import type { ExtensionAPI, ProviderModelConfig } from "@oh-my-pi/pi-coding-agent";

const BASE_URL = "http://openai.beefsms.com:38888/v1";
const PROVIDER = "beefsms";
const COMPACTION_MODEL = "beefsms/deepseek-flash";

type BeefsmsModel = ProviderModelConfig & { compactionModel: string };

const ZERO_COST = { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 };

const GLM_COMPAT = {
	supportsReasoningEffort: true,
	thinkingFormat: "zai" as const,
	requiresReasoningContentForToolCalls: true,
};

function textModel(
	id: string,
	name: string,
	compat: NonNullable<ProviderModelConfig["compat"]>,
): BeefsmsModel {
	return {
		id,
		name,
		reasoning: true,
		input: ["text"],
		contextWindow: 1_048_576,
		maxTokens: 131_072,
		cost: ZERO_COST,
		compat,
		compactionModel: COMPACTION_MODEL,
	};
}

const MODELS: BeefsmsModel[] = [
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
		compactionModel: COMPACTION_MODEL,
	},
	textModel("happy/glm-5.3", "GLM-5.3", GLM_COMPAT),
	textModel("happy/glm-5.3-plus", "GLM-5.3 Plus", GLM_COMPAT),
	textModel("happy/qwen-3.8-fast", "Qwen 3.8 Fast", {
		supportsReasoningEffort: true,
		thinkingFormat: "qwen",
		requiresReasoningContentForToolCalls: true,
	}),
	{
		id: "deepseek-flash",
		name: "DeepSeek Flash",
		reasoning: true,
		input: ["text", "image"],
		contextWindow: 1_000_000,
		maxTokens: 384_000,
		cost: ZERO_COST,
		compat: {
			supportsReasoningEffort: true,
			thinkingFormat: "openai",
			maxTokensField: "max_tokens",
			reasoningContentField: "reasoning_content",
			requiresReasoningContentForToolCalls: true,
			requiresAssistantContentForToolCalls: true,
			allowsSyntheticReasoningContentForToolCalls: false,
			supportsToolChoice: false,
			stripImageInput: false,
			clampOutputToModelMax: true,
		},
		compactionModel: COMPACTION_MODEL,
	},
];

const MODELS_BY_ID = new Map(MODELS.map((model) => [model.id, model]));

function guessUnknownModel(id: string): BeefsmsModel {
	const lower = id.toLowerCase();
	if (lower.includes("glm")) return textModel(id, id, GLM_COMPAT);
	if (lower.includes("qwen")) {
		return textModel(id, id, {
			supportsReasoningEffort: true,
			thinkingFormat: "qwen",
			requiresReasoningContentForToolCalls: true,
		});
	}
	if (lower.includes("kimi")) {
		return textModel(id, id, {
			supportsDeveloperRole: false,
			supportsReasoningEffort: true,
			supportsStore: false,
			supportsStrictMode: false,
			maxTokensField: "max_tokens",
			thinkingFormat: "openai",
			streamMarkupHealingPattern: "kimi",
		});
	}
	if (lower.includes("deepseek")) {
		const flash = MODELS_BY_ID.get("deepseek-flash");
		if (flash) return { ...flash, id, name: id };
	}
	return textModel(id, id, {
		supportsReasoningEffort: true,
		thinkingFormat: "openai",
	});
}

function modelForId(id: string): BeefsmsModel {
	return MODELS_BY_ID.get(id) ?? guessUnknownModel(id);
}

function parseModelIds(payload: unknown): string[] {
	const rows = Array.isArray(payload)
		? payload
		: payload && typeof payload === "object" && "data" in payload && Array.isArray((payload as { data: unknown }).data)
			? (payload as { data: unknown[] }).data
			: [];
	const ids: string[] = [];
	for (const row of rows) {
		if (typeof row === "string" && row) ids.push(row);
		else if (row && typeof row === "object" && typeof (row as { id?: unknown }).id === "string") {
			const id = (row as { id: string }).id.trim();
			if (id) ids.push(id);
		}
	}
	return ids;
}

async function listGatewayIds(apiKey: string, signal?: AbortSignal): Promise<string[]> {
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
	return parseModelIds(await response.json());
}

function modelsFromIds(ids: string[]): BeefsmsModel[] {
	const seen = new Set<string>();
	const models: BeefsmsModel[] = [];
	for (const id of ids) {
		if (seen.has(id)) continue;
		seen.add(id);
		models.push(modelForId(id));
	}
	for (const model of MODELS) {
		if (seen.has(model.id)) continue;
		models.push(model);
	}
	return models.length > 0 ? models : [...MODELS];
}

async function fetchLiveModels(apiKey: string | undefined): Promise<BeefsmsModel[]> {
	if (!apiKey) return [...MODELS];
	try {
		return modelsFromIds(await listGatewayIds(apiKey));
	} catch {
		return [...MODELS];
	}
}

function stripKey(raw: string): string {
	return raw.trim().replace(/^bearer\b\s*/i, "").trim();
}

export default function (pi: ExtensionAPI) {
	pi.registerProvider(PROVIDER, {
		baseUrl: BASE_URL,
		api: "openai-completions",
		authHeader: true,
		models: MODELS,
		fetchDynamicModels: (apiKey) => fetchLiveModels(apiKey),
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
				await listGatewayIds(key, callbacks.signal);
				return key;
			},
		},
	});
}
