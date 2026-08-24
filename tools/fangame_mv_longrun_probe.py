#!/usr/bin/env python3
import argparse
import json
import shutil
import time
from collections import Counter, deque
from pathlib import Path

from playwright.sync_api import sync_playwright

STATE_JS = r'''() => {
  const out = {};
  try { out.scene = (window.SceneManager && SceneManager._scene && SceneManager._scene.constructor) ? SceneManager._scene.constructor.name : null; } catch(e) { out.scene_error=String(e); }
  try { out.map_id = window.$gameMap ? $gameMap.mapId() : null; } catch(e) { out.map_error=String(e); }
  try { out.map_size = window.$gameMap ? {width:$gameMap.width(), height:$gameMap.height()} : null; } catch(e) { out.map_size_error=String(e); }
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
  try {
    out.events = window.$gameMap ? $gameMap.events().map(e => {
      const ev = e.event ? e.event() : null;
      const page = e.page ? e.page() : null;
      const list = page && Array.isArray(page.list) ? page.list : [];
      const codes = list.map(c => c && c.code).filter(c => Number.isInteger(c));
      return {
        id:e.eventId ? e.eventId() : e._eventId,
        x:e.x, y:e.y,
        name:ev && ev.name ? ev.name : "",
        trigger:e._trigger,
        priority:e._priorityType,
        through:e.isThrough ? e.isThrough() : false,
        erased:!!e._erased,
        page_index:e._pageIndex,
        has_transfer:codes.includes(201),
        has_battle:codes.includes(301),
        has_text:codes.includes(101) || codes.includes(401),
        command_count:codes.length
      };
    }).filter(e => !e.erased && e.page_index >= 0) : [];
  } catch(e) { out.events_error=String(e); out.events=[]; }
  try { out.message_busy = window.$gameMessage ? $gameMessage.isBusy() : null; } catch(e) { out.message_error=String(e); }
  try { out.choices = window.$gameMessage && Array.isArray($gameMessage._choices) ? $gameMessage._choices.slice(0,12) : []; } catch(e) { out.choice_error=String(e); }
  try { out.event_running = window.$gameMap && $gameMap._interpreter ? $gameMap._interpreter.isRunning() : null; } catch(e) { out.event_error=String(e); }
  try { out.in_battle = window.$gameParty ? $gameParty.inBattle() : null; } catch(e) { out.battle_error=String(e); }
  try {
    out.party = window.$gameParty ? $gameParty.members().map(a => ({
      id:a.actorId(), name:a.name(), hp:a.hp, mhp:a.mhp, mp:a.mp, mmp:a.mmp, dead:a.isDead()
    })) : [];
  } catch(e) { out.party_error=String(e); }
  try {
    const s = window.SceneManager && SceneManager._scene;
    const defs = [
      ["party_command", s && s._partyCommandWindow],
      ["actor_command", s && s._actorCommandWindow],
      ["skill", s && s._skillWindow],
      ["item", s && s._itemWindow],
      ["enemy", s && s._enemyWindow],
      ["actor", s && s._actorWindow]
    ];
    const hit = defs.find(row => row[1] && row[1].active && row[1].visible);
    const kind = hit ? hit[0] : null, w = hit ? hit[1] : null;
    let entries = [];
    if (w && Array.isArray(w._list)) {
      entries = w._list.map((c,i) => ({index:i,name:c && c.name,symbol:c && c.symbol,enabled:!(c && c.enabled === false),ext:c && c.ext}));
    } else if (w && Array.isArray(w._data)) {
      entries = w._data.map((d,i) => d ? ({
        index:i,id:d.id,name:d.name,hp:d.hp,mhp:d.mhp,
        mpCost:d.mpCost || 0,scope:d.scope,
        damage_type:d.damage && d.damage.type,
        effects:Array.isArray(d.effects) ? d.effects.map(e => e && e.code).filter(Number.isInteger) : []
      }) : ({index:i}));
    } else if (kind === "enemy" && w && Array.isArray(w._enemies)) {
      entries = w._enemies.map((d,i) => ({index:i,name:d && d.name(),hp:d && d.hp,mhp:d && d.mhp}));
    }
    out.battle_ui = {
      active_window:kind,
      index:w && typeof w.index === "function" ? w.index() : null,
      entries:entries,
      actor_index:window.BattleManager ? BattleManager._actorIndex : null,
      turn_count:window.$gameTroop ? $gameTroop.turnCount() : null
    };
    out.enemies = window.$gameTroop ? $gameTroop.aliveMembers().map((e,i) => ({
      index:i,name:e.name(),hp:e.hp,mhp:e.mhp,states:e.states().map(s=>s.name)
    })) : [];
  } catch(e) { out.battle_ui_error=String(e); out.battle_ui={active_window:null,entries:[]}; }
  return out;
}'''

