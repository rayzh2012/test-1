#!/usr/bin/env python3
import argparse, json, math
from pathlib import Path


def clamp(x,a=0,b=5): return max(a,min(b,x))
def log_score(v, low, high):
    if v <= 0: return 0.0
    if v <= low: return 1.0 + 1.5*(v/low)
    if v >= high: return 5.0
    return 2.5 + 2.5*math.log(v/low)/math.log(high/low)

def smoke_score(status):
    return {
        'INPUT_FLOW_VERIFIED':4.5,
        'POST_CONFIRM_RESPONSE_VERIFIED':4.2,
        'BOOT_VERIFIED':4.0,
        'BOOT_VERIFIED_THEN_EXITED':3.0,
        'PROCESS_ALIVE_NO_VISIBLE_WINDOW':2.5,
        'NO_CURRENT_RUNTIME_PATH_IN_CI':2.0,
        'CI_RUNTIME_SETUP_FAILED':2.0,
        'CI_AUDIO_SETUP_FAILED':2.0,
        'BOOT_FAILED':1.5,
        'SMOKE_ERROR':1.5,
    }.get(status,2.0)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--static',required=True); ap.add_argument('--smoke',required=False); ap.add_argument('--target',required=False); ap.add_argument('--out-json',default='fangame_review_card.json'); ap.add_argument('--out-md',default='fangame_review_card.md'); a=ap.parse_args()
    st=json.loads(Path(a.static).read_text(encoding='utf-8')); sm={}; target={}
    if a.smoke and Path(a.smoke).exists(): sm=json.loads(Path(a.smoke).read_text(encoding='utf-8'))
    if a.target and Path(a.target).exists(): target=json.loads(Path(a.target).read_text(encoding='utf-8'))
    mc=st.get('marshal_content') or {}
    maps=mc.get('maps_loaded',st.get('map_count',0)) or 0; events=mc.get('event_commands',0) or 0; dialogue=mc.get('dialogue_lines',0) or 0; choices=mc.get('choice_options',0) or 0; commons=mc.get('common_events',0) or 0; skills=mc.get('skills',0) or 0; items=mc.get('items',0) or 0; enemies=mc.get('enemies',0) or 0; transfers=mc.get('map_transfers',0) or 0; shops=mc.get('shop_calls',0) or 0
    narrative=clamp(0.55*log_score(dialogue,150,5000)+0.25*log_score(events,800,18000)+0.20*log_score(maps,25,350))
    system=clamp(0.30*log_score(skills,25,180)+0.25*log_score(items,30,250)+0.20*log_score(enemies,20,140)+0.15*log_score(commons,10,180)+0.10*log_score(shops,3,35))
    agency=clamp(0.55*log_score(choices,10,500)+0.25*log_score(transfers,30,700)+0.20*log_score(maps,25,350))
    content=clamp(0.40*narrative+0.35*system+0.25*agency)
    play=smoke_score(sm.get('status')) if sm else (2.5 if st.get('playability_structural')=='STRUCTURAL_OK' else 1.0)
    ai_interest=clamp(0.70*content+0.30*play)
    hist=target.get('historical_reputation') or {}; hist_rating=hist.get('rating_5'); hist_votes=hist.get('votes'); hist_downloads=hist.get('downloads'); hist_note=hist.get('summary')
    if hist_rating is None and target.get('historical_rating_10') is not None: hist_rating=float(target['historical_rating_10'])/2.0
    if hist_votes is None: hist_votes=target.get('historical_votes')
    if hist_downloads is None: hist_downloads=target.get('historical_downloads')
    status=sm.get('status','NOT_SMOKE_TESTED')
    if status=='INPUT_FLOW_VERIFIED': verdict='高优先：内容规模强，CI已验证窗口、确认键与后续输入链；地图实机阶段仍需截图语义复核'
    elif status=='POST_CONFIRM_RESPONSE_VERIFIED': verdict='值得玩：已验证启动且确认键产生实质响应，需截图复核是否已进入 New Game'
    elif status=='BOOT_VERIFIED': verdict='值得继续测：已验证可启动，尚未证明进入游戏流程'
    elif st.get('playability_structural')=='STRUCTURAL_OK': verdict='值得保存/继续测：结构完整，但当前运行路径未完全验证'
    else: verdict='低优先：先解决完整性或运行路径问题'
    card={
      'name':target.get('name') or target.get('title') or st.get('archive'),'engine':st.get('engine'),
      'evidence_separation':'Historical reputation, AI structural prediction, mechanical CI smoke, and semantic screenshot review are separate evidence layers. AI score is NOT a claim that the game was played through.',
      'historical_player_rating_5':hist_rating,'historical_votes':hist_votes,'historical_downloads':hist_downloads,'historical_summary':hist_note,
      'ci_playability_status':status,'ci_playability_score_5':round(play,2),'semantic_visual_review_required_for':sm.get('semantic_visual_review_required_for',['TITLE_VERIFIED','NEW_GAME_VERIFIED','MAP_GAMEPLAY_VERIFIED']),
      'content_scale':st.get('content_scale'),'metrics':{'maps':maps,'event_commands':events,'dialogue_lines':dialogue,'choice_options':choices,'common_events':commons,'skills':skills,'items':items,'enemies':enemies,'map_transfers':transfers,'shop_calls':shops},
      'ai_structural_scores_5':{'narrative_volume':round(narrative,2),'system_breadth':round(system,2),'agency_exploration':round(agency,2),'content_richness':round(content,2),'ai_interest_prediction':round(ai_interest,2)},
      'verdict':verdict,'confidence':'MEDIUM' if mc.get('maps_loaded',0)>0 else 'LOW_TO_MEDIUM'
    }
    Path(a.out_json).write_text(json.dumps(card,ensure_ascii=False,indent=2),encoding='utf-8')
    h='未收录' if hist_rating is None else f'{float(hist_rating):.1f}/5' + (f'（{hist_votes}票）' if hist_votes else '')
    md=f'''# {card['name']}｜AI Rescue Review Card\n\n- 引擎：{card['engine']}\n- 历史玩家口碑：{h}\n- CI机械可玩性：{status}（{play:.1f}/5）\n- 内容规模：{card['content_scale']}\n- AI结构预测：{ai_interest:.1f}/5（不是实机通关评分）\n- 剧情量：{narrative:.1f}/5｜系统广度：{system:.1f}/5｜选择/探索：{agency:.1f}/5\n- 地图 {maps}｜事件命令 {events}｜对话 {dialogue}｜选择项 {choices}｜公共事件 {commons}\n- 技能 {skills}｜物品 {items}｜敌人 {enemies}｜地图传送 {transfers}\n\n**结论：{verdict}**\n\n> 历史口碑、文件结构、CI机械输入和截图语义复核严格分层；只有截图/行为证据确认后才标 TITLE_VERIFIED / NEW_GAME_VERIFIED / MAP_GAMEPLAY_VERIFIED。\n'''
    if hist_note: md += f'\n历史评价摘要：{hist_note}\n'
    Path(a.out_md).write_text(md,encoding='utf-8'); print(json.dumps(card,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
