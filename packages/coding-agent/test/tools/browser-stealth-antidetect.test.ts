import { afterAll, beforeAll, describe, expect, it } from "bun:test";
import * as fs from "node:fs/promises";
import * as os from "node:os";
import * as path from "node:path";

import { Settings } from "@oh-my-pi/pi-coding-agent/config/settings";
import { disposeAllVmContexts } from "@oh-my-pi/pi-coding-agent/eval/js/context-manager";
import { createBrowserPrelude } from "@oh-my-pi/pi-coding-agent/tools/browser";
import { releaseAllTabs } from "@oh-my-pi/pi-coding-agent/tools/browser/tab-supervisor";
import type { ToolSession } from "@oh-my-pi/pi-coding-agent/tools/index";
import { UTILITY_WORLD_NAME } from "puppeteer-core/lib/puppeteer/common/util.js";
import { chromiumAvailable } from "./chromium-probe";

const CHROMIUM_AVAILABLE = await chromiumAvailable();
const root = await fs.mkdtemp(path.join(os.tmpdir(), "omp-browser-antidetect-"));
const session: ToolSession = {
	cwd: root,
	hasUI: false,
	getSessionFile: () => null,
	getSessionSpawns: () => "*",
	settings: Settings.isolated({
		"browser.enabled": true,
		"browser.headless": true,
		"browser.cmux": false,
		"browser.tern": false,
		"tools.maxTimeout": 0,
	}),
};
const prelude = createBrowserPrelude(session);
const context = { session, toolCallId: "browser-stealth-antidetect-test" };

interface CaptureEntry {
	seq: number;
	type: string;
	level: string;
	text: string;
	location?: string;
	args?: unknown[];
}

interface CaptureResult {
	entries: CaptureEntry[];
	nextSeq: number;
	dropped: number;
}

async function invoke(parameters: unknown) {
	return await prelude.invoke(parameters, context);
}

function valueFrom<T>(result: { details?: unknown }): T {
	const details = result.details;
	if (!details || typeof details !== "object" || !("value" in details)) {
		return undefined as T;
	}
	return details.value as T;
}

async function call<T = unknown>(method: string, args: unknown[] = []): Promise<T> {
	const result = await invoke({ action: "call", name: "antidetect", chain: [{ method, args }] });
	return valueFrom<T>(result);
}

let server: Bun.Server<undefined> | undefined;
let baseUrl = "";

beforeAll(async () => {
	if (!CHROMIUM_AVAILABLE) return;
	server = Bun.serve({
		port: 0,
		hostname: "127.0.0.1",
		fetch(req) {
			const url = new URL(req.url);
			if (url.pathname === "/traps") {
				return new Response(
					`<!doctype html><html><head><meta charset="utf-8"><script>
window.__trapReport = (() => {
	let prepareStackTraceCalls = 0;
	let customErrorStackGetterCalls = 0;
	let tableRowGetterCalls = 0;
	let objectPropertyGetterCalls = 0;

	const prevPrepare = Error.prepareStackTrace;
	Error.prepareStackTrace = (err, stack) => {
		prepareStackTraceCalls++;
		return "prepared-stack";
	};
	try {
		const e1 = new Error("prepare-probe");
		console.debug(e1);
	} finally {
		Error.prepareStackTrace = prevPrepare;
	}

	const e2 = new Error("getter-probe");
	Object.defineProperty(e2, "stack", {
		configurable: true,
		get() {
			customErrorStackGetterCalls++;
			return "custom-stack";
		},
	});
	console.debug(e2);
	console.log(e2);

	const tableRow = {};
	Object.defineProperty(tableRow, "secret", {
		enumerable: true,
		configurable: true,
		get() {
			tableRowGetterCalls++;
			return "trap";
		},
	});
	console.table([tableRow]);

	const payload = { safe: "ok" };
	Object.defineProperty(payload, "trap", {
		enumerable: true,
		configurable: true,
		get() {
			objectPropertyGetterCalls++;
			return "boom";
		},
	});
	console.info("trap-check", payload);

	let preloadLeakInThrow = false;
	try {
		null.f();
	} catch (err) {
		const stack = String(err && err.stack || "");
		if (stack.includes("puppeteer") || stack.includes("UtilityWorld")) {
			preloadLeakInThrow = true;
		}
	}

	return {
		prepareStackTraceCalls,
		customErrorStackGetterCalls,
		tableRowGetterCalls,
		objectPropertyGetterCalls,
		preloadLeakInThrow,
	};
})();
</script></head><body><h1>antidetect</h1></body></html>`,
					{ headers: { "content-type": "text/html; charset=utf-8" } },
				);
			}
			return new Response("<!doctype html><title>alt</title><body>ok</body>", {
				headers: { "content-type": "text/html; charset=utf-8" },
			});
		},
	});
	baseUrl = `http://127.0.0.1:${server.port}`;
});

