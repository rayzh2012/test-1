#!/usr/bin/env ruby
require 'json'
require 'optparse'
require 'set'

GRAPH_VERSION = 'rpgmaker.graph.v0.3'

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

def utf8(s)
  s.to_s.encode('UTF-8',invalid: :replace,undef: :replace,replace: '')
rescue
  s.to_s
end

def primitive(v, depth=0)
  return nil if depth > 3
  case v
  when NilClass, TrueClass, FalseClass, Integer, Float then v
  when String then utf8(v)
  when Symbol then v.to_s
  when Array then v.first(30).map{|x| primitive(x,depth+1)}
  when Hash
    h={}; v.to_a.first(30).each{|k,x| h[primitive(k,depth+1).to_s]=primitive(x,depth+1)}; h
  else
    utf8(v)
  end
end

def bool_iv(o,name)
  !!iv(o,name,false)
end

def map_id_from_file(path)
  m=File.basename(path).match(/Map(\d+)/i)
  m ? m[1].to_i : nil
end

def map_infos(data_dir)
  f=Dir[File.join(data_dir,'MapInfos.*data*')].first
  return {} unless f
  obj,err=mload(f)
  return {} unless obj && obj.respond_to?(:each)
  out={}
  obj.each do |id,mi|
    out[id.to_i]={
      'id'=>id.to_i,
      'name'=>utf8(iv(mi,:@name,'')),
      'parent_id'=>iv(mi,:@parent_id,0).to_i,
      'order'=>iv(mi,:@order,0).to_i,
      'expanded'=>!!iv(mi,:@expanded,false),
      'scroll_x'=>iv(mi,:@scroll_x,nil),
      'scroll_y'=>iv(mi,:@scroll_y,nil)
    }
  end
  out
end

def system_start(data_dir)
  f=Dir[File.join(data_dir,'System.*data*')].first
  return {} unless f
  obj,err=mload(f)
  return {'load_error'=>err} unless obj
  {
    'start_map_id'=>iv(obj,:@start_map_id,nil),
    'start_x'=>iv(obj,:@start_x,nil),
    'start_y'=>iv(obj,:@start_y,nil),
    'party_members'=>primitive(iv(obj,:@party_members,[]))
  }
end

def condition_info(pg)
  c=iv(pg,:@condition,nil)
  return {'switches'=>[],'variables'=>[],'self_switches'=>[],'actors'=>[],'items'=>[]} unless c
  out={'switches'=>[],'variables'=>[],'self_switches'=>[],'actors'=>[],'items'=>[]}
  if bool_iv(c,:@switch1_valid)
    out['switches'] << {'id'=>iv(c,:@switch1_id,0).to_i,'expected'=>true,'slot'=>1}
  end
  if bool_iv(c,:@switch2_valid)
    out['switches'] << {'id'=>iv(c,:@switch2_id,0).to_i,'expected'=>true,'slot'=>2}
  end
  if bool_iv(c,:@variable_valid)
    out['variables'] << {'id'=>iv(c,:@variable_id,0).to_i,'min_value'=>iv(c,:@variable_value,0)}
  end
  if bool_iv(c,:@self_switch_valid)
    out['self_switches'] << {'key'=>utf8(iv(c,:@self_switch_ch,'')),'expected'=>true}
  end
  if bool_iv(c,:@actor_valid)
    out['actors'] << {'id'=>iv(c,:@actor_id,0).to_i}
  end
  if bool_iv(c,:@item_valid)
    out['items'] << {'id'=>iv(c,:@item_id,0).to_i}
  end
  out
end

def expand_range(a,b,max_ids=500)
  x=a.to_i; y=b.to_i
  lo=[x,y].min; hi=[x,y].max
  return nil if hi-lo+1 > max_ids
  (lo..hi).to_a
end

def source_base(node_id,map_id=nil,event_id=nil,page_index=nil,common_event_id=nil,command_index=nil)
  h={'node_id'=>node_id}
  h['map_id']=map_id if map_id
  h['event_id']=event_id if event_id
  h['page_index']=page_index unless page_index.nil?
  h['common_event_id']=common_event_id if common_event_id
  h['command_index']=command_index unless command_index.nil?
  h
end

TERMINAL_TEXT = /(THE\s*END|STAFF|CREDITS?|ENDING|结局|結局|终章|終章|通关|通關|完结|完結|感谢.*游玩|感謝.*遊玩|制作人员|製作人員)/i

