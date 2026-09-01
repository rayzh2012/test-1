using System;
using System.Collections;
using System.Collections.Generic;

namespace UnityEngine
{
    public class Object
    {
        public static void Destroy(Object obj) { }
    }

    public class GameObject : Object
    {
        public string name { get; set; }
        public static GameObject CreatePrimitive(PrimitiveType type) => new GameObject();
        public T GetComponent<T>() where T : class => default;
        public T AddComponent<T>() where T : class, new() => new T();
    }

    public class Collider : Object { }

    public class Light : Object
    {
        public LightType type { get; set; }
        public float range { get; set; }
        public float intensity { get; set; }
    }

    public enum PrimitiveType { Sphere }
    public enum LightType { Point }

    public readonly struct Vector3
    {
        public readonly float x;
        public readonly float y;
        public readonly float z;

        public Vector3(float x, float y, float z)
        {
            this.x = x;
            this.y = y;
            this.z = z;
        }

        public static Vector3 zero => new(0f, 0f, 0f);
        public static Vector3 one => new(1f, 1f, 1f);
        public static Vector3 up => new(0f, 1f, 0f);
        public static Vector3 operator +(Vector3 left, Vector3 right) =>
            new(left.x + right.x, left.y + right.y, left.z + right.z);
        public static Vector3 operator *(Vector3 value, float scale) =>
            new(value.x * scale, value.y * scale, value.z * scale);
    }

    public sealed class WaitForSeconds
    {
        public WaitForSeconds(float seconds) { }
    }
}

namespace Engine.Core.Abstraction
{
    using UnityEngine;

    public interface ITransform
    {
        Vector3 Position { get; set; }
        Vector3 LocalPosition { get; set; }
        Vector3 LocalScale { get; set; }
    }

    public interface IGameEntity
    {
        ITransform Transform { get; }
        bool IsNativeObjectDisposed { get; }
        void SetParent(IGameEntity parent, bool worldPositionStays);
        void Destroy();
    }
}

namespace Engine.Core.Implementation
{
    using Engine.Core.Abstraction;
    using UnityEngine;

    public sealed class StubTransform : ITransform
    {
        public Vector3 Position { get; set; }
        public Vector3 LocalPosition { get; set; }
        public Vector3 LocalScale { get; set; }
    }

    public sealed class GameEntity : IGameEntity
    {
        public GameEntity(GameObject gameObject) { }
        public ITransform Transform { get; } = new StubTransform();
        public bool IsNativeObjectDisposed => false;
        public void SetParent(IGameEntity parent, bool worldPositionStays) { }
        public void Destroy() { }
    }

    public static class GameEntityFactory
    {
        public static IGameEntity Create(
            string name,
            object prefab,
            IGameEntity parent,
            bool worldPositionStays = false) => new GameEntity(new GameObject());
    }
}

namespace Engine.Animation
{
    using System.Collections;
    using Engine.Core.Abstraction;
    using UnityEngine;

    public static class CoreAnimation
    {
        public static IEnumerator MoveAsync(
            this ITransform target,
            Vector3 toPosition,
            float duration)
        {
            yield break;
        }
    }
}

namespace Engine.Extensions
{
    public static class StubExtensions { }
}

namespace Engine.Logging
{
    public static class EngineLogger
    {
        public static void Log(string message) { }
        public static void LogWarning(string message) { }
    }
}

namespace Pal3.Core.Command.SceCommands
{
    public sealed class PlaySfxCommand
    {
        public PlaySfxCommand(string sfxName, int count) { }
    }
}

namespace Pal3.Core.Contract.Constants
{
    public static class EffectConstants
    {
        public static readonly Dictionary<int, string> EffectSfxInfo = new();
    }
}

namespace Pal3.Core.Contract.Enums
{
    public enum ElementPosition
    {
        AllyWater,
        EnemyWater,
    }
}

namespace Pal3.Game.Data
{
    public sealed class GameResourceProvider
    {
        public IEnumerator PreLoadVfxEffectAsync(int effectGroupId)
        {
            yield break;
        }

        public object GetVfxEffectPrefab(int effectGroupId) => null;
    }
}

namespace Pal3.Game.GameSystems.Combat.Domain
{
    public enum SkillVisualArchetype
    {
        Projectile,
    }

    public enum CombatEventKind
    {
        SkillCast,
        Damage,
        TargetDefeated,
    }
}

namespace Pal3.Game.GameSystems.Combat.Presentation
{
    using global::Pal3.Game.GameSystems.Combat.Domain;

    public enum SkillPresentationCueKind
    {
        Cast,
        Travel,
        Impact,
        TargetDefeated,
    }

    public readonly struct SkillPresentationCue
    {
        public SkillPresentationCueKind Kind { get; }
        public CombatEventKind? TriggerEventKind { get; }
        public int ResolvedAmount { get; }

        public SkillPresentationCue(
            SkillPresentationCueKind kind,
            CombatEventKind? triggerEventKind,
            int resolvedAmount = 0)
        {
            Kind = kind;
            TriggerEventKind = triggerEventKind;
            ResolvedAmount = resolvedAmount;
        }
    }

    public sealed class SkillPresentationPlan
    {
        public uint SkillId { get; }
        public SkillVisualArchetype Archetype { get; }
        public string VisualProfileKey { get; }
        public IReadOnlyList<SkillPresentationCue> Cues { get; }

        public SkillPresentationPlan(
            uint skillId,
            SkillVisualArchetype archetype,
            string visualProfileKey,
            IEnumerable<SkillPresentationCue> cues)
        {
            SkillId = skillId;
            Archetype = archetype;
            VisualProfileKey = visualProfileKey;
            Cues = new List<SkillPresentationCue>(cues);
        }
    }
}

namespace Pal3.Game.GameSystems.Combat.Actor.Controllers
{
    using System.Collections;
    using Engine.Core.Abstraction;
    using Engine.Core.Implementation;

    public sealed class CombatActorController
    {
        public IGameEntity GameEntity { get; } = new GameEntity(new UnityEngine.GameObject());
        public ITransform Transform => GameEntity.Transform;

        public IEnumerator StartMagicCastAsync()
        {
            yield break;
        }

        public IEnumerator StartHitReactionAsync()
        {
            yield break;
        }
    }
}

namespace Pal3.Game.GameSystems.Combat.Scene
{
    using Engine.Core.Abstraction;
    using Engine.Core.Implementation;
    using global::Pal3.Core.Contract.Enums;
    using global::Pal3.Game.GameSystems.Combat.Actor.Controllers;

    public sealed class CombatScene
    {
        public IGameEntity GameEntity { get; } = new GameEntity(new UnityEngine.GameObject());
        public CombatActorController GetCombatActorController(ElementPosition position) => new();
    }
}

namespace Pal3.Game
{
    using System.Collections;

    public sealed class Pal3
    {
        public static Pal3 Instance { get; } = new();
        public object StartCoroutine(IEnumerator routine) => new object();
        public void Execute(object command) { }
    }
}
