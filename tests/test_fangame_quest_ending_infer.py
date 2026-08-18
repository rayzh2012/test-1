import importlib.util
from pathlib import Path

MOD_PATH = Path(__file__).resolve().parents[1] / 'tools' / 'fangame_quest_ending_infer.py'
spec = importlib.util.spec_from_file_location('qe', MOD_PATH)
qe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qe)


def test_quest_candidate_requires_text_and_state_signal():
    mg = {
        'switch_reads': {'5':[{'map_id':2,'event_id':7}]},
        'switch_writes': {'5':[{'map_id':2,'event_id':7}]},
        'variable_reads': {}, 'variable_writes': {}
    }
    dialogue = {'rows':[{
        'scope':'map','map_id':2,'event_id':7,
        'text':'请你帮忙寻找三朵花，回来后会给你奖励。', 'conditions':{}
    }]}
    norm = {'leaf_maps':[2], 'isolated_maps':[]}
    out = qe.infer(mg, dialogue, norm)
    assert len(out['quest_candidates']) == 1
    q = out['quest_candidates'][0]
    assert q['map_id'] == 2 and q['event_id'] == 7
    assert q['state_signal_count'] >= 2
    assert out['summary']['quest_candidate_events'] == 1


def test_ending_candidate_detects_terminal_language():
    mg = {'switch_reads':{},'switch_writes':{},'variable_reads':{},'variable_writes':{}}
    dialogue = {'rows':[{
        'scope':'map','map_id':99,'event_id':1,
        'text':'全剧终。感谢您的游玩！', 'conditions':{}
    }]}
    norm = {'leaf_maps':[99], 'isolated_maps':[]}
    out = qe.infer(mg, dialogue, norm)
    assert len(out['ending_candidates']) == 1
    assert out['ending_candidates'][0]['leaf_map'] is True


def test_plain_story_dialogue_is_not_misreported_as_quest_or_ending():
    mg = {'switch_reads':{},'switch_writes':{},'variable_reads':{},'variable_writes':{}}
    dialogue = {'rows':[{
        'scope':'map','map_id':1,'event_id':1,
        'text':'我们去城里看看吧。', 'conditions':{}
    }]}
    norm = {'leaf_maps':[], 'isolated_maps':[]}
    out = qe.infer(mg, dialogue, norm)
    assert out['quest_candidates'] == []
    assert out['ending_candidates'] == []
