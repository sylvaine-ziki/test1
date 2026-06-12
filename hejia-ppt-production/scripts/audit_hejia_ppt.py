#!/usr/bin/env python3
"""Audit hard Hejia PPT SOP rules without changing the PPTX."""

import argparse
import re
import zipfile
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET

NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
}

TITLE_COLOR = "404040"
SECONDARY_COLOR = "7F7F7F"
SOURCE_COLOR = "919191"
SOURCE_SIZE = 1000
STORYLINE_SECONDARY_SIZE = 1600
STORYLINE_PRIMARY_SIZE = 2400
SOURCE_TEXT = "数据来源"
ALLOWED_FONT_PARTS = ("思源黑体", "Source Han Sans")
RED_COLORS = {"AD0B29", "AE0B2A", "AD0C29"}


def slide_number(path):
    return int(re.search(r"\d+", path.stem).group())


def shape_text(shape):
    return "".join(node.text or "" for node in shape.findall(".//a:t", NS))


def shape_name(shape):
    node = shape.find("p:nvSpPr/p:cNvPr", NS)
    return node.attrib.get("name", "") if node is not None else ""


def run_color(run):
    solid = run.find("a:solidFill", NS)
    if solid is None:
        return None
    srgb = solid.find("a:srgbClr", NS)
    return srgb.attrib.get("val", "").upper() if srgb is not None else None


def run_fonts(run):
    fonts = []
    for tag in ("latin", "ea", "cs"):
        node = run.find(f"a:{tag}", NS)
        if node is not None and node.attrib.get("typeface"):
            fonts.append(node.attrib["typeface"])
    return fonts


def has_red_triangle(root):
    for shape in root.findall(".//p:sp", NS):
        geom = shape.find(".//a:prstGeom", NS)
        if geom is None or geom.attrib.get("prst") not in {"triangle", "rtTriangle"}:
            continue
        for color in shape.findall(".//a:srgbClr", NS):
            if color.attrib.get("val", "").upper() in RED_COLORS:
                return True
    return False


def has_red_source_bullet(archive):
    for name in archive.namelist():
        if not re.fullmatch(r"ppt/slideLayouts/slideLayout\d+\.xml", name):
            continue
        root = ET.fromstring(archive.read(name))
        for shape in root.findall(".//p:sp", NS):
            placeholder = shape.find("p:nvSpPr/p:nvPr/p:ph", NS)
            if placeholder is None or placeholder.attrib.get("idx") != "17":
                continue
            for color in shape.findall(".//a:buClr/a:srgbClr", NS):
                if color.attrib.get("val", "").upper() in RED_COLORS:
                    return True
    return False


def check_named_text_style(shape, slide_num, expected_size, expected_color, expected_bold, errors, warnings):
    name = shape_name(shape)
    runs = shape.findall(".//a:rPr", NS) + shape.findall(".//a:defRPr", NS)
    if not runs:
        warnings.append(f"slide {slide_num}: {name} has no explicit run style to audit")
        return
    for run in runs:
        size = int(run.attrib.get("sz", "0") or 0)
        color = run_color(run)
        bold = run.attrib.get("b") == "1"
        fonts = run_fonts(run)
        if size and size != expected_size:
            errors.append(f"slide {slide_num}: {name} must be {expected_size / 100:g} pt")
        if color and color != expected_color:
            errors.append(f"slide {slide_num}: {name} color must be #{expected_color}")
        if bold != expected_bold:
            errors.append(f"slide {slide_num}: {name} bold setting is incorrect")
        if fonts and not all(any(part in font for part in ALLOWED_FONT_PARTS) for font in fonts):
            errors.append(f"slide {slide_num}: {name} must use Source Han Sans / 思源黑体")


