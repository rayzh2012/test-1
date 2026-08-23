#!/usr/bin/env python3
import argparse
import json
import shutil
import time
from collections import Counter
from pathlib import Path

from playwright.sync_api import sync_playwright

STATE_JS = r'''() => {
  const out = {};
  try { out.scene = (window.SceneManager && SceneManager._scene && SceneManager._scene.constructor) ? SceneManager._scene.constructor.name : null; } catch(e) { out.scene_error=String(e); }
  try { out.map_id = window.$gameMap ? $gameMap.mapId() : null; } catch(e) { out.map_error=String(e); }
  try {
    out.player = window.$gamePlayer ? {
      x:$gamePlayer.x, y:$gamePlayer.y, direction:$gamePlayer.direction(),
      moving:$gamePlayer.isMoving(), transparent:$gamePlayer.isTransparent(),
      passable:{
        "2":$gamePlayer.canPass($gamePlayer.x,$gamePlayer.y,2),
        "4":$gamePlayer.canPass($gamePlayer.x,$gamePlayer.y,4),
        "6":$gamePlayer.canPass($gamePlayer.x,$gamePlayer.y,6),
        "8":$gamePlayer.canPass($gamePlayer.x,$gamePlayer.y,8)
      }
    } : null;
  } catch(e) { out.player_error=String(e); }
  try { out.message_busy = window.$gameMessage ? $gameMessage.isBusy() : null; } catch(e) { out.message_error=String(e); }
  try { out.choices = window.$gameMessage && Array.isArray($gameMessage._choices) ? $gameMessage._choices.slice(0,12) : []; } catch(e) { out.choice_error=String(e); }
  try { out.event_running = window.$gameMap && $gameMap._interpreter ? $gameMap._interpreter.isRunning() : null; } catch(e) { out.event_error=String(e); }
  try { out.in_battle = window.$gameParty ? $gameParty.inBattle() : null; } catch(e) { out.battle_error=String(e); }
  try {
    out.party = window.$gameParty ? $gameParty.members().map(a => ({
      id:a.actorId(), hp:a.hp, mhp:a.mhp, mp:a.mp, mmp:a.mmp, dead:a.isDead()
    })) : [];
  } catch(e) { out.party_error=String(e); }
  return out;
}'''

KEY_FOR_DIR = {2: "ArrowDown", 4: "ArrowLeft", 6: "ArrowRight", 8: "ArrowUp"}
DELTA_FOR_DIR = {2: (0, 1), 4: (-1, 0), 6: (1, 0), 8: (0, -1)}


def snap_state(page):
    try:
        return page.evaluate(STATE_JS)
    except Exception as exc:
        return {"eval_error": repr(exc)}


def signature(state):
    p = state.get("player") or {}
    return (
        state.get("scene"),
        state.get("map_id"),
        p.get("x"),
        p.get("y"),
        state.get("message_busy"),
        state.get("event_running"),
        state.get("in_battle"),
    )


def write_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def append_jsonl(handle, record):
    handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    handle.flush()


def key_tap(page, key, hold=0.08):
    page.keyboard.down(key)
    time.sleep(hold)
    page.keyboard.up(key)


def move_one(page, direction):
    key = KEY_FOR_DIR[direction]
    page.keyboard.down(key)
    time.sleep(0.42)
    page.keyboard.up(key)
    time.sleep(0.18)
    return key


def choose_direction(state, visits, attempt_no):
    p = state.get("player") or {}
    passable = p.get("passable") or {}
    map_id, x, y = state.get("map_id"), p.get("x"), p.get("y")
    candidates = []
    for d in (6, 2, 4, 8):
        if passable.get(str(d)) is not True:
            continue
        dx, dy = DELTA_FOR_DIR[d]
        target = (map_id, x + dx, y + dy)
        candidates.append((visits[target], d))
    if not candidates:
        return None
    candidates.sort(key=lambda t: (t[0], (t[1] + attempt_no) % 11))
    return candidates[0][1]


