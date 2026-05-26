"""Convert PPTX slides into JSON slide elements.

Usage:
    uv run python pptx_to_json.py deck.pptx -o deck.json --assets-dir assets/pptx-assets
"""

from __future__ import annotations

import argparse
import hashlib
import math
import mimetypes
import posixpath
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, TypeAlias
from xml.etree import ElementTree as ET

from pydantic import BaseModel, TypeAdapter

from elements import Size, SlideElement


EMU_TO_PX = 1 / 9525
DEFAULT_TARGET_WIDTH = 1280.0
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "c": "http://schemas.openxmlformats.org/drawingml/2006/chart",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}

THEME_COLOR_ALIASES = {
    "bg1": "lt1",
    "tx1": "dk1",
    "bg2": "lt2",
    "tx2": "dk2",
}

DASH_PATTERNS = {
    "dash": [6, 4],
    "dashDot": [6, 3, 1, 3],
    "dot": [1, 3],
    "lgDash": [10, 4],
    "lgDashDot": [10, 4, 1, 4],
    "lgDashDotDot": [10, 4, 1, 4, 1, 4],
    "sysDash": [4, 3],
    "sysDashDot": [4, 3, 1, 3],
    "sysDashDotDot": [4, 3, 1, 3, 1, 3],
    "sysDot": [1, 2],
}


Slide: TypeAlias = List[SlideElement]
SLIDE_ADAPTER = TypeAdapter(Slide)


class PPTXPresentation(BaseModel):
    name: str
    size: Size
    slides: List[Slide]


@dataclass
class Transform:
    offx: float
    offy: float
    scale_x: float
    scale_y: float
    ch_offx: float = 0
    ch_offy: float = 0
    rotation: float = 0


@dataclass
class Box:
    x: float
    y: float
    width: float
    height: float
    rotation: float = 0


def convert_pptx_to_json(
    pptx_path: str | Path,
    *,
    output_path: str | Path | None = None,
    assets_dir: str | Path | None = None,
    target_width: float = DEFAULT_TARGET_WIDTH,
    max_slides: int | None = None,
) -> PPTXPresentation:
    """Convert a PPTX file into a JSON-serializable presentation object."""

    converter = PPTXToJSON(
        pptx_path=pptx_path,
        assets_dir=assets_dir,
        target_width=target_width,
    )
    try:
        data = converter.convert(max_slides=max_slides)
    finally:
        converter.close()

    if output_path is not None:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(data.model_dump_json(indent=2) + "\n", encoding="utf-8")

    return data


