---
name: avs
description: 用 ADB 读取安卓当前屏幕上的文字/按钮及坐标，并按编号点击。用户提到手机屏幕、权限弹窗、点按钮、Android/ADB 自动化时使用。
---

# avs — 读安卓屏幕、按编号点击

`avs` 是一个命令行工具。它截图、读取界面树（必要时调用视觉模型），把屏幕内容变成纯文本：
可见文字 + 带编号的可点击控件 + 设备像素坐标。你不需要看图，也不会收到图片。

## 什么时候用

- 用户让你看手机/模拟器屏幕上有什么
- 需要点按钮：权限弹窗（允许 / 拒绝 / 始终允许 / 仅在使用该应用时允许）、安装确认（继续安装 / 安装）、应用内按钮
- Android / ADB 自动化中需要"看一眼再点一下"

不适用：iOS、桌面程序。

## 命令

```
avs devices                                   # 列出已连接设备
avs snapshot [--serial S] [--force-vision]    # 读屏，输出编号列表
avs tap <id> | --text 允许 | --xy 720,1620 [--serial S]
avs type <id> TEXT | --text "Phone number" TEXT [--serial S]
avs key BACK|HOME|ENTER [--serial S]
```

任何命令都可以加 `--json` 得到结构化输出。

## 标准流程：先 snapshot，再 tap

1. `avs snapshot`
2. 读输出，找到目标控件的编号
3. `avs tap <id>`（或 `avs tap --text 允许`）。往输入框填字用 `avs type <id> TEXT`，不要先点出键盘再 `input text`
4. **再次 `avs snapshot`** 确认结果 —— 每次 tap/type/key 之后旧编号立即作废；前台应用变化或 snapshot 超过 10 分钟也会作废，必须重新 snapshot

输出示例：

```
ok=true snapshot=s_001 serial=emulator-5554 source=hybrid 1080x2400
app=com.android.permissioncontroller
[1] text "要允许“地图”获取此设备的位置信息吗？"
[2] button "仅在使用该应用时允许" @(540,1690)
[3] button "仅限这一次" @(540,1850)
[4] button "不允许" @(540,2010)
```

- `[n]` 是编号，`tap` / `type` 用它；`@(x,y)` 是设备像素中心点（左上角为原点）
- `source=tree` 来自界面树，`vision` 来自视觉模型，`hybrid` 两者合并
- 行尾可能有 `checked` / `unchecked` / `disabled` / `focused`。无文字的控件显示资源 id，如 `[5] button #fab_add`
- 输入框始终带 `#resource_id`。行尾 `empty` 表示框里还没有值，引号里是 hint（占位提示），不是已经输入的内容。有值时引号里就是当前值，例如 `[8] input "838-0802-6584" #registration_phone @(439,513)`
- `warning=...` 行表示视觉模型失败但界面树仍有结果，可以继续用

## 规则

- **不要猜像素坐标。** 坐标只来自 `avs snapshot` 的输出。优先 `avs tap <id>`，其次 `--text`；`--xy` 只在 snapshot 给出了坐标但控件没法用编号/文字表达时使用。
- **点控件不依赖坐标注入。** 界面树里能看到的控件，`avs tap` 走无障碍 `ACTION_CLICK`（直接 `performClick`，不经过输入栈）。成功时输出 `via=action`。透明遮罩、对话框外的全屏触摸区、残留窗口会把 `input tap` 吃掉——这种情况下坐标注入不会被拿来冒充成功。`via=input` 只出现在界面树里没有这个控件（例如纯视觉结果或 `--xy`）且没有遮罩挡住该点时。
- **往输入框填字用 `avs type`。** `avs type 8 83808026584` 或 `avs type --text "Phone number" 83808026584`。这是 `ACTION_SET_TEXT`，不需要先点出键盘，中文也可以。读回值和你写的不一样时（号码被加上横线）会多一行 `readback=`。`warning=tree_hides_value` 表示控件接受了文字但界面树读不回内容，接着用 `avs snapshot --force-vision` 核对。填完后按钮可能要过一会儿才从 `disabled` 变成可点，所以要再 snapshot。
- **权限弹窗、安装确认**（允许 / 拒绝 / 始终允许 / 继续安装 等）：用 `avs tap --text 允许` 或 `avs tap <id>`。`--text` 先精确匹配，再忽略大小写，再子串匹配；匹配到多个会报 `error=ambiguous` 并列出候选编号，此时改用编号。子串匹配不会选中多了否定词的按钮（`--text 允许` 不会点到"不允许"，`--text Allow` 不会点到"Don't allow"）；报 `not_found` 时看列表改用编号。
- **`error=secure_or_black`**：截图全黑（FLAG_SECURE 页面、锁屏或熄屏）。**停下来告诉用户**，不要编造按钮，不要盲点。
- **多设备**：`avs devices` 列出多台时，所有命令都要带 `--serial S`（也可设置环境变量 `AVS_SERIAL`）。avs 不会替你选设备。
- 需要结构化结果时加 `--json`（`elements[].id/text/type/clickable/center/bounds`）。
- 需要返回/回桌面/回车：`avs key BACK|HOME|ENTER`。状态栏和系统导航栏不会出现在列表里。
- **不要安装 MCP，不要自己拼 adb 命令**（`adb shell input tap ...` 等），一律通过 `avs`。

## 错误

输出第一行 `ok=false error=<code>`，第二行 `message=...`，退出码非 0：

| error | 含义 / 怎么办 |
|---|---|
| `secure_or_black` | 屏幕被保护或锁屏，停止并告知用户（退出码 3） |
| `no_snapshot` / `stale_snapshot` | 先运行 `avs snapshot` |
| `not_found` / `ambiguous` | 重新看 snapshot，换编号 |
| `out_of_screen` | 坐标超出屏幕 |
| `action_failed` | 界面树里的控件没有接受无障碍点击。重新 snapshot；不要改用坐标盲点 |
| `input_blocked` | 这个坐标会被一块窗口的触摸区吃掉（窗口的可见区域并不包含该点）。不要再 `input tap` |
| `not_editable` | `avs type` 的目标不是输入框，或控件拒绝写入 |
| `multiple_devices` / `no_device` / `device_not_found` / `device_offline` / `device_unauthorized` | 加 `--serial`（先 `avs devices` 看列表），或让用户连接/授权设备 |
| `vision_failed` | 界面树不可用且视觉模型失败；可 `avs snapshot` 重试一次，仍失败则告知用户检查 `AVS_VISION_*` 配置 |

屏幕上只有很少控件或出现系统弹窗时 avs 会自动调用视觉模型；只有在列表明显漏掉可见按钮时才用 `--force-vision`。
