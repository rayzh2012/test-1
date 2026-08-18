import importlib.util
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('runner',ROOT/'tools/fangame_genome_runner.py')
runner=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(runner)

def test_encrypted_without_exposed_data_is_opaque():
    assert runner.is_opaque_encrypted({'encrypted_game_archive':True,'data_file_count':0})

def test_unencrypted_zero_data_is_not_encrypted_opaque():
    assert not runner.is_opaque_encrypted({'encrypted_game_archive':False,'data_file_count':0})

def test_encrypted_with_exposed_data_can_continue_inspectable_path():
    assert not runner.is_opaque_encrypted({'encrypted_game_archive':True,'data_file_count':4})
