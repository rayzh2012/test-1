#!/usr/bin/env python3
import argparse, json, re
from collections import defaultdict

SCHEMA = "fangame.narrative.inference.v0.4"

TASK_EXPLICIT_RE = re.compile(r"(接受任务|接受任務|任务完成|任務完成|支线任务|支線任務)")
REQUEST_RE = re.compile(r"(帮我|幫我|希望你|拜托|拜託|请你|請你|有事找你|去.{0,12}(找|寻找|尋找|消灭|消滅|打败|打敗|救出|救|收集|取得))")
COMPLETE_RE = re.compile(r"(任务完成|任務完成|谢谢你|謝謝你|感谢你|感謝你|很高兴你能|很高興你能|果然|成功)")
REWARD_RE = re.compile(r"(奖励|獎勵|报酬|報酬|得到|送给你|送給你|金钱|金錢|金币|金幣|经验|經驗|宠物蛋|寵物蛋|法器)")
MAINLINE_RE = re.compile(r"(救出国王|救國王|国王|國王|魔王|保卫.*大陆|保衛.*大陸|铲除邪恶|剷除邪惡|下一.{0,8}(镇|鎮|城)|救国|救國)")
CONTENT_ENDPOINT_RE = re.compile(r"(游戏.{0,12}(还没有结束|還沒有結束)|未完待续|未完待續|TO\s*BE\s*CONTINUED|之后.{0,12}继续更新|之後.{0,12}繼續更新|寒假.{0,12}(继续|繼續)更新)", re.I)
ENDING_RE = re.compile(r"(\bTHE\s*END\b|\bENDING\b|结局|結局|通关|通關|完结|完結|製作人員|制作人员|感谢.{0,8}游玩|感謝.{0,8}遊玩)", re.I)


