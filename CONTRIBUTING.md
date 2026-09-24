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

如果希望收录某个版本，可补充 Release 链接、Tag 或 commit；留空时取最新正式 Release，没有 Release 则取默认分支。机器人会把解析出的版本和完整 commit 回贴到 Issue。插件用途、特殊依赖和验证环境也可以写在补充说明里。

提交后，Actions 自动读取 manifest、核对 ID 并试打包，检查结果和预览包链接会回贴到 Issue。检查失败时按提示修正；编辑 Issue 会重新检查，插件仓库有改动时也可以评论 `/recheck`。

维护者查看固定源码与检查结果后，评论 `/approve 检查编号`。机器人生成收录 PR 并启动校验，维护者合并后完成收录、关闭原 Issue。你无需 Fork Registry、填写索引记录或提交 PR。

GitHub 可能在机器人 PR 上显示工作流审批按钮，由维护者处理；自动分支校验会照常运行。

审批对应某次检查的固定结果。编辑 Issue 后需要重新检查；上游后续提交不会替换已检查的源码。检查产物保留 30 天，过期后评论 `/recheck` 即可。

收录合并后自动构建 Catalog 和安装包，全部上传完成后发布到 GitHub Releases。客户端从最新目录读取详细信息，再通过 GitHub 或镜像下载对应安装包。构建失败时不会切换目录，原已发布目录保持可用。

## 发布新版

推送新版本后，使用同一投稿表单新建 Issue，填写原插件 ID、仓库地址和新版 Release、Tag 或 commit，并说明主要变化。每个版本分别确认，不会自动收录仓库后续的所有提交。

已收录版本的源码保持不变，修复代码或更新随包文档时请发布新版本，再提交收录。仅修改仓库默认分支的 README 不会更新已发布 Catalog 中的说明。

## 修改或撤回

通过 [版本变更表单](https://github.com/Rvosy/Sakura-Registry/issues/new?template=change-plugin.yml) 提交版本撤回或恢复请求，填写插件 ID、版本号和原因。撤回无需下载上游源码；恢复会重新检查原来固定的源码。维护者批准后生成变更 PR。

资料更正、仓库迁移等其他变更，请开普通 Issue 说明，由维护者处理。

撤回会保留历史记录，后续目录不再为该版本提供安装包。

## 改进 Registry 工具

欢迎通过 PR 修改 Registry 代码和文档，运行方式见 [开发与构建](docs/development.md)。
