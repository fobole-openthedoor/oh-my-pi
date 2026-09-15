import { spawn } from "node:child_process";
import { homedir } from "node:os";
import { join } from "node:path";
import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";

function forkRoot(): string {
	return process.env.OMP_FORK_ROOT || join(homedir(), "oh-my-pi");
}

function scriptPath(): string {
	return join(forkRoot(), "scripts/hacker/ghidra-open.sh");
}

function runOpen(
	args: string[],
	signal: AbortSignal | undefined,
	onChunk?: (text: string) => void,
): Promise<{ code: number; stdout: string }> {
	return new Promise((resolve, reject) => {
		const child = spawn("sh", [scriptPath(), ...args], {
			env: process.env,
		});
		let stdout = "";
		const onAbort = () => {
			child.kill("SIGTERM");
		};
		signal?.addEventListener("abort", onAbort, { once: true });
		child.stdout?.on("data", (buf: Buffer) => {
			const text = buf.toString("utf8");
			stdout += text;
			onChunk?.(text);
		});
		child.stderr?.on("data", (buf: Buffer) => {
			const text = buf.toString("utf8");
			stdout += text;
			onChunk?.(text);
		});
		child.on("error", (err) => {
			signal?.removeEventListener("abort", onAbort);
			reject(err);
		});
		child.on("close", (code) => {
			signal?.removeEventListener("abort", onAbort);
			resolve({ code: code ?? 1, stdout });
		});
	});
}

function lastJson(blob: string): string {
	const start = blob.lastIndexOf("{");
	if (start < 0) return blob.trim();
	return blob.slice(start).trim();
}

export default function (pi: ExtensionAPI) {
	const z = pi.zod;

	pi.registerCommand("ghidra-open", {
		description: "Import a binary into Ghidra for MCP open_database",
		handler: async (args, ctx) => {
			const path = args.trim().split(/\s+/)[0] || "";
			if (!path) {
				ctx.ui.notify("usage: /ghidra-open <binary>", "error");
				return;
			}
			ctx.ui.notify(`ghidra-open ${path}`, "info");
			try {
				const { code, stdout } = await runOpen([path]);
				const summary = lastJson(stdout);
				pi.sendMessage(
					{
						customType: "ghidra-open",
						content: summary,
						display: true,
					},
					{ triggerTurn: false },
				);
				ctx.ui.notify(code === 0 ? "ghidra-open done" : "ghidra-open failed", code === 0 ? "info" : "error");
			} catch (err) {
				ctx.ui.notify(err instanceof Error ? err.message : String(err), "error");
			}
		},
	});

	pi.registerTool({
		name: "ghidra_open",
		label: "Ghidra Open",
		description:
			"Import a local binary with analyzeHeadless into <dir>/ghidra_projects/<basename>, matching re-mcp-ghidra. After success, call MCP open_database with the same file_path (run_auto_analysis false unless no_analyze). Use before decompiling ELF/PE/APK/SO.",
		loadMode: "essential",
		approval: "write",
		parameters: z.object({
			path: z.string().describe("Absolute or home-relative path to the binary"),
			force: z.boolean().optional().describe("Rebuild the Ghidra project if it already exists"),
			no_analyze: z.boolean().optional().describe("Import only; MCP open_database should then run auto analysis"),
		}),
		async execute(_id, params, signal, onUpdate) {
			const args = [params.path];
			if (params.force) args.unshift("--force");
			if (params.no_analyze) args.unshift("--no-analyze");
			onUpdate?.({ content: [{ type: "text", text: `ghidra-open ${params.path}` }] });
			const { code, stdout } = await runOpen(args, signal, (chunk) => {
				onUpdate?.({ content: [{ type: "text", text: chunk.slice(-2000) }] });
			});
			const summary = lastJson(stdout);
			return {
				content: [{ type: "text", text: summary }],
				details: { exitCode: code, path: params.path },
				isError: code !== 0,
			};
		},
	});
}
