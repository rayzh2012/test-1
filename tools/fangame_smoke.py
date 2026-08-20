#!/usr/bin/env python3
import argparse, json, os, shutil, subprocess, time
from pathlib import Path


def run(cmd, env=None, cwd=None, timeout=30):
    try:
        p = subprocess.run(cmd, env=env, cwd=cwd, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, text=True, timeout=timeout)
        return p.returncode, p.stdout[-8000:]
    except Exception as e:
        return 999, repr(e)


def ensure_wine32(notes):
    if not shutil.which('wine') or not shutil.which('dpkg') or not shutil.which('sudo'):
        return False
    _, out = run(['dpkg', '--print-foreign-architectures'], timeout=10)
    if 'i386' not in out.split():
        rc, log = run(['sudo', 'dpkg', '--add-architecture', 'i386'], timeout=30)
        notes.append(f'wine32 add-architecture rc={rc}')
        if rc != 0:
            notes.append(log[-1500:]); return False
    rc, log = run(['sudo', 'apt-get', 'update'], timeout=180)
    notes.append(f'wine32 apt-update rc={rc}')
    if rc != 0:
        notes.append(log[-1500:]); return False
    pkgs = ['wine32:i386', 'libasound2-plugins:i386', 'libpulse0:i386']
    rc, log = run(['sudo', 'apt-get', 'install', '-y', *pkgs], timeout=360)
    notes.append(f'wine32/audio install rc={rc}')
    if rc != 0:
        notes.append(log[-2500:]); return False
    return True


def ensure_virtual_audio(notes):
    if not shutil.which('pulseaudio') or not shutil.which('pactl'):
        if not shutil.which('sudo'):
            return False, None
        rc, log = run(['sudo', 'apt-get', 'install', '-y', 'pulseaudio', 'pulseaudio-utils'], timeout=240)
        notes.append(f'pulseaudio install rc={rc}')
        if rc != 0:
            notes.append(log[-1500:]); return False, None
    runtime = Path('/tmp/fangame-pulse-runtime')
    runtime.mkdir(parents=True, exist_ok=True)
    try: runtime.chmod(0o700)
    except Exception: pass
    env = os.environ.copy(); env['XDG_RUNTIME_DIR'] = str(runtime)
    subprocess.run(['pulseaudio', '-k'], env=env, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL, timeout=10, check=False)
    try:
        p = subprocess.run(['pulseaudio', '--start', '--exit-idle-time=-1'], env=env,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=30, check=False)
        notes.append(f'pulseaudio start rc={p.returncode}')
    except Exception as e:
        notes.append('pulseaudio start error: ' + repr(e)); return False, None
    time.sleep(1)
    rc, info = run(['pactl', 'info'], env=env, timeout=10)
    if rc != 0:
        notes.append('pactl info failed: ' + info[-1200:]); return False, None
    rc, _ = run(['pactl', 'load-module', 'module-null-sink', 'sink_name=fangame_ci',
                 'sink_properties=device.description=FangameCI'], env=env, timeout=10)
    notes.append(f'null-sink load rc={rc}')
    rc, log = run(['pactl', 'set-default-sink', 'fangame_ci'], env=env, timeout=10)
    if rc != 0:
        notes.append('set-default-sink failed: ' + log[-1000:]); return False, None
    server = None
    for line in info.splitlines():
        if line.lower().startswith('server string:'):
            server = line.split(':', 1)[1].strip(); break
    notes.append('virtual audio ready')
    return True, {'XDG_RUNTIME_DIR': str(runtime), **({'PULSE_SERVER': server} if server else {})}


def configure_wine_audio(env, cwd, notes):
    rc, log = run(['wine', 'reg', 'add', r'HKCU\Software\Wine\Drivers', '/v', 'Audio',
                   '/t', 'REG_SZ', '/d', 'pulse', '/f'], env=env, cwd=cwd, timeout=30)
    notes.append(f'wine force-pulse rc={rc}')
    if rc != 0: notes.append(log[-1500:])
    return rc == 0


def screenshot(env, path):
    if shutil.which('scrot'):
        rc, log = run(['scrot', '-o', str(path)], env=env, timeout=10)
        return rc == 0 and path.exists(), log
    if shutil.which('import'):
        rc, log = run(['import', '-window', 'root', str(path)], env=env, timeout=10)
        return rc == 0 and path.exists(), log
    return False, 'no screenshot tool'


