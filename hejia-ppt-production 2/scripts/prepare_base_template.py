#!/usr/bin/env python3
"""Prepare the Hejia base template by removing the source bullet."""

import argparse
import shutil
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
NS = {"a": A_NS, "p": P_NS}
ET.register_namespace("a", A_NS)
ET.register_namespace("p", P_NS)


def update_layout(xml_bytes):
    root = ET.fromstring(xml_bytes)
    changed = False
    for shape in root.findall(".//p:sp", NS):
        placeholder = shape.find("p:nvSpPr/p:nvPr/p:ph", NS)
        if placeholder is None or placeholder.attrib.get("idx") != "17":
            continue
        for level in shape.findall(".//a:lvl1pPr", NS):
            for tag in ("buClr", "buChar", "buAutoNum", "buBlip", "buNone"):
                for child in level.findall(f"a:{tag}", NS):
                    level.remove(child)
            level.insert(0, ET.Element(f"{{{A_NS}}}buNone"))
            changed = True
    if not changed:
        raise RuntimeError("Could not find data-source placeholder idx=17 in slideLayout21.xml")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir) / "prepared.pptx"
        with zipfile.ZipFile(args.source) as source_zip, zipfile.ZipFile(temp_path, "w") as output_zip:
            for info in source_zip.infolist():
                data = source_zip.read(info.filename)
                if info.filename == "ppt/slideLayouts/slideLayout21.xml":
                    data = update_layout(data)
                output_zip.writestr(info, data)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(temp_path, args.output)


if __name__ == "__main__":
    main()
