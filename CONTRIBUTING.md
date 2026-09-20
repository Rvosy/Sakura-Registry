# 提交插件

插件作者通过 GitHub Issue 投稿。只需提供插件 ID 和公开仓库地址，收录记录由维护者处理。

## 准备插件

插件仓库根目录需要有 `plugin.yaml`，使用 Sakura Plugin API v4。入口代码、运行资源和许可证随源码提交。开发方式见 [插件 SDK 文档](https://github.com/Rvosy/Sakura/blob/main/docs/devdocs/SAKURA_PLUGIN_SDK.md)。

投稿前，先在 Sakura 中安装并运行插件。在插件 README 中说明功能、配置方式和运行依赖。如果需要 API Key，提供配置方法，不提交实际凭据。

Registry 不运行插件仓库的构建脚本。需要编译的前端资源应提前生成并提交；`dist`、`build` 和 `vendor` 会保留，缓存、日志、`.env` 等本地文件不会进入安装包。

## 首次投稿

打开 [插件投稿表单](https://github.com/Rvosy/Sakura-Registry/issues/new?template=submit-plugin.yml)，填写：

- 插件 ID：与 `plugin.yaml` 的 `id` 一致。
- GitHub 仓库：插件源码的公开仓库地址。

如果希望收录某个版本，可补充 Release、Tag 或 commit；留空时由维护者在 Issue 中与你确认。插件用途、特殊依赖和验证环境也可以写在补充说明里。

提交后，维护者在 Issue 中检查和反馈，确定版本后更新 Registry。你只需按反馈修改自己的插件仓库，无需 Fork Registry、填写 manifest 快照或提交 PR。

目前 Issue 由维护者手动处理，已有 CI 负责收录记录的校验和打包。自动处理投稿仍待接入；客户端在线安装与 CDN 分发也尚未开放。

## 发布新版

推送新版本后，使用同一投稿表单新建 Issue，填写原插件 ID、仓库地址和新版 Release、Tag 或 commit，并说明主要变化。每个版本分别确认，不会自动收录仓库后续的所有提交。

已收录版本的源码保持不变，修复代码时请发布新版本。

## 修改或撤回

通过 [收录变更表单](https://github.com/Rvosy/Sakura-Registry/issues/new?template=change-plugin.yml) 提交资料更正、仓库迁移、版本撤回或恢复请求。涉及具体版本时，请写明版本号和原因。

撤回会保留历史记录，后续目录不再为该版本提供安装包。

## 改进 Registry 工具

欢迎通过 PR 修改 Registry 代码和文档，运行方式见 [开发与构建](docs/development.md)。
