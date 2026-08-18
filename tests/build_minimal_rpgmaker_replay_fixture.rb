#!/usr/bin/env ruby
require 'fileutils'

module RPG; end

def klass(path)
  cur=Object
  path.split('::').reject(&:empty?).each do |name|
    cur = if cur.const_defined?(name,false)
      cur.const_get(name,false)
    else
      k=Class.new; cur.const_set(name,k); k
    end
  end
  cur
end

%w[
RPG::Map RPG::MapInfo RPG::Event RPG::Event::Page RPG::Event::Page::Condition RPG::EventCommand
RPG::CommonEvent RPG::System RPG::Enemy RPG::Item RPG::Weapon RPG::Armor RPG::Class RPG::Actor
].each{|x| klass(x)}

def obj(k, **ivs)
  o=k.new
  ivs.each{|name,value| o.instance_variable_set("@#{name}",value)}
  o
end

def cmd(code,params=[])
  obj(RPG::EventCommand,code:code,parameters:params,indent:0)
end

def condition(switch_id=nil)
  obj(RPG::Event::Page::Condition,
      switch1_valid:!switch_id.nil?,switch1_id:(switch_id||1),
      switch2_valid:false,switch2_id:1,
      variable_valid:false,variable_id:1,variable_value:0,
      self_switch_valid:false,self_switch_ch:'A',item_valid:false,item_id:1,actor_valid:false,actor_id:1)
end

def page(commands,switch_id=nil)
  obj(RPG::Event::Page,condition:condition(switch_id),list:commands)
end

def event(id,name,pages)
  obj(RPG::Event,id:id,name:name,x:1,y:1,pages:pages)
end

def map(events,encounters=[],step=30)
  obj(RPG::Map,events:events,encounter_list:encounters,encounter_step:step,width:20,height:15)
end

def dump(path,value)
  File.binwrite(path,Marshal.dump(value))
end

root=ARGV.shift or abort 'usage: build_minimal_rpgmaker_replay_fixture.rb OUTDIR'
root=File.expand_path(root)
data=File.join(root,'Data')
FileUtils.mkdir_p(data)
File.write(File.join(root,'Game.ini'),"[Game]\nLibrary=RGSS202E.dll\nScripts=Data\\Scripts.rvdata\nTitle=Replay Fixture\nRTP=\n")
File.binwrite(File.join(root,'Game.exe'),"MZREPLAYFIXTURE")

map1_commands=[
  cmd(101,['Please help with the replay quest.']),
  cmd(102,[['Accept','Decline'],0]),
  cmd(121,[5,5,0]),
  cmd(125,[0,0,100]),
  cmd(126,[1,0,0,1]),
  cmd(201,[0,2,5,5,2,0])
]
map2_commands=[
  cmd(101,['Quest complete. Reward received.']),
  cmd(301,[0,1,true,false]),
  cmd(302,[1,0,0,0]),
  cmd(314,[]),
  cmd(315,[0,1,0,0,50]),
  cmd(121,[6,6,0]),
  cmd(201,[0,1,2,2,2,0])
]

dump(File.join(data,'Map001.rvdata'),map({1=>event(1,'Quest giver',[page(map1_commands)])},[1],20))
dump(File.join(data,'Map002.rvdata'),map({2=>event(2,'Quest target',[page(map2_commands,5)])},[1],25))
dump(File.join(data,'MapInfos.rvdata'),{
  1=>obj(RPG::MapInfo,name:'Start Town',parent_id:0,order:1,expanded:true,scroll_x:0,scroll_y:0),
  2=>obj(RPG::MapInfo,name:'Replay Cave',parent_id:0,order:2,expanded:true,scroll_x:0,scroll_y:0)
})
dump(File.join(data,'System.rvdata'),obj(RPG::System,start_map_id:1,start_x:1,start_y:1))
dump(File.join(data,'CommonEvents.rvdata'),[nil,obj(RPG::CommonEvent,id:1,name:'Reward helper',trigger:0,switch_id:1,list:[cmd(125,[0,0,50])])])
dump(File.join(data,'Enemies.rvdata'),[nil,obj(RPG::Enemy,id:1,name:'Slime',exp:50,gold:20)])
dump(File.join(data,'Items.rvdata'),[nil,obj(RPG::Item,id:1,name:'Potion',price:100)])
dump(File.join(data,'Weapons.rvdata'),[nil,obj(RPG::Weapon,id:1,name:'Sword',price:300)])
dump(File.join(data,'Armors.rvdata'),[nil,obj(RPG::Armor,id:1,name:'Armor',price:500)])
dump(File.join(data,'Classes.rvdata'),[nil,obj(RPG::Class,id:1,name:'Hero',exp_basis:300,exp_inflation:35)])
dump(File.join(data,'Actors.rvdata'),[nil,obj(RPG::Actor,id:1,name:'Tester',initial_level:1,final_level:99,exp_basis:500,exp_inflation:45)])
dump(File.join(data,'Skills.rvdata'),[nil])
dump(File.join(data,'States.rvdata'),[nil])
dump(File.join(data,'Troops.rvdata'),[nil])

puts root
