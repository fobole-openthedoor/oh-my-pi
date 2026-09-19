// avs-tools: native omp tools wrapping the `avs` Android screen CLI.
//
// Registers avs_devices / avs_snapshot / avs_tap / avs_key so the agent calls
// real tools instead of hand-assembling `adb`/`avs` bash. Each tool shells to
// the `avs` binary (argv array, never a host shell) and returns its plain-text
// output, which is already written for a coding agent. The vision model avs
// uses is configured out-of-band in ~/.config/avs/config.yaml (point it at
// beefsms/qwen3-vl-8b-instruct).
//
// Requires the `avs` binary on PATH (or $AVS_BIN). Built from the avs repo.
import { spawnSync } from "node:child_process";
import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";

type Result = { content: { type: "text"; text: string }[]; isError?: boolean };

function avsBin(): string {
	return process.env.AVS_BIN && process.env.AVS_BIN.trim() ? process.env.AVS_BIN.trim() : "avs";
}

function run(args: string[], serial?: string): Result {
	const argv = serial && serial.trim() ? [...args, "--serial", serial.trim()] : args;
	let out;
	try {
		out = spawnSync(avsBin(), argv, { encoding: "utf8", timeout: 90_000, maxBuffer: 8 << 20 });
	} catch (e) {
		return { content: [{ type: "text", text: `avs failed to spawn: ${String(e)}` }], isError: true };
	}
	if (out.error) {
		const err = out.error as NodeJS.ErrnoException;
		const hint =
			err.code === "ENOENT"
				? `avs binary not found (looked for "${avsBin()}"). Build it from the avs repo and put it on PATH, or set AVS_BIN.`
				: `avs failed: ${err.message}`;
		return { content: [{ type: "text", text: hint }], isError: true };
	}
	const text = [out.stdout, out.stderr].map(s => (s || "").trimEnd()).filter(Boolean).join("\n");
	// avs exits non-zero on every error (secure_or_black=3, others=1); surface
	// it as a tool error so the model notices and reads the error= code.
	return { content: [{ type: "text", text: text || "(no output)" }], isError: out.status !== 0 };
}

export default function avsTools(pi: ExtensionAPI) {
	const z = pi.zod;
	const serial = z.string().describe("Device serial (required when several devices are attached; see avs_devices)").optional();

	pi.registerTool({
		name: "avs_devices",
		label: "avs devices",
		description: "List attached Android devices (serial, state, model) via ADB. Run this first when unsure which device or when several are connected.",
		parameters: z.object({}),
		approval: "read",
		async execute() {
			return run(["devices"]);
		},
	});

	pi.registerTool({
		name: "avs_snapshot",
		label: "avs snapshot",
		description:
			"Read the current Android screen: prints numbered, tappable elements with device-pixel coordinates plus visible text. Always call this before avs_tap by id/text. On error=secure_or_black the screen is protected or locked — stop and tell the user, do not invent buttons. Uses the UI tree first and a vision model when the tree is blocked or a permission/install dialog is up.",
		parameters: z.object({
			serial,
			force_vision: z.boolean().describe("Skip the UI tree and use the vision model only (rarely needed)").optional(),
		}),
		approval: "read",
		async execute(_id, params) {
			const args = ["snapshot"];
			if (params.force_vision) args.push("--force-vision");
			return run(args, params.serial);
		},
	});

	pi.registerTool({
		name: "avs_tap",
		label: "avs tap",
		description:
			"Tap a control from the most recent avs_snapshot. Give exactly one of: id (preferred), text (the label to match), or xy ('X,Y' device pixels, only when snapshot gave coordinates but no usable id/text). Ids expire after any tap/key, app change, or 10 minutes — snapshot again first. Never guess coordinates.",
		parameters: z
			.object({
				id: z.number().int().positive().describe("Element id from the last snapshot").optional(),
				text: z.string().describe("Label to tap, e.g. 允许 / CONTINUE").optional(),
				xy: z.string().describe("Device pixels 'X,Y', e.g. 720,1620").optional(),
				serial,
			})
			.describe("Exactly one of id / text / xy"),
		approval: "write",
		async execute(_id, params) {
			const chosen = ["id", "text", "xy"].filter(k => (params as Record<string, unknown>)[k] !== undefined);
			if (chosen.length !== 1) {
				return {
					content: [{ type: "text", text: `avs_tap needs exactly one of id / text / xy (got ${chosen.length}).` }],
					isError: true,
				};
			}
			const args = ["tap"];
			if (params.id !== undefined) args.push(String(params.id));
			else if (params.text !== undefined) args.push("--text", params.text);
			else if (params.xy !== undefined) args.push("--xy", params.xy);
			return run(args, params.serial);
		},
	});

	pi.registerTool({
		name: "avs_key",
		label: "avs key",
		description: "Press a hardware/navigation key: BACK, HOME, or ENTER.",
		parameters: z.object({
			key: z.enum(["BACK", "HOME", "ENTER"]).describe("Key to press"),
			serial,
		}),
		approval: "write",
		async execute(_id, params) {
			return run(["key", params.key], params.serial);
		},
	});
}
