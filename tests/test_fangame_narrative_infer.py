import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("fni", ROOT / "tools" / "fangame_narrative_infer.py")
fni = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fni)


def row(map_id, event_id, page_id, text, conditions=None):
    return {
        "scope": "map",
        "map_id": map_id,
        "event_id": event_id,
        "page_id": page_id,
        "conditions": conditions or {},
        "text": text,
    }


def test_explicit_sidequest_and_unfinished_endpoint():
    dialogue = {"rows": [
        row(8, 1, 1, "罗宾：帮我找找约翰。 接受任务 寻找约翰"),
        row(8, 1, 2, "罗宾：快去帮我找找他啊。", {"self_switch_ch": "A"}),
        row(8, 1, 3, "寻找约翰任务完成 奖励经验300 金钱1000", {"switch1_id": 6}),
        row(27, 8, 1, "怒龙：约翰，赶紧回去吧。", {"switch1_id": 5}),
        row(122, 2, 1, "作者留言：这部游戏到这里还没有结束，寒假的时候还会继续更新。"),
    ]}
    graph = {
        "switch_reads": {
            "5": [{"map_id": 27, "event_id": 8, "page_id": 1, "source": "page_condition"}],
            "6": [{"map_id": 8, "event_id": 1, "page_id": 3, "source": "page_condition"}],
        },
        "switch_writes": {
            "5": [{"map_id": 8, "event_id": 1, "page_id": 1, "command_index": 4, "value": 0}],
            "6": [{"map_id": 27, "event_id": 8, "page_id": 1, "command_index": 5, "value": 0}],
        },
    }
    out = fni.infer(dialogue, graph)
    assert out["summary"]["explicit_sidequests"] == 1
    assert out["sidequests"][0]["map_id"] == 8
    assert out["sidequests"][0]["state_evidence"]["completion_switches"]["6"][0]["map_id"] == 27
    assert out["summary"]["content_endpoints"] == 1
    assert out["summary"]["ending_text_signals"] == 0
    assert out["summary"]["release_completion_status"] == "UNFINISHED_CONTENT_ENDPOINT"


def test_mainline_request_is_not_promoted_to_sidequest():
    dialogue = {"rows": [
        row(2, 1, 1, "村长：魔王挟持了国王，希望你救出国王，打败头领后回来见我，我送你一件法器。"),
        row(2, 1, 2, "村长：赶紧去吧。", {"self_switch_ch": "A"}),
        row(2, 1, 3, "很高兴你能打败头领，得到冰凝指环。", {"switch1_id": 3}),
    ]}
    graph = {
        "switch_reads": {"3": [{"map_id": 2, "event_id": 1, "page_id": 3, "source": "page_condition"}]},
        "switch_writes": {"3": [{"map_id": 25, "event_id": 1, "page_id": 1, "command_index": 14, "value": 0}]},
    }
    out = fni.infer(dialogue, graph)
    assert out["summary"]["explicit_sidequests"] == 0
    assert out["summary"]["mainline_gate_candidates"] == 1
    assert out["mainline_gate_candidates"][0]["classification"] == "MAINLINE_GATE_CANDIDATE"


def test_strict_ending_signal_is_separate_from_generic_final_wording():
    dialogue = {"rows": [
        row(124, 2, 1, "怒龙：最终一定会让光明重现大陆的。"),
        row(130, 1, 1, "THE END"),
    ]}
    out = fni.infer(dialogue, {"switch_reads": {}, "switch_writes": {}})
    assert out["summary"]["ending_text_signals"] == 1
    assert out["ending_signals"][0]["map_id"] == 130
    assert out["summary"]["release_completion_status"] == "ENDING_SIGNAL_PRESENT"
