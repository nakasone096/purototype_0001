# -*- coding: utf-8 -*-
bl_info = {
    "name": "3DCG Tutorial Simulator",
    "blender": (4, 2, 0),
    "version": (0, 8, 3),
    "author": "Daichi",
    "description": "Interactive 3D learning simulation for Blender (Ch1-6 tutorials + per-participant JSONL logging + CSV export + DIR_PATH w/ safe buttons; Ch6 Stage1 only w/ auto camera+sun on setup)",
    "category": "Education",
    "support": "COMMUNITY",
}

import bpy
import bmesh
import math
import time
import json
import os
import csv
import subprocess
import sys
from mathutils import Vector
from bpy.types import Operator, Panel, PropertyGroup
from bpy.props import (
    IntProperty,
    BoolProperty,
    FloatVectorProperty,
    FloatProperty,
    CollectionProperty,
    StringProperty,
    EnumProperty,
)

# =====================================================
# REFERENCE IMAGE SETTINGS
# ファイル名を変更したい場合はここだけ編集してください
# 拡張子なしで書くと .png / .jpg / .jpeg を自動検索します
# =====================================================

REFERENCE_IMAGE_FILENAME = "fruit_apple"
REFERENCE_IMAGE_LOCATION  = (1.6, 2.2, 0.0)
REFERENCE_IMAGE_ROTATION_DEG = (90.0, 0.0, 90.0)
REFERENCE_IMAGE_DISPLAY_SIZE  = 2.0

# =====================================================
# SHORTCUT TABLE
# (intro_ch, intro_st, section, action, keys)
# intro_ch/st = そのショートカットが初登場するステージ
# =====================================================

SHORTCUT_TABLE = [
    # --- Ch1: 基本操作 ---
    (1, 1, "基本操作", "選択",              "左クリック"),
    (1, 1, "基本操作", "確定",              "Enter"),
    (1, 1, "基本操作", "キャンセル",         "右クリック / Esc"),
    (1, 2, "基本操作", "移動",              "G"),
    (1, 2, "基本操作", "軸固定移動",         "G → X/Y/Z → 数字 → Enter"),
    (1, 3, "基本操作", "回転",              "R"),
    (1, 3, "基本操作", "軸固定回転",         "R → X/Y/Z → 角度 → Enter"),
    (1, 4, "基本操作", "拡大縮小",           "S → 数字 → Enter"),
    # --- Ch2: ビュー操作 ---
    (2, 1, "ビュー操作", "ビュー回転",       "中ボタン ドラッグ"),
    (2, 1, "ビュー操作", "パン",             "Shift + 中ボタン"),
    (2, 2, "ビュー操作", "ズーム",           "ホイール スクロール"),
    (2, 4, "ビュー操作", "正面 / 側面 / 上面", "テンキー 1 / 3 / 7"),
    # --- Ch3: オブジェクト操作 + モデリング ---
    (3, 1, "オブジェクト", "追加",           "Shift + A"),
    (3, 2, "オブジェクト", "元に戻す",        "Ctrl + Z"),
    (3, 2, "オブジェクト", "やり直し",        "Ctrl + Shift + Z"),
    (3, 3, "オブジェクト", "削除",           "X / Delete"),
    (3, 4, "モデリング",   "エディットモード",  "Tab"),
    (3, 5, "モデリング",   "頂点選択",        "1"),
    (3, 6, "モデリング",   "エッジ選択",      "2"),
    (3, 7, "モデリング",   "フェース選択",     "3"),
    (3, 8, "モデリング",   "押し出し",        "E"),
    (3, 9, "モデリング",   "ループカット",     "Ctrl + R"),
    # --- Ch4: モディファイアー ---
    (4, 1, "モディファイアー", "モディファイアー追加", "プロパティ → レンチアイコン → 追加"),
    (4, 1, "モディファイアー", "適用",               "モディファイアー → 適用"),
    # --- Ch5: スカルプト ---
    (5, 1, "スカルプト",  "ブラシサイズ",     "F → ドラッグ"),
    (5, 1, "スカルプト",  "強さ調整",         "Shift + F → ドラッグ"),
    (5, 1, "スカルプト",  "反転（凹み）",      "Ctrl + ドラッグ"),
    # --- Ch6: マテリアル ---
    (6, 1, "マテリアル",  "ノード追加",       "Shift + A（ノードエディター内）"),
    (6, 1, "マテリアル",  "ノード削除",       "X（ノードエディター内）"),
]

# =====================================================
# VERTEX POSITION STORAGE
# =====================================================

class VertexPos(PropertyGroup):
    """Store vertex position for comparison"""
    co: FloatVectorProperty(size=3)

# =====================================================
# RESEARCH DATA STORAGE (SESSION-IN-MEMORY)
# =====================================================

class StageRun(PropertyGroup):
    chapter: IntProperty(default=1, min=1, max=7)
    stage: IntProperty(default=1, min=1, max=10)

    completed: BoolProperty(default=False)
    last_reason: StringProperty(default="")
    last_message: StringProperty(default="")

    failed_count: IntProperty(default=0, min=0)
    stalled_seconds: FloatProperty(default=0.0, min=0.0)

    started_at: FloatProperty(default=0.0)
    ended_at: FloatProperty(default=0.0)

# =====================================================
# STAGE MANAGER
# =====================================================

