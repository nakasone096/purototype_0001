# -*- coding: utf-8 -*-
"""フリー章の「お手本」用の小さな .blend を作る（開発用ツール。アドオン本体からは使いません）。

元の .blend から、メッシュだけを取り出して、次のように整理して書き出します。
  - カメラ・ライト・背景の床板などは入れない（--exclude で、入れたくないメッシュを指定）
  - モディファイアーを適用した形（見た目のとおりの普通のメッシュ）にする
  - 全体の中心を原点に、一番下を Z=0 にそろえる
  - マテリアルは「お手本_色1…」に改名し、ソリッド表示でも色が見えるよう表示色にも設定する
  - コレクション名は「お手本_〜」（アドオンは、この名前の前半で、お手本を見分けて消します）

使い方（Blender 4.2 で）:
  blender --background --factory-startup 元.blend --python make_free_models.py -- \
      出力.blend コレクション名 [--exclude メッシュ名 ...] [--rename 元の名前=新しい名前 ...]
例:
  blender -b --factory-startup 3つ目.blend --python make_free_models.py -- free_model_house.blend お手本_ミニチュアハウス       --exclude 平面 --rename Cube=壁 Cube.001=屋根
パーツの名前は、アウトライナーに出るので、「何のパーツか」が分かる名前にします（お手本_壁、お手本_屋根 など）。
どのオブジェクトにも、お手本の印（カスタムプロパティ tutorial_free_model）を付けます。
"""
import sys
import bpy
from mathutils import Matrix

PREFIX = "お手本_"


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    out_path, coll_name = argv[0], argv[1]
    exclude, rename, mode = set(), {}, None
    for tok in argv[2:]:
        if tok in ("--exclude", "--rename"):
            mode = tok
        elif mode == "--exclude":
            exclude.add(tok)
        elif mode == "--rename":
            old, new = tok.split("=", 1)
            rename[old] = new
    if not coll_name.startswith(PREFIX):
        raise SystemExit(f"コレクション名は「{PREFIX}」で始めてください: {coll_name}")

    dg = bpy.context.evaluated_depsgraph_get()
    sources = [o for o in bpy.data.objects if o.type == 'MESH' and o.name not in exclude]
    if not sources:
        raise SystemExit("取り出せるメッシュがありません")

    coll = bpy.data.collections.new(coll_name)
    made = []
    for o in sources:
        ev = o.evaluated_get(dg)
        me = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=True, depsgraph=dg)
        me.transform(o.matrix_world)
        if o.matrix_world.determinant() < 0:      # マイナスのスケールで裏返っていた面を、直す
            me.flip_normals()
        name = PREFIX + rename.get(o.name, o.name)
        me.name = name
        ob = bpy.data.objects.new(name, me)
        ob["tutorial_free_model"] = True            # お手本の印（名前が変わっても見分けられる）
        coll.objects.link(ob)
        made.append(ob)

    # 中心を原点、一番下をZ=0に
    pts = [v.co.copy() for ob in made for v in ob.data.vertices]
    lo = [min(p[i] for p in pts) for i in range(3)]
    hi = [max(p[i] for p in pts) for i in range(3)]
    shift = Matrix.Translation(((-(lo[0] + hi[0]) / 2), (-(lo[1] + hi[1]) / 2), -lo[2]))
    for ob in made:
        ob.data.transform(shift)
        ob.data.update()

    # マテリアルの整理（改名＋ソリッド表示用の色）
    mats = []
    for ob in made:
        for m in ob.data.materials:
            if m and m not in mats:
                mats.append(m)
    for i, m in enumerate(mats, 1):
        m.name = f"{PREFIX}色{i}"
        if m.use_nodes and m.node_tree:
            b = [n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED']
            if b:
                m.diffuse_color = b[0].inputs['Base Color'].default_value

    for ob in made:
        ob.hide_select = True

    bpy.data.libraries.write(out_path, {coll}, compress=True)
    size = [round(hi[i] - lo[i], 2) for i in range(3)]
    print(f"[make_free_models] {coll_name}: objects={len(made)} verts={len(pts)} materials={len(mats)} size(x,y,z)={size} -> {out_path}")


main()