def parse_commands(list, source, graph, node_metrics)
  Array(list).each_with_index do |c,idx|
    code=iv(c,:@code,0).to_i
    params=Array(iv(c,:@parameters,[]))
    indent=iv(c,:@indent,0).to_i
    graph['command_histogram'][code.to_s]=(graph['command_histogram'][code.to_s]||0)+1
    node_metrics['command_count'] += 1
    base=source.merge('command_index'=>idx,'code'=>code,'indent'=>indent)

    case code
    when 101,401,405
      strings=params.flatten.select{|x| x.is_a?(String)}.map{|s| utf8(s)}
      node_metrics['dialogue_lines'] += strings.length
      node_metrics['dialogue_chars'] += strings.sum(&:length)
      strings.each do |s|
        node_metrics['dialogue_samples'] << s if !s.empty? && node_metrics['dialogue_samples'].length < 5
        if s.match?(TERMINAL_TEXT)
          graph['terminal_signals'] << base.merge('type'=>'terminal_text_signal','text'=>s[0,240])
        end
      end
    when 102
      opts=params[0].is_a?(Array) ? params[0].map{|x| utf8(x)} : params.flatten.select{|x| x.is_a?(String)}.map{|x| utf8(x)}
      node_metrics['choice_options'] += opts.length
      graph['choice_nodes'] << base.merge('options'=>opts.first(30))
    when 111
      node_metrics['conditional_branches'] += 1
      kind=params[0].to_i
      read=nil
      case kind
      when 0
        read={'state_type'=>'switch','state_id'=>params[1].to_i,'comparison'=>primitive(params[2]),'reason'=>'conditional_branch'}
      when 1
        read={'state_type'=>'variable','state_id'=>params[1].to_i,'comparison'=>primitive(params[2..]),'reason'=>'conditional_branch'}
      when 2
        read={'state_type'=>'self_switch','state_id'=>utf8(params[1]),'comparison'=>primitive(params[2]),'reason'=>'conditional_branch'}
      end
      graph['state_reads'] << base.merge(read) if read
      graph['conditional_branches'] << base.merge('branch_type'=>kind,'parameters'=>primitive(params))
    when 117
      graph['common_event_edges'] << base.merge('target_common_event_id'=>params[0].to_i)
    when 121
      ids=expand_range(params[0],params[1])
      if ids
        ids.each{|id| graph['state_writes'] << base.merge('state_type'=>'switch','state_id'=>id,'operation'=>primitive(params[2]),'reason'=>'control_switches')}
      else
        graph['state_writes'] << base.merge('state_type'=>'switch_range','state_id'=>"#{params[0]}..#{params[1]}",'operation'=>primitive(params[2]),'reason'=>'control_switches')
      end
    when 122
      ids=expand_range(params[0],params[1])
      payload={'operation'=>primitive(params[2]),'operand_type'=>primitive(params[3]),'operand'=>primitive(params[4..]),'reason'=>'control_variables'}
      if ids
        ids.each{|id| graph['state_writes'] << base.merge(payload).merge('state_type'=>'variable','state_id'=>id)}
      else
        graph['state_writes'] << base.merge(payload).merge('state_type'=>'variable_range','state_id'=>"#{params[0]}..#{params[1]}")
      end
    when 123
      graph['state_writes'] << base.merge('state_type'=>'self_switch','state_id'=>utf8(params[0]),'operation'=>primitive(params[1]),'reason'=>'control_self_switch')
    when 201
      mode=params[0].to_i
      edge=base.merge('source_map_id'=>source['map_id'],'target_mode'=>(mode==0 ? 'direct' : 'variable'),'raw_parameters'=>primitive(params))
      if mode==0
        edge['target_map_id']=params[1].to_i
      else
        edge['target_map_variable_id']=params[1].to_i
        edge['target_x_variable_id']=params[2].to_i if params.length>2
        edge['target_y_variable_id']=params[3].to_i if params.length>3
        [params[1],params[2],params[3]].compact.each do |vid|
          graph['state_reads'] << base.merge('state_type'=>'variable','state_id'=>vid.to_i,'reason'=>'variable_transfer_destination')
        end
      end
      graph['map_edges'] << edge
    when 301
      graph['battle_nodes'] << base.merge('parameters'=>primitive(params))
    when 302
      graph['shop_nodes'] << base.merge('parameters'=>primitive(params))
    when 353
      graph['terminal_signals'] << base.merge('type'=>'game_over')
    when 354
      graph['terminal_signals'] << base.merge('type'=>'return_to_title')
    when 115
      graph['terminal_signals'] << base.merge('type'=>'exit_event_processing')
    when 118
      graph['labels'] << base.merge('label'=>utf8(params[0]))
    when 119
      graph['label_jumps'] << base.merge('label'=>utf8(params[0]))
    end
  end
end

