#!/usr/bin/env ruby
require 'json'
require 'optparse'

EVIDENCE_VERSION = 'rpgmaker.progression.v0.5a'

class Table
  def self._load(s); o=new; o.instance_variable_set(:@raw,s); o; end
end
class Color
  def self._load(s); o=new; o.instance_variable_set(:@raw,s); o; end
end
class Tone
  def self._load(s); o=new; o.instance_variable_set(:@raw,s); o; end
end
module RPG; end

def ensure_class(path)
  parts=path.split('::').reject(&:empty?)
  cur=Object
  parts.each do |name|
    if cur.const_defined?(name,false)
      cur=cur.const_get(name,false)
    else
      k=Class.new
      cur.const_set(name,k)
      cur=k
    end
  end
end

%w[
RPG::Map RPG::MapInfo RPG::Event RPG::Event::Page RPG::Event::Page::Condition RPG::Event::Page::Graphic
RPG::EventCommand RPG::MoveRoute RPG::MoveCommand RPG::AudioFile RPG::BGM RPG::BGS RPG::ME RPG::SE
RPG::System RPG::System::Words RPG::System::Terms RPG::System::Vehicle RPG::System::TestBattler
RPG::Actor RPG::Class RPG::Skill RPG::Item RPG::Weapon RPG::Armor RPG::Enemy RPG::Enemy::Action
RPG::Troop RPG::Troop::Member RPG::Troop::Page RPG::Troop::Page::Condition RPG::State RPG::Animation
RPG::Animation::Frame RPG::Animation::Timing RPG::Tileset RPG::CommonEvent RPG::BaseItem RPG::BaseItem::Feature
RPG::UsableItem RPG::UsableItem::Effect RPG::EquipItem
].each { |n| ensure_class(n) }

def mload(path)
  data=File.binread(path)
  50.times do
    begin
      return Marshal.load(data), nil
    rescue ArgumentError, NameError => e
      m=e.message.match(/undefined class\/module ([A-Za-z0-9_:]+)/)
      if m
        ensure_class(m[1]); next
      end
      return nil,"#{e.class}: #{e.message}"
    rescue => e
      return nil,"#{e.class}: #{e.message}"
    end
  end
  [nil,'too many missing class retries']
end

def iv(o,n,default=nil)
  o && o.instance_variable_defined?(n) ? o.instance_variable_get(n) : default
end

def num(v)
  return nil if v.nil? || v == true || v == false
  Float(v)
rescue
  nil
end

def quantile(sorted,q)
  return nil if sorted.empty?
  return sorted[0] if sorted.length == 1
  pos=(sorted.length-1)*q
  lo=pos.floor; hi=pos.ceil
  return sorted[lo] if lo==hi
  sorted[lo] + (sorted[hi]-sorted[lo])*(pos-lo)
end

def stats(values)
  xs=Array(values).map{|x| num(x)}.compact.select{|x| x.finite?}.sort
  return {'count'=>0,'min'=>nil,'p25'=>nil,'median'=>nil,'p75'=>nil,'max'=>nil,'mean'=>nil} if xs.empty?
  {
    'count'=>xs.length,
    'min'=>xs.first,
    'p25'=>quantile(xs,0.25),
    'median'=>quantile(xs,0.5),
    'p75'=>quantile(xs,0.75),
    'max'=>xs.last,
    'mean'=>xs.sum/xs.length.to_f
  }
end

def first_data_file(data_dir,base)
  Dir[File.join(data_dir,"#{base}.*data*")].first
end

def load_array(data_dir,base,errors)
  f=first_data_file(data_dir,base)
  return [] unless f
  obj,err=mload(f)
  unless obj
    errors << "#{File.basename(f)}: #{err}" if errors.length < 50
    return []
  end
  Array(obj).compact
end

def positive_field(rows,field)
  rows.map{|x| num(iv(x,field,nil))}.compact.select{|x| x > 0}
end

