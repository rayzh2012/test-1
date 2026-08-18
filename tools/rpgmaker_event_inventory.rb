#!/usr/bin/env ruby
require 'json'
require 'optparse'
require_relative 'rpgmaker_marshal_lib'
opts={}; OptionParser.new{|o| o.on('--out PATH'){|v|opts[:out]=v}}.parse!
root=ARGV.shift or abort 'usage: rpgmaker_event_inventory.rb GAME_ROOT --out FILE'
data_dir=File.join(root,'Data'); start_map_id=nil
sysf=Dir[File.join(data_dir,'System.*data*')].first
if sysf
  sys,err=rpg_mload(sysf); start_map_id=iv(sys,:@start_map_id,nil) if sys
end
maps=[]; character_graphics=Hash.new(0); event_name_counts=Hash.new(0); total_events=0; total_pages=0
map_files_for(root).each do |f|
  map,err=rpg_mload(f); next unless map
  mid=map_id_from_file(f); evs=iv(map,:@events,{}) || {}; evs=evs.values if evs.respond_to?(:values)
  row={'map_id'=>mid,'width'=>iv(map,:@width,nil),'height'=>iv(map,:@height,nil),'events'=>[]}
  Array(evs).compact.each do |ev|
    eid=iv(ev,:@id,nil); name=utf8(iv(ev,:@name,'').to_s); pages=Array(iv(ev,:@pages,[])).compact
    total_events+=1; total_pages+=pages.length; event_name_counts[name]+=1 unless name.empty?
    page_rows=[]
    pages.each_with_index do |pg,pidx|
      gr=iv(pg,:@graphic,nil); cname=gr ? utf8(iv(gr,:@character_name,'').to_s) : ''; character_graphics[cname]+=1 unless cname.empty?
      cmds=Array(iv(pg,:@list,[])); counts=Hash.new(0); cmds.each{|c|counts[iv(c,:@code,0).to_i]+=1}
      page_rows << {'page_id'=>pidx+1,'character_name'=>cname,'command_count'=>cmds.length,'dialogue_commands'=>counts[401]+counts[405],'choice_commands'=>counts[102],'battle_calls'=>counts[301],'shop_calls'=>counts[302],'transfer_calls'=>counts[201],'switch_writes'=>counts[121],'variable_writes'=>counts[122],'script_commands'=>counts[355]+counts[655]}
    end
    row['events'] << {'event_id'=>eid,'name'=>name,'x'=>iv(ev,:@x,nil),'y'=>iv(ev,:@y,nil),'page_count'=>pages.length,'pages'=>page_rows}
  end
  row['event_count']=row['events'].length; row['event_pages']=row['events'].sum{|e|e['page_count']}
  row['dialogue_commands']=row['events'].sum{|e|e['pages'].sum{|p|p['dialogue_commands']}}; row['battle_calls']=row['events'].sum{|e|e['pages'].sum{|p|p['battle_calls']}}; row['shop_calls']=row['events'].sum{|e|e['pages'].sum{|p|p['shop_calls']}}
  maps << row
end
actor_names=[]; af=Dir[File.join(data_dir,'Actors.*data*')].first
if af
  arr,err=rpg_mload(af); actor_names=Array(arr).compact.map{|a|utf8(iv(a,:@name,'').to_s)}.reject(&:empty?) if arr
end
out={'schema'=>'fangame-event-inventory-v1','start_map_id'=>start_map_id,'summary'=>{'maps'=>maps.length,'events'=>total_events,'event_pages'=>total_pages,'named_database_actors'=>actor_names.length,'unique_event_character_graphics'=>character_graphics.length,'unique_event_names'=>event_name_counts.length},'actor_names'=>actor_names,'character_graphics'=>character_graphics.sort_by{|k,v|[-v,k]}.map{|k,v|{'name'=>k,'page_uses'=>v}},'event_name_frequency'=>event_name_counts.sort_by{|k,v|[-v,k]}.first(200).map{|k,v|{'name'=>k,'count'=>v}},'maps'=>maps.sort_by{|m|m['map_id']}}
json=JSON.pretty_generate(out); opts[:out] ? File.write(opts[:out],json) : puts(json)
