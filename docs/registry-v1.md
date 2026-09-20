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

同一插件不能有重复版本，ID 和版本路径按大小写不敏感规则去重。历史记录只允许修改撤回状态及原因，插件仓库不可替换。正式收录以维护者合并 PR 为依据，记录中不设置提交者可以自行填写的 `approved: true`。

## Manifest 与包

使用 `api: 4`、`id`、`version` 和 `entry: module:Class`。不接受旧字段 `plugin_id`、`api_version`、`optional` 或 `required: true`。入口模块 `.py` 必须存在，声明的 renderer/editor 文件必须存在。未知扩展字段保留给 Sakura 判断，Registry 不宣称已实现完整宿主兼容解析。

YAML 不允许重复键、anchor/alias、非 JSON 值；快照按实际字段比较。构建不导入插件，也不调用上游发布脚本。ZIP 根为插件 ID，保留原 manifest 字节。所有源码条目检查路径和文件类型，排除 Git 元数据、常见缓存、日志、环境配置和明显私钥文件；保留 `build`、`dist`、`vendor` 及许可证。

限制：源码压缩包 64 MiB，源码声明展开尺寸 128 MiB，源码最多 4096 条目；安装内容最多 512 文件、合计 32 MiB，单文件 16 MiB，manifest 64 KiB。超出则失败，不截断。ZIP 不允许链接、设备、加密内容、Windows 保留名、重复路径或大小写及 Unicode 规范化碰撞。

## Catalog

根对象同样为 `schema_version: 1`、`plugins`。每个插件保留 ID、仓库和所有版本记录；版本新增 `prerelease` 和 `package`。

有效版本的 `package` 为 `{path, url, size}`，`size` 是生成 ZIP 的字节数。`path` 为 `plugins/<id>/<version>/<完整 commit>/plugin.zip`，`url` 由构建时指定的 HTTPS 根地址拼接。撤回版本的 `package` 为 `null`，不要求重新下载已经不可访问的上游源码。

构建必须使用全新输出目录，全部成功后才写入 `catalog/v1/catalog.json`。不会覆盖既有目录；失败目录不得发布。构建结果的顺序不代表推荐顺序，客户端不能直接取最后一个版本安装。

未来上传流程必须先发布所有包，确认对象不存在或复用原始已发布对象，再切换 Catalog。路径包含 commit 不代表存储服务已经禁止覆盖；本阶段只实现本地输出防覆盖。

## 客户端接入约束

客户端应校验 schema、大小限制、HTTPS 下载地址、ZIP 结构及解包后的 ID/版本，并交给现有安装器。不能回退到作者 Release ZIP 或其他源码包。静态文本必须以文本渲染，不能把远端说明当作可信 HTML。

推荐版本应排除撤回和预发布，按 SemVer 选择满足 Plugin API、宿主能力、平台、Python 与依赖要求的最高版本。当前 manifest 没有完整的这些约束，不能凭 `api: 4` 就声称完全兼容；客户端算法在后续 Spec 中落实，本工具不生成 `recommendedVersion`。

安装来源记录计划为 `registry_url`、`plugin_id`、`version`、`repository`、`commit`、`package_url`、`pinned`。这是后续安装事务需要持久化的接口，本阶段未修改 Sakura 安装器，也没有写入真实用户配置。固定版本和更新语义随更新事务一起实施。
