# CS2Toolkit

一个面向 `Counter-Strike 2` 的 Windows 桌面工具，提供游戏资源替换、GSI 实时事件联动、视觉覆盖和 `GO桌宠` 等功能。

本仓库是 [thok404/CS2Toolkit](https://github.com/thok404/CS2Toolkit) 维护的 fork 修复版，基于 [clover-233/CS2Toolkit](https://github.com/clover-233/CS2Toolkit)。原作者为 Moon4Quartz。

**本版本遇到的问题请反馈到 thok404/CS2Toolkit，不要联系原作者。** 本版本的更新检查仅以此 fork 的发布版本为准。

## 项目状态

- 技术栈：`Python`、`PySide6`、`PySide6-Fluent-Widgets`
- 当前平台：`Windows 10/11`
- 主要依赖：`PySide6`、`PySide6-Fluent-Widgets`、`requests`、`pycaw`
- 开源许可证：`GPL-3.0-only`

## 功能概览

### 资源替换
- 自定义开屏动画，支持 `WEBM`
- 自定义启动音效
- 自定义游戏字体
- 预设保存、切换、删除与导入导出

### GSI 联动
- 基于 `Game State Integration` 监听游戏状态
- 根据击杀、死亡、炸弹、回合状态等事件播放音效
- 支持更细粒度的互动事件配置

### 游戏内视觉
- 自定义闪光替换图
- 自定义击杀图标
- 自定义死亡媒体
- 支持文件夹资源随机选择

### GO桌宠
- 支持图片、GIF、`WEBM`
- 支持大小与位置调节
- 支持游戏内显示和主播输出窗口模式
- 支持根据血量、炸弹、胜负、MVP、Freeze Time 等事件切换状态

## 快速开始

### 环境要求
- 已安装 `Python 3.10+`
- 已安装 `Counter-Strike 2`
- 操作系统为 `Windows 10/11`

### 安装依赖

```bash
pip install -r requirements.txt
```

### 运行项目

```bash
python main.py
```

### 自定义数据存储目录

默认情况下，CS2Toolkit 会将您的配置文件、导入的媒体素材等保存在系统 C 盘 (`%LOCALAPPDATA%\CS2Toolkit`)。如果您希望将其移动到其他盘符：

1. 打开软件，进入 **“设置”** 页面。
2. 找到 **“数据存储”** 面板，点击 **“迁移目录”**。
3. 选择新的目标文件夹（例如 `D:\CS2ToolkitData`），软件会自动将所有配置和素材安全复制过去。
4. 迁移成功后软件将退出，重新启动即可在新路径下运行。

## 目录结构

```text
CS2Toolkit/
├── main.py
├── app/
│   ├── main_window.py
│   ├── assets/
│   ├── logic/
│   └── ui/
├── LICENSE
├── README.md
├── THIRD_PARTY_NOTICES.md
└── OPEN_SOURCE_RELEASE_CHECKLIST.md
```

## 开源说明

### 重要许可结论

- 本项目当前依赖 `PySide6-Fluent-Widgets`
- 根据该依赖上游声明，非商业/开源使用通常应走 `GPLv3` 路线；如果要做闭源分发或单独商业发行，通常应向该库作者获取商业许可证
- 因此，在继续使用当前依赖组合且未单独购买商业许可证的前提下，本项目以 `GPLv3` 开源发布
- 这也意味着：你不能再额外给本项目代码加上与 `GPLv3` 冲突的限制，例如“禁止修改”“禁止再分发”“禁止收费分发”或“禁止商用”

### 许可证

本项目以 `GPLv3` 发布，详见 [LICENSE](./LICENSE)。

你可以：
- 使用、学习、修改和再发布本项目源码
- 在遵守 `GPLv3` 前提下发布修改版本

你需要：
- 保留原始版权和许可证声明
- 在分发二进制时同时提供对应源码或源码获取方式
- 将基于本项目形成的衍生作品继续以 `GPLv3` 兼容方式发布

需要特别说明：
- 在 `GPLv3` 下，其他人可以修改、再分发，甚至收费分发本项目代码，但前提是他们也必须继续遵守 `GPLv3`
- `GPLv3` 可以约束“闭源分发”，但不能阻止“在继续开源并遵守许可证前提下的再分发或收费分发”
- 如果你不能接受这一点，就不应在当前依赖组合下继续使用 `GPLv3` 开源方案，而应更换依赖或另行获取商业授权

### 第三方依赖

项目依赖的第三方组件及许可证摘要见 [THIRD_PARTY_NOTICES.zh-CN.md](./THIRD_PARTY_NOTICES.zh-CN.md)。

需要特别注意：
- `PySide6` 本身并不等于整个项目都可直接闭源商用
- 本项目依赖 `PySide6-Fluent-Widgets`，如果你以当前依赖组合做闭源或单独商业分发，不能只依据 `PySide6` 的许可判断
- 以当前方案开源并按 `GPLv3` 发布是匹配的
- 如果未来要做闭源商用版本，应单独向 `PySide6-Fluent-Widgets` 作者获取商业许可证

### 非官方声明

- 本项目不是 `Valve` 官方产品，也不隶属于 `Valve`
- `Counter-Strike`、`Counter-Strike 2`、`CS2` 及相关名称、图形和商标归其各自权利人所有

### 资源与版权边界

本仓库默认不应包含未获授权的第三方素材，包括但不限于：
- 游戏原始资源
- 动漫、影视、游戏角色图片
- 第三方音频、视频、字体、图标
- 用户自行导入的配置包与资源包

如果你要公开发布仓库或二进制，请确保：
- 你拥有仓库内所有媒体资源的分发权
- 你未提交本机配置、日志、缓存、打包产物和导入资源
- 你明确告知用户：自行导入的资源版权由用户负责

以下内容不视为本项目代码 `GPLv3` 授权范围的一部分，除非仓库中另有明确声明：
- 项目名称、作者名称与作者主页信息
- 图标、Logo、截图、宣传图、赞赏码图片等品牌或展示素材
- 默认媒体资源、演示资源以及任何未单独声明为可再分发的非代码文件

如果他人基于本项目进行 fork、修改或再分发：
- 不应暗示其版本是本项目官方版本
- 不应在未经许可的情况下继续使用你的品牌标识、作者身份信息、赞赏码或默认宣传素材进行宣传或售卖

## 仓库清洁规则

以下内容不应提交到公开仓库：
- `preconfig.json`
- `imported/`
- `configs/`
- `thumbnails/`
- `dist/`
- `*.log`
- `nuitka-crash-report*.xml`

发布前请参考 [OPEN_SOURCE_RELEASE_CHECKLIST.zh-CN.md](./OPEN_SOURCE_RELEASE_CHECKLIST.zh-CN.md) 逐项检查。

## fork 更新检查与公告

软件默认通过 GitHub Releases 检查 `thok404/CS2Toolkit` 的最新正式发布，读取发布标签、说明和便携包下载链接。仅当发布版本比当前版本更新时才提示下载，未发布 Release 时会在手动检查中说明。

首页默认显示 fork 说明。“关于”页和便携包内的 `FORK_NOTICE.txt` 也注明反馈归属。

如需本地覆盖更新或公告源：

1. 复制 `release_endpoints.local.example.json`
2. 重命名为 `release_endpoints.local.json`
3. 按你的实际地址填写（更新源须兼容 GitHub Releases 响应格式，公告源使用 `title`/`content` JSON）：

```json
{
  "update_url": "https://api.github.com/repos/thok404/CS2Toolkit/releases/latest",
  "announcement_url": ""
}
```

也可使用 `CS2TOOLKIT_UPDATE_URL`、`CS2TOOLKIT_ANNOUNCEMENT_URL` 环境变量。打包后会还原源文件中的默认地址，本地覆盖值不会写入提交。

## 已知边界

- 项目会读取本机 `Steam/CS2` 安装路径并与本地游戏文件交互
- 项目部分功能依赖 `GSI` 和 Windows 音频接口
- 不同版本的游戏资源结构或系统环境可能影响功能表现

## 贡献

欢迎提交 `Issue` 和 `Pull Request`。

提交前建议：
- 不要提交本机配置、日志和素材资源
- 不要在 PR 中混入打包产物
- 如果新增依赖，请同步更新第三方许可证说明

## 免责声明

- 本项目按“现状”提供，不附带任何明示或暗示担保
- 使用本工具修改本地游戏文件、覆盖资源或加载第三方素材的风险由用户自行承担
- 使用者应自行确认其行为符合当地法律、平台规则与相关软件许可协议
