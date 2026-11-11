"""Build Warden Start against the local GOG Ultimate Edition campaign."""
from pathlib import Path
import argparse
import struct
import xml.etree.ElementTree as ET
import zlib
from gff import read, write, u32, word

HERE = Path(__file__).resolve().parent
AREAS = {
    "bdc210ar_players_home": "bdc210wp_start",
    "bdn120ar_royal_palace": "start",
    "bec110ar_players_house": "bec110wp_start",
    "bed100ar_forest_clearing": "bed100wp_start",
    "bhm500ar_tower_harrowing": "bhm400wp_start",
    "bhm600ar_fade_harrowing": "bhm600wp_pc_start",
    "bhn100ar_castle_cousland": "bhn100wp_start",
    "cam100ar_camp_plains": "cam100wp_entrance",
}


def index(path):
    with path.open("rb") as stream:
        version = stream.read(16).decode("utf-16le")
        layouts = {"ERF V2.0": (32, "<64sII"), "ERF V2.2": (56, "<64sIII")}
        if version not in layouts:
            raise ValueError(f"Unknown archive version in {path}")
        start, fmt = layouts[version]
        count = u32(stream.read(4), 0)
        stream.seek(start)
        rows = struct.iter_unpack(fmt, stream.read(count * struct.calcsize(fmt)))
        return {raw.decode("utf-16le").rstrip("\0"): (offset, size)
                for raw, offset, size, *_ in rows}


def resource(source, name):
    for archive in reversed([source, *sorted((source.parent.parent / "patch").glob("*.erf"))]):
        entry = index(archive).get(name)
        if entry:
            with archive.open("rb") as stream:
                stream.seek(entry[0])
                return stream.read(entry[1])
    raise KeyError(name)


def jsr(at, target):
    return b"\x1e\x00" + struct.pack(">i", target - at)


def new_game_script(original):
    # Redirect only the logging call in EVENT_TYPE_MODULE_CHARGEN_DONE.
    # The trampoline invokes the original logger, then dispatches the same
    # event to the XP script before the stock origin-area transition begins.
    marker = b"EVENT_TYPE_MODULE_CHARGEN_DONE" + bytes.fromhex("040300000258")
    if original.count(marker) != 1:
        raise ValueError("Unrecognized character-generation handler")
    at = original.index(marker) + len(marker)
    if original[at:at+2] != b"\x1e\x00":
        raise ValueError("Missing character-generation log call")
    target = at + struct.unpack_from(">i", original, at+2)[0]
    tail = jsr(len(original), target)
    script = b"ws_grant_xp.ncs"
    tail += b"\x04\x60" + struct.pack(">H", len(script)) + script
    tail += bytes.fromhex("0500006c00 0500007902 2000")
    data = bytearray(original + tail)
    data[at:at+6] = jsr(at, len(original))
    struct.pack_into(">I", data, 9, len(data))
    return data


def scale_areas(original, maximum=25):
    data = bytearray(original)
    base = u32(data, 24)
    cols, rows = (base + u32(data, base+i) for i in (0, 4))
    stride = u32(data, 28 + 2*16 + 12)
    headers = [u32(data, cols+4+i*8) for i in range(u32(data, cols))]
    def field(label):
        return 4 * headers.index(zlib.crc32(label.lower().encode("utf-16le")))
    cap, ignore, ident = map(field, ("MaxLevel", "IgnoreAppMaxLevel", "ID"))
    for i in range(u32(data, rows)):
        pos = rows + 4 + i * stride
        if u32(data, pos + ident) == 0:
            continue
        old = struct.unpack_from("<i", data, pos + cap)[0]
        if 0 < old < maximum:
            struct.pack_into("<i", data, pos + cap, maximum)
        data[pos+ignore:pos+ignore+4] = word(1)
    return data


def checked_gff(signature, tree):
    blob = write(signature, tree)
    if read(blob) != tree:
        raise ValueError("GFF round-trip validation failed")
    return blob





if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--game", type=Path, default=Path(r"C:\Program Files (x86)\GOG Galaxy\Games\Dragon Age Origins"))
    parser.add_argument("--profile", type=Path, default=Path.home()/"Documents/BioWare/Dragon Age")
    parser.add_argument("--output", type=Path, default=HERE/"Package")
    args = parser.parse_args()
    from campaigns import build
    build(args.game, args.profile, args.output)


