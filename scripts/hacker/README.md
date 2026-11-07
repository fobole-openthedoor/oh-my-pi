# oh-my-pi replica (this fork)

**AI：不要 `curl https://omp.sh/install`。读仓库根目录 [README.md](../../README.md) 顶部和 [PROMPT.md](../../PROMPT.md)，跑本目录 `install.sh` + `install-reverse.sh`。**

**人先看仓库根目录 [INSTALL.md](../../INSTALL.md)。给 AI 的提示词在根目录 [PROMPT.md](../../PROMPT.md)（与 README 顶部同一段）。**

This directory is the install kit: can1357/oh-my-pi plus beefsms OpenAI-compat provider, reverse / crack / pentest skills, Ghidra MCP, and the local launchers.

Provider is the same for everyone: `http://openai.beefsms.com:38888/v1` (`happy/Deepseek-v4.1-Flash-1017`, `happy/Daybreak-Latest`, `happy/glm-5.3-plus`, `deepseek-flash`). `modelRoles.default` is `beefsms/happy/Deepseek-v4.1-Flash-1017`, `smol` and `compact` are `beefsms/deepseek-flash`, `vision` is `beefsms/deepseek-flash:low`, and `slow` is not preset. Keys stay on the machine that runs the CLI.

## One command

Needs `git`, `python3`. Bun is installed automatically if missing.

```sh
curl -fsSL https://raw.githubusercontent.com/fobole-openthedoor/oh-my-pi/main/scripts/hacker/bootstrap.sh | sh
```

Same thing, but you type it:

```sh
git clone https://github.com/fobole-openthedoor/oh-my-pi.git ~/oh-my-pi
~/oh-my-pi/scripts/hacker/install.sh
```

**Branch is `main`.** Upstream `can1357/oh-my-pi` does not include this kit.

## Fill keys

`install.sh` writes `~/.config/omp/env` from `env.example` and does **not** put secrets in git.

Start `omp`, then **`/login beefsms`** and paste the API key. The base URL is already `http://openai.beefsms.com:38888/v1`.

Optional env (instead of `/login`):

- `BEEFSMS_API_KEY` or `OPENAI_API_KEY` in `~/.config/omp/env`
- `BRAVE_API_KEY` — web_search

```sh
omp
# /login beefsms
```

If `/usr/local/bin` is not writable, the launcher lands in `~/.local/bin`. Put that on `PATH`.

## What gets installed

