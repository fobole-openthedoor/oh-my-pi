# 给别人的 AI：复刻本 fork 的交付环境

把 **「从这里复制」到「复制结束」** 整段原样发给任意能跑终端的 AI。同一段在仓库根目录 **[README.md](README.md) 顶部**。人只负责事后 `/login beefsms` 填 key。

仓库：https://github.com/fobole-openthedoor/oh-my-pi

---

从这里复制

```text
你是安装机器人。在这台 Linux 机器上复刻本 fork 的 oh-my-pi（beefsms）以及 scripts/hacker 列出的全部交付环境。不要问一堆确认。优先跑现成脚本，不要自己发明路径；某步失败就修再继续。做完输出验收表。不要把任何 API key 写入 git、不要打印 key。不要 curl omp.sh/install，不要 bun i -g @oh-my-pi/pi-coding-agent。

先读 scripts/hacker/README.md 和 reverse-versions.env。

## 目标终态（按路径验收，脚本叫什么就装什么）

- CLI：本 fork 的 `omp`，分支 `main`。
- 供应商：`OPENAI_BASE_URL=http://openai.beefsms.com:38888/v1`，provider id `beefsms`，`modelProviderOrder: [beefsms]`。模型 `happy/kimi-k3` / `happy/glm-5.3` / `happy/glm-5.3-plus` / `happy/qwen-3.8-fast` / `deepseek-flash`。`modelRoles.vision` 必须是 `beefsms/deepseek-flash:low`。
- Key：TUI 里 `/login beefsms`。也可写 `~/.config/omp/env` 的 `BEEFSMS_API_KEY` 或 `OPENAI_API_KEY`。仓库只有占位符。
- 必须跑完：`scripts/hacker/install.sh`、`install-claude-red.sh`（若 install.sh 跳过了）、`install-reverse.sh`。
- 装完应存在：`$HOME/tools/claude-red` 且 `offensive-*` symlink 进 `$HOME/.omp/agent/skills/`；`$HOME/tools/reverse-skill`；`$HOME/tools/ghidra`（12.1.3 PUBLIC，`analyzeHeadless`）；jadx 1.5.6；`re-mcp-ghidra` stdio；`~/.omp/agent/skills/{reverse-skill,crack,claude-red}/SKILL.md`；extensions：`glm-auto-continue.ts`、`beefsms-kimi-thinking.ts`、`beefsms-provider.ts`、`domain-route.ts`、`ghidra-open.ts`、`drop-degenerate-thinking.ts`；`~/.omp/agent/rules/no-telegraph.md`。
- `~/.omp/agent/mcp.json` 的 ghidra 为 stdio（`re-mcp-ghidra stdio`，env：GHIDRA_INSTALL_DIR / GHIDRA_HOME / JAVA_HOME）。不要改用 HTTP :8765。
- 版本只准来自 `scripts/hacker/reverse-versions.env`（Ghidra zip sha256 必须是 `93a5d11a9ad510622acaaf908c556a7b9b764d338e78a7567f3689bf5081fd54`）。
- 启动器：`scripts/hacker/launch.sh`，避免 `~/.bashrc` 里其它 `OPENAI_BASE_URL` 漏进来。

## 步骤

1. 确认 git / python3 / curl。没有 bun 就 `curl -fsSL https://bun.sh/install | bash`（≥ 1.3.14）。不要为了跑 omp 去装 Rust / Bazel；`install.sh` 会拉预编译 natives。
2. 若还没有 checkout：`git clone https://github.com/fobole-openthedoor/oh-my-pi.git $HOME/oh-my-pi`
3. `$HOME/oh-my-pi/scripts/hacker/install.sh`。若 Claude-Red 被跳过，再跑 `install-claude-red.sh`。
4. `$HOME/oh-my-pi/scripts/hacker/install-reverse.sh`。zip 约 570MB。磁盘不够或用户明确跳过才加 `--skip-ghidra`。不要改版本。
5. 若 `install-reverse.sh` 不存在（旧 checkout），按 `reverse-versions.env` 的 URL 安装同一组工具：Ghidra / jadx、clone `https://github.com/zhaoxuya520/reverse-skill.git` 到 `$HOME/tools/reverse-skill`，`pipx install re-mcp-ghidra==3.0.3 frida-tools==14.10.4 objection==1.12.5 pwntools==4.15.0`，能装则 apt：`openjdk-21-jdk radare2 apktool binwalk gdb gdb-multiarch ffuf nmap sqlmap hashcat adb p7zip-full pipx`，`ln -sfn $HOME/tools/ghidra_12.1.3_PUBLIC $HOME/tools/ghidra`，`bash $HOME/tools/reverse-skill/skills/scripts/refresh-tool-index.sh`，用 `scripts/hacker/wire-ghidra-mcp.py` 写 mcp.json。不要把 API key 写进 mcp.json。
6. 启动 `omp` 后让用户 `/login beefsms` 贴 key。没有 key 就停，不要编造。可选 `BRAVE_API_KEY`。
7. PATH 加上 `$HOME/.local/bin`、`$HOME/tools/jadx/bin`、`$HOME/tools/ghidra/support`、`$HOME/.bun/bin`。
8. 跑 `verify-reverse.sh` 和 `verify-claude-red.sh`。失败就修，直到通过或只剩「用户还没填 key」。
9. 不要提交 `~/.config/omp/env`，不要把真实 key 写进 `models.yml`。不要配置 Forgejo。不要用 `~/.audncode-platform`。

## 验收表

- omp 启动器路径 / git commit / 分支
- OPENAI_BASE_URL（应是 beefsms）；`/login beefsms`；key 是否已填（只答 是/否）
- java 21、analyzeHeadless、jadx、r2、re-mcp-ghidra
- `$HOME/tools/reverse-skill`、tool-index.md
- adapters：`skills/reverse-skill`、`skills/crack`；offensive-sqli symlink
- mcp.json ghidra 为 stdio
- 上列 extensions 与 `rules/no-telegraph.md`
- `domain-route.py --self-test`、`ghidra-open.sh --dry-run`
- verify-reverse.sh / verify-claude-red.sh 退出码
```

复制结束