def load(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def event_key(row):
    if row.get("scope") != "map":
        return None
    return (row.get("map_id"), row.get("event_id"))


def event_text(rows):
    return " ".join((r.get("text") or "").replace("\n", " ").strip() for r in rows if r.get("text"))


def switch_conditions(rows):
    out = set()
    for r in rows:
        c = r.get("conditions") or {}
        for k in ("switch1_id", "switch2_id"):
            if c.get(k) not in (None, 0, "0"):
                out.add(str(c[k]))
    return sorted(out, key=lambda x: int(x) if str(x).isdigit() else str(x))


def self_switch_conditions(rows):
    vals = set()
    for r in rows:
        c = r.get("conditions") or {}
        if c.get("self_switch_ch"):
            vals.add(str(c["self_switch_ch"]))
    return sorted(vals)


def compact_writer(e):
    return {k: e.get(k) for k in ("map_id", "event_id", "page_id", "command_index", "value") if e.get(k) is not None}


def infer(dialogue, map_graph):
    rows = dialogue.get("rows") or []
    sr = map_graph.get("switch_reads") or {}
    sw = map_graph.get("switch_writes") or {}

    groups = defaultdict(list)
    for r in rows:
        k = event_key(r)
        if k and all(v is not None for v in k):
            groups[k].append(r)

    sidequests = []
    mainline = []
    generic = []
    for (mid, eid), erows in sorted(groups.items()):
        text = event_text(erows)
        if not text:
            continue
        pages = sorted({r.get("page_id") for r in erows if r.get("page_id") is not None})
        cond_switches = switch_conditions(erows)
        self_switches = self_switch_conditions(erows)

        external_completion = {}
        for sid in cond_switches:
            ext = [w for w in sw.get(sid, []) if (w.get("map_id"), w.get("event_id")) != (mid, eid)]
            if ext:
                external_completion[sid] = [compact_writer(w) for w in ext]

        activation = {}
        for sid, writers in sw.items():
            if any((w.get("map_id"), w.get("event_id")) == (mid, eid) for w in writers):
                readers = [r for r in sr.get(str(sid), []) if (r.get("map_id"), r.get("event_id")) != (mid, eid)]
                if readers:
                    activation[str(sid)] = [
                        {k: r.get(k) for k in ("map_id", "event_id", "page_id", "source") if r.get(k) is not None}
                        for r in readers
                    ]

        has_explicit = bool(TASK_EXPLICIT_RE.search(text))
        has_request = bool(REQUEST_RE.search(text))
        has_complete = bool(COMPLETE_RE.search(text))
        has_reward = bool(REWARD_RE.search(text))
        has_mainline = bool(MAINLINE_RE.search(text))
        state_driven = bool(external_completion)
        multi_page = len(pages) >= 3

        score = ((4 if has_explicit else 0) + (1 if has_request else 0) +
                 (1 if has_complete else 0) + (1 if has_reward else 0) +
                 (1 if state_driven else 0) + (1 if multi_page else 0))
        if score < 4:
            continue

        ev = {
            "map_id": mid,
            "event_id": eid,
            "pages": pages,
            "signals": {
                "explicit_task_wording": has_explicit,
                "request_language": has_request,
                "completion_language": has_complete,
                "reward_language": has_reward,
                "mainline_language": has_mainline,
                "multi_page_event": multi_page,
                "external_completion_switch": state_driven,
            },
            "state_evidence": {
                "self_switch_conditions": self_switches,
                "completion_switches": external_completion,
                "activation_switches": activation,
            },
            "evidence_text": text[:1200],
            "score": score,
        }

        if has_explicit and has_complete and has_reward and state_driven:
            ev["classification"] = "SIDEQUEST_EXPLICIT"
            ev["confidence"] = "HIGH"
            sidequests.append(ev)
        elif has_mainline and has_request and (state_driven or multi_page):
            ev["classification"] = "MAINLINE_GATE_CANDIDATE"
            ev["confidence"] = "MEDIUM"
            mainline.append(ev)
        elif has_request and has_reward and (state_driven or multi_page):
            ev["classification"] = "QUEST_ARC_CANDIDATE"
            ev["confidence"] = "LOW"
            generic.append(ev)

    content_endpoints = []
    endings = []
    for r in rows:
        text = (r.get("text") or "").strip()
        if not text:
            continue
        if CONTENT_ENDPOINT_RE.search(text):
            content_endpoints.append({
                "scope": r.get("scope"),
                "map_id": r.get("map_id"),
                "event_id": r.get("event_id"),
                "page_id": r.get("page_id"),
                "classification": "CONTENT_ENDPOINT_UNFINISHED_RELEASE",
                "confidence": "HIGH",
                "text": text[:700],
            })
        elif ENDING_RE.search(text):
            endings.append({
                "scope": r.get("scope"),
                "map_id": r.get("map_id"),
                "event_id": r.get("event_id"),
                "page_id": r.get("page_id"),
                "classification": "ENDING_TEXT_SIGNAL",
                "confidence": "MEDIUM",
                "text": text[:700],
            })

    def dedupe(items):
        seen, out = set(), []
        for x in items:
            key = (x.get("map_id"), x.get("event_id"), x.get("page_id"), x.get("text"))
            if key not in seen:
                seen.add(key)
                out.append(x)
        return out

    content_endpoints = dedupe(content_endpoints)
    endings = dedupe(endings)
    if content_endpoints and not endings:
        completion_status = "UNFINISHED_CONTENT_ENDPOINT"
    elif endings:
        completion_status = "ENDING_SIGNAL_PRESENT"
    else:
        completion_status = "UNKNOWN"

    return {
        "schema": SCHEMA,
        "summary": {
            "explicit_sidequests": len(sidequests),
            "mainline_gate_candidates": len(mainline),
            "generic_quest_arc_candidates": len(generic),
            "content_endpoints": len(content_endpoints),
            "ending_text_signals": len(endings),
            "release_completion_status": completion_status,
        },
        "sidequests": sidequests,
        "mainline_gate_candidates": mainline,
        "generic_quest_arc_candidates": generic,
        "content_endpoints": content_endpoints,
        "ending_signals": endings,
        "interpretation": [
            "INFERRED layer: candidates are derived from dialogue + event-page + switch lifecycle evidence; they are not runtime-complete quest proofs.",
            "SIDEQUEST_EXPLICIT requires explicit task wording plus completion/reward language and an externally-written completion switch.",
            "Mainline language suppresses automatic promotion of request/reward arcs to sidequests.",
            "CONTENT_ENDPOINT_UNFINISHED_RELEASE is distinct from a completed ending.",
        ],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dialogue", required=True)
    ap.add_argument("--map-graph", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = infer(load(a.dialogue), load(a.map_graph))
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(json.dumps(out["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