def check_storyline_style(shape, slide_num, errors, warnings):
    paragraphs = [
        paragraph
        for paragraph in shape.findall(".//a:p", NS)
        if "".join(node.text or "" for node in paragraph.findall(".//a:t", NS)).strip()
    ]
    if len(paragraphs) not in {2, 3}:
        errors.append(f"slide {slide_num}: HEJIA_STORYLINE must contain 2–3 non-empty lines in one text box")
        return
    for index, paragraph in enumerate(paragraphs):
        expected_size = STORYLINE_SECONDARY_SIZE if index == 0 else STORYLINE_PRIMARY_SIZE
        expected_color = SECONDARY_COLOR if index == 0 else TITLE_COLOR
        runs = (
            paragraph.findall(".//a:rPr", NS)
            + paragraph.findall("a:pPr/a:defRPr", NS)
            + paragraph.findall("a:endParaRPr", NS)
        )
        if not runs:
            warnings.append(f"slide {slide_num}: HEJIA_STORYLINE line {index + 1} has no explicit style to audit")
            continue
        for run in runs:
            size = int(run.attrib.get("sz", "0") or 0)
            color = run_color(run)
            bold = run.attrib.get("b") == "1"
            fonts = run_fonts(run)
            if not size:
                errors.append(f"slide {slide_num}: HEJIA_STORYLINE line {index + 1} must explicitly set {expected_size / 100:g} pt")
            elif size != expected_size:
                errors.append(f"slide {slide_num}: HEJIA_STORYLINE line {index + 1} must be {expected_size / 100:g} pt")
            if not color:
                errors.append(f"slide {slide_num}: HEJIA_STORYLINE line {index + 1} must explicitly set color #{expected_color}")
            elif color != expected_color:
                errors.append(f"slide {slide_num}: HEJIA_STORYLINE line {index + 1} color must be #{expected_color}")
            if bold is False and "b" in run.attrib:
                errors.append(f"slide {slide_num}: HEJIA_STORYLINE line {index + 1} must be bold")
            if fonts and not all(any(part in font for part in ALLOWED_FONT_PARTS) for font in fonts):
                errors.append(f"slide {slide_num}: HEJIA_STORYLINE must use Source Han Sans / 思源黑体")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("pptx", type=Path)
    parser.add_argument("--allow-no-source", action="store_true", help="Allow cover/chapter/ending slides without sources")
    args = parser.parse_args()

    errors = []
    warnings = []
    font_counts = Counter()

    with zipfile.ZipFile(args.pptx) as archive:
        master_has_red_source_bullet = has_red_source_bullet(archive)
        slide_names = sorted(
            (name for name in archive.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)),
            key=lambda name: int(re.search(r"\d+", name).group()),
        )
        for name in slide_names:
            num = int(re.search(r"\d+", name).group())
            root = ET.fromstring(archive.read(name))
            shapes = root.findall(".//p:sp", NS)
            texts = [shape_text(shape) for shape in shapes]
            joined = "".join(texts)
            has_source = SOURCE_TEXT in joined

            if not has_source and not args.allow_no_source:
                warnings.append(f"slide {num}: missing 数据来源; confirm it is a cover/chapter/ending slide")
            if has_source and not (master_has_red_source_bullet or has_red_triangle(root)):
                errors.append(f"slide {num}: 数据来源 exists but red source triangle is missing")

            named_shapes = {shape_name(shape): shape for shape in shapes if shape_name(shape)}
            if "HEJIA_STORYLINE" in named_shapes:
                errors.append(f"slide {num}: Storyline must use two text boxes, not one HEJIA_STORYLINE box")
            elif any(name.startswith("HEJIA_STORYLINE_") for name in named_shapes):
                storyline_specs = {
                    "HEJIA_STORYLINE_SECONDARY": (STORYLINE_SECONDARY_SIZE, SECONDARY_COLOR),
                    "HEJIA_STORYLINE_PRIMARY": (STORYLINE_PRIMARY_SIZE, TITLE_COLOR),
                }
                for name, (size, color) in storyline_specs.items():
                    if name not in named_shapes:
                        errors.append(f"slide {num}: missing {name}")
                        continue
                    check_named_text_style(named_shapes[name], num, size, color, True, errors, warnings)
                if "HEJIA_STORYLINE_PRIMARY" in named_shapes:
                    primary_paragraphs = [
                        paragraph
                        for paragraph in named_shapes["HEJIA_STORYLINE_PRIMARY"].findall(".//a:p", NS)
                        if "".join(node.text or "" for node in paragraph.findall(".//a:t", NS)).strip()
                    ]
                    if len(primary_paragraphs) not in {1, 2}:
                        errors.append(f"slide {num}: HEJIA_STORYLINE_PRIMARY must contain 1–2 title lines in one text box")
            if "HEJIA_SOURCE_TEXT" in named_shapes:
                check_named_text_style(
                    named_shapes["HEJIA_SOURCE_TEXT"],
                    num,
                    SOURCE_SIZE,
                    SOURCE_COLOR,
                    False,
                    errors,
                    warnings,
                )

            title_shapes = []
            for shape in shapes:
                ph = shape.find(".//p:ph", NS)
                if ph is not None and ph.attrib.get("type") in {"title", "ctrTitle"}:
                    title_shapes.append(shape)

            for shape in title_shapes:
                paras = [p for p in shape.findall(".//a:p", NS) if "".join(t.text or "" for t in p.findall(".//a:t", NS)).strip()]
                if len(paras) > 3:
                    warnings.append(f"slide {num}: Storyline title has more than 3 non-empty paragraphs")

            for shape in shapes:
                text = shape_text(shape)
                is_source = SOURCE_TEXT in text
                for run in shape.findall(".//a:rPr", NS) + shape.findall(".//a:defRPr", NS):
                    size = int(run.attrib.get("sz", "0") or 0)
                    color = run_color(run)
                    fonts = run_fonts(run)
                    for font in fonts:
                        font_counts[font] += 1
                        if not font.startswith("+") and not any(part in font for part in ALLOWED_FONT_PARTS):
                            warnings.append(f"slide {num}: non-SOP font {font}")
                    if size and size < 900:
                        errors.append(f"slide {num}: text below 9 pt")
                    if is_source:
                        if size and size != SOURCE_SIZE:
                            errors.append(f"slide {num}: source text must be 10 pt, found {size / 100:g} pt")
                        if color and color != SOURCE_COLOR:
                            errors.append(f"slide {num}: source text color must be #{SOURCE_COLOR}, found #{color}")

            primary_storyline = named_shapes.get("HEJIA_STORYLINE_PRIMARY")
            primary_storyline_paragraphs = set(primary_storyline.findall(".//a:pPr", NS)) if primary_storyline is not None else set()
            secondary_storyline = named_shapes.get("HEJIA_STORYLINE_SECONDARY")
            secondary_storyline_paragraphs = set(secondary_storyline.findall(".//a:pPr", NS)) if secondary_storyline is not None else set()
            for paragraph in root.findall(".//a:pPr", NS):
                spacing = paragraph.find("a:lnSpc/a:spcPct", NS)
                if spacing is not None:
                    value = int(spacing.attrib.get("val", "0") or 0)
                    if (
                        value
                        and value < 100000
                        and paragraph not in primary_storyline_paragraphs
                        and paragraph not in secondary_storyline_paragraphs
                    ):
                        warnings.append(f"slide {num}: line spacing below 100%")

    errors = list(dict.fromkeys(errors))
    warnings = list(dict.fromkeys(warnings))
    print(f"slides: {len(slide_names)}")
    print("fonts:", ", ".join(f"{font}({count})" for font, count in font_counts.most_common(10)))
    print(f"errors: {len(errors)}, warnings: {len(warnings)}")
    for item in errors:
        print("ERROR:", item)
    for item in warnings:
        print("WARN:", item)
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
