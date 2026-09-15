import { spawnSync } from "node:child_process";
import { homedir } from "node:os";
import { join } from "node:path";
import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";

type BranchEntry = {
	type?: string;
	message?: {
		role?: string;
		content?: unknown;
	};
};

function lastAssistantText(ctx: { sessionManager: { getBranch(): unknown } }): string {
	let text = "";
	const branch = ctx.sessionManager.getBranch() as BranchEntry[];
	for (const entry of branch) {
		if (entry?.type !== "message") continue;
		const msg = entry.message;
		if (msg?.role !== "assistant") continue;
		const parts: string[] = [];
		const content = msg.content;
		if (typeof content === "string") {
			parts.push(content);
		} else if (Array.isArray(content)) {
			for (const block of content) {
				if (
					block &&
					typeof block === "object" &&
					"type" in block &&
					(block as { type?: string }).type === "text" &&
					typeof (block as { text?: unknown }).text === "string"
				) {
					parts.push((block as { text: string }).text);
				}
			}
		}
		text = parts.join("\n");
	}
	return text.trim();
}

function classify(script: string, lastText: string): { kind: string; reason: string | null } {
	const result = spawnSync("python3", [script, "--classify"], {
		input: JSON.stringify({ last_assistant_message: lastText }),
		encoding: "utf8",
		timeout: 5000,
	});
	if (result.status !== 0) {
		return { kind: "allow", reason: null };
	}
	try {
		const parsed = JSON.parse(result.stdout || "{}") as {
			kind?: string;
			reason?: string | null;
		};
		return { kind: parsed.kind || "allow", reason: parsed.reason ?? null };
	} catch {
		return { kind: "allow", reason: null };
	}
}

export default function (pi: ExtensionAPI) {
	const fork = process.env.OMP_FORK_ROOT || join(homedir(), "oh-my-pi");
	const script = join(fork, "scripts/hacker/hooks/glm-auto-continue.py");

	pi.on("session_stop", async (event, ctx) => {
		if (event.stop_hook_active) return;
		if (process.env.GLM_AUTO_CONTINUE === "0") return;
		const last = lastAssistantText(ctx);
		const { kind, reason } = classify(script, last);
		if (kind === "allow" || !reason) return;
		return { continue: true, additionalContext: reason };
	});
}