NAV_JS = r'''() => {
  if (!window.$gameMap) return null;
  const w=$gameMap.width(), h=$gameMap.height();
  const dirs=[2,4,6,8], opp={2:8,4:6,6:4,8:2};
  const delta={2:[0,1],4:[-1,0],6:[1,0],8:[0,-1]};
  const rows=[];
  for (let y=0;y<h;y++) {
    for (let x=0;x<w;x++) {
      let mask=0;
      for (let i=0;i<dirs.length;i++) {
        const d=dirs[i], dd=delta[d], nx=x+dd[0], ny=y+dd[1];
        if (!$gameMap.isValid(nx,ny)) continue;
        try {
          if ($gameMap.isPassable(x,y,d) && $gameMap.isPassable(nx,ny,opp[d])) mask |= (1<<i);
        } catch(e) {}
      }
      if (mask) rows.push([x,y,mask]);
    }
  }
  return {map_id:$gameMap.mapId(), width:w, height:h, rows:rows};
}'''

KEY_FOR_DIR = {2: "ArrowDown", 4: "ArrowLeft", 6: "ArrowRight", 8: "ArrowUp"}
DELTA_FOR_DIR = {2: (0, 1), 4: (-1, 0), 6: (1, 0), 8: (0, -1)}
DIRS = (2, 4, 6, 8)
OPPOSITE = {2: 8, 4: 6, 6: 4, 8: 2}


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


def choose_window_index(page, current, target):
    current = current if isinstance(current, int) and current >= 0 else 0
    target = max(0, int(target))
    for _ in range(current + 1):
        key_tap(page, "ArrowUp", hold=0.04)
    for _ in range(target):
        key_tap(page, "ArrowDown", hold=0.04)
    key_tap(page, "Enter", hold=0.08)


def battle_policy_action(page, state, retry_no, decisions):
    ui = state.get("battle_ui") or {}
    kind = ui.get("active_window")
    entries = ui.get("entries") or []
    party = [a for a in (state.get("party") or []) if not a.get("dead")]
    hp_ratio = min((a.get("hp", 0) / max(1, a.get("mhp", 1)) for a in party), default=1.0)
    heal_threshold = min(0.82, 0.42 + 0.08 * retry_no)

    def pick(predicate, score=lambda e: 0):
        choices = [e for e in entries if e.get("name") and predicate(e)]
        return max(choices, key=score) if choices else None

    if kind == "party_command":
        choice = pick(lambda e: e.get("symbol") == "fight") or (entries[0] if entries else {"index": 0})
        choose_window_index(page, ui.get("index"), choice.get("index", 0))
        action = "battle_fight"
    elif kind == "actor_command":
        symbols = {e.get("symbol"): e for e in entries if e.get("enabled", True)}
        if hp_ratio < heal_threshold and "skill" in symbols:
            choice, action = symbols["skill"], "battle_open_skill_low_hp"
        elif hp_ratio < heal_threshold and "item" in symbols:
            choice, action = symbols["item"], "battle_open_item_low_hp"
        elif hp_ratio < 0.28 and "guard" in symbols:
            choice, action = symbols["guard"], "battle_guard_critical"
        else:
            choice = symbols.get("attack") or symbols.get("skill") or (entries[0] if entries else {"index": 0})
            action = "battle_attack"
        choose_window_index(page, ui.get("index"), choice.get("index", 0))
    elif kind in ("skill", "item"):
        healing = pick(
            lambda e: e.get("damage_type") in (3, 4) or 11 in (e.get("effects") or []),
            score=lambda e: (e.get("damage_type") == 3, -(e.get("mpCost") or 0))
        )
        damaging = pick(
            lambda e: e.get("damage_type") in (1, 2, 5, 6),
            score=lambda e: -(e.get("mpCost") or 0)
        )
        choice = healing if hp_ratio < heal_threshold and healing else damaging or healing or (entries[0] if entries else {"index": 0})
        choose_window_index(page, ui.get("index"), choice.get("index", 0))
        action = f"battle_{kind}_{'heal' if choice is healing and healing else 'offense'}_{choice.get('name','unknown')}"
    elif kind == "enemy":
        choice = min(entries, key=lambda e: e.get("hp", 10**18)) if entries else {"index": 0}
        choose_window_index(page, ui.get("index"), choice.get("index", 0))
        action = f"battle_target_enemy_{choice.get('name','unknown')}"
    elif kind == "actor":
        choice = min(entries, key=lambda e: e.get("hp", 10**18) / max(1, e.get("mhp", 1))) if entries else {"index": 0}
        choose_window_index(page, ui.get("index"), choice.get("index", 0))
        action = f"battle_target_ally_{choice.get('name','unknown')}"
    else:
        key_tap(page, "Enter", hold=0.08)
        action = "battle_confirm_wait"
    decisions[action] += 1
    return action


