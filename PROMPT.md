# 给别人的 AI：复刻这套 oh-my-pi + 逆向环境

把 **「从这里复制」到「复制结束」** 整段原样发给任意能跑终端的 AI（oh-my-pi / Claude Code / Codex / Cursor 都行）。人只需要事后在 `~/.config/omp/env` 里填自己的 beefsms key。

仓库：https://github.com/fobole-openthedoor/oh-my-pi
人看的安装说明：**[INSTALL.md](INSTALL.md)**（仓库根目录，打开就能看到）。

---

从这里复制

```text
你是安装机器人。在这台 Linux 机器上复刻一套 oh-my-pi（本 fork，beefsms 供应商）+ 逆向环境。不要问一堆确认，按清单执行；某步失败就修再继续。做完输出验收表。不要把任何 API key 写入 git、不要打印 key。

先读仓库根目录 INSTALL.md 和 scripts/hacker/README.md，优先跑现成脚本，不要自己发明安装路径。

## 目标终态

- CLI：本 fork 的 `omp`（can1357/oh-my-pi 的 fork），不是 `omp.sh/install` 上游二进制，也不是 `bun i -g @oh-my-pi/pi-coding-agent`。
- 分支必须是 `main`。上游 can1357/oh-my-pi 没有这套安装脚本。
- 供应商固定：`OPENAI_BASE_URL=http://openai.beefsms.com:38888/v1`，模型 `happy/kimi-k3` / `happy/glm-5.3` / `happy/qwen-3.8-fast`。写进 `~/.omp/agent/models.yml` 的 provider id 是 `beefsms`。
- Key 只存在 `~/.config/omp/env`，由用户自己填。仓库里只有占位符。`models.yml` 的 apiKey 字段必须是环境变量名 `OPENAI_API_KEY`，不能是真实 key。
- 逆向：`$HOME/tools/reverse-skill`、`$HOME/tools/ghidra`（12.1.3 PUBLIC）、jadx 1.5.6、`re-mcp-ghidra` stdio MCP。不要装 LaurieWired GhidraMCP，不要改用 HTTP :8765。
- 工作域三套：逆向 `reverse-skill`（`$HOME/tools/reverse-skill`）、破解 `crack`（同一套 reverse pack，脱壳/去校验/补丁）、渗透 Claude-Red `offensive-*`。`~/.omp/agent/AGENTS.md` 必须有 `Work mode: 逆向 / 破解 / 渗透`，任务一开始先分域再 `read skill://<name>`。
- 进攻技能包：`$HOME/tools/claude-red`（https://github.com/SnailSploit/Claude-Red）。每个 `Skills/*/*/SKILL.md` **symlink 进** `$HOME/.omp/agent/skills/`。分域脚本：`scripts/hacker/skills/domain-route.py`。
- Ghidra MCP 写进 `$HOME/.omp/agent/mcp.json`（stdio，`re-mcp-ghidra stdio`，env 里 GHIDRA_INSTALL_DIR / GHIDRA_HOME / JAVA_HOME）。
- GLM 自动续跑：`~/.omp/agent/extensions/glm-auto-continue.ts`。Kimi K3 thinking 改写：`~/.omp/agent/extensions/beefsms-kimi-thinking.ts`。

## 步骤

1. 确认 git / python3 / curl。没有 bun 就 `curl -fsSL https://bun.sh/install | bash`（需要 ≥ 1.3.14）。不要为了跑 omp 去装 Rust / Bazel；`install.sh` 会下载预编译 natives。
2. 若还没有 checkout：
   `git clone https://github.com/fobole-openthedoor/oh-my-pi.git $HOME/oh-my-pi`
3. 跑 `$HOME/oh-my-pi/scripts/hacker/install.sh`（里面会 clone Claude-Red 到 `$HOME/tools/claude-red`）。若跳过了，再跑 `install-claude-red.sh`。
4. 跑 `$HOME/oh-my-pi/scripts/hacker/install-reverse.sh`。
   Ghidra zip 约 570MB，sha256 必须是 `93a5d11a9ad510622acaaf908c556a7b9b764d338e78a7567f3689bf5081fd54`。磁盘不够或用户明确说跳过时才加 `--skip-ghidra`。
   版本钉死在 `scripts/hacker/reverse-versions.env`，不要自作主张升版本。
5. 若 `install-reverse.sh` 不存在（旧 checkout），按 `scripts/hacker/reverse-versions.env` 里的 URL 自己下 Ghidra / jadx，clone `https://github.com/zhaoxuya520/reverse-skill.git` 到 `$HOME/tools/reverse-skill`，然后：
   - `pipx install re-mcp-ghidra==3.0.3 frida-tools==14.10.4`
   - `pipx install objection==1.12.5 pwntools==4.15.0`
   - apt（能装就装）：`openjdk-21-jdk radare2 apktool binwalk gdb gdb-multiarch ffuf nmap sqlmap hashcat adb p7zip-full pipx`
   - `ln -sfn $HOME/tools/ghidra_12.1.3_PUBLIC $HOME/tools/ghidra`
   - `bash $HOME/tools/reverse-skill/skills/scripts/refresh-tool-index.sh`
   - 用 `scripts/hacker/wire-ghidra-mcp.py` 把 ghidra MCP 写进 `$HOME/.omp/agent/mcp.json`（stdio，`re-mcp-ghidra stdio`，env 里 GHIDRA_INSTALL_DIR / GHIDRA_HOME / JAVA_HOME）。没有这个 py 就手工 merge，不要把 API key 写进 mcp.json。
6. 编辑 `$HOME/.config/omp/env`：把 `OPENAI_API_KEY` 从 `PASTE_YOUR_BEEFSMS_KEY_HERE` 换成用户的 beefsms key。没有 key 就停在这一步并告诉用户去填，不要编造 key。可选 `BRAVE_API_KEY`。
7. 把 `$HOME/.local/bin`、`$HOME/tools/jadx/bin`、`$HOME/tools/ghidra/support`、`$HOME/.bun/bin` 放进 PATH（launch.sh 会 source env）。
8. 跑 `$HOME/oh-my-pi/scripts/hacker/verify-reverse.sh` 和 `verify-claude-red.sh`。失败就修，再跑直到通过或只剩「用户还没填 key」。
9. 不要安装 IDA Pro / Burp 正版替代品。不要提交 `~/.config/omp/env` 或把真实 key 写进 `models.yml`。不要配置 Forgejo。不要把 OpenClaude 的 `~/.audncode-platform` 路径当 omp 配置用。

## 验收表（按这个格式汇报）

- omp 启动器路径 / git commit / 分支
- OPENAI_BASE_URL（应是 beefsms）
- OPENAI_API_KEY 是否已填（只回答 是/否）
- java 版本、Ghidra analyzeHeadless、jadx、r2、re-mcp-ghidra
- reverse-skill 路径、tool-index.md 是否生成
- AGENTS.md 是否有 Work mode 三域；`/skill:crack` adapter；`domain-route.py --hint 脱壳` → crack；offensive-sqli 是否 symlink
- mcp.json 里 ghidra 是否 stdio
- glm-auto-continue.ts / beefsms-kimi-thinking.ts 是否在 ~/.omp/agent/extensions/
- verify-reverse.sh / verify-claude-red.sh 退出码
```

复制结束