def scan_commands(list,summary)
  Array(list).each do |c|
    code=iv(c,:@code,0).to_i
    params=Array(iv(c,:@parameters,[]))
    summary['event_command_count'] += 1
    case code
    when 201 then summary['transfer_ops'] += 1
    when 301 then summary['battle_processing_ops'] += 1
    when 302 then summary['shop_processing_ops'] += 1
    when 311,312,313 then summary['hp_mp_state_change_ops'] += 1
    when 314 then summary['recover_all_ops'] += 1
    when 315 then summary['change_exp_ops'] += 1
    when 316 then summary['change_level_ops'] += 1
    when 318 then summary['change_skill_ops'] += 1
    when 125
      summary['change_gold_ops'] += 1
      op=params[0].to_i
      summary[op==0 ? 'positive_gold_reward_ops' : 'negative_gold_cost_ops'] += 1
    when 126
      summary['change_item_ops'] += 1
      op=params[1].to_i
      summary[op==0 ? 'positive_item_reward_ops' : 'negative_item_cost_ops'] += 1
    when 127
      summary['change_weapon_ops'] += 1
      op=params[1].to_i
      summary[op==0 ? 'positive_weapon_reward_ops' : 'negative_weapon_cost_ops'] += 1
    when 128
      summary['change_armor_ops'] += 1
      op=params[1].to_i
      summary[op==0 ? 'positive_armor_reward_ops' : 'negative_armor_cost_ops'] += 1
    end
  end
end

def scan_map_commands(map,summary)
  events=iv(map,:@events,{}) || {}
  events=events.values if events.respond_to?(:values)
  Array(events).compact.each do |ev|
    Array(iv(ev,:@pages,[])).compact.each do |pg|
      scan_commands(iv(pg,:@list,[]),summary)
    end
  end
end

def scan_common_events(data_dir,summary,errors)
  load_array(data_dir,'CommonEvents',errors).each do |ce|
    scan_commands(iv(ce,:@list,[]),summary)
  end
end

def map_id_from_file(path)
  m=File.basename(path).match(/Map(\d+)/i)
  m ? m[1].to_i : nil
end

opts={}
OptionParser.new{|o| o.on('--out PATH'){|v| opts[:out]=v}}.parse!
root=ARGV.shift or abort 'usage: rpgmaker_progression_probe.rb GAME_ROOT --out FILE'
data_dir=File.join(root,'Data')
abort "Data directory not found: #{data_dir}" unless Dir.exist?(data_dir)

errors=[]
command_summary={
  'event_command_count'=>0,
  'transfer_ops'=>0,'battle_processing_ops'=>0,'shop_processing_ops'=>0,
  'hp_mp_state_change_ops'=>0,'recover_all_ops'=>0,'change_exp_ops'=>0,'change_level_ops'=>0,'change_skill_ops'=>0,
  'change_gold_ops'=>0,'positive_gold_reward_ops'=>0,'negative_gold_cost_ops'=>0,
  'change_item_ops'=>0,'positive_item_reward_ops'=>0,'negative_item_cost_ops'=>0,
  'change_weapon_ops'=>0,'positive_weapon_reward_ops'=>0,'negative_weapon_cost_ops'=>0,
  'change_armor_ops'=>0,'positive_armor_reward_ops'=>0,'negative_armor_cost_ops'=>0
}

map_records=[]
map_globs=['Map*.rxdata','Map*.rvdata','Map*.rvdata2']
map_files=map_globs.flat_map{|g| Dir[File.join(data_dir,g)]}.uniq.select{|f| File.basename(f).match?(/^Map\d+\./i)}.sort
map_files.each do |f|
  map,err=mload(f)
  unless map
    errors << "#{File.basename(f)}: #{err}" if errors.length < 50
    next
  end
  encounter_list=Array(iv(map,:@encounter_list,[])).compact
  encounter_step=num(iv(map,:@encounter_step,nil))
  map_records << {
    'map_id'=>map_id_from_file(f),
    'random_encounter_troop_refs'=>encounter_list.length,
    'encounter_step'=>encounter_step
  }
  scan_map_commands(map,command_summary)
