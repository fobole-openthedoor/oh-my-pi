# 安装这套 oh-my-pi（本 fork）

打开这个仓库就是为了装这个。**不要** `bun install -g @oh-my-pi/pi-coding-agent`，**不要** `curl -fsSL https://omp.sh/install | sh`。那些是上游二进制，没有本 fork 的 `scripts/hacker` 安装包。

供应商已经写死：`http://openai.beefsms.com:38888/v1`（`happy/kimi-k3` / `happy/glm-5.3` / `happy/glm-5.3-plus` / `happy/qwen-3.8-fast` / `deepseek-flash`）。`modelRoles.default` 默认 `beefsms/happy/glm-5.3-plus`，`smol` 默认 `beefsms/deepseek-flash`，`vision` 默认 `beefsms/deepseek-flash:low`，不预置 `slow`。Key 自己填，不进 git。

需要：`git`、`python3`、Bun ≥ 1.3.14。没有 bun 脚本会装。不需要本机装 Rust：`install.sh` 会拉对应平台的预编译 `pi-natives` addon。

## 人：三条命令

```sh
curl -fsSL https://raw.githubusercontent.com/fobole-openthedoor/oh-my-pi/main/scripts/hacker/bootstrap.sh | sh
~/oh-my-pi/scripts/hacker/install-reverse.sh
```

`install.sh` 会铺 launcher、beefsms、Claude-Red `offensive-*` skills 和 kit extension。第二行脚本按 `reverse-versions.env` 钉死版本拉齐本机工具链（含 Ghidra zip，约 570MB；已有安装可加 `--skip-ghidra`）。若 Claude-Red 被跳过，再跑 `~/oh-my-pi/scripts/hacker/install-claude-red.sh`。更新已有机器：`~/oh-my-pi/scripts/hacker/update.sh`（merge 安装包，不覆盖 key）。

然后启动 `omp`，在 TUI 里执行 **`/login beefsms`**，粘贴 beefsms API key。网关地址已经写死为 `http://openai.beefsms.com:38888/v1`，不用填 URL。

也可以把 key 写进 `~/.config/omp/env` 的 `BEEFSMS_API_KEY` 或 `OPENAI_API_KEY`（不进 git）。可选 `BRAVE_API_KEY`。

```sh
~/oh-my-pi/scripts/hacker/verify-reverse.sh
~/oh-my-pi/scripts/hacker/verify-claude-red.sh
omp
# 然后: /login beefsms
```

磁盘不够可先跳过 Ghidra zip，CLI 也能用。

## AI：把提示词整段贴过去

打开仓库根目录 **[README.md](README.md) 顶部** 或 **[PROMPT.md](PROMPT.md)**（两段相同），把「从这里复制」到「复制结束」发给任意能跑终端的 AI。只丢 GitHub 链接时，AI 应先读 README 顶部，不要跑下面上游的 `omp.sh/install`，也不要跳过 copy-block 里点名的脚本。人只负责事后填 key。

细节与脚本清单：`scripts/hacker/README.md`。