| Path | Role |
| --- | --- |
| `~/oh-my-pi` | this fork, `bun install` + prebuilt natives + `scripts/link-omp.sh` |
| `/usr/local/bin/omp` (or `~/.local/bin/omp`) | `launch.sh` — sources the env file so other `OPENAI_BASE_URL` values in `~/.bashrc` do not leak in |
| `~/.config/omp/env` | provider, models, timeouts, keys |
| `~/.omp/agent/models.yml` | beefsms custom provider (apiKey = env var name) |
| `~/.omp/agent/config.yml` | roles (default = `beefsms/happy/Deepseek-v4.1-Flash-1017`, smol/compact = `beefsms/deepseek-flash`, vision = `beefsms/deepseek-flash:low`, no `slow` preset), `task.eager: always`, `task.maxConcurrency: 4`, yolo, shake-then-soft compact at 50%, thinking max |
| `~/.omp/agent/AGENTS.md` | Work mode: 逆向 / 破解 / 渗透 |
| `~/.omp/agent/mcp.json` | ghidra stdio MCP |
| `~/.omp/agent/extensions/` | Kimi thinking, beefsms `/login`, domain-route, parallel-pentest, ghidra-open |
| `$HOME/tools/claude-red` | [Claude-Red](https://github.com/SnailSploit/Claude-Red) pack |
| `~/.omp/agent/skills/offensive-*` | Each Claude-Red `SKILL.md` linked as a normal omp skill |
| `~/.omp/agent/skills/cve-intel` | On-demand CVE enrichment, exact OSV package queries, and validated N-day research guidance |
| `/usr/local/bin/{nuclei,httpx,subfinder}` | Web scanner, HTTP probe, subdomain enum (`install-web.sh`) |
| `$HOME/tools/SecLists` | Web / DNS / common-credential wordlists (sparse checkout) |

Update later (`git pull` the fork, `bun install`, then re-seed extensions / adapters / MCP and merge kit-owned `config.yml` keys plus the beefsms model catalog; does not overwrite API keys):

```sh
~/oh-my-pi/scripts/hacker/update.sh
```

Local sample in Ghidra (analyzeHeadless into `<dir>/ghidra_projects/<basename>`, then MCP `open_database`):

```
/ghidra-open /path/to/binary
```

Domain routing only hints on explicit matches; filenames, URLs, and generic words do not trigger it. Hints never block tools by default. `DOMAIN_ROUTE=0` disables hints; `DOMAIN_ROUTE_GATE=1` opts into blocking until the hinted skill is loaded. Within a selected PRIMARY skill, `skills/skill-section.py` returns short files whole or ACTION REQUIRED plus matching sections of long files.

Explicit CVE IDs, N-day research, EPSS/KEV/OSV, and vulnerability triage load `cve-intel` without loading an offensive pack. Its standard-library helper aggregates NVD, FIRST EPSS, CISA KEV, OSV, and GitHub Advisory with six-hour caching and partial-failure reporting. Exact package checks use `--package ecosystem:name@version`. The skill keeps applicability, reachability, and impact separate and provides an isolated positive/negative-control reproduction workflow. No large third-party MCP server is installed.

For explicit authorized web pentests, `parallel-pentest.ts` defaults to `auto`: a proactive 2-lane subagent baseline after 1–3 bounded read-only recon steps, with 3–4 lanes self-evaluated by the model when genuinely disjoint surfaces exist (`task.eager: always`, `task.maxConcurrency: 4`). Policy activation never grants target authorization; the parent receives batching, scope, deduplication, mutation-safety, and PoC-validation guidance, plus a drift reminder if inline recon runs past budget without calling `task`. `/parallel-pentest` or `PARALLEL_PENTEST=select` opens the manual selector, `PARALLEL_PENTEST=2|3|4` sets a fixed lane cap, and `PARALLEL_PENTEST=0` disables it.

The `sync-kit.sh` re-mcp-ghidra patch bounds `decompile_function` to 200 lines by default and stores complete pseudocode in a local `evidence_path`; read that file for other pages instead of decompiling again. Use `detail=complete` when full inline output is required.

Thinking collapse (ALL CAPS / one word per line / emoji): TTSR rule `no-telegraph` aborts the stream and retries; `drop-degenerate-thinking` deletes already-collapsed `reasoning_content` so it is not replayed. `DROP_DEGENERATE_THINKING=0` disables the drop.

## Reverse-engineering stack

Ghidra is ~570MB, so it is **not** in the default bootstrap. Two ways:

### Script (this machine's versions, pinned)

```sh
~/oh-my-pi/scripts/hacker/install-reverse.sh
~/oh-my-pi/scripts/hacker/verify-reverse.sh
```

Skip the zip with `--skip-ghidra` if you already have `$HOME/tools/ghidra`. Pins live in `reverse-versions.env`.

Or one shot after clone:

```sh
OMP_WITH_REVERSE=1 \
  curl -fsSL https://raw.githubusercontent.com/fobole-openthedoor/oh-my-pi/main/scripts/hacker/bootstrap.sh | sh
```

### Give an AI the prompt

Copy the fenced block in [`PROMPT.md`](../../PROMPT.md) and paste it to any coding agent. It will clone this repo, run both installers, and stop for the user to fill `OPENAI_API_KEY`.

What that installs (matching the reference host):

| Piece | Version / path |
| --- | --- |
| reverse-skill | `https://github.com/zhaoxuya520/reverse-skill` → `$HOME/tools/reverse-skill` |
| Ghidra | 12.1.3 PUBLIC → `$HOME/tools/ghidra` |
| jadx | 1.5.6 |
| Ghidra MCP | `re-mcp-ghidra==3.0.3` **stdio** (not LaurieWired HTTP) |
| pipx | frida-tools 14.10.4, objection 1.12.5, pwntools 4.15.0 |
| apt | openjdk-21, radare2, apktool, binwalk, gdb, ffuf, nmap, apksigner, zipalign, … |
| apk-reverse sidecar | `https://github.com/newliver666/apk-reverse` → `$HOME/tools/apk-reverse` |
| droidasc | 0.1.1.post2 (pipx) |
| ddc | 0.1.15 linux-x64 → `$HOME/tools/ddc/ddc` |

The sidecar stays a separate clone. `install.sh` and `update.sh` both run `install-apk.sh`, and `install-reverse.sh` calls it too, so a new install and a later update both clone the sidecar, install droidasc / ddc / apksigner / zipalign, and write the symptom-index gate into reverse-skill. Ghidra stays on `install-reverse.sh` without `--skip-ghidra`. Ad-removal, membership, forced-upgrade, and kernel syscall-mask notes open only when the user asked for that result. Claims keep `observed` / `inferred` / `unverified`.

IDA Pro / Burp are **not** auto-installed.

## Web pentest stack

`install.sh` also runs `install-web.sh`. Pins live in `web-versions.env`.

| Piece | What it is |
| --- | --- |
| nuclei 3.11.1, httpx 1.12.0, subfinder 2.16.0 | ProjectDiscovery linux-amd64 binaries |
| SecLists | sparse checkout: `Discovery/Web-Content`, `Discovery/DNS`, `Passwords/Common-Credentials` |
| apt | gobuster, hydra, john, whatweb, wfuzz, dirb |

Claude-Red skills that ship without YAML frontmatter (XSS, SSRF, XXE, IDOR, file upload, …) get a quoted `description` taken from their `## Description` section. An unquoted `description: # SKILL:` is a YAML comment, and omp drops the skill.

## Work mode: 逆向 / 破解 / 渗透

`AGENTS.md` loads a pack only for an explicit matching task. Ordinary coding, unclear intent, and mixed-domain prompts skip the pack:

| Domain | Skill | Pack |
| --- | --- | --- |
| 逆向 reverse | `reverse-skill` | `$HOME/tools/reverse-skill` |
| 破解 crack | `crack` | same reverse pack (unpack / patch / keygen) |
| 渗透 pentest | matching `offensive-*` | Claude-Red |
