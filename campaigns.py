"""Campaign item pools, area-entry hooks and native DAO script instructions."""
import struct
from functools import lru_cache
import xml.etree.ElementTree as ET
from gff import read, word, u32
from build import AREAS, checked_gff, index, new_game_script, resource, scale_areas, jsr


def action(number, argc):
    return struct.pack(">BBHB", 5, 0, number, argc)


def literal(text, kind=5):
    raw = text.encode("ascii")
    return bytes([4, kind]) + struct.pack(">H", len(raw)) + raw


def integer(value):
    return b"\x04\x03" + struct.pack(">i", value)


def ncs(body):
    return b"NCS V1.0B" + struct.pack(">I", len(body) + 13) + body


RETURN = bytes.fromhex("2000")
POP = bytes.fromhex("1b00fffffffc")
HERO = action(502, 0)


def run_xp():
    return literal("ws_grant_xp.ncs", 0x60) + action(108, 0) + action(121, 2)


def xp_script(original):
    # Substitute the integer parser in stock addxp. The reward code still
    # applies the game's campaign-specific level-up and point allocation.
    parser = bytes.fromhex("0301fffffff80004") + action(51, 1)
    at = original.index(parser)
    if original.count(parser) != 1:
        raise ValueError("Ambiguous XP parser")
    # GetM2DAInt(164, "XP", GetMaxLevel(), "") - current XP
    delta = literal("") + action(840, 0) + literal("XP") + integer(164) + action(667, 4)
    delta += integer(2) + integer(19) + HERO + action(738, 3) + action(49, 1) + bytes.fromhex("1520")
    # Clamp negative differences to zero on imported characters.
    delta += bytes.fromhex("0301fffffffc0004") + integer(0) + bytes.fromhex("0e20")
    delta += bytes.fromhex("1f0000000008") + RETURN + POP + integer(0) + RETURN
    data = bytearray(original + delta)
    data[at:at+13] = jsr(at, len(original)) + bytes.fromhex("1d000000000700")
    struct.pack_into(">I", data, 9, len(data))
    return data


def lookup(tag):
    return integer(0) + literal(tag) + action(211, 2)


def when(condition, body):
    return condition + b"\x1f\x00" + struct.pack(">I", 6 + len(body)) + body


def spawn_script(chest, waypoint="", top_up=False):
    # NCS native calls consume arguments in reverse source order.
    anchor = lookup(waypoint) if waypoint else HERO
    valid = action(206, 1)
    exit_if_present = when(lookup(chest) + valid, RETURN)
    exit_if_missing = when(anchor + valid + bytes.fromhex("2203"), RETURN)
    offset = bytes.fromhex("040400000000 040400000000 04043fa00000") + action(41, 3)
    position = anchor + action(21, 1) + offset + bytes.fromhex("143a")
    location = bytes.fromhex("040400000000") + position + anchor + action(223, 1) + action(454, 3)
    spawn = integer(0) + integer(1) + literal("") + location + literal(chest+".utp", 0x60)
    spawn += integer(512) + action(306, 6) + POP
    return ncs(exit_if_present + exit_if_missing + (run_xp() if top_up else b"") + spawn + RETURN)


def prcscr(template, rows):
    base = u32(template, 24)
    row_start = base + u32(template, base + 4)
    result = bytearray(template[:row_start]) + word(len(rows)) + bytearray(12 * len(rows))
    for i, (area, script) in enumerate(rows):
        row = row_start + 4 + i*12
        struct.pack_into("<I", result, row, 9204000+i)
        for j, value in enumerate((area, script)):
            struct.pack_into("<I", result, row+4+4*j, len(result)-base)
            result.extend(word(len(value)+1) + (value+"\0").encode("utf-16le"))
            while len(result) % 4:
                result.append(255)
    return result


def scale_creatures(original):
    # The standard spawn handler also runs inside DLC areas with their own
    # area tables. Replace only its two area-cap lookups, keeping the rank,
    # difficulty and encounter-specific branches.
    data = original
    for column, result in (("MaxLevel", action(840, 0)), ("IgnoreAppMaxLevel", integer(1))):
        tail = literal(column) + integer(225) + action(667, 4)
        if data.count(tail) != 1:
            raise ValueError("Unrecognized scaling routine for "+column)
        first = data.index(tail) - 12
        prefix = data[first:first+12]
        if prefix[:6] != bytes.fromhex("040500000301") or prefix[-2:] != b"\x00\x04":
            raise ValueError("Unexpected area lookup arguments")
        length = 12 + len(tail)
        skip = length - len(result)
        replacement = result + b"\x1d\x00" + struct.pack(">i", skip) + bytes(skip-6)
        data = data[:first] + replacement + data[first+length:]
    return data


