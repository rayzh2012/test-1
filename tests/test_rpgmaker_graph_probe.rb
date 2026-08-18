#!/usr/bin/env ruby
require 'json'
require 'tmpdir'
require 'fileutils'
require 'open3'

ROOT=File.expand_path('..',__dir__)
PROBE=File.join(ROOT,'tools','rpgmaker_graph_probe.rb')

module RPG; end
%w[Map MapInfo Event EventCommand CommonEvent System].each do |name|
  RPG.const_set(name,Class.new) unless RPG.const_defined?(name,false)
end
RPG::Event.const_set('Page',Class.new) unless RPG::Event.const_defined?('Page',false)
RPG::Event::Page.const_set('Condition',Class.new) unless RPG::Event::Page.const_defined?('Condition',false)

def obj(klass, **ivs)
  o=klass.new
  ivs.each{|k,v| o.instance_variable_set("@#{k}",v)}
  o
end

def cmd(code, params=[], indent=0)
  obj(RPG::EventCommand, code:code, parameters:params, indent:indent)
end

def condition(**overrides)
  base={
    switch1_valid:false,switch1_id:0,switch2_valid:false,switch2_id:0,
    variable_valid:false,variable_id:0,variable_value:0,
    self_switch_valid:false,self_switch_ch:'A',actor_valid:false,actor_id:0,item_valid:false,item_id:0
  }
  obj(RPG::Event::Page::Condition, **base.merge(overrides))
end

def page(cond,commands)
  obj(RPG::Event::Page,condition:cond,list:commands)
end

def event(id,name,x,y,pages)
  obj(RPG::Event,id:id,name:name,x:x,y:y,pages:pages)
end

def map(width,height,events)
  obj(RPG::Map,width:width,height:height,events:events)
end

def dump(path,obj)
  File.binwrite(path,Marshal.dump(obj))
end

def assert(cond,msg)
  raise "ASSERTION FAILED: #{msg}" unless cond
end

Dir.mktmpdir('rpgmaker-graph-fixture') do |td|
  data=File.join(td,'Game','Data'); FileUtils.mkdir_p(data)

  infos={
    1=>obj(RPG::MapInfo,name:'起点村',parent_id:0,order:1,expanded:true,scroll_x:0,scroll_y:0),
    2=>obj(RPG::MapInfo,name:'终局地图',parent_id:0,order:2,expanded:true,scroll_x:0,scroll_y:0)
  }
  dump(File.join(data,'MapInfos.rvdata'),infos)
  dump(File.join(data,'System.rvdata'),obj(RPG::System,start_map_id:1,start_x:5,start_y:6,party_members:[1]))

  p1=page(
    condition(switch1_valid:true,switch1_id:5),
    [
      cmd(101,['主线开始']),
      cmd(111,[0,5,0]),
      cmd(121,[10,10,0]),
      cmd(122,[20,20,0,0,3]),
      cmd(102,[['接受','拒绝'],0,0,2,0]),
      cmd(201,[0,2,3,4,2,0]),
      cmd(117,[1]),
      cmd(301,[0,1,true,false]),
      cmd(302,[1,0,0,0])
    ]
  )
  dump(File.join(data,'Map001.rvdata'),map(20,15,{1=>event(1,'任务NPC',4,5,[p1])}))

  p2=page(
    condition(variable_valid:true,variable_id:20,variable_value:3),
    [cmd(101,['结局 A']),cmd(354,[])]
  )
  dump(File.join(data,'Map002.rvdata'),map(12,10,{1=>event(1,'终局事件',3,3,[p2])}))

  ce=obj(RPG::CommonEvent,id:1,name:'奖励处理',trigger:2,switch_id:10,list:[cmd(121,[11,11,0]),cmd(101,['支线奖励'])])
  dump(File.join(data,'CommonEvents.rvdata'),[nil,ce])

  out=File.join(td,'graph.json')
  stdout,stderr,status=Open3.capture3('ruby',PROBE,File.join(td,'Game'),'--out',out)
  raise "probe failed: #{stdout}\n#{stderr}" unless status.success?
  g=JSON.parse(File.read(out,encoding:'UTF-8'))
  s=g.fetch('summary')

  assert(g['graph_version']=='rpgmaker.graph.v0.3','graph version')
  assert(s['maps_loaded']==2,'maps loaded')
  assert(s['event_page_nodes']==2,'event page nodes')
  assert(s['common_event_nodes']==1,'common event nodes')
  assert(s['direct_map_edges']==1,'direct map edge count')
  assert(s['unique_direct_map_pairs']==1,'unique map pair count')
  assert(s['weak_component_count']==1,'weak component count')
  assert(s['largest_component_maps']==2,'largest component size')
  assert(s['conditional_branch_nodes']==1,'conditional branch count')
  assert(s['choice_nodes']==1,'choice node count')
  assert(s['common_event_call_edges']==1,'common event edge count')
  assert(s['battle_call_nodes']==1,'battle call count')
  assert(s['shop_call_nodes']==1,'shop call count')
  assert(s['start_map_id']==1,'start map')
  assert(s['switch_read_ids']>=2,'switch reads')
  assert(s['switch_write_ids']==2,'switch writes')
  assert(s['variable_read_ids']==1,'variable reads')
  assert(s['variable_write_ids']==1,'variable writes')
  assert(s['shared_variable_ids']==1,'variable 20 spans maps 1 and 2')
  assert(s['terminal_signal_nodes']==2,'text ending signal + return title')
  assert(s['terminal_signals_by_type']['return_to_title']==1,'return title signal')
  assert(s['terminal_signals_by_type']['terminal_text_signal']==1,'terminal text signal')

  edge=g['map_edges'].find{|e| e['source_map_id']==1 && e['target_map_id']==2}
  assert(!edge.nil?,'map 1 -> map 2 edge')
  assert(g['state_writes'].any?{|e| e['state_type']=='switch' && e['state_id']==10},'switch 10 write')
  assert(g['state_writes'].any?{|e| e['state_type']=='variable' && e['state_id']==20},'variable 20 write')
  assert(g['state_reads'].any?{|e| e['state_type']=='variable' && e['state_id']==20 && e['map_id']==2},'variable 20 page condition read')

  puts JSON.pretty_generate({'status'=>'PASS','summary'=>s})
end
