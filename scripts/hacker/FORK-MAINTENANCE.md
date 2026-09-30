# Fork 维护手册:同步上游与本地定制

本文件是这台机器上 oh-my-pi fork 的运维真相源。新会话读到后按此操作,不要即兴发挥。

## 仓库拓扑

| 仓库 | 路径 | origin | upstream | 说明 |
|---|---|---|---|---|
| oh-my-pi fork | `/root/oh-my-pi` | `fobole-openthedoor/oh-my-pi` | `can1357/oh-my-pi` | omp CLI 本体,fork 启动器直接跑这个检出 |
| reverse-skill (pi clone) | `/root/.pi/agent/git/github.com/zhaoxuya520/reverse-skill` | `zhaoxuya520/reverse-skill`(只读) | 同 origin;另有 `fork` remote = `fobole-openthedoor/reverse-skill`(可写) | 我们的改动推 fork,上游无写权限 |
| reverse-skill (omp 实际使用) | `/root/tools/reverse-skill` | 本地路径,指向上面的 pi clone | — | `~/.omp/agent/AGENTS.md` 的 `REVERSE_SKILL_ROOT` 指向这里;**改 pi clone 不等于 omp 生效,必须同步到这个目录** |

**`omp update` 在本机不可用**:`/usr/local/bin/omp` 是 fork 启动器,exec `/root/oh-my-pi/packages/coding-agent/scripts/omp`。更新 omp = 同步这个 git 仓库。

## oh-my-pi fork:同步上游

历史是线性的:upstream/main + 5 个定制 commit(2026-09-30 重组,旧历史在 `backup/pre-grouping-18.4.5` 分支)。commit 按上游耦合度排序:

1. `feat(status-line)` — packages/** 状态栏 TTFT/tok-s(最可能与上游冲突)
2. `feat(coding-agent)` — version banner 下的 fork 更新提示
3. `ci` — fork 精简版 CI
4. `docs` — fork README
5. `feat(hacker)` — scripts/hacker/** 全套 kit(零上游重叠,永不冲突)

同步流程:

```bash
cd /root/oh-my-pi
git fetch upstream
git rebase upstream/main        # 5 个 commit 逐个重放,冲突按主题隔离
bun install                     # lockfile 变了才需要
bun run check                   # 必须全绿;不要 tsc
git push origin main --force-with-lease   # rebase 后必须 force
```

注意:

- 上游大版本可能搬迁文件(18.4.5 把 status-line 从 coding-agent 迁到 `packages/tui/`),rebase 冲突先看是不是 rename。
- 新增本地定制时:能放进现有 5 组的就 `commit --fixup` + autosquash 进去;新主题开新 commit,保持按耦合度排序。
- 其他机器 clone 过 fork 的话,force push 后那边要 `git fetch && git reset --hard origin/main`,不能 pull。

## reverse-skill:同步与分发

```bash
# 1. pi clone:拉上游,把我们的 commit rebase 到最新,推 fork
cd /root/.pi/agent/git/github.com/zhaoxuya520/reverse-skill
git fetch origin
git rebase origin/main
bash skills/scripts/test-bootstrap-manifest.sh   # 全绿才继续
bash skills/scripts/test-routing.sh
git push fork main                               # fork remote 可写

# 2. 同步到 omp 实际使用的副本(有本地定制,先 stash)
cd /root/tools/reverse-skill
git stash push -m "omp-sidecar-local-mods"
git pull --ff-only origin main
git stash pop                                    # 冲突则手工合并,sidecar 标记块必须保留
bash skills/scripts/refresh-tool-index.sh        # 重新生成探测表
```

`/root/tools/reverse-skill` 的本地定制(不能丢):apk sidecar 工具(droidasc/ddc/apksigner/zipalign,带 `omp-apk-reverse-sidecar-*:start/end` 标记块)、field-journal 经验记录、community-security-skills.md。

## 本机工具链基线(2026-09-30 装齐)

angr 10.0.0 / keystone-engine 0.9.2 / lief 1.0.0 / pefile 2024.8.26(pip --user,PEP 668 需 `--break-system-packages`);unblob / ropper / semgrep(pipx);lldb(apt);dotnet SDK 8 在 `/root/.dotnet`,ilspycmd 9.1.0.7988(pin 死的,最新版包是坏的);Ghidra 12.1.3 在 `/root/tools/ghidra`(MCP 直连);SecLists 在 `/root/tools/SecLists`。

新工具要让别人受益:加进 reverse-skill 的 `skills/scripts/bootstrap-manifest.json` + `bootstrap-reverse.sh` + `refresh-tool-index.sh`(kali/ 和 ps1 保持 parity),跑通测试后推 fork。
