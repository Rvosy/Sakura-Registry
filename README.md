# Sakura Registry

[Sakura](https://github.com/Rvosy/Sakura) 的社区插件目录。插件作者在自己的 GitHub 仓库维护源码，通过这里提交收录和版本更新；Registry 从收录的源码版本构建安装包，供 Sakura 插件市场分发。

目前开放 PR 投稿，自动校验和构建已可用。客户端在线安装与 CDN 分发仍在开发中，收录合并后暂不会直接出现在应用内市场。

## 开发插件

插件使用 Sakura Plugin API v4。将 `plugin.yaml` 放在仓库根目录，与入口代码和运行资源一起提交。开发接口和示例见 [插件 SDK 文档](https://github.com/Rvosy/Sakura/blob/main/docs/devdocs/SAKURA_PLUGIN_SDK.md)，也可以参考独立插件 [Sakura-Spine](https://github.com/Rvosy/Sakura-Spine)。

投稿前，请先在 Sakura 中安装并运行自己的插件，在插件仓库的 README 中写明功能、配置方式、运行依赖和许可证。

## 提交插件

1. 将插件源码推送到公开 GitHub 仓库，确定要提交的版本和完整 commit。
2. Fork 本仓库，参考 [Spine 收录示例](examples/spine.json)，在 [`plugins.json`](plugins.json) 的 `plugins` 数组中添加插件记录。
3. 填入仓库地址、版本、commit、该提交的 manifest 快照和版本说明，向本仓库发起 PR。

CI 会检查记录并尝试打包。维护者通过 PR 反馈问题、审核和合并。具体字段与本地检查命令见 [投稿指南](CONTRIBUTING.md)。

插件源码继续保留在作者仓库，无需把源码或 ZIP 提交到这里。构建时会保留已提交的运行资源；需要编译前端资源的插件，应将编译结果一起提交。

## 更新与撤回

发布新版时，在原插件的 `versions` 数组中追加记录，再提交 PR。每个版本分别收录，已有版本的 commit 和 manifest 保持不变；版本说明可以修正。

需要撤回某个版本时，将其 `yanked` 改为 `true`，填写 `yank_reason` 后提交 PR。记录会保留，构建目录中不再为该版本提供安装包。

## 参与维护

发现收录信息有误或投稿遇到问题，可以 [提交 Issue](https://github.com/Rvosy/Sakura-Registry/issues/new)。改进 Registry 工具本身请阅读 [开发与构建](docs/development.md)；数据字段见 [Registry v1 契约](docs/registry-v1.md)。
