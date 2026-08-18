#!/usr/bin/env ruby
require 'json'
require 'tmpdir'
require 'fileutils'
require 'open3'

ROOT=File.expand_path('..',__dir__)
PROBE=File.join(ROOT,'tools','rpgmaker_progression_probe.rb')

module RPG; end
%w[Map Event EventCommand Enemy Item Weapon Armor Class Actor CommonEvent].each do |name|
  RPG.const_set(name,Class.new) unless RPG.const_defined?(name,false)
end
RPG::Event.const_set('Page',Class.new) unless RPG::Event.const_defined?('Page',false)

def obj(klass, **ivs)
  o=klass.new
  ivs.each{|k,v| o.instance_variable_set("@#{k}",v)}
  o
end

def cmd(code, params=[])
  obj(RPG::EventCommand, code:code, parameters:params, indent:0)
end

def page(commands)
  obj(RPG::Event::Page,list:commands)
end

def event(id,pages)
  obj(RPG::Event,id:id,pages:pages)
end

def map(encounters,step,events)
  obj(RPG::Map,encounter_list:encounters,encounter_step:step,events:events)
end

def dump(path,obj)
  File.binwrite(path,Marshal.dump(obj))
end

def assert(cond,msg)
  raise "ASSERTION FAILED: #{msg}" unless cond
end

Dir.mktmpdir('rpgmaker-progression-fixture') do |td|
  data=File.join(td,'Game','Data'); FileUtils.mkdir_p(data)

  commands=[
    cmd(301,[0,1,true,false]),
    cmd(302,[1,0,0,0]),
    cmd(314,[]),
    cmd(125,[0,0,100]),
    cmd(126,[1,0,0,1]),
    cmd(127,[1,1,0,1]),
    cmd(201,[0,2,3,4,2,0])
  ]
  dump(File.join(data,'Map001.rvdata'),map([1],20,{1=>event(1,[page(commands)])}))
  dump(File.join(data,'Map002.rvdata'),map([],30,{}))

  dump(File.join(data,'Enemies.rvdata'),[
    nil,
    obj(RPG::Enemy,exp:50,gold:20),
    obj(RPG::Enemy,exp:100,gold:40)
  ])
  dump(File.join(data,'Items.rvdata'),[
    nil,obj(RPG::Item,price:100),obj(RPG::Item,price:200)
  ])
  dump(File.join(data,'Weapons.rvdata'),[
    nil,obj(RPG::Weapon,price:300)
  ])
  dump(File.join(data,'Armors.rvdata'),[
    nil,obj(RPG::Armor,price:500)
  ])
  dump(File.join(data,'Classes.rvdata'),[
    nil,obj(RPG::Class,exp_basis:300,exp_inflation:35)
  ])
  dump(File.join(data,'Actors.rvdata'),[
    nil,obj(RPG::Actor,initial_level:1,final_level:99)
  ])
  dump(File.join(data,'CommonEvents.rvdata'),[
    nil,obj(RPG::CommonEvent,id:1,list:[cmd(315,[0,1,0,0,50])])
  ])

  out=File.join(td,'progression.json')
  stdout,stderr,status=Open3.capture3('ruby',PROBE,File.join(td,'Game'),'--out',out)
  raise "probe failed: #{stdout}\n#{stderr}" unless status.success?
  g=JSON.parse(File.read(out,encoding:'UTF-8'))
  o=g.fetch('observed'); c=o.fetch('event_commands'); d=g.fetch('derived')

  assert(g['evidence_version']=='rpgmaker.progression.v0.5a','evidence version')
  assert(o['maps_loaded']==2,'maps loaded')
  assert(o['maps_with_random_encounters']==1,'random encounter maps')
  assert((o['random_encounter_map_ratio']-0.5).abs<1e-9,'random encounter ratio')
  assert(o['encounter_step_stats']['median']==20.0,'encounter step median only on encounter maps')
  assert(o['enemy_count']==2,'enemy count')
  assert(o['enemy_exp_stats']['median']==75.0,'enemy exp median')
  assert(o['enemy_gold_stats']['median']==30.0,'enemy gold median')
  assert(o['equipment_price_stats']['median']==400.0,'equipment median price')
  assert(o['class_exp_basis_stats']['median']==300.0,'class exp basis')
  assert(o['actor_initial_level_stats']['median']==1.0,'initial level')
  assert(o['actor_final_level_stats']['median']==99.0,'final level')

  assert(c['battle_processing_ops']==1,'forced battle')
  assert(c['shop_processing_ops']==1,'shop')
  assert(c['recover_all_ops']==1,'recover all')
  assert(c['change_exp_ops']==1,'common event exp change')
  assert(c['positive_gold_reward_ops']==1,'gold reward')
  assert(c['positive_item_reward_ops']==1,'item reward')
  assert(c['negative_weapon_cost_ops']==1,'weapon removal/cost')
  assert(c['transfer_ops']==1,'transfer')

  assert((d['median_equipment_price_to_enemy_gold_ratio']-(400.0/30.0)).abs<1e-9,'economy proxy')
  assert((d['median_class_exp_basis_to_enemy_exp_ratio']-4.0).abs<1e-9,'progression proxy')
  assert(g['load_errors'].empty?,'load errors')

  puts JSON.pretty_generate({'status'=>'PASS','observed'=>o,'derived'=>d})
end