class StageManager:
    # -----------------------------
    # Time/helpers
    # -----------------------------
    @staticmethod
    def _now():
        return time.time()

    @staticmethod
    def degrees_to_radians_xyz(deg_xyz):
        return tuple(math.radians(v) for v in deg_xyz)

    @staticmethod
    def vec_dist(a, b):
        return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(3)))

    # -----------------------------
    # Windows-safe log dir helpers
    # -----------------------------
    @staticmethod
    def default_log_dir() -> str:
        if os.name == "nt":
            return r"C:\temp\tutorial_logs\\"
        return os.path.join("~", "tutorial_logs") + os.sep

    @staticmethod
    def ensure_dir_exists(path: str) -> str:
        abs_path = bpy.path.abspath(path)
        os.makedirs(abs_path, exist_ok=True)
        return abs_path

    @staticmethod
    def open_folder_in_os(path: str):
        abs_path = StageManager.ensure_dir_exists(path)
        if os.name == "nt":
            os.startfile(abs_path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", abs_path])
        else:
            subprocess.Popen(["xdg-open", abs_path])

    # -----------------------------
    # Participant log (JSONL)
    # -----------------------------
    @staticmethod
    def _safe_participant_id(pid: str) -> str:
        pid = (pid or "").strip()
        if not pid:
            return ""
        allowed = []
        for ch in pid:
            if ch.isalnum() or ch in ("-", "_"):
                allowed.append(ch)
            else:
                allowed.append("_")
        return "".join(allowed)

    @staticmethod
    def get_stall_seconds(context) -> float:
        props = context.scene.tutorial_props
        if props.stage_start_time <= 0.0:
            return 0.0
        return max(0.0, StageManager._now() - props.stage_start_time)

    @staticmethod
    def ensure_participant_log_file(context) -> bool:
        props = context.scene.tutorial_props
        pid = StageManager._safe_participant_id(props.participant_id)

        if not pid:
            props.participant_log_error = "参加者IDが未入力です"
            return False

        if not (props.log_dir or "").strip():
            props.log_dir = StageManager.default_log_dir()

        try:
            dir_abs = StageManager.ensure_dir_exists(props.log_dir)
        except Exception as e:
            props.participant_log_error = f"ログ保存フォルダ作成に失敗: {e}"
            return False

        if props.participant_log_path:
            try:
                existing = bpy.path.abspath(props.participant_log_path)
                if os.path.isfile(existing):
                    props.participant_log_error = ""
                    return True
            except Exception:
                pass

        ts = time.strftime("%Y%m%d_%H%M%S", time.localtime(StageManager._now()))
        log_path = os.path.join(dir_abs, f"{pid}_{ts}.jsonl")

        try:
            with open(log_path, "a", encoding="utf-8") as f:
                # SAFE: bl_info may not exist depending on load/reload context
                _addon_info = globals().get("bl_info", {}) or {}
                f.write(json.dumps({
                    "t": StageManager._now(),
                    "participant_id": pid,
                    "event": "session_start",
                    "blender_version": ".".join(map(str, bpy.app.version)),
                    "addon_version": ".".join(map(str, _addon_info.get("version", (0, 0, 0)))),
                }, ensure_ascii=False) + "\n")

            props.participant_log_path = log_path
            props.participant_log_error = ""
            return True
        except Exception as e:
            props.participant_log_error = f"ログファイル作成に失敗: {type(e).__name__}: {e}"
            return False

    @staticmethod
    def append_participant_event(context, event: dict):
        props = context.scene.tutorial_props
        if not props.enable_participant_logging:
            return
        if not StageManager.ensure_participant_log_file(context):
            return
        try:
            with open(bpy.path.abspath(props.participant_log_path), "a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
        except Exception as e:
            props.participant_log_error = f"ログ書き込みに失敗: {type(e).__name__}: {e}"

    @staticmethod
    def log_setup_event(context):
        props = context.scene.tutorial_props
        pid = StageManager._safe_participant_id(props.participant_id)
        StageManager.append_participant_event(context, {
            "t": StageManager._now(),
            "participant_id": pid,
            "event": "setup",
            "chapter": props.current_chapter,
            "stage": props.current_stage,
            "difficulty_mode": props.difficulty_mode,
        })

    @staticmethod
    def log_validate_event(context, ok: bool, reason: str, message: str, auto: bool = False):
        props = context.scene.tutorial_props
        pid = StageManager._safe_participant_id(props.participant_id)
        StageManager.append_participant_event(context, {
            "t": StageManager._now(),
            "participant_id": pid,
            "event": "validate",
            "chapter": props.current_chapter,
            "stage": props.current_stage,
            "ok": bool(ok),
            "reason": reason or "",
            "message": message or "",
            "fail_count": int(props.failed_validate_count),
            "stall_s": float(props.current_stall_seconds),
            "auto": bool(auto),
        })

    @staticmethod
    def log_navigation_event(context, from_ch: int, from_st: int, to_ch: int, to_st: int, direction: str):
        props = context.scene.tutorial_props
        pid = StageManager._safe_participant_id(props.participant_id)
        StageManager.append_participant_event(context, {
            "t": StageManager._now(),
            "participant_id": pid,
            "event": "navigation",
            "direction": direction,          # "prev" or "next"
            "from_chapter": from_ch,
            "from_stage": from_st,
            "to_chapter": to_ch,
            "to_stage": to_st,
            "difficulty_mode": props.difficulty_mode,
        })

    @staticmethod
    def log_finalize_event(context, completed: bool, stalled_seconds: float):
        props = context.scene.tutorial_props
        pid = StageManager._safe_participant_id(props.participant_id)

        reason_seq = [r for r in (props.reason_sequence or "").split(",") if r]

        time_to_first = None
        if props.first_attempt_time > 0.0 and props.stage_start_time > 0.0:
            time_to_first = round(props.first_attempt_time - props.stage_start_time, 3)

        time_to_success = round(float(stalled_seconds), 3) if completed else None

        StageManager.append_participant_event(context, {
            "t": StageManager._now(),
            "participant_id": pid,
            "event": "finalize",
            "chapter": props.current_chapter,
            "stage": props.current_stage,
            "completed": bool(completed),
            "failed_count": int(props.failed_validate_count),
            "stalled_seconds": float(stalled_seconds),
            "last_reason": props.last_reason or "",
            "last_message": props.last_message or "",
            "stage_started_at": float(props.stage_start_time),
            # 追加フィールド
            "hint_level": min(int(props.failed_validate_count), 3),
            "reason_sequence": reason_seq,
            "setup_count": int(props.setup_count),
            "time_to_first_attempt_s": time_to_first,
            "time_to_success_s": time_to_success,
            "undo_count": int(props.undo_count),
            "survey_difficulty": int(props.survey_difficulty) if props.survey_difficulty > 0 else None,
            "difficulty_mode": props.difficulty_mode,
        })

    # -----------------------------
    # Research metrics (in-memory) + finalize
    # -----------------------------
    @staticmethod
    def finalize_current_run(context, completed: bool):
        props = context.scene.tutorial_props
        if props.stage_start_time <= 0.0:
            return

        now = StageManager._now()
        stalled = max(0.0, now - props.stage_start_time)

        r = props.stage_runs.add()
        r.chapter = props.current_chapter
        r.stage = props.current_stage
        r.completed = bool(completed)
        r.failed_count = int(props.failed_validate_count)
        r.stalled_seconds = float(stalled)
        r.last_reason = props.last_reason or ""
        r.last_message = props.last_message or ""
        r.started_at = float(props.stage_start_time)
        r.ended_at = float(now)

        MAX_RUNS = 500
        if len(props.stage_runs) > MAX_RUNS:
            for _ in range(len(props.stage_runs) - MAX_RUNS):
                props.stage_runs.remove(0)

        StageManager.log_finalize_event(context, completed=completed, stalled_seconds=stalled)

    # -----------------------------
    # Chapter 6: camera + sun + render helper + cleanup
    # -----------------------------
    @staticmethod
    def file_exists_nonempty(path: str) -> bool:
        try:
            return os.path.isfile(path) and os.path.getsize(path) > 0
        except Exception:
            return False

    @staticmethod
    def ensure_camera_for_ch6_stage1(location=(10.0, -4.0, 5), rotation_deg=(63.0, 0.0, 66.0)):
        """Create or replace the scene camera for Chapter 6 Stage 1."""
        for obj in list(bpy.data.objects):
            if obj.type == 'CAMERA':
                bpy.data.objects.remove(obj, do_unlink=True)

        cam_data = bpy.data.cameras.new(name="Ch6_Camera")
        cam_obj = bpy.data.objects.new(name="Ch6_Camera", object_data=cam_data)
        bpy.context.collection.objects.link(cam_obj)
        cam_obj.location = location
        cam_obj.rotation_euler = tuple(math.radians(v) for v in rotation_deg)
        bpy.context.scene.camera = cam_obj
        return cam_obj

    @staticmethod
    def delete_all_lights():
        for obj in list(bpy.data.objects):
            if obj.type == 'LIGHT':
                bpy.data.objects.remove(obj, do_unlink=True)

    @staticmethod
    def create_sun_light(
        name="Ch6_Sun",
        location=(10.0, -4.0, 5),
        rotation_deg=(63.0, 0.0, 66.0),
        energy=10.0,
    ):
        light_data = bpy.data.lights.new(name=name, type='SUN')
        light_data.energy = float(energy)

        light_obj = bpy.data.objects.new(name=name, object_data=light_data)
        bpy.context.collection.objects.link(light_obj)

        light_obj.location = location
        light_obj.rotation_euler = tuple(math.radians(v) for v in rotation_deg)
        light_obj.hide_viewport = False
        light_obj.hide_render = False
        return light_obj

    @staticmethod
    def ensure_sun_for_ch6_stage1(
        location=(10.0, -4.0, 5),
        rotation_deg=(63.0, 0.0, 66.0),
        energy=10.0,
    ):
        StageManager.delete_all_lights()
        return StageManager.create_sun_light(
            name="Ch6_Sun",
            location=location,
            rotation_deg=rotation_deg,
            energy=energy,
        )

    @staticmethod
    def turn_off_scene_camera_and_lights():
        """End-of-session cleanup (do not delete)."""
        scene = bpy.context.scene
        scene.camera = None
        for obj in bpy.data.objects:
            if obj.type == 'LIGHT':
                obj.hide_viewport = True
                obj.hide_render = True

    # -----------------------------
    # Reference image placement (Ch7)
    # -----------------------------
    @staticmethod
    def _find_reference_image_path(filename: str) -> str:
        """拡張子なしでも .png/.jpg/.jpeg を自動検索して絶対パスを返す"""
        addon_dir = os.path.dirname(os.path.abspath(__file__))
        # 拡張子が含まれている場合はそのまま確認
        if os.path.splitext(filename)[1]:
            p = os.path.join(addon_dir, filename)
            return p if os.path.isfile(p) else ""
        # 拡張子なし → 順番に試す
        for ext in (".png", ".jpg", ".jpeg", ".webp"):
            p = os.path.join(addon_dir, filename + ext)
            if os.path.isfile(p):
                return p
        return ""

    @staticmethod
    def place_reference_image():
        """REFERENCE_IMAGE_FILENAME の画像を指定座標に Empty(Image) として配置する"""
        img_path = StageManager._find_reference_image_path(REFERENCE_IMAGE_FILENAME)
        if not img_path:
            print(f"[Tutorial] 参考画像が見つかりません: {REFERENCE_IMAGE_FILENAME}")
            return False

        # 既存の同名 Empty を削除
        for obj in list(bpy.data.objects):
            if obj.name == "Reference_Image" and obj.type == 'EMPTY':
                bpy.data.objects.remove(obj, do_unlink=True)

        bpy.ops.object.empty_add(
            type='IMAGE',
            location=REFERENCE_IMAGE_LOCATION,
        )
        empty = bpy.context.active_object
        empty.name = "Reference_Image"
        empty.rotation_euler = tuple(
            math.radians(v) for v in REFERENCE_IMAGE_ROTATION_DEG
        )
        empty.empty_display_size = REFERENCE_IMAGE_DISPLAY_SIZE

        # 画像をロード（既にロード済みなら再利用）
        img = bpy.data.images.get(os.path.basename(img_path))
        if not img:
            img = bpy.data.images.load(img_path)
        empty.data = img
        print(f"[Tutorial] 参考画像を配置しました: {img_path}")
        return True

    # -----------------------------
    # Scene reset (shared by setup_stage, validate on fail, next_stage)
    # -----------------------------
    @staticmethod
    def reset_scene_for_chapter(context):
        """シーンオブジェクトのみリセット。props の記録値（fail_count等）は触らない。"""
        props = context.scene.tutorial_props
        ch = props.current_chapter

        if ch == 1:
            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.select_all(action='SELECT')
            bpy.ops.object.delete(use_global=False)
            bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
            cube = bpy.context.active_object
            cube.name = "Cube"
            props.initial_position = tuple(cube.location)
            props.initial_rotation = tuple(cube.rotation_euler)
            props.initial_scale = tuple(cube.scale)

        elif ch == 2:
            space = StageManager.get_view3d_space(context)
            if space and space.region_3d:
                props.initial_view_distance = space.region_3d.view_distance
                props.initial_view_location = tuple(space.region_3d.view_location)
                props.initial_view_rotation = tuple(space.region_3d.view_rotation)

        elif ch == 3:
            st = props.current_stage
            try:
                bpy.ops.object.mode_set(mode='OBJECT')
            except Exception:
                pass
            bpy.ops.object.select_all(action='SELECT')
            bpy.ops.object.delete(use_global=False)

            if st == 1:
                # Shift+A ステージ: 何もない状態からスタート
                pass

            elif st == 2:
                # Ctrl+Z ステージ: bpy.ops を使わず直接データ生成（Undoスタックに積まない）
                mesh = bpy.data.meshes.new("Cube")
                bm_tmp = bmesh.new()
                bmesh.ops.create_cube(bm_tmp, size=2.0)
                bm_tmp.to_mesh(mesh)
                bm_tmp.free()
                cube = bpy.data.objects.new("Cube", mesh)
                bpy.context.collection.objects.link(cube)
                bpy.context.view_layer.objects.active = cube
                cube.select_set(True)
                props.initial_position = (0.0, 0.0, 0.0)

            elif st == 3:
                # Delete ステージ: キューブを配置
                bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
                cube = bpy.context.active_object
                cube.name = "Cube"

            else:
                # St4〜: エディットモードへ
                bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
                cube = bpy.context.active_object
                cube.name = "Cube"
                bpy.context.view_layer.objects.active = cube
                cube.select_set(True)
                bpy.ops.object.mode_set(mode='EDIT')
                bpy.context.view_layer.update()
                props.initial_vertex_count = len(cube.data.vertices)
                props.initial_edge_count = len(cube.data.edges)
                props.initial_face_count = len(cube.data.polygons)

        elif ch == 4:
            # 新Ch4: モディファイアー章
            try:
                bpy.ops.object.mode_set(mode='OBJECT')
            except Exception:
                pass
            bpy.ops.object.select_all(action='SELECT')
            bpy.ops.object.delete(use_global=False)

            if props.current_stage == 3:
                # St3 Solidify: トーラスを使用
                bpy.ops.mesh.primitive_torus_add(location=(0, 0, 0))
                obj_new = bpy.context.active_object
                obj_new.name = "Torus"
                obj_new.modifiers.clear()
            else:
                # St1, St2, St4: キューブ
                bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
                obj_new = bpy.context.active_object
                obj_new.name = "Cube"
                obj_new.modifiers.clear()

        elif ch == 5:
            # 旧Ch4: スカルプト
            try:
                bpy.ops.object.mode_set(mode='OBJECT')
            except Exception:
                pass
            bpy.ops.object.select_all(action='SELECT')
            bpy.ops.object.delete(use_global=False)
            bpy.ops.mesh.primitive_uv_sphere_add(radius=1, location=(0, 0, 0))
            sphere = bpy.context.active_object
            sphere.name = "Sphere"
            bpy.context.view_layer.objects.active = sphere
            sphere.select_set(True)
            bpy.ops.object.mode_set(mode='SCULPT')
            props.initial_vertex_positions.clear()
            for v in sphere.data.vertices:
                item = props.initial_vertex_positions.add()
                item.co = v.co.copy()

        elif ch == 6:
            # 旧Ch5: マテリアル
            try:
                bpy.ops.object.mode_set(mode='OBJECT')
            except Exception:
                pass
            bpy.ops.object.select_all(action='SELECT')
            bpy.ops.object.delete(use_global=False)
            bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
            cube = bpy.context.active_object
            cube.name = "Cube"
            space = StageManager.get_view3d_space(context)
            if space:
                space.shading.type = 'MATERIAL'
            StageManager.open_shader_editor_at_bottom()

        elif ch == 7:
            # 最終制作: リンゴを作る
            props.final_render_saved_path = ""

            # シーンをリセットしてリンゴのベース球を配置
            try:
                bpy.ops.object.mode_set(mode='OBJECT')
            except Exception:
                pass
            bpy.ops.object.select_all(action='SELECT')
            bpy.ops.object.delete(use_global=False)

            bpy.ops.mesh.primitive_uv_sphere_add(
                radius=1.0, segments=32, ring_count=16, location=(0, 0, 0)
            )
            apple = bpy.context.active_object
            apple.name = "Apple"
            bpy.ops.object.shade_smooth()

            # カメラ・Sunライトを配置
            StageManager.ensure_camera_for_ch6_stage1(
                location=(10.0, 0.0, 0.0),
                rotation_deg=(90.0, 0.0, 90.0),
            )
            StageManager.ensure_sun_for_ch6_stage1(
                location=(10.0, 0.0, 0.0),
                rotation_deg=(90.0, 0.0, 90.0),
                energy=10.0,
            )
            # 参考画像を配置
            StageManager.place_reference_image()

    # -----------------------------
    # Existing helpers for chapters 1-5
    # -----------------------------
    @staticmethod
    def open_shader_editor_at_bottom():
        try:
            context = bpy.context

            # すでにシェーダーエディターがあれば何もしない
            for area in context.screen.areas:
                if area.type == 'NODE_EDITOR':
                    for sp in area.spaces:
                        if sp.type == 'NODE_EDITOR' and sp.tree_type == 'ShaderNodeTree':
                            return True

            view_area = None
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    view_area = area
                    break
            if not view_area:
                return False

            # WINDOW リージョンを取得
            region = next(
                (r for r in view_area.regions if r.type == 'WINDOW'),
                view_area.regions[-1]
            )

            # 分割前の高さを記録（分割後に新エリアを高さで特定するため）
            original_height = view_area.height

            with context.temp_override(
                window=context.window,
                screen=context.screen,
                area=view_area,
                region=region,
            ):
                bpy.ops.screen.area_split(direction='HORIZONTAL', factor=0.65)

            # 新エリアの特定:
            # factor=0.65 → 下エリアは元の高さの約35%
            # 元の高さの半分より小さい VIEW_3D が新エリア
            new_area = None
            for area in context.screen.areas:
                if area.type == 'VIEW_3D' and area.height < original_height * 0.5:
                    new_area = area
                    break

            if not new_area:
                return False

            # NODE_EDITOR（シェーダーエディター）に変更
            new_area.type = 'NODE_EDITOR'
            new_area.ui_type = 'ShaderNodeTree'
            for sp in new_area.spaces:
                if sp.type == 'NODE_EDITOR':
                    sp.tree_type = 'ShaderNodeTree'
                    break
            return True
        except Exception as e:
            print(f"[Tutorial] open_shader_editor_at_bottom error: {e}")
            return False

    @staticmethod
    def find_cube():
        for obj in bpy.data.objects:
            if obj.type == 'MESH' and obj.name == "Cube":
                return obj
        return None

    @staticmethod
    def find_sphere():
        for obj in bpy.data.objects:
            if obj.type == 'MESH' and obj.name == "Sphere":
                return obj
        return None

    @staticmethod
    def get_view3d_space(context):
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                for space in area.spaces:
                    if space.type == 'VIEW_3D':
                        return space
        return None

    @staticmethod
    def get_bm(obj):
        if not obj or obj.type != 'MESH':
            return None
        if bpy.context.mode != 'EDIT_MESH':
            return None
        return bmesh.from_edit_mesh(obj.data)

    @staticmethod
    def get_mesh_select_mode(context):
        try:
            ts = context.tool_settings
            mode = getattr(ts, "mesh_select_mode", None) if ts else None
            return tuple(mode) if mode else (False, False, False)
        except Exception:
            return (False, False, False)

    @staticmethod
    def is_in_sculpt_mode():
        return bpy.context.mode == 'SCULPT'

    @staticmethod
    def get_current_brush_name():
        try:
            s = bpy.context.tool_settings.sculpt
            return s.brush.name if s and s.brush else None
        except Exception:
            return None

    @staticmethod
    def is_brush_type_selected(brush_type_name):
        bn = StageManager.get_current_brush_name()
        return bool(bn and brush_type_name in bn)

    @staticmethod
    def get_vertex_deformation_amount(sphere, initial_positions):
        """Crash-safe deformation detection."""
        try:
            if not sphere or not sphere.data or not sphere.data.vertices:
                return 0, 0.0
            if initial_positions is None:
                return 0, 0.0

            moved = 0
            total = 0.0
            compare_count = min(len(sphere.data.vertices), len(initial_positions))

            for i in range(compare_count):
                try:
                    v = sphere.data.vertices[i]
                    init = Vector(initial_positions[i].co)
                    dist = (v.co - init).length
                    if dist > 0.001:
                        moved += 1
                        total += dist
                except Exception:
                    continue

            return moved, total
        except Exception:
            return 0, 0.0

    @staticmethod
    def get_active_material(obj):
        if not obj or not obj.material_slots:
            return None
        return obj.active_material

    @staticmethod
    def get_principled_bsdf(material):
        if not material or not material.use_nodes:
            return None
        for node in material.node_tree.nodes:
            if node.type == 'BSDF_PRINCIPLED':
                return node
        return None

    @staticmethod
    def check_image_texture_node_exists(obj):
        mat = StageManager.get_active_material(obj)
        if not mat or not mat.use_nodes:
            return False
        return any(n.type == 'TEX_IMAGE' and n.image for n in mat.node_tree.nodes)

    @staticmethod
    def check_correct_node_link(obj):
        mat = StageManager.get_active_material(obj)
        if not mat or not mat.use_nodes:
            return False

        tex = None
        bsdf = None
        for n in mat.node_tree.nodes:
            if n.type == 'TEX_IMAGE':
                tex = n
            if n.type == 'BSDF_PRINCIPLED':
                bsdf = n
        if not tex or not bsdf:
            return False

        for link in mat.node_tree.links:
            if link.from_node == tex and link.to_node == bsdf:
                if link.from_socket.name == 'Color' and link.to_socket.name == 'Base Color':
                    return True
        return False

    # -----------------------------
    # Shortcut accumulation
    # -----------------------------
    @staticmethod
    def get_accumulated_shortcuts(chapter, stage):
        """
        Returns:
            current_new : [(action, keys)]  今のステージで初登場のショートカット
            all_sections: {section: [(action, keys), ...]}  これまで全累積
        """
        from collections import OrderedDict
        current_new = []
        all_sections = OrderedDict()

        for (intro_ch, intro_st, section, action, keys) in SHORTCUT_TABLE:
            if (intro_ch, intro_st) > (chapter, stage):
                continue
            if section not in all_sections:
                all_sections[section] = []
            all_sections[section].append((action, keys))
            if intro_ch == chapter and intro_st == stage:
                current_new.append((action, keys))

        return current_new, all_sections

    # -----------------------------
    # UI stage descriptions
    # -----------------------------
    @staticmethod
    def get_stage_info(chapter_num, stage_num):
        if chapter_num == 4:
            stages = {
                1: {
                    "title": "第4章: モディファイアー",
                    "name": "ステージ1: サブディビジョンサーフェス",
                    "description": "Subdivision Surface を追加してください",
                    "details": "① 右のプロパティパネルで\n"
                               "   レンチアイコン（モディファイアー）を開く\n"
                               "② 「モディファイアーを追加」\n"
                               "   →「生成」→「サブディビジョンサーフェス」\n"
                               "③ 追加したら数値を確認しよう\n"
                               "\n"
                               "   ・ビューポートのレベル数「2」\n"
                               "     3Dビュー上での分割数\n"
                               "     大きいほど重くなるので注意\n"
                               "\n"
                               "   ・レンダーのレベル数「2」\n"
                               "     レンダリング時の分割数\n"
                               "     高いほどなめらかに仕上がる",
                },
                2: {
                    "title": "第4章: モディファイアー",
                    "name": "ステージ2: ミラー",
                    "description": "Mirror モディファイアーを追加してください（Y軸）",
                    "details": "① キューブを選択してエディットモードへ（Tab）\n"
                               "② Ctrl+R でキューブ中心にループカットを入れる\n"
                               "③ Y座標が負の側の頂点4つをボックス選択\n"
                               "④ X キー →「頂点」で削除\n"
                               "⑤ Tab でオブジェクトモードに戻る\n"
                               "⑥ モディファイアーを追加 →「生成」→「ミラー」\n"
                               "⑦ 「座標軸」を「Y」に変更する\n"
                               "   → 削除した側が自動で補完される！",
                },
                3: {
                    "title": "第4章: モディファイアー",
                    "name": "ステージ3: 厚み付け（Solidify）",
                    "description": "トーラスに Solidify モディファイアーを追加してください",
                    "details": "① トーラス（ドーナツ型）がセットアップされています\n"
                               "② モディファイアーを追加\n"
                               "   →「生成」→「厚み付け」\n"
                               "③ 数値の説明\n"
                               "\n"
                               "   ・幅（厚み）\n"
                               "     面に追加される厚さの量\n"
                               "     値を増やすと厚くなる\n"
                               "\n"
                               "   ・オフセット（-1 〜 +1）\n"
                               "     厚みが付く方向\n"
                               "     -1：内側 / 0：中央 / +1：外側",
                },
                4: {
                    "title": "第4章: モディファイアー",
                    "name": "ステージ4: ベベル（Bevel）",
                    "description": "Bevel モディファイアーを追加してください",
                    "details": "① モディファイアーを追加\n"
                               "   →「生成」→「ベベル」\n"
                               "② 数値の説明\n"
                               "\n"
                               "   ・量（幅）\n"
                               "     角が丸まる大きさ\n"
                               "     値を増やすほど丸みが大きくなる\n"
                               "\n"
                               "   ・セグメント\n"
                               "     丸みを表現する面の分割数\n"
                               "     1：単純な面取り\n"
                               "     3以上：なめらかな丸み",
                },
            }
            return stages.get(stage_num, {})

        if chapter_num == 7:
            return {
                "title": "第7章: 最終制作",
                "name": "ステージ1: リンゴを作ってレンダー保存",
                "description": "参考画像を見ながらリンゴを作り、レンダーを保存してください",
                "details": "参考画像を見ながらリンゴを作ってみてください\n"
                           "\n"
                           "「確認」ボタンを押すたびに\n"
                           "作り方のヒントが1つずつ表示されます\n"
                           "\n"
                           "完成したら F12 でレンダー\n"
                           "→ 画像を保存するとクリアになります\n"
                           "（下の補助ボタンでも保存できます）",
            }

        if chapter_num == 1:
            stages = {
                1: {
                    "title": "第1章: 基本操作",
                    "name": "ステージ1: キューブを選択",
                    "description": "キューブを左クリックで選択してください",
                    "details": "① 3Dビューのキューブを左クリック\n"
                               "② オレンジの枠が表示されたら選択完了\n"
                               "   （何もない場所をクリックすると解除）",
                },
                2: {
                    "title": "第1章: 基本操作",
                    "name": "ステージ2: キューブを移動",
                    "description": "キューブを X 軸方向に +2 移動してください",
                    "details": "① キューブを選択した状態で\n"
                               "② G キーを押す（移動モード）\n"
                               "③ X キーを押す（X軸に固定）\n"
                               "④ 2 と入力して Enter で確定",
                },
                3: {
                    "title": "第1章: 基本操作",
                    "name": "ステージ3: キューブを回転",
                    "description": "X 軸周りに 45 度回転してください",
                    "details": "① キューブを選択した状態で\n"
                               "② R キーを押す（回転モード）\n"
                               "③ X キーを押す（X軸周りに固定）\n"
                               "④ 45 と入力して Enter で確定",
                },
                4: {
                    "title": "第1章: 基本操作",
                    "name": "ステージ4: スケール変更",
                    "description": "キューブのサイズを変更してください",
                    "details": "① キューブを選択した状態で\n"
                               "② S キーを押す（スケールモード）\n"
                               "③ 数字を入力（例: 2 で2倍）\n"
                               "④ Enter で確定\n"
                               "   （軸固定: S → X/Y/Z → 数字 → Enter）",
                },
            }
            return stages.get(stage_num, {})
        if chapter_num == 2:
            stages = {
                1: {
                    "title": "第2章: ビュー操作",
                    "name": "ステージ1: パン（視点を平行移動）",
                    "description": "Shift + 中ボタンで視点を動かしてください",
                    "details": "① マウスの中ボタンを押しながら\n"
                               "   Shift キーを同時に押す\n"
                               "② そのままドラッグすると\n"
                               "   視点が上下左右に平行移動する\n"
                               "   （オブジェクトは動きません）",
                },
                2: {
                    "title": "第2章: ビュー操作",
                    "name": "ステージ2: ズーム（拡大縮小）",
                    "description": "マウスホイールで拡大・縮小してください",
                    "details": "① マウスのホイールを前に回す\n"
                               "   → ズームイン（拡大）\n"
                               "② ホイールを後ろに回す\n"
                               "   → ズームアウト（縮小）",
                },
                3: {
                    "title": "第2章: ビュー操作",
                    "name": "ステージ3: ビュー回転",
                    "description": "中ボタンドラッグで視点を回転してください",
                    "details": "① マウスの中ボタンを押したまま\n"
                               "   ドラッグする（Shiftは押さない）\n"
                               "② 視点がぐるりと回転する\n"
                               "   オブジェクトの裏側も見られる",
                },
                4: {
                    "title": "第2章: ビュー操作",
                    "name": "ステージ4: すべてマスター",
                    "description": "パンとズームを両方実行してください",
                    "details": "① Shift + 中ボタンでパン（平行移動）\n"
                               "② ホイールスクロールでズーム\n"
                               "③ 両方を実行するとクリア",
                },
            }
            return stages.get(stage_num, {})
        if chapter_num == 3:
            stages = {
                1: {"title": "第3章: オブジェクト操作", "name": "ステージ1: オブジェクト追加",
                    "description": "Shift+A でオブジェクトを追加してください",
                    "details": "① Shift+A を押す\n"
                               "② メッシュ → 立方体（または好きなもの）を選択"},
                2: {"title": "第3章: オブジェクト操作", "name": "ステージ2: 元に戻す",
                    "description": "Ctrl+Z でミスを取り消せます",
                    "details": "① G → X → 3 → Enter でキューブを動かす\n"
                               "② Ctrl+Z を押して元の位置に戻してみよう\n"
                               "③ 試したら「確認」ボタンを押してください"},
                3: {"title": "第3章: オブジェクト操作", "name": "ステージ3: 削除",
                    "description": "オブジェクトを削除してください",
                    "details": "① オブジェクトをクリックして選択\n"
                               "② X キーまたは Delete キーを押す\n"
                               "③ 「削除」をクリックして確定"},
                4: {"title": "第3章: モデリング基礎", "name": "ステージ4: エディットモード",
                    "description": "Tab キーでエディットモードに切り替え",
                    "details": "① Cubeを左クリックで選択\n"
                               "② Tab キーでエディットモードへ"},
                5: {"title": "第3章: モデリング基礎", "name": "ステージ5: 頂点選択",
                    "description": "3個以上の頂点を選択",
                    "details": "① 1キーで頂点選択モードに切り替え\n"
                               "② クリックで頂点を選択\n"
                               "   （Shift+クリックで複数選択）\n"
                               "③ Gキーで動かしてみよう"},
                6: {"title": "第3章: モデリング基礎", "name": "ステージ6: エッジ選択",
                    "description": "エッジ（辺）を選択",
                    "details": "① 2キーでエッジ選択モードに切り替え\n"
                               "② クリックでエッジを選択\n"
                               "③ Gキーで動かしてみよう"},
                7: {"title": "第3章: モデリング基礎", "name": "ステージ7: フェース選択",
                    "description": "フェース（面）を選択",
                    "details": "① 3キーでフェース選択モードに切り替え\n"
                               "② クリックでフェースを選択\n"
                               "③ Gキーで動かしてみよう"},
                8: {"title": "第3章: モデリング基礎", "name": "ステージ8: エクストルード",
                    "description": "E キーで面を押し出してください",
                    "details": "① 3キーでフェース選択モード\n"
                               "② 面をクリックして選択\n"
                               "③ E → 動かす → 左クリックで確定"},
                9: {"title": "第3章: モデリング基礎", "name": "ステージ9: ループカット",
                    "description": "Ctrl+R でループカットを追加してください",
                    "details": "① Ctrl+R を押す\n"
                               "② 黄色い線が出たらクリック\n"
                               "③ もう一度クリックで確定"},
            }
            return stages.get(stage_num, {})
        if chapter_num == 5:
            stages = {
                1: {
                    "title": "第5章: スカルプティング体験",
                    "name": "ステージ1: スカルプトモードに入る",
                    "description": "Sculpt Mode（スカルプトモード）に入ってください",
                    "details": "① セットアップで球（Sphere）が出現\n"
                               "② 画面左上のモード切替から\n"
                               "   「スカルプトモード」を選択\n"
                               "   または Ctrl+Tab → スカルプト",
                },
                2: {
                    "title": "第5章: スカルプティング体験",
                    "name": "ステージ2: Draw ブラシで変形",
                    "description": "Draw ブラシで球の表面をドラッグして変形してください",
                    "details": "① 左のツールバーから「Draw」を選択\n"
                               "② 球の上でクリック＆ドラッグ\n"
                               "③ 表面が盛り上がれば成功\n"
                               "   F キーでブラシサイズを変更できる\n"
                               "   Ctrl を押しながらで凹ませられる",
                },
                3: {
                    "title": "第5章: スカルプティング体験",
                    "name": "ステージ3: Smooth ブラシに切り替え",
                    "description": "Smooth（スムーズ）ブラシを選択してください",
                    "details": "① 左のツールバーをスクロールして\n"
                               "   「Smooth」を選択\n"
                               "② または Shift キーを押しながらドラッグ\n"
                               "   （一時的に Smooth ブラシになる）\n"
                               "③ ブラシ名に「Smooth」が表示されたらOK",
                },
                4: {
                    "title": "第5章: スカルプティング体験",
                    "name": "ステージ4: Grab ブラシに切り替え",
                    "description": "Grab（グラブ）ブラシを選択してください",
                    "details": "① 左のツールバーから「Grab」を選択\n"
                               "② 球の表面をドラッグすると\n"
                               "   粘土をつまむように形が変わる\n"
                               "③ ブラシ名に「Grab」が表示されたらOK",
                },
            }
            return stages.get(stage_num, {})
        if chapter_num == 6:
            stages = {
                1: {
                    "title": "第6章: マテリアルノード",
                    "name": "ステージ1: マテリアル作成",
                    "description": "マテリアルを新規作成してください",
                    "details": "① 画面左上の「エディタータイプ」から\n"
                               "　 球アイコン（シェーダーエディタ）であることを確認\n"
                               "② 「新規」ボタンをクリック",
                },
                2: {
                    "title": "第6章: マテリアルノード",
                    "name": "ステージ2: 色変更",
                    "description": "Base Color（ベースカラー）を変更してください",
                    "details": "① ステージ1の手順 1～2 を済ませておく\n"
                               "② 「ベースカラー」の色をクリック\n"
                               "③ カラーピッカーで好きな色に変更",
                },
                3: {
                    "title": "第6章: マテリアルノード",
                    "name": "ステージ3: 画像テクスチャ追加",
                    "description": "画像テクスチャノードを追加して画像を読み込んでください",
                    "details": "① ステージ1～2の手順を済ませておく\n"
                               "② 追加 → テクスチャ → 画像テクスチャ\n"
                               "③ 「23DB000」フォルダの中から\n"
                               "　 画像ファイルを選択して「画像を開く」",
                },
                4: {
                    "title": "第6章: マテリアルノード",
                    "name": "ステージ4: ノード接続",
                    "description": "画像テクスチャの「カラー」をベースカラーに接続してください",
                    "details": "① 画像テクスチャノードの右側\n"
                               "　 「カラー」ソケット（黄色の点）をドラッグ\n"
                               "② Principled BSDF の\n"
                               "　 「ベースカラー」ソケットに繋げる\n"
                               "③ 線がつながれば接続完了",
                },
                5: {
                    "title": "第6章: マテリアルノード",
                    "name": "ステージ5: 質感調整",
                    "description": "Roughness または Metallic を変更してください",
                    "details": "① ステージ1～2の手順を済ませておく\n"
                               "② Roughness または Metallic を変更\n"
                               "\n"
                               "　1. Principled BSDF ノードの\n"
                               "　   「粗さ（Roughness）」を変更\n"
                               "　   → 0に近い：ツルツル / 1に近い：ザラザラ\n"
                               "\n"
                               "　2. または「メタリック（Metallic）」を変更\n"
                               "　   → 1にすると金属質になる",
                },
            }
            return stages.get(stage_num, {})
        return {}

    @staticmethod
    def apply_hint_escalation(hints, failed_validate_count: int, difficulty_mode: str = 'NORMAL'):
        if not hints:
            return []
        if difficulty_mode == 'EASY':
            return hints              # 最初から全ヒント表示
        if difficulty_mode == 'HARD':
            return []                 # ヒントなし
        # NORMAL: 失敗するたびに1つずつ追加（ヒント数まで）
        return hints[:min(failed_validate_count, len(hints))]

    # -----------------------------
    # Validation: Chapters 1-6 (Ch6 Stage1 only)
    # -----------------------------
    @staticmethod
    def validate_stage(context):
        props = context.scene.tutorial_props
        ch = props.current_chapter
        st = props.current_stage
        obj = context.active_object

        # ---- Chapter 1 ----
        if ch == 1:
            if st == 1:
                if obj and obj.name == "Cube":
                    return True, "✓ キューブが選択されました", "OK", []
                return False, "❌ キューブを選択してください", "NO_ACTIVE_CUBE", [
                    "3Dビュー中央のキューブを左クリックしてみよう",
                    "オレンジ色の枠が表示されれば選択成功です",
                    "何もない場所をクリックすると選択が解除されます",
                ]
            if st == 2:
                if not obj or obj.name != "Cube":
                    return False, "❌ キューブなし", "NO_ACTIVE_CUBE", [
                        "まずキューブを左クリックで選択してください",
                        "オレンジ枠が出たら選択できています",
                        "その後 G → X → 2 → Enter を入力します",
                    ]
                movement = obj.location.x - props.initial_position[0]
                if abs(movement - 2.0) < 0.1:
                    return True, "✓ +2移動しました", "OK", []
                return False, f"❌ 移動量: {movement:.2f}（目標: +2.0）", "TRANSFORM_NOT_MATCHED", [
                    "G キーを押すと移動モードになります",
                    "X キーを押すとX軸だけに固定されます",
                    "2 と入力して Enter を押すと +2 移動できます",
                ]
            if st == 3:
                if not obj or obj.name != "Cube":
                    return False, "❌ キューブなし", "NO_ACTIVE_CUBE", [
                        "まずキューブを左クリックで選択してください",
                        "オレンジ枠が出たら選択できています",
                        "その後 R → X → 45 → Enter を入力します",
                    ]
                rot = math.degrees(obj.rotation_euler.x) - math.degrees(props.initial_rotation[0])
                if abs(rot - 45.0) < 1.0:
                    return True, "✓ 45度回転しました", "OK", []
                return False, f"❌ 回転量: {rot:.1f}°（目標: 45°）", "TRANSFORM_NOT_MATCHED", [
                    "R キーを押すと回転モードになります",
                    "X キーでX軸周りの回転に固定されます",
                    "45 と入力して Enter を押すと45度回転できます",
                ]
            if st == 4:
                if not obj or obj.name != "Cube":
                    return False, "❌ キューブなし", "NO_ACTIVE_CUBE", [
                        "まずキューブを左クリックで選択してください",
                        "オレンジ枠が出たら選択できています",
                        "その後 S → 数字 → Enter でスケール変更できます",
                    ]
                if abs(obj.scale.x - props.initial_scale[0]) > 0.01:
                    return True, "✓ スケール変更完了", "OK", []
                return False, "❌ スケール値を変更してください", "SCALE_NOT_CHANGED", [
                    "S キーを押すとスケールモードになります",
                    "数字を入力すると倍率を指定できます（例: 2 で2倍）",
                    "Enter で確定。S → X → 2 → Enter でX軸だけ2倍にもできます",
                ]

        # ---- Chapter 2 ----
        if ch == 2:
            space = StageManager.get_view3d_space(context)
            if not space or not space.region_3d:
                return False, "❌ 3Dビューなし", "NO_VIEW3D", [
                    "3Dビューがあるレイアウトに戻してください",
                    "画面上部の「Layout」タブをクリックしてみてください",
                    "それでも直らない場合はリセットしてください",
                ]
            r3d = space.region_3d
            if st == 1:
                loc_diff = StageManager.vec_dist(tuple(r3d.view_location), tuple(props.initial_view_location))
                if loc_diff > 0.1:
                    return True, "✓ ビュー移動完了", "OK", []
                return False, "❌ ビューをパンしてください", "VIEW_NOT_MOVED", [
                    "マウスの中ボタンを押しながら Shift キーを同時に押してください",
                    "その状態でマウスをドラッグすると視点が平行移動します",
                    "オブジェクト自体は動きません。カメラ視点を動かすイメージです",
                ]
            if st == 2:
                if abs(r3d.view_distance - props.initial_view_distance) > 0.5:
                    return True, "✓ ズーム完了", "OK", []
                return False, "❌ ズームしてください", "VIEW_NOT_ZOOMED", [
                    "マウスのホイールを前に回すと拡大できます",
                    "ホイールを後ろに回すと縮小できます",
                    "大きく動かすとすぐ検出されます",
                ]
            if st == 3:
                rot_diff = StageManager.vec_dist(tuple(r3d.view_rotation), tuple(props.initial_view_rotation))
                if rot_diff > 0.01:
                    return True, "✓ ビュー回転完了", "OK", []
                return False, "❌ ビューを回転させてください", "VIEW_NOT_ROTATED", [
                    "マウスの中ボタンを押したままドラッグしてください",
                    "Shift は押さないでください（押すとパンになります）",
                    "大きくドラッグすると検出されやすいです",
                ]
            if st == 4:
                loc_diff = StageManager.vec_dist(tuple(r3d.view_location), tuple(props.initial_view_location))
                dist_diff = abs(r3d.view_distance - props.initial_view_distance)
                if loc_diff > 0.1 and dist_diff > 0.5:
                    return True, "✓ すべてのビュー操作をマスターしました", "OK", []
                return False, "❌ パン + ズームを両方実行してください", "VIEW_NOT_COMPLETED", [
                    "Shift + 中ボタンドラッグでパン（平行移動）してください",
                    "ホイールスクロールでズーム（拡大縮小）してください",
                    "両方の操作を行うとクリアになります",
                ]

        # ---- Chapter 3 ----
        if ch == 3:
            # --- 新St1: Shift+A でオブジェクト追加 ---
            if st == 1:
                meshes = [o for o in bpy.data.objects if o.type == 'MESH']
                if meshes:
                    return True, "✓ オブジェクトを追加しました", "OK", []
                return False, "❌ Shift+A でオブジェクトを追加してください", "NO_OBJECT_ADDED", [
                    "Shift キーを押しながら A キーを押してみてください",
                    "メニューが開いたら「メッシュ」を選んでください",
                    "「立方体」や「UV球」など好きなものを選んで追加できます",
                ]

            # --- 新St2: Ctrl+Z の説明ステージ（確認ボタンで通過）---
            if st == 2:
                return True, "✓ Ctrl+Z の使い方を確認しました", "OK", []

            # --- 新St3: Delete で削除 ---
            if st == 3:
                meshes = [o for o in bpy.data.objects if o.type == 'MESH']
                if not meshes:
                    return True, "✓ オブジェクトを削除しました", "OK", []
                return False, "❌ オブジェクトを削除してください", "OBJECT_NOT_DELETED", [
                    "オブジェクトを左クリックで選択してください",
                    "キーボードの X キーまたは Delete キーを押してください",
                    "確認メニューが出たら「削除」をクリックして確定します",
                ]

            # --- St4〜: 旧St1〜6 (エディットモード〜ループカット) ---
            if st == 4:
                if obj and bpy.context.mode == 'EDIT_MESH':
                    return True, "✓ エディットモード突入", "OK", []
                return False, "❌ エディットモードに入ってください", "NOT_IN_EDIT_MODE", [
                    "まずキューブを左クリックで選択してください",
                    "Tab キーを押すとエディットモードに切り替わります",
                    "画面左上のモード表示が「編集モード」になればOKです",
                ]

            bm = StageManager.get_bm(obj)
            if not bm:
                return False, "❌ エディットモード必須", "NOT_IN_EDIT_MODE", [
                    "キューブを選択してから Tab キーを押してください",
                    "画面左上が「編集モード」になっていることを確認してください",
                    "オブジェクトが選択されていないと入れません",
                ]

            if st == 5:
                if not StageManager.get_mesh_select_mode(context)[0]:
                    return False, "❌ 頂点選択モードに切り替えてください", "WRONG_SELECT_MODE", [
                        "キーボードの 1 キーを押してください",
                        "画面左上のアイコンで「頂点」を選択することもできます",
                        "頂点は黒い点（選択すると白くなります）です",
                    ]
                sel_count = sum(1 for v in bm.verts if v.select)
                if sel_count >= 3:
                    return True, f"✓ 頂点選択: {sel_count}個", "OK", []
                return False, f"❌ 頂点を選択してください（現在 {sel_count}個）", "NOT_ENOUGH_SELECTED", [
                    "頂点（黒い点）を左クリックすると選択できます",
                    "Shift キーを押しながらクリックすると複数選択できます",
                    "3つ以上選択するとクリアになります",
                ]
            if st == 6:
                if not StageManager.get_mesh_select_mode(context)[1]:
                    return False, "❌ エッジ選択モードに切り替えてください", "WRONG_SELECT_MODE", [
                        "キーボードの 2 キーを押してください",
                        "画面左上のアイコンで「辺」を選択することもできます",
                        "辺は頂点と頂点をつなぐ線のことです",
                    ]
                if any(e.select for e in bm.edges):
                    return True, "✓ エッジ選択完了", "OK", []
                return False, "❌ エッジを選択してください", "NOTHING_SELECTED", [
                    "2キーでエッジ選択モードにしてください",
                    "辺（エッジ）を左クリックすると選択できます",
                    "選択するとオレンジ色になります",
                ]
            if st == 7:
                if not StageManager.get_mesh_select_mode(context)[2]:
                    return False, "❌ フェース選択モードに切り替えてください", "WRONG_SELECT_MODE", [
                        "キーボードの 3 キーを押してください",
                        "画面左上のアイコンで「面」を選択することもできます",
                        "面は複数の辺で囲まれた平らな部分です",
                    ]
                if any(f.select for f in bm.faces):
                    return True, "✓ フェース選択完了", "OK", []
                return False, "❌ フェースを選択してください", "NOTHING_SELECTED", [
                    "3キーでフェース選択モードにしてください",
                    "面の中央部分を左クリックすると選択できます",
                    "選択するとオレンジ色になります",
                ]
            if st == 8:
                if len(bm.faces) > props.initial_face_count:
                    return True, "✓ 押し出し完了", "OK", []
                return False, "❌ 面を押し出してください", "EXTRUDE_NOT_DETECTED", [
                    "3キーでフェース選択モードにして面を選択してください",
                    "E キーを押すと押し出しモードになります",
                    "マウスを動かして Enter または左クリックで確定します",
                ]
            if st == 9:
                if len(bm.verts) > props.initial_vertex_count:
                    return True, "✓ ループカット完了", "OK", []
                return False, "❌ ループカットを追加してください", "LOOPCUT_NOT_DETECTED", [
                    "Ctrl + R キーを押してください",
                    "黄色い線がメッシュに表示されたらクリックで位置を確定します",
                    "もう一度クリック（またはEnter）で最終確定します",
                ]

        # ---- Chapter 4: モディファイアー ----
        if ch == 4:
            if not obj or obj.type != 'MESH':
                return False, "❌ オブジェクトを選択してください", "NO_ACTIVE_OBJECT", [
                    "3DビューでキューブをクリックしてActiveにしてください",
                    "オレンジ枠が出たら選択できています",
                    "セットアップを押すとキューブが配置されます",
                ]
            if st == 1:
                if any(m.type == 'SUBSURF' for m in obj.modifiers):
                    return True, "✓ サブディビジョンサーフェスを追加しました", "OK", []
                return False, "❌ サブディビジョンサーフェスを追加してください", "NO_MODIFIER", [
                    "右のプロパティパネルのレンチアイコンを開いてください",
                    "「モディファイアーを追加」→「生成」→「サブディビジョンサーフェス」",
                    "追加すると面が細かく分割されてなめらかになります",
                ]
            if st == 2:
                mirror_y = any(
                    m.type == 'MIRROR' and m.use_axis[1]
                    for m in obj.modifiers
                )
                if mirror_y:
                    return True, "✓ ミラー（Y軸）を追加しました", "OK", []
                has_mirror = any(m.type == 'MIRROR' for m in obj.modifiers)
                if has_mirror:
                    return False, "❌ ミラーの座標軸を「Y」にしてください", "MIRROR_WRONG_AXIS", [
                        "モディファイアーパネルでミラーを確認してください",
                        "「座標軸」の「Y」ボタンをクリックしてONにしてください",
                        "「X」のチェックははずしてもOKです",
                    ]
                return False, "❌ ミラーモディファイアーを追加してください", "NO_MODIFIER", [
                    "まずエディットモードでループカット→片側を削除してみてください",
                    "その後レンチアイコン→「生成」→「ミラー」を追加してください",
                    "座標軸の「Y」をONにすると削除した側が補完されます",
                ]
            if st == 3:
                if any(m.type == 'SOLIDIFY' for m in obj.modifiers):
                    return True, "✓ 厚み付けを追加しました", "OK", []
                return False, "❌ 厚み付け（Solidify）を追加してください", "NO_MODIFIER", [
                    "トーラス（ドーナツ型）にモディファイアーを追加します",
                    "レンチアイコン→「生成」→「厚み付け」を選んでください",
                    "追加後に「幅」の値を変えると厚さが変わります",
                ]
            if st == 4:
                if any(m.type == 'BEVEL' for m in obj.modifiers):
                    return True, "✓ ベベルを追加しました", "OK", []
                return False, "❌ ベベル（Bevel）を追加してください", "NO_MODIFIER", [
                    "右のプロパティパネルのレンチアイコンを開いてください",
                    "「モディファイアーを追加」→「生成」→「ベベル」",
                    "追加すると角が丸くなります",
                ]

        # ---- Chapter 5: スカルプト（旧Ch4） ----
        if ch == 5:
            sphere = StageManager.find_sphere()
            if st == 1:
                if StageManager.is_in_sculpt_mode() and sphere:
                    return True, "✓ スカルプトモード入場", "OK", []
                return False, "❌ スカルプトモードに入ってください", "NOT_IN_SCULPT_MODE", [
                    "球（Sphere）を左クリックで選択してください",
                    "画面左上のモード切替から「スカルプトモード」を選んでください",
                    "または Ctrl + Tab を押してスカルプトを選択できます",
                ]
            if st == 2:
                if StageManager.is_in_sculpt_mode() and sphere:
                    moved, _ = StageManager.get_vertex_deformation_amount(sphere, props.initial_vertex_positions)
                    if moved > 5:
                        return True, "✓ Draw ブラシで変形しました", "OK", []
                    return False, "❌ Draw ブラシで球を変形してください", "SCULPT_NOT_DETECTED", [
                        "左のツールバーから「Draw」ブラシを選んでください",
                        "球の上でクリックしながらドラッグすると盛り上がります",
                        "F キーでブラシサイズを変更すると変形しやすくなります",
                    ]
                return False, "❌ スカルプトモード必須", "NOT_IN_SCULPT_MODE", [
                    "まずスカルプトモードに切り替えてください",
                    "球を選択してから画面左上のモード切替を使います",
                    "Ctrl + Tab でモード一覧が出ます",
                ]
            if st == 3:
                if StageManager.is_in_sculpt_mode() and StageManager.is_brush_type_selected("Smooth"):
                    return True, "✓ Smooth ブラシを選択しました", "OK", []
                return False, "❌ Smooth ブラシを選択してください", "WRONG_BRUSH", [
                    "左のツールバーをスクロールして「Smooth」を探してください",
                    "Shift キーを押しながらドラッグすると一時的にSmoothになります",
                    "ブラシ名の表示が「Smooth」になればOKです",
                ]
            if st == 4:
                if StageManager.is_in_sculpt_mode() and StageManager.is_brush_type_selected("Grab"):
                    return True, "✓ Grab ブラシを選択しました", "OK", []
                return False, "❌ Grab ブラシを選択してください", "WRONG_BRUSH", [
                    "左のツールバーから「Grab」を探してください",
                    "Grabは粘土をつまむように形を引っ張るブラシです",
                    "ブラシ名の表示が「Grab」になればOKです",
                ]

        # ---- Chapter 6: マテリアル（旧Ch5） ----
        if ch == 6:
            if st == 1:
                if not obj:
                    return False, "❌ オブジェクトを選択してください", "NO_ACTIVE_OBJECT", [
                        "3DビューでキューブをクリックしてActiveにしてください",
                        "オレンジ枠が出たら選択できています",
                        "その状態でマテリアルを作成してください",
                    ]
                mat = StageManager.get_active_material(obj)
                if mat and mat.use_nodes:
                    return True, "✓ マテリアル作成完了", "OK", []
                return False, "❌ マテリアルを作成してください", "NO_MATERIAL", [
                    "シェーダーエディター左上が球アイコン（シェーダーエディタ）か確認してください",
                    "「新規」ボタンをクリックするとマテリアルが作成されます",
                    "「ノードを使用」が有効になっていることを確認してください",
                ]
            if st == 2:
                if not obj:
                    return False, "❌ オブジェクトを選択してください", "NO_ACTIVE_OBJECT", [
                        "3DビューでキューブをクリックしてActiveにしてください",
                        "オレンジ枠が出たら選択できています",
                        "その後マテリアルのベースカラーを変更してください",
                    ]
                mat = StageManager.get_active_material(obj)
                bsdf = StageManager.get_principled_bsdf(mat) if mat else None
                if not bsdf:
                    return False, "❌ Principled BSDF が見つかりません", "NO_BSDF", [
                        "まずステージ1でマテリアルを作成してください",
                        "シェーダーエディターに「Principled BSDF」ノードが必要です",
                        "「ノードを使用」をONにすると自動で追加されます",
                    ]
                base_color = bsdf.inputs['Base Color'].default_value
                default = (1.0, 1.0, 1.0, 1.0)
                changed = any(abs(base_color[i] - default[i]) > 0.01 for i in range(4))
                if changed:
                    return True, "✓ Base Color を変更しました", "OK", []
                return False, "❌ Base Color を変更してください", "BASE_COLOR_NOT_CHANGED", [
                    "Principled BSDF ノードの「ベースカラー」をクリックしてください",
                    "カラーピッカーが開くので好きな色を選んでください",
                    "白（デフォルト）以外の色にするとクリアになります",
                ]
            if st == 3:
                if obj and StageManager.check_image_texture_node_exists(obj):
                    return True, "✓ 画像テクスチャをロードしました", "OK", []
                return False, "❌ 画像テクスチャをロードしてください", "NO_IMAGE_TEXTURE", [
                    "シェーダーエディター内で Shift+A → テクスチャ → 画像テクスチャを選んでください",
                    "追加されたノードの「開く」ボタンをクリックしてください",
                    "「23DB000」フォルダの中の画像ファイルを選んで「画像を開く」してください",
                ]
            if st == 4:
                if obj and StageManager.check_correct_node_link(obj):
                    return True, "✓ ノード接続完了", "OK", []
                return False, "❌ ノード接続してください", "NODE_LINK_INCORRECT", [
                    "画像テクスチャノードの右側にある「カラー」ソケット（黄色の点）をドラッグしてください",
                    "Principled BSDF の「ベースカラー」ソケットまでドラッグして離すと接続されます",
                    "線でつながれたらノード接続完了です",
                ]
            if st == 5:
                if not obj:
                    return False, "❌ オブジェクトを選択してください", "NO_ACTIVE_OBJECT", [
                        "3DビューでキューブをクリックしてActiveにしてください",
                        "オレンジ枠が出たら選択できています",
                        "その後 Roughness または Metallic を変更してください",
                    ]
                mat = StageManager.get_active_material(obj)
                bsdf = StageManager.get_principled_bsdf(mat) if mat else None
                if not bsdf:
                    return False, "❌ Principled BSDF が見つかりません", "NO_BSDF", [
                        "まずステージ1でマテリアルを作成してください",
                        "シェーダーエディターに「Principled BSDF」ノードが必要です",
                        "「ノードを使用」をONにすると自動で追加されます",
                    ]
                roughness = bsdf.inputs['Roughness'].default_value
                metallic = bsdf.inputs['Metallic'].default_value
                if abs(roughness - 0.5) > 0.01 or abs(metallic - 0.0) > 0.01:
                    return True, "✓ 質感を変更しました", "OK", []
                return False, "❌ Roughness または Metallic を変更してください", "PBR_NOT_CHANGED", [
                    "Principled BSDF ノードの「粗さ（Roughness）」の値を変更してください",
                    "0に近いほどツルツル、1に近いほどザラザラになります",
                    "または「メタリック（Metallic）」を1にすると金属のような質感になります",
                ]

        # ---- Chapter 7: 最終制作（旧Ch6） ----
        if ch == 7:
            if props.current_stage != 1:
                props.current_stage = 1

            saved = (props.final_render_saved_path or "").strip()
            if saved and StageManager.file_exists_nonempty(bpy.path.abspath(saved)):
                return True, f"✓ 保存OK: {os.path.basename(saved)}", "OK", []
            return False, "❌ まだ保存が検出できません", "RENDER_NOT_SAVED", [
                "① スカルプトモードで球の天面を Ctrl+ドラッグで押し込んで凹みを作ろう",
                "② Grabブラシで球全体を縦長に整えて楕円形（卵型）にしよう",
                "③ 編集モード（Tab）で頂点を動かして形を細かく調整しよう",
                "④ Shift+A → メッシュ → 円柱で茎を追加し、細くして天面に配置しよう",
                "⑤ マテリアルで赤色を設定しよう（Roughnessを下げると光沢感が出る）",
                "⑥ 完成したら F12 でレンダー → 「画像を名前をつけて保存」でクリア！",
            ]

        return False, "❌ 判定エラー", "UNKNOWN", ["セットアップして再試行"]

    @staticmethod
    def check_stage(context):
        try:
            props = context.scene.tutorial_props
            # Ch3 St2 は説明確認ステージのため自動判定しない
            if props.current_chapter == 3 and props.current_stage == 2:
                return
            ok, message, reason, hints = StageManager.validate_stage(context)

            props.last_result_ok = ok
            props.last_message = message
            props.last_reason = reason

            if ok and not props.stage_complete:
                props.stage_complete = True
                props.last_hints = ""
                StageManager.log_validate_event(context, ok=True, reason=reason, message=message, auto=True)
        except Exception:
            return

# =====================================================
# PROPERTIES
# =====================================================

class TUTORIAL_PG_Properties(PropertyGroup):
    current_chapter: IntProperty(default=1, min=1, max=7)
    current_stage: IntProperty(default=1, min=1, max=10)
    stage_complete: BoolProperty(default=False)
    monitoring_active: BoolProperty(default=False)

    # Chapter 1 initial transforms
    initial_position: FloatVectorProperty(default=(0.0, 0.0, 0.0), size=3)
    initial_rotation: FloatVectorProperty(default=(0.0, 0.0, 0.0), size=3)
    initial_scale: FloatVectorProperty(default=(1.0, 1.0, 1.0), size=3)

    # Chapter 2 view state
    initial_view_distance: FloatProperty(default=0.0)
    initial_view_location: FloatVectorProperty(default=(0.0, 0.0, 0.0), size=3)
    initial_view_rotation: FloatVectorProperty(default=(1.0, 0.0, 0.0, 0.0), size=4)

    # Chapter 3 mesh counts
    initial_vertex_count: IntProperty(default=0)
    initial_edge_count: IntProperty(default=0)
    initial_face_count: IntProperty(default=0)

    # Chapter 4
    initial_vertex_positions: CollectionProperty(type=VertexPos)

    # Feedback
    failed_validate_count: IntProperty(default=0, min=0)
    stage_start_time: FloatProperty(default=0.0)
    last_result_ok: BoolProperty(default=True)
    last_reason: StringProperty(default="")
    last_message: StringProperty(default="")
    last_hints: StringProperty(default="")

    # Research: per-stage behavioral metrics
    reason_sequence: StringProperty(default="")      # 失敗コードをカンマ区切りで蓄積
    setup_count: IntProperty(default=0, min=0)       # 同ステージのセットアップ回数
    first_attempt_time: FloatProperty(default=0.0)   # 最初の確認ボタン押下時刻
    undo_count: IntProperty(default=0, min=0)        # Ctrl+Z 回数
    survey_difficulty: IntProperty(default=0, min=0, max=5)  # 難易度アンケート (0=未回答)

    # Research summary
    stage_runs: CollectionProperty(type=StageRun)
    current_stall_seconds: FloatProperty(default=0.0, min=0.0)

    # 難易度設定（セッション開始前に実験者が設定）
    difficulty_mode: EnumProperty(
        name="難易度",
        description="ヒントの表示量を制御します",
        items=[
            ('EASY',   "かんたん",   "最初からすべてのヒントを表示"),
            ('NORMAL', "ふつう",     "失敗するたびにヒントを段階的に表示（デフォルト）"),
            ('HARD',   "むずかしい", "ヒントを表示しない"),
        ],
        default='NORMAL',
    )

    # Logging
    enable_participant_logging: BoolProperty(default=True)
    participant_id: StringProperty(name="参加者ID", default="")
    log_dir: StringProperty(
        name="ログ保存フォルダ",
        description="クリックでフォルダ選択（環境によってFile Browserが落ちる場合あり：下の安全ボタンを使用）",
        subtype='DIR_PATH',
        default=StageManager.default_log_dir(),
    )
    participant_log_path: StringProperty(default="")
    participant_log_error: StringProperty(default="")

    # Chapter 6
    final_render_saved_path: StringProperty(default="")

# =====================================================
# OPERATORS
# =====================================================

class TUTORIAL_OT_set_default_log_dir(Operator):
    bl_idname = "tutorial.set_default_log_dir"
    bl_label = "既定フォルダに設定"
    bl_description = "ログ保存フォルダを既定値に戻し、フォルダも作成します"

    def execute(self, context):
        props = context.scene.tutorial_props
        props.log_dir = StageManager.default_log_dir()
        try:
            StageManager.ensure_dir_exists(props.log_dir)
        except Exception as e:
            self.report({'ERROR'}, f"フォルダ作成に失敗: {e}")
            return {'CANCELLED'}
        self.report({'INFO'}, f"設定: {bpy.path.abspath(props.log_dir)}")
        return {'FINISHED'}

class TUTORIAL_OT_open_log_folder(Operator):
    bl_idname = "tutorial.open_log_folder"
    bl_label = "ログフォルダを開く"
    bl_description = "OSのファイルエクスプローラでログ保存フォルダを開きます（BlenderのFile Browserは使いません）"

    def execute(self, context):
        props = context.scene.tutorial_props
        try:
            StageManager.open_folder_in_os(props.log_dir or StageManager.default_log_dir())
        except Exception as e:
            self.report({'ERROR'}, f"フォルダを開けません: {e}")
            return {'CANCELLED'}
        return {'FINISHED'}

class TUTORIAL_OT_confirm_all_chapters(Operator):
    bl_idname = "tutorial.confirm_all_chapters"
    bl_label = "全チャプター確認"
    bl_description = "第1章〜第6章のステージ1を順番に判定し、OK/NGを一覧表示します（状態は元に戻します）"

    def execute(self, context):
        props = context.scene.tutorial_props
        original_ch = props.current_chapter
        original_st = props.current_stage

        results = []
        try:
            for ch in range(1, 7):
                props.current_chapter = ch
                props.current_stage = 1
                ok, message, reason, _hints = StageManager.validate_stage(context)
                results.append((ch, ok, reason, message))
        finally:
            props.current_chapter = original_ch
            props.current_stage = original_st

        print("[Confirm All Chapters]")
        for ch, ok, reason, message in results:
            status = "OK" if ok else "NG"
            print(f"  Ch{ch}: {status} ({reason}) {message}")

        summary = " / ".join([f"Ch{ch}:{'OK' if ok else 'NG'}" for ch, ok, _, _ in results])
        self.report({'INFO'}, summary)
        return {'FINISHED'}

class TUTORIAL_OT_export_stage_summary_csv(Operator):
    bl_idname = "tutorial.export_stage_summary_csv"
    bl_label = "ステージ集計CSV出力"
    bl_description = "参加者ログ(JSONL)から、失敗回数/停滞時間(finalizeのみ)をステージ別に集計してCSV出力します"

    def execute(self, context):
        props = context.scene.tutorial_props

        # Create log automatically so CSV can be exported even before first "確認"
        if not props.participant_log_path:
            ok = StageManager.ensure_participant_log_file(context)
            if not ok or not props.participant_log_path:
                self.report({'ERROR'}, props.participant_log_error or "ログファイルを作成できません。参加者IDとログ保存フォルダを確認してください。")
                return {'CANCELLED'}

        jsonl_path = bpy.path.abspath(props.participant_log_path)
        if not os.path.isfile(jsonl_path):
            self.report({'ERROR'}, f"ログファイルが見つかりません: {jsonl_path}")
            return {'CANCELLED'}

        events = []
        try:
            with open(jsonl_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            self.report({'ERROR'}, f"ログ読み込みに失敗: {e}")
            return {'CANCELLED'}

        by_stage = {}
        for ev in events:
            ev_type = ev.get("event")
            if ev_type not in ("validate", "finalize"):
                continue
            ch = ev.get("chapter")
            st = ev.get("stage")
            if ch is None or st is None:
                continue
            key = (int(ch), int(st))
            if key not in by_stage:
                by_stage[key] = {
                    "chapter": int(ch), "stage": int(st),
                    "failures": 0, "stalled_seconds": None, "completed": None,
                    "hint_level": None, "setup_count": None,
                    "time_to_first_attempt_s": None, "time_to_success_s": None,
                    "reason_sequence": None,
                    "undo_count": None, "survey_difficulty": None,
                    "difficulty_mode": None,
                }
            if ev_type == "validate" and ev.get("ok") is False and not ev.get("auto"):
                by_stage[key]["failures"] += 1
            if ev_type == "finalize":
                if ev.get("stalled_seconds") is not None:
                    by_stage[key]["stalled_seconds"] = float(ev["stalled_seconds"])
                if ev.get("completed") is not None:
                    by_stage[key]["completed"] = bool(ev["completed"])
                if ev.get("hint_level") is not None:
                    by_stage[key]["hint_level"] = int(ev["hint_level"])
                if ev.get("setup_count") is not None:
                    by_stage[key]["setup_count"] = int(ev["setup_count"])
                if ev.get("time_to_first_attempt_s") is not None:
                    by_stage[key]["time_to_first_attempt_s"] = float(ev["time_to_first_attempt_s"])
                if ev.get("time_to_success_s") is not None:
                    by_stage[key]["time_to_success_s"] = float(ev["time_to_success_s"])
                seq = ev.get("reason_sequence")
                if seq is not None:
                    by_stage[key]["reason_sequence"] = "|".join(seq) if isinstance(seq, list) else str(seq)
                if ev.get("undo_count") is not None:
                    by_stage[key]["undo_count"] = int(ev["undo_count"])
                if ev.get("survey_difficulty") is not None:
                    by_stage[key]["survey_difficulty"] = int(ev["survey_difficulty"])
                if ev.get("difficulty_mode") is not None:
                    by_stage[key]["difficulty_mode"] = str(ev["difficulty_mode"])

        total_stalled = 0.0
        for r in by_stage.values():
            if isinstance(r["stalled_seconds"], (int, float)):
                total_stalled += float(r["stalled_seconds"])

        out_csv = os.path.splitext(jsonl_path)[0] + ".stage_summary.csv"
        try:
            # Excel-friendly UTF-8 with BOM
            with open(out_csv, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.writer(f)
                w.writerow(["participant_log_file", os.path.basename(jsonl_path)])
                w.writerow(["total_stalled_seconds_finalize_only", f"{total_stalled:.3f}"])
                w.writerow([])
                w.writerow([
                    "chapter", "stage", "failures", "stalled_seconds",
                    "completed", "hint_level", "setup_count",
                    "time_to_first_attempt_s", "time_to_success_s",
                    "undo_count", "survey_difficulty", "difficulty_mode", "reason_sequence",
                ])
                for key in sorted(by_stage.keys()):
                    r = by_stage[key]
                    def _fmt_f(v): return f"{v:.3f}" if isinstance(v, (int, float)) else ""
                    def _fmt_any(v): return "" if v is None else str(v)
                    w.writerow([
                        r["chapter"], r["stage"], r["failures"],
                        _fmt_f(r["stalled_seconds"]),
                        _fmt_any(r["completed"]),
                        _fmt_any(r["hint_level"]),
                        _fmt_any(r["setup_count"]),
                        _fmt_f(r["time_to_first_attempt_s"]),
                        _fmt_f(r["time_to_success_s"]),
                        _fmt_any(r["undo_count"]),
                        _fmt_any(r["survey_difficulty"]),
                        _fmt_any(r["difficulty_mode"]),
                        _fmt_any(r["reason_sequence"]),
                    ])
        except Exception as e:
            self.report({'ERROR'}, f"CSV出力に失敗: {e}")
            return {'CANCELLED'}

        self.report({'INFO'}, f"CSV出力完了: {out_csv}")
        return {'FINISHED'}

class TUTORIAL_OT_render_and_mark_saved(Operator):
    bl_idname = "tutorial.render_and_mark_saved"
    bl_label = "補助: レンダーして保存（自動）"
    bl_description = "最終制作: レンダー画像を自動で保存し、クリア判定できるようにします"

    def execute(self, context):
        props = context.scene.tutorial_props
        try:
            base_dir = StageManager.ensure_dir_exists(props.log_dir or StageManager.default_log_dir())
        except Exception as e:
            self.report({'ERROR'}, f"ログ保存フォルダ作成に失敗: {e}")
            return {'CANCELLED'}

        pid = StageManager._safe_participant_id(props.participant_id) or "participant"
        out_dir = os.path.join(base_dir, f"{pid}_renders")
        os.makedirs(out_dir, exist_ok=True)

        try:
            bpy.ops.render.render('EXEC_DEFAULT', write_still=False)
        except Exception as e:
            self.report({'ERROR'}, f"レンダーに失敗: {e}")
            return {'CANCELLED'}

        try:
            img = bpy.data.images.get("Render Result")
            if not img:
                self.report({'ERROR'}, "Render Result が見つかりません")
                return {'CANCELLED'}

            ts = time.strftime("%Y%m%d_%H%M%S", time.localtime(StageManager._now()))
            filename = f"{pid}_final_{ts}.png"
            out_path = os.path.join(out_dir, filename)

            img.save_render(filepath=out_path, scene=context.scene)
            props.final_render_saved_path = out_path
            self.report({'INFO'}, f"保存しました: {out_path}")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"保存に失敗: {e}")
            return {'CANCELLED'}

class TUTORIAL_OT_finish_and_turn_off(Operator):
    bl_idname = "tutorial.finish_and_turn_off"
    bl_label = "完了（カメラ・ライトOFF）"
    bl_description = "セッション終了: シーンのカメラを解除し、ライトを表示/レンダーから非表示にします"

    def execute(self, context):
        StageManager.turn_off_scene_camera_and_lights()
        self.report({'INFO'}, "カメラとライトをOFFにしました（削除はしていません）")
        return {'FINISHED'}

class TUTORIAL_OT_setup_stage(Operator):
    bl_idname = "tutorial.setup_stage"
    bl_label = "ステージセットアップ"

    def execute(self, context):
        props = context.scene.tutorial_props
        ch = props.current_chapter

        StageManager.finalize_current_run(context, completed=False)

        if ch == 7:
            props.current_stage = 1

        try:
            StageManager.reset_scene_for_chapter(context)
        except Exception as e:
            self.report({'ERROR'}, f"セットアップ中にエラー: {e}")
            return {'CANCELLED'}

        props.stage_complete = False
        props.monitoring_active = True

        props.failed_validate_count = 0
        props.stage_start_time = time.time()
        props.current_stall_seconds = 0.0
        props.last_result_ok = True
        props.last_reason = ""
        props.last_message = ""
        props.last_hints = ""

        props.setup_count += 1
        props.reason_sequence = ""
        props.first_attempt_time = 0.0
        props.undo_count = 0
        props.survey_difficulty = 0

        if not (props.log_dir or "").strip():
            props.log_dir = StageManager.default_log_dir()
        try:
            StageManager.ensure_dir_exists(props.log_dir)
        except Exception as e:
            props.participant_log_error = f"ログ保存フォルダ作成に失敗: {e}"

        StageManager.log_setup_event(context)
        self.report({'INFO'}, "セットアップ完了")
        return {'FINISHED'}

class TUTORIAL_OT_validate_stage(Operator):
    bl_idname = "tutorial.validate_stage"
    bl_label = "確認"

    def execute(self, context):
        props = context.scene.tutorial_props

        if props.first_attempt_time <= 0.0:
            props.first_attempt_time = time.time()

        ok, message, reason, hints = StageManager.validate_stage(context)

        props.last_result_ok = ok
        props.last_reason = reason
        props.last_message = message

        existing = [r for r in (props.reason_sequence or "").split(",") if r]
        existing.append(reason)
        props.reason_sequence = ",".join(existing)

        if ok:
            props.stage_complete = True
            props.failed_validate_count = 0
            props.last_hints = ""
        else:
            props.failed_validate_count += 1
            escalated = StageManager.apply_hint_escalation(hints, props.failed_validate_count, props.difficulty_mode)
            props.last_hints = "\n".join(escalated) if escalated else ""
            # Ch5はマテリアルが積み上がるため、Ch3 St2はundo_countが消えるためリセットしない
            if props.current_chapter == 5:
                pass
            elif props.current_chapter == 3 and props.current_stage == 2:
                pass
            elif True:
                try:
                    StageManager.reset_scene_for_chapter(context)
                except Exception:
                    pass

        StageManager.log_validate_event(context, ok=ok, reason=reason, message=message, auto=False)
        self.report({'INFO'} if ok else {'WARNING'}, message)
        return {'FINISHED'}

class TUTORIAL_OT_next_stage(Operator):
    bl_idname = "tutorial.next_stage"
    bl_label = "次へ"

    def execute(self, context):
        props = context.scene.tutorial_props
        StageManager.finalize_current_run(context, completed=True)

        max_stages_per_chapter = {1: 4, 2: 4, 3: 9, 4: 4, 5: 4, 6: 5, 7: 1}
        max_stages = max_stages_per_chapter.get(props.current_chapter, 1)

        if props.current_stage < max_stages:
            props.current_stage += 1
        else:
            if props.current_chapter < 7:
                props.current_chapter += 1
                props.current_stage = 1
            else:
                StageManager.turn_off_scene_camera_and_lights()
                self.report({'INFO'}, "完了!（カメラ・ライトをOFFにしました）")
                props.stage_start_time = 0.0
                return {'FINISHED'}

        props.stage_complete = False
        props.failed_validate_count = 0
        props.stage_start_time = 0.0
        props.current_stall_seconds = 0.0
        props.last_result_ok = True
        props.last_reason = ""
        props.last_message = ""
        props.last_hints = ""
        props.setup_count = 1
        props.reason_sequence = ""
        props.first_attempt_time = 0.0
        props.undo_count = 0
        props.survey_difficulty = 0

        try:
            StageManager.reset_scene_for_chapter(context)
            props.stage_start_time = time.time()
            props.monitoring_active = True
            StageManager.log_setup_event(context)
        except Exception as e:
            self.report({'WARNING'}, f"自動セットアップに失敗: {e}（手動でセットアップしてください）")

        return {'FINISHED'}

class TUTORIAL_OT_reset(Operator):
    bl_idname = "tutorial.reset"
    bl_label = "リセット"

    def execute(self, context):
        props = context.scene.tutorial_props
        StageManager.finalize_current_run(context, completed=False)

        props.current_chapter = 1
        props.current_stage = 1
        props.stage_complete = False
        props.monitoring_active = False

        props.failed_validate_count = 0
        props.stage_start_time = 0.0
        props.current_stall_seconds = 0.0
        props.last_result_ok = True
        props.last_reason = ""
        props.last_message = ""
        props.last_hints = ""
        props.setup_count = 0
        props.reason_sequence = ""
        props.first_attempt_time = 0.0
        props.undo_count = 0
        props.survey_difficulty = 0
        return {'FINISHED'}

class TUTORIAL_OT_goto_chapter(Operator):
    bl_idname = "tutorial.goto_chapter"
    bl_label = "チャプターへ"
    chapter: IntProperty(default=1, min=1, max=7)

    def execute(self, context):
        props = context.scene.tutorial_props
        StageManager.finalize_current_run(context, completed=False)

        props.current_chapter = self.chapter
        props.current_stage = 1
        props.stage_complete = False
        props.monitoring_active = False

        props.failed_validate_count = 0
        props.stage_start_time = 0.0
        props.current_stall_seconds = 0.0
        props.last_result_ok = True
        props.last_reason = ""
        props.last_message = ""
        props.last_hints = ""
        props.setup_count = 0
        props.reason_sequence = ""
        props.first_attempt_time = 0.0
        props.undo_count = 0
        props.survey_difficulty = 0
        return {'FINISHED'}

class TUTORIAL_OT_stage_prev(Operator):
    bl_idname = "tutorial.stage_prev"
    bl_label = "← 前のステージ"
    bl_description = "前のステージに移動してセットアップします"

    def execute(self, context):
        props = context.scene.tutorial_props
        max_stages_per_chapter = {1: 4, 2: 4, 3: 9, 4: 4, 5: 4, 6: 5, 7: 1}

        from_ch, from_st = props.current_chapter, props.current_stage
        StageManager.finalize_current_run(context, completed=False)

        if props.current_stage > 1:
            props.current_stage -= 1
        elif props.current_chapter > 1:
            props.current_chapter -= 1
            props.current_stage = max_stages_per_chapter.get(props.current_chapter, 1)
        else:
            self.report({'INFO'}, "最初のステージです")
            return {'FINISHED'}

        StageManager.log_navigation_event(
            context, from_ch, from_st,
            props.current_chapter, props.current_stage, "prev"
        )
        self._reset_and_setup(context, props)
        return {'FINISHED'}

    def _reset_and_setup(self, context, props):
        props.stage_complete = False
        props.failed_validate_count = 0
        props.stage_start_time = 0.0
        props.current_stall_seconds = 0.0
        props.last_result_ok = True
        props.last_reason = ""
        props.last_message = ""
        props.last_hints = ""
        props.setup_count = 1
        props.reason_sequence = ""
        props.first_attempt_time = 0.0
        props.undo_count = 0
        props.survey_difficulty = 0
        try:
            StageManager.reset_scene_for_chapter(context)
            props.stage_start_time = time.time()
            props.monitoring_active = True
            StageManager.log_setup_event(context)
        except Exception as e:
            self.report({'WARNING'}, f"セットアップに失敗: {e}（手動でセットアップしてください）")


class TUTORIAL_OT_stage_next_free(Operator):
    bl_idname = "tutorial.stage_next_free"
    bl_label = "次のステージ →"
    bl_description = "クリア判定なしで次のステージに移動してセットアップします"

    def execute(self, context):
        props = context.scene.tutorial_props
        max_stages_per_chapter = {1: 4, 2: 4, 3: 9, 4: 4, 5: 4, 6: 5, 7: 1}
        max_stages = max_stages_per_chapter.get(props.current_chapter, 1)

        from_ch, from_st = props.current_chapter, props.current_stage
        StageManager.finalize_current_run(context, completed=False)

        if props.current_stage < max_stages:
            props.current_stage += 1
        elif props.current_chapter < 6:
            props.current_chapter += 1
            props.current_stage = 1
        else:
            self.report({'INFO'}, "最後のステージです")
            return {'FINISHED'}

        StageManager.log_navigation_event(
            context, from_ch, from_st,
            props.current_chapter, props.current_stage, "next"
        )
        self._reset_and_setup(context, props)
        return {'FINISHED'}

    def _reset_and_setup(self, context, props):
        props.stage_complete = False
        props.failed_validate_count = 0
        props.stage_start_time = 0.0
        props.current_stall_seconds = 0.0
        props.last_result_ok = True
        props.last_reason = ""
        props.last_message = ""
        props.last_hints = ""
        props.setup_count = 1
        props.reason_sequence = ""
        props.first_attempt_time = 0.0
        props.undo_count = 0
        props.survey_difficulty = 0
        try:
            StageManager.reset_scene_for_chapter(context)
            props.stage_start_time = time.time()
            props.monitoring_active = True
            StageManager.log_setup_event(context)
        except Exception as e:
            self.report({'WARNING'}, f"セットアップに失敗: {e}（手動でセットアップしてください）")


class TUTORIAL_OT_rate_difficulty(Operator):
    bl_idname = "tutorial.rate_difficulty"
    bl_label = "難易度を評価"
    bl_description = "このステージの難しさを記録します"
    difficulty: IntProperty(default=1, min=1, max=5)

    def execute(self, context):
        props = context.scene.tutorial_props
        props.survey_difficulty = self.difficulty
        StageManager.append_participant_event(context, {
            "t": StageManager._now(),
            "participant_id": StageManager._safe_participant_id(props.participant_id),
            "event": "survey",
            "chapter": props.current_chapter,
            "stage": props.current_stage,
            "difficulty": self.difficulty,
        })
        return {'FINISHED'}

class TUTORIAL_OT_monitoring(Operator):
    bl_idname = "wm.tutorial_monitoring"
    bl_label = "Tutorial Monitoring"
    _timer = None
    _last_check = 0.0

    def modal(self, context, event):
        if event.type == 'TIMER':
            try:
                props = context.scene.tutorial_props
                if not props.monitoring_active:
                    wm = context.window_manager
                    if self._timer:
                        wm.event_timer_remove(self._timer)
                    return {'FINISHED'}

                props.current_stall_seconds = StageManager.get_stall_seconds(context)

                current_time = time.time()
                if current_time - self._last_check > 0.2:
                    StageManager.check_stage(context)
                    self._last_check = current_time

                for area in context.screen.areas:
                    if area.type == 'VIEW_3D':
                        area.tag_redraw()
                        break
            except Exception:
                pass
        return {'PASS_THROUGH'}

    def execute(self, context):
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.1, window=context.window)
        self._last_check = time.time()
        wm.modal_handler_add(self)
        return {'RUNNING_MODAL'}

# =====================================================
# PANEL
# =====================================================

class TUTORIAL_PT_main(Panel):
    bl_label = "3DCG チュートリアル"
    bl_idname = "TUTORIAL_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Tutorial"

    def draw(self, context):
        layout = self.layout
        props = context.scene.tutorial_props

        pbox = layout.box()
        pbox.label(text="参加者ログ（DIR_PATH + 安全ボタン）")
        pbox.prop(props, "participant_id")
        pbox.prop(props, "log_dir")

        row = pbox.row(align=True)
        row.operator("tutorial.set_default_log_dir", text="既定フォルダに設定")
        row.operator("tutorial.open_log_folder", text="ログフォルダを開く")

        pbox.prop(props, "enable_participant_logging", text="ログ記録を有効化")
        pbox.prop(props, "difficulty_mode", text="難易度")
        pbox.operator("tutorial.export_stage_summary_csv", text="ステージ集計CSV出力")

        if props.participant_log_path:
            pbox.label(text=f"ログ: {os.path.basename(props.participant_log_path)}")
        if props.participant_log_error:
            pbox.label(text=f"注意: {props.participant_log_error}")

        cbox = layout.box()
        cbox.label(text="チャプター選択")
        row = cbox.row(align=True)
        for i in range(1, 8):
            op = row.operator("tutorial.goto_chapter", text=f"第{i}章", depress=(props.current_chapter == i))
            op.chapter = i
        cbox.operator("tutorial.confirm_all_chapters", text="全チャプター確認")

        info = StageManager.get_stage_info(props.current_chapter, props.current_stage)
        sbox = layout.box()
        sbox.label(text=info.get("title", ""))
        max_stages_per_chapter = {1: 4, 2: 4, 3: 9, 4: 4, 5: 4, 6: 5, 7: 1}
        sbox.label(text=f"ステージ {props.current_stage}/{max_stages_per_chapter.get(props.current_chapter, 1)}")
        sbox.label(text=info.get("name", ""))
        sbox.separator()
        sbox.label(text=info.get("description", ""))

        if info.get("details"):
            sbox.separator()
            for line in info["details"].split("\n"):
                sbox.label(text=line)

        if props.current_chapter == 7:
            sbox.separator()
            sbox.operator("tutorial.render_and_mark_saved", text="補助: レンダーして保存（自動）")
            if props.final_render_saved_path:
                sbox.label(text=f"保存検出: {props.final_render_saved_path}")

        current_new, _ = StageManager.get_accumulated_shortcuts(
            props.current_chapter, props.current_stage
        )
        if current_new:
            nbox = layout.box()
            nbox.label(text="★ 今回のショートカット", icon='KEYINGSET')
            for action, keys in current_new:
                row = nbox.split(factor=0.45)
                row.label(text=action)
                row.label(text=keys)

        if not props.last_result_ok and props.last_message:
            fb = layout.box()
            fb.label(text="フィードバック")
            fb.label(text=props.last_message)
            if props.last_hints:
                fb.separator()
                for line in props.last_hints.split("\n"):
                    fb.label(text=f"- {line}")

        layout.separator()
        col = layout.column()
        col.scale_y = 1.2
        col.operator("tutorial.setup_stage", text="セットアップ")
        if props.monitoring_active:
            col.label(text="● 監視中（自動判定）")
        else:
            col.operator("wm.tutorial_monitoring", text="監視開始")
        col.operator("tutorial.validate_stage", text="確認")
        if props.stage_complete:
            col.operator("tutorial.next_stage", text="次へ")
        layout.operator("tutorial.reset", text="リセット")
        layout.operator("tutorial.finish_and_turn_off", text="完了（カメラ・ライトOFF）")

        layout.separator()
        nav = layout.row(align=True)
        nav.scale_y = 1.3
        max_st = max_stages_per_chapter.get(props.current_chapter, 1)
        at_start = (props.current_chapter == 1 and props.current_stage == 1)
        at_end   = (props.current_chapter == 7 and props.current_stage == max_st)
        left = nav.row()
        left.enabled = not at_start
        left.operator("tutorial.stage_prev", text="← 前のステージ", icon='TRIA_LEFT')
        right = nav.row()
        right.enabled = not at_end
        right.operator("tutorial.stage_next_free", text="次のステージ →", icon='TRIA_RIGHT')

        layout.separator()
        layout.label(text=f"失敗回数: {props.failed_validate_count}回")

# =====================================================
# SHORTCUT LIST SUB-PANEL
# =====================================================

class TUTORIAL_PT_shortcuts(Panel):
    bl_label = "ショートカット一覧（累積）"
    bl_idname = "TUTORIAL_PT_shortcuts"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Tutorial"
    bl_parent_id = "TUTORIAL_PT_main"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        props = context.scene.tutorial_props

        _, all_sections = StageManager.get_accumulated_shortcuts(
            props.current_chapter, props.current_stage
        )

        if not all_sections:
            layout.label(text="セットアップするとショートカットが表示されます")
            return

        for section, entries in all_sections.items():
            box = layout.box()
            box.label(text=section, icon='KEYINGSET')
            for action, keys in entries:
                row = box.split(factor=0.45)
                row.label(text=action)
                row.label(text=keys)

# =====================================================
# UNDO HANDLER
# =====================================================

@bpy.app.handlers.persistent
def _tutorial_undo_handler(*args):
    """Ctrl+Z 検出: 監視中のみカウント＆ログ記録"""
    try:
        scene = bpy.context.scene
        if not scene or not hasattr(scene, 'tutorial_props'):
            return
        props = scene.tutorial_props
        if not props.monitoring_active:
            return
        props.undo_count += 1
        StageManager.append_participant_event(bpy.context, {
            "t": StageManager._now(),
            "participant_id": StageManager._safe_participant_id(props.participant_id),
            "event": "undo",
            "chapter": props.current_chapter,
            "stage": props.current_stage,
            "undo_count_stage": int(props.undo_count),
        })
    except Exception:
        pass

# =====================================================
# REGISTER
# =====================================================

classes = (
    VertexPos,
    StageRun,
    TUTORIAL_PG_Properties,
    TUTORIAL_OT_set_default_log_dir,
    TUTORIAL_OT_open_log_folder,
    TUTORIAL_OT_confirm_all_chapters,
    TUTORIAL_OT_export_stage_summary_csv,
    TUTORIAL_OT_render_and_mark_saved,
    TUTORIAL_OT_finish_and_turn_off,
    TUTORIAL_OT_setup_stage,
    TUTORIAL_OT_validate_stage,
    TUTORIAL_OT_next_stage,
    TUTORIAL_OT_reset,
    TUTORIAL_OT_goto_chapter,
    TUTORIAL_OT_stage_prev,
    TUTORIAL_OT_stage_next_free,
    TUTORIAL_OT_rate_difficulty,
    TUTORIAL_OT_monitoring,
    TUTORIAL_PT_main,
    TUTORIAL_PT_shortcuts,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.tutorial_props = bpy.props.PointerProperty(type=TUTORIAL_PG_Properties)
    if _tutorial_undo_handler not in bpy.app.handlers.undo_post:
        bpy.app.handlers.undo_post.append(_tutorial_undo_handler)

def unregister():
    if _tutorial_undo_handler in bpy.app.handlers.undo_post:
        bpy.app.handlers.undo_post.remove(_tutorial_undo_handler)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.tutorial_props

if __name__ == "__main__":
    register()