class PPTXToJSON:
    def __init__(
        self,
        pptx_path: str | Path,
        *,
        assets_dir: str | Path | None = None,
        target_width: float = DEFAULT_TARGET_WIDTH,
    ) -> None:
        self.pptx_path = Path(pptx_path)
        if not self.pptx_path.exists():
            raise FileNotFoundError(f"PPTX file not found: {self.pptx_path}")

        self.assets_dir = (
            Path(assets_dir)
            if assets_dir is not None
            else self.pptx_path.with_suffix("").parent
            / f"{self.pptx_path.stem}_assets"
        )
        self.target_width = target_width
        self.archive = zipfile.ZipFile(self.pptx_path, "r")
        self.rels_cache: dict[str, dict[str, dict[str, str | bool]]] = {}
        self.asset_cache: dict[str, str] = {}
        self.theme_colors: dict[str, str] = {}
        self.theme_fonts: dict[str, str] = {}
        self.slide_width = 0.0
        self.slide_height = 0.0
        self.scale_factor = 1.0

    def close(self) -> None:
        self.archive.close()

    def convert(self, *, max_slides: int | None = None) -> PPTXPresentation:
        presentation = self._read_xml("ppt/presentation.xml")
        if presentation is None:
            raise ValueError("Invalid PPTX: ppt/presentation.xml not found")

        self._load_theme()
        self._load_slide_size(presentation)

        slides: List[Slide] = []
        pres_rels = self._get_rels("ppt/presentation.xml")
        sld_id_lst = presentation.find("p:sldIdLst", NS)
        if sld_id_lst is not None:
            for slide_id in sld_id_lst.findall("p:sldId", NS):
                if max_slides is not None and len(slides) >= max_slides:
                    break

                rel_id = slide_id.get(f"{{{NS['r']}}}id")
                if not rel_id or rel_id not in pres_rels:
                    continue

                slide_path = str(pres_rels[rel_id]["path"])
                slides.append(self._convert_slide(slide_path))

        return PPTXPresentation(
            name=self.pptx_path.stem,
            size=Size(
                width=_round(self.slide_width),
                height=_round(self.slide_height),
            ),
            slides=slides,
        )

    def _convert_slide(self, slide_path: str) -> Slide:
        slide_xml = self._read_xml(slide_path)
        if slide_xml is None:
            return []

        slide_rels = self._get_rels(slide_path)
        layout_path = self._first_related_path(slide_rels, "slideLayout")
        layout_xml = self._read_xml(layout_path) if layout_path else None
        layout_rels = self._get_rels(layout_path) if layout_path else {}

        master_path = self._first_related_path(layout_rels, "slideMaster")
        master_xml = self._read_xml(master_path) if master_path else None
        master_rels = self._get_rels(master_path) if master_path else {}

        placeholder_xfrms = self._build_placeholder_xfrm_map(layout_xml, master_xml)

        elements: list[dict[str, Any]] = []
        elements.extend(self._convert_background(master_xml, master_rels))
        elements.extend(self._convert_background(layout_xml, layout_rels))
        elements.extend(self._convert_background(slide_xml, slide_rels))

        if master_xml is not None:
            elements.extend(
                self._convert_shape_tree(
                    master_xml.find(".//p:spTree", NS),
                    master_rels,
                    skip_placeholders=True,
                )
            )

        if layout_xml is not None:
            elements.extend(
                self._convert_shape_tree(
                    layout_xml.find(".//p:spTree", NS),
                    layout_rels,
                    skip_placeholders=True,
                )
            )

        elements.extend(
            self._convert_shape_tree(
                slide_xml.find(".//p:spTree", NS),
                slide_rels,
                placeholder_xfrms=placeholder_xfrms,
            )
        )

        return SLIDE_ADAPTER.validate_python(elements)

    def _convert_background(
        self,
        slide_xml: ET.Element | None,
        rels: dict[str, dict[str, str | bool]],
    ) -> list[dict[str, Any]]:
        if slide_xml is None:
            return []

        bg = slide_xml.find("p:cSld/p:bg", NS)
        if bg is None:
            return []

        bg_pr = bg.find("p:bgPr", NS)
        if bg_pr is None:
            return []

        elements: list[dict[str, Any]] = []
        fill = self._extract_fill(bg_pr)
        if fill is not None:
            elements.append(
                {
                    "type": "rectangle",
                    "fixed": True,
                    "position": {"x": 0, "y": 0},
                    "size": {
                        "width": _round(self.slide_width),
                        "height": _round(self.slide_height),
                    },
                    "fill": fill,
                }
            )

        image_url = self._resolve_blip_asset(bg_pr, rels)
        if image_url is not None:
            elements.append(
                {
                    "type": "image",
                    "fixed": True,
                    "position": {"x": 0, "y": 0},
                    "size": {
                        "width": _round(self.slide_width),
                        "height": _round(self.slide_height),
                    },
                    "data": image_url,
                    "name": "background",
                    "fit": "cover",
                }
            )

        return elements

    def _convert_shape_tree(
        self,
        tree: ET.Element | None,
        rels: dict[str, dict[str, str | bool]],
        *,
        transform: Transform | None = None,
        skip_placeholders: bool = False,
        placeholder_xfrms: dict[tuple[str, str | None], ET.Element] | None = None,
    ) -> list[dict[str, Any]]:
        if tree is None:
            return []

        elements: list[dict[str, Any]] = []
        for child in list(tree):
            tag = _local_name(child.tag)
            if tag in {"sp", "pic", "cxnSp"}:
                elements.extend(
                    self._convert_shape(
                        child,
                        rels,
                        transform=transform,
                        skip_placeholders=skip_placeholders,
                        placeholder_xfrms=placeholder_xfrms,
                    )
                )
            elif tag == "grpSp":
                group_transform = self._build_group_transform(child, transform)
                elements.extend(
                    self._convert_shape_tree(
                        child,
                        rels,
                        transform=group_transform,
                        skip_placeholders=skip_placeholders,
                        placeholder_xfrms=placeholder_xfrms,
                    )
                )
            elif tag == "graphicFrame":
                table = self._convert_table(child, transform=transform)
                if table is not None:
                    elements.append(table)
                    continue

                chart = self._convert_chart(child, rels, transform=transform)
                if chart is not None:
                    elements.append(chart)

        return elements

    def _convert_shape(
        self,
        shape: ET.Element,
        rels: dict[str, dict[str, str | bool]],
        *,
        transform: Transform | None = None,
        skip_placeholders: bool = False,
        placeholder_xfrms: dict[tuple[str, str | None], ET.Element] | None = None,
    ) -> list[dict[str, Any]]:
        if self._is_hidden(shape):
            return []
        if skip_placeholders and self._is_placeholder(shape):
            return []

        box = self._shape_box(
            shape,
            transform=transform,
            placeholder_xfrms=placeholder_xfrms,
        )
        if box is None:
            return []

        image_url = self._shape_image_url(shape, rels)
        if image_url is not None:
            return [
                _drop_none(
                    {
                        "type": "image",
                        "fixed": False,
                        "position": {"x": box.x, "y": box.y},
                        "size": {"width": box.width, "height": box.height},
                        "rotation": box.rotation or None,
                        "data": image_url,
                        "name": self._shape_name(shape) or Path(image_url).name,
                        "fit": self._image_fit(shape),
                    }
                )
            ]

        tag = _local_name(shape.tag)
        sp_pr = shape.find("p:spPr", NS)
        geometry = self._shape_geometry(shape)
        fill = self._extract_fill(sp_pr)
        stroke = self._extract_stroke(sp_pr)
        shadow = self._extract_shadow(sp_pr)
        has_text = self._shape_has_text(shape)

        elements: list[dict[str, Any]] = []
        if tag == "cxnSp" or geometry == "line":
            elements.append(
                _drop_none(
                    {
                        "type": "line",
                        "fixed": True,
                        "position": {"x": box.x, "y": box.y},
                        "size": {
                            "width": max(box.width, 1),
                            "height": max(box.height, 1),
                        },
                        "rotation": box.rotation or None,
                        "stroke": stroke
                        or {"color": "#000000", "width": _round(self.scale_factor)},
                        "shadow": shadow,
                    }
                )
            )
        elif fill is not None or stroke is not None or shadow is not None:
            element_type = "ellipse" if geometry == "ellipse" else "rectangle"
            elements.append(
                _drop_none(
                    {
                        "type": element_type,
                        "fixed": True,
                        "position": {"x": box.x, "y": box.y},
                        "size": {"width": box.width, "height": box.height},
                        "rotation": box.rotation or None,
                        "fill": fill,
                        "stroke": stroke,
                        "shadow": shadow,
                        "borderRadius": self._border_radius(geometry, box),
                    }
                )
            )

        if has_text:
            text_element = self._convert_text(shape, box)
            if text_element is not None:
                elements.append(text_element)

        return elements

    def _convert_text(self, shape: ET.Element, box: Box) -> dict[str, Any] | None:
        tx_body = shape.find("p:txBody", NS)
        if tx_body is None:
            return None

        paragraphs = tx_body.findall("a:p", NS)
        runs: list[dict[str, Any]] = []
        first_alignment: str | None = None
        first_font: dict[str, Any] | None = None

        for paragraph_index, paragraph in enumerate(paragraphs):
            p_pr = paragraph.find("a:pPr", NS)
            if first_alignment is None:
                first_alignment = self._paragraph_alignment(p_pr)

            if paragraph_index > 0 and runs:
                runs.append({"text": "\n", "font": first_font})

            paragraph_runs = self._paragraph_runs(paragraph, p_pr)
            if not paragraph_runs:
                continue

            for run in paragraph_runs:
                if first_font is None:
                    first_font = run.get("font")
                runs.append(run)

        runs = _merge_text_runs(runs)
        if not runs:
            return None

        return _drop_none(
            {
                "type": "text",
                "fixed": False,
                "position": {"x": box.x, "y": box.y},
                "size": {"width": box.width, "height": box.height},
                "rotation": box.rotation or None,
                "font": first_font,
                "alignment": {
                    "horizontal": first_alignment,
                    "vertical": self._vertical_alignment(tx_body.find("a:bodyPr", NS)),
                },
                "runs": runs,
                "minLength": _plain_text_length(runs),
                "maxLength": _plain_text_length(runs),
            }
        )

    def _paragraph_runs(
        self,
        paragraph: ET.Element,
        p_pr: ET.Element | None,
    ) -> list[dict[str, Any]]:
        paragraph_font = self._font_from_run_properties(
            p_pr.find("a:defRPr", NS) if p_pr is not None else None
        )
        runs: list[dict[str, Any]] = []

        for child in list(paragraph):
            tag = _local_name(child.tag)
            if tag == "br":
                runs.append({"text": "\n", "font": paragraph_font})
                continue
            if tag not in {"r", "fld"}:
                continue

            text_node = child.find("a:t", NS)
            if text_node is None or text_node.text is None:
                continue

            font = self._font_from_run_properties(child.find("a:rPr", NS))
            font = {**paragraph_font, **font} if paragraph_font else font
            runs.append({"text": text_node.text, "font": font or None})

        return runs

    def _convert_table(
        self,
        graphic_frame: ET.Element,
        *,
        transform: Transform | None = None,
    ) -> dict[str, Any] | None:
        tbl = graphic_frame.find(".//a:tbl", NS)
        if tbl is None:
            return None

        box = self._graphic_frame_box(graphic_frame, transform=transform)
        if box is None:
            return None

        columns = [
            self._empty_table_cell()
            for _ in tbl.findall("a:tblGrid/a:gridCol", NS)
        ]
        rows: list[list[dict[str, Any]]] = []

        for tr in tbl.findall("a:tr", NS):
            row: list[dict[str, Any]] = []
            for tc in tr.findall("a:tc", NS):
                row.append(self._convert_table_cell(tc))
            rows.append(row)

        if not columns and rows:
            columns = [self._empty_table_cell() for _ in range(len(rows[0]))]

        if not rows:
            return None

        return _drop_none(
            {
                "type": "table",
                "fixed": False,
                "position": {"x": box.x, "y": box.y},
                "size": {"width": box.width, "height": box.height},
                "rotation": box.rotation or None,
                "columns": columns,
                "rows": rows,
                "minColumns": len(columns),
                "maxColumns": len(columns),
                "minRows": len(rows),
                "maxRows": len(rows),
            }
        )

    def _convert_table_cell(self, cell: ET.Element) -> dict[str, Any]:
        cell_pr = cell.find("a:tcPr", NS)
        text = self._text_body_plain_text(cell.find("a:txBody", NS))
        return _drop_none(
            {
                "fill": self._extract_fill(cell_pr),
                "stroke": self._extract_stroke(cell_pr),
                "text": text,
                "minLength": len(text) if text is not None else None,
                "maxLength": len(text) if text is not None else None,
            }
        )

    def _convert_chart(
        self,
        graphic_frame: ET.Element,
        rels: dict[str, dict[str, str | bool]],
        *,
        transform: Transform | None = None,
    ) -> dict[str, Any] | None:
        chart_ref = graphic_frame.find(".//c:chart", NS)
        if chart_ref is None:
            return None

        rel_id = chart_ref.get(f"{{{NS['r']}}}id")
        if not rel_id or rel_id not in rels:
            return None

        chart_path = str(rels[rel_id]["path"])
        chart_xml = self._read_xml(chart_path)
        if chart_xml is None:
            return None

        box = self._graphic_frame_box(graphic_frame, transform=transform)
        if box is None:
            return None

        chart_type = self._chart_type(chart_xml)
        data = self._chart_data(chart_xml)
        if chart_type is None or not data:
            return None

        return _drop_none(
            {
                "type": "chart",
                "fixed": False,
                "position": {"x": box.x, "y": box.y},
                "size": {"width": box.width, "height": box.height},
                "rotation": box.rotation or None,
                "chartType": chart_type,
                "data": data,
                "title": self._chart_title(chart_xml),
                "showValues": True,
            }
        )

    def _shape_box(
        self,
        shape: ET.Element,
        *,
        transform: Transform | None = None,
        placeholder_xfrms: dict[tuple[str, str | None], ET.Element] | None = None,
    ) -> Box | None:
        xfrm = self._shape_xfrm(shape)
        if xfrm is None and placeholder_xfrms:
            placeholder_key = self._placeholder_key(shape)
            if placeholder_key is not None:
                xfrm = placeholder_xfrms.get(placeholder_key)
                if xfrm is None:
                    xfrm = placeholder_xfrms.get((placeholder_key[0], None))
        if xfrm is None:
            return None

        return self._box_from_xfrm(xfrm, transform=transform)

    def _graphic_frame_box(
        self,
        graphic_frame: ET.Element,
        *,
        transform: Transform | None = None,
    ) -> Box | None:
        return self._box_from_xfrm(
            graphic_frame.find("p:xfrm", NS),
            transform=transform,
        )

    def _box_from_xfrm(
        self,
        xfrm: ET.Element | None,
        *,
        transform: Transform | None = None,
    ) -> Box | None:
        if xfrm is None:
            return None

        off = xfrm.find("a:off", NS)
        ext = xfrm.find("a:ext", NS)
        if off is None or ext is None:
            return None

        x = _emu_to_px(off.get("x"))
        y = _emu_to_px(off.get("y"))
        width = _emu_to_px(ext.get("cx"))
        height = _emu_to_px(ext.get("cy"))
        rotation = _rotation_degrees(xfrm.get("rot"))

        if transform is None:
            x *= self.scale_factor
            y *= self.scale_factor
            width *= self.scale_factor
            height *= self.scale_factor
        else:
            x = transform.offx + (x - transform.ch_offx) * transform.scale_x
            y = transform.offy + (y - transform.ch_offy) * transform.scale_y
            width *= transform.scale_x
            height *= transform.scale_y
            rotation += transform.rotation

        return Box(
            x=_round(x),
            y=_round(y),
            width=_round(width),
            height=_round(height),
            rotation=_round(rotation),
        )

    def _build_group_transform(
        self,
        group: ET.Element,
        parent_transform: Transform | None,
    ) -> Transform | None:
        grp_sp_pr = group.find("p:grpSpPr", NS)
        if grp_sp_pr is None:
            return parent_transform

        xfrm = grp_sp_pr.find("a:xfrm", NS)
        if xfrm is None:
            return parent_transform

        off = xfrm.find("a:off", NS)
        ext = xfrm.find("a:ext", NS)
        ch_off = xfrm.find("a:chOff", NS)
        ch_ext = xfrm.find("a:chExt", NS)
        if off is None or ext is None or ch_off is None or ch_ext is None:
            return parent_transform

        offx = _emu_to_px(off.get("x"))
        offy = _emu_to_px(off.get("y"))
        extx = _emu_to_px(ext.get("cx"))
        exty = _emu_to_px(ext.get("cy"))
        ch_offx = _emu_to_px(ch_off.get("x"))
        ch_offy = _emu_to_px(ch_off.get("y"))
        ch_extx = _emu_to_px(ch_ext.get("cx"))
        ch_exty = _emu_to_px(ch_ext.get("cy"))
        scale_x = extx / ch_extx if ch_extx else 1
        scale_y = exty / ch_exty if ch_exty else 1
        rotation = _rotation_degrees(xfrm.get("rot"))

        if parent_transform is None:
            return Transform(
                offx=offx * self.scale_factor,
                offy=offy * self.scale_factor,
                scale_x=scale_x * self.scale_factor,
                scale_y=scale_y * self.scale_factor,
                ch_offx=ch_offx,
                ch_offy=ch_offy,
                rotation=rotation,
            )

        return Transform(
            offx=parent_transform.offx
            + (offx - parent_transform.ch_offx) * parent_transform.scale_x,
            offy=parent_transform.offy
            + (offy - parent_transform.ch_offy) * parent_transform.scale_y,
            scale_x=scale_x * parent_transform.scale_x,
            scale_y=scale_y * parent_transform.scale_y,
            ch_offx=ch_offx,
            ch_offy=ch_offy,
            rotation=rotation + parent_transform.rotation,
        )

    def _build_placeholder_xfrm_map(
        self,
        layout_xml: ET.Element | None,
        master_xml: ET.Element | None,
    ) -> dict[tuple[str, str | None], ET.Element]:
        xfrms: dict[tuple[str, str | None], ET.Element] = {}
        for xml in (master_xml, layout_xml):
            if xml is None:
                continue
            for shape in xml.findall(".//p:spTree/*", NS):
                if _local_name(shape.tag) not in {"sp", "pic", "cxnSp"}:
                    continue

                key = self._placeholder_key(shape)
                xfrm = self._shape_xfrm(shape)
                if key is not None and xfrm is not None:
                    xfrms[key] = xfrm
                    if key[1] is not None:
                        xfrms.setdefault((key[0], None), xfrm)

        return xfrms

    def _shape_xfrm(self, shape: ET.Element) -> ET.Element | None:
        sp_pr = shape.find("p:spPr", NS)
        if sp_pr is not None:
            xfrm = sp_pr.find("a:xfrm", NS)
            if xfrm is not None:
                return xfrm
        return shape.find("p:xfrm", NS)

    def _shape_geometry(self, shape: ET.Element) -> str:
        tag = _local_name(shape.tag)
        if tag == "cxnSp":
            return "line"

        sp_pr = shape.find("p:spPr", NS)
        if sp_pr is None:
            return "rect"

        prst = sp_pr.find("a:prstGeom", NS)
        if prst is None:
            return "rect"

        geometry = prst.get("prst") or "rect"
        if geometry in {"straightConnector1", "straightConnector", "line"}:
            return "line"
        return geometry

    def _shape_image_url(
        self,
        shape: ET.Element,
        rels: dict[str, dict[str, str | bool]],
    ) -> str | None:
        tag = _local_name(shape.tag)
        if tag == "pic":
            search_root = shape.find("p:blipFill", NS)
        else:
            search_root = shape.find("p:spPr/a:blipFill", NS)

        return self._resolve_blip_asset(search_root, rels)

    def _resolve_blip_asset(
        self,
        search_root: ET.Element | None,
        rels: dict[str, dict[str, str | bool]],
    ) -> str | None:
        if search_root is None:
            return None

        blip = search_root.find(".//a:blip", NS)
        if blip is None:
            return None

        rel_id = blip.get(f"{{{NS['r']}}}embed") or blip.get(f"{{{NS['r']}}}link")
        if not rel_id or rel_id not in rels:
            return None

        rel = rels[rel_id]
        if rel.get("external"):
            return str(rel["path"])

        return self._save_asset(str(rel["path"]))

    def _save_asset(self, archive_path: str) -> str | None:
        if archive_path in self.asset_cache:
            return self.asset_cache[archive_path]

        try:
            data = self.archive.read(archive_path)
        except KeyError:
            return None

        digest = hashlib.sha1(data).hexdigest()[:12]
        source_name = Path(archive_path).name
        stem = _safe_filename(Path(source_name).stem) or "asset"
        suffix = Path(source_name).suffix
        if not suffix:
            suffix = mimetypes.guess_extension(_media_type_from_path(archive_path)) or ""

        self.assets_dir.mkdir(parents=True, exist_ok=True)
        asset_path = self.assets_dir / f"{stem}-{digest}{suffix}"
        if not asset_path.exists() or asset_path.read_bytes() != data:
            asset_path.write_bytes(data)

        url = asset_path.resolve().as_uri()
        self.asset_cache[archive_path] = url
        return url

    def _extract_fill(self, element: ET.Element | None) -> dict[str, Any] | None:
        if element is None:
            return None
        if element.find("a:noFill", NS) is not None:
            return None

        solid = element.find("a:solidFill", NS)
        if solid is None and _local_name(element.tag) == "solidFill":
            solid = element
        if solid is None:
            return None

        color, opacity = self._resolve_color(solid)
        if color is None:
            return None

        return _drop_none({"color": color, "opacity": opacity})

    def _extract_stroke(self, element: ET.Element | None) -> dict[str, Any] | None:
        if element is None:
            return None

        ln = element.find("a:ln", NS)
        if ln is None:
            return None
        if ln.find("a:noFill", NS) is not None:
            return None

        color, opacity = self._resolve_color(ln)
        if color is None:
            color = "#000000"

        width = _emu_to_px(ln.get("w")) * self.scale_factor
        if width <= 0:
            width = self.scale_factor

        dash_node = ln.find("a:prstDash", NS)
        dash_value = dash_node.get("val") if dash_node is not None else None
        dash = DASH_PATTERNS.get(dash_value or "")

        return _drop_none(
            {
                "color": color,
                "opacity": opacity,
                "width": _round(max(width, 1)),
                "dash": dash,
            }
        )

    def _extract_shadow(self, element: ET.Element | None) -> dict[str, Any] | None:
        if element is None:
            return None

        shadow = element.find(".//a:outerShdw", NS)
        if shadow is None:
            return None

        color, opacity = self._resolve_color(shadow)
        if color is None:
            color = "#000000"

        blur = _emu_to_px(shadow.get("blurRad")) * self.scale_factor
        distance = _emu_to_px(shadow.get("dist")) * self.scale_factor
        direction = int(shadow.get("dir", "0")) / 60000
        radians = math.radians(direction)

        return _drop_none(
            {
                "color": color,
                "blur": _round(blur) if blur else None,
                "opacity": opacity,
                "offsetX": _round(math.cos(radians) * distance) if distance else None,
                "offsetY": _round(math.sin(radians) * distance) if distance else None,
            }
        )

    def _resolve_color(self, element: ET.Element) -> tuple[str | None, float | None]:
        color_node: ET.Element | None = None
        for tag in ("srgbClr", "schemeClr", "prstClr", "sysClr"):
            color_node = element.find(f".//a:{tag}", NS)
            if color_node is not None:
                break

        if color_node is None:
            return None, None

        tag = _local_name(color_node.tag)
        if tag == "srgbClr":
            hex_color = color_node.get("val")
        elif tag == "schemeClr":
            hex_color = self._theme_color(color_node.get("val"))
        elif tag == "sysClr":
            hex_color = color_node.get("lastClr")
        else:
            hex_color = color_node.get("val")

        rgb = _hex_to_rgb(hex_color)
        if rgb is None:
            return None, None

        rgb = self._apply_color_modifiers(rgb, color_node)
        opacity = self._color_opacity(color_node)
        return f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}", opacity

    def _apply_color_modifiers(
        self,
        rgb: tuple[int, int, int],
        color_node: ET.Element,
    ) -> tuple[int, int, int]:
        r, g, b = rgb
        lum_mod = _percent_child_value(color_node, "lumMod")
        lum_off = _percent_child_value(color_node, "lumOff")
        tint = _percent_child_value(color_node, "tint")
        shade = _percent_child_value(color_node, "shade")

        if lum_mod is not None:
            r = r * lum_mod
            g = g * lum_mod
            b = b * lum_mod
        if lum_off is not None:
            r += 255 * lum_off
            g += 255 * lum_off
            b += 255 * lum_off
        if tint is not None:
            r += (255 - r) * tint
            g += (255 - g) * tint
            b += (255 - b) * tint
        if shade is not None:
            r *= shade
            g *= shade
            b *= shade

        return (_clamp_color(r), _clamp_color(g), _clamp_color(b))

    def _color_opacity(self, color_node: ET.Element) -> float | None:
        alpha = color_node.find("a:alpha", NS)
        if alpha is None:
            return None

        try:
            opacity = int(alpha.get("val", "100000")) / 100000
        except ValueError:
            return None

        return _round(opacity)

    def _theme_color(self, color_name: str | None) -> str | None:
        if color_name is None:
            return None
        theme_key = THEME_COLOR_ALIASES.get(color_name, color_name)
        return self.theme_colors.get(theme_key)

    def _font_from_run_properties(
        self,
        run_pr: ET.Element | None,
    ) -> dict[str, Any]:
        if run_pr is None:
            return {}

        font: dict[str, Any] = {}
        size = run_pr.get("sz")
        if size:
            try:
                point_size = int(size) / 100
                font["size"] = _round(point_size * 96 / 72 * self.scale_factor)
            except ValueError:
                pass

        latin = run_pr.find("a:latin", NS)
        if latin is not None and latin.get("typeface"):
            font["family"] = self._resolve_theme_font(latin.get("typeface") or "")

        color, _opacity = self._resolve_color(run_pr)
        if color is not None:
            font["color"] = color

        if run_pr.get("b") in {"1", "true"}:
            font["bold"] = True
        if run_pr.get("i") in {"1", "true"}:
            font["italic"] = True

        return font

    def _resolve_theme_font(self, typeface: str) -> str:
        if typeface.startswith("+mj"):
            return self.theme_fonts.get("major", typeface)
        if typeface.startswith("+mn"):
            return self.theme_fonts.get("minor", typeface)
        return typeface

    def _paragraph_alignment(self, p_pr: ET.Element | None) -> str | None:
        if p_pr is None:
            return None

        align = p_pr.get("algn")
        if align in {"ctr", "center"}:
            return "center"
        if align in {"r", "right"}:
            return "right"
        if align in {"l", "left"}:
            return "left"
        return None

    def _vertical_alignment(self, body_pr: ET.Element | None) -> str | None:
        if body_pr is None:
            return None

        anchor = body_pr.get("anchor")
        if anchor == "ctr":
            return "middle"
        if anchor == "b":
            return "bottom"
        if anchor == "t":
            return "top"
        return None

    def _text_body_plain_text(self, tx_body: ET.Element | None) -> str | None:
        if tx_body is None:
            return None

        paragraphs: list[str] = []
        for paragraph in tx_body.findall("a:p", NS):
            parts: list[str] = []
            for text_node in paragraph.findall(".//a:t", NS):
                if text_node.text:
                    parts.append(text_node.text)
            paragraphs.append("".join(parts))

        text = "\n".join(paragraphs).strip()
        return text or None

    def _chart_type(self, chart_xml: ET.Element) -> str | None:
        if chart_xml.find(".//c:barChart", NS) is not None:
            return "bar"
        if chart_xml.find(".//c:lineChart", NS) is not None:
            return "line"
        if chart_xml.find(".//c:doughnutChart", NS) is not None:
            return "donut"
        if chart_xml.find(".//c:pieChart", NS) is not None:
            return "donut"
        return None

    def _chart_title(self, chart_xml: ET.Element) -> str | None:
        title_parts = [
            text.text
            for text in chart_xml.findall(".//c:title//a:t", NS)
            if text.text
        ]
        title = "".join(title_parts).strip()
        return title or None

    def _chart_data(self, chart_xml: ET.Element) -> list[dict[str, Any]]:
        series = chart_xml.find(".//c:ser", NS)
        if series is None:
            return []

        labels = self._chart_labels(series)
        values = self._chart_values(series)
        data: list[dict[str, Any]] = []
        for index, value in enumerate(values):
            label = labels[index] if index < len(labels) else f"Value {index + 1}"
            data.append({"label": label, "value": value})

        return data

    def _chart_labels(self, series: ET.Element) -> list[str]:
        labels = [
            node.text
            for node in series.findall(".//c:cat//c:strCache//c:pt/c:v", NS)
            if node.text
        ]
        if labels:
            return labels

        return [
            node.text
            for node in series.findall(".//c:cat//c:numCache//c:pt/c:v", NS)
            if node.text
        ]

    def _chart_values(self, series: ET.Element) -> list[float]:
        values: list[float] = []
        for node in series.findall(".//c:val//c:numCache//c:pt/c:v", NS):
            if node.text is None:
                continue
            try:
                values.append(float(node.text))
            except ValueError:
                continue

        return values

    def _empty_table_cell(self) -> dict[str, Any]:
        return {}

    def _border_radius(self, geometry: str, box: Box) -> dict[str, float] | None:
        if geometry not in {"roundRect", "round2SameRect"}:
            return None

        radius = _round(min(box.width, box.height) * 0.15)
        return {"tl": radius, "tr": radius, "bl": radius, "br": radius}

    def _image_fit(self, shape: ET.Element) -> str:
        if shape.find(".//a:srcRect", NS) is not None:
            return "cover"
        return "fill"

    def _shape_has_text(self, shape: ET.Element) -> bool:
        return shape.find(".//p:txBody//a:t", NS) is not None

    def _shape_name(self, shape: ET.Element) -> str | None:
        for path in ("p:nvSpPr/p:cNvPr", "p:nvPicPr/p:cNvPr", "p:nvCxnSpPr/p:cNvPr"):
            node = shape.find(path, NS)
            if node is not None and node.get("name"):
                return node.get("name")
        return None

    def _is_placeholder(self, shape: ET.Element) -> bool:
        return shape.find(".//p:ph", NS) is not None

    def _placeholder_key(self, shape: ET.Element) -> tuple[str, str | None] | None:
        ph = shape.find(".//p:ph", NS)
        if ph is None:
            return None

        return (ph.get("type") or "body", ph.get("idx"))

    def _is_hidden(self, shape: ET.Element) -> bool:
        for path in ("p:nvSpPr/p:cNvPr", "p:nvPicPr/p:cNvPr", "p:nvCxnSpPr/p:cNvPr"):
            node = shape.find(path, NS)
            if node is not None and node.get("hidden") in {"1", "true"}:
                return True
        return False

    def _first_related_path(
        self,
        rels: dict[str, dict[str, str | bool]],
        type_fragment: str,
    ) -> str | None:
        for rel in rels.values():
            if type_fragment in str(rel.get("type", "")):
                return str(rel["path"])
        return None

    def _load_slide_size(self, presentation: ET.Element) -> None:
        slide_size = presentation.find("p:sldSz", NS)
        if slide_size is None:
            self.slide_width = DEFAULT_TARGET_WIDTH
            self.slide_height = DEFAULT_TARGET_WIDTH * 9 / 16
            self.scale_factor = 1.0
            return

        original_width = _emu_to_px(slide_size.get("cx"))
        original_height = _emu_to_px(slide_size.get("cy"))
        if original_width <= 0 or original_height <= 0:
            self.slide_width = DEFAULT_TARGET_WIDTH
            self.slide_height = DEFAULT_TARGET_WIDTH * 9 / 16
            self.scale_factor = 1.0
            return

        if self.target_width > 0:
            self.scale_factor = self.target_width / original_width
            self.slide_width = self.target_width
            self.slide_height = original_height * self.scale_factor
        else:
            self.scale_factor = 1.0
            self.slide_width = original_width
            self.slide_height = original_height

    def _load_theme(self) -> None:
        pres_rels = self._get_rels("ppt/presentation.xml")
        theme_path = self._first_related_path(pres_rels, "theme") or "ppt/theme/theme1.xml"
        theme_xml = self._read_xml(theme_path)
        if theme_xml is None:
            return

        for color_node in theme_xml.findall(".//a:clrScheme/*", NS):
            color_name = _local_name(color_node.tag)
            srgb = color_node.find("a:srgbClr", NS)
            sys_color = color_node.find("a:sysClr", NS)
            if srgb is not None and srgb.get("val"):
                self.theme_colors[color_name] = srgb.get("val") or ""
            elif sys_color is not None and sys_color.get("lastClr"):
                self.theme_colors[color_name] = sys_color.get("lastClr") or ""

        major = theme_xml.find(".//a:fontScheme/a:majorFont/a:latin", NS)
        minor = theme_xml.find(".//a:fontScheme/a:minorFont/a:latin", NS)
        if major is not None and major.get("typeface"):
            self.theme_fonts["major"] = major.get("typeface") or ""
        if minor is not None and minor.get("typeface"):
            self.theme_fonts["minor"] = minor.get("typeface") or ""

    def _read_xml(self, path: str | None) -> ET.Element | None:
        if not path:
            return None

        try:
            with self.archive.open(path) as file:
                return ET.fromstring(file.read())
        except (KeyError, ET.ParseError):
            return None

    def _get_rels(self, path: str | None) -> dict[str, dict[str, str | bool]]:
        if not path:
            return {}
        if path in self.rels_cache:
            return self.rels_cache[path]

        directory = posixpath.dirname(path)
        filename = posixpath.basename(path)
        rels_path = posixpath.join(directory, "_rels", f"{filename}.rels")
        rels: dict[str, dict[str, str | bool]] = {}

        try:
            with self.archive.open(rels_path) as file:
                root = ET.fromstring(file.read())
        except (KeyError, ET.ParseError):
            self.rels_cache[path] = rels
            return rels

        for rel in root.findall(f"{{{REL_NS}}}Relationship"):
            rel_id = rel.get("Id")
            target = rel.get("Target")
            if not rel_id or not target:
                continue

            is_external = rel.get("TargetMode") == "External"
            if not is_external:
                if target.startswith("/"):
                    target = target.lstrip("/")
                else:
                    target = posixpath.normpath(posixpath.join(directory, target))

            rels[rel_id] = {
                "path": target,
                "type": rel.get("Type") or "",
                "external": is_external,
            }

        self.rels_cache[path] = rels
        return rels


