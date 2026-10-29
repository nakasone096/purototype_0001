# -*- coding: utf-8 -*-
bl_info = {
    "name": "3DCG Tutorial Simulator",
    "blender": (4, 2, 0),
    "version": (0, 9, 1),
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

# 各チャプターのステージ数（Ch1・Ch3・Ch4の末尾は「復習」ステージ）
MAX_STAGES = {1: 5, 2: 4, 3: 10, 4: 5, 5: 4, 6: 5, 7: 1, 8: 6}

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
    (4, 2, "モディファイアー", "ミラー",             "レンチ → 追加 → 生成 → ミラー"),
    (4, 3, "モディファイアー", "ソリッド化",          "レンチ → 追加 → 生成 → ソリッド化"),
    (4, 4, "モディファイアー", "ベベル",             "レンチ → 追加 → 生成 → ベベル"),
    (4, 5, "モディファイアー", "ベベルの調整",        "パネルの「量」「セグメント」の数値"),
    # --- Ch5: スカルプト ---
    (5, 1, "スカルプト",  "ブラシサイズ",     "F → ドラッグ"),
    (5, 1, "スカルプト",  "強さ調整",         "Shift + F → ドラッグ"),
    (5, 1, "スカルプト",  "反転（凹み）",      "Ctrl + ドラッグ"),
    # --- Ch6: マテリアル ---
    (6, 1, "マテリアル",  "ノード追加",       "Shift + A（ノードエディター内）"),
    (6, 1, "マテリアル",  "ノード削除",       "X（ノードエディター内）"),
    (6, 3, "マテリアル",  "画像を選ぶ",       "画像ノードの画像欄 → fruit_apple"),
]

# 難易度「ふつう」「むずかしい」で、手順の全文の代わりに表示する機能の説明
STAGE_ABOUT = {
    (1, 1): "選択とは\n  操作するオブジェクトを決めること\n  選んだものだけが動く・変わる",
    (1, 2): "移動とは\n  オブジェクトの位置を変えること\n  X・Y・Zの軸ごとに動かせる",
    (1, 3): "回転とは\n  オブジェクトの向きを変えること\n  軸を決めて角度で回す",
    (1, 4): "拡大縮小（スケール）とは\n  オブジェクトの大きさを変えること\n  倍率で指定する（2なら2倍）",
    (1, 5): "復習：変えた形を元に戻そう\n  回転0°・スケール1が元の状態\n  数値を見つけて直すこともできる",
    (2, 1): "パンとは\n  視点を上下左右に平行移動すること\n  オブジェクト自体は動かない",
    (2, 2): "ズームとは\n  視点を近づけたり遠ざけたりすること",
    (2, 3): "ビュー回転とは\n  視点をぐるりと回すこと\n  裏側も見られる",
    (2, 4): "ビュー操作の組み合わせ\n  回す・ずらす・寄るを使い分けて\n  見たい角度に合わせる",
    (3, 1): "オブジェクトの追加とは\n  新しい形（立方体・球など）を\n  シーンに足すこと",
    (3, 2): "元に戻す（アンドゥ）とは\n  直前の操作を取り消すこと\n  失敗しても大丈夫",
    (3, 3): "削除とは\n  選んだオブジェクトを消すこと",
    (3, 4): "エディットモードとは\n  形そのもの（頂点・辺・面）を\n  直接いじるモード",
    (3, 5): "頂点とは\n  形をつくる点のこと\n  頂点を動かすと形が変わる",
    (3, 6): "エッジ（辺）とは\n  頂点と頂点をつなぐ線のこと",
    (3, 7): "フェース（面）とは\n  辺で囲まれた平らな部分のこと",
    (3, 8): "押し出し（エクストルード）とは\n  選んだ面を外に伸ばして\n  出っ張りをつくる機能",
    (3, 9): "ループカットとは\n  メッシュをぐるっと一周切って\n  新しい辺のループを足す機能",
    (3, 10): "復習：ここまでの組み合わせ\n  追加 → ループカット → 2倍に拡大\n  順番は自分で考えよう",
    (4, 1): "サブディビジョンサーフェスとは\n  面を細かく分けて\n  形をなめらかにする機能",
    (4, 2): "ミラーとは\n  片側の形を反対側にも映して\n  左右対称にする機能",
    (4, 3): "ソリッド化とは\n  面に厚みをつける機能",
    (4, 4): "ベベルとは\n  角を丸める（面取りする）機能\n  量＝大きさ／セグメント＝なめらかさ",
    (4, 5): "復習：ベベルの数値を調整しよう\n  セグメントを増やすほど\n  角がなめらかな丸みになる",
    (5, 1): "スカルプトモードとは\n  粘土をこねるように形を変えるモード",
    (5, 2): "Drawブラシとは\n  表面を盛り上げるブラシ\n  Ctrlを押すと凹ませられる",
    (5, 3): "Smoothブラシとは\n  表面をなめらかにならすブラシ",
    (5, 4): "Grabブラシとは\n  形をつまんで動かすブラシ",
    (6, 1): "マテリアルとは\n  オブジェクトの色や質感の設定のこと",
    (6, 2): "ベースカラーとは\n  オブジェクトの基本の色のこと",
    (6, 3): "画像テクスチャとは\n  画像をオブジェクトの表面に貼ること",
    (6, 4): "ノード接続とは\n  ノードどうしを線でつないで\n  画像の色をベースカラーに使うこと",
    (6, 5): "質感（粗さ・メタリック）とは\n  粗さ：ツルツル⇔ザラザラ\n  メタリック：金属らしさ",
}

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

# Blender の FloatProperty は 32bit 浮動小数点のため、UNIX時間（約17億）をそのまま保存すると
# 最大±64秒ずれる。ステージ開始時刻などプロパティに保存する時刻は、起動時からの相対秒（_rel）にする。
_T0 = time.time()

# Ctrl+Z の発生時刻（相対秒）。シーンのプロパティはUndoで巻き戻るため、シーンの外に持つ
_UNDO_TIMES = []