end
scan_common_events(data_dir,command_summary,errors)

enemies=load_array(data_dir,'Enemies',errors)
items=load_array(data_dir,'Items',errors)
weapons=load_array(data_dir,'Weapons',errors)
armors=load_array(data_dir,'Armors',errors)
classes=load_array(data_dir,'Classes',errors)
actors=load_array(data_dir,'Actors',errors)

maps_with_encounters=map_records.select{|m| m['random_encounter_troop_refs'].to_i > 0}
encounter_steps=maps_with_encounters.map{|m| m['encounter_step']}.compact.select{|x| x > 0}
enemy_exp=positive_field(enemies,:@exp)
enemy_gold=positive_field(enemies,:@gold)
item_prices=positive_field(items,:@price)
weapon_prices=positive_field(weapons,:@price)
armor_prices=positive_field(armors,:@price)
equipment_prices=weapon_prices+armor_prices
class_exp_basis=positive_field(classes,:@exp_basis)
class_exp_inflation=positive_field(classes,:@exp_inflation)
actor_initial_levels=positive_field(actors,:@initial_level)
actor_final_levels=positive_field(actors,:@final_level)

map_count=map_records.length
random_ratio=map_count>0 ? maps_with_encounters.length.to_f/map_count : nil
median_enemy_gold=stats(enemy_gold)['median']
median_equip=stats(equipment_prices)['median']
price_gold_ratio=(median_enemy_gold && median_enemy_gold>0 && median_equip) ? median_equip/median_enemy_gold : nil
median_enemy_exp=stats(enemy_exp)['median']
median_exp_basis=stats(class_exp_basis)['median']
exp_basis_ratio=(median_enemy_exp && median_enemy_exp>0 && median_exp_basis) ? median_exp_basis/median_enemy_exp : nil

out={
  'evidence_version'=>EVIDENCE_VERSION,
  'game_root'=>File.expand_path(root),
  'observed'=>{
    'maps_loaded'=>map_count,
    'maps_with_random_encounters'=>maps_with_encounters.length,
    'random_encounter_map_ratio'=>random_ratio,
    'encounter_step_stats'=>stats(encounter_steps),
    'encounter_troop_refs_total'=>map_records.sum{|m| m['random_encounter_troop_refs'].to_i},
    'enemy_count'=>enemies.length,
    'enemy_exp_stats'=>stats(enemy_exp),
    'enemy_gold_stats'=>stats(enemy_gold),
    'item_price_stats'=>stats(item_prices),
    'weapon_price_stats'=>stats(weapon_prices),
    'armor_price_stats'=>stats(armor_prices),
    'equipment_price_stats'=>stats(equipment_prices),
    'class_exp_basis_stats'=>stats(class_exp_basis),
    'class_exp_inflation_stats'=>stats(class_exp_inflation),
    'actor_initial_level_stats'=>stats(actor_initial_levels),
    'actor_final_level_stats'=>stats(actor_final_levels),
    'event_commands'=>command_summary,
    'map_records'=>map_records
  },
  'derived'=>{
    'median_equipment_price_to_enemy_gold_ratio'=>price_gold_ratio,
    'median_class_exp_basis_to_enemy_exp_ratio'=>exp_basis_ratio
  },
  'limitations'=>[
    'Enemy EXP/Gold are per database enemy, not per actual troop encounter.',
    'Equipment price / enemy gold ratio is an economy proxy, not fights-to-buy.',
    'Class exp_basis / enemy EXP ratio is a progression proxy, not battles-to-level.',
    'Encounter step semantics vary by engine and scripts; values are preserved as evidence, not converted directly into grind scores.',
    'Custom scripts can override default economy, encounters, EXP curves, recovery, and rewards.'
  ],
  'load_errors'=>errors
}

json=JSON.pretty_generate(out)
opts[:out] ? File.write(opts[:out],json) : puts(json)
