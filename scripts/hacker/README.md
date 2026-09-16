# oh-my-pi replica (this fork)

**AI：不要 `curl https://omp.sh/install`。读仓库根目录 [README.md](../../README.md) 顶部和 [PROMPT.md](../../PROMPT.md)，跑本目录 `install.sh` + `install-reverse.sh`。**

**人先看仓库根目录 [INSTALL.md](../../INSTALL.md)。给 AI 的提示词在根目录 [PROMPT.md](../../PROMPT.md)（与 README 顶部同一段）。**

This directory is the install kit: can1357/oh-my-pi plus beefsms OpenAI-compat provider, reverse / crack / pentest skills, Ghidra MCP, and the local launchers.

Provider is the same for everyone: `http://openai.beefsms.com:38888/v1` (`happy/kimi-k3`, `happy/glm-5.3`, `happy/glm-5.3-plus`, `happy/qwen-3.8-fast`, `deepseek-flash`). `modelRoles.default` is `beefsms/happy/glm-5.3-plus`, `smol` and `compact` are `beefsms/deepseek-flash`, `vision` is `beefsms/deepseek-flash:low`, and `slow` is not preset. Keys stay on the machine that runs the CLI.

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
| `~/.omp/agent/config.yml` | roles (default = `beefsms/happy/glm-5.3-plus`, smol/compact = `beefsms/deepseek-flash`, vision = `beefsms/deepseek-flash:low`, no `slow` preset), yolo, shake-only auto-compact, thinking max |
| `~/.omp/agent/AGENTS.md` | Work mode: 逆向 / 破解 / 渗透 |
| `~/.omp/agent/mcp.json` | ghidra stdio MCP |
| `~/.omp/agent/extensions/` | GLM auto-continue, Kimi thinking, beefsms `/login`, domain-route, ghidra-open |
| `$HOME/tools/claude-red` | [Claude-Red](https://github.com/SnailSploit/Claude-Red) pack |
| `~/.omp/agent/skills/offensive-*` | Each Claude-Red `SKILL.md` linked as a normal omp skill |

Update later (`git pull` the fork, `bun install`, then re-seed extensions / adapters / MCP and merge kit-owned `config.yml` keys plus beefsms `compactionModel`; does not overwrite API keys):

```sh
~/oh-my-pi/scripts/hacker/update.sh
```

Local sample in Ghidra (analyzeHeadless into `<dir>/ghidra_projects/<basename>`, then MCP `open_database`):

```
/ghidra-open /path/to/binary
```

Domain routing is an extension: it injects `read skill://…` and blocks bash/write/edit until that skill is loaded. `DOMAIN_ROUTE=0` disables; `DOMAIN_ROUTE_GATE=0` injects only.

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
| apt | openjdk-21, radare2, apktool, binwalk, gdb, ffuf, nmap, … |

IDA Pro / Burp are **not** auto-installed.

## Work mode: 逆向 / 破解 / 渗透

`AGENTS.md` triages every task into one domain, then the matching skill is read:

| Domain | Skill | Pack |
| --- | --- | --- |
| 逆向 reverse | `reverse-skill` | `$HOME/tools/reverse-skill` |
| 破解 crack | `crack` | same reverse pack (unpack / patch / keygen) |
| 渗透 pentest | matching `offensive-*` | Claude-Red |

Do not mix packs on the first turn.
