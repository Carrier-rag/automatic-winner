#!/usr/bin/env python3
"""把特效镜头参数渲染成标准分镜卡 Markdown，并在渲染前做结构校验。

用法:
    python render_shot_card.py shot.json
    python render_shot_card.py shot.json --out card.md
    python render_shot_card.py shots.json --check-only
    cat shot.json | python render_shot_card.py -

输入 JSON 结构:
{
  "title": "掌心雷",
  "category": "能量系",
  "duration": 5.0,
  "aspect": "16:9",
  "logline": "一句话概括",
  "first_frame": "首帧提示词全文",
  "video": {
    "camera": "固定机位，50mm，浅景深，主体占画面高度二分之一",
    "timeline": [
      {"t": "0.0-0.8s", "beat": "起势", "desc": "..."},
      {"t": "0.8-2.2s", "beat": "爆发", "desc": "..."},
      {"t": "2.2-3.0s", "beat": "顶点", "desc": "..."},
      {"t": "3.0-5.0s", "beat": "余韵", "desc": "..."}
    ],
    "move": "全程固定，不推不摇",
    "light": "唯一光源是掌心光核，墙面光斑必须同步跳动",
    "forbid": ["出现人脸", "镜头抖动", "特效形态变成烟雾"]
  },
  "notes": "为什么这样写"
}

也接受批量: {"shots": [ {上述结构}, ... ]}
"""

import argparse
import json
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ABSTRACT_WORDS = [
    "震撼", "炫酷", "史诗", "绚丽", "极致", "大片感", "超高清",
    "8K", "电影级大片", "炸裂", "酷炫", "唯美", "惊艳",
]
SCALE_HINTS = [
    "米", "厘米", "毫米", "身高", "一人高", "参照", "栏杆",
    "地砖", "拳头", "巴掌", "手掌大小", "车",
]
FEEDBACK_HINTS = [
    "照亮", "投出", "投影", "阴影", "光斑", "吹动", "掀起", "震落",
    "灰尘", "粉尘", "反射", "倒影", "焦痕", "扭曲", "折射", "晃动",
]
MOVE_WORDS = ["推", "拉", "摇", "横移", "环绕", "手持", "跟拍"]

REQUIRED = ["title", "category", "duration", "first_frame"]
REQUIRED_VIDEO = ["camera", "timeline", "move", "light"]

TIME_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*[-–~]\s*(\d+(?:\.\d+)?)\s*s?\s*$")


def parse_range(text):
    m = TIME_RE.match(str(text))
    if not m:
        return None
    return float(m.group(1)), float(m.group(2))


def validate(shot):
    errors, warns = [], []
    title = shot.get("title", "<未命名>")

    for key in REQUIRED:
        if not shot.get(key):
            errors.append(f"缺少字段 {key}")
    for key in REQUIRED_VIDEO:
        if not shot.get("video", {}).get(key):
            errors.append(f"缺少字段 video.{key}")

    duration = shot.get("duration")
    if isinstance(duration, (int, float)):
        if duration > 8:
            errors.append(f"时长 {duration}s 超过 8 秒，必须拆成两段")
        if duration <= 0:
            errors.append("时长必须为正数")
    else:
        errors.append("duration 必须是数字")

    first_frame = shot.get("first_frame", "") or ""
    n = len(first_frame)
    if n and n < 60:
        warns.append(f"首帧提示词仅 {n} 字，信息量可能不足（建议 80–160 字）")
    if n > 220:
        warns.append(f"首帧提示词 {n} 字，超过 220 字模型容易丢条件")

    video = shot.get("video", {}) or {}
    timeline = video.get("timeline") or []
    if len(timeline) < 4:
        errors.append(f"时间轴只有 {len(timeline)} 个节拍，至少需要 4 个（起势/爆发/顶点/余韵）")

    prev_end = 0.0
    for i, seg in enumerate(timeline, 1):
        rng = parse_range(seg.get("t", ""))
        if rng is None:
            errors.append(f"第 {i} 个节拍时间格式无法解析: {seg.get('t')!r}（应为 0.0-0.8s）")
            continue
        start, end = rng
        if end <= start:
            errors.append(f"第 {i} 个节拍 {seg.get('t')} 结束时间不大于开始时间")
        elif end - start < 0.3:
            warns.append(
                f"第 {i} 个节拍仅 {end - start:.2f}s，短于 0.3s 模型难以呈现，建议合并或延长"
            )
        if abs(start - prev_end) > 0.011:
            warns.append(f"第 {i} 个节拍从 {start}s 开始，与上一节拍结束于 {prev_end}s 不连续")
        prev_end = end
        if not seg.get("beat"):
            warns.append(f"第 {i} 个节拍缺少 beat 名称")
        desc = seg.get("desc", "") or ""
        if len(desc) < 6:
            warns.append(f"第 {i} 个节拍描述过短，可能无法驱动变化")

    if isinstance(duration, (int, float)) and timeline and abs(prev_end - duration) > 0.011:
        warns.append(f"时间轴结束于 {prev_end}s，与设定时长 {duration}s 不一致")

    beats = " ".join((s.get("beat", "") or "") for s in timeline)
    for need in ("起势", "余韵"):
        if need not in beats:
            warns.append(f"时间轴缺少「{need}」节拍，微弧线不完整")

    move = video.get("move", "") or ""
    active = [w for w in MOVE_WORDS if re.search(rf"(?<![不无没未]){w}", move)]
    if len(active) >= 2:
        warns.append(f"运镜同时出现多种主动运动 {active}，模型难以执行，建议只保留一种")

    light = video.get("light", "") or ""
    if "同步" not in light:
        warns.append("【光照】未声明同步关系，特效亮度变化时环境光斑容易闪烁")

    forbid = video.get("forbid") or []
    if len(forbid) < 3:
        warns.append(f"禁止项只有 {len(forbid)} 条，建议 3–5 条具体约束")
    if len(forbid) > 5:
        warns.append(f"禁止项 {len(forbid)} 条，过多会削弱正向描述")

    blob = " ".join([
        first_frame,
        " ".join((s.get("desc", "") or "") for s in timeline),
    ])
    hits = [w for w in ABSTRACT_WORDS if w in blob]
    if hits:
        warns.append(f"出现抽象形容词 {hits}，请改写为可见的物理描述")

    if first_frame and not any(h in first_frame for h in SCALE_HINTS):
        warns.append("首帧缺少尺度参照物（人/手/栏杆/地砖等），模型无法判断特效大小")
    if first_frame and not any(h in first_frame for h in FEEDBACK_HINTS):
        warns.append("首帧缺少环境反馈（照亮/投影/扰动），特效容易变成贴纸")

    return title, errors, warns


