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
CONTENT_TITLE_SPACIOUS_SIZES = (1400, 1200)
CONTENT_TITLE_COMPACT_SIZES = (1200, 1000)
SOURCE_TEXT = "数据来源"
ALLOWED_FONT_PARTS = ("思源黑体", "Source Han Sans")
SOURCE_SUFFIX = "，和君咨询分析"


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
    if name in {"HEJIA_SOURCE_TEXT", "HEJIA_MASTER_SOURCE"}:
        for paragraph in shape.findall(".//a:p", NS):
            if not "".join(node.text or "" for node in paragraph.findall(".//a:t", NS)).strip():
                continue
            spacing = paragraph.find("a:pPr/a:lnSpc/a:spcPct", NS)
            if spacing is None or int(spacing.attrib.get("val", "0") or 0) != 100000:
                errors.append(f"slide {slide_num}: source line spacing must be 100%")


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


def check_content_block_title(shape, slide_num, errors, warnings):
    name = shape_name(shape)
    paragraphs = [
        paragraph
        for paragraph in shape.findall(".//a:p", NS)
        if "".join(node.text or "" for node in paragraph.findall(".//a:t", NS)).strip()
    ]
    if len(paragraphs) != 2:
        errors.append(f"slide {slide_num}: {name} must contain title and unit in one two-line text box")
        return

    found_sizes = []
    for index, paragraph in enumerate(paragraphs):
        explicit_runs = paragraph.findall(".//a:rPr", NS)
        runs = explicit_runs or paragraph.findall("a:pPr/a:defRPr", NS)
        explicit_sizes = {int(run.attrib["sz"]) for run in runs if run.attrib.get("sz")}
        if len(explicit_sizes) != 1:
            warnings.append(f"slide {slide_num}: {name} line {index + 1} should have one explicit font size")
            found_sizes.append(None)
        else:
            found_sizes.append(explicit_sizes.pop())
        for run in runs:
            if run.attrib.get("b") == "0":
                errors.append(f"slide {slide_num}: {name} title and unit must be bold")
            fonts = run_fonts(run)
            if fonts and not all(any(part in font for part in ALLOWED_FONT_PARTS) for font in fonts):
                errors.append(f"slide {slide_num}: {name} must use Source Han Sans / 思源黑体")
            if fonts and any("Bold" in font for font in fonts):
                errors.append(f"slide {slide_num}: {name} must use Regular typeface with bold property, not Bold typeface")

    if tuple(found_sizes) not in {CONTENT_TITLE_SPACIOUS_SIZES, CONTENT_TITLE_COMPACT_SIZES}:
        errors.append(
            f"slide {slide_num}: {name} sizes must be 14/12 pt in spacious layout or 12/10 pt in compact layout"
        )
    for paragraph in paragraphs:
        spacing = paragraph.find("a:pPr/a:lnSpc/a:spcPct", NS)
        if spacing is None or int(spacing.attrib.get("val", "0") or 0) != 120000:
            errors.append(f"slide {slide_num}: {name} title and unit line spacing must be 120%")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("pptx", type=Path)
    parser.add_argument("--allow-no-source", action="store_true", help="Allow cover/chapter/ending slides without sources")
    args = parser.parse_args()

    errors = []
    warnings = []
    font_counts = Counter()

    with zipfile.ZipFile(args.pptx) as archive:
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
            if has_source and SOURCE_SUFFIX not in joined:
                errors.append(f"slide {num}: 数据来源 must end with {SOURCE_SUFFIX}")

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
                    if len(primary_paragraphs) != 1:
                        errors.append(
                            f"slide {num}: HEJIA_STORYLINE_PRIMARY must be one sentence in one paragraph; allow natural wrapping"
                        )
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
            if "HEJIA_MASTER_SOURCE" in named_shapes:
                check_named_text_style(
                    named_shapes["HEJIA_MASTER_SOURCE"],
                    num,
                    SOURCE_SIZE,
                    SOURCE_COLOR,
                    False,
                    errors,
                    warnings,
                )
            for shape in shapes:
                if shape_name(shape).startswith("HEJIA_CONTENT_BLOCK_TITLE"):
                    check_content_block_title(shape, num, errors, warnings)

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
                is_storyline = shape_name(shape).startswith("HEJIA_STORYLINE_")
                for run in shape.findall(".//a:rPr", NS) + shape.findall(".//a:defRPr", NS):
                    size = int(run.attrib.get("sz", "0") or 0)
                    color = run_color(run)
                    fonts = run_fonts(run)
                    for font in fonts:
                        font_counts[font] += 1
                        if not font.startswith("+") and not any(part in font for part in ALLOWED_FONT_PARTS):
                            warnings.append(f"slide {num}: non-SOP font {font}")
                        if not is_storyline and "Bold" in font:
                            errors.append(
                                f"slide {num}: content-area text must use Regular typeface; emphasize with bold property"
                            )
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
