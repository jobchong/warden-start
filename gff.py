"""Small GFF V3.2 reader/writer for Origins placeables and area lists."""
import struct


def u32(data, at):
    return struct.unpack_from("<I", data, at)[0]


def word(value):
    return struct.pack("<I", value)


def read(data):
    if data[4:8] != b"V3.2":
        raise ValueError("Expected GFF V3.2")
    structs, _, fields, _, labels, _, payload, _, indices, _, lists, _ = struct.unpack_from("<12I", data, 8)

    def node(index):
        tag, start, count = struct.unpack_from("<III", data, structs + 12 * index)
        ids = [start] if count == 1 else struct.unpack_from(f"<{count}I", data, indices + start)
        result = {}
        for field in ids:
            kind, label, value = struct.unpack_from("<III", data, fields + 12 * field)
            name = data[labels + 16 * label:labels + 16 * (label + 1)].rstrip(b"\0").decode()
            if kind in (10, 11, 12):
                pos = payload + value
                width = 1 if kind == 11 else 4
                length = int.from_bytes(data[pos:pos + width], "little")
                value = data[pos + width:pos + width + length]
            elif kind == 15:
                pos = lists + value
                value = [node(i) for i in struct.unpack_from(f"<{u32(data, pos)}I", data, pos + 4)]
            elif kind not in (0, 1, 2, 3, 4, 5, 8):
                raise ValueError(f"Unexpected field type {kind} in {name}")
            result[name] = (kind, value)
        return tag, result
    return node(0)


def write(signature, root):
    structs, fields, labels, payload, indices, lists = (bytearray() for _ in range(6))
    label_ids = {}

    def node(value):
        tag, record = value
        here = len(structs)
        structs.extend(bytes(12))
        ids = []
        for name, (kind, val) in record.items():
            if name not in label_ids:
                label_ids[name] = len(labels) // 16
                labels.extend(name.encode().ljust(16, b"\0"))
            if kind in (10, 11, 12):
                offset = len(payload)
                payload.extend(len(val).to_bytes(1 if kind == 11 else 4, "little") + val)
                val = offset
            elif kind == 15:
                children = [node(child) for child in val]
                val = len(lists)
                lists.extend(word(len(children)) + b"".join(map(word, children)))
            ids.append(len(fields) // 12)
            fields.extend(struct.pack("<III", kind, label_ids[name], val))
        start = ids[0] if len(ids) == 1 else len(indices)
        if len(ids) > 1:
            indices.extend(b"".join(map(word, ids)))
        struct.pack_into("<III", structs, here, tag, start, len(ids))
        return here // 12

    node(root)
    parts = [structs, fields, labels, payload, indices, lists]
    header = bytearray(signature + b"V3.2")
    pos = 56
    for sector, unit in zip(parts, (12, 12, 16, 1, 1, 1)):
        header.extend(struct.pack("<II", pos, len(sector) // unit))
        pos += len(sector)
    return bytes(header) + b"".join(parts)
