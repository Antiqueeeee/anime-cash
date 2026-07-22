# 01 · 软件平台

用户使用的 Web 设计平台：用户上传素材、选择风格参数，由 AI 生成纪念钞/书签/海报等产品的设计图；纪念钞可提交印刷订单邮寄实物。

## 文档

| 文档 | 定位 | 阅读说明 |
|------|------|----------|
| [raw-requirements.md](./raw-requirements.md) | 需求起源 | 用户原始想法的对话式记录。了解"为什么这么做"，不是规格 |
| [bdd-spec.md](./bdd-spec.md) | **当前产品规格** | BDD 格式的完整行为规格，开发以此为准 |
| [open-questions.md](./open-questions.md) | 待决清单 | 尚未敲定的决策事项，标注优先级和倾向 |

## 关系

```
raw-requirements.md（想法从哪来）
        ↓ 结构化
bdd-spec.md（现在做成什么样）
        ↓ 没定的部分
open-questions.md（还缺什么决策）
```

改动规格时同步检查 open-questions 中对应条目是否需要更新或关闭。

## 相关代码

- 根目录 `image_generate.py`：AI 底稿生成工具（提示词工程与出图脚本）