class StageManager:
    _st_enter_t = 0.0   # 現在のステージに入った時刻（相対秒・シーン外）

    # -----------------------------
    # Time/helpers
    # -----------------------------
    @staticmethod
    def _now():
        return time.time()

    @staticmethod
    def _rel():
        return time.time() - _T0

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
    def desktop_dir() -> str:
        """実際のデスクトップのパス（OneDrive配下などにリダイレクトされていても取得できる）。"""
        if os.name == "nt":
            try:
                import winreg
                with winreg.OpenKey(
                        winreg.HKEY_CURRENT_USER,
                        r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders") as k:
                    path, _ = winreg.QueryValueEx(k, "Desktop")
                if path and os.path.isdir(path):
                    return path
            except Exception:
                pass
        return os.path.join(os.path.expanduser("~"), "Desktop")

    @staticmethod
    def auto_log_dir(props) -> str:
        """デスクトップ/学籍番号_addon （例：23DB999_addon）。参加者ID未入力なら空文字。"""
        pid = StageManager._safe_participant_id(props.participant_id)
        if not pid:
            return ""
        return os.path.join(StageManager.desktop_dir(), f"{pid}_addon")

    @staticmethod
    def resolve_log_dir(props) -> str:
        """欄が空なら、デスクトップ/学籍番号_addon を使う。それも決められなければ既定フォルダ。"""
        return (props.log_dir or "").strip() or StageManager.auto_log_dir(props) or StageManager.default_log_dir()

    @staticmethod
    def ensure_dir_exists(path: str) -> str:
        abs_path = bpy.path.abspath(path)
        os.makedirs(abs_path, exist_ok=True)
        return abs_path

    @staticmethod
    def open_folder_in_os(path: str):
        abs_path = StageManager.ensure_dir_exists(path)
        if os.name == "nt":
            # os.startfile() はBlender埋め込みPythonから呼ぶとCOM状態の衝突で
            # クラッシュすることがあるため、explorer.exeをプロセス起動する方式にする
            subprocess.Popen(["explorer", abs_path])
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
        return max(0.0, StageManager._rel() - props.stage_start_time)

    @staticmethod
    def ensure_participant_log_file(context) -> bool:
        props = context.scene.tutorial_props
        pid = StageManager._safe_participant_id(props.participant_id)

        if not pid:
            props.participant_log_error = "参加者IDが未入力です"
            return False

        try:
            dir_abs = StageManager.ensure_dir_exists(StageManager.resolve_log_dir(props))
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
        log_path = os.path.join(dir_abs, f"{pid}_addon_{ts}.jsonl")

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
            "stage_started_at": (_T0 + float(props.stage_start_time)) if props.stage_start_time > 0 else 0.0,
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

        now = StageManager._rel()
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
    # No-undo scene helpers (bpy.data 直接操作でアンドゥスタックに積まない)
    # -----------------------------
    @staticmethod
    def _clear_scene_no_undo():
        """全オブジェクトをアンドゥなしで削除する"""
        try:
            bpy.ops.object.mode_set(mode='OBJECT')
        except Exception:
            pass
        for obj in list(bpy.data.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        for mesh in [m for m in bpy.data.meshes if m.users == 0]:
            bpy.data.meshes.remove(mesh)
        bpy.context.view_layer.update()

    @staticmethod
    def _make_cube_no_undo(name="Cube", size=2.0, location=(0.0, 0.0, 0.0)):
        """キューブをアンドゥなしで作成して返す"""
        mesh = bpy.data.meshes.new(name)
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=size)
        bm.to_mesh(mesh)
        bm.free()
        obj = bpy.data.objects.new(name, mesh)
        obj.location = location
        bpy.context.collection.objects.link(obj)
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.context.view_layer.update()
        return obj

    @staticmethod
    def _make_uvsphere_no_undo(name="Sphere", radius=1.0, location=(0.0, 0.0, 0.0)):
        """UV球をアンドゥなしで作成して返す"""
        mesh = bpy.data.meshes.new(name)
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=radius)
        bm.to_mesh(mesh)
        bm.free()
        obj = bpy.data.objects.new(name, mesh)
        obj.location = location
        bpy.context.collection.objects.link(obj)
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.context.view_layer.update()
        return obj

    @staticmethod
    def _make_torus_no_undo(name="Torus", location=(0.0, 0.0, 0.0)):
        """トーラスをアンドゥなしで作成して返す（bmesh spin利用）"""
        mesh = bpy.data.meshes.new(name)
        bm = bmesh.new()
        # 小円を作ってスピンでトーラス生成
        bmesh.ops.create_circle(bm, cap_ends=False, radius=0.25, segments=12)
        # 小円を X+1 に移動
        for v in bm.verts:
            v.co.x += 1.0
        # Z軸周りにスピン（360度、大円）
        bmesh.ops.spin(
            bm,
            geom=bm.verts[:] + bm.edges[:],
            axis=(0, 0, 1),
            cent=(0, 0, 0),
            angle=math.radians(360),
            steps=24,
            use_merge=True,
        )
        bm.to_mesh(mesh)
        bm.free()
        obj = bpy.data.objects.new(name, mesh)
        obj.location = location
        bpy.context.collection.objects.link(obj)
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.context.view_layer.update()
        return obj

    # -----------------------------
    # Scene reset (shared by setup_stage, validate on fail, next_stage)
    # -----------------------------
    @staticmethod
    def reset_scene_for_chapter(context):
        """シーンオブジェクトのみリセット。bpy.data 直接操作でアンドゥスタックに積まない。"""
        props = context.scene.tutorial_props
        ch = props.current_chapter

        if ch == 1:
            StageManager._clear_scene_no_undo()
            cube = StageManager._make_cube_no_undo("Cube", size=2.0)
            props.initial_position = tuple(cube.location)
            props.initial_rotation = tuple(cube.rotation_euler)
            props.initial_scale = tuple(cube.scale)
            # St1はキューブを「選択する」課題なので初期状態は非選択にする
            if props.current_stage == 1:
                cube.select_set(False)
                bpy.context.view_layer.objects.active = None
            elif props.current_stage == 5:
                # 復習：回転とスケールを変えた状態から始める（元に戻す課題）
                cube.rotation_euler = tuple(math.radians(45.0) for _ in range(3))
                cube.scale = (3.0, 3.0, 3.0)
                bpy.context.view_layer.objects.active = cube
                cube.select_set(True)

        elif ch == 2:
            # キューブのトランスフォームをリセット
            for obj in bpy.data.objects:
                if obj.type == 'MESH' and obj.name == "Cube":
                    obj.location = (0.0, 0.0, 0.0)
                    obj.rotation_euler = (0.0, 0.0, 0.0)
                    obj.scale = (1.0, 1.0, 1.0)
                    break
            # 視点を指定位置にリセットしてから初期値として記録する
            space = StageManager.get_view3d_space(context)
            if space and space.region_3d:
                r3d = space.region_3d
                from mathutils import Euler
                _cam_pos = (10.0, -9.0, 3.0)
                r3d.view_distance = math.sqrt(
                    _cam_pos[0]**2 + _cam_pos[1]**2 + _cam_pos[2]**2
                )
                r3d.view_location = (0.0, 0.0, 0.0)
                r3d.view_rotation = Euler(
                    (math.radians(80), math.radians(0), math.radians(45)), 'XYZ'
                ).to_quaternion()
                bpy.context.view_layer.update()
                props.initial_view_distance = r3d.view_distance
                props.initial_view_location = tuple(r3d.view_location)
                props.initial_view_rotation = tuple(r3d.view_rotation)

        elif ch == 3:
            st = props.current_stage
            StageManager._clear_scene_no_undo()

            if st in (1, 10):
                pass  # Shift+A ステージ／組み合わせ（復習）: 空の状態からスタート

            elif st == 2:
                cube = StageManager._make_cube_no_undo("Cube", size=2.0)
                props.initial_position = (0.0, 0.0, 0.0)

            elif st == 3:
                StageManager._make_cube_no_undo("Cube", size=2.0)

            elif st == 4:
                # St4: Tab切り替えの課題なのでオブジェクトモードで置く
                cube = StageManager._make_cube_no_undo("Cube", size=2.0)
                props.initial_vertex_count = len(cube.data.vertices)
                props.initial_edge_count = len(cube.data.edges)
                props.initial_face_count = len(cube.data.polygons)

            else:
                # St5〜: Editモードから始める（頂点・辺・面・押し出し・ループカット）
                cube = StageManager._make_cube_no_undo("Cube", size=2.0)
                bpy.ops.object.mode_set(mode='EDIT')
                bpy.context.view_layer.update()
                props.initial_vertex_count = len(cube.data.vertices)
                props.initial_edge_count = len(cube.data.edges)
                props.initial_face_count = len(cube.data.polygons)

        elif ch == 4:
            StageManager._clear_scene_no_undo()
            if props.current_stage == 3:
                obj_new = StageManager._make_torus_no_undo("Torus")
            else:
                obj_new = StageManager._make_cube_no_undo("Cube", size=2.0)
            obj_new.modifiers.clear()
            if props.current_stage == 5:
                # 復習：すでに付いているベベル（セグメント1）を調整する課題
                bev = obj_new.modifiers.new("Bevel", 'BEVEL')
                bev.segments = 1
                bev.width = 0.1

        elif ch == 5:
            StageManager._clear_scene_no_undo()
            sphere = StageManager._make_uvsphere_no_undo("Sphere", radius=1.0)
            # B3修正: モード切替ドロップダウンに選択肢を出すため、確実に選択・アクティブ化する
            bpy.context.view_layer.objects.active = sphere
            sphere.select_set(True)
            bpy.context.view_layer.update()
            props.initial_vertex_positions.clear()
            for v in sphere.data.vertices:
                item = props.initial_vertex_positions.add()
                item.co = v.co.copy()

        elif ch == 6:
            # マテリアルノードは消さない。初回のみキューブを作成する
            try:
                bpy.ops.object.mode_set(mode='OBJECT')
            except Exception:
                pass
            cube = StageManager.find_cube()
            if cube is None:
                StageManager._clear_scene_no_undo()
                StageManager._make_cube_no_undo("Cube", size=2.0)
            # 画像テクスチャ用の画像を読み込み済みにしておく（ファイルブラウザを使わせない）
            try:
                img_path = StageManager._find_reference_image_path(REFERENCE_IMAGE_FILENAME)
                if img_path:
                    img = bpy.data.images.load(img_path, check_existing=True)
                    img.use_fake_user = True
            except Exception as e:
                print(f"[Tutorial] 画像の読み込みに失敗: {e}")
            space = StageManager.get_view3d_space(context)
            if space:
                space.shading.type = 'MATERIAL'
            StageManager.open_shader_editor_at_bottom()

        elif ch == 7:
            # 最終制作: リンゴを作る
            props.final_render_saved_path = ""
            StageManager._clear_scene_no_undo()
            apple = StageManager._make_uvsphere_no_undo("Apple", radius=1.0)
            # スムーズシェード（これだけ bpy.ops が必要）
            try:
                for poly in apple.data.polygons:
                    poly.use_smooth = True
                apple.data.update()
            except Exception:
                pass
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
            StageManager.place_reference_image()

        elif ch == 8:
            # テストフェーズ: 学習の定着確認
            props = context.scene.tutorial_props
            st = props.current_stage
            StageManager._clear_scene_no_undo()

            if st == 1:
                # キューブをY方向に+3移動（Ch1応用）
                cube = StageManager._make_cube_no_undo("Cube", size=2.0)
                cube.select_set(False)
                bpy.context.view_layer.objects.active = None
                props.initial_position = (0.0, 0.0, 0.0)

            elif st == 2:
                # ビュー回転＋ズーム（Ch2応用）
                StageManager._make_cube_no_undo("Cube", size=2.0)
                space = StageManager.get_view3d_space(context)
                if space and space.region_3d:
                    from mathutils import Euler
                    r3d = space.region_3d
                    r3d.view_distance = 7.0
                    r3d.view_location = (0.0, 0.0, 0.0)
                    r3d.view_rotation = Euler(
                        (math.radians(80), math.radians(0), math.radians(45)), 'XYZ'
                    ).to_quaternion()
                    bpy.context.view_layer.update()
                    props.initial_view_distance = r3d.view_distance
                    props.initial_view_rotation = tuple(r3d.view_rotation)

            elif st == 3:
                pass  # シーンは空: プレイヤーが自分で追加する

            elif st == 4:
                # Bevelモディファイア追加（Ch4応用）
                obj = StageManager._make_cube_no_undo("Cube", size=2.0)
                obj.modifiers.clear()

            elif st == 5:
                # Grabブラシで球を変形（Ch5応用）
                sphere = StageManager._make_uvsphere_no_undo("Sphere", radius=1.0)
                props.initial_vertex_positions.clear()
                for v in sphere.data.vertices:
                    item = props.initial_vertex_positions.add()
                    item.co = v.co.copy()

            elif st == 6:
                # マテリアル作成＋Roughness変更（Ch6応用）
                StageManager._make_cube_no_undo("Cube", size=2.0)
                space = StageManager.get_view3d_space(context)
                if space:
                    space.shading.type = 'MATERIAL'
                StageManager.open_shader_editor_at_bottom()

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
        if chapter_num == 8:
            stages = {
                1: {
                    "title": "第8章: 確認テスト",
                    "name": "テスト1: 移動",
                    "description": "キューブを Y 方向に +3 移動してください",
                    "details": "【ヒントなし】\n"
                               "学んだ操作を思い出して挑戦しよう",
                },
                2: {
                    "title": "第8章: 確認テスト",
                    "name": "テスト2: ビュー操作",
                    "description": "ビューを回転させ、さらにズームしてください",
                    "details": "【ヒントなし】\n"
                               "学んだ操作を思い出して挑戦しよう",
                },
                3: {
                    "title": "第8章: 確認テスト",
                    "name": "テスト3: モデリング",
                    "description": "立方体を追加し、Editモードでループカットを入れてください",
                    "details": "【ヒントなし】\n"
                               "学んだ操作を思い出して挑戦しよう",
                },
                4: {
                    "title": "第8章: 確認テスト",
                    "name": "テスト4: モディファイア",
                    "description": "キューブに Bevel モディファイアを追加してください",
                    "details": "【ヒントなし】\n"
                               "学んだ操作を思い出して挑戦しよう",
                },
                5: {
                    "title": "第8章: 確認テスト",
                    "name": "テスト5: スカルプト",
                    "description": "Grab ブラシで球を変形させてください",
                    "details": "【ヒントなし】\n"
                               "学んだ操作を思い出して挑戦しよう",
                },
                6: {
                    "title": "第8章: 確認テスト",
                    "name": "テスト6: マテリアル",
                    "description": "マテリアルを作成し、粗さ（Roughness）を 0.2 以下にしてください",
                    "details": "【ヒントなし】\n"
                               "学んだ操作を思い出して挑戦しよう",
                },
            }
            return stages.get(stage_num, {})

        if chapter_num == 4:
            stages = {
                1: {
                    "title": "第4章: モディファイアー",
                    "name": "ステージ1: サブディビジョンサーフェス",
                    "description": "Subdivision Surface を追加してください",
                    "details": "① 右のプロパティパネルで\n"
                               "   青いレンチアイコン（モディファイアー）を開く\n"
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
                               "② Ctrl+R でキューブ中心に縦にループカットを入れる\n"
                               "   （黄色い線が出たら1回クリック→もう1回クリックで確定）\n"
                               "③ Y座標が負の側の頂点4つをボックス選択\n"
                               "④ X キー →「頂点」で削除\n"
                               "⑤ Tab でオブジェクトモードに戻る\n"
                               "⑥ モディファイアーを追加 →「生成」→「ミラー」\n"
                               "⑦ 「座標軸」を「Y」に変更する\n"
                               "   → 削除した側が自動で補完される！",
                },
                3: {
                    "title": "第4章: モディファイアー",
                    "name": "ステージ3: ソリッド化（Solidify）",
                    "description": "トーラスに Solidify モディファイアーを追加してください",
                    "details": "① トーラス（ドーナツ型）がセットアップされています\n"
                               "② モディファイアーを追加\n"
                               "   →「生成」→「ソリッド化」\n"
                               "③ 数値の説明\n"
                               "\n"
                               "   ・幅\n"
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
                5: {
                    "title": "第4章: モディファイアー",
                    "name": "ステージ5: ベベルを調整しよう（復習）",
                    "description": "ベベルの丸みをなめらかにしてください（セグメントを3以上に）",
                    "details": "① キューブにベベルがすでに付いています\n"
                               "② 右のプロパティパネルのレンチアイコンを開く\n"
                               "③ ベベルの「セグメント」の数字を 3 以上にする\n"
                               "   → 角がなめらかな丸みになる",
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
                               "③ 好きな数字を入力（例: 2 で2倍）\n"
                               "④ Enter で確定\n"
                               "   （軸固定: S → X/Y/Z → 数字 → Enter）",
                },
                5: {
                    "title": "第1章: 基本操作",
                    "name": "ステージ5: 元に戻そう（復習）",
                    "description": "回転とスケールが変わったキューブを、元の状態（回転0°・スケール1）に戻してください",
                    "details": "① 今のキューブは 回転 X・Y・Z=45°、スケール 3 になっています\n"
                               "② 回転をすべて 0° に戻す\n"
                               "   （R → 軸 → 角度、または N キーのサイドバーで数値を直接入力）\n"
                               "③ スケールをすべて 1 に戻す\n"
                               "   （S → 数字、または N キーのサイドバーで数値を直接入力）",
                },
            }
            return stages.get(stage_num, {})
        if chapter_num == 2:
            stages = {
                1: {
                    "title": "第2章: ビュー操作",
                    "name": "ステージ1: パン（視点を平行移動）",
                    "description": "Shift + 中ボタンで視点を動かしてください",
                    "details": "① まず Shift キーを押す\n"
                               "② Shift を押したまま中ボタンを押す\n"
                               "③ そのままドラッグすると\n"
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
                    "details": "① まず Shift を押しながら中ボタンでパン（平行移動）\n"
                               "② 次にホイールスクロールでズーム（拡大縮小）\n"
                               "③ 順番に両方やるとクリア\n"
                               "   （同時にやろうとしなくて大丈夫！）",
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
                               "③ 押すと自動でクリアになります（反応しないときは「確認」ボタン）"},
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
                               "② Shift+クリックで頂点を複数選択\n"
                               "   （3個以上選ぼう）\n"
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
                    "details": "ループカットとは？\n"
                               "  メッシュをぐるっと一周切って\n"
                               "  新しいエッジ（辺）のループを追加する機能\n"
                               "  形を細かく整えるときに使う\n"
                               "\n"
                               "① Ctrl+R を押す\n"
                               "② マウスをメッシュに近づけると\n"
                               "   黄色い線が出る\n"
                               "③ 1回クリックで位置を確定\n"
                               "④ もう1回クリックで確定（または Enter）"},
                10: {"title": "第3章: モデリング基礎", "name": "ステージ10: 組み合わせ（復習）",
                     "description": "立方体を追加し、ループカットを1本入れて、サイズを2倍にしてください",
                     "details": "① Shift+A → メッシュ → 立方体\n"
                                "② Tab でエディットモードへ\n"
                                "③ Ctrl+R でループカットを1本入れる\n"
                                "④ Tab でオブジェクトモードに戻る\n"
                                "⑤ S → 2 → Enter でサイズを2倍にする"},
            }
            return stages.get(stage_num, {})
        if chapter_num == 5:
            stages = {
                1: {
                    "title": "第5章: スカルプティング体験",
                    "name": "ステージ1: スカルプトモードに入る",
                    "description": "Sculpt Mode（スカルプトモード）に切り替えてください",
                    "details": "① セットアップで球（Sphere）が出現します\n"
                               "② 球を左クリックで選択\n"
                               "③ 画面左上のモード切替ボタン（「オブジェクトモード」と表示）\n"
                               "   をクリック\n"
                               "④ 「スカルプトモード」を選択\n"
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
                    "details": "① ステージ1でマテリアルを作成済みか確認\n"
                               "② シェーダーエディター内で\n"
                               "   Shift+A を押す\n"
                               "③ 「テクスチャ」→「画像テクスチャ」を選択\n"
                               "   ノードが追加される\n"
                               "④ ノードの画像欄（画像アイコンの▼）を開く\n"
                               "⑤ 一覧から「fruit_apple」を選ぶ\n"
                               "   （「開く」ボタンは使いません）",
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

            if st == 5:
                if not obj or obj.name != "Cube":
                    return False, "❌ キューブを選択してください", "NO_ACTIVE_CUBE", [
                        "3Dビューのキューブをクリックして選択してください",
                        "回転とスケールの数値を元に戻します",
                        "N キーで出るサイドバーの「アイテム」に数値があります",
                    ]
                rot_ok = all(abs(((math.degrees(a) + 180.0) % 360.0) - 180.0) < 2.0 for a in obj.rotation_euler)
                scale_ok = all(abs(v - 1.0) < 0.05 for v in obj.scale)
                if rot_ok and scale_ok:
                    return True, "✓ 元の状態に戻せました", "OK", []
                msg = []
                if not scale_ok:
                    msg.append(f"スケール {obj.scale.x:.2f}/{obj.scale.y:.2f}/{obj.scale.z:.2f}")
                if not rot_ok:
                    msg.append("回転が0°ではありません")
                return False, "❌ まだ元の状態ではありません（" + "、".join(msg) + "）", "NOT_RESTORED", [
                    "S を押して数字を入力すると、その倍率になります（2なら2倍）。3倍に大きくなったものを小さくするには何倍にすればよいでしょう？",
                    "角度は R → 軸 → 数字 以外の方法もあります。N キーで出るサイドバーの「アイテム」に、数値が出ています。そこを直接書き換えてみよう",
                    "回転は X・Y・Z すべてを 0° に、スケールは X・Y・Z すべてを 1 にします",
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

            # --- 新St2: Ctrl+Z を実際に押したか（シーン外の記録で判定）---
            if st == 2:
                entered = StageManager._st_enter_t
                if entered > 0.0 and any(t > entered for t in _UNDO_TIMES):
                    return True, "✓ Ctrl+Z で元に戻せました", "OK", []
                return False, "❌ まだ Ctrl+Z が押されていません", "UNDO_NOT_USED", [
                    "① G → X → 3 → Enter でキューブを動かしてください",
                    "② Ctrl+Z を押すと、直前の操作が取り消されて元の位置に戻ります",
                    "（マウスを3Dビューの上に置いて押してください）",
                ]

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

            # --- St10: 組み合わせ（復習）追加→ループカット→2倍（編集モードに依存しないので先に判定）---
            if st == 10:
                meshes = [o for o in bpy.data.objects if o.type == 'MESH']
                if not meshes:
                    return False, "❌ まず立方体を追加してください", "NO_OBJECT_ADDED", [
                        "Shift+A → メッシュ → 立方体 で追加します",
                        "追加したら Tab でエディットモードに入り、Ctrl+R でループカットを1本入れます",
                        "最後に Tab でオブジェクトモードに戻り、S → 2 → Enter で2倍にします",
                    ]
                if len(meshes) > 1:
                    return False, "❌ 立方体は1つだけにしてください", "TOO_MANY_OBJECTS", [
                        "余分なオブジェクトは X キーで削除してください",
                        "立方体を1つだけ追加して進めます",
                        "やり直すときは「リセット」ボタンが使えます",
                    ]
                target = meshes[0]
                if target.mode == 'EDIT':
                    coords = [tuple(v.co) for v in bmesh.from_edit_mesh(target.data).verts]
                else:
                    coords = [tuple(v.co) for v in target.data.vertices]
                distinct = len({(round(x, 3), round(y, 3), round(z, 3)) for x, y, z in coords})
                xs = [c[0] for c in coords]
                ys = [c[1] for c in coords]
                zs = [c[2] for c in coords]
                sx, sy, sz = (abs(v) for v in target.scale)
                dims = ((max(xs) - min(xs)) * sx, (max(ys) - min(ys)) * sy, (max(zs) - min(zs)) * sz)
                if not (12 <= distinct <= 20):
                    return False, "❌ ループカットが入っていません", "LOOPCUT_NOT_DETECTED", [
                        "Tab でエディットモードに入ってください",
                        "Ctrl+R を押して、黄色い線が出たらクリックで確定します",
                        "（もう1回クリックまたは Enter で最終確定）",
                    ]
                if not all(abs(d - 4.0) <= 0.4 for d in dims):
                    return False, "❌ サイズが2倍になっていません", "NOT_SCALED", [
                        "追加した立方体の1辺は2です。2倍にすると4になります",
                        "オブジェクトモードで S → 2 → Enter を押してください",
                        "（エディットモードのまま S → 2 でも同じ結果になります）",
                    ]
                return True, "✓ 追加・ループカット・拡大ができました", "OK", []

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
                    return True, "✓ ソリッド化を追加しました", "OK", []
                return False, "❌ ソリッド化（Solidify）を追加してください", "NO_MODIFIER", [
                    "トーラス（ドーナツ型）にモディファイアーを追加します",
                    "レンチアイコン→「生成」→「ソリッド化」を選んでください",
                    "追加後に「幅」の値を変えると厚さが変わります",
                ]
            if st == 5:
                bev = [m for m in obj.modifiers if m.type == 'BEVEL']
                if bev and bev[0].segments >= 3 and bev[0].width >= 0.02:
                    return True, "✓ ベベルがなめらかな丸みになりました", "OK", []
                if bev:
                    return False, f"❌ セグメントが {bev[0].segments} です（3以上にしてください）", "BEVEL_NOT_SMOOTH", [
                        "右のプロパティパネルのレンチアイコンを開いてください",
                        "ベベルの「セグメント」の数字を増やしてください",
                        "3以上にすると、角がなめらかな丸みになります",
                    ]
                return False, "❌ ベベルが見つかりません", "NO_MODIFIER", [
                    "リセットボタンで最初の状態に戻せます",
                    "または「モディファイアーを追加」→「生成」→「ベベル」で追加します",
                    "そのあと「セグメント」を3以上にしてください",
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
                    "追加されたノードの画像欄（画像アイコンの▼）をクリックしてください",
                    "一覧から「fruit_apple」を選んでください（「開く」ボタンは使いません）",
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

        # ---- Chapter 8: テストフェーズ（ヒント完全ゼロ） ----
        if ch == 8:
            # Ch8は難易度設定に関わらずヒントなし
            if st == 1:
                # Ch1応用: キューブをY方向に+3移動
                if not obj or obj.name != "Cube":
                    return False, "❌ キューブを選択してください", "NO_ACTIVE_CUBE", []
                if abs(obj.location.y - 3.0) < 0.15:
                    return True, "✓ Y方向に+3移動できました", "OK", []
                return False, f"❌ Y移動量: {obj.location.y:.2f}（目標: +3.0）", "TRANSFORM_NOT_MATCHED", []

            if st == 2:
                # Ch2応用: ビュー回転＋ズーム
                space = StageManager.get_view3d_space(context)
                if not space or not space.region_3d:
                    return False, "❌ 3Dビューなし", "NO_VIEW3D", []
                r3d = space.region_3d
                rot_diff = StageManager.vec_dist(tuple(r3d.view_rotation), tuple(props.initial_view_rotation))
                dist_diff = abs(r3d.view_distance - props.initial_view_distance)
                if rot_diff > 0.01 and dist_diff > 0.5:
                    return True, "✓ ビュー回転＋ズーム完了", "OK", []
                if rot_diff <= 0.01:
                    return False, "❌ ビューを回転させてください", "VIEW_NOT_ROTATED", []
                return False, "❌ ズームもしてください", "VIEW_NOT_ZOOMED", []

            if st == 3:
                # Ch3応用: 立方体追加→Editモード→ループカット（辺数>12）
                if bpy.context.mode != 'EDIT_MESH':
                    return False, "❌ エディットモードに入ってください", "NOT_IN_EDIT", []
                active = bpy.context.active_object
                if not active or active.type != 'MESH':
                    return False, "❌ メッシュオブジェクトを選択してください", "NO_MESH", []
                bm = bmesh.from_edit_mesh(active.data)
                if len(bm.edges) > 12:
                    return True, "✓ ループカット追加完了", "OK", []
                return False, "❌ ループカットを追加してください（Ctrl+R）", "NO_LOOP_CUT", []

            if st == 4:
                # Ch4応用: Bevelモディファイア追加
                if not obj:
                    return False, "❌ オブジェクトを選択してください", "NO_ACTIVE_OBJECT", []
                has_bevel = any(m.type == 'BEVEL' for m in obj.modifiers)
                if has_bevel:
                    return True, "✓ Bevelモディファイア追加完了", "OK", []
                return False, "❌ Bevelモディファイアを追加してください", "NO_MODIFIER", []

            if st == 5:
                # Ch5応用: Grabブラシで球を変形
                sphere = StageManager.find_sphere()
                if not sphere:
                    return False, "❌ 球（Sphere）が見つかりません", "NO_SPHERE", []
                if bpy.context.mode != 'SCULPT':
                    return False, "❌ スカルプトモードに入ってください", "NOT_SCULPT", []
                moved, total = StageManager.get_vertex_deformation_amount(sphere, props.initial_vertex_positions)
                if moved > 5 and total > 0.05:
                    return True, "✓ 球を変形できました", "OK", []
                return False, "❌ Grabブラシで球を変形させてください", "NO_DEFORM", []

            if st == 6:
                # Ch6応用: マテリアル作成＋Roughnessを0.2以下に
                if not obj:
                    return False, "❌ オブジェクトを選択してください", "NO_ACTIVE_OBJECT", []
                mat = StageManager.get_active_material(obj)
                bsdf = StageManager.get_principled_bsdf(mat) if mat else None
                if not bsdf:
                    return False, "❌ マテリアルを作成してください", "NO_MATERIAL", []
                roughness = bsdf.inputs['Roughness'].default_value
                if roughness <= 0.2:
                    return True, "✓ マテリアル作成＋粗さ設定完了", "OK", []
                return False, f"❌ 粗さ（Roughness）を0.2以下にしてください（現在: {roughness:.2f}）", "ROUGHNESS_NOT_LOW", []

        return False, "❌ 判定エラー", "UNKNOWN", ["セットアップして再試行"]

    @staticmethod
    def check_stage(context):
        try:
            props = context.scene.tutorial_props
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

# 直前の難易度（シーンのプロパティはUndoで巻き戻るため、シーンの外に持つ）
_LAST_DIFFICULTY = {"value": None}


def _on_difficulty_changed(self, context):
    """難易度が変わったら、いつ・どのステージで・何から何に変えたかをログに残す。"""
    try:
        new = self.difficulty_mode
        old = _LAST_DIFFICULTY["value"]
        _LAST_DIFFICULTY["value"] = new
        if old is None or old == new:
            return
        StageManager.append_participant_event(bpy.context, {
            "t": StageManager._now(),
            "participant_id": StageManager._safe_participant_id(self.participant_id),
            "event": "difficulty_changed",
            "chapter": self.current_chapter,
            "stage": self.current_stage,
            "from": old,
            "to": new,
        })
    except Exception:
        pass


class TUTORIAL_PG_Properties(PropertyGroup):
    current_chapter: IntProperty(default=1, min=1, max=8)
    current_stage: IntProperty(default=1, min=1, max=10)
    stage_complete: BoolProperty(default=False)
    monitoring_active: BoolProperty(default=False)
    test_mode_active: BoolProperty(default=False)      # 確認テスト中フラグ（Ch1〜7への移動をロック）
    intro_popup_shown: BoolProperty(default=False)     # 初回説明ポップアップ表示済みフラグ

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

    # 難易度設定（参加者が自分に合うものを選ぶ。ログに記録される）
    difficulty_mode: EnumProperty(
        name="難易度",
        description="手順とヒントの表示量を変えます",
        items=[
            ('EASY',   "かんたん",   "手順をすべて表示。ヒントも最初から全部表示"),
            ('NORMAL', "ふつう",     "ショートカットだけ表示。手順は「手順を見る」ボタンで開く。失敗するたびヒントを1つずつ表示（デフォルト）"),
            ('HARD',   "むずかしい", "機能の説明だけ表示（ショートカットも手順もなし）。ヒントも出さない"),
        ],
        default='NORMAL',
        update=_on_difficulty_changed,
    )
    # 「手順を見る」を開いたステージ（"章-ステージ"）。開いていなければ空
    steps_open_key: StringProperty(default="")

    # Logging
    enable_participant_logging: BoolProperty(default=True)
    participant_id: StringProperty(name="参加者ID", default="")
    log_dir: StringProperty(
        name="ログ保存フォルダ",
        description="空欄ならデスクトップの「学籍番号_addon」フォルダに自動で保存します。"
                    "（フォルダ選択ボタンはBlenderが落ちることがあるため使いません）",
        default="",
    )
    participant_log_path: StringProperty(default="")
    participant_log_error: StringProperty(default="")

    # Chapter 6 / 7
    final_render_saved_path: StringProperty(default="")

    # Chapter 7: 折りたたみ工程メモの開閉状態
    ch7_show_step1: BoolProperty(name="STEP1: スカルプトで形を整える", default=False)
    ch7_show_step2: BoolProperty(name="STEP2: 茎を追加する",           default=False)
    ch7_show_step3: BoolProperty(name="STEP3: マテリアルで色をつける", default=False)
    ch7_show_step4: BoolProperty(name="STEP4: レンダーして保存",       default=False)


# =====================================================
# OPERATORS
# =====================================================

class TUTORIAL_OT_set_default_log_dir(Operator):
    bl_idname = "tutorial.set_default_log_dir"
    bl_label = "フォルダを自動作成"
    bl_description = "デスクトップに「学籍番号_addon」フォルダ（例：23DB999_addon）を作り、ログ保存先に設定します"

    def execute(self, context):
        props = context.scene.tutorial_props
        target = StageManager.auto_log_dir(props)
        if not target:
            self.report({'ERROR'}, "先に参加者IDを入力してください")
            return {'CANCELLED'}
        props.log_dir = target
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
            StageManager.open_folder_in_os(StageManager.resolve_log_dir(props))
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
            if ev_type not in ("validate", "finalize", "steps_opened", "difficulty_changed"):
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
                    "difficulty_mode": None, "steps_opened": 0, "difficulty_changes": 0,
                }
            if ev_type == "difficulty_changed":
                by_stage[key]["difficulty_changes"] += 1
            if ev_type == "steps_opened":
                by_stage[key]["steps_opened"] += 1
                if ev.get("difficulty_mode") is not None and by_stage[key]["difficulty_mode"] is None:
                    by_stage[key]["difficulty_mode"] = str(ev["difficulty_mode"])
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
                    "steps_opened", "difficulty_changes",
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
                        r["steps_opened"], r["difficulty_changes"],
                    ])
        except Exception as e:
            self.report({'ERROR'}, f"CSV出力に失敗: {e}")
            return {'CANCELLED'}

        self.report({'INFO'}, f"CSV出力完了: {out_csv}")
        return {'FINISHED'}

class TUTORIAL_OT_toggle_steps(Operator):
    bl_idname = "tutorial.toggle_steps"
    bl_label = "手順を見る"
    bl_description = "このステージの手順を開く／閉じる（開いた回数がログに記録されます）"

    def execute(self, context):
        props = context.scene.tutorial_props
        key = f"{props.current_chapter}-{props.current_stage}"
        if props.steps_open_key == key:
            props.steps_open_key = ""
            return {'FINISHED'}
        props.steps_open_key = key
        StageManager.append_participant_event(context, {
            "t": StageManager._now(),
            "participant_id": StageManager._safe_participant_id(props.participant_id),
            "event": "steps_opened",
            "chapter": props.current_chapter,
            "stage": props.current_stage,
            "difficulty_mode": props.difficulty_mode,
        })
        return {'FINISHED'}


class TUTORIAL_OT_render_and_mark_saved(Operator):
    bl_idname = "tutorial.render_and_mark_saved"
    bl_label = "補助: レンダーして保存（自動）"
    bl_description = "最終制作: レンダー画像を自動で保存し、クリア判定できるようにします"

    def execute(self, context):
        props = context.scene.tutorial_props
        try:
            base_dir = StageManager.ensure_dir_exists(StageManager.resolve_log_dir(props))
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

    def invoke(self, context, event):
        props = context.scene.tutorial_props
        # 初回のみボタンの使い方ポップアップを表示する
        if not props.intro_popup_shown:
            return context.window_manager.invoke_props_dialog(self, width=380)
        return self.execute(context)

    def draw(self, context):
        """初回ポップアップ用の描画（invoke_props_dialog のときだけ呼ばれる）"""
        layout = self.layout
        layout.label(text="ようこそ！ 3DCGチュートリアルへ", icon='INFO')
        layout.separator()
        layout.label(text="ボタンの使い方：")
        layout.separator()
        col = layout.column(align=True)
        col.label(text="【セットアップ】 問題を準備します（最初に押す）")
        col.label(text="【監視開始】　　自動で正誤を判定します")
        col.label(text="【確認】　　　　答え合わせをします")
        col.label(text="【次へ】　　　　クリアしたら次のステージへ")
        col.label(text="【← →】　　　ステージを自由に移動できます")
        layout.separator()
        layout.label(text="OKを押すと最初のステージが始まります！")

    def execute(self, context):
        props = context.scene.tutorial_props
        props.intro_popup_shown = True   # 表示済みフラグをセット
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
        props.stage_start_time = StageManager._rel()
        StageManager._st_enter_t = StageManager._rel()
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
        _LAST_DIFFICULTY["value"] = props.difficulty_mode

        try:
            StageManager.ensure_dir_exists(StageManager.resolve_log_dir(props))
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
            props.first_attempt_time = StageManager._rel()

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
            # Ch5はスカルプト形状、Ch6はマテリアルノード、Ch8はテスト中のため、Ch3 St2はundo_countが消えるためリセットしない
            if props.current_chapter in (5, 6, 8):
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

    def invoke(self, context, event):
        props = context.scene.tutorial_props
        max_stages_per_chapter = MAX_STAGES
        max_stages = max_stages_per_chapter.get(props.current_chapter, 1)
        # Ch7 最終ステージ → Ch8 への移行はカスタムダイアログ
        going_to_ch8 = (
            props.current_chapter == 7 and
            props.current_stage >= max_stages
        )
        if going_to_ch8:
            return context.window_manager.invoke_props_dialog(self, width=360)
        return self.execute(context)

    def draw(self, context):
        layout = self.layout
        layout.label(text="⚠  確認テストに進みますか？", icon='ERROR')
        layout.separator()
        layout.label(text="・確認テストに進むと元のチャプターには戻れません")
        layout.label(text="・今までに学んだ機能をテストします")
        layout.separator()
        layout.label(text="OKを押すとテスト開始です")

    def execute(self, context):
        props = context.scene.tutorial_props
        StageManager.finalize_current_run(context, completed=True)

        max_stages_per_chapter = MAX_STAGES
        max_stages = max_stages_per_chapter.get(props.current_chapter, 1)

        if props.current_stage < max_stages:
            props.current_stage += 1
        else:
            if props.current_chapter < 8:
                props.current_chapter += 1
                props.current_stage = 1
                # Ch8 移行時にテストモードをON
                if props.current_chapter == 8:
                    props.test_mode_active = True
            else:
                StageManager.turn_off_scene_camera_and_lights()
                self.report({'INFO'}, "全チャプター完了！おつかれさまでした")
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
            props.stage_start_time = StageManager._rel()
            StageManager._st_enter_t = StageManager._rel()
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
        props.test_mode_active = False

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

class TUTORIAL_OT_enter_test_mode(Operator):
    bl_idname = "tutorial.enter_test_mode"
    bl_label = "確認テストへ進む"
    bl_description = "第8章・確認テストに入ります。入ったらCh1〜7には戻れません"

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=360)

    def draw(self, context):
        layout = self.layout
        layout.label(text="⚠  確認テストに進みますか？", icon='ERROR')
        layout.separator()
        layout.label(text="・確認テストに進むと元のチャプターには戻れません")
        layout.label(text="・今までに学んだ機能をテストします")
        layout.separator()
        layout.label(text="OKを押すとテスト開始です")

    def execute(self, context):
        props = context.scene.tutorial_props
        StageManager.finalize_current_run(context, completed=False)

        props.test_mode_active = True
        props.current_chapter = 8
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

        self.report({'INFO'}, "確認テスト開始！Ch1〜7へは戻れません")
        return {'FINISHED'}

