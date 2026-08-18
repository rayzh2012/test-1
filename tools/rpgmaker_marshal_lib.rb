#!/usr/bin/env ruby
# Shared Marshal loader/helpers for XP/VX/VX Ace static mining.
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

def ensure_rpg_class(path)
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
RPG::Map RPG::MapInfo RPG::Event RPG::Event::Page RPG::Event::Page::Condition RPG::Event::Page::Graphic
RPG::EventCommand RPG::MoveRoute RPG::MoveCommand RPG::AudioFile RPG::BGM RPG::BGS RPG::ME RPG::SE
RPG::System RPG::System::Words RPG::System::Terms RPG::System::Vehicle RPG::System::TestBattler
RPG::Actor RPG::Class RPG::Skill RPG::Item RPG::Weapon RPG::Armor RPG::Enemy RPG::Enemy::Action
RPG::Troop RPG::Troop::Member RPG::Troop::Page RPG::Troop::Page::Condition RPG::State RPG::Animation
RPG::Animation::Frame RPG::Animation::Timing RPG::Tileset RPG::CommonEvent RPG::BaseItem RPG::BaseItem::Feature
RPG::UsableItem RPG::UsableItem::Effect RPG::EquipItem
].each { |n| ensure_rpg_class(n) }

def rpg_mload(path)
  data=File.binread(path)
  60.times do
    begin
      return Marshal.load(data), nil
    rescue ArgumentError, NameError => e
      m=e.message.match(/undefined class\/module ([A-Za-z0-9_:]+)/)
      if m
        ensure_rpg_class(m[1]); next
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

def utf8(v)
  return '' if v.nil?
  v.to_s.encode('UTF-8',invalid: :replace,undef: :replace,replace: '')
rescue
  v.to_s
end

def data_dir_for(root)
  File.join(root,'Data')
end

def map_files_for(root)
  %w[Map*.rxdata Map*.rvdata Map*.rvdata2].flat_map{|g| Dir[File.join(data_dir_for(root),g)]}.uniq.sort
end

def common_events_file(root)
  Dir[File.join(data_dir_for(root),'CommonEvents.*data*')].first
end

def map_id_from_file(path)
  File.basename(path)[/Map(\d+)/,1].to_i
end
