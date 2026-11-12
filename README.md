# Skills

可复用的 AI 技能集合。每个技能是一个自包含目录，遵循 `SKILL.md` + `references/` + `scripts/` + `assets/` 的标准结构。

## 技能列表

| 技能 | 说明 |
|---|---|
| [`vfx-shots`](./vfx-shots) | 设计独立的创意特效镜头：能量、火焰、碎裂、变身、传送门、时间静止等，输出冻结关键帧图片提示词与分段时间轴视频提示词，含首帧验收标准、镜头组衔接规则与失败排查清单 |

版本变更见各技能目录下的 `CHANGELOG.md`。

## 使用方式

把技能目录放进对应工具的 skills 目录即可被自动加载：

| 工具 | 路径 |
|---|---|
| WorkBuddy | `~/.workbuddy/skills/` |
| Claude Code | `~/.claude/skills/` |
| CodeBuddy | `~/.codebuddy/skills/` |

```bash
git clone https://github.com/Carrier-rag/automatic-winner.git
cp -r automatic-winner/vfx-shots ~/.workbuddy/skills/
```

## 目录结构

```
<skill-name>/
├── SKILL.md          # 必需。YAML frontmatter（name / description）+ 工作流
├── references/       # 按需加载的参考资料
├── scripts/          # 确定性脚本，可直接执行
└── assets/           # 输出模板与样例输入
```