def add_page_condition_reads(graph, source, cond)
  cond['switches'].each{|x| graph['state_reads'] << source.merge('state_type'=>'switch','state_id'=>x['id'],'reason'=>'page_condition','comparison'=>x['expected'])}
  cond['variables'].each{|x| graph['state_reads'] << source.merge('state_type'=>'variable','state_id'=>x['id'],'reason'=>'page_condition','comparison'=>x['min_value'])}
  cond['self_switches'].each{|x| graph['state_reads'] << source.merge('state_type'=>'self_switch','state_id'=>x['key'],'reason'=>'page_condition','comparison'=>x['expected'])}
end

def weak_components(map_ids,edges)
  parent={}; map_ids.each{|id| parent[id]=id}
  find=lambda do |x|
    parent[x]=find.call(parent[x]) if parent[x] != x
    parent[x]
  end
  union=lambda do |a,b|
    return unless parent.key?(a) && parent.key?(b)
    ra=find.call(a); rb=find.call(b); parent[rb]=ra if ra != rb
  end
  edges.each{|e| union.call(e['source_map_id'],e['target_map_id']) if e['target_mode']=='direct'}
  groups=Hash.new{|h,k| h[k]=[]}
  map_ids.each{|id| groups[find.call(id)] << id}
  groups.values.sort_by{|g| [-g.length,g.min||0]}
end

def state_locality(reads,writes)
  touched=Hash.new{|h,k| h[k]=Set.new}
  (reads+writes).each do |e|
    t=e['state_type']; id=e['state_id']; mid=e['map_id']
    next unless %w[switch variable].include?(t) && !id.nil? && mid
    touched[[t,id]] << mid
  end
  out={'switch'=>{'local'=>0,'shared'=>0},'variable'=>{'local'=>0,'shared'=>0}}
  touched.each do |(t,id),maps|
    if maps.length <= 1 then out[t]['local']+=1 else out[t]['shared']+=1 end
  end
  out
end

opts={}
OptionParser.new{|o| o.on('--out PATH'){|v| opts[:out]=v}}.parse!
root=ARGV.shift or abort 'usage: rpgmaker_graph_probe.rb GAME_ROOT --out FILE'
data_dir=File.join(root,'Data')
abort "Data directory not found: #{data_dir}" unless Dir.exist?(data_dir)

infos=map_infos(data_dir)
system=system_start(data_dir)
graph={
  'graph_version'=>GRAPH_VERSION,
  'game_root'=>File.expand_path(root),
  'system'=>system,
  'maps'=>[],
  'event_pages'=>[],
  'common_events'=>[],
  'map_edges'=>[],
  'state_reads'=>[],
  'state_writes'=>[],
  'common_event_edges'=>[],
  'conditional_branches'=>[],
  'choice_nodes'=>[],
  'battle_nodes'=>[],
  'shop_nodes'=>[],
  'terminal_signals'=>[],
  'labels'=>[],
  'label_jumps'=>[],
  'command_histogram'=>{},
  'load_errors'=>[]
}

map_globs=['Map*.rxdata','Map*.rvdata','Map*.rvdata2']
map_files=map_globs.flat_map{|g| Dir[File.join(data_dir,g)]}.uniq.sort
map_files.each do |f|
  mid=map_id_from_file(f); map,err=mload(f)
  unless map
    graph['load_errors'] << "#{File.basename(f)}: #{err}" if graph['load_errors'].length < 50
    next
  end
  info=infos[mid]||{}
  events=iv(map,:@events,{}) || {}; events=events.values if events.respond_to?(:values); events=Array(events).compact
  graph['maps'] << {
    'map_id'=>mid,
    'name'=>info['name']||'',
    'parent_id'=>info['parent_id'],
    'width'=>iv(map,:@width,nil),
    'height'=>iv(map,:@height,nil),
    'event_count'=>events.length
  }
  events.each do |ev|
    eid=iv(ev,:@id,nil).to_i; ename=utf8(iv(ev,:@name,'')); x=iv(ev,:@x,nil); y=iv(ev,:@y,nil)
    Array(iv(ev,:@pages,[])).compact.each_with_index do |pg,pidx|
      node_id="map:#{mid}:event:#{eid}:page:#{pidx}"
      source=source_base(node_id,mid,eid,pidx,nil,nil)
      cond=condition_info(pg); add_page_condition_reads(graph,source,cond)
      metrics={'command_count'=>0,'dialogue_lines'=>0,'dialogue_chars'=>0,'choice_options'=>0,'conditional_branches'=>0,'dialogue_samples'=>[]}
      parse_commands(iv(pg,:@list,[]),source,graph,metrics)
      graph['event_pages'] << source.merge({
        'event_name'=>ename,'x'=>x,'y'=>y,'conditions'=>cond
      }).merge(metrics)
    end
  end