def render_one(shot, index=None):
    video = shot.get("video", {}) or {}
    duration = shot.get("duration", "")
    aspect = shot.get("aspect", "16:9")
    heading = "## " + (f"{index}. " if index else "") + shot.get("title", "未命名")
    lines = [heading, ""]

    meta = [f"**类型** {shot.get('category', '')}", f"**时长** {duration}s", f"**画幅** {aspect}"]
    if shot.get("logline"):
        meta.insert(0, f"**一句话** {shot['logline']}")
    lines.append(" ｜ ".join(meta))
    lines.append("")

    lines.append("### 冻结关键帧（首帧）")
    lines.append("")
    lines.append("```text")
    lines.append(shot.get("first_frame", ""))
    lines.append("```")
    lines.append("")

    lines.append("### 视频提示词")
    lines.append("")
    lines.append("```text")
    lines.append(f"【镜头】{video.get('camera', '')}")
    lines.append("【时间轴】")
    for seg in video.get("timeline") or []:
        lines.append(f"{seg.get('t', '')}｜{seg.get('beat', '')}：{seg.get('desc', '')}")
    lines.append(f"【运镜】{video.get('move', '')}")
    lines.append(f"【光照】{video.get('light', '')}")
    forbid = video.get("forbid") or []
    lines.append("【禁止】" + "；".join(forbid) + ("。" if forbid else ""))
    lines.append("```")
    lines.append("")

    if shot.get("notes"):
        lines.append("### 设计说明")
        lines.append("")
        lines.append(shot["notes"])
        lines.append("")

    return "\n".join(lines)


def render(payload, check_only=False, as_json=False):
    shots = payload["shots"] if isinstance(payload, dict) and "shots" in payload else [payload]
    if not isinstance(shots, list) or not shots:
        print("错误: 输入必须是镜头对象或 {\"shots\": [...]}", file=sys.stderr)
        return 2

    all_ok = True
    report = []
    for i, shot in enumerate(shots, 1):
        title, errors, warns = validate(shot)
        tag = f"[{i}] {title}"
        if errors:
            all_ok = False
            print(f"✗ {tag}", file=sys.stderr)
            for e in errors:
                print(f"    错误: {e}", file=sys.stderr)
        else:
            print(f"✓ {tag}", file=sys.stderr)
        for w in warns:
            print(f"    提醒: {w}", file=sys.stderr)
        report.append({"index": i, "title": title, "errors": errors, "warnings": warns})

    if as_json:
        print(json.dumps({"ok": all_ok, "shots": report}, ensure_ascii=False, indent=2))
        return 0 if all_ok else 1

    if not all_ok:
        print("\n校验未通过，未输出分镜卡。", file=sys.stderr)
        return 1
    if check_only:
        print("\n校验通过。", file=sys.stderr)
        return 0

    out = ["# 特效镜头卡", ""]
    if len(shots) > 1:
        out.append("| # | 镜头 | 类型 | 时长 | 一句话 |")
        out.append("|---|---|---|---|---|")
        for i, shot in enumerate(shots, 1):
            out.append(
                f"| {i} | {shot.get('title', '')} | {shot.get('category', '')} "
                f"| {shot.get('duration', '')}s | {shot.get('logline', '')} |"
            )
        out.append("")
        out.append("---")
        out.append("")

    for i, shot in enumerate(shots, 1):
        out.append(render_one(shot, i if len(shots) > 1 else None))
        if i < len(shots):
            out.append("---")
            out.append("")

    return "\n".join(out).rstrip() + "\n"


def main():
    ap = argparse.ArgumentParser(description="渲染特效镜头分镜卡")
    ap.add_argument("source", help="JSON 文件路径，或 - 表示从标准输入读取")
    ap.add_argument("--out", help="输出 Markdown 路径，默认打印到标准输出")
    ap.add_argument("--check-only", action="store_true", help="只校验，不输出分镜卡")
    ap.add_argument("--json", dest="as_json", action="store_true",
                    help="以 JSON 输出校验报告（ok / shots[].errors / shots[].warnings）")
    args = ap.parse_args()

    try:
        if args.source == "-":
            payload = json.load(sys.stdin)
        else:
            with open(args.source, "r", encoding="utf-8") as f:
                payload = json.load(f)
    except FileNotFoundError:
        print(f"错误: 找不到文件 {args.source}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as e:
        print(f"错误: JSON 解析失败 — {e}", file=sys.stderr)
        return 2

    result = render(payload, check_only=args.check_only, as_json=args.as_json)
    if isinstance(result, int):
        return result

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(result)
        print(f"\n已写入 {args.out}", file=sys.stderr)
    else:
        print(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