def bootstrap_to_map(page, result, out, max_confirms):
    page.goto(result["index_uri"], wait_until="domcontentloaded", timeout=30000)
    time.sleep(12)
    page.screenshot(path=str(out / "00_title.png"))
    result["title_state"] = snap_state(page)

    key_tap(page, "Enter")
    time.sleep(2.5)
    result["after_new_game_enter"] = snap_state(page)

    stable = 0
    last_sig = None
    for i in range(max_confirms):
        st = snap_state(page)
        candidate = (
            st.get("scene") == "Scene_Map"
            and isinstance(st.get("map_id"), int)
            and st.get("map_id", 0) > 0
            and isinstance(st.get("player"), dict)
            and st.get("message_busy") is False
            and st.get("event_running") is False
        )
        sig = (st.get("map_id"), (st.get("player") or {}).get("x"), (st.get("player") or {}).get("y"))
        if candidate:
            stable = stable + 1 if sig == last_sig else 1
            last_sig = sig
            if stable >= 2:
                page.screenshot(path=str(out / "01_first_idle_map.png"))
                return {"confirm_index": i, "state": st}
        else:
            stable = 0
            last_sig = None
        key_tap(page, "Enter")
        time.sleep(0.30)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--static", required=True)
    ap.add_argument("--extract-root", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--outdir", required=True)
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    st = json.loads(Path(args.static).read_text(encoding="utf-8"))
    duration_minutes = int(cfg.get("duration_minutes", 10))
    max_minutes = int(cfg.get("max_duration_minutes", 240))
    if duration_minutes < 1 or duration_minutes > max_minutes or max_minutes > 240:
        raise SystemExit("INVALID_DURATION_GUARD")

    extract = Path(args.extract_root).resolve()
    root = (extract / st.get("game_root", ".")).resolve()
    out = Path(args.outdir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    index = next((p for p in (root / "www" / "index.html", root / "index.html") if p.exists()), None)

    result = {
        "schema": "fangame.mv_longrun_probe.v0.1",
        "mode": "PROOF_OF_POSSIBILITY",
        "game_id": cfg.get("game_id"),
        "decision_engine": cfg.get("decision_engine", "runtime_symbolic_agent_v0.1"),
        "external_ai_api": False,
        "requested_duration_minutes": duration_minutes,
        "max_duration_minutes": max_minutes,
        "engine": st.get("engine"),
        "index_html": str(index) if index else None,
        "status": "NOT_RUN",
        "battle_verified": False,
        "save_load_verified": False,
        "long_run_3h_verified": False,
        "long_run_4h_verified": False,
    }
    if not index:
        result["status"] = "NO_INDEX_HTML"
        write_json(out / "mv_longrun_summary.json", result)
        return 2

    result["index_uri"] = index.as_uri()
    trace_path = out / "mv_longrun_trace.jsonl"
    visits = Counter()
    unique_maps = set()
    unique_positions = set()
    scene_counts = Counter()
    map_transitions = 0
    coordinate_changes = 0
    actions = 0
    battle_starts = 0
    battle_completions = 0
    stalls_recovered = 0
    screenshot_no = 2
    previous = None
    battle_active = False
    fatal = None

    with trace_path.open("w", encoding="utf-8") as trace:
        try:
            with sync_playwright() as p:
                kwargs = {
                    "headless": True,
                    "args": [
                        "--allow-file-access-from-files",
                        "--autoplay-policy=no-user-gesture-required",
                        "--disable-web-security",
                        "--no-sandbox",
                        "--disable-gpu",
                    ],
                }
                chrome = shutil.which("google-chrome") or shutil.which("google-chrome-stable") or shutil.which("chromium")
                if chrome:
                    kwargs["executable_path"] = chrome
                browser = p.chromium.launch(**kwargs)
                page = browser.new_page(viewport={"width": 1280, "height": 720})
                result["console_tail"] = []
                result["page_errors"] = []
                page.on("console", lambda m: result["console_tail"].append({"type": m.type, "text": m.text[:800]}))
                page.on("pageerror", lambda e: result["page_errors"].append(str(e)[:2000]))

                first_map = bootstrap_to_map(page, result, out, int(cfg.get("max_intro_confirms", 360)))
                result["first_idle_map"] = first_map
                if not first_map:
                    result["status"] = "INTRO_NOT_CLEARED"
                    browser.close()
                    write_json(out / "mv_longrun_summary.json", result)
                    return 3

                started = time.monotonic()
                deadline = started + duration_minutes * 60
                last_progress = started
                last_periodic_shot = started
                loop_no = 0

                while time.monotonic() < deadline:
                    loop_no += 1
                    if page.is_closed():
                        fatal = "PAGE_CLOSED"
                        break
                    state = snap_state(page)
                    now = time.monotonic()
                    scene = state.get("scene")
                    scene_counts[str(scene)] += 1
                    pstate = state.get("player") or {}
                    if isinstance(state.get("map_id"), int) and state.get("map_id", 0) > 0:
                        unique_maps.add(state["map_id"])
                        if isinstance(pstate.get("x"), int) and isinstance(pstate.get("y"), int):
                            pos = (state["map_id"], pstate["x"], pstate["y"])
                            visits[pos] += 1
                            unique_positions.add(pos)

                    sig = signature(state)
                    if previous:
                        psig = signature(previous)
                        if sig != psig:
                            last_progress = now
                        if state.get("map_id") != previous.get("map_id") and state.get("map_id") is not None:
                            map_transitions += 1
                            page.screenshot(path=str(out / f"{screenshot_no:02d}_map_{state.get('map_id')}.png"))
                            screenshot_no += 1
                        pp, cp = previous.get("player") or {}, state.get("player") or {}
                        if (pp.get("x"), pp.get("y")) != (cp.get("x"), cp.get("y")) and state.get("map_id") == previous.get("map_id"):
                            coordinate_changes += 1

                    in_battle = scene == "Scene_Battle" or state.get("in_battle") is True
                    if in_battle and not battle_active:
                        battle_active = True
                        battle_starts += 1
                        page.screenshot(path=str(out / f"{screenshot_no:02d}_battle_start.png"))
                        screenshot_no += 1
                    elif battle_active and not in_battle and scene == "Scene_Map":
                        battle_active = False
                        battle_completions += 1
                        page.screenshot(path=str(out / f"{screenshot_no:02d}_battle_return_map.png"))
                        screenshot_no += 1

                    if state.get("message_busy") is True or state.get("event_running") is True:
                        action = "confirm_dialogue_or_event"
                        key_tap(page, "Enter")
                    elif in_battle:
                        action = "battle_default_confirm"
                        key_tap(page, "Enter", hold=0.10)
                    elif scene == "Scene_Map":
                        if loop_no % 9 == 0:
                            action = "interact_facing_event"
                            key_tap(page, "Enter")
                        else:
                            direction = choose_direction(state, visits, loop_no)
                            if direction is not None:
                                action = f"move_{KEY_FOR_DIR[direction]}"
                                move_one(page, direction)
                            else:
                                action = "probe_interaction_no_passable_neighbor"
                                key_tap(page, "Enter")
                    elif scene in ("Scene_Menu", "Scene_Item", "Scene_Skill", "Scene_Equip", "Scene_Status", "Scene_Options"):
                        action = "escape_nonprogress_menu"
                        key_tap(page, "Escape")
                    elif scene == "Scene_Gameover":
                        fatal = "GAME_OVER"
                        append_jsonl(trace, {"t": round(now - started, 3), "state": state, "action": "stop_game_over"})
                        break
                    else:
                        action = "generic_confirm"
                        key_tap(page, "Enter")

                    actions += 1
                    append_jsonl(trace, {"t": round(now - started, 3), "state": state, "action": action})

                    if now - last_progress >= float(cfg.get("stall_seconds", 25)):
                        stalls_recovered += 1
                        key_tap(page, "Enter")
                        key_tap(page, "Escape")
                        for d in (6, 2, 4, 8):
                            move_one(page, d)
                        last_progress = time.monotonic()
                        append_jsonl(trace, {"t": round(last_progress - started, 3), "action": "stall_recovery_sequence"})

                    if now - last_periodic_shot >= float(cfg.get("checkpoint_seconds", 120)):
                        page.screenshot(path=str(out / f"{screenshot_no:02d}_checkpoint.png"))
                        screenshot_no += 1
                        last_periodic_shot = now

                    previous = state
                    time.sleep(0.12)

                elapsed = time.monotonic() - started
                result["final_state"] = snap_state(page)
                result["page_still_open"] = not page.is_closed()
                page.screenshot(path=str(out / f"{screenshot_no:02d}_final.png"))
                browser.close()

                result.update({
                    "elapsed_play_seconds": round(elapsed, 3),
                    "actions": actions,
                    "unique_maps": sorted(unique_maps),
                    "unique_map_count": len(unique_maps),
                    "unique_position_count": len(unique_positions),
                    "map_transitions": map_transitions,
                    "coordinate_changes": coordinate_changes,
                    "battle_starts": battle_starts,
                    "battle_completions": battle_completions,
                    "stalls_recovered": stalls_recovered,
                    "scene_counts": dict(scene_counts),
                    "fatal_stop": fatal,
                    "duration_reached": elapsed >= duration_minutes * 60 * 0.98 and fatal is None,
                    "progress_observed": coordinate_changes > 0 or map_transitions > 0 or battle_completions > 0,
                    "battle_verified": battle_completions > 0,
                })
                enough_progress = len(unique_maps) >= 2 and coordinate_changes >= 40 and fatal is None
                result["long_run_3h_verified"] = elapsed >= 10800 and enough_progress
                result["long_run_4h_verified"] = elapsed >= 14400 and enough_progress
                if result["long_run_4h_verified"]:
                    result["status"] = "LONG_RUN_4H_VERIFIED"
                elif result["long_run_3h_verified"]:
                    result["status"] = "LONG_RUN_3H_VERIFIED"
                elif result["duration_reached"] and result["progress_observed"]:
                    result["status"] = "LONGRUN_PROOF_PROGRESS_OBSERVED"
                elif result["duration_reached"]:
                    result["status"] = "LONGRUN_PROOF_DURATION_ONLY"
                else:
                    result["status"] = "LONGRUN_STOPPED_EARLY"
        except Exception as exc:
            result["status"] = "LONGRUN_PROBE_ERROR"
            result["error"] = repr(exc)

    result.pop("index_uri", None)
    write_json(out / "mv_longrun_summary.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] not in ("NO_INDEX_HTML", "INTRO_NOT_CLEARED", "LONGRUN_PROBE_ERROR") else 4


if __name__ == "__main__":
    raise SystemExit(main())
