# 提交插件

当前通过 Pull Request 收录插件和新版本，Issue 用于讨论与反馈。

## 准备插件仓库

插件源码需要放在公开 GitHub 仓库，根目录有 `plugin.yaml`。使用 Plugin API v4，在 manifest 中填写稳定的 `id`、SemVer 版本号及 `entry` 入口。入口代码、运行资源、许可证应随源码提交。

先在 Sakura 中安装并运行插件，确认主要功能可用。在插件 README 中说明安装后的配置、所需服务或模型；如果需要 API Key，提供配置方式，不提交实际凭据。

Registry 不运行插件仓库的构建脚本。前端等需要编译的资源应提前生成并提交。`.git`、`.github`、缓存、日志、`.env` 等本地配置不会进入包，`dist`、`build` 和 `vendor` 会保留。

## 添加收录记录

在插件仓库中获取要投稿的提交：

```sh
git rev-parse HEAD
```

确认该提交已推送到 GitHub。Fork 并克隆 Sakura-Registry，在 `plugins.json` 的 `plugins` 数组中加入一条记录。以下为字段示例，仓库、commit 和 manifest 都需要替换为自己的实际值：

```json
{
  "id": "my_plugin",
  "repository": "https://github.com/your-name/my-plugin",
  "versions": [
    {
      "version": "1.0.0",
      "commit": "填写 git rev-parse HEAD 输出的完整 commit",
      "manifest": {
        "api": 4,
        "id": "my_plugin",
        "name": "我的插件",
        "version": "1.0.0",
        "entry": "plugin:MyPlugin",
        "provides": [],
        "requires": []
      },
      "notes": "首次发布。",
      "yanked": false,
      "yank_reason": ""
    }
  ]
}
```

`manifest` 是指定 commit 中整份 `plugin.yaml` 的 JSON 表示，包含自己的所有字段。不要只摘取上面示例列出的字段，也不要从尚未提交的工作区复制。可参考 [Spine 的完整记录](examples/spine.json)。

使用 Python 3.12 或以上版本，在 Registry 仓库根目录检查记录：

```sh
python -m pip install -r requirements.txt
python -m registry validate
```

这个命令检查记录格式。提交 PR 后，CI 还会下载指定源码、核对 manifest 并构建 ZIP；本地运行同样的构建流程见 [开发与构建](docs/development.md)。

## 发起 PR

标题建议为 `收录：插件名 版本号` 或 `更新：插件名 版本号`。在 PR 中写明插件用途、源码提交、运行依赖，以及已在什么 Sakura 版本和系统上验证过哪些功能。

如果 CI 失败，可以在 Actions 日志中查看失败原因，修正记录或源码后继续推送到同一 PR。维护者会在 PR 中提出修改意见，审核完成后合并。当前合并仅完成收录，应用内在线分发仍在接入。

## 维护已有插件

新版本追加到已有插件的 `versions` 数组，保留历史记录。已收录版本的源码 commit 和 manifest 不可替换；代码需要修复时发布新版本。版本说明中的笔误可以直接修正。

撤回版本时设置 `yanked: true` 并填写原因，保留原版本记录。恢复时改为 `false`，清空原因。两种操作都通过 PR 提交。

需要迁移或重命名插件仓库时，请先开 Issue 说明。目前仓库地址也用于构建历史版本，需要确认旧版本仍可取得。
