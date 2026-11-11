"""Expose owned Awakening item resources and level progression to Origins."""
import re
import struct
from pathlib import Path
from build import resource, index
from gff import u32, word


def table_rows(blob):
    base = u32(blob, 24)
    start = base + u32(blob, base + 4)
    stride = u32(blob, 72)
    return base, start, stride


def xp_property(blob):
    # Only row 19 sets the experience property maximum. Retain the string
    # pool at its original relative offsets while exposing just that row.
    base, start, stride = table_rows(blob)
    row = next(i for i in range(u32(blob,start)) if u32(blob,start+4+stride*i)==19)
    data = bytearray(blob)
    data[start:start+4] = word(1)
    data[start+4:start+4+stride] = blob[start+4+stride*row:start+4+stride*(row+1)]
    assert struct.unpack_from("<f",data,start+4+16)[0] == 353501
    return data


def merge_talktables(paths):
    # Origins TLK V0.2 stores a sparse array of string IDs and UTF-16
    # references. Original localized lines retain precedence on collisions.
    lines = {}
    for path in paths:
        blob = path.read_bytes()
        if blob[:20] != b"GFF V4.0PC  TLK V0.2":
            raise ValueError(f"Unknown talktable format: {path}")
        base = u32(blob,24)
        array = base + u32(blob,base)
        for i in range(u32(blob,array)):
            ident, ref = struct.unpack_from("<II",blob,array+4+i*8)
            if 0xffffffff in (ident,ref) or ident in lines:
                continue
            pos = base+ref
            lines[ident] = blob[pos:pos+4+2*u32(blob,pos)]
    buf = bytearray(word(4)+word(len(lines))+bytes(len(lines)*8))
    for i,(ident,string) in enumerate(sorted(lines.items())):
        struct.pack_into("<II",buf,8+i*8,ident,len(buf))
        buf.extend(string)
    return blob[:base]+buf


def export(game, out):
    core = game/"packages/core/data"
    ep = game/"packages/core_ep1/data"
    sp = game/"modules/single player/data"
    module = game/"Addins/dao_prc_ep_1/module/data"
    dest = out/"AwakeningEquipment"
    dest.mkdir(exist_ok=True)
    assets = {}
    def take(path, accept):
        for n, entry in index(path).items():
            if accept(n):
                assets[n] = path,entry
    for root in (ep,module):
        archive = root/"designeritems.erf"
        take(archive,lambda n:n.endswith(".uti"))
        for p in sorted((root.parent/"patch").glob("*.erf")):
            take(p,lambda n:n.endswith(".uti"))
    def gear_model(n):
        return n.startswith(("w_","s_")) or bool(re.match(r"(?:[hedq][mf]|pm|pf)_(?:arm|boo|glv|hl|rob|clo)",n))
    def gear_material(n):
        return n.startswith(("w_","s_","arm_","boo_","glv_","hl","rob_","clo_","shd_"))
    selected_tables = {"exptable_gxa","item_sets_gxa","bitm_gxa","itemstats_gxa","itemprps_gxa",
                       "materialrules_gxa","materialtypes_gxa","crafting_recipes_gxa","crafting_recipe_types_gxa"}
    take(ep/"2da.erf",lambda n:n[:-4] in selected_tables or "_variation_g" in n)
    for name in ("modelhierarchies","modelmeshdata"):
        take(ep/(name+".erf"),gear_model)
    take(ep/"materialobjects.erf",gear_material)
    take(ep/"guiexport.erf",lambda n:True)
    take(ep/"tints.erf",lambda n:True)
    for p in (ep/"textures.erf",ep.parent/"textures/high/texturepack.erf"):
        take(p,gear_material)
    # Materials may share maps whose names do not match the equipment prefix.
    maps = set()
    for name,(p,(pos,size)) in assets.items():
        if name.endswith(".mao"):
            with p.open("rb") as f:
                f.seek(pos)
                maps.update(v.decode().lower() for v in re.findall(rb'[a-zA-Z0-9_]+\.dds', f.read(size),re.I))
    for p in (ep/"textures.erf",ep.parent/"textures/high/texturepack.erf"):
        take(p,lambda n:n in maps)
    for p in sorted((ep.parent/"patch").glob("*.erf")):
        take(p,lambda n:n in assets)
    # Do not override models or materials that already belong to Origins.
    stock = set()
    for p in (core,sp):
        for archive in [*p.glob("*.erf"),*p.glob("*.rim"),*(p.parent/"patch").glob("*.erf")]:
            stock.update(index(archive))
    for archive in (core.parent/"textures").rglob("texturepack.erf"):
        stock.update(index(archive))
    for name,(path,(offset,size)) in assets.items():
        if name in stock:
            continue
        with path.open("rb") as f:
            f.seek(offset)
            (dest/name).write_bytes(f.read(size))
    (dest/"properties_wardenxp.gda").write_bytes(xp_property(resource(ep/"2da.erf","properties_gxa.gda")))
    # Scope localization to the existing English Origins campaign talktable.
    names = [sp/"talktables/singleplayer_en-us.tlk",ep/"talktables/core_ep1_en-us.tlk",
             module/"talktables/dao_prc_ep_1_en-us.tlk"]
    (dest/names[0].name).write_bytes(merge_talktables(names))
    return {n[:-4] for n in assets if n.endswith(".uti")}