def _drop_none(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _drop_none(item)
            for key, item in value.items()
            if item is not None and item != {}
        }
    if isinstance(value, list):
        return [_drop_none(item) for item in value if item is not None]
    return value


def _merge_text_runs(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    for run in runs:
        text = run.get("text")
        if not text:
            continue

        font = run.get("font")
        if merged and merged[-1].get("font") == font:
            merged[-1]["text"] += text
            continue

        merged.append(_drop_none({"text": text, "font": font}))

    return merged


def _plain_text_length(runs: list[dict[str, Any]]) -> int:
    return len("".join(str(run.get("text", "")) for run in runs))


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _emu_to_px(value: str | None) -> float:
    if not value:
        return 0.0
    try:
        return float(value) * EMU_TO_PX
    except ValueError:
        return 0.0


def _rotation_degrees(value: str | None) -> float:
    if not value:
        return 0.0
    try:
        return float(value) / 60000
    except ValueError:
        return 0.0


def _round(value: float) -> float:
    rounded = round(value, 2)
    if abs(rounded) == 0:
        return 0
    return rounded


def _hex_to_rgb(value: str | None) -> tuple[int, int, int] | None:
    if not value:
        return None

    hex_value = value.strip().lstrip("#")
    if len(hex_value) == 3:
        hex_value = "".join(ch * 2 for ch in hex_value)
    if len(hex_value) != 6:
        return None

    try:
        return (
            int(hex_value[0:2], 16),
            int(hex_value[2:4], 16),
            int(hex_value[4:6], 16),
        )
    except ValueError:
        return None


def _clamp_color(value: float) -> int:
    return max(0, min(255, int(round(value))))


def _percent_child_value(element: ET.Element, tag_name: str) -> float | None:
    child = element.find(f"a:{tag_name}", NS)
    if child is None or child.get("val") is None:
        return None

    try:
        return int(child.get("val") or "0") / 100000
    except ValueError:
        return None


def _safe_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")


def _media_type_from_path(path: str) -> str:
    guessed, _encoding = mimetypes.guess_type(path)
    return guessed or "application/octet-stream"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Convert PPTX slides into JSON slide elements.",
    )
    parser.add_argument("pptx", help="Path to the PPTX file to convert.")
    parser.add_argument(
        "-o",
        "--output",
        help="Path to write JSON output. Defaults to stdout.",
    )
    parser.add_argument(
        "--assets-dir",
        help="Directory where embedded media assets will be saved.",
    )
    parser.add_argument(
        "--target-width",
        type=float,
        default=DEFAULT_TARGET_WIDTH,
        help="Slide width to scale coordinates to. Use 0 to keep PPTX pixel size.",
    )
    parser.add_argument(
        "--max-slides",
        type=int,
        help="Limit conversion to the first N slides.",
    )
    args = parser.parse_args(argv)

    data = convert_pptx_to_json(
        args.pptx,
        output_path=args.output,
        assets_dir=args.assets_dir,
        target_width=args.target_width,
        max_slides=args.max_slides,
    )
    if args.output is None:
        print(data.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
