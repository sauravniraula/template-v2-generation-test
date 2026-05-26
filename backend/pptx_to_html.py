import asyncio
import io
import os
import zipfile
import hashlib
import re
import math
import uuid
from typing import Dict, List, Optional, Set, Tuple
from lxml import etree

from presenton_backend.s3.service import S3_SERVICE


# --- Constants ---
EMU_TO_PX_FACTOR = 1 / 9525
PPT_NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "cx": "http://schemas.microsoft.com/office/drawing/2014/chartex",
}
CHART_NS = {
    "c": "http://schemas.openxmlformats.org/drawingml/2006/chart",
}
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
RECT_TOTAL_UNITS = 100000.0
FONT_STYLE_META = {
    "regular": {"weight": "400", "style": "normal"},
    "bold": {"weight": "700", "style": "normal"},
    "italic": {"weight": "400", "style": "italic"},
    "boldItalic": {"weight": "700", "style": "italic"},
}


def _write_text_file(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as file:
        file.write(content)


def emu_to_px(emu: str) -> float:
    if not emu:
        return 0
    return float(emu) * EMU_TO_PX_FACTOR


def round_dimension(value: float) -> float:
    """Round dimension to 1 decimal place."""
    return round(value, 1)


def get_tag_name(element) -> str:
    return etree.QName(element).localname


def _hex_to_rgb(hex_str: str) -> Tuple[int, int, int]:
    hex_str = hex_str.strip().lstrip("#")
    if len(hex_str) == 3:
        hex_str = "".join(ch * 2 for ch in hex_str)
    if len(hex_str) != 6:
        return (0, 0, 0)
    try:
        r = int(hex_str[0:2], 16)
        g = int(hex_str[2:4], 16)
        b = int(hex_str[4:6], 16)
    except ValueError:
        return (0, 0, 0)
    return (r, g, b)


class PPTXToHTML:
    def __init__(
        self,
        pptx_path: str,
        user: uuid.UUID,
        use_temporary_bucket: bool = False,
    ):
        self.pptx_path = pptx_path
        if not os.path.exists(pptx_path):
            raise FileNotFoundError(f"PPTX file not found: {pptx_path}")

        self.archive = zipfile.ZipFile(pptx_path, "r")
        self.theme_colors: Dict[str, str] = {}
        self.theme_fonts: Dict[str, str] = {}
        self.slides_data: List[dict] = []
        self.rels_cache: Dict[str, Dict] = {}
        self.width = 0
        self.height = 0
        self.scale_factor = 1.0
        self.target_width = 1280.0
        self.color_map: Dict[str, str] = {}
        self.default_text_color: Optional[str] = None

        # S3 configuration
        if use_temporary_bucket:
            bucket_path = S3_SERVICE.get_user_temporary_bucket_path(user)
        else:
            bucket_path = S3_SERVICE.get_user_public_bucket_path(user)
        if not bucket_path:
            raise ValueError("S3 bucket path is not configured correctly.")
        self.s3_prefix = f"{bucket_path}/xml-to-html"
        self.image_url_cache: Dict[
            str, str
        ] = {}  # Cache of image path -> presigned URL
        self.embedded_fonts: Dict[str, Dict[str, Dict[str, str]]] = {}
        self.font_asset_cache: Dict[str, Dict[str, str]] = {}
        self.font_css_name_cache: Dict[str, str] = {}
        self.current_slide_fonts: Optional[Set[str]] = None

    def close(self) -> None:
        self.archive.close()

    def _scale_and_round(self, value: float) -> float:
        """Scale a dimension by the scale factor and round to 1 decimal place."""
        return round_dimension(value * self.scale_factor)

    def _points_to_scaled_px(self, points: float) -> float:
        """Convert point units to scaled pixels."""
        pixels = points * 96.0 / 72.0
        return self._scale_and_round(pixels)

    def _read_xml(self, path: str):
        """Helper to read XML from zip safely."""
        try:
            with self.archive.open(path) as f:
                return etree.fromstring(f.read())
        except KeyError:
            print(f"Warning: Could not find file in archive: {path}")
            return None
        except Exception as e:
            print(f"Error reading {path}: {e}")
            return None

    def _get_rels(self, path: str) -> Dict[str, dict]:
        """
        Parses .rels file for a specific XML file.
        Returns dict: { 'rId1': {'path': 'ppt/slides/slide1.xml', 'type': '...'}, ... }
        """
        if path in self.rels_cache:
            return self.rels_cache[path]

        dir_name = os.path.dirname(path)
        filename = os.path.basename(path)
        rels_path = os.path.join(dir_name, "_rels", f"{filename}.rels").replace(
            "\\", "/"
        )

        rels_data = {}
        xml = self._read_xml(rels_path)

        if xml is not None:
            # The namespace for Relationships is usually default or specific
            for rel in xml.findall(f"{{{REL_NS}}}Relationship"):
                r_id = rel.get("Id")
                r_type = rel.get("Type")
                target = rel.get("Target")

                # Resolve relative paths
                if not target.startswith("/"):
                    target = os.path.normpath(os.path.join(dir_name, target)).replace(
                        "\\", "/"
                    )
                elif target.startswith("/"):
                    target = target[1:]  # Strip leading slash for zip lookup

                rels_data[r_id] = {"path": target, "type": r_type}

        self.rels_cache[path] = rels_data
        return rels_data

    def _load_theme(self):
        """Attempts to find and load the theme color scheme."""
        # 1. Check presentation relationships for theme
        pres_rels = self._get_rels("ppt/presentation.xml")
        theme_path = None
        for r in pres_rels.values():
            if "theme" in r["type"]:
                theme_path = r["path"]
                break

        if not theme_path:
            # Fallback
            theme_path = "ppt/theme/theme1.xml"

        theme_xml = self._read_xml(theme_path)
        if theme_xml is None:
            return

        clr_scheme = theme_xml.find(".//a:clrScheme", PPT_NS)
        if clr_scheme is None:
            return

        for child in clr_scheme:
            name = get_tag_name(child)
            srgb = child.find("a:srgbClr", PPT_NS)
            sys = child.find("a:sysClr", PPT_NS)

            if srgb is not None:
                self.theme_colors[name] = srgb.get("val")
            elif sys is not None:
                self.theme_colors[name] = sys.get("lastClr") or "FFFFFF"

        font_scheme = theme_xml.find(".//a:fontScheme", PPT_NS)
        if font_scheme is not None:
            major = font_scheme.find("a:majorFont/a:latin", PPT_NS)
            minor = font_scheme.find("a:minorFont/a:latin", PPT_NS)
            if major is not None and major.get("typeface"):
                self.theme_fonts["major"] = major.get("typeface")
            if minor is not None and minor.get("typeface"):
                self.theme_fonts["minor"] = minor.get("typeface")

    def _resolve_theme_typeface(self, typeface: str) -> str:
        """Resolve theme shorthand like +mj-lt/+mn-lt to actual typefaces."""
        if not typeface:
            return typeface
        if typeface.startswith("+mj"):
            return self.theme_fonts.get("major", typeface)
        if typeface.startswith("+mn"):
            return self.theme_fonts.get("minor", typeface)
        return typeface

    def _resolve_color(self, element, default="transparent") -> str:
        """Resolves color from XML element (solidFill, schemeClr, etc)."""
        if element is None:
            return default

        solid_fill = element.find("a:solidFill", PPT_NS)
        if solid_fill is None:
            # Sometimes color is direct child (like in text runs)
            if get_tag_name(element) == "solidFill":
                solid_fill = element

        if solid_fill is not None:
            srgb = solid_fill.find("a:srgbClr", PPT_NS)
            if srgb is not None:
                hex_val = srgb.get("val")
                if not hex_val:
                    return default
                r, g, b = _hex_to_rgb(hex_val)
                r, g, b = self._apply_color_modifiers(r, g, b, srgb)
                alpha = 1.0
                alpha_elem = srgb.find("a:alpha", PPT_NS)
                if alpha_elem is not None:
                    try:
                        alpha = float(alpha_elem.get("val", "100000")) / 100000.0
                    except (TypeError, ValueError):
                        alpha = 1.0
                if alpha <= 0:
                    return "transparent"
                if alpha >= 0.999:
                    return f"#{int(r):02X}{int(g):02X}{int(b):02X}"
                alpha = round(alpha, 3)
                return f"rgba({r},{g},{b},{alpha})"

            scheme = solid_fill.find("a:schemeClr", PPT_NS)
            if scheme is not None:
                val = scheme.get("val")
                if not val:
                    return default
                if val in self.color_map:
                    val = self.color_map[val]
                color_hex = self.theme_colors.get(val, "000000")
                r, g, b = _hex_to_rgb(color_hex)
                r, g, b = self._apply_color_modifiers(r, g, b, scheme)
                alpha = 1.0
                alpha_elem = scheme.find("a:alpha", PPT_NS)
                if alpha_elem is not None:
                    try:
                        alpha = float(alpha_elem.get("val", "100000")) / 100000.0
                    except (TypeError, ValueError):
                        alpha = 1.0
                if alpha <= 0:
                    return "transparent"
                if alpha >= 0.999:
                    return f"#{int(r):02X}{int(g):02X}{int(b):02X}"
                alpha = round(alpha, 3)
                return f"rgba({r},{g},{b},{alpha})"

        return default

    def _apply_color_modifiers(
        self, r: int, g: int, b: int, color_elem
    ) -> Tuple[int, int, int]:
        """Apply tint/shade/lumMod/lumOff adjustments to an RGB tuple."""

        def _clamp(value: float) -> int:
            return max(0, min(255, int(round(value))))

        shade_elem = color_elem.find("a:shade", PPT_NS)
        tint_elem = color_elem.find("a:tint", PPT_NS)
        lum_mod_elem = color_elem.find("a:lumMod", PPT_NS)
        lum_off_elem = color_elem.find("a:lumOff", PPT_NS)

        if shade_elem is not None and shade_elem.get("val"):
            try:
                factor = float(shade_elem.get("val")) / 100000.0
                r, g, b = r * factor, g * factor, b * factor
            except (TypeError, ValueError):
                pass

        if tint_elem is not None and tint_elem.get("val"):
            try:
                factor = float(tint_elem.get("val")) / 100000.0
                r = r + (255 - r) * factor
                g = g + (255 - g) * factor
                b = b + (255 - b) * factor
            except (TypeError, ValueError):
                pass

        if lum_mod_elem is not None and lum_mod_elem.get("val"):
            try:
                factor = float(lum_mod_elem.get("val")) / 100000.0
                r, g, b = r * factor, g * factor, b * factor
            except (TypeError, ValueError):
                pass

        if lum_off_elem is not None and lum_off_elem.get("val"):
            try:
                offset = float(lum_off_elem.get("val")) / 100000.0 * 255.0
                r, g, b = r + offset, g + offset, b + offset
            except (TypeError, ValueError):
                pass

        return _clamp(r), _clamp(g), _clamp(b)

    def _load_color_map(self, master_xml) -> Dict[str, str]:
        """Load color map from slide master (bg1/tx1 -> lt1/dk1)."""
        if master_xml is None:
            return {}
        clr_map = master_xml.find("p:clrMap", PPT_NS)
        if clr_map is None:
            return {}
        return {k: v for k, v in clr_map.attrib.items() if v}

    async def _extract_background_info(
        self, bg_elem, rels: Optional[Dict[str, dict]] = None
    ) -> Tuple[Optional[str], str]:
        """
        Returns the resolved background color and inline style snippet for images.

        Args:
            bg_elem: XML element pointing to <p:bg> or similar.
            rels: Relationship dict (from _get_rels) so we can resolve embedded images.
        """
        if bg_elem is None:
            return None, ""

        rels = rels or {}
        bg_pr = bg_elem.find("p:bgPr", PPT_NS)
        if bg_pr is None:
            return None, ""

        color = self._resolve_color(bg_pr, default=None)
        if color == "transparent":
            color = None

        image_style_parts = []
        blip_fill = bg_pr.find("a:blipFill", PPT_NS)
        if blip_fill is not None:
            blip = blip_fill.find("a:blip", PPT_NS)
            if blip is not None:
                embed_id = blip.get(f"{{{PPT_NS['r']}}}embed")
                if embed_id and embed_id in rels:
                    img_path = rels[embed_id]["path"]
                    img_url = await self._get_image_url(img_path)
                    image_style_parts.append(f"background-image: url('{img_url}');")
                    position = self._calculate_object_position(blip_fill)
                    if position:
                        image_style_parts.append(f"background-position: {position};")
                    image_style_parts.append("background-size: cover;")
                    image_style_parts.append("background-repeat: no-repeat;")

        return color, " ".join(image_style_parts).strip()

    def _load_embedded_fonts(self, presentation, pres_rels):
        """Collect embedded fonts and their relationship targets."""
        embedded_list = presentation.find("p:embeddedFontLst", PPT_NS)
        if embedded_list is None:
            return

        for embedded in embedded_list.findall("p:embeddedFont", PPT_NS):
            font_elem = embedded.find("p:font", PPT_NS)
            if font_elem is None:
                continue

            typeface = font_elem.get("typeface")
            if not typeface:
                continue

            style_map: Dict[str, Dict[str, str]] = {}
            for tag_name, style_key in (
                ("p:regular", "regular"),
                ("p:bold", "bold"),
                ("p:italic", "italic"),
                ("p:boldItalic", "boldItalic"),
            ):
                style_elem = embedded.find(tag_name, PPT_NS)
                if style_elem is None:
                    continue
                r_id = style_elem.get(f"{{{PPT_NS['r']}}}id")
                if not r_id:
                    continue
                rel_info = pres_rels.get(r_id)
                if not rel_info:
                    continue
                style_map[style_key] = {"path": rel_info["path"], "rid": r_id}

            if style_map:
                self.embedded_fonts[typeface] = style_map

    def _register_font_usage(self, typeface: Optional[str]):
        """Track fonts used on the current slide for later CSS generation."""
        if not typeface or self.current_slide_fonts is None:
            return
        self.current_slide_fonts.add(typeface)

    @staticmethod
    def _sanitize_font_name(typeface: str) -> str:
        """Return a CSS-safe font-family name by replacing whitespace with underscores."""
        return re.sub(r"\s+", "_", typeface.strip())

    def _get_css_font_name(self, typeface: str) -> str:
        if typeface not in self.font_css_name_cache:
            self.font_css_name_cache[typeface] = self._sanitize_font_name(typeface)
        return self.font_css_name_cache[typeface]

    def _format_font_class(self, typeface: str) -> str:
        css_name = self._get_css_font_name(typeface)
        return f"font-['{css_name}']"

    def get_font_and_image_urls(self) -> Dict[str, List[Dict[str, str]]]:
        """
        Return the cached presigned URLs collected during parsing.
        """
        images = [
            {"path": path, "url": url} for path, url in self.image_url_cache.items()
        ]
        fonts = [
            {"path": path, "url": meta["url"], "format": meta["format"]}
            for path, meta in self.font_asset_cache.items()
        ]
        return {"images": images, "fonts": fonts}

    async def _upload_image_to_s3(self, image_path: str) -> Optional[str]:
        """
        Upload an image from the PPTX archive to S3 and return a presigned URL.

        Args:
            image_path: Path to the image file within the PPTX archive (e.g., "ppt/media/image1.jpeg")

        Returns:
            Presigned URL string if successful, None otherwise
        """
        if not self.s3_prefix:
            return None

        try:
            # Read image from archive
            try:
                image_data = self.archive.read(image_path)
            except KeyError:
                print(f"Warning: Image not found in archive: {image_path}")
                return None

            # Generate a unique S3 key based on image content hash
            image_hash = hashlib.md5(image_data).hexdigest()
            file_ext = os.path.splitext(image_path)[1] or ".jpg"
            s3_key = f"{self.s3_prefix}/{image_hash}{file_ext}"

            # Upload to S3
            payload = io.BytesIO(image_data)
            await S3_SERVICE.upload_file(s3_key, payload)
            presigned_url = await S3_SERVICE.get_public_or_presigned_url(s3_key)

            return presigned_url

        except Exception as e:
            print(f"Error uploading image to S3: {e}")
            return None

    def _detect_font_format(
        self, font_data: bytes, font_path: str
    ) -> Tuple[str, str, str]:
        """Best-effort detection of the font format for uploads and CSS."""
        lower_path = font_path.lower()
        header = font_data[:4]

        if lower_path.endswith(".woff2") or header.startswith(b"wOF2"):
            return ".woff2", "font/woff2", "woff2"
        if lower_path.endswith(".woff") or header.startswith(b"wOFF"):
            return ".woff", "font/woff", "woff"
        if lower_path.endswith(".otf") or header == b"OTTO":
            return ".otf", "font/otf", "opentype"
        if lower_path.endswith(".ttf") or header in (
            b"\x00\x01\x00\x00",
            b"true",
            b"typ1",
        ):
            return ".ttf", "font/ttf", "truetype"
        if lower_path.endswith(".fntdata") or lower_path.endswith(".eot"):
            return ".eot", "application/vnd.ms-fontobject", "embedded-opentype"

        # Fallback to TrueType if unsure
        return ".ttf", "font/ttf", "truetype"

    def _extract_sfnt_from_eot(
        self, font_data: bytes
    ) -> Optional[Tuple[bytes, str, str, str]]:
        """Attempt to strip the EOT wrapper and return raw TTF/OTF bytes."""
        if len(font_data) < 12:
            return None

        font_data_size = int.from_bytes(font_data[4:8], "little", signed=False)
        if font_data_size <= 0 or font_data_size > len(font_data):
            return None

        sfnt_bytes = font_data[-font_data_size:]
        signature = sfnt_bytes[:4]
        signature_map = {
            b"\x00\x01\x00\x00": (".ttf", "font/ttf", "truetype"),
            b"true": (".ttf", "font/ttf", "truetype"),
            b"typ1": (".ttf", "font/ttf", "truetype"),
            b"OTTO": (".otf", "font/otf", "opentype"),
        }

        if signature not in signature_map:
            return None

        ext, content_type, css_format = signature_map[signature]
        return sfnt_bytes, ext, content_type, css_format

    def _prepare_font_payload(
        self, font_path: str, raw_font_data: bytes
    ) -> Optional[Tuple[bytes, str, str, str]]:
        """
        Convert embedded fonts to modern formats when needed and determine upload metadata.
        Returns tuple: (font_bytes, ext, content_type, css_format)
        """
        ext, content_type, css_format = self._detect_font_format(
            raw_font_data, font_path
        )

        if ext == ".eot":
            converted = self._extract_sfnt_from_eot(raw_font_data)
            if converted is None:
                print(
                    f"Warning: Could not convert legacy font {font_path} to a modern format."
                )
                return None
            raw_font_data, ext, content_type, css_format = converted

        return raw_font_data, ext, content_type, css_format

    async def _upload_font_to_s3(self, font_path: str) -> Optional[Dict[str, str]]:
        """Upload an embedded font to S3 and return metadata needed for CSS."""
        if font_path in self.font_asset_cache:
            return self.font_asset_cache[font_path]

        if not self.s3_prefix:
            return None

        try:
            raw_font = self.archive.read(font_path)
        except KeyError:
            print(f"Warning: Font not found in archive: {font_path}")
            return None
        except Exception as exc:
            print(f"Unexpected error reading font {font_path}: {exc}")
            return None

        prepared = self._prepare_font_payload(font_path, raw_font)
        if prepared is None:
            return None
        font_bytes, ext, _, font_format = prepared

        font_hash = hashlib.md5(font_bytes).hexdigest()
        s3_key = f"{self.s3_prefix}/fonts/{font_hash}{ext}"

        try:
            payload = io.BytesIO(font_bytes)
            await S3_SERVICE.upload_file(s3_key, payload)
            presigned_url = await S3_SERVICE.get_public_or_presigned_url(s3_key)
            asset = {"url": presigned_url, "format": font_format}
            self.font_asset_cache[font_path] = asset
            return asset
        except Exception as exc:
            print(f"Unexpected error uploading font {font_path}: {exc}")
            return None

    async def _get_font_face_definitions(self, font_name: str) -> List[Dict[str, str]]:
        """Return @font-face definition info for a particular typeface."""
        font_entries = self.embedded_fonts.get(font_name)
        if not font_entries:
            return []

        definitions: List[Dict[str, str]] = []
        for style_key, meta in font_entries.items():
            font_meta = await self._upload_font_to_s3(meta["path"])
            if not font_meta:
                continue

            style_info = FONT_STYLE_META.get(style_key, FONT_STYLE_META["regular"])
            definitions.append(
                {
                    "family": font_name,
                    "weight": style_info["weight"],
                    "style": style_info["style"],
                    "url": font_meta["url"],
                    "format": font_meta["format"],
                }
            )
        return definitions

    async def _build_font_face_css(self, font_names: List[str]) -> str:
        """Generate @font-face CSS blocks for all fonts used on a slide."""
        css_rules = []
        for font_name in font_names:
            definitions = await self._get_font_face_definitions(font_name)
            for definition in definitions:
                family = font_name.replace("'", "\\'")
                css_rules.append(
                    "@font-face {{ font-family: '{family}'; font-weight: {weight}; "
                    "font-style: {style}; font-display: swap; src: url('{url}') format('{fmt}'); }}".format(
                        family=family,
                        weight=definition["weight"],
                        style=definition["style"],
                        url=definition["url"],
                        fmt=definition["format"],
                    )
                )
        if not css_rules:
            return ""
        return f"<style>{''.join(css_rules)}</style>"

    async def _get_image_url(self, path: str) -> str:
        """
        Get image URL - either from S3 (presigned URL) or placeholder.

        Args:
            path: Path to the image file within the PPTX archive

        Returns:
            Image URL (presigned S3 URL or placeholder)
        """
        # Check cache first
        if path in self.image_url_cache:
            return self.image_url_cache[path]

        # Try to upload to S3 and get presigned URL
        if self.s3_prefix:
            presigned_url = await self._upload_image_to_s3(path)
            if presigned_url:
                self.image_url_cache[path] = presigned_url
                return presigned_url

        # Fallback to placeholder
        placeholder_url = (
            "https://images.pexels.com/photos/2387793/pexels-photo-2387793.jpeg"
        )
        self.image_url_cache[path] = placeholder_url
        return placeholder_url

    # --- Renderers ---

    def _extract_line_spacing_style(
        self, p_pr, default_pprs: Optional[List[etree._Element]] = None
    ) -> Optional[str]:
        lnSpc = p_pr.find("a:lnSpc", PPT_NS) if p_pr is not None else None
        if lnSpc is None:
            if default_pprs:
                for default_ppr in default_pprs:
                    lnSpc = default_ppr.find("a:lnSpc", PPT_NS)
                    if lnSpc is not None:
                        break
            if lnSpc is None:
                return None

        spcPts = lnSpc.find("a:spcPts", PPT_NS)
        if spcPts is not None and spcPts.get("val"):
            try:
                raw_value = float(spcPts.get("val"))
                points = raw_value / 100.0
                pixels = points * 96.0 / 72.0
                line_height_px = self._scale_and_round(pixels)
                return f"line-height: {line_height_px}px;"
            except (TypeError, ValueError):
                return None

        spcPct = lnSpc.find("a:spcPct", PPT_NS)
        if spcPct is not None and spcPct.get("val"):
            try:
                percent = float(spcPct.get("val")) / 1000.0
                ratio = round(percent / 100.0, 3)
                if ratio <= 0:
                    return None
                ratio_str = f"{ratio:.3f}".rstrip("0").rstrip(".")
                return f"line-height: {ratio_str};"
            except (TypeError, ValueError):
                return None

        return None

    def _extract_paragraph_spacing_styles(
        self, p_pr, default_pprs: Optional[List[etree._Element]] = None
    ) -> List[str]:
        def _find_spacing(tag_name: str) -> Optional[etree._Element]:
            spacing = p_pr.find(tag_name, PPT_NS) if p_pr is not None else None
            if spacing is None and default_pprs:
                for default_ppr in default_pprs:
                    spacing = default_ppr.find(tag_name, PPT_NS)
                    if spacing is not None:
                        break
            return spacing

        styles: List[str] = []
        for tag_name, css_prop in (
            ("a:spcBef", "margin-top"),
            ("a:spcAft", "margin-bottom"),
        ):
            spacing = _find_spacing(tag_name)
            if spacing is None:
                continue
            spcPts = spacing.find("a:spcPts", PPT_NS)
            if spcPts is not None and spcPts.get("val"):
                try:
                    raw_value = float(spcPts.get("val"))
                    points = raw_value / 100.0
                    pixels = points * 96.0 / 72.0
                    spacing_px = self._scale_and_round(pixels)
                    styles.append(f"{css_prop}: {spacing_px}px;")
                except (TypeError, ValueError):
                    continue
            spcPct = spacing.find("a:spcPct", PPT_NS)
            if spcPct is not None and spcPct.get("val"):
                try:
                    ratio = float(spcPct.get("val")) / 100000.0
                    if ratio > 0:
                        ratio_str = f"{ratio:.3f}".rstrip("0").rstrip(".")
                        styles.append(f"{css_prop}: {ratio_str}em;")
                except (TypeError, ValueError):
                    continue
        return styles

    def _extract_body_padding_style(
        self, body_pr, fallback_body_pr: Optional[etree._Element] = None
    ) -> Optional[str]:
        if body_pr is None and fallback_body_pr is None:
            return None

        def _get_inset(attr_name: str) -> Optional[float]:
            value = None
            if body_pr is not None:
                value = body_pr.get(attr_name)
            if value is None and fallback_body_pr is not None:
                value = fallback_body_pr.get(attr_name)
            if not value:
                return None
            try:
                return self._scale_and_round(emu_to_px(value))
            except (TypeError, ValueError):
                return None

        padding_left = _get_inset("lIns")
        padding_right = _get_inset("rIns")
        padding_top = _get_inset("tIns")
        padding_bottom = _get_inset("bIns")

        style_parts = []
        if padding_left is not None:
            style_parts.append(f"padding-left: {padding_left}px;")
        if padding_right is not None:
            style_parts.append(f"padding-right: {padding_right}px;")
        if padding_top is not None:
            style_parts.append(f"padding-top: {padding_top}px;")
        if padding_bottom is not None:
            style_parts.append(f"padding-bottom: {padding_bottom}px;")

        return " ".join(style_parts) if style_parts else None

    def _get_line_dasharray(
        self, ln: Optional[etree._Element], stroke_width_px: float
    ) -> Optional[str]:
        if ln is None:
            return None
        prst_dash = ln.find("a:prstDash", PPT_NS)
        if prst_dash is None:
            return None
        val = prst_dash.get("val")
        if not val or val == "solid":
            return None
        dash_map = {
            "sysDash": [4, 2],
            "sysDot": [1, 2],
            "sysDashDot": [4, 2, 1, 2],
            "sysDashDotDot": [4, 2, 1, 2, 1, 2],
            "dash": [4, 2],
            "dot": [1, 2],
            "dashDot": [4, 2, 1, 2],
            "lgDash": [8, 4],
            "lgDashDot": [8, 4, 1, 4],
            "lgDashDotDot": [8, 4, 1, 4, 1, 4],
        }
        pattern = dash_map.get(val)
        if not pattern:
            return None
        scale = max(stroke_width_px, 1.0)
        scaled = [round_dimension(step * scale) for step in pattern]
        return " ".join(str(step) for step in scaled)

    def _get_linecap(self, ln: Optional[etree._Element]) -> Optional[str]:
        if ln is None:
            return None
        if ln.get("cap") == "rnd" or ln.find("a:round", PPT_NS) is not None:
            return "round"
        return None

    def _extract_letter_spacing_style(self, r_pr) -> Optional[str]:
        if r_pr is None:
            return None
        spc = r_pr.get("spc")
        if not spc:
            return None
        try:
            raw_value = float(spc)
        except ValueError:
            return None

        letter_px = round_dimension((raw_value * self.scale_factor) / 100.0)
        if letter_px == 0:
            return None
        return f"letter-spacing: {letter_px}px;"

    def _render_text_body(
        self,
        txBody,
        placeholder_text_styles: Optional[
            Dict[Tuple[str, Optional[str]], Dict[int, List[etree._Element]]]
        ] = None,
        placeholder_paragraph_styles: Optional[
            Dict[Tuple[str, Optional[str]], Dict[int, List[etree._Element]]]
        ] = None,
        placeholder_key: Optional[Tuple[str, Optional[str]]] = None,
    ) -> str:
        if txBody is None:
            return ""
        html_paras = []

        def _get_default_rpr(p_pr) -> List[etree._Element]:
            if not placeholder_text_styles or not placeholder_key:
                return []
            lvl = 0
            if p_pr is not None and p_pr.get("lvl"):
                try:
                    lvl = int(p_pr.get("lvl"))
                except ValueError:
                    lvl = 0
            style_map = placeholder_text_styles.get(placeholder_key)
            if style_map is None and placeholder_key[0]:
                style_map = placeholder_text_styles.get((placeholder_key[0], None))
            if not style_map:
                return []
            return style_map.get(lvl, [])

        def _get_default_ppr(p_pr) -> List[etree._Element]:
            if not placeholder_paragraph_styles or not placeholder_key:
                return []
            lvl = 0
            if p_pr is not None and p_pr.get("lvl"):
                try:
                    lvl = int(p_pr.get("lvl"))
                except ValueError:
                    lvl = 0
            style_map = placeholder_paragraph_styles.get(placeholder_key)
            if style_map is None and placeholder_key[0]:
                style_map = placeholder_paragraph_styles.get((placeholder_key[0], None))
            if not style_map:
                return []
            return style_map.get(lvl, [])

        def _get_lvl(p_pr) -> int:
            if p_pr is not None and p_pr.get("lvl"):
                try:
                    return int(p_pr.get("lvl"))
                except ValueError:
                    return 0
            return 0

        def _first_ppr_child(tag_name: str, p_pr, default_pprs):
            if p_pr is not None:
                node = p_pr.find(tag_name, PPT_NS)
                if node is not None:
                    return node
            if default_pprs:
                for default_ppr in default_pprs:
                    node = default_ppr.find(tag_name, PPT_NS)
                    if node is not None:
                        return node
            return None

        def _first_ppr_attr(attr_name: str, p_pr, default_pprs) -> Optional[str]:
            if p_pr is not None and p_pr.get(attr_name) is not None:
                return p_pr.get(attr_name)
            if default_pprs:
                for default_ppr in default_pprs:
                    if default_ppr.get(attr_name) is not None:
                        return default_ppr.get(attr_name)
            return None

        def _resolve_bullet(p_pr, default_pprs) -> Optional[str]:
            if _first_ppr_child("a:buNone", p_pr, default_pprs) is not None:
                return None
            bu_char = _first_ppr_child("a:buChar", p_pr, default_pprs)
            if bu_char is not None and bu_char.get("char"):
                return bu_char.get("char")
            if _first_ppr_child("a:buAutoNum", p_pr, default_pprs) is not None:
                return "•"
            return None

        for p in txBody.findall("a:p", PPT_NS):
            p_pr = p.find("a:pPr", PPT_NS)
            default_pprs = _get_default_ppr(p_pr)
            align_class = "text-left"
            align_val = p_pr.get("algn") if p_pr is not None else None
            if not align_val and default_pprs:
                for default_ppr in default_pprs:
                    if default_ppr.get("algn"):
                        align_val = default_ppr.get("algn")
                        break
            if align_val:
                align_class = {
                    "ctr": "text-center",
                    "r": "text-right",
                    "j": "text-justify",
                }.get(align_val, "text-left")

            para_styles = []
            line_style = self._extract_line_spacing_style(p_pr, default_pprs)
            if line_style:
                para_styles.append(line_style)
            para_styles.extend(
                self._extract_paragraph_spacing_styles(p_pr, default_pprs)
            )
            lvl = _get_lvl(p_pr)
            mar_l = _first_ppr_attr("marL", p_pr, default_pprs)
            indent = _first_ppr_attr("indent", p_pr, default_pprs)
            if mar_l:
                try:
                    mar_l_px = self._scale_and_round(emu_to_px(mar_l))
                    para_styles.append(f"margin-left: {mar_l_px}px;")
                except (TypeError, ValueError):
                    pass
            elif lvl > 0:
                indent_px = round_dimension(24.0 * lvl * self.scale_factor)
                para_styles.append(f"margin-left: {indent_px}px;")
            if indent:
                try:
                    indent_px = self._scale_and_round(emu_to_px(indent))
                    if indent_px != 0:
                        para_styles.append(f"text-indent: {indent_px}px;")
                except (TypeError, ValueError):
                    pass

            spans = []
            bullet_char = _resolve_bullet(p_pr, default_pprs)
            default_rprs = _get_default_rpr(p_pr)
            first_text_styles = None
            has_text = False

            def _resolve_run_styles(r_pr):
                classes = []
                span_styles = []
                if r_pr is not None or default_rprs:

                    def _first_attr(attr_name: str) -> Optional[str]:
                        if r_pr is not None and r_pr.get(attr_name) is not None:
                            return r_pr.get(attr_name)
                        for default_rpr in default_rprs:
                            if default_rpr.get(attr_name) is not None:
                                return default_rpr.get(attr_name)
                        return None

                    def _first_color() -> Optional[str]:
                        if r_pr is not None:
                            color_val = self._resolve_color(r_pr, default=None)
                            if color_val:
                                return color_val
                        for default_rpr in default_rprs:
                            color_val = self._resolve_color(default_rpr, default=None)
                            if color_val:
                                return color_val
                        if self.default_text_color:
                            return self.default_text_color
                        return None

                    def _first_latin() -> Optional[etree._Element]:
                        if r_pr is not None:
                            latin_elem = r_pr.find("a:latin", PPT_NS)
                            if latin_elem is not None:
                                return latin_elem
                        for default_rpr in default_rprs:
                            latin_elem = default_rpr.find("a:latin", PPT_NS)
                            if latin_elem is not None:
                                return latin_elem
                        return None

                    def _first_letter_spacing() -> Optional[str]:
                        if r_pr is not None:
                            letter_style = self._extract_letter_spacing_style(r_pr)
                            if letter_style:
                                return letter_style
                        for default_rpr in default_rprs:
                            letter_style = self._extract_letter_spacing_style(
                                default_rpr
                            )
                            if letter_style:
                                return letter_style
                        return None

                    # Size
                    sz = _first_attr("sz")
                    if sz:
                        # PowerPoint font size: sz is in hundredths of a point
                        points = int(sz) / 100.0
                        pixels = points * 96.0 / 72.0
                        scaled_pixels = pixels * self.scale_factor
                        classes.append(f"text-[{round_dimension(scaled_pixels)}px]")

                    # Bold/Italic/Underline
                    bold_val = _first_attr("b")
                    if bold_val in ("1", "true"):
                        classes.append("font-bold")
                    italic_val = _first_attr("i")
                    if italic_val in ("1", "true"):
                        classes.append("italic")
                    underline_val = _first_attr("u")
                    if underline_val == "sng":
                        classes.append("underline")

                    # Color
                    color = _first_color()
                    if color:
                        classes.append(f"text-[{color}]")

                    # Font family (latin)
                    latin = _first_latin()
                    if latin is not None:
                        typeface = self._resolve_theme_typeface(latin.get("typeface"))
                        if typeface:
                            self._register_font_usage(typeface)
                            classes.append(self._format_font_class(typeface))

                    # Letter spacing
                    letter_style = _first_letter_spacing()
                    if letter_style:
                        span_styles.append(letter_style)

                return classes, span_styles

            def _append_run(run):
                nonlocal first_text_styles, has_text
                t_node = run.find("a:t", PPT_NS)
                if t_node is None or not t_node.text:
                    return

                r_pr = run.find("a:rPr", PPT_NS)
                classes, span_styles = _resolve_run_styles(r_pr)
                if first_text_styles is None:
                    first_text_styles = (classes, span_styles)
                has_text = True

                style_attr = f' style="{" ".join(span_styles)}"' if span_styles else ""
                spans.append(
                    f'<span class="{" ".join(classes)}"{style_attr}>{t_node.text}</span>'
                )

            children = list(p)
            last_text_idx = -1
            for idx, child in enumerate(children):
                if child.tag != f"{{{PPT_NS['a']}}}r":
                    continue
                t_node = child.find("a:t", PPT_NS)
                if t_node is not None and t_node.text:
                    last_text_idx = idx
            trailing_br_count = 0
            for child in reversed(children[last_text_idx + 1 :]):
                if child.tag == f"{{{PPT_NS['a']}}}endParaRPr":
                    continue
                if child.tag == f"{{{PPT_NS['a']}}}br":
                    trailing_br_count += 1
                    continue
                break

            for idx, child in enumerate(children):
                if child.tag == f"{{{PPT_NS['a']}}}r":
                    _append_run(child)
                elif child.tag == f"{{{PPT_NS['a']}}}br":
                    if idx > last_text_idx:
                        continue
                    spans.append("<br/>")

            if not has_text:
                if trailing_br_count:
                    line_only_style = line_style or ""
                    blank_style_attr = (
                        f' style="{line_only_style}"' if line_only_style else ""
                    )
                    for _ in range(trailing_br_count):
                        html_paras.append(
                            f'<div class="{align_class} min-h-[1.2em]"{blank_style_attr}></div>'
                        )
                continue

            if bullet_char:
                bullet_classes, bullet_styles = first_text_styles or ([], [])
                bullet_style_attr = (
                    f' style="{" ".join(bullet_styles)}"' if bullet_styles else ""
                )
                spans.insert(
                    0,
                    f'<span class="{" ".join(bullet_classes)}"{bullet_style_attr}>{bullet_char} </span>',
                )

            style_attr = f' style="{" ".join(para_styles)}"' if para_styles else ""
            html_paras.append(
                f'<div class="{align_class} min-h-[1.2em]"{style_attr}>{"".join(spans)}</div>'
            )
            if trailing_br_count:
                line_only_style = line_style or ""
                blank_style_attr = (
                    f' style="{line_only_style}"' if line_only_style else ""
                )
                for _ in range(trailing_br_count):
                    html_paras.append(
                        f'<div class="{align_class} min-h-[1.2em]"{blank_style_attr}></div>'
                    )

        return "".join(html_paras)

    def _rect_center_percent(self, left_offset: int, right_offset: int) -> float:
        """Convert PPT fill/src rect offsets into a CSS percentage for object-position."""
        left_edge = left_offset
        right_edge = RECT_TOTAL_UNITS - right_offset
        center = (left_edge + right_edge) / 2.0
        percent = center / 1000.0
        return round(max(min(percent, 200.0), -200.0), 2)

    def _calculate_object_position(self, blipFill) -> Optional[str]:
        """Approximate object-position based on srcRect/fillRect adjustments."""
        if blipFill is None:
            return None

        rect = blipFill.find("a:srcRect", PPT_NS)
        if rect is None:
            rect = blipFill.find("a:stretch/a:fillRect", PPT_NS)
        if rect is None:
            return None

        def parse_value(attr_name: str) -> int:
            try:
                return int(rect.get(attr_name, "0"))
            except (TypeError, ValueError):
                return 0

        pos_x = self._rect_center_percent(parse_value("l"), parse_value("r"))
        pos_y = self._rect_center_percent(parse_value("t"), parse_value("b"))
        return f"{pos_x}% {pos_y}%"

    def _build_custom_geometry_path(
        self, custGeom, width: float, height: float
    ) -> Optional[str]:
        """Convert a custom geometry path to an SVG path string scaled to width/height."""
        if custGeom is None:
            return None
        path = custGeom.find("a:pathLst/a:path", PPT_NS)
        if path is None:
            return None
        try:
            path_w = float(path.get("w", "0")) or 0.0
            path_h = float(path.get("h", "0")) or 0.0
        except ValueError:
            return None
        if path_w == 0 or path_h == 0:
            return None

        commands = []

        def scale_point(pt_elem):
            try:
                x = float(pt_elem.get("x", "0"))
                y = float(pt_elem.get("y", "0"))
            except ValueError:
                return None
            scaled_x = (x / path_w) * width
            scaled_y = (y / path_h) * height
            return round_dimension(scaled_x), round_dimension(scaled_y)

        for cmd in path:
            tag = get_tag_name(cmd)
            if tag in ("moveTo", "lnTo"):
                pt = cmd.find("a:pt", PPT_NS)
                if pt is None:
                    continue
                scaled = scale_point(pt)
                if scaled is None:
                    continue
                prefix = "M" if tag == "moveTo" else "L"
                commands.append(f"{prefix} {scaled[0]} {scaled[1]}")
            elif tag == "cubicBezTo":
                pts = cmd.findall("a:pt", PPT_NS)
                if len(pts) != 3:
                    continue
                scaled_pts = [scale_point(pt) for pt in pts]
                if any(sp is None for sp in scaled_pts):
                    continue
                c1, c2, end = scaled_pts
                commands.append(f"C {c1[0]} {c1[1]} {c2[0]} {c2[1]} {end[0]} {end[1]}")
            elif tag == "quadBezTo":
                pts = cmd.findall("a:pt", PPT_NS)
                if len(pts) != 2:
                    continue
                scaled_pts = [scale_point(pt) for pt in pts]
                if any(sp is None for sp in scaled_pts):
                    continue
                c, end = scaled_pts
                commands.append(f"Q {c[0]} {c[1]} {end[0]} {end[1]}")
            elif tag == "close":
                commands.append("Z")

        if not commands:
            return None
        if commands[-1] != "Z":
            commands.append("Z")
        return " ".join(commands)

    @staticmethod
    def _rounded_rect_path(width: float, height: float, radius: float) -> str:
        """Return an SVG path for a rounded rectangle."""
        rx = max(0.0, min(radius, width / 2.0))
        ry = max(0.0, min(radius, height / 2.0))
        return (
            f"M {rx} 0 "
            f"H {width - rx} "
            f"A {rx} {ry} 0 0 1 {width} {ry} "
            f"V {height - ry} "
            f"A {rx} {ry} 0 0 1 {width - rx} {height} "
            f"H {rx} "
            f"A {rx} {ry} 0 0 1 0 {height - ry} "
            f"V {ry} "
            f"A {rx} {ry} 0 0 1 {rx} 0 Z"
        )

    @staticmethod
    def _rounded_rect_one_side(
        width: float, height: float, radius: float, side: str
    ) -> str:
        """Return an SVG path with rounding on one side."""
        r = max(0.0, min(radius, min(width, height) / 2.0))
        if side == "right":
            return (
                f"M 0 0 "
                f"H {width - r} "
                f"A {r} {r} 0 0 1 {width} {r} "
                f"V {height - r} "
                f"A {r} {r} 0 0 1 {width - r} {height} "
                f"H 0 Z"
            )
        if side == "top":
            return (
                f"M 0 {r} "
                f"A {r} {r} 0 0 1 {r} 0 "
                f"H {width - r} "
                f"A {r} {r} 0 0 1 {width} {r} "
                f"V {height} "
                f"H 0 Z"
            )
        if side == "bottom":
            return (
                f"M 0 0 "
                f"H {width} "
                f"V {height - r} "
                f"A {r} {r} 0 0 1 {width - r} {height} "
                f"H {r} "
                f"A {r} {r} 0 0 1 0 {height - r} "
                f"V 0 Z"
            )
        # default: left side
        return (
            f"M {r} 0 "
            f"H {width} "
            f"V {height} "
            f"H {r} "
            f"A {r} {r} 0 0 1 0 {height - r} "
            f"V {r} "
            f"A {r} {r} 0 0 1 {r} 0 Z"
        )

    def _build_preset_geometry_path(
        self, prstGeom, width: float, height: float
    ) -> Optional[str]:
        """Build a path for common preset geometries."""
        if prstGeom is None:
            return None
        prst = prstGeom.get("prst")
        if not prst:
            return None
        if prst == "triangle":
            return f"M {width / 2.0} 0 L {width} {height} L 0 {height} Z"
        if prst == "arc":

            def _adj_value(name: str, fallback: float) -> float:
                gd = prstGeom.find(f".//a:gd[@name='{name}']", PPT_NS)
                if gd is not None and gd.get("fmla"):
                    parts = gd.get("fmla").split()
                    if len(parts) == 2 and parts[0] == "val":
                        try:
                            return float(parts[1])
                        except ValueError:
                            return fallback
                return fallback

            # Angles are stored in 1/60000 of a degree.
            start_raw = _adj_value("adj1", 0.0)
            end_raw = _adj_value("adj2", 21600000.0)
            start_deg = (start_raw / 60000.0) % 360.0
            end_deg = (end_raw / 60000.0) % 360.0
            delta = (end_deg - start_deg) % 360.0
            if delta == 0:
                delta = 360.0

            rx = width / 2.0
            ry = height / 2.0
            cx = rx
            cy = ry

            start_rad = math.radians(start_deg)
            end_rad = math.radians(end_deg)
            start_x = cx + rx * math.cos(start_rad)
            start_y = cy + ry * math.sin(start_rad)
            end_x = cx + rx * math.cos(end_rad)
            end_y = cy + ry * math.sin(end_rad)

            large_arc = 1 if delta > 180.0 else 0
            sweep = 1
            return (
                f"M {round_dimension(start_x)} {round_dimension(start_y)} "
                f"A {round_dimension(rx)} {round_dimension(ry)} 0 {large_arc} {sweep} "
                f"{round_dimension(end_x)} {round_dimension(end_y)}"
            )
        return None

    def _is_placeholder(self, sp) -> bool:
        """Check if a shape is a placeholder (should be skipped in master/layout)."""
        nvSpPr = sp.find("p:nvSpPr", PPT_NS)
        if nvSpPr is not None:
            nvPr = nvSpPr.find("p:nvPr", PPT_NS)
            if nvPr is not None:
                ph = nvPr.find("p:ph", PPT_NS)
                if ph is not None:
                    return True
        return False

    def _is_hidden(self, sp) -> bool:
        """Check if a shape is marked hidden."""
        nv_container = sp.find("p:nvSpPr", PPT_NS)
        if nv_container is None:
            nv_container = sp.find("p:nvPicPr", PPT_NS)
        if nv_container is None:
            return False
        cNvPr = nv_container.find("p:cNvPr", PPT_NS)
        if cNvPr is None:
            return False
        return cNvPr.get("hidden") in ("1", "true")

    def _get_placeholder_key(self, sp) -> Optional[Tuple[str, Optional[str]]]:
        """Return placeholder key (type, idx) if shape is a placeholder."""
        nv_container = sp.find("p:nvSpPr", PPT_NS)
        if nv_container is None:
            nv_container = sp.find("p:nvPicPr", PPT_NS)
        if nv_container is None:
            return None
        nvPr = nv_container.find("p:nvPr", PPT_NS)
        if nvPr is None:
            return None
        ph = nvPr.find("p:ph", PPT_NS)
        if ph is None:
            return None
        ph_type = ph.get("type") or "body"
        ph_idx = ph.get("idx")
        return (ph_type, ph_idx)

    def _extract_xfrm_data(self, sp) -> Optional[Dict[str, str]]:
        """Extract xfrm data from a shape/pic element."""
        spPr = sp.find("p:spPr", PPT_NS)
        if spPr is None:
            return None
        xfrm = spPr.find("a:xfrm", PPT_NS)
        if xfrm is None:
            return None
        off = xfrm.find("a:off", PPT_NS)
        ext = xfrm.find("a:ext", PPT_NS)
        if off is None or ext is None:
            return None
        return {
            "x": off.get("x"),
            "y": off.get("y"),
            "cx": ext.get("cx"),
            "cy": ext.get("cy"),
            "rot": xfrm.get("rot", "0"),
            "flipH": xfrm.get("flipH", "0"),
            "flipV": xfrm.get("flipV", "0"),
        }

    def _build_placeholder_xfrm_map(
        self, layout_xml, master_xml
    ) -> Dict[Tuple[str, Optional[str]], Dict[str, str]]:
        """Build a placeholder -> xfrm lookup from layout/master."""
        placeholder_map: Dict[Tuple[str, Optional[str]], Dict[str, str]] = {}
        for xml in (master_xml, layout_xml):
            if xml is None:
                continue
            spTree = xml.find(".//p:spTree", PPT_NS)
            if spTree is None:
                continue
            for child in spTree:
                tag = get_tag_name(child)
                if tag not in ("sp", "pic"):
                    continue
                key = self._get_placeholder_key(child)
                if not key:
                    continue
                xfrm_data = self._extract_xfrm_data(child)
                if not xfrm_data:
                    continue
                placeholder_map[key] = xfrm_data
        return placeholder_map

    def _build_placeholder_text_style_map(
        self, layout_xml, master_xml
    ) -> Dict[Tuple[str, Optional[str]], Dict[int, List[etree._Element]]]:
        """Build a placeholder -> text style (defRPr) lookup from layout/master."""
        style_map: Dict[Tuple[str, Optional[str]], Dict[int, List[etree._Element]]] = {}

        def _get_txstyle_defaults() -> Dict[str, Dict[int, etree._Element]]:
            tx_styles = (
                master_xml.find("p:txStyles", PPT_NS)
                if master_xml is not None
                else None
            )
            if tx_styles is None:
                return {}
            styles = {}
            for name, key in (
                ("p:titleStyle", "title"),
                ("p:bodyStyle", "body"),
                ("p:otherStyle", "other"),
            ):
                style_elem = tx_styles.find(name, PPT_NS)
                if style_elem is None:
                    continue
                per_level: Dict[int, etree._Element] = {}
                for lvl in range(1, 10):
                    lvl_pr = style_elem.find(f"a:lvl{lvl}pPr", PPT_NS)
                    if lvl_pr is None:
                        continue
                    def_rpr = lvl_pr.find("a:defRPr", PPT_NS)
                    if def_rpr is not None:
                        per_level[lvl - 1] = def_rpr
                if per_level:
                    styles[key] = per_level
            return styles

        def _ph_style_key(ph_type: str) -> str:
            if ph_type in ("title", "ctrTitle"):
                return "title"
            if ph_type == "body":
                return "body"
            return "other"

        txstyle_defaults = _get_txstyle_defaults()

        for xml in (master_xml, layout_xml):
            if xml is None:
                continue
            spTree = xml.find(".//p:spTree", PPT_NS)
            if spTree is None:
                continue
            for child in spTree:
                tag = get_tag_name(child)
                if tag not in ("sp", "pic"):
                    continue
                key = self._get_placeholder_key(child)
                if not key:
                    continue
                ph_style_key = _ph_style_key(key[0])
                base_defaults = txstyle_defaults.get(ph_style_key, {})
                txBody = child.find("p:txBody", PPT_NS)
                lstStyle = (
                    txBody.find("a:lstStyle", PPT_NS) if txBody is not None else None
                )
                per_level: Dict[int, List[etree._Element]] = {}
                for lvl in range(1, 10):
                    overrides: List[etree._Element] = []
                    if lstStyle is not None:
                        lvl_pr = lstStyle.find(f"a:lvl{lvl}pPr", PPT_NS)
                        if lvl_pr is not None:
                            def_rpr = lvl_pr.find("a:defRPr", PPT_NS)
                            if def_rpr is not None:
                                overrides.append(def_rpr)
                    if lvl - 1 in base_defaults:
                        overrides.append(base_defaults[lvl - 1])
                    if overrides:
                        per_level[lvl - 1] = overrides
                if per_level:
                    style_map[key] = per_level
        return style_map

    def _build_placeholder_paragraph_style_map(
        self, layout_xml, master_xml
    ) -> Dict[Tuple[str, Optional[str]], Dict[int, List[etree._Element]]]:
        """Build a placeholder -> paragraph style (lvlXpPr) lookup from layout/master."""
        paragraph_map: Dict[
            Tuple[str, Optional[str]], Dict[int, List[etree._Element]]
        ] = {}

        def _get_txstyle_ppr_defaults() -> Dict[str, Dict[int, etree._Element]]:
            tx_styles = (
                master_xml.find("p:txStyles", PPT_NS)
                if master_xml is not None
                else None
            )
            if tx_styles is None:
                return {}
            styles = {}
            for name, key in (
                ("p:titleStyle", "title"),
                ("p:bodyStyle", "body"),
                ("p:otherStyle", "other"),
            ):
                style_elem = tx_styles.find(name, PPT_NS)
                if style_elem is None:
                    continue
                per_level: Dict[int, etree._Element] = {}
                for lvl in range(1, 10):
                    lvl_pr = style_elem.find(f"a:lvl{lvl}pPr", PPT_NS)
                    if lvl_pr is not None:
                        per_level[lvl - 1] = lvl_pr
                if per_level:
                    styles[key] = per_level
            return styles

        def _ph_style_key(ph_type: str) -> str:
            if ph_type in ("title", "ctrTitle"):
                return "title"
            if ph_type == "body":
                return "body"
            return "other"

        txstyle_defaults = _get_txstyle_ppr_defaults()

        for xml in (master_xml, layout_xml):
            if xml is None:
                continue
            spTree = xml.find(".//p:spTree", PPT_NS)
            if spTree is None:
                continue
            for child in spTree:
                tag = get_tag_name(child)
                if tag not in ("sp", "pic"):
                    continue
                key = self._get_placeholder_key(child)
                if not key:
                    continue
                ph_style_key = _ph_style_key(key[0])
                base_defaults = txstyle_defaults.get(ph_style_key, {})
                txBody = child.find("p:txBody", PPT_NS)
                lstStyle = (
                    txBody.find("a:lstStyle", PPT_NS) if txBody is not None else None
                )
                per_level: Dict[int, List[etree._Element]] = {}
                for lvl in range(1, 10):
                    overrides: List[etree._Element] = []
                    if lstStyle is not None:
                        lvl_pr = lstStyle.find(f"a:lvl{lvl}pPr", PPT_NS)
                        if lvl_pr is not None:
                            overrides.append(lvl_pr)
                    if lvl - 1 in base_defaults:
                        overrides.append(base_defaults[lvl - 1])
                    if overrides:
                        per_level[lvl - 1] = overrides
                if per_level:
                    paragraph_map[key] = per_level
        return paragraph_map

    def _build_placeholder_bodypr_map(
        self, layout_xml, master_xml
    ) -> Dict[Tuple[str, Optional[str]], etree._Element]:
        """Build a placeholder -> bodyPr lookup from layout/master."""
        bodypr_map: Dict[Tuple[str, Optional[str]], etree._Element] = {}
        for xml in (master_xml, layout_xml):
            if xml is None:
                continue
            spTree = xml.find(".//p:spTree", PPT_NS)
            if spTree is None:
                continue
            for child in spTree:
                tag = get_tag_name(child)
                if tag not in ("sp", "pic"):
                    continue
                key = self._get_placeholder_key(child)
                if not key:
                    continue
                txBody = child.find("p:txBody", PPT_NS)
                if txBody is None:
                    continue
                bodyPr = txBody.find("a:bodyPr", PPT_NS)
                if bodyPr is not None:
                    bodypr_map[key] = bodyPr
        return bodypr_map

    async def _render_shape(
        self,
        sp,
        rels,
        parent_transform=None,
        skip_placeholders=False,
        placeholder_xfrm_map: Optional[
            Dict[Tuple[str, Optional[str]], Dict[str, str]]
        ] = None,
        placeholder_text_styles: Optional[
            Dict[Tuple[str, Optional[str]], Dict[int, List[etree._Element]]]
        ] = None,
        placeholder_paragraph_styles: Optional[
            Dict[Tuple[str, Optional[str]], Dict[int, List[etree._Element]]]
        ] = None,
        placeholder_bodypr_map: Optional[
            Dict[Tuple[str, Optional[str]], etree._Element]
        ] = None,
        group_fill_color: Optional[str] = None,
    ) -> str:
        # Skip placeholders if requested (for master/layout slides)
        if skip_placeholders and self._is_placeholder(sp):
            return ""
        if self._is_hidden(sp):
            return ""

        # Check if this is a pic element (has p:blipFill directly)
        is_pic = get_tag_name(sp) == "pic"

        # For pic elements, blipFill is a direct child; for sp elements, it's under spPr
        if is_pic:
            blipFill = sp.find("p:blipFill", PPT_NS)
            spPr = sp.find("p:spPr", PPT_NS)
        else:
            spPr = sp.find("p:spPr", PPT_NS)
            blipFill = None

        if spPr is None:
            return ""

        prstGeom_early = spPr.find("a:prstGeom", PPT_NS)
        is_triangle = (
            prstGeom_early is not None and prstGeom_early.get("prst") == "triangle"
        )

        xfrm_data = self._extract_xfrm_data(sp)
        if xfrm_data is None and placeholder_xfrm_map:
            ph_key = self._get_placeholder_key(sp)
            if ph_key:
                xfrm_data = placeholder_xfrm_map.get(ph_key)
                if xfrm_data is None and ph_key[0]:
                    xfrm_data = placeholder_xfrm_map.get((ph_key[0], None))
        if xfrm_data is None:
            return ""  # Some placeholders rely on layout/master geometry

        shape_flip_h = xfrm_data.get("flipH") in ("1", "true")
        shape_flip_v = xfrm_data.get("flipV") in ("1", "true")
        parent_flip_h = False
        parent_flip_v = False

        x = emu_to_px(xfrm_data.get("x"))
        y = emu_to_px(xfrm_data.get("y"))
        w = emu_to_px(xfrm_data.get("cx"))
        h = emu_to_px(xfrm_data.get("cy"))
        rot = int(xfrm_data.get("rot", "0")) / 60000
        rot_raw = rot

        # Apply Parent Transform (Group)
        if parent_transform:
            # parent_transform = {'offx':, 'offy':, 'scale_x':, 'scale_y':, 'chOffx':, 'chOffy':}
            # child_screen_x = group_off_x + (child_off_x - group_chOff_x) * scale_x

            px = parent_transform["offx"]
            py = parent_transform["offy"]
            sx = parent_transform["scale_x"]
            sy = parent_transform["scale_y"]
            chx = parent_transform["chOffx"]
            chy = parent_transform["chOffy"]
            ch_ext_x = parent_transform.get("chExtcx")
            ch_ext_y = parent_transform.get("chExtcy")
            flip_h = parent_transform.get("flipH", False)
            flip_v = parent_transform.get("flipV", False)
            parent_flip_h = flip_h
            parent_flip_v = flip_v

            # Recalculate
            local_x = x - chx
            local_y = y - chy
            if flip_h and ch_ext_x is not None:
                local_x = ch_ext_x - local_x - w
            if flip_v and ch_ext_y is not None:
                local_y = ch_ext_y - local_y - h
            new_x = px + local_x * sx
            new_y = py + local_y * sy
            scaled_w = w * sx
            scaled_h = h * sy
            new_w = scaled_w
            new_h = scaled_h
            if is_triangle and abs(rot) % 180 == 90:
                swapped_w = h * sx
                swapped_h = w * sy
                new_x += (scaled_w - swapped_w) / 2.0
                new_y += (scaled_h - swapped_h) / 2.0
                new_w = swapped_w
                new_h = swapped_h

            x, y, w, h = new_x, new_y, new_w, new_h
            # Values are already scaled (sx/sy include scale_factor), just round
            x = round_dimension(x)
            y = round_dimension(y)
            w = round_dimension(w)
            h = round_dimension(h)
        else:
            # No parent transform - scale and round
            x = self._scale_and_round(x)
            y = self._scale_and_round(y)
            w = self._scale_and_round(w)
            h = self._scale_and_round(h)

        final_flip_h = shape_flip_h ^ parent_flip_h
        final_flip_v = shape_flip_v ^ parent_flip_v
        # When flips are present, PowerPoint applies flip before rotation.
        # Tailwind applies rotate before scale, so invert rotation for odd flips.
        if (final_flip_h ^ final_flip_v) and not is_triangle:
            rot = -rot
        rot = round_dimension(rot)

        # Base classes for positioning and size
        classes = [
            "absolute",
            f"left-[{x}px]",
            f"top-[{y}px]",
            f"w-[{w}px]",
            f"h-[{h}px]",
        ]

        image_html = None

        # 1. Check for Image (for pic elements, blipFill is direct child; for sp, it's under spPr)
        if is_pic and blipFill is not None:
            # For p:pic, blipFill contains a:blip directly
            blip = blipFill.find("a:blip", PPT_NS)
            if blip is not None:
                embed_id = blip.get(f"{{{PPT_NS['r']}}}embed")
                if embed_id and embed_id in rels:
                    img_path = rels[embed_id]["path"]
                    img_url = await self._get_image_url(img_path)
                    obj_pos = self._calculate_object_position(blipFill)
                    style_attr = (
                        f' style="object-position: {obj_pos};"' if obj_pos else ""
                    )
                    image_html = f'<img src="{img_url}" class="w-full h-full object-cover"{style_attr}>'
        elif not is_pic:
            # For p:sp, check under spPr
            blipFill = spPr.find("a:blipFill", PPT_NS)
            if blipFill is not None:
                blip = blipFill.find("a:blip", PPT_NS)
                if blip is not None:
                    embed_id = blip.get(f"{{{PPT_NS['r']}}}embed")
                    if embed_id and embed_id in rels:
                        img_path = rels[embed_id]["path"]
                        img_url = await self._get_image_url(img_path)
                        obj_pos = self._calculate_object_position(blipFill)
                        style_attr = (
                            f' style="object-position: {obj_pos};"' if obj_pos else ""
                        )
                        image_html = f'<img src="{img_url}" class="w-full h-full object-cover"{style_attr}>'

        # 2. Check for Geometry / Fill
        bg_color = self._resolve_color(spPr, default=None)
        if spPr.find("a:grpFill", PPT_NS) is not None:
            bg_color = group_fill_color
        elif bg_color is None and group_fill_color:
            bg_color = group_fill_color
        bg_class = None
        if bg_color and bg_color != "transparent":
            bg_class = f"bg-[{bg_color}]"

        # Borders
        ln = spPr.find("a:ln", PPT_NS)
        ln_col = None
        border_width_px = None
        if ln is not None and ln.find("a:noFill", PPT_NS) is None:
            ln_col = self._resolve_color(ln, default=None)
            if ln_col:
                border_width_px = self._scale_and_round(
                    max(emu_to_px(ln.get("w", "12700")), 1)
                )

        custGeom = spPr.find("a:custGeom", PPT_NS)
        prstGeom = prstGeom_early
        if prstGeom is not None:
            geom = prstGeom.get("prst")
        elif custGeom is not None:
            geom = "custGeom"
        else:
            geom = "rect"
        if geom in ("straightConnector1", "straightConnector", "line"):
            geom = "line"

        custom_path_d = None
        if geom == "custGeom" and custGeom is not None:
            custom_path_d = self._build_custom_geometry_path(custGeom, w, h)
        elif prstGeom is not None:
            custom_path_d = self._build_preset_geometry_path(prstGeom, w, h)

        txBody = sp.find("p:txBody", PPT_NS)
        has_text = txBody is not None and txBody.find(".//a:t", PPT_NS) is not None
        apply_rotation = True
        skip_round2_rotation = False
        round2_rot = rot
        # For round2SameRect in grouped shapes, PPTX often stores rotated bounds.
        # Skip rotation to avoid double-rotating pills.
        if (
            parent_transform
            and prstGeom is not None
            and not has_text
            and rot
            and (abs(rot) % 90) == 0
            and geom == "round2SameRect"
        ):
            apply_rotation = False
            skip_round2_rotation = True

        if geom == "triangle":
            rot = round_dimension(rot_raw)
        if geom == "round2SameRect" and prstGeom is not None:
            adj1 = 0.0
            gd = prstGeom.find(".//a:gd[@name='adj1']", PPT_NS)
            if gd is not None and gd.get("fmla"):
                fmla = gd.get("fmla")
                parts = fmla.split()
                if len(parts) == 2 and parts[0] == "val":
                    try:
                        adj1 = float(parts[1]) / 100000.0
                    except ValueError:
                        adj1 = 0.0
            radius = min(w, h) * adj1
            round_side = "left" if final_flip_h else "right"
            if skip_round2_rotation and round2_rot:
                # When group transforms already encode rotation, keep side orientation.
                round_side = "left" if shape_flip_h else "right"
                rot = 0
            custom_path_d = self._rounded_rect_one_side(w, h, radius, round_side)

        if geom == "triangle":
            angle = int(round(rot_raw)) % 360
            # PowerPoint flips happen before rotation; horizontal flip does not
            # change triangle direction, vertical flip flips the apex direction.
            triangle_flip_h = parent_flip_h if parent_transform else final_flip_h
            triangle_flip_v = parent_flip_v if parent_transform else final_flip_v
            if triangle_flip_h:
                angle = (360 - angle) % 360
            if triangle_flip_v:
                angle = (angle + 180) % 360
            if angle == 0:
                custom_path_d = f"M {w / 2.0} 0 L {w} {h} L 0 {h} Z"
            elif angle == 90:
                custom_path_d = f"M 0 0 L {w} {h / 2.0} L 0 {h} Z"
            elif angle == 180:
                custom_path_d = f"M 0 0 L {w} 0 L {w / 2.0} {h} Z"
            elif angle == 270:
                custom_path_d = f"M {w} 0 L 0 {h / 2.0} L {w} {h} Z"
            apply_rotation = False
            rot = 0

        if not is_triangle:
            apply_flip_h = final_flip_h
            apply_flip_v = final_flip_v
            if apply_flip_h:
                classes.append("scale-x-[-1]")
            if apply_flip_v:
                classes.append("scale-y-[-1]")
            if (apply_flip_h or apply_flip_v) and "origin-center" not in classes:
                classes.append("origin-center")

        if rot != 0 and apply_rotation:
            classes.append(f"rotate-[{rot}deg]")
            classes.append("origin-center")

        # Check shape name (for sp elements) or pic name (for pic elements)
        shape_name = ""
        nvSpPr = None
        if is_pic:
            nvPicPr = sp.find("p:nvPicPr", PPT_NS)
            if nvPicPr is not None:
                cNvPr = nvPicPr.find("p:cNvPr", PPT_NS)
                if cNvPr is not None:
                    shape_name = cNvPr.get("name", "")
        else:
            nvSpPr = sp.find("p:nvSpPr", PPT_NS)
            if nvSpPr is not None:
                cNvPr = nvSpPr.find("p:cNvPr", PPT_NS)
                if cNvPr is not None:
                    shape_name = cNvPr.get("name", "")

        print(f"DEBUG: Shape: {shape_name}, Geom: {geom}, x={x}, y={y}, w={w}, h={h}")

        if geom == "ellipse":
            classes.append("rounded-full")
        # elif geom == "custGeom":
        #      pass

        if geom == "line":
            # Render line as SVG
            stroke_w = max(emu_to_px(ln.get("w", "0")), 1) if ln is not None else 1
            stroke_w = self._scale_and_round(stroke_w)
            col = ln_col or "#000"
            dash_array = self._get_line_dasharray(ln, stroke_w)
            linecap = self._get_linecap(ln)
            dash_attr = f' stroke-dasharray="{dash_array}"' if dash_array else ""
            cap_attr = f' stroke-linecap="{linecap}"' if linecap else ""

            # Determine line direction based on ext dimensions
            # If h is 0 or very small, it's a horizontal line
            # If w is 0 or very small, it's a vertical line
            # Otherwise, it's diagonal
            # Ensure minimum size for visibility
            min_size = max(stroke_w, 1.0)
            if h <= 1:  # Horizontal line
                # Ensure minimum height for visibility
                actual_h = max(h, min_size)
                x1, y1 = "0%", "50%"
                x2, y2 = "100%", "50%"
                return f'''
            <div class="absolute left-[{x}px] top-[{y}px] w-[{w}px] h-[{actual_h}px] rotate-[{rot}deg]">
                <svg width="100%" height="100%" overflow="visible">
                    <line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{col}" stroke-width="{stroke_w}"{dash_attr}{cap_attr} />
                </svg>
            </div>'''
            elif w <= 1:  # Vertical line
                # Ensure minimum width for visibility
                actual_w = max(w, min_size)
                x1, y1 = "50%", "0%"
                x2, y2 = "50%", "100%"
                return f'''
            <div class="absolute left-[{x}px] top-[{y}px] w-[{actual_w}px] h-[{h}px] rotate-[{rot}deg]">
                <svg width="100%" height="100%" overflow="visible">
                    <line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{col}" stroke-width="{stroke_w}"{dash_attr}{cap_attr} />
                </svg>
            </div>'''
            else:  # Diagonal line
                x1, y1 = "0", "0"
                x2, y2 = "100%", "100%"
            return f'''
            <div class="absolute left-[{x}px] top-[{y}px] w-[{w}px] h-[{h}px] rotate-[{rot}deg]">
                <svg width="100%" height="100%" overflow="visible">
                    <line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{col}" stroke-width="{stroke_w}"{dash_attr}{cap_attr} />
                </svg>
            </div>'''
        elif ln_col and border_width_px and not custom_path_d:
            classes.append(f"border-[{border_width_px}px]")
            classes.append("border-solid")
            classes.append(f"border-[{ln_col}]")

        # 3. Text
        txBody = sp.find("p:txBody", PPT_NS)
        text_html = self._render_text_body(
            txBody,
            placeholder_text_styles=placeholder_text_styles,
            placeholder_paragraph_styles=placeholder_paragraph_styles,
            placeholder_key=self._get_placeholder_key(sp),
        )

        if bg_class and not custom_path_d:
            classes.append(bg_class)

        # Vertical Alignment
        valign_class = ""
        padding_style = None
        if txBody is not None:
            bodyPr = txBody.find("a:bodyPr", PPT_NS)
            anchor = None
            if bodyPr is not None:
                anchor = bodyPr.get("anchor")
            if not anchor and placeholder_bodypr_map is not None:
                ph_key = self._get_placeholder_key(sp)
                fallback_bodypr = placeholder_bodypr_map.get(ph_key) if ph_key else None
                if fallback_bodypr is None and ph_key and ph_key[0]:
                    fallback_bodypr = placeholder_bodypr_map.get((ph_key[0], None))
                if fallback_bodypr is not None:
                    anchor = fallback_bodypr.get("anchor")
                padding_style = self._extract_body_padding_style(
                    bodyPr, fallback_bodypr
                )
            if anchor:
                if anchor == "ctr":
                    valign_class = "flex flex-col justify-center"
                elif anchor == "b":
                    valign_class = "flex flex-col justify-end"

        # Use overflow-visible to prevent clipping by default
        if image_html is not None:
            return (
                f'<div class="{" ".join(classes)} overflow-hidden">{image_html}</div>'
            )

        layered_content = []
        if custom_path_d:
            dash_array = self._get_line_dasharray(ln, border_width_px or 1.0)
            linecap = self._get_linecap(ln)
            dash_attr = f' stroke-dasharray="{dash_array}"' if dash_array else ""
            cap_attr = f' stroke-linecap="{linecap}"' if linecap else ""
            stroke_attr = (
                f'stroke="{ln_col}" stroke-width="{border_width_px}"{dash_attr}{cap_attr}'
                if ln_col and border_width_px
                else 'stroke="none"'
            )
            if not bg_color or bg_color == "transparent":
                fill_color = "none"
            else:
                fill_color = bg_color
            layered_content.append(
                f'<svg class="absolute inset-0 w-full h-full pointer-events-none" viewBox="0 0 {w} {h}" preserveAspectRatio="none"><path d="{custom_path_d}" fill="{fill_color}" {stroke_attr} /></svg>'
            )
            if text_html:
                text_html = f'<div class="relative z-10 w-full">{text_html}</div>'

        layered_content.append(text_html)

        style_attr = f' style="{padding_style}"' if padding_style else ""
        return f'<div class="{" ".join(classes)} {valign_class} overflow-visible"{style_attr}>{"".join(layered_content)}</div>'

    def _render_table(self, graphic_frame, rels) -> str:
        xfrm = graphic_frame.find("p:xfrm", PPT_NS)
        if xfrm is None:
            return ""

        off = xfrm.find("a:off", PPT_NS)
        ext = xfrm.find("a:ext", PPT_NS)

        if off is None or ext is None:
            return ""

        x = emu_to_px(off.get("x"))
        y = emu_to_px(off.get("y"))
        w = emu_to_px(ext.get("cx"))
        h = emu_to_px(ext.get("cy"))

        tbl = graphic_frame.find(".//a:tbl", PPT_NS)
        if tbl is None:
            return ""

        # Table Grid (Columns)
        tblGrid = tbl.find("a:tblGrid", PPT_NS)
        col_widths = []
        if tblGrid is not None:
            for gridCol in tblGrid.findall("a:gridCol", PPT_NS):
                cw = emu_to_px(gridCol.get("w"))
                col_widths.append(cw)

        # Rows
        rows_html = []
        for tr in tbl.findall("a:tr", PPT_NS):
            tr_h = emu_to_px(tr.get("h"))
            cells_html = []
            col_idx = 0

            for tc in tr.findall("a:tc", PPT_NS):
                # Handle gridSpan (colspan)
                gridSpan = int(tc.get("gridSpan", "1"))

                # Calculate width for this cell
                current_col_w = 0
                if col_idx < len(col_widths):
                    for k in range(gridSpan):
                        if col_idx + k < len(col_widths):
                            current_col_w += col_widths[col_idx + k]

                # Scale and round cell width
                current_col_w = self._scale_and_round(current_col_w)

                # Cell Properties
                tcPr = tc.find("a:tcPr", PPT_NS)
                bg_color = self._resolve_color(tcPr, default="transparent")

                cell_valign_class = "align-top"
                txBody = tc.find("a:txBody", PPT_NS)
                if txBody is not None:
                    bodyPr = txBody.find("a:bodyPr", PPT_NS)
                    anchor = bodyPr.get("anchor") if bodyPr is not None else None
                    if anchor == "ctr":
                        cell_valign_class = "align-middle"
                    elif anchor == "b":
                        cell_valign_class = "align-bottom"

                cell_classes = [
                    f"w-[{current_col_w}px]",
                    cell_valign_class,
                ]
                cell_styles: List[str] = []
                has_custom_borders = False
                if bg_color != "transparent":
                    cell_classes.append(f"bg-[{bg_color}]")

                if tcPr is not None:
                    margin_map = {
                        "marL": ("pl-[{}px]",),
                        "marR": ("pr-[{}px]",),
                        "marT": ("pt-[{}px]",),
                        "marB": ("pb-[{}px]",),
                    }
                    for attr, tailwind_fmt in margin_map.items():
                        val = tcPr.get(attr)
                        if val:
                            pad_px = self._scale_and_round(emu_to_px(val))
                            cell_classes.append(tailwind_fmt[0].format(pad_px))

                    border_styles, has_custom_borders = (
                        self._extract_table_cell_borders(tcPr)
                    )
                    cell_styles.extend(border_styles)

                if not has_custom_borders:
                    cell_classes.extend(["border", "border-gray-300"])

                # Text Body
                content = self._render_text_body(txBody) or "&nbsp;"

                style_attr = f' style="{" ".join(cell_styles)}"' if cell_styles else ""
                cells_html.append(
                    f'<td class="{" ".join(cell_classes)}" colspan="{gridSpan}"{style_attr}>{content}</td>'
                )

                col_idx += gridSpan

            # Scale and round row height
            tr_h = self._scale_and_round(tr_h)
            rows_html.append(f'<tr class="h-[{tr_h}px]">{"".join(cells_html)}</tr>')

        # Scale and round table dimensions
        x = self._scale_and_round(x)
        y = self._scale_and_round(y)
        w = self._scale_and_round(w)
        h = self._scale_and_round(h)

        return f"""
        <div class="absolute left-[{x}px] top-[{y}px] w-[{w}px] h-[{h}px] overflow-hidden">
            <table class="w-full h-full border-collapse table-fixed">
                <tbody>
                    {"".join(rows_html)}
                </tbody>
            </table>
        </div>
        """

    def _extract_table_cell_borders(self, tcPr) -> Tuple[List[str], bool]:
        """Extract inline CSS for PowerPoint table cell borders."""
        if tcPr is None:
            return [], False

        styles: List[str] = []
        has_custom = False
        tc_borders = tcPr.find("a:tcBorders", PPT_NS)

        border_map = [
            ("lnL", "left", "border-left"),
            ("lnR", "right", "border-right"),
            ("lnT", "top", "border-top"),
            ("lnB", "bottom", "border-bottom"),
        ]

        dash_map = {
            "solid": "solid",
            "dash": "dashed",
            "sysDash": "dashed",
            "lgDash": "dashed",
            "lgDashDot": "dashed",
            "dot": "dotted",
            "sysDot": "dotted",
            "sysDashDot": "dashed",
            "sysDashDotDot": "dashed",
        }

        def parse_line(line_elem, css_prop: str):
            nonlocal has_custom
            if line_elem is None:
                return

            no_fill = line_elem.find("a:noFill", PPT_NS)
            if no_fill is not None:
                styles.append(f"{css_prop}:0;")
                has_custom = True
                return

            width_attr = line_elem.get("w")
            width_px = 1.0
            if width_attr:
                width_px = max(self._scale_and_round(emu_to_px(width_attr)), 1.0)

            color = self._resolve_color(line_elem, default="#9ca3af")
            dash = line_elem.find("a:prstDash", PPT_NS)
            dash_val = dash.get("val") if dash is not None else "solid"
            css_dash = dash_map.get(dash_val, "solid")

            styles.append(f"{css_prop}:{width_px}px {css_dash} {color};")
            has_custom = True

        for attr_name, fallback_name, css_prop in border_map:
            line = tcPr.find(f"a:{attr_name}", PPT_NS)
            if line is None and tc_borders is not None and fallback_name:
                line = tc_borders.find(f"a:{fallback_name}", PPT_NS)
            parse_line(line, css_prop)

        return styles, has_custom

    def _render_chart(self, graphic_frame, rels) -> str:
        xfrm = graphic_frame.find("p:xfrm", PPT_NS)
        if xfrm is None:
            return ""

        off = xfrm.find("a:off", PPT_NS)
        ext = xfrm.find("a:ext", PPT_NS)
        if off is None or ext is None:
            return ""

        x = self._scale_and_round(emu_to_px(off.get("x")))
        y = self._scale_and_round(emu_to_px(off.get("y")))
        w = self._scale_and_round(emu_to_px(ext.get("cx")))
        h = self._scale_and_round(emu_to_px(ext.get("cy")))

        chart_elem = graphic_frame.find(".//c:chart", CHART_NS)
        if chart_elem is None:
            return ""

        r_id = chart_elem.get(f"{{{PPT_NS['r']}}}id")
        if not r_id or r_id not in rels:
            return ""

        chart_xml = self._read_xml(rels[r_id]["path"])
        if chart_xml is None:
            return ""

        chart_data = self._extract_chart_data(chart_xml)
        if chart_data is None:
            return ""

        categories = chart_data["categories"]
        series = chart_data["series"]
        legend_position = chart_data.get("legend_position", "b")
        axes_info = chart_data.get("axes", {})
        value_axis_info = axes_info.get("value", {})
        category_axis_info = axes_info.get("category", {})
        if not categories or not series:
            return ""

        data_points = [
            value for ser in series for value in ser["values"] if ser["values"]
        ]
        data_min = min(data_points) if data_points else 0
        data_max = max(data_points) if data_points else 0

        axis_min = value_axis_info.get("min")
        if axis_min is None:
            axis_min = min(0.0, data_min)
        axis_max = value_axis_info.get("max")
        if axis_max is None:
            axis_max = max(data_max, axis_min + 1)
        if axis_max <= axis_min:
            axis_max = axis_min + 1

        axis_range = axis_max - axis_min
        major_unit = value_axis_info.get("major_unit")
        tick_values = self._generate_axis_ticks(axis_min, axis_max, major_unit)
        grid_color = value_axis_info.get("grid_color") or "#d1d5db"
        value_axis_position = value_axis_info.get("position", "l")
        category_axis_position = category_axis_info.get("position", "b")
        show_zero_line = axis_min <= 0 <= axis_max

        columns_html = []
        for idx, category in enumerate(categories):
            bars = []
            for ser in series:
                value = ser["values"][idx] if idx < len(ser["values"]) else 0
                relative = (value - axis_min) / axis_range
                height_pct = max(min(relative * 100, 100), 0)
                bars.append(
                    f'<div class="flex-1 rounded-sm" style="height:{height_pct}%; background:{ser["color"]};" title="{ser["name"]}: {value}"></div>'
                )
            bars_html = f'<div class="flex items-end gap-1 w-full h-full min-h-[80px]">{"".join(bars)}</div>'
            label_spacing = "mb-2" if category_axis_position == "t" else "mt-2"
            label_html = f'<div class="text-xs text-center {label_spacing} text-[#1f2933]">{category}</div>'
            if category_axis_position == "t":
                column_content = f"{label_html}{bars_html}"
            else:
                column_content = f"{bars_html}{label_html}"
            columns_html.append(
                f'<div class="flex-1 flex flex-col items-center h-full" style="min-width:40px;">{column_content}</div>'
            )

        legend_items = []
        for ser in series:
            legend_items.append(
                f'<div class="flex items-center gap-2 text-xs text-[#1f2933]">'
                f'<span class="w-3 h-3 rounded-sm inline-block" style="background:{ser["color"]};"></span>'
                f"{ser['name']}</div>"
            )

        axis_labels_html = "".join(
            f'<div class="flex-1 flex items-center justify-end text-[11px] text-[#4b5563] leading-none">{self._format_axis_value(val)}</div>'
            for val in reversed(tick_values)
        )
        axis_column = f'<div class="flex flex-col justify-between pr-2 min-w-[48px] h-full">{axis_labels_html}</div>'

        gridlines = []
        zero_drawn = False
        for tick in tick_values:
            pct = (tick - axis_min) / axis_range * 100 if axis_range else 0
            pct = max(min(pct, 100), 0)
            if show_zero_line and abs(tick) < 1e-6:
                zero_drawn = True
                continue
            gridlines.append(
                f'<div class="absolute left-0 right-0 border-t opacity-60" style="bottom:{pct}%; border-color:{grid_color};"></div>'
            )

        if show_zero_line and not zero_drawn:
            zero_pct = (0 - axis_min) / axis_range * 100 if axis_range else 0
            zero_pct = max(min(zero_pct, 100), 0)
            gridlines.append(
                '<div class="absolute left-0 right-0 border-t" style="bottom:{:.2f}%; border-color:#4b5563; border-width:1.5px;"></div>'.format(
                    zero_pct
                )
            )

        padding_top = "pt-6" if category_axis_position == "t" else "pt-2"
        padding_bottom = "pb-2" if category_axis_position == "t" else "pb-6"
        bars_wrapper = (
            f'<div class="relative flex-1">'
            f'<div class="absolute inset-0 pointer-events-none">{"".join(gridlines)}</div>'
            f'<div class="relative flex items-end gap-3 h-full {padding_top} {padding_bottom} z-10">{"".join(columns_html)}</div>'
            "</div>"
        )

        if value_axis_position == "r":
            plot_content = f'<div class="flex flex-1 gap-3 items-stretch">{bars_wrapper}{axis_column}</div>'
        else:
            plot_content = f'<div class="flex flex-1 gap-3 items-stretch">{axis_column}{bars_wrapper}</div>'

        chart_core = f'<div class="flex flex-1 flex-col">{plot_content}</div>'

        def build_legend_block(position: str) -> str:
            if not legend_items:
                return ""
            if position in ("l", "r"):
                return f'<div class="flex flex-col gap-2 text-xs text-[#1f2933] min-w-[140px]">{"".join(legend_items)}</div>'
            justify = "justify-start"
            if position == "tr":
                justify = "justify-end"
            elif position == "b":
                justify = "justify-start"
            elif position == "t":
                justify = "justify-start"
            return f'<div class="flex flex-wrap gap-4 text-xs text-[#1f2933] {justify}">{"".join(legend_items)}</div>'

        legend_block = build_legend_block(legend_position)

        if legend_block:
            if legend_position == "t":
                body_html = f'<div class="flex flex-col gap-3 h-full">{legend_block}{chart_core}</div>'
            elif legend_position == "tr":
                body_html = f'<div class="flex flex-col gap-3 h-full"><div class="flex justify-end">{legend_block}</div>{chart_core}</div>'
            elif legend_position == "l":
                body_html = f'<div class="flex flex-row gap-4 items-stretch h-full">{legend_block}{chart_core}</div>'
            elif legend_position == "r":
                body_html = f'<div class="flex flex-row gap-4 items-stretch h-full">{chart_core}{legend_block}</div>'
            else:  # default bottom
                body_html = f'<div class="flex flex-col gap-3 h-full">{chart_core}{legend_block}</div>'
        else:
            body_html = chart_core

        classes = [
            "absolute",
            f"left-[{x}px]",
            f"top-[{y}px]",
            f"w-[{w}px]",
            f"h-[{h}px]",
            "p-4",
            "flex",
            "flex-col",
            "justify-between",
            "rounded",
            "bg-white/70",
            "backdrop-blur-sm",
        ]

        return f'''
        <div class="{" ".join(classes)} overflow-hidden">
            {body_html}
        </div>
        '''

    def _extract_chart_data(self, chart_xml) -> Optional[Dict[str, List]]:
        plot_area = chart_xml.find(".//c:plotArea", CHART_NS)
        if plot_area is None:
            return None

        chart_node = None
        for tag_name in ("c:barChart", "c:barChart", "c:colChart"):
            chart_node = plot_area.find(tag_name, CHART_NS)
            if chart_node is not None:
                break

        if chart_node is None:
            return None

        categories: List[str] = []
        cat_node = chart_node.find("c:cat", CHART_NS)
        if cat_node is not None:
            categories = self._extract_chart_categories(cat_node)
        if not categories:
            for ser_node in chart_node.findall("c:ser", CHART_NS):
                ser_cat_node = ser_node.find("c:cat", CHART_NS)
                if ser_cat_node is None:
                    continue
                categories = self._extract_chart_categories(ser_cat_node)
                if categories:
                    break

        series = []
        max_points = len(categories)
        for idx, ser in enumerate(chart_node.findall("c:ser", CHART_NS)):
            name = self._extract_chart_text(ser.find("c:tx", CHART_NS))
            if not name:
                name = f"Series {idx + 1}"
            color = self._extract_chart_color(ser, idx)
            values = self._extract_chart_values(ser.find("c:val", CHART_NS), max_points)
            if not categories and values:
                max_points = len(values)
                categories = [f"Cat {i + 1}" for i in range(max_points)]
            if max_points and len(values) < max_points:
                values.extend([0.0] * (max_points - len(values)))
            series.append({"name": name, "color": color, "values": values})

        if not categories and series:
            max_points = max((len(ser["values"]) for ser in series), default=0)
            categories = [f"Cat {i + 1}" for i in range(max_points)]
            for ser in series:
                if len(ser["values"]) < max_points:
                    ser["values"].extend([0.0] * (max_points - len(ser["values"])))

        axes_info = self._extract_axes_info(plot_area)
        legend_position = self._extract_legend_position(chart_xml)

        return {
            "categories": categories,
            "series": series,
            "axes": axes_info,
            "legend_position": legend_position,
        }

    def _extract_axes_info(self, plot_area) -> Dict[str, Dict]:
        axes = {
            "category": {"position": "b"},
            "value": {
                "position": "l",
                "min": None,
                "max": None,
                "major_unit": None,
                "grid_color": "#d1d5db",
            },
        }

        if plot_area is None:
            return axes

        cat_ax = plot_area.find("c:catAx", CHART_NS)
        if cat_ax is not None:
            ax_pos = cat_ax.find("c:axPos", CHART_NS)
            if ax_pos is not None and ax_pos.get("val"):
                axes["category"]["position"] = ax_pos.get("val")

        val_ax = plot_area.find("c:valAx", CHART_NS)
        if val_ax is not None:
            ax_pos = val_ax.find("c:axPos", CHART_NS)
            if ax_pos is not None and ax_pos.get("val"):
                axes["value"]["position"] = ax_pos.get("val")

            scaling = val_ax.find("c:scaling", CHART_NS)
            if scaling is not None:
                min_node = scaling.find("c:min", CHART_NS)
                max_node = scaling.find("c:max", CHART_NS)
                try:
                    if min_node is not None and min_node.get("val"):
                        axes["value"]["min"] = float(min_node.get("val"))
                except ValueError:
                    axes["value"]["min"] = None
                try:
                    if max_node is not None and max_node.get("val"):
                        axes["value"]["max"] = float(max_node.get("val"))
                except ValueError:
                    axes["value"]["max"] = None

            major_unit = val_ax.find("c:majorUnit", CHART_NS)
            if major_unit is not None and major_unit.get("val"):
                try:
                    axes["value"]["major_unit"] = float(major_unit.get("val"))
                except ValueError:
                    axes["value"]["major_unit"] = None

            gridlines = val_ax.find("c:majorGridlines", CHART_NS)
            if gridlines is not None:
                line = gridlines.find(".//a:ln", PPT_NS)
                if line is not None:
                    axes["value"]["grid_color"] = self._resolve_color(
                        line, default="#d1d5db"
                    )

        return axes

    def _extract_legend_position(self, chart_xml) -> str:
        legend = chart_xml.find(".//c:legend", CHART_NS)
        if legend is None:
            return "b"
        legend_pos = legend.find("c:legendPos", CHART_NS)
        if legend_pos is not None and legend_pos.get("val"):
            return legend_pos.get("val")
        return "b"

    def _generate_axis_ticks(
        self, axis_min: float, axis_max: float, major_unit: Optional[float]
    ) -> List[float]:
        if axis_max <= axis_min:
            return [round(axis_min, 2), round(axis_max, 2)]

        span = axis_max - axis_min
        desired_ticks = 5

        if major_unit is not None and major_unit > 0:
            step = major_unit
        else:
            raw_step = span / max(desired_ticks - 1, 1)
            step = self._nice_step(raw_step)

        start = math.floor(axis_min / step) * step
        ticks: List[float] = []
        current = start
        limit = axis_max + step
        while current <= limit:
            if current >= axis_min - step * 0.5:
                ticks.append(round(current, 4))
            current += step

        if not ticks or ticks[0] > axis_min + 1e-6:
            ticks.insert(0, round(axis_min, 4))
        if ticks[-1] < axis_max - 1e-6:
            ticks.append(round(axis_max, 4))

        # Ensure unique sorted values
        unique_ticks = sorted({round(val, 4) for val in ticks})
        return unique_ticks

    def _nice_step(self, raw_step: float) -> float:
        if raw_step <= 0:
            return 1.0
        exponent = math.floor(math.log10(raw_step))
        fraction = raw_step / (10**exponent)
        if fraction <= 1:
            nice_fraction = 1
        elif fraction <= 2:
            nice_fraction = 2
        elif fraction <= 5:
            nice_fraction = 5
        else:
            nice_fraction = 10
        return nice_fraction * (10**exponent)

    def _format_axis_value(self, value: float) -> str:
        if abs(value) >= 1000:
            return f"{value:,.0f}"
        if abs(value - round(value)) < 1e-6:
            return str(int(round(value)))
        if abs(value) >= 1:
            return f"{value:.1f}"
        return f"{value:.2f}"

    def _extract_chart_categories(self, cat_node) -> List[str]:
        if cat_node is None:
            return []
        cache = cat_node.find(".//c:strCache", CHART_NS)
        if cache is None:
            cache = cat_node.find(".//c:numCache", CHART_NS)
        if cache is None:
            return []

        values: Dict[int, str] = {}
        for pt in cache.findall("c:pt", CHART_NS):
            try:
                idx = int(pt.get("idx", "0"))
            except ValueError:
                continue
            v = pt.find("c:v", CHART_NS)
            if v is not None:
                values[idx] = v.text or ""

        if not values:
            return []

        max_idx = max(values.keys())
        return [values.get(i, f"Cat {i + 1}") for i in range(max_idx + 1)]

    def _extract_chart_values(self, val_node, target_len: int) -> List[float]:
        if val_node is None:
            return [0.0] * target_len
        num_cache = val_node.find(".//c:numCache", CHART_NS)
        if num_cache is None:
            return [0.0] * target_len

        values: Dict[int, float] = {}
        for pt in num_cache.findall("c:pt", CHART_NS):
            try:
                idx = int(pt.get("idx", "0"))
                val = float(pt.find("c:v", CHART_NS).text or 0)
            except (ValueError, AttributeError):
                continue
            values[idx] = val

        if not values:
            return [0.0] * target_len

        if target_len == 0:
            target_len = max(values.keys()) + 1

        return [values.get(i, 0.0) for i in range(target_len)]

    def _extract_chart_text(self, tx_node) -> str:
        if tx_node is None:
            return ""
        v = tx_node.find(".//c:v", CHART_NS)
        if v is not None and v.text:
            return v.text
        return ""

    def _extract_chart_color(self, ser, series_index: int) -> str:
        if ser is not None:
            spPr = ser.find("c:spPr", CHART_NS)
            if spPr is not None:
                srgb = spPr.find(".//a:srgbClr", PPT_NS)
                if srgb is not None and srgb.get("val"):
                    return f"#{srgb.get('val')}"

        palette = ["#2563EB", "#F97316", "#0EA5E9", "#10B981", "#EC4899", "#FACC15"]
        return palette[series_index % len(palette)]

    async def _process_shapes(
        self,
        tree,
        rels,
        parent_transform=None,
        skip_placeholders=False,
        placeholder_xfrm_map: Optional[
            Dict[Tuple[str, Optional[str]], Dict[str, str]]
        ] = None,
        placeholder_text_styles: Optional[
            Dict[Tuple[str, Optional[str]], Dict[int, List[etree._Element]]]
        ] = None,
        placeholder_paragraph_styles: Optional[
            Dict[Tuple[str, Optional[str]], Dict[int, List[etree._Element]]]
        ] = None,
        placeholder_bodypr_map: Optional[
            Dict[Tuple[str, Optional[str]], etree._Element]
        ] = None,
        group_fill_color: Optional[str] = None,
    ) -> str:
        if tree is None:
            return ""
        html_out = []

        for child in tree:
            tag = get_tag_name(child)
            if tag in ("sp", "pic", "cxnSp"):
                html_out.append(
                    await self._render_shape(
                        child,
                        rels,
                        parent_transform,
                        skip_placeholders,
                        placeholder_xfrm_map,
                        placeholder_text_styles,
                        placeholder_paragraph_styles,
                        placeholder_bodypr_map,
                        group_fill_color,
                    )
                )
            elif tag == "grpSp":
                # Parse Group Recursively
                grpSpPr = child.find("p:grpSpPr", PPT_NS)
                new_transform = parent_transform
                group_rotation = 0
                group_container_html = None
                group_color = group_fill_color

                if grpSpPr is not None:
                    group_color = self._resolve_color(grpSpPr, default=group_fill_color)
                    xfrm = grpSpPr.find("a:xfrm", PPT_NS)
                    if xfrm is not None:
                        off = xfrm.find("a:off", PPT_NS)
                        ext = xfrm.find("a:ext", PPT_NS)
                        chOff = xfrm.find("a:chOff", PPT_NS)
                        chExt = xfrm.find("a:chExt", PPT_NS)
                        flip_h = xfrm.get("flipH") in ("1", "true")
                        flip_v = xfrm.get("flipV") in ("1", "true")

                        # Extract rotation from group
                        group_rotation = int(xfrm.get("rot", 0)) / 60000

                        if (
                            off is not None
                            and ext is not None
                            and chOff is not None
                            and chExt is not None
                        ):
                            offx = emu_to_px(off.get("x"))
                            offy = emu_to_px(off.get("y"))
                            extcx = emu_to_px(ext.get("cx"))
                            extcy = emu_to_px(ext.get("cy"))
                            chOffx = emu_to_px(chOff.get("x"))
                            chOffy = emu_to_px(chOff.get("y"))
                            chExtcx = emu_to_px(chExt.get("cx"))
                            chExtcy = emu_to_px(chExt.get("cy"))

                            scale_x = extcx / chExtcx if chExtcx != 0 else 1
                            scale_y = extcy / chExtcy if chExtcy != 0 else 1

                            # Compose with parent transform if it exists
                            if parent_transform:
                                # Apply parent transform to group position
                                px = parent_transform["offx"]
                                py = parent_transform["offy"]
                                psx = parent_transform["scale_x"]
                                psy = parent_transform["scale_y"]
                                pchx = parent_transform["chOffx"]
                                pchy = parent_transform["chOffy"]

                                # Transform group position
                                # offx/offy are in pixels (from emu_to_px), need to be transformed through parent
                                transformed_offx = px + (offx - pchx) * psx
                                transformed_offy = py + (offy - pchy) * psy

                                new_transform = {
                                    "offx": transformed_offx,
                                    "offy": transformed_offy,
                                    "scale_x": scale_x * psx,
                                    "scale_y": scale_y * psy,
                                    "chOffx": chOffx,
                                    "chOffy": chOffy,
                                    "chExtcx": chExtcx,
                                    "chExtcy": chExtcy,
                                    "flipH": flip_h,
                                    "flipV": flip_v,
                                    "rotation": group_rotation
                                    + (parent_transform.get("rotation", 0)),
                                }
                            else:
                                # No parent - scale position by slide scale factor
                                # scale_x and scale_y are ratios, they will be applied to child positions
                                # which are in pixels (from emu_to_px), so we need to include slide scale in the scale factors
                                # chOffx and chOffy are in the same units as child positions (pixels from emu_to_px, not scaled)
                                new_transform = {
                                    "offx": offx * self.scale_factor,
                                    "offy": offy * self.scale_factor,
                                    "scale_x": scale_x * self.scale_factor,
                                    "scale_y": scale_y * self.scale_factor,
                                    "chOffx": chOffx,
                                    "chOffy": chOffy,
                                    "chExtcx": chExtcx,
                                    "chExtcy": chExtcy,
                                    "flipH": flip_h,
                                    "flipV": flip_v,
                                    "rotation": group_rotation,
                                }

                            # If group has rotation, wrap children in a rotated container
                            if group_rotation != 0:
                                # For rotated groups in PowerPoint:
                                # - Rotation happens around the center of the group's bounding box (ext)
                                # - Children are positioned relative to chOff in group coordinates
                                # - The group's bounding box is at off with size ext

                                # Calculate transformed group position for container
                                # Note: scale_x and scale_y are the scale from chExt to ext (group's internal scale)
                                # For the container size, we need the slide scale factor, not the group's internal scale

                                if parent_transform:
                                    # Parent transform: px, py are in screen coordinates (already scaled)
                                    # psx, psy include the slide scale factor
                                    # pchx, pchy are in the parent's child coordinate system (not scaled)
                                    px = parent_transform["offx"]
                                    py = parent_transform["offy"]
                                    psx = parent_transform["scale_x"]
                                    psy = parent_transform["scale_y"]
                                    pchx = parent_transform["chOffx"]
                                    pchy = parent_transform["chOffy"]

                                    # Transform group position through parent
                                    # offx/offy are in pixels (from emu_to_px), need to be in parent's coordinate system
                                    # The parent's scale_x already includes slide_scale, so we need to account for that
                                    # Group position in parent's child coordinate system: (offx - pchx)
                                    # Then scale by parent's scale: (offx - pchx) * psx
                                    # Then add parent's position: px + (offx - pchx) * psx
                                    # But offx needs to be scaled first to match parent's coordinate system
                                    container_x = px + (
                                        offx * self.scale_factor
                                        - pchx * self.scale_factor
                                    ) * (psx / self.scale_factor)
                                    container_y = py + (
                                        offy * self.scale_factor
                                        - pchy * self.scale_factor
                                    ) * (psy / self.scale_factor)

                                    # Simplify: (a - b) * c / d = (a * c - b * c) / d
                                    # Actually: (offx * scale - pchx * scale) * (psx / scale) = (offx - pchx) * psx
                                    container_x = px + (offx - pchx) * psx
                                    container_y = py + (offy - pchy) * psy

                                    # For children positioning, use the combined scale
                                    final_scale_x = scale_x * psx
                                    final_scale_y = scale_y * psy
                                else:
                                    # No parent - scale position by slide scale factor
                                    container_x = offx * self.scale_factor
                                    container_y = offy * self.scale_factor
                                    # For children positioning, use the group's scale multiplied by slide scale
                                    final_scale_x = scale_x * self.scale_factor
                                    final_scale_y = scale_y * self.scale_factor

                                # Container size should be ext scaled by slide scale factor
                                slide_scale_x = self.scale_factor
                                slide_scale_y = self.scale_factor

                                # In PowerPoint, rotation happens around the center of the group's bounding box (ext)
                                # The group's bounding box center is at: (off.x + ext.cx/2, off.y + ext.cy/2)
                                #
                                # Children are positioned relative to chOff in the group's coordinate system.
                                # A child at (x, y) relative to chOff is at (off.x + chOff.x + x, off.y + chOff.y + y)
                                # in slide coordinates BEFORE rotation.
                                #
                                # When we create a container:
                                # - Container is at (off.x * scale, off.y * scale) with size (ext.cx * scale, ext.cy * scale)
                                # - Container center (rotation point) is at (ext.cx * scale / 2, ext.cy * scale / 2) in container coords
                                # - Child at (x, y) relative to chOff should be at (chOff.x * scale + x * scale, chOff.y * scale + y * scale)
                                #   in container coordinates, but we need to account for the scale_x/scale_y which is ext/chExt
                                #
                                # The transform calculation: new_x = px + (x - chx) * sx
                                # Where px=0 (container origin), x=child position, chx=chOff, sx=scale_x
                                # This gives: new_x = (child_x - chOffx) * scale_x
                                # But we want: new_x = chOffx * slide_scale + (child_x - chOffx) * scale_x
                                # Actually, we want the child at its absolute position in the container

                                # In PowerPoint, rotation happens around the center of the group's bounding box.
                                # Children are positioned relative to chOff in the group's coordinate system.
                                #
                                # The key insight: When we rotate a container in CSS, children rotate with it
                                # around the container's center. So we need to position children at their
                                # correct positions in the container, and the rotation will handle the rest.
                                #
                                # Child at (x, y) relative to chOff should be positioned at:
                                #   (chOff.x + x) * slide_scale in container coordinates
                                # But we also need to account for the scale from child coords to group coords.
                                #
                                # The transform calculation: new_x = px + (x - chx) * sx
                                # Where sx = (ext.cx / chExt.cx) * slide_scale
                                # This scales from child coordinate system to container coordinate system.
                                #
                                # So if child is at (x, y) relative to chOff:
                                #   new_x = 0 + (x - chOffx) * sx
                                #   = (x - chOffx) * (ext.cx / chExt.cx) * slide_scale
                                #
                                # But we want: (chOffx + x) * slide_scale
                                # So we need: new_x = chOffx * slide_scale + (x - chOffx) * sx
                                #           = chOffx * slide_scale + x * sx - chOffx * sx
                                #           = chOffx * (slide_scale - sx) + x * sx
                                #
                                # Actually, let's think differently. The transform positions children
                                # relative to chOff, scaled by sx. So a child at (0, 0) relative to chOff
                                # will be at (0, 0) in the container. But we want it at (chOffx * slide_scale, chOffy * slide_scale).
                                #
                                # So we need to offset by chOffx * slide_scale:

                                # The correct approach: Children should be positioned at their locations
                                # in the group's coordinate system, scaled to container coordinates.
                                #
                                # A child at (x, y) relative to chOff is at (chOffx + x, chOffy + y) in group coords.
                                # In container coordinates (scaled), this is:
                                #   ((chOffx + x) * slide_scale, (chOffy + y) * slide_scale)
                                #
                                # But the transform calculation does: new_x = px + (x - chx) * sx
                                # where sx = (ext.cx / chExt.cx) * slide_scale
                                #
                                # For a child at (x, y) relative to chOff:
                                #   new_x = 0 + (x - chOffx) * sx
                                #        = (x - chOffx) * (ext.cx / chExt.cx) * slide_scale
                                #
                                # We want: (chOffx + x) * slide_scale
                                # So we need to adjust: new_x = chOffx * slide_scale + (x - chOffx) * sx
                                #
                                # This simplifies to positioning children at chOff location, then offsetting by child position
                                # Actually, let's use the transform correctly:
                                # - Set container origin offset to chOff location
                                # - Children are then positioned relative to that

                                # Position children at chOff location in container (scaled)
                                chOff_container_x = chOffx * self.scale_factor
                                chOff_container_y = chOffy * self.scale_factor

                                group_relative_transform = {
                                    "offx": chOff_container_x,  # Container offset to chOff location
                                    "offy": chOff_container_y,
                                    "scale_x": final_scale_x,  # Scales from child coords to container coords
                                    "scale_y": final_scale_y,
                                    "chOffx": 0,  # Children are relative to chOff, which is now at container origin
                                    "chOffy": 0,
                                    "chExtcx": chExtcx,
                                    "chExtcy": chExtcy,
                                    "flipH": flip_h,
                                    "flipV": flip_v,
                                    "rotation": parent_transform.get("rotation", 0)
                                    if parent_transform
                                    else 0,
                                }

                                # Process children with group-relative transform
                                children_html = await self._process_shapes(
                                    child,
                                    rels,
                                    group_relative_transform,
                                    skip_placeholders=False,
                                    placeholder_xfrm_map=placeholder_xfrm_map,
                                    placeholder_text_styles=placeholder_text_styles,
                                    placeholder_paragraph_styles=placeholder_paragraph_styles,
                                    placeholder_bodypr_map=placeholder_bodypr_map,
                                    group_fill_color=group_color,
                                )

                                # Create container positioned at group location with rotation
                                # Container should be sized to ext (group's bounding box) scaled by slide scale
                                container_w = extcx * slide_scale_x
                                container_h = extcy * slide_scale_y

                                # Round container dimensions (already scaled)
                                container_x = round_dimension(container_x)
                                container_y = round_dimension(container_y)
                                container_w = round_dimension(container_w)
                                container_h = round_dimension(container_h)
                                group_rotation = round_dimension(group_rotation)

                                container_classes = [
                                    "absolute",
                                    f"left-[{container_x}px]",
                                    f"top-[{container_y}px]",
                                    f"w-[{container_w}px]",
                                    f"h-[{container_h}px]",
                                    f"rotate-[{group_rotation}deg]",
                                    "origin-center",
                                ]

                                group_container_html = f'<div class="{" ".join(container_classes)} overflow-visible">{children_html}</div>'

                # Add group content (either rotated container or directly processed children)
                if group_container_html:
                    html_out.append(group_container_html)
                elif new_transform != parent_transform:
                    # Group has transform, process children with it
                    html_out.append(
                        await self._process_shapes(
                            child,
                            rels,
                            new_transform,
                            skip_placeholders=False,
                            placeholder_xfrm_map=placeholder_xfrm_map,
                            placeholder_text_styles=placeholder_text_styles,
                            placeholder_paragraph_styles=placeholder_paragraph_styles,
                            placeholder_bodypr_map=placeholder_bodypr_map,
                            group_fill_color=group_color,
                        )
                    )
                else:
                    # Group transform matches parent; still process children
                    html_out.append(
                        await self._process_shapes(
                            child,
                            rels,
                            parent_transform,
                            skip_placeholders=False,
                            placeholder_xfrm_map=placeholder_xfrm_map,
                            placeholder_text_styles=placeholder_text_styles,
                            placeholder_paragraph_styles=placeholder_paragraph_styles,
                            placeholder_bodypr_map=placeholder_bodypr_map,
                            group_fill_color=group_color,
                        )
                    )
            elif tag == "graphicFrame":
                print("DEBUG: Found graphicFrame")
                # Check for table
                tbl = child.find(".//a:tbl", PPT_NS)
                if tbl is not None:
                    html_out.append(self._render_table(child, rels))
                else:
                    chart = child.find(".//c:chart", CHART_NS)
                    if chart is not None:
                        chart_html = self._render_chart(child, rels)
                        if chart_html:
                            html_out.append(chart_html)
                        else:
                            print("DEBUG: Failed to render chart")
                    else:
                        print("DEBUG: graphicFrame is not a table")
        return "\n".join(html_out)

    async def parse(self, max_slides: int = None):
        # 1. Parse Presentation XML
        presentation = self._read_xml("ppt/presentation.xml")
        if presentation is None:
            raise ValueError("Invalid PPTX: ppt/presentation.xml not found")

        self._load_theme()

        # Get dimensions
        sldSz = presentation.find("p:sldSz", PPT_NS)
        if sldSz is not None:
            original_width = emu_to_px(sldSz.get("cx"))
            original_height = emu_to_px(sldSz.get("cy"))

            # Calculate scale factor to resize to target width (1280px) while maintaining aspect ratio
            if original_width > 0:
                self.scale_factor = self.target_width / original_width
                self.width = round_dimension(self.target_width)
                self.height = round_dimension(original_height * self.scale_factor)
            else:
                self.width = round_dimension(original_width)
                self.height = round_dimension(original_height)

        # Get Slides List
        sld_id_lst = presentation.find("p:sldIdLst", PPT_NS)
        pres_rels = self._get_rels("ppt/presentation.xml")
        self._load_embedded_fonts(presentation, pres_rels)

        if sld_id_lst is None:
            return

        slides_parsed = 0
        for sldId in sld_id_lst.findall("p:sldId", PPT_NS):
            if max_slides is not None and slides_parsed >= max_slides:
                break
            r_id = sldId.get(f"{{{PPT_NS['r']}}}id")
            if r_id in pres_rels:
                slide_info = pres_rels[r_id]
                await self._parse_slide_hierarchy(slide_info["path"])
                slides_parsed += 1

    async def _parse_slide_hierarchy(self, slide_path):
        """Builds the HTML by stacking Master -> Layout -> Slide."""
        self.current_slide_fonts = set()

        # 1. Read Slide
        slide_xml = self._read_xml(slide_path)
        if slide_xml is None:
            self.current_slide_fonts = None
            return
        slide_rels = self._get_rels(slide_path)

        # 2. Find Layout
        layout_path = None
        for r in slide_rels.values():
            # Check for standard relationship type for slideLayout
            if "slideLayout" in r["type"]:
                layout_path = r["path"]
                break

        print(f"DEBUG: Slide: {slide_path}, Layout: {layout_path}")

        # 3. Read Layout & Find Master
        layout_xml = None
        layout_rels = {}
        master_path = None

        if layout_path:
            layout_xml = self._read_xml(layout_path)
            layout_rels = self._get_rels(layout_path)
            for r in layout_rels.values():
                if "slideMaster" in r["type"]:
                    master_path = r["path"]
                    break

        print(f"DEBUG: Master: {master_path}")

        # 4. Read Master
        master_xml = None
        master_rels = {}
        if master_path:
            master_xml = self._read_xml(master_path)
            master_rels = self._get_rels(master_path)
        self.color_map = self._load_color_map(master_xml)
        self.default_text_color = None
        if master_xml is not None:
            tx_styles = master_xml.find("p:txStyles", PPT_NS)
            if tx_styles is not None:
                for style_name in ("p:otherStyle", "p:bodyStyle", "p:titleStyle"):
                    style_elem = tx_styles.find(style_name, PPT_NS)
                    if style_elem is None:
                        continue
                    lvl_pr = style_elem.find("a:lvl1pPr", PPT_NS)
                    if lvl_pr is None:
                        continue
                    def_rpr = lvl_pr.find("a:defRPr", PPT_NS)
                    if def_rpr is None:
                        continue
                    color_val = self._resolve_color(def_rpr, default=None)
                    if color_val and color_val != "transparent":
                        self.default_text_color = color_val
                        break

        # 5. Render Layers (Bottom to Top)
        layers = []
        placeholder_xfrm_map = self._build_placeholder_xfrm_map(layout_xml, master_xml)
        placeholder_text_styles = self._build_placeholder_text_style_map(
            layout_xml, master_xml
        )
        placeholder_paragraph_styles = self._build_placeholder_paragraph_style_map(
            layout_xml, master_xml
        )
        placeholder_bodypr_map = self._build_placeholder_bodypr_map(
            layout_xml, master_xml
        )

        # Master - skip placeholders
        if master_xml is not None:
            spTree = master_xml.find(".//p:spTree", PPT_NS)
            if spTree is not None:
                print("DEBUG: Processing Master Shapes")
                layers.append(
                    await self._process_shapes(
                        spTree,
                        master_rels,
                        skip_placeholders=True,
                        placeholder_xfrm_map=None,
                        placeholder_text_styles=None,
                        placeholder_paragraph_styles=None,
                        placeholder_bodypr_map=None,
                    )
                )

        # Layout - skip placeholders
        if layout_xml is not None:
            spTree = layout_xml.find(".//p:spTree", PPT_NS)
            if spTree is not None:
                print("DEBUG: Processing Layout Shapes")
                layers.append(
                    await self._process_shapes(
                        spTree,
                        layout_rels,
                        skip_placeholders=True,
                        placeholder_xfrm_map=None,
                        placeholder_text_styles=None,
                        placeholder_paragraph_styles=None,
                        placeholder_bodypr_map=None,
                    )
                )

        # Slide
        spTree = slide_xml.find(".//p:spTree", PPT_NS)
        if spTree is not None:
            print("DEBUG: Processing Slide Shapes")
            layers.append(
                await self._process_shapes(
                    spTree,
                    slide_rels,
                    placeholder_xfrm_map=placeholder_xfrm_map,
                    placeholder_text_styles=placeholder_text_styles,
                    placeholder_paragraph_styles=placeholder_paragraph_styles,
                    placeholder_bodypr_map=placeholder_bodypr_map,
                )
            )

        # Determine background (slide > layout > master)
        slide_bg_elem = slide_xml.find("p:cSld/p:bg", PPT_NS)
        slide_bg_color, slide_bg_image = await self._extract_background_info(
            slide_bg_elem, slide_rels
        )
        layout_bg_color, layout_bg_image = (
            await self._extract_background_info(
                layout_xml.find("p:cSld/p:bg", PPT_NS), layout_rels
            )
            if layout_xml is not None
            else (None, "")
        )
        master_bg_color, master_bg_image = (
            await self._extract_background_info(
                master_xml.find("p:cSld/p:bg", PPT_NS), master_rels
            )
            if master_xml is not None
            else (None, "")
        )

        bg_color = slide_bg_color or layout_bg_color or master_bg_color or "white"
        bg_image_style = slide_bg_image or layout_bg_image or master_bg_image or ""

        fonts_used = (
            sorted(self.current_slide_fonts) if self.current_slide_fonts else []
        )
        self.slides_data.append(
            {
                "html": "\n".join(layers),
                "bg_color": bg_color,
                "bg_extra_style": bg_image_style,
                "fonts": fonts_used,
            }
        )
        self.current_slide_fonts = None

    async def get_slides_html_and_fonts(
        self, get_fonts: bool = False
    ) -> Tuple[List[str], str]:
        """
        Build slides HTML and collect all fonts used across all slides.

        Returns:
            Tuple[str, str]: A tuple containing (slides_html_string, font_css_string)
        """
        if not self.slides_data:
            return "", ""

        # Collect all unique fonts from all slides
        all_fonts = set()
        for slide in self.slides_data:
            all_fonts.update(slide.get("fonts", []))

        # Build font CSS once for all fonts
        if get_fonts:
            font_css = await self._build_font_face_css(sorted(all_fonts))
        else:
            font_css = ""

        slides_html = []
        for i, slide in enumerate(self.slides_data):
            # Slide background is resolved during parsing (slide > layout > master)
            # so we get a color class and may append inline styles for images.
            bg_color = slide.get("bg_color") or "white"
            bg_class = f"bg-[{bg_color}]" if bg_color else "bg-white"
            extra_bg_style = slide.get("bg_extra_style", "")
            style_parts = [f"width:{self.width}px;", f"height:{self.height}px;"]
            if extra_bg_style:
                style_parts.append(extra_bg_style)
            style_attr = " ".join(style_parts)

            slides_html.append(f"""
            <div class="slide-container mb-5 flex justify-center" id="slide-{i + 1}">
                <div class="slide-content relative overflow-hidden shadow-lg {bg_class}" style="{style_attr}">
                    {slide["html"]}
                </div>
            </div>
            """)

        return slides_html, font_css

    async def to_html(self, output_file: str, get_fonts: bool = False):
        await asyncio.to_thread(
            os.makedirs,
            os.path.dirname(output_file),
            exist_ok=True,
        )

        if not self.slides_data:
            print("No slides found or parsed.")
            return

        slides_html, font_css = await self.get_slides_html_and_fonts(get_fonts)
        slides_html = "\n".join(slides_html)

        full_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Presentation</title>
            <script src="https://cdn.tailwindcss.com"></script>
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;700&display=swap" rel="stylesheet">
            {font_css}
            <style>
                /* Custom scrollbar or other global resets if needed */
                body {{ background: #222; margin: 0; padding: 20px; font-family: 'Inter', sans-serif; }}
            </style>
        </head>
        <body class="bg-[#222] p-5 font-sans m-0">
            {slides_html}
        </body>
        </html>
        """

        try:
            await asyncio.to_thread(_write_text_file, output_file, full_html)
            print(f"Done! Saved to {output_file}")
        except Exception as e:
            print(f"Error writing HTML: {e}")


async def convert_pptx_to_slides_in_thread(
    pptx_path: str,
    user: uuid.UUID,
    max_slides: int | None = None,
    *,
    use_temporary_bucket: bool = False,
    get_fonts: bool = False,
) -> Tuple[List[str], str, Dict[str, List[Dict[str, str]]]]:
    """
    Run PPTX parsing/rendering in a worker thread so ZIP/XML traversal does not
    block the FastAPI event loop.
    """

    def _convert() -> Tuple[List[str], str, Dict[str, List[Dict[str, str]]]]:
        async def _run_conversion():
            pptx_to_html = PPTXToHTML(
                pptx_path,
                user,
                use_temporary_bucket=use_temporary_bucket,
            )
            try:
                await pptx_to_html.parse(max_slides)
                slide_htmls, font_css = await pptx_to_html.get_slides_html_and_fonts(
                    get_fonts
                )
                uploaded_assets = pptx_to_html.get_font_and_image_urls()
                return slide_htmls, font_css, uploaded_assets
            finally:
                pptx_to_html.close()

        return asyncio.run(_run_conversion())

    return await asyncio.to_thread(_convert)
