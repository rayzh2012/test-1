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
  if iv(c,:@switch1_valid,false); out['switch1_id']=iv(c,:@switch1_id,nil); end
  if iv(c,:@switch2_valid,false); out['switch2_id']=iv(c,:@switch2_id,nil); end
  if iv(c,:@variable_valid,false); out['variable_id']=iv(c,:@variable_id,nil); out['variable_value']=iv(c,:@variable_value,nil); end
  if iv(c,:@self_switch_valid,false); out['self_switch_ch']=utf8(iv(c,:@self_switch_ch,'')); end
  if iv(c,:@actor_valid,false); out['actor_id']=iv(c,:@actor_id,nil); end
  if iv(c,:@item_valid,false); out['item_id']=iv(c,:@item_id,nil); end
  out
end

def add_or_append_text(current, base, idx, text, rows, header_meta=nil)
  return current if text.nil? || text.strip.empty?
  if current
    current['lines'] << text
    current['text']=current['lines'].join("\n")
    current
  else
    row={**base,'command_index'=>idx,'kind'=>'dialogue','text'=>text,'lines'=>[text]}
    row['header_meta']=header_meta if header_meta
    rows << row
    row
  end
end

def extract_commands(list, base, rows)
  current=nil
  Array(list).each_with_index do |cmd,idx|
    code=iv(cmd,:@code,0).to_i; params=iv(cmd,:@parameters,[])
    case code
    when 101
      current=nil
      if params.length==1 && params[0].is_a?(String)
        current=add_or_append_text(nil,base,idx,utf8(params[0]),rows)
      else
        current={**base,'command_index'=>idx,'kind'=>'dialogue','text'=>'','lines'=>[],'header_meta'=>params.map{|x| x.is_a?(String) ? utf8(x) : x}}
      end
    when 401
      text=params.map{|x| utf8(x)}.reject(&:empty?).join(' ')
      if current && current['lines'].empty? && !rows.include?(current)
        current['lines'] << text unless text.strip.empty?
        current['text']=current['lines'].join("\n")
        rows << current unless current['text'].strip.empty?
      else
        current=add_or_append_text(current,base,idx,text,rows)
      end
    when 105
      current={**base,'command_index'=>idx,'kind'=>'dialogue','text'=>'','lines'=>[],'header_meta'=>params}
    when 405
      text=params.map{|x| utf8(x)}.reject(&:empty?).join(' ')
      if current && current['lines'].empty? && !rows.include?(current)
        current['lines'] << text unless text.strip.empty?
        current['text']=current['lines'].join("\n")
        rows << current unless current['text'].strip.empty?
      else
        current=add_or_append_text(current,base,idx,text,rows)
      end
    when 102
      choices=Array(params[0]).map{|x| utf8(x)}.reject(&:empty?)
      rows << {**base,'command_index'=>idx,'kind'=>'choice','choices'=>choices,'text'=>choices.join(' | ')} unless choices.empty?
      current=nil
    else
      current=nil unless [401,405].include?(code)
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

text_rows=rows.select{|r| r['kind']=='dialogue'}
choice_rows=rows.select{|r| r['kind']=='choice'}
texts=text_rows.map{|r| r['text'].to_s.strip}.reject(&:empty?)
unique_count=texts.uniq.length
duplicate_count=texts.length-unique_count
summary={
  'dialogue_blocks'=>text_rows.length,
  'dialogue_lines'=>text_rows.sum{|r| Array(r['lines']).length},
  'choice_blocks'=>choice_rows.length,
  'dialogue_chars'=>texts.sum(&:length),
  'choice_options'=>choice_rows.sum{|r| Array(r['choices']).length},
  'unique_dialogue_blocks'=>unique_count,
  'duplicate_dialogue_blocks'=>duplicate_count,
  'unique_text_blocks'=>unique_count,
  'duplicate_text_blocks'=>duplicate_count,
  'duplicate_dialogue_ratio'=>texts.empty? ? 0.0 : (duplicate_count.to_f/texts.length).round(4),
  'errors'=>errors
}
out={'schema'=>'fangame-dialogue-v2','summary'=>summary,'rows'=>rows}
json=JSON.pretty_generate(out)
opts[:out] ? File.write(opts[:out],json) : puts(json)