def diff_pixels(a, b):
    if not (a.exists() and b.exists()) or not shutil.which('compare'): return None
    p = subprocess.run(['compare', '-metric', 'AE', str(a), str(b), 'null:'],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    raw = (p.stderr or p.stdout).strip().splitlines()
    try: return int(float(raw[-1])) if raw else None
    except Exception: return None


def key(env, keyname):
    if not shutil.which('xdotool'): return False
    subprocess.run(['xdotool', 'key', '--clearmodifiers', keyname], env=env,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return True


def windows(env):
    if not shutil.which('xdotool'): return []
    p = subprocess.run(['xdotool', 'search', '--onlyvisible', '--name', '.'], env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    return [x for x in p.stdout.split() if x.strip()]


def window_titles(env, ids):
    out = []
    for wid in ids:
        p = subprocess.run(['xdotool', 'getwindowname', wid], env=env,
                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        if p.stdout.strip(): out.append(p.stdout.strip())
    return out


def choose_command(root: Path, engine: str):
    if engine == 'RPG Maker 2000/2003' and shutil.which('easyrpg-player'):
        return ['easyrpg-player', '--window'], 'EasyRPG Player'
    if engine in ('RPG Maker XP', 'RPG Maker VX', 'RPG Maker VX Ace'):
        for c in ('mkxp-z', 'mkxp'):
            if shutil.which(c): return [c], c
    exe = root / 'Game.exe'
    if not exe.exists(): exe = root / 'RPG_RT.exe'
    if exe.exists() and shutil.which('wine'):
        return ['wine', exe.name], 'Wine/original Windows launcher'
    return None, None


def generate_review(args, out):
    script = Path(__file__).with_name('fangame_review_card.py').resolve()
    if not script.exists(): return
    smoke = out / 'playability_smoke.json'
    fetch = Path(args.static).resolve().parent / 'fetch_report.json'
    cmd = ['python3', str(script), '--static', str(Path(args.static).resolve()),
           '--smoke', str(smoke), '--out-json', str(out / 'fangame_review_card.json'),
           '--out-md', str(out / 'fangame_review_card.md')]
    if fetch.exists(): cmd += ['--target', str(fetch)]
    run(cmd, timeout=30)


def write_result(args, out, result):
    (out / 'playability_smoke.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    generate_review(args, out)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def capture(env, out, name):
    path = out / name
    ok, log = screenshot(env, path)
    return path if ok else None, log


def probe_map_like_input(env, out, proc, base_frame):
    """Collect conservative map-like movement evidence without declaring semantics.

    A menu cursor can also produce a small pixel diff. To reduce that false positive,
    require local responses on both horizontal and vertical axes plus a roughly
    reversible round trip. Final MAP_GAMEPLAY_VERIFIED still requires semantic
    screenshot review outside this mechanical probe.
    """
    evidence = {
        'idle_stability_changed_pixels': None,
        'steps': [],
        'localized_step_count': 0,
        'horizontal_localized_count': 0,
        'vertical_localized_count': 0,
        'roundtrip_changed_pixels': None,
        'candidate': False,
        'candidate_reason': 'INSUFFICIENT_MAP_LIKE_BEHAVIOR',
    }
    time.sleep(2.0)
    idle, _ = capture(env, out, '21_probe_idle.png')
    if idle:
        evidence['idle_stability_changed_pixels'] = diff_pixels(base_frame, idle)
        prev = idle
    else:
        prev = base_frame

    sequence = ('Right', 'Right', 'Left', 'Left', 'Down', 'Down', 'Up', 'Up')
    for i, k in enumerate(sequence, 22):
        if proc.poll() is not None:
            evidence['candidate_reason'] = 'PROCESS_EXITED_DURING_MOVEMENT_PROBE'
            return evidence
        key(env, k); time.sleep(0.9)
        frame, _ = capture(env, out, f'{i:02d}_probe_{k.lower()}.png')
        d = diff_pixels(prev, frame) if frame else None
        local = d is not None and 40 <= d <= 60000
        evidence['steps'].append({'key': k, 'changed_pixels': d, 'localized_change': local})
        if local:
            evidence['localized_step_count'] += 1
            if k in ('Left', 'Right'): evidence['horizontal_localized_count'] += 1
            if k in ('Up', 'Down'): evidence['vertical_localized_count'] += 1
        if frame: prev = frame

    evidence['roundtrip_changed_pixels'] = diff_pixels(base_frame, prev)
    idle_delta = evidence['idle_stability_changed_pixels']
    stable = idle_delta is not None and idle_delta <= 12000
    reversible = (evidence['roundtrip_changed_pixels'] is not None and
                  evidence['roundtrip_changed_pixels'] <= 40000)
    axis_support = (evidence['horizontal_localized_count'] >= 2 and
                    evidence['vertical_localized_count'] >= 2)
    enough_steps = evidence['localized_step_count'] >= 4
    if stable and reversible and axis_support and enough_steps and proc.poll() is None and windows(env):
        evidence['candidate'] = True
        evidence['candidate_reason'] = 'STABLE_BIDIRECTIONAL_LOCALIZED_ROUNDTRIP'
    elif not stable:
        evidence['candidate_reason'] = 'SCREEN_NOT_STABLE_BEFORE_MOVEMENT'
    elif not axis_support:
        evidence['candidate_reason'] = 'NO_LOCALIZED_RESPONSE_ON_BOTH_AXES'
    elif not reversible:
        evidence['candidate_reason'] = 'INPUT_SEQUENCE_NOT_ROUGHLY_REVERSIBLE'
    return evidence


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--static', required=True)
    ap.add_argument('--extract-root', required=True)
    ap.add_argument('--outdir', default='playability_smoke')
    args = ap.parse_args()
    st = json.loads(Path(args.static).read_text(encoding='utf-8'))
    extract = Path(args.extract_root).resolve()
    game_root = (extract / st.get('game_root', '.')).resolve()
    out = Path(args.outdir).resolve(); out.mkdir(parents=True, exist_ok=True)
    result = {'engine': st.get('engine'), 'game_root': str(game_root), 'status': 'NOT_RUN',
              'runtime': None, 'process_alive_boot': False, 'visible_windows_boot': 0,
              'window_titles': [], 'boot_to_confirm_changed_pixels': None,
              'confirm_to_movement_changed_pixels': None, 'confirm_probe': [],
              'map_gameplay_candidate': False, 'map_gameplay_probe': None,
              'stage_evidence': [],
              'semantic_visual_review_required_for': ['TITLE_VERIFIED','NEW_GAME_VERIFIED','MAP_GAMEPLAY_VERIFIED'],
              'notes': []}
    cmd, runtime = choose_command(game_root, st.get('engine', 'UNKNOWN')); result['runtime'] = runtime
    if not cmd:
        result['status'] = 'NO_CURRENT_RUNTIME_PATH_IN_CI'; result['playability_class'] = 'PLAYABILITY_UNKNOWN'
        write_result(args, out, result); return 0
    audio_env = {}
    if runtime == 'Wine/original Windows launcher':
        result['wine32_ready'] = ensure_wine32(result['notes'])
        if not result['wine32_ready']:
            result['status'] = 'CI_RUNTIME_SETUP_FAILED'; result['playability_class'] = 'PLAYABILITY_UNKNOWN'
            write_result(args, out, result); return 0
        result['virtual_audio_ready'], audio_env = ensure_virtual_audio(result['notes'])
        if not result['virtual_audio_ready']:
            result['status'] = 'CI_AUDIO_SETUP_FAILED'; result['playability_class'] = 'PLAYABILITY_UNKNOWN'
            write_result(args, out, result); return 0
    display = ':99'; prefix = (extract.parent / 'wineprefix').resolve()
    if prefix.exists(): shutil.rmtree(prefix)
    env = os.environ.copy(); env.update(audio_env)
    env.update({'DISPLAY': display, 'WINEDEBUG': '-all',
                'WINEDLLOVERRIDES': 'winemenubuilder.exe=d', 'WINEPREFIX': str(prefix)})
    xvfb = proc = logf = None
    try:
        xvfb = subprocess.Popen(['Xvfb', display, '-screen', '0', '1280x720x24', '-nolisten', 'tcp'],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        logf = open(out / 'runtime.log', 'w', encoding='utf-8', errors='ignore')
        time.sleep(1.5)
        if runtime == 'Wine/original Windows launcher':
            rc, bootlog = run(['wineboot', '-u'], env=env, cwd=game_root, timeout=90)
            result['wineboot_rc'] = rc
            if rc != 0: result['notes'].append('wineboot failed: ' + bootlog[-1500:])
            configure_wine_audio(env, game_root, result['notes'])
            time.sleep(2)
        proc = subprocess.Popen(cmd, cwd=game_root, env=env, stdout=logf,
                                stderr=subprocess.STDOUT, text=True)
        time.sleep(12)
        alive = proc.poll() is None; wins_boot = windows(env)
        result['process_alive_boot'] = alive; result['visible_windows_boot'] = len(wins_boot)
        result['window_titles'] = window_titles(env, wins_boot)
        s1, _ = capture(env, out, '01_boot.png')
        if not alive:
            result['status'] = 'BOOT_FAILED'; result['notes'].append(f'process exited rc={proc.returncode}')
        else:
            result['status'] = 'WINDOW_VISIBLE_BOOT' if wins_boot else 'PROCESS_ALIVE_NO_VISIBLE_WINDOW'
            if wins_boot: result['stage_evidence'].append('VISIBLE_WINDOW_AT_BOOT_UNVERIFIED')

            # Preserve the original first-confirm evidence for backward comparability.
            key(env, 'Return'); time.sleep(4)
            s2, _ = capture(env, out, '02_after_confirm.png')
            d1 = diff_pixels(s1, s2) if s1 and s2 else None
            result['boot_to_confirm_changed_pixels'] = d1
            alive2 = proc.poll() is None; result['process_alive_after_confirm'] = alive2
            wins2 = windows(env); result['visible_windows_after_confirm'] = len(wins2)
            if not alive2:
                result['status'] = 'WINDOW_THEN_EXITED_AFTER_CONFIRM'
                result['notes'].append('Process exited after first confirm; startup/error dialog possible.')
            else:
                if (d1 or 0) > 1000: result['stage_evidence'].append('CONFIRM_CAUSED_LARGE_VISUAL_CHANGE')

                # Advance through title/instruction/dialogue screens while retaining every
                # frame. This is intentionally bounded; it never claims a semantic stage.
                prev = s2
                last = s2
                for n in range(2, 13):
                    if proc.poll() is not None: break
                    key(env, 'Return'); time.sleep(1.8)
                    frame, _ = capture(env, out, f'{n+1:02d}_after_confirm_{n:02d}.png')
                    d = diff_pixels(prev, frame) if prev and frame else None
                    result['confirm_probe'].append({'confirm_index': n, 'changed_pixels': d})
                    if frame:
                        prev = frame; last = frame

                result['process_alive_after_confirm_probe'] = proc.poll() is None
                result['visible_windows_after_confirm_probe'] = len(windows(env))
                if result['process_alive_after_confirm_probe'] and last:
                    result['map_gameplay_probe'] = probe_map_like_input(env, out, proc, last)
                    result['map_gameplay_candidate'] = bool(result['map_gameplay_probe']['candidate'])
                    movement_deltas = [x.get('changed_pixels') for x in result['map_gameplay_probe']['steps']
                                       if x.get('changed_pixels') is not None]
                    result['confirm_to_movement_changed_pixels'] = max(movement_deltas) if movement_deltas else None
                    if result['map_gameplay_candidate']:
                        result['stage_evidence'].append('MAP_GAMEPLAY_CANDIDATE_BEHAVIOR')
                    elif movement_deltas:
                        result['stage_evidence'].append('DIRECTIONAL_INPUT_PROBED')

                alive3 = proc.poll() is None; result['process_alive_after_inputs'] = alive3
                wins3 = windows(env); result['visible_windows_after_inputs'] = len(wins3)
                has_window = bool(wins2 or wins3)
                any_confirm_change = ((d1 or 0) > 1000 or
                                      any((x.get('changed_pixels') or 0) > 1000 for x in result['confirm_probe']))
                any_input_change = bool(result['map_gameplay_probe'] and
                                        any((x.get('changed_pixels') or 0) > 300
                                            for x in result['map_gameplay_probe']['steps']))
                if alive3 and has_window and any_confirm_change and any_input_change:
                    result['status'] = 'INPUT_FLOW_VERIFIED'
                    result['stage_evidence'].append('ARROW_INPUTS_CAUSED_VISUAL_CHANGE')
                elif alive3 and has_window and any_confirm_change:
                    result['status'] = 'POST_CONFIRM_RESPONSE_VERIFIED'
                elif alive3 and has_window:
                    result['status'] = 'WINDOW_ALIVE_AFTER_CONFIRM'
                else:
                    result['status'] = 'POST_CONFIRM_RUNTIME_UNCERTAIN'
    except Exception as e:
        result['status'] = 'SMOKE_ERROR'; result['notes'].append(repr(e))
    finally:
        if proc and proc.poll() is None:
            try: proc.terminate(); proc.wait(timeout=3)
            except Exception:
                try: proc.kill()
                except Exception: pass
        if xvfb:
            try: xvfb.terminate(); xvfb.wait(timeout=3)
            except Exception:
                try: xvfb.kill()
                except Exception: pass
        if logf:
            try: logf.close()
            except Exception: pass
    if result['status'] == 'INPUT_FLOW_VERIFIED':
        result['playability_class'] = 'PLAYABILITY_VERIFIED_INPUT_FLOW'
    elif result['status'] == 'POST_CONFIRM_RESPONSE_VERIFIED':
        result['playability_class'] = 'PLAYABILITY_VERIFIED_BOOT'
    elif result['status'] == 'WINDOW_ALIVE_AFTER_CONFIRM':
        result['playability_class'] = 'PLAYABILITY_RECOVERABLE_RUNTIME_ALIVE'
    else:
        result['playability_class'] = 'PLAYABILITY_UNKNOWN'
    write_result(args, out, result); return 0


if __name__ == '__main__':
    raise SystemExit(main())