end

common_file=Dir[File.join(data_dir,'CommonEvents.*data*')].first
if common_file
  arr,err=mload(common_file)
  if arr
    Array(arr).compact.each do |ce|
      cid=iv(ce,:@id,nil).to_i; name=utf8(iv(ce,:@name,'')); trigger=iv(ce,:@trigger,nil); switch_id=iv(ce,:@switch_id,nil)
      node_id="common:#{cid}"; source=source_base(node_id,nil,nil,nil,cid,nil)
      if switch_id && switch_id.to_i>0
        graph['state_reads'] << source.merge('state_type'=>'switch','state_id'=>switch_id.to_i,'reason'=>'common_event_trigger')
      end
      metrics={'command_count'=>0,'dialogue_lines'=>0,'dialogue_chars'=>0,'choice_options'=>0,'conditional_branches'=>0,'dialogue_samples'=>[]}
      parse_commands(iv(ce,:@list,[]),source,graph,metrics)
      graph['common_events'] << source.merge({'name'=>name,'trigger'=>primitive(trigger),'trigger_switch_id'=>switch_id}).merge(metrics)
    end
  else
    graph['load_errors'] << "#{File.basename(common_file)}: #{err}"
  end
end

map_ids=graph['maps'].map{|m| m['map_id']}.compact.uniq.sort
direct_edges=graph['map_edges'].select{|e| e['target_mode']=='direct' && e['source_map_id'] && e['target_map_id']}
variable_edges=graph['map_edges'].select{|e| e['target_mode']=='variable'}
unique_pairs=direct_edges.map{|e| [e['source_map_id'],e['target_map_id']]}.uniq
incoming=Hash.new(0); outgoing=Hash.new(0)
unique_pairs.each{|a,b| outgoing[a]+=1; incoming[b]+=1}
components=weak_components(map_ids,direct_edges)
loc=state_locality(graph['state_reads'],graph['state_writes'])
switch_reads=graph['state_reads'].select{|e| e['state_type']=='switch'}.map{|e|e['state_id']}.compact.uniq
switch_writes=graph['state_writes'].select{|e| e['state_type']=='switch'}.map{|e|e['state_id']}.compact.uniq
variable_reads=graph['state_reads'].select{|e| e['state_type']=='variable'}.map{|e|e['state_id']}.compact.uniq
variable_writes=graph['state_writes'].select{|e| e['state_type']=='variable'}.map{|e|e['state_id']}.compact.uniq
terminal_by_type=graph['terminal_signals'].group_by{|x|x['type']}.transform_values(&:length)

graph['summary']={
  'maps_loaded'=>map_ids.length,
  'event_page_nodes'=>graph['event_pages'].length,
  'common_event_nodes'=>graph['common_events'].length,
  'direct_map_edges'=>direct_edges.length,
  'variable_map_edges'=>variable_edges.length,
  'unique_direct_map_pairs'=>unique_pairs.length,
  'weak_component_count'=>components.length,
  'largest_component_maps'=>components.first ? components.first.length : 0,
  'isolated_maps_by_direct_transfer'=>map_ids.count{|id| incoming[id]==0 && outgoing[id]==0},
  'maps_without_direct_outgoing'=>map_ids.count{|id| outgoing[id]==0},
  'maps_without_direct_incoming'=>map_ids.count{|id| incoming[id]==0},
  'conditional_branch_nodes'=>graph['conditional_branches'].length,
  'choice_nodes'=>graph['choice_nodes'].length,
  'common_event_call_edges'=>graph['common_event_edges'].length,
  'battle_call_nodes'=>graph['battle_nodes'].length,
  'shop_call_nodes'=>graph['shop_nodes'].length,
  'switch_read_ids'=>switch_reads.length,
  'switch_write_ids'=>switch_writes.length,
  'variable_read_ids'=>variable_reads.length,
  'variable_write_ids'=>variable_writes.length,
  'local_switch_ids'=>loc['switch']['local'],
  'shared_switch_ids'=>loc['switch']['shared'],
  'local_variable_ids'=>loc['variable']['local'],
  'shared_variable_ids'=>loc['variable']['shared'],
  'terminal_signal_nodes'=>graph['terminal_signals'].length,
  'terminal_signals_by_type'=>terminal_by_type,
  'label_nodes'=>graph['labels'].length,
  'label_jump_nodes'=>graph['label_jumps'].length,
  'start_map_id'=>system['start_map_id'],
  'load_error_count'=>graph['load_errors'].length
}

graph['components']=components.first(100)
json=JSON.pretty_generate(graph)
opts[:out] ? File.write(opts[:out],json) : puts(json)
