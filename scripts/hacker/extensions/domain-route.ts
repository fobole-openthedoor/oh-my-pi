import { spawnSync } from "node:child_process";
import { homedir } from "node:os";
import { join } from "node:path";
import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";

type Route = {
	domain: string;
	next: string;
	skip: boolean;
};

type Gate = {
	skill: string;
	domain: string;
};

type BranchEntry = {
	type?: string;
	customType?: string;
	content?: unknown;
	details?: { name?: string };
	message?: {
		role?: string;
		toolName?: string;
		content?: unknown;
	};
};

const ALLOWED_TOOLS = new Set([
	"read",
	"grep",
	"glob",
	"todo",
	"ask",
	"web_search",
	"ghidra_open",
]);

const BASH_ALLOW = [
	"domain-route.py",
	"master-route.sh",
	"case-init.sh",
	"ghidra-open.sh",
	"refresh-tool-index.sh",
	"analyzeHeadless",
];

function envOn(name: string): boolean {
	const value = process.env[name];
	return value !== "0" && value !== "false";
}

function forkRoot(): string {
	return process.env.OMP_FORK_ROOT || join(homedir(), "oh-my-pi");
}

function routeScript(): string {
	return join(forkRoot(), "scripts/hacker/skills/domain-route.py");
}

function classify(hint: string): Route | null {
	const result = spawnSync("python3", [routeScript(), "--json", "--hint", hint], {
		encoding: "utf8",
		timeout: 8000,
		env: process.env,
	});
	if (result.status !== 0) return null;
	try {
		const parsed = JSON.parse(result.stdout || "{}") as Partial<Route>;
		if (typeof parsed.domain !== "string") return null;
		return {
			domain: parsed.domain,
			next: typeof parsed.next === "string" ? parsed.next : "",
			skip: parsed.skip === true || parsed.domain === "skip",
		};
	} catch {
		return null;
	}
}

function stringFrom(value: unknown): string {
	if (typeof value === "string") return value;
	if (Array.isArray(value)) {
		return value
			.map((block) => {
				if (typeof block === "string") return block;
				if (block && typeof block === "object" && "text" in block) {
					return String((block as { text?: unknown }).text ?? "");
				}
				return "";
			})
			.join("\n");
	}
	return "";
}

function pathOf(input: unknown): string {
	if (!input || typeof input !== "object") return "";
	const rec = input as Record<string, unknown>;
	return String(rec.path ?? rec.file_path ?? rec.target ?? "");
}

function commandOf(input: unknown): string {
	if (!input || typeof input !== "object") return "";
	return String((input as { command?: unknown }).command ?? "");
}

function matchesSkill(value: string, skill: string): boolean {
	if (!skill || !value) return false;
	const lower = value.toLowerCase();
	const name = skill.toLowerCase();
	if (lower.includes(`skill://${name}`)) return true;
	if (lower.includes(`/skill:${name}`)) return true;
	if (lower.includes(`/skills/${name}/`) || lower.endsWith(`/skills/${name}`)) return true;
	if (lower.includes(`/.omp/agent/skills/${name}`)) return true;
	return false;
}

function isSubagent(ctx: { sessionManager: { getHeader?: () => { parentSession?: string } | null } }): boolean {
	const header = ctx.sessionManager.getHeader?.() ?? null;
	return Boolean(header?.parentSession);
}

function skillLoaded(branch: unknown, skill: string): boolean {
	if (!skill) return false;
	const entries = Array.isArray(branch) ? (branch as BranchEntry[]) : [];
	for (const entry of entries) {
		if (entry?.type === "custom_message" || entry?.customType === "skill-prompt") {
			const name = entry.details?.name;
			if (typeof name === "string" && name === skill) return true;
			if (matchesSkill(stringFrom(entry.content), skill)) return true;
		}
		const msg = entry?.message;
		if (!msg) continue;
		if (msg.role === "toolResult" && matchesSkill(stringFrom(msg.content), skill)) return true;
		const content = msg.content;
		if (!Array.isArray(content)) continue;
		for (const block of content) {
			if (!block || typeof block !== "object") continue;
			const rec = block as Record<string, unknown>;
			const type = String(rec.type ?? "");
			const name = String(rec.name ?? rec.toolName ?? "");
			if (type !== "toolCall" && type !== "toolUse" && name !== "read") continue;
			const args = rec.arguments ?? rec.input ?? rec.params;
			if (matchesSkill(pathOf(args), skill) || matchesSkill(stringFrom(args), skill)) return true;
		}
	}
	return false;
}

function mcpOpenDatabase(toolName: string): boolean {
	return /ghidra/i.test(toolName) && /open_database/i.test(toolName);
}

function bashAllowed(command: string): boolean {
	return BASH_ALLOW.some((token) => command.includes(token));
}

function toolAllowed(toolName: string, input: unknown): boolean {
	if (ALLOWED_TOOLS.has(toolName)) return true;
	if (mcpOpenDatabase(toolName)) return true;
	if (toolName === "bash" && bashAllowed(commandOf(input))) return true;
	return false;
}

function reminder(route: Route): string {
	const parts = [
		`Work mode: ${route.domain}.`,
		`NOW: read skill://${route.next} before any other tool.`,
		"Do not bash, write, edit, or scan until that skill is loaded.",
	];
	if (route.domain === "reverse" || route.domain === "crack") {
		parts.push(
			"Local sample: `/ghidra-open <binary>` (or tool ghidra_open), then MCP `open_database` with that file_path.",
		);
	}
	return parts.join(" ");
}

export default function (pi: ExtensionAPI) {
	let gate: Gate | null = null;

	const refreshLoaded = (ctx: { sessionManager: { getBranch(): unknown } }, skill: string): boolean => {
		return skillLoaded(ctx.sessionManager.getBranch(), skill);
	};

	pi.on("session_start", async () => {
		gate = null;
	});

	pi.on("session_switch", async () => {
		gate = null;
	});

	pi.on("before_agent_start", async (event, ctx) => {
		if (!envOn("DOMAIN_ROUTE")) return;
		if (isSubagent(ctx)) return;
		const route = classify(event.prompt || "");
		if (!route || route.skip || !route.next) {
			gate = null;
			return;
		}
		gate = { skill: route.next, domain: route.domain };
		if (refreshLoaded(ctx, route.next)) return;
		return {
			message: {
				customType: "domain-route",
				content: reminder(route),
				display: true,
			},
		};
	});

	pi.on("tool_call", async (event, ctx) => {
		try {
			if (!envOn("DOMAIN_ROUTE") || !envOn("DOMAIN_ROUTE_GATE")) return;
			if (!gate?.skill) return;
			if (isSubagent(ctx)) return;
			if (refreshLoaded(ctx, gate.skill)) return;
			if (toolAllowed(event.toolName, event.input)) return;
			return {
				block: true,
				reason:
					`domain-route: load skill://${gate.skill} first ` +
					`(domain ${gate.domain}). Allowed until then: read/grep/glob that skill, ` +
					`ghidra_open / MCP open_database, and routing scripts. ` +
					`Set DOMAIN_ROUTE_GATE=0 to inject-only, DOMAIN_ROUTE=0 to disable.`,
			};
		} catch {
			return;
		}
	});
}
