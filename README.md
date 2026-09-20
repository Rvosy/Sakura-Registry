# Sakura Registry

[Sakura](https://github.com/Rvosy/Sakura) 的社区插件目录。插件作者在自己的 GitHub 仓库维护源码，通过这里提交收录和版本更新；Registry 从收录的源码版本构建安装包，供 Sakura 插件市场分发。

通过 GitHub Issue 投稿，维护者确认后收录。客户端在线安装与 CDN 分发仍在开发中，收录后暂不会直接出现在应用内市场。

## 开发插件

插件使用 Sakura Plugin API v4。将 `plugin.yaml` 放在仓库根目录，与入口代码和运行资源一起提交。开发接口和示例见 [插件 SDK 文档](https://github.com/Rvosy/Sakura/blob/main/docs/devdocs/SAKURA_PLUGIN_SDK.md)，也可以参考独立插件 [Sakura-Spine](https://github.com/Rvosy/Sakura-Spine)。

投稿前，请先在 Sakura 中安装并运行自己的插件，在插件仓库的 README 中写明功能、配置方式、运行依赖和许可证。

## 提交插件

1. 将插件源码推送到公开 GitHub 仓库。
2. 打开 [插件投稿表单](https://github.com/Rvosy/Sakura-Registry/issues/new?template=submit-plugin.yml)，填写插件 ID 和仓库地址；需要指定版本时附上 Release、Tag 或 commit。
3. 提交 Issue，维护者会在其中反馈问题并确认收录版本。

作者无需 Fork 本仓库或填写 Registry JSON。维护者负责解析版本、生成 manifest 快照并更新目录，现有 CI 检查记录和构建安装包。投稿细节见 [投稿指南](CONTRIBUTING.md)。

插件源码继续保留在作者仓库，无需把源码或 ZIP 提交到这里。构建时会保留已提交的运行资源；需要编译前端资源的插件，应将编译结果一起提交。

## 更新与撤回

发布新版后，再通过 [投稿表单](https://github.com/Rvosy/Sakura-Registry/issues/new?template=submit-plugin.yml) 提交版本信息。每个版本分别确认，已有版本的源码保持不变。

需要更正资料或撤回版本时，提交 [收录变更 Issue](https://github.com/Rvosy/Sakura-Registry/issues/new?template=change-plugin.yml)，说明版本和原因。撤回后保留历史记录，不再为该版本提供安装包。

## 参与维护

发现收录信息有误或投稿遇到问题，可以 [提交 Issue](https://github.com/Rvosy/Sakura-Registry/issues/new)。改进 Registry 工具本身请阅读 [开发与构建](docs/development.md)；数据字段见 [Registry v1 契约](docs/registry-v1.md)。
