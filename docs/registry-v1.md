# Registry v1 契约

状态：第一阶段已实现。该契约约束本仓库的记录和构建产物，客户端接入尚未完成。

## 收录记录

根对象为 `schema_version: 1` 和 `plugins` 数组。每个插件只有 `id`、`repository`、`versions`。

`repository` 是不带 `.git` 后缀的规范 GitHub HTTPS 仓库地址。v1 仅支持仓库根目录下的 `plugin.yaml`。ID 沿用 Sakura 的字母、数字、下划线、点和连字符格式，不要求反向域名。

每个版本包含：

| 字段 | 约束 |
|---|---|
| `version` | SemVer 2.0 字符串，与 manifest 完全相同；预发布数字段不能有多余前导零 |
| `commit` | 40 位小写 Git commit，不接受分支、tag 或缩写 |
| `manifest` | 完整 JSON 可表达的 manifest 快照，保留 `provides`、`requires`、`presentation`、`visuals` 等字段 |
| `notes` | 版本说明，字符串 |
| `yanked` | 布尔值 |
| `yank_reason` | 撤回时必填；未撤回时为空 |

作者通过 Issue 投稿，维护者确认具体版本后更新收录记录。PR 用于维护者审阅目录变更，不要求作者提交。正式收录以维护者合并 PR 为依据。

同一插件不能有重复版本，ID 和版本路径按大小写不敏感规则去重。历史版本的 commit 和 manifest 保持不变，说明、撤回状态及原因可以修改。插件仓库地址仍用于构建历史版本，目前不可直接替换。

## Manifest 与包

Registry 检查打包所需的 `api: 4`、`id`、`version` 和 `entry: module:Class`，不接受旧字段 `plugin_id`、`api_version`、`optional` 或 `required: true`。入口模块 `.py` 必须存在，声明的 renderer/editor 文件必须存在。其他 manifest 字段随快照保留，完整字段校验和运行兼容性由 Sakura 负责。

JSON 使用标准解析器，YAML 与 Sakura 一样使用 `yaml.safe_load`，支持标准 anchor/alias；快照需能表示为 JSON，并按实际字段比较。构建不导入插件，也不调用上游发布脚本。ZIP 根为插件 ID，保留原 manifest 字节。

先排除 Git 元数据、常见缓存、日志、`.env`、`.npmrc`、`.pypirc` 和 `id_rsa` 等明确文件名，再对实际入包文件检查路径、文件类型和大小。保留 `build`、`dist`、`vendor`、许可证及证书等运行资源；不按 `.pem`、`.key` 等扩展名猜测内容。作者负责确认提交的文件不含凭据。

下载源码压缩包上限为 64 MiB。安装内容沿用 Sakura 安装器的限制：最多 512 文件、合计 32 MiB，单文件 16 MiB，manifest 64 KiB。已排除文件不解压、不计入安装包限制。入包文件不允许链接、设备、加密内容、Windows 保留名、重复路径或大小写及 Unicode 规范化碰撞。

## Catalog

根对象同样为 `schema_version: 1`、`plugins`。每个插件保留 ID、仓库和所有版本记录；版本新增 `prerelease` 和 `package`。

有效版本的 `package` 为 `{path, url, size}`，`size` 是生成 ZIP 的字节数。`path` 为 `plugins/<id>/<version>/<完整 commit>/plugin.zip`，`url` 由构建时指定的 HTTPS 根地址拼接。撤回版本的 `package` 为 `null`，不要求重新下载已经不可访问的上游源码。

构建必须使用全新输出目录，全部成功后才写入 `catalog/v1/catalog.json`。不会覆盖既有目录；失败目录不得发布。构建结果的顺序不代表推荐顺序，客户端不能直接取最后一个版本安装。

未来上传流程必须先发布所有包，确认对象不存在或复用原始已发布对象，再切换 Catalog。路径包含 commit 不代表存储服务已经禁止覆盖；本阶段只实现本地输出防覆盖。

## 客户端接入约束

客户端应校验 schema、大小限制、HTTPS 下载地址、ZIP 结构及解包后的 ID/版本，并交给现有安装器。不能回退到作者 Release ZIP 或其他源码包。静态文本必须以文本渲染，不能把远端说明当作可信 HTML。

推荐版本应排除撤回和预发布，按 SemVer 选择满足 Plugin API、宿主能力、平台、Python 与依赖要求的最高版本。当前 manifest 没有完整的这些约束，不能凭 `api: 4` 就声称完全兼容；客户端算法在后续 Spec 中落实，本工具不生成 `recommendedVersion`。

安装来源记录计划为 `registry_url`、`plugin_id`、`version`、`repository`、`commit`、`package_url`、`pinned`。这是后续安装事务需要持久化的接口，本阶段未修改 Sakura 安装器，也没有写入真实用户配置。固定版本和更新语义随更新事务一起实施。