class TUTORIAL_OT_stage_prev(Operator):
    bl_idname = "tutorial.stage_prev"
    bl_label = "← 前のステージ"
    bl_description = "前のステージに移動してセットアップします"

    def execute(self, context):
        props = context.scene.tutorial_props
        max_stages_per_chapter = MAX_STAGES

        from_ch, from_st = props.current_chapter, props.current_stage
        StageManager.finalize_current_run(context, completed=False)

        # テスト中はCh8より前には戻れない
        if props.test_mode_active:
            if props.current_stage > 1:
                props.current_stage -= 1
            else:
                self.report({'WARNING'}, "テスト中はCh1〜7に戻れません")
                return {'FINISHED'}
        elif props.current_stage > 1:
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
            props.stage_start_time = StageManager._rel()
            StageManager._st_enter_t = StageManager._rel()
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
        max_stages_per_chapter = MAX_STAGES
        max_stages = max_stages_per_chapter.get(props.current_chapter, 1)

        from_ch, from_st = props.current_chapter, props.current_stage
        StageManager.finalize_current_run(context, completed=False)

        if props.current_stage < max_stages:
            props.current_stage += 1
        elif props.test_mode_active:
            # テスト中はCh8の最終ステージより先に進めない
            self.report({'INFO'}, "テストの最後のステージです")
            return {'FINISHED'}
        elif props.current_chapter < 8:
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
            props.stage_start_time = StageManager._rel()
            StageManager._st_enter_t = StageManager._rel()
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
    _running = False  # 二重起動防止フラグ

    def modal(self, context, event):
        if event.type == 'TIMER':
            try:
                props = context.scene.tutorial_props
                if not props.monitoring_active:
                    wm = context.window_manager
                    if self._timer:
                        wm.event_timer_remove(self._timer)
                    TUTORIAL_OT_monitoring._running = False
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
        if TUTORIAL_OT_monitoring._running:
            return {'CANCELLED'}  # すでに起動中なら何もしない
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.1, window=context.window)
        self._last_check = time.time()
        TUTORIAL_OT_monitoring._running = True
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
        if not (props.log_dir or "").strip():
            pbox.label(text="空欄＝デスクトップの「学籍番号_addon」に自動保存")

        row = pbox.row(align=True)
        row.operator("tutorial.set_default_log_dir", text="フォルダを自動作成")
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
        chapter_names = {
            1: "基本操作",
            2: "ビュー",
            3: "モデリング",
            4: "モディファイア",
            5: "スカルプト",
            6: "マテリアル",
            7: "最終制作",
            8: "確認テスト",
        }
        # Ch1〜7 ボタン（テスト中はロック）
        row = cbox.row(align=True)
        row.enabled = not props.test_mode_active
        for i in range(1, 8):
            op = row.operator("tutorial.goto_chapter", text=chapter_names[i], depress=(props.current_chapter == i))
            op.chapter = i

        # Ch8 確認テストボタン（いつでも押せる・ポップアップ付き）
        test_row = cbox.row()
        test_row.operator(
            "tutorial.enter_test_mode",
            text="▶ 確認テスト（Ch8）" if not props.test_mode_active else "● テスト中",
            depress=props.test_mode_active,
        )
        if props.test_mode_active:
            cbox.label(text="⚠ テスト中はCh1〜7に戻れません", icon='LOCKED')

        info = StageManager.get_stage_info(props.current_chapter, props.current_stage)
        sbox = layout.box()
        sbox.label(text=info.get("title", ""))
        max_stages_per_chapter = MAX_STAGES
        sbox.label(text=f"ステージ {props.current_stage}/{max_stages_per_chapter.get(props.current_chapter, 1)}")
        sbox.label(text=info.get("name", ""))
        sbox.separator()
        sbox.label(text=info.get("description", ""))

        ch_now, st_now = props.current_chapter, props.current_stage
        guided = ch_now in (1, 2, 3, 4, 5, 6)
        mode = props.difficulty_mode
        if guided and mode != 'EASY':
            # ふつう／むずかしい：手順の全文は出さず、機能の説明を表示
            about = STAGE_ABOUT.get((ch_now, st_now), "")
            if about:
                sbox.separator()
                for line in about.split("\n"):
                    sbox.label(text=line)
            if mode == 'NORMAL':
                opened = (props.steps_open_key == f"{ch_now}-{st_now}")
                sbox.separator()
                sbox.operator("tutorial.toggle_steps",
                              text="手順をとじる" if opened else "手順を見る（ヒント）",
                              icon='TRIA_UP' if opened else 'TRIA_DOWN')
                if opened and info.get("details"):
                    for line in info["details"].split("\n"):
                        sbox.label(text=line)
        elif info.get("details"):
            sbox.separator()
            for line in info["details"].split("\n"):
                sbox.label(text=line)

        if props.current_chapter == 7:
            sbox.separator()
            sbox.label(text="━━ 作り方メモ（クリックで開閉）━━")

            # --- STEP 1: スカルプト ---
            b1 = sbox.box()
            r1 = b1.row()
            r1.prop(props, "ch7_show_step1",
                    icon='TRIA_DOWN' if props.ch7_show_step1 else 'TRIA_RIGHT',
                    icon_only=True, emboss=False)
            r1.label(text="STEP1: スカルプトで形を整える")
            if props.ch7_show_step1:
                for line in (
                    "① スカルプトモードに切り替える",
                    "   （左上のモード切替 or Ctrl+Tab）",
                    "② Grab ブラシで球全体を",
                    "   縦長の楕円形に整える",
                    "③ Ctrl+ドラッグで天面を押し込み",
                    "   凹みを作る（ヘタ部分）",
                    "④ Clay ブラシで表面を細かく整える",
                ):
                    b1.label(text=line)

            # --- STEP 2: 茎 ---
            b2 = sbox.box()
            r2 = b2.row()
            r2.prop(props, "ch7_show_step2",
                    icon='TRIA_DOWN' if props.ch7_show_step2 else 'TRIA_RIGHT',
                    icon_only=True, emboss=False)
            r2.label(text="STEP2: 茎を追加する")
            if props.ch7_show_step2:
                for line in (
                    "① Tab でオブジェクトモードに戻る",
                    "② Shift+A → メッシュ → 円柱",
                    "③ S → 0.1 → Enter で細くする",
                    "④ G → Z で上に移動し",
                    "   リンゴ天面の凹みに配置する",
                ):
                    b2.label(text=line)

            # --- STEP 3: マテリアル ---
            b3 = sbox.box()
            r3 = b3.row()
            r3.prop(props, "ch7_show_step3",
                    icon='TRIA_DOWN' if props.ch7_show_step3 else 'TRIA_RIGHT',
                    icon_only=True, emboss=False)
            r3.label(text="STEP3: マテリアルで色をつける")
            if props.ch7_show_step3:
                for line in (
                    "① オブジェクトモードでリンゴを選択",
                    "② プロパティ → 球アイコン →「新規」",
                    "③ ベースカラーを赤に設定",
                    "④ Roughness を下げると光沢感UP",
                    "   （0.2 くらいがおすすめ）",
                ):
                    b3.label(text=line)

            # --- STEP 4: レンダー ---
            b4 = sbox.box()
            r4 = b4.row()
            r4.prop(props, "ch7_show_step4",
                    icon='TRIA_DOWN' if props.ch7_show_step4 else 'TRIA_RIGHT',
                    icon_only=True, emboss=False)
            r4.label(text="STEP4: レンダーして保存")
            if props.ch7_show_step4:
                for line in (
                    "① F12 でレンダリング開始",
                    "② 画像エディターで",
                    "   「画像 → 名前をつけて保存」",
                    "③ または下の補助ボタンで自動保存",
                ):
                    b4.label(text=line)

            sbox.separator()
            sbox.operator("tutorial.render_and_mark_saved", text="補助: レンダーして保存（自動）")
            if props.final_render_saved_path:
                sbox.label(text=f"✓ 保存済: {os.path.basename(props.final_render_saved_path)}")


        current_new, _ = StageManager.get_accumulated_shortcuts(
            props.current_chapter, props.current_stage
        )
        # むずかしい：ショートカットは出さない（モディファイアーはメニューの道筋なので出す）
        show_keys = (props.difficulty_mode != 'HARD') or (props.current_chapter == 4)
        if current_new and show_keys:
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

        # クリア時は目立つ表示に切り替え
        if props.stage_complete:
            clear_box = layout.box()
            clear_box.label(text="🎉 ステージクリア！", icon='CHECKMARK')
            clear_row = clear_box.row()
            clear_row.scale_y = 1.5
            clear_row.operator("tutorial.next_stage", text="次へ進もう →", icon='TRIA_RIGHT')

        layout.operator("tutorial.reset", text="リセット")

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

    @classmethod
    def poll(cls, context):
        # むずかしい：累積のショートカット一覧も出さない
        return context.scene.tutorial_props.difficulty_mode != 'HARD'

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
        _UNDO_TIMES.append(StageManager._rel())
        del _UNDO_TIMES[:-200]
    except Exception:
        pass
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
    TUTORIAL_OT_toggle_steps,
    TUTORIAL_OT_finish_and_turn_off,
    TUTORIAL_OT_setup_stage,
    TUTORIAL_OT_validate_stage,
    TUTORIAL_OT_next_stage,
    TUTORIAL_OT_reset,
    TUTORIAL_OT_goto_chapter,
    TUTORIAL_OT_enter_test_mode,
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