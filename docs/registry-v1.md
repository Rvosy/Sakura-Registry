# Registry v1 契约

状态：记录、构建和 GitHub 投稿流程已实现，客户端与 CDN 接入尚未完成。

## 收录记录

根对象为 `schema_version: 1` 和 `plugins` 数组。每个插件包含：

| 字段 | 内容 |
|---|---|
| `id` | 插件 ID |
| `repository` | 不带 `.git` 后缀的 GitHub HTTPS 仓库地址 |
| `versions` | 版本号到完整 commit 的映射，例如 `{"0.2.6": "6f17c62310c5a7fdd60c7aab82391572db2d9031"}` |
| `yanked` | 可选的撤回版本到原因的映射，例如 `{"0.2.6": "无法加载"}`；无撤回时省略 |

版本号使用 SemVer 2.0，预发布数字段不能有多余前导零。commit 为 40 位小写 Git 引用，不接受分支、Tag 或缩写。撤回版本必须已经收录，原因不能为空。

v1 仅支持仓库根目录下的 `plugin.yaml`。ID 沿用 Sakura 的字母、数字、下划线、点和连字符格式，不要求反向域名。索引不保存 manifest 副本、空说明或默认状态；插件资料从固定源码读取，投稿补充说明留在 Issue。

作者通过 Issue 投稿，自动检查将具体版本解析为完整 commit 并生成候选记录。维护者使用 `/approve 检查编号` 批准该次成功检查，机器人从保留的候选记录生成收录 PR。审批后不会重新解析上游 Tag；Issue 内容变化时旧检查不可用于生成新 PR。正式收录以维护者合并 PR 为依据。

同一插件不能有重复版本，ID 和版本路径按大小写不敏感规则去重。历史版本的 commit 保持不变，撤回状态及原因可以修改。插件仓库地址仍用于构建历史版本，目前不可直接替换。

## Manifest 与包

Registry 检查打包所需的 `api: 4`、`id`、`version` 和 `entry: module:Class`，不接受旧字段 `plugin_id`、`api_version`、`optional` 或 `required: true`。入口模块 `.py` 必须存在，声明的 renderer/editor 文件必须存在。源码中的 ID、版本必须与收录记录一致。其他 manifest 字段写入生成的 Catalog，完整字段校验和运行兼容性由 Sakura 负责。

JSON 使用标准解析器，YAML 与 Sakura 一样使用 `yaml.safe_load`，支持标准 anchor/alias；manifest 需能表示为 JSON。构建不导入插件，也不调用上游发布脚本。ZIP 根为插件 ID，保留原 manifest 字节。

先排除 Git 元数据、常见缓存、日志、`.env`、`.npmrc`、`.pypirc` 和 `id_rsa` 等明确文件名，再对实际入包文件检查路径、文件类型和大小。保留 `build`、`dist`、`vendor`、许可证及证书等运行资源；不按 `.pem`、`.key` 等扩展名猜测内容。作者负责确认提交的文件不含凭据。

下载源码压缩包上限为 64 MiB。安装内容沿用 Sakura 安装器的限制：最多 512 文件、合计 32 MiB，单文件 16 MiB，manifest 64 KiB。已排除文件不解压、不计入安装包限制。入包文件不允许链接、设备、加密内容、Windows 保留名、重复路径或大小写及 Unicode 规范化碰撞。

## Catalog

根对象同样为 `schema_version: 1`、`plugins`。每个插件保留 ID、仓库；`versions` 为生成的版本记录数组，每项包含 `version`、`commit`、`manifest`、`yanked`、`yank_reason`、`prerelease` 和 `package`。有效版本的 `manifest` 是从固定源码读取的完整插件清单，未撤回时 `yanked` 为 `false`、`yank_reason` 为空字符串。

有效版本的 `package` 为 `{path, url, size}`，`size` 是生成 ZIP 的字节数。`path` 为 `plugins/<id>/<version>/<完整 commit>/plugin.zip`，`url` 由构建时指定的 HTTPS 根地址拼接。撤回版本的 `manifest` 和 `package` 均为 `null`，不要求重新下载已经不可访问的上游源码。

构建必须使用全新输出目录，全部成功后才写入 `catalog/v1/catalog.json`。不会覆盖既有目录；失败目录不得发布。构建结果的顺序不代表推荐顺序，客户端不能直接取最后一个版本安装。

未来上传流程必须先发布所有包，确认对象不存在或复用原始已发布对象，再切换 Catalog。路径包含 commit 不代表存储服务已经禁止覆盖；本阶段只实现本地输出防覆盖。

## 客户端接入约束

客户端应校验 schema、大小限制、HTTPS 下载地址、ZIP 结构及解包后的 ID/版本，并交给现有安装器。不能回退到作者 Release ZIP 或其他源码包。静态文本必须以文本渲染，不能把远端说明当作可信 HTML。

推荐版本应排除撤回和预发布，按 SemVer 选择满足 Plugin API、宿主能力、平台、Python 与依赖要求的最高版本。当前 manifest 没有完整的这些约束，不能凭 `api: 4` 就声称完全兼容；客户端算法在后续 Spec 中落实，本工具不生成 `recommendedVersion`。

安装来源记录计划为 `registry_url`、`plugin_id`、`version`、`repository`、`commit`、`package_url`、`pinned`。这是后续安装事务需要持久化的接口，本阶段未修改 Sakura 安装器，也没有写入真实用户配置。固定版本和更新语义随更新事务一起实施。
