#!/usr/bin/env ruby
require 'json'
require 'optparse'

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
  40.times do
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

def flatten_strings(x,out=[])
  case x
  when String then out << x
  when Array then x.each{|v| flatten_strings(v,out)}
  when Hash then x.each{|k,v| flatten_strings(k,out); flatten_strings(v,out)}
  end
  out
end

def slen(s)
  s.to_s.encode('UTF-8',invalid: :replace,undef: :replace,replace: '').length
rescue
  s.to_s.bytesize
end

def command_metrics(list,m)
  Array(list).each do |c|
    code=iv(c,:@code,0).to_i
    params=iv(c,:@parameters,[])
    ss=flatten_strings(params)
    m['event_commands'] += 1
    case code
    when 101,401,405
      m['dialogue_lines'] += ss.length
      m['dialogue_chars'] += ss.sum{|s| slen(s)}
    when 102,402
      m['choice_options'] += ss.length
      m['choice_chars'] += ss.sum{|s| slen(s)}
    when 108,408
      m['comment_chars'] += ss.sum{|s| slen(s)}
    when 355,655
      m['script_chars'] += ss.sum{|s| slen(s)}
    when 117 then m['common_event_calls'] += 1
    when 201 then m['map_transfers'] += 1
    when 301 then m['battle_calls'] += 1
    when 302 then m['shop_calls'] += 1
    when 311,312,313,314 then m['actor_recovery_or_state_ops'] += 1
    when 121 then m['switch_ops'] += 1
    when 122 then m['variable_ops'] += 1
    end
  end
end

def named_count(arr)
  Array(arr).compact.count{|x| x}
end

def database_text(arr)
  chars=0
  Array(arr).compact.each do |x|
    [:@name,:@description,:@message1,:@message2,:@message3,:@message4,:@note].each do |k|
      v=iv(x,k,nil); chars += slen(v) if v.is_a?(String)
    end
  end
  chars
end

opts={}
OptionParser.new{|o| o.on('--out PATH'){|v| opts[:out]=v}}.parse!
root=ARGV.shift or abort 'usage: rpgmaker_marshal_probe.rb GAME_ROOT --out FILE'
data_dir=File.join(root,'Data')
metrics={
  'marshal_probe'=>true,'maps_loaded'=>0,'map_load_errors'=>0,'events'=>0,'event_pages'=>0,'event_commands'=>0,
  'dialogue_lines'=>0,'dialogue_chars'=>0,'choice_options'=>0,'choice_chars'=>0,'comment_chars'=>0,'script_chars'=>0,
  'common_event_calls'=>0,'map_transfers'=>0,'battle_calls'=>0,'shop_calls'=>0,'actor_recovery_or_state_ops'=>0,
  'switch_ops'=>0,'variable_ops'=>0,'common_events'=>0,'database_text_chars'=>0,'load_errors'=>[]
}
map_globs=['Map*.rxdata','Map*.rvdata','Map*.rvdata2']
map_globs.flat_map{|g| Dir[File.join(data_dir,g)]}.uniq.sort.each do |f|
  map,err=mload(f)
  if !map
    metrics['map_load_errors']+=1
    metrics['load_errors'] << "#{File.basename(f)}: #{err}" if metrics['load_errors'].length < 20
    next
  end
  metrics['maps_loaded']+=1
  events=iv(map,:@events,{}) || {}
  events=events.values if events.respond_to?(:values)
  Array(events).compact.each do |ev|
    metrics['events']+=1
    Array(iv(ev,:@pages,[])).compact.each do |pg|
      metrics['event_pages']+=1
      command_metrics(iv(pg,:@list,[]),metrics)
    end
  end
end

common=Dir[File.join(data_dir,'CommonEvents.*data*')].first
if common
  arr,err=mload(common)
  if arr
    Array(arr).compact.each do |ce|
      metrics['common_events']+=1
      command_metrics(iv(ce,:@list,[]),metrics)
    end
  else
    metrics['load_errors'] << "#{File.basename(common)}: #{err}"
  end
end

{
  'actors'=>'Actors','classes'=>'Classes','skills'=>'Skills','items'=>'Items','weapons'=>'Weapons','armors'=>'Armors',
  'enemies'=>'Enemies','troops'=>'Troops','states'=>'States'
}.each do |key,base|
  f=Dir[File.join(data_dir,"#{base}.*data*")].first
  next unless f
  arr,err=mload(f)
  if arr
    metrics[key]=named_count(arr)
    metrics['database_text_chars'] += database_text(arr)
  else
    metrics['load_errors'] << "#{File.basename(f)}: #{err}" if metrics['load_errors'].length < 20
  end
end

metrics['story_text_chars_proxy']=metrics['dialogue_chars']+metrics['choice_chars']+metrics['database_text_chars']
metrics['system_complexity_proxy']=metrics['choice_options']+metrics['common_event_calls']+metrics['battle_calls']+metrics['shop_calls']+metrics['switch_ops']+metrics['variable_ops']
json=JSON.pretty_generate(metrics)
opts[:out] ? File.write(opts[:out],json) : puts(json)