def write_walkthrough(out, result, deaths, route_facts, decisions):
    memory = {
        "schema": "fangame.strategy_memory.v0.1",
        "game_id": result.get("game_id"),
        "evidence": "RPG_MAKER_RUNTIME_STATE_PLUS_REAL_KEY_INPUT",
        "deaths": deaths,
        "learned_policy": {
            "death_retry_count": len(deaths),
            "heal_threshold_increases_per_retry": 0.08,
            "battle_decisions": dict(decisions),
        },
        "route_facts": route_facts,
    }
    write_json(out / "mv_strategy_memory.json", memory)
    lines = [
        "# Final Redemption — observed route notes",
        "",
        "This is an evidence-derived run log, not a claim of complete coverage.",
        "",
        f"- Runtime: {result.get('elapsed_play_seconds', 0)} seconds",
        f"- Maps observed: {result.get('unique_maps', [])}",
        f"- Map transitions: {result.get('map_transitions', 0)}",
        f"- Battles started/completed: {result.get('battle_starts', 0)}/{result.get('battle_completions', 0)}",
        f"- Deaths/restarts: {result.get('death_count', 0)}/{result.get('restart_count', 0)}",
        "",
        "## Learned survival rules",
        "",
        "- Prefer healing skills/items when the weakest living party member falls below the adaptive threshold.",
        "- Raise the healing threshold after each defeat instead of repeating the same policy.",
        "- Target the lowest-HP visible enemy first; use guard only at critical HP when healing is unavailable.",
        "- Preserve each defeat snapshot and resume from a clean new-game state with the revised policy.",
        "",
        "## Observed route events",
        "",
    ]
    lines.extend(f"- t={r['t']}s: map {r['from_map']} → {r['to_map']}" for r in route_facts)
    if deaths:
        lines += ["", "## Defeat evidence", ""]
        lines.extend(f"- t={d['t']}s: defeat #{d['death_no']} on map {d.get('map_id')}; next retry healing threshold={d['next_heal_threshold']:.2f}." for d in deaths)
    (out / "mv_walkthrough.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def position_of(state):
    p = state.get("player") or {}
    if not isinstance(state.get("map_id"), int):
        return None
    if not isinstance(p.get("x"), int) or not isinstance(p.get("y"), int):
        return None
    return (state["map_id"], p["x"], p["y"])


def build_nav(nav_raw):
    if not nav_raw:
        return None
    graph = {}
    for x, y, mask in nav_raw.get("rows") or []:
        edges = []
        for i, d in enumerate(DIRS):
            if mask & (1 << i):
                dx, dy = DELTA_FOR_DIR[d]
                edges.append((x + dx, y + dy, d))
        graph[(x, y)] = edges
    return {
        "map_id": nav_raw.get("map_id"),
        "width": nav_raw.get("width"),
        "height": nav_raw.get("height"),
        "graph": graph,
    }


def bfs_first_step(nav, start_xy, goals):
    if not nav or not goals:
        return None, None
    if start_xy in goals:
        return None, 0
    graph = nav["graph"]
    q = deque([start_xy])
    prev = {start_xy: None}
    prev_dir = {}
    found = None
    while q:
        cur = q.popleft()
        for nx, ny, d in graph.get(cur, ()):
            nxt = (nx, ny)
            if nxt in prev:
                continue
            prev[nxt] = cur
            prev_dir[nxt] = d
            if nxt in goals:
                found = nxt
                q.clear()
                break
            q.append(nxt)
    if found is None:
        return None, None
    node = found
    distance = 1
    while prev[node] != start_xy:
        node = prev[node]
        distance += 1
        if node is None:
            return None, None
    return prev_dir[node], distance


def event_key(map_id, ev):
    return (map_id, ev.get("id"), ev.get("page_index"))


def adjacent_xy(x, y):
    return {d: (x + dx, y + dy) for d, (dx, dy) in DELTA_FOR_DIR.items()}


def select_event_target(state, nav, event_attempts):
    pos = position_of(state)
    if not pos or not nav:
        return None
    map_id, px, py = pos
    candidates = []
    for ev in state.get("events") or []:
        key = event_key(map_id, ev)
        attempts = event_attempts[key]
        if attempts >= (4 if ev.get("has_transfer") else 2):
            continue
        trigger = ev.get("trigger")
        if ev.get("has_transfer"):
            rank = 0
        elif ev.get("has_battle"):            rank = 1
        elif trigger in (1, 2):
            rank = 2
        elif trigger == 0 and (ev.get("has_text") or ev.get("command_count", 0) > 1):
            rank = 3
        else:
            continue
        ex, ey = ev.get("x"), ev.get("y")
        if not isinstance(ex, int) or not isinstance(ey, int):
            continue

        around = adjacent_xy(ex, ey)
        goal_into_event = {}
        for d_from_event, goal in around.items():
            if goal in nav["graph"]:
                goal_into_event[goal] = OPPOSITE[d_from_event]

        cur_xy = (px, py)
        if cur_xy in goal_into_event:
            distance = 0
            first_dir = None
        else:
            first_dir, distance = bfs_first_step(nav, cur_xy, set(goal_into_event))
            if first_dir is None:
                continue
        candidates.append((rank, distance, attempts, ev, first_dir, goal_into_event))

    if not candidates:
        return None
    candidates.sort(key=lambda row: (row[0], row[1], row[2], row[3].get("id", 0)))
    rank, distance, attempts, ev, first_dir, goal_into_event = candidates[0]
    cur_xy = (px, py)
    key = event_key(map_id, ev)
    if distance == 0:
        into_dir = goal_into_event[cur_xy]
        if ev.get("trigger") == 0:
            return {"kind": "interact_event", "event": ev, "event_key": key, "direction": into_dir}
        return {"kind": "bump_event", "event": ev, "event_key": key, "direction": into_dir}
    return {"kind": "route_to_event", "event": ev, "event_key": key, "direction": first_dir, "distance": distance}


def select_frontier_direction(state, nav, visited):
    pos = position_of(state)
    if not pos or not nav:
        return None, None
    map_id, px, py = pos
    unseen = {(x, y) for (x, y) in nav["graph"] if (map_id, x, y) not in visited}
    if not unseen:
        return None, None
    return bfs_first_step(nav, (px, py), unseen)


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
        "schema": "fangame.mv_longrun_probe.v0.3",
        "mode": "ZERO_COST_LEARNING_LONG_RUN",
        "game_id": cfg.get("game_id"),
        "decision_engine": "runtime_symbolic_agent_v0.3_adaptive_battle_retry_walkthrough",
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
    event_attempts = Counter()
    map_transitions = 0
    coordinate_changes = 0
    actions = 0
    battle_starts = 0
    battle_completions = 0
    stalls_recovered = 0
    nav_refreshes = 0
    event_route_steps = 0
    event_interactions = 0
    frontier_steps = 0
    screenshot_no = 2
    previous = None
    battle_active = False
    fatal = None
    nav_cache = {}
    death_limit = int(cfg.get("death_retry_limit", 6))
    death_count = 0
    restart_count = 0
    deaths = []
    route_facts = []
    battle_decisions = Counter()
    survival_segment_started = None
    max_survival_seconds = 0.0

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

                def on_console(m):
                    result["console_tail"].append({"type": m.type, "text": m.text[:800]})
                    if len(result["console_tail"]) > 200:
                        del result["console_tail"][:-200]

                def on_page_error(e):
                    result["page_errors"].append(str(e)[:2000])
                    if len(result["page_errors"]) > 100:
                        del result["page_errors"][:-100]

                page.on("console", on_console)
                page.on("pageerror", on_page_error)

                first_map = bootstrap_to_map(page, result, out, int(cfg.get("max_intro_confirms", 360)))
                result["first_idle_map"] = first_map
                if not first_map:
                    result["status"] = "INTRO_NOT_CLEARED"
                    browser.close()
                    write_json(out / "mv_longrun_summary.json", result)
                    return 3

                started = time.monotonic()
                survival_segment_started = started
                deadline = started + duration_minutes * 60
                last_periodic_shot = started
                last_semantic_progress = started
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
                    pos = position_of(state)
                    if pos:
                        map_id, x, y = pos
                        unique_maps.add(map_id)
                        visits[pos] += 1
                        if pos not in unique_positions:
                            last_semantic_progress = now
                        unique_positions.add(pos)
                    if previous:
                        if state.get("map_id") != previous.get("map_id") and state.get("map_id") is not None:
                            map_transitions += 1
                            route_facts.append({"t": round(now - started, 3), "from_map": previous.get("map_id"), "to_map": state.get("map_id")})
                            last_semantic_progress = now
                            page.screenshot(path=str(out / f"{screenshot_no:02d}_map_{state.get('map_id')}.png"))
                            screenshot_no += 1
                        pp, cp = previous.get("player") or {}, state.get("player") or {}
                        if (pp.get("x"), pp.get("y")) != (cp.get("x"), cp.get("y")) and state.get("map_id") == previous.get("map_id"):
                            coordinate_changes += 1

                    in_battle = scene == "Scene_Battle" or state.get("in_battle") is True
                    if in_battle and not battle_active:
                        battle_active = True
                        battle_starts += 1
                        last_semantic_progress = now
                        page.screenshot(path=str(out / f"{screenshot_no:02d}_battle_start.png"))
                        screenshot_no += 1
                    elif battle_active and not in_battle and scene == "Scene_Map":
                        battle_active = False
                        battle_completions += 1
                        last_semantic_progress = now
                        page.screenshot(path=str(out / f"{screenshot_no:02d}_battle_return_map.png"))
                        screenshot_no += 1

                    if state.get("message_busy") is True or state.get("event_running") is True:
                        action = "confirm_dialogue_or_event"
                        key_tap(page, "Enter")
                    elif in_battle:
                        action = battle_policy_action(page, state, death_count, battle_decisions)
                    elif scene == "Scene_Map" and pos:
                        map_id = pos[0]
                        if map_id not in nav_cache:
                            nav_cache[map_id] = build_nav(page.evaluate(NAV_JS))
                            nav_refreshes += 1
                            append_jsonl(trace, {
                                "t": round(now - started, 3),
                                "action": "build_nav_graph",
                                "map_id": map_id,
                                "nav_nodes": len((nav_cache[map_id] or {}).get("graph", {})),
                            })
                        nav = nav_cache.get(map_id)
                        target = select_event_target(state, nav, event_attempts)
                        if target:
                            d = target["direction"]
                            if target["kind"] == "route_to_event":
                                action = f"route_event_{target['event'].get('id')}_{KEY_FOR_DIR[d]}"
                                move_one(page, d)
                                event_route_steps += 1
                            elif target["kind"] == "bump_event":
                                action = f"bump_event_{target['event'].get('id')}_{KEY_FOR_DIR[d]}"
                                event_attempts[target["event_key"]] += 1
                                move_one(page, d)
                                event_interactions += 1
                            else:
                                action = f"interact_event_{target['event'].get('id')}_{KEY_FOR_DIR[d]}"
                                event_attempts[target["event_key"]] += 1
                                key_tap(page, KEY_FOR_DIR[d], hold=0.06)
                                time.sleep(0.08)
                                key_tap(page, "Enter")
                                event_interactions += 1
                        else:
                            direction, distance = select_frontier_direction(state, nav, unique_positions)
                            if direction is not None:
                                action = f"frontier_{KEY_FOR_DIR[direction]}_d{distance}"
                                move_one(page, direction)
                                frontier_steps += 1
                            else:
                                action = "frontier_exhausted_probe"
                                key_tap(page, "Enter")
                                d = DIRS[loop_no % len(DIRS)]
                                move_one(page, d)
                    elif scene in ("Scene_Menu", "Scene_Item", "Scene_Skill", "Scene_Equip", "Scene_Status", "Scene_Options"):
                        action = "escape_nonprogress_menu"
                        key_tap(page, "Escape")
                    elif scene == "Scene_Gameover":
                        death_count += 1
                        segment = now - survival_segment_started
                        max_survival_seconds = max(max_survival_seconds, segment)
                        death = {
                            "death_no": death_count,
                            "t": round(now - started, 3),
                            "segment_survival_seconds": round(segment, 3),
                            "map_id": state.get("map_id"),
                            "party": state.get("party") or [],
                            "next_heal_threshold": min(0.82, 0.42 + 0.08 * death_count),
                        }
                        deaths.append(death)
                        page.screenshot(path=str(out / f"{screenshot_no:02d}_gameover_{death_count}.png"))
                        screenshot_no += 1
                        append_jsonl(trace, {"t": round(now - started, 3), "state": state, "action": "learn_from_game_over", "memory": death})
                        if death_count > death_limit:
                            fatal = "GAME_OVER_RETRY_LIMIT"
                            break
                        restarted = bootstrap_to_map(page, result, out, int(cfg.get("max_intro_confirms", 360)))
                        if not restarted:
                            fatal = "RESTART_INTRO_NOT_CLEARED"
                            break
                        restart_count += 1
                        survival_segment_started = time.monotonic()
                        previous = None
                        battle_active = False
                        nav_cache = {}
                        event_attempts.clear()
                        last_semantic_progress = survival_segment_started
                        append_jsonl(trace, {"t": round(survival_segment_started - started, 3), "action": "restart_with_learned_policy", "retry": restart_count})
                        continue
                    else:
                        action = "generic_confirm"
                        key_tap(page, "Enter")

                    actions += 1
                    append_jsonl(trace, {"t": round(now - started, 3), "state": state, "action": action})

                    if now - last_semantic_progress >= float(cfg.get("stall_seconds", 25)):
                        stalls_recovered += 1
                        key_tap(page, "Enter")
                        key_tap(page, "Escape")
                        for d in (6, 2, 4, 8):
                            move_one(page, d)
                        last_semantic_progress = time.monotonic()
                        append_jsonl(trace, {"t": round(last_semantic_progress - started, 3), "action": "semantic_stall_recovery_sequence"})

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

                route_progress = map_transitions > 0 or battle_completions > 0 or len(unique_positions) >= 25
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
                    "nav_refreshes": nav_refreshes,
                    "event_route_steps": event_route_steps,
                    "event_interactions": event_interactions,
                    "frontier_steps": frontier_steps,
                    "scene_counts": dict(scene_counts),
                    "fatal_stop": fatal,
                    "duration_reached": elapsed >= duration_minutes * 60 * 0.98 and fatal is None,
                    "progress_observed": coordinate_changes > 0 or map_transitions > 0 or battle_completions > 0,
                    "route_progress_verified": route_progress and fatal is None,
                    "local_motion_only": coordinate_changes > 0 and len(unique_positions) < 10 and map_transitions == 0 and battle_completions == 0,
                    "battle_verified": battle_completions > 0,
                    "death_count": death_count,
                    "restart_count": restart_count,
                    "death_retry_limit": death_limit,
                    "max_survival_segment_seconds": round(max(max_survival_seconds, time.monotonic() - survival_segment_started), 3),
                    "strategy_memory_file": "mv_strategy_memory.json",
                    "walkthrough_file": "mv_walkthrough.md",
                    "battle_decision_counts": dict(battle_decisions),
                })
                enough_progress = len(unique_maps) >= 2 and coordinate_changes >= 40 and fatal is None
                result["long_run_3h_verified"] = elapsed >= 10800 and enough_progress
                result["long_run_4h_verified"] = elapsed >= 14400 and enough_progress
                if result["long_run_4h_verified"]:
                    result["status"] = "LONG_RUN_4H_VERIFIED"
                elif result["long_run_3h_verified"]:
                    result["status"] = "LONG_RUN_3H_VERIFIED"
                elif result["duration_reached"] and result["route_progress_verified"]:
                    result["status"] = "LONGRUN_PROOF_PROGRESS_OBSERVED"
                    result["progress_quality"] = "ROUTE_PROGRESS"
                elif result["duration_reached"] and result["progress_observed"]:
                    result["status"] = "LONGRUN_PROOF_PROGRESS_OBSERVED"
                    result["progress_quality"] = "LOCAL_MOTION_ONLY"
                elif fatal:
                    result["status"] = f"LONGRUN_STOPPED_{fatal}"
                else:
                    result["status"] = "LONGRUN_NO_MEANINGFUL_PROGRESS"

        except Exception as exc:
            result["status"] = "LONGRUN_PROBE_ERROR"
            result["fatal_stop"] = repr(exc)

    write_walkthrough(out, result, deaths, route_facts, battle_decisions)
    write_json(out / "mv_longrun_summary.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") in {
        "LONGRUN_PROOF_PROGRESS_OBSERVED",
        "LONG_RUN_3H_VERIFIED",
        "LONG_RUN_4H_VERIFIED",
    } else 4


if __name__ == "__main__":
    raise SystemExit(main())