# YAML 核查脚本

机械体检层的工具：对拆解产出做**客观、可复现**的自动检查，把"眼睛能发现的机械问题"交给脚本，人工只保留判断。

## 它检查什么

| 类别 | 检查项 |
| --- | --- |
| **YAML 语法** | 每个 ` ```yaml ` 块能否被 `yaml.safe_load_all` 解析 |
| **结构完整性** | 必填字段是否齐全、是否为空 |
| **枚举合法性** | `rule_type` / `action.type` / `condition.operator` 是否在允许集合内 |
| **条款号真伪** | `article` 是否为真实条款号、是否存在于官方原文 |
| **引用逐字** | `legal_basis.quote` 能否在官方文本中逐字匹配（去空白后比对） |
| **占位符残留** | `XXXXXXXX` / `???` / `[待填]` / `TODO` / `待补充` |
| **唯一性** | `rule_id` 是否重复 |

## 用法

```bash
pip install pyyaml python-docx
```

```bash
# 只做结构与语法检查
python yaml_audit.py sample.md

# 带官方原文，校验条款号与 quote 逐字
python yaml_audit.py sample.md --law-text law.docx

# 严格模式（警告也算失败）+ 输出 JSON 报告
python yaml_audit.py sample.md --law-text law.docx --strict --json report.json
```

`--law-text` 支持 `.docx`（需要 python-docx）和 `.txt`。

## 输出

- 统计：YAML 块数、解析成功数、`rule_id` 数、官方条款数、错误数、警告数；
- 逐条问题：`[ERROR|WARN] line N rule_id 描述`；
- 退出码：有 ERROR（strict 模式下有 WARN）返回 1，可直接接入 CI。

示例：

```
======================================================================
file: sample.md
yaml_blocks: 12 parsed_docs: 12 unique_rule_ids: 12
official_articles: 55 errors: 2 warnings: 3
[ERROR] line 88 DSL-004 article 不存在于官方原文: 第73条
[WARN]  line 102 DSL-006 quote 未在官方文本中逐字匹配（可能标点/改字/拼接）
======================================================================
```

## 边界

**脚本只抓机械问题，不判断法律推理对错。**

- 它能告诉你"这条引用不是原文原句"，但不能告诉你"这个例外挂错了分支"；
- 它能告诉你"义务类型编码不是 obligation"，但不能告诉你"这里应该是义务还是授权"；
- 逻辑正确性、但书完整性、覆盖账本诚实度，仍需人工复核。

这一层的设计意义：**把可以自动化的部分固化下来，让裁判的注意力全部放在真正需要判断的地方。**
