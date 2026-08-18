#!/usr/bin/env ruby
require 'json'
require 'optparse'
require_relative 'rpgmaker_marshal_lib'

opts={}
OptionParser.new{|o| o.on('--out PATH'){|v| opts[:out]=v}}.parse!
root=ARGV.shift or abort 'usage: rpgmaker_dialogue_extract.rb GAME_ROOT --out FILE'
rows=[]; errors=[]

def condition_summary(pg)
  c=iv(pg,:@condition,nil); return {} unless c
  out={}
  [:@switch1_valid,:@switch2_valid,:@variable_valid,:@self_switch_valid,:@actor_valid,:@item_valid].each do |k|
    v=iv(c,k,nil); out[k.to_s.sub('@','')]=v unless v.nil?
  end
  [:@switch1_id,:@switch2_id,:@variable_id,:@variable_value,:@self_switch_ch,:@actor_id,:@item_id].each do |k|
    v=iv(c,k,nil); out[k.to_s.sub('@','')]=v unless v.nil?
  end
  out
end

def extract_commands(list, base, rows)
  current_text=nil
  Array(list).each_with_index do |cmd,idx|
    code=iv(cmd,:@code,0).to_i; params=iv(cmd,:@parameters,[])
    case code
    when 101
      text=params.map{|x| utf8(x)}.reject(&:empty?).join(' ')
      current_text={**base,'command_index'=>idx,'kind'=>'dialogue','text'=>text,'continuations'=>[]}
      rows << current_text unless text.empty?
    when 401,405
      text=params.map{|x| utf8(x)}.reject(&:empty?).join(' ')
      if current_text && !text.empty?
        current_text['continuations'] << text
        current_text['text'] = ([current_text['text']] + current_text['continuations']).join("\n")
      elsif !text.empty?
        rows << {**base,'command_index'=>idx,'kind'=>'dialogue','text'=>text,'continuations'=>[]}
      end
    when 102
      choices=Array(params[0]).map{|x| utf8(x)}
      rows << {**base,'command_index'=>idx,'kind'=>'choice','choices'=>choices,'text'=>choices.join(' | ')} unless choices.empty?
      current_text=nil
    else
      current_text=nil unless [401,405].include?(code)
    end
  end
end

map_files_for(root).each do |f|
  map,err=rpg_mload(f)
  unless map
    errors << "#{File.basename(f)}: #{err}"; next
  end
  mid=map_id_from_file(f); events=iv(map,:@events,{}) || {}; events=events.values if events.respond_to?(:values)
  Array(events).compact.each do |ev|
    eid=iv(ev,:@id,nil); ename=utf8(iv(ev,:@name,''))
    Array(iv(ev,:@pages,[])).compact.each_with_index do |pg,pidx|
      base={'scope'=>'map','map_id'=>mid,'event_id'=>eid,'event_name'=>ename,'page_id'=>pidx+1,'conditions'=>condition_summary(pg)}
      extract_commands(iv(pg,:@list,[]),base,rows)
    end
  end
end

cf=common_events_file(root)
if cf
  arr,err=rpg_mload(cf)
  if arr
    Array(arr).compact.each do |ce|
      cid=iv(ce,:@id,nil); cname=utf8(iv(ce,:@name,''))
      extract_commands(iv(ce,:@list,[]),{'scope'=>'common_event','common_event_id'=>cid,'event_name'=>cname,'page_id'=>1,'conditions'=>{}},rows)
    end
  else
    errors << "#{File.basename(cf)}: #{err}"
  end
end

summary={
  'dialogue_blocks'=>rows.count{|r| r['kind']=='dialogue'},
  'choice_blocks'=>rows.count{|r| r['kind']=='choice'},
  'dialogue_chars'=>rows.select{|r| r['kind']=='dialogue'}.sum{|r| r['text'].to_s.length},
  'choice_options'=>rows.select{|r| r['kind']=='choice'}.sum{|r| Array(r['choices']).length},
  'unique_text_blocks'=>rows.map{|r| r['text']}.reject(&:empty?).uniq.length,
  'duplicate_text_blocks'=>rows.length-rows.map{|r| r['text']}.reject(&:empty?).uniq.length,
  'errors'=>errors
}
out={'schema'=>'fangame-dialogue-v1','summary'=>summary,'rows'=>rows}
json=JSON.pretty_generate(out)
opts[:out] ? File.write(opts[:out],json) : puts(json)
