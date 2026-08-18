#!/usr/bin/env ruby
require 'json'
require 'optparse'
require_relative 'rpgmaker_marshal_lib'

opts={}
OptionParser.new{|o| o.on('--out PATH'){|v| opts[:out]=v}}.parse!
root=ARGV.shift or abort 'usage: rpgmaker_map_graph.rb GAME_ROOT --out FILE'
nodes={}; edges=[]; switch_reads=Hash.new{|h,k|h[k]=[]}; switch_writes=Hash.new{|h,k|h[k]=[]}; variable_reads=Hash.new{|h,k|h[k]=[]}; variable_writes=Hash.new{|h,k|h[k]=[]}; errors=[]

def cond_refs(pg)
  c=iv(pg,:@condition,nil); refs={'switches'=>[],'variables'=>[]}; return refs unless c
  refs['switches'] << iv(c,:@switch1_id,nil) if iv(c,:@switch1_valid,false)
  refs['switches'] << iv(c,:@switch2_id,nil) if iv(c,:@switch2_valid,false)
  refs['variables'] << iv(c,:@variable_id,nil) if iv(c,:@variable_valid,false)
  refs.each_value do |v|
    v.compact!
    v.uniq!
  end
  refs
end

map_files_for(root).each do |f|
  map,err=rpg_mload(f)
  unless map
    errors << "#{File.basename(f)}: #{err}"; next
  end
  mid=map_id_from_file(f); events=iv(map,:@events,{}) || {}; events=events.values if events.respond_to?(:values)
  nodes[mid]={'map_id'=>mid,'event_count'=>Array(events).compact.length,'width'=>iv(map,:@width,nil),'height'=>iv(map,:@height,nil)}
  Array(events).compact.each do |ev|
    eid=iv(ev,:@id,nil)
    Array(iv(ev,:@pages,[])).compact.each_with_index do |pg,pidx|
      cref=cond_refs(pg)
      cref['switches'].each{|sid| switch_reads[sid] << {'map_id'=>mid,'event_id'=>eid,'page_id'=>pidx+1,'source'=>'page_condition'}}
      cref['variables'].each{|vid| variable_reads[vid] << {'map_id'=>mid,'event_id'=>eid,'page_id'=>pidx+1,'source'=>'page_condition'}}
      Array(iv(pg,:@list,[])).each_with_index do |cmd,cidx|
        code=iv(cmd,:@code,0).to_i; p=iv(cmd,:@parameters,[])
        case code
        when 201
          dest=(p[0].to_i==0 ? p[1].to_i : nil) rescue nil
          edges << {'type'=>'transfer','from_map'=>mid,'to_map'=>dest,'event_id'=>eid,'page_id'=>pidx+1,'command_index'=>cidx,'raw_parameters'=>p.map{|x| x.is_a?(String) ? utf8(x) : x}} if dest && dest>0
        when 121
          first=p[0].to_i; last=p[1].to_i
          (first..last).each{|sid| switch_writes[sid] << {'map_id'=>mid,'event_id'=>eid,'page_id'=>pidx+1,'command_index'=>cidx,'value'=>p[2]}}
        when 122
          first=p[0].to_i; last=p[1].to_i
          (first..last).each{|vid| variable_writes[vid] << {'map_id'=>mid,'event_id'=>eid,'page_id'=>pidx+1,'command_index'=>cidx,'operation'=>p[2],'operand_type'=>p[3]}}
        when 111
          kind=p[0].to_i rescue -1
          if [0,1].include?(kind)
            id=p[1].to_i rescue nil
            bucket=(kind==0 ? switch_reads : variable_reads)
            bucket[id] << {'map_id'=>mid,'event_id'=>eid,'page_id'=>pidx+1,'command_index'=>cidx,'source'=>'conditional_branch'} if id && id>0
          end
        end
      end
    end
  end
end

indeg=Hash.new(0); outdeg=Hash.new(0)
edges.each{|e| next unless e['to_map']; outdeg[e['from_map']]+=1; indeg[e['to_map']]+=1}
map_ids=nodes.keys.sort
hub_candidates=map_ids.map{|id| [id,indeg[id]+outdeg[id]]}.sort_by{|x|-x[1]}.first(20).map{|id,d| {'map_id'=>id,'degree'=>d,'in_degree'=>indeg[id],'out_degree'=>outdeg[id]}}
terminal=map_ids.select{|id| outdeg[id]==0}
branching=map_ids.select{|id| outdeg[id]>=2}
reciprocal=edges.count{|e| e['to_map'] && edges.any?{|r| r['from_map']==e['to_map'] && r['to_map']==e['from_map']}}
summary={
  'map_nodes'=>nodes.length,'transfer_edges'=>edges.length,'branching_maps'=>branching.length,'terminal_maps'=>terminal.length,
  'hub_candidates'=>hub_candidates,'reciprocal_edge_count'=>reciprocal,
  'switch_ids_read'=>switch_reads.keys.compact.length,'switch_ids_written'=>switch_writes.keys.compact.length,
  'variable_ids_read'=>variable_reads.keys.compact.length,'variable_ids_written'=>variable_writes.keys.compact.length,
  'errors'=>errors
}
out={'schema'=>'fangame-map-graph-v1','summary'=>summary,'nodes'=>nodes.values.sort_by{|n|n['map_id']},'edges'=>edges,'switch_reads'=>switch_reads,'switch_writes'=>switch_writes,'variable_reads'=>variable_reads,'variable_writes'=>variable_writes}
json=JSON.pretty_generate(out)
opts[:out] ? File.write(opts[:out],json) : puts(json)