STANDALONE = {
    "lel": ["lel100ar_market"],
    "drk": ["drk100ar_gates"],
    "gib": ["gib100ar_smithy"],
    "str": ["str100ar_hut_exterior"],
    "pcg": ["pcg100ar_tapsters"],
}


@lru_cache(maxsize=None)
def item_names(folder):
    names = set()
    for archive in folder.glob("*"):
        if archive.suffix.lower() in (".erf", ".rim"):
            names.update(n[:-4] for n in index(archive) if n.endswith(".uti"))
    return names


def build(game, profile, out):
    core = game/"packages/core/data"
    ep = game/"packages/core_ep1/data"
    campaign = game/"modules/single player/data"
    expansion = game/"Addins/dao_prc_ep_1/module/data"
    out.mkdir(parents=True, exist_ok=True)
    active = [a for a in ET.parse(profile/"Settings/AddIns.xml").getroot() if a.get("Enabled") == "1"]
    def collect(folders):
        return set().union(*(item_names(p) | item_names(p.parent/"patch") for p in folders))
    def extensions(uid):
        return [game/"Addins"/a.attrib["UID"]/bucket/"data" for a in active
                if a.get("ExtendedModuleUID", "").lower() == uid.lower() for bucket in ("core","module")]
    base = collect([core])
    pools = {"dao": base | collect([campaign, *extensions("Single Player")]),
             "ep1": base | collect([ep, expansion, expansion.parents[1]/"core/data", *extensions("DAO_PRC_EP_1")])}
    for short in STANDALONE:
        uid = "PC_GAMER_TALE" if short == "pcg" else "dao_prc_"+short
        root = game/"Addins"/uid
        folders = [root/"core/data",root/"module/data"]
        if short in ("str", "gib"):
            folders += [root/"module/data/coreep1"]
        pools[short] = base | collect(folders)
    from awakening import export
    pools["dao"].update(export(game, out))
    for key, names in pools.items():
        tag = "ws_chest_"+key
        chest = read(resource(core/"designerplaceables.erf", "genip_chest_wood_1.utp"))
        chest[1].update(Tag=(10,tag.encode()),TemplateResRef=(11,tag.encode()),
                        PickLock=(5,0),TreasureCategory=(5,0),Useable=(0,1))
        chest[1]["ItemList"] = (15, [(0, {"TemplateResRef": (11,n.encode()),"StackSize": (5,1)})
                                      for n in sorted(names)])
        (out/(tag+".utp")).write_bytes(checked_gff(b"UTP ",chest))
        (out/("ws_"+key+".ncs")).write_bytes(spawn_script(tag, top_up=True))
    lists = {"bdc210ar_players_home":"bdc02al_slums", "bec110ar_players_house":"bec01al_alienage",
             "bhn100ar_castle_cousland":"bhn01al_castle_cousland"}
    rows = []
    for i, (area, wp) in enumerate(AREAS.items()):
        script = f"ws_origin_{i}"
        (out/(script+".ncs")).write_bytes(spawn_script("ws_chest_dao", wp))
        rows.append((lists.get(area,area),script))
    (out/"ws_vigil.ncs").write_bytes(spawn_script("ws_chest_ep1","int100wp_start",top_up=True))
    rows.append(("int100ar_exterior","ws_vigil"))
    for key, areas in STANDALONE.items():
        rows.extend((area,"ws_"+key) for area in areas)
    table = resource(ep/"2da.erf","prcscr_gxa.gda")
    for name in ("prcscr_wardenstart","prcscrep1_wardenstart"):
        (out/(name+".gda")).write_bytes(prcscr(table,rows))
    stock = core/"designerscripts.rim"
    (out/"ws_grant_xp.ncs").write_bytes(xp_script(resource(stock,"addxp.ncs")))
    (out/"sp_module.ncs").write_bytes(new_game_script(resource(campaign/"designerscripts.erf","sp_module.ncs")))
    (out/"gxa_module_chargen.ncs").write_bytes(new_game_script(resource(expansion/"designerscripts.erf","gxa_module_chargen.ncs")))
    (out/"creature_core.ncs").write_bytes(scale_creatures(resource(stock,"creature_core.ncs")))
    (out/"areadata.gda").write_bytes(scale_areas(resource(core/"2da.erf","areadata.gda"),35))
    (out/"areadata_gxa.gda").write_bytes(scale_areas(resource(ep/"2da.erf","areadata_gxa.gda"),35))
    print("Unique item templates per campaign:", {k:len(v) for k,v in pools.items()})