afterAll(async () => {
	server?.stop(true);
	await releaseAllTabs({ kill: true });
	await disposeAllVmContexts();
	await fs.rm(root, { recursive: true, force: true });
});

describe("Puppeteer isolated utility world naming", () => {
	it("strips the __puppeteer_utility_world__ marker from the utility world name", () => {
		expect(UTILITY_WORLD_NAME).not.toContain("puppeteer");
		expect(UTILITY_WORLD_NAME).toBe("UtilityWorld");
	});
});

describe.skipIf(!CHROMIUM_AVAILABLE)("headless anti-detection contracts", () => {
	it("captures console logs without triggering CDP Runtime.enable or object/Error getter traps", async () => {
		await invoke({ action: "open", name: "antidetect", url: `${baseUrl}/traps` });

		const report = await call<{
			prepareStackTraceCalls: number;
			customErrorStackGetterCalls: number;
			tableRowGetterCalls: number;
			objectPropertyGetterCalls: number;
			preloadLeakInThrow: boolean;
		}>("evaluate", ["window.__trapReport"]);

		expect(report).toEqual({
			prepareStackTraceCalls: 0,
			customErrorStackGetterCalls: 0,
			tableRowGetterCalls: 0,
			objectPropertyGetterCalls: 0,
			preloadLeakInThrow: false,
		});

		const captured = await call<CaptureResult>("console");
		const trapInfo = captured.entries.find(entry => entry.text.includes("trap-check"));
		expect(trapInfo).toBeDefined();
		expect(trapInfo?.args).toEqual(["trap-check", { safe: "ok" }]);
	});

	it("leaves zero __omp or __puppeteer globals or symbols in the main world when observers and guards are active", async () => {
		await call("vitals");
		await invoke({
			action: "run",
			name: "antidetect",
			code: `
				await tab.mouseMove(10, 10);
			`,
		});

		const surface = await call<{
			ompGlobals: string[];
			puppeteerGlobals: string[];
			leakedSymbols: string[];
			webdriver: unknown;
		}>("evaluate", [
			`(() => {
				const names = Object.getOwnPropertyNames(window);
				const symbols = Object.getOwnPropertySymbols(window).map(sym => String(sym));
				return {
					ompGlobals: names.filter(k => k.includes("__omp") || k.startsWith("cdc_")),
					puppeteerGlobals: names.filter(k => k.toLowerCase().includes("puppeteer")),
					leakedSymbols: symbols.filter(s => s.includes("omp.") || s.toLowerCase().includes("puppeteer")),
					webdriver: navigator.webdriver,
				};
			})()`,
		]);

		expect(surface).toEqual({
			ompGlobals: [],
			puppeteerGlobals: [],
			leakedSymbols: [],
			webdriver: false,
		});
	});

	it("keeps User-Agent, navigator.platform, and UA-CH high-entropy hints coherent across navigations", async () => {
		await call("goto", [`${baseUrl}/other`]);

		const uaProfile = await call<{
			userAgent: string;
			platform: string;
			uaDataPlatform: string | null;
			uaDataMobile: boolean | null;
			platformVersion: string | null;
			fullVersionList: Array<{ brand: string; version: string }>;
		}>("evaluate", [
			`(async () => {
				const uaData = navigator.userAgentData;
				const highEntropy = uaData
					? await uaData.getHighEntropyValues(["platform", "platformVersion", "fullVersionList"])
					: null;
				return {
					userAgent: navigator.userAgent,
					platform: navigator.platform,
					uaDataPlatform: highEntropy ? highEntropy.platform : null,
					uaDataMobile: uaData ? uaData.mobile : null,
					platformVersion: highEntropy ? highEntropy.platformVersion : null,
					fullVersionList: highEntropy && Array.isArray(highEntropy.fullVersionList) ? highEntropy.fullVersionList : [],
				};
			})()`,
		]);

		expect(uaProfile.userAgent).not.toContain("HeadlessChrome");
		expect(uaProfile.uaDataMobile).toBe(false);
		expect(uaProfile.fullVersionList.some(b => b.brand.includes("Headless"))).toBe(false);
		if (uaProfile.platformVersion !== null) {
			expect(uaProfile.platformVersion).toMatch(/^\d+\.\d+\.\d+$/);
		}

		if (uaProfile.userAgent.includes("Linux")) {
			expect(uaProfile.platform.startsWith("Linux")).toBe(true);
			expect(uaProfile.uaDataPlatform).toBe("Linux");
		} else if (uaProfile.userAgent.includes("Macintosh")) {
			expect(uaProfile.platform).toBe("MacIntel");
			expect(uaProfile.uaDataPlatform).toBe("macOS");
		} else if (uaProfile.userAgent.includes("Windows")) {
			expect(uaProfile.platform).toBe("Win32");
			expect(uaProfile.uaDataPlatform).toBe("Windows");
		}
	});

	it("preserves native Function.prototype.toString, arity, and clean error stacks on patched built-ins", async () => {
		const inspection = await call<{
			fillTextLength: number;
			fillTextName: string;
			fillTextToString: string;
			toStringToString: string;
			stackAccessorPreserved: boolean;
			leakedFrames: Array<{ probe: string; stack: string; callSites: string[] }>;
		}>("evaluate", [
			`(() => {
				const probes = [
					["Function.toString", () => Function.prototype.toString.call(null)],
					["Object.getOwnPropertyDescriptor", () => Object.getOwnPropertyDescriptor(null, "x")],
					["Canvas2D.fillText", () => CanvasRenderingContext2D.prototype.fillText.call(null, "a", 0, 0)],
					["WebGL.getParameter", () => WebGLRenderingContext.prototype.getParameter.call(null, 0x1f00)],
					["HTMLMediaElement.canPlayType", () => HTMLMediaElement.prototype.canPlayType.call(null, "video/mp4")],
				];
				const leakedFrames = [];
				let stackAccessorPreserved = true;

				for (const [label, fn] of probes) {
					try {
						fn();
					} catch (err) {
						const desc = Object.getOwnPropertyDescriptor(err, "stack");
						if (!desc || typeof desc.get !== "function" || typeof desc.set !== "function") {
							stackAccessorPreserved = false;
						}
						let callSites = [];
						const prevPrepare = Error.prepareStackTrace;
						Error.prepareStackTrace = (_e, structured) => {
							callSites = structured.map(site => String(site.getFunctionName() || "") + "@" + String(site.getFileName() || ""));
							return prevPrepare ? prevPrepare(_e, structured) : structured.join("\\n");
						};
						let stack = "";
						try {
							stack = String(err.stack || "");
						} finally {
							Error.prepareStackTrace = prevPrepare;
						}
						const hasWrapperFrame =
							stack.includes("Object.apply") ||
							stack.includes("Proxy.") ||
							stack.includes("invokeWithCleanStack") ||
							stack.includes("constructWithCleanStack") ||
							stack.includes("__puppeteer_evaluation_script__") ||
							callSites.some(
								s =>
									s.includes("apply@") ||
									s.includes("invokeWithCleanStack") ||
									s.includes("__puppeteer_evaluation_script__"),
							);
						if (hasWrapperFrame) {
							leakedFrames.push({ probe: label, stack, callSites });
						}
					}
				}

				return {
					fillTextLength: CanvasRenderingContext2D.prototype.fillText.length,
					fillTextName: CanvasRenderingContext2D.prototype.fillText.name,
					fillTextToString: Function.prototype.toString.call(CanvasRenderingContext2D.prototype.fillText),
					toStringToString: Function.prototype.toString.call(Function.prototype.toString),
					stackAccessorPreserved,
					leakedFrames,
				};
			})()`,
		]);

		expect(inspection.fillTextLength).toBe(3);
		expect(inspection.fillTextName).toBe("fillText");
		expect(inspection.fillTextToString).toBe("function fillText() { [native code] }");
		expect(inspection.toStringToString).toBe("function toString() { [native code] }");
		expect(inspection.stackAccessorPreserved).toBe(true);
		expect(inspection.leakedFrames).toEqual([]);
	});
});
