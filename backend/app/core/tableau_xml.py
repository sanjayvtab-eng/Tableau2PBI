from __future__ import annotations
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterable, Optional


def parse_xml_file(path: Path) -> ET.Element:
    parser = ET.XMLParser(encoding="utf-8")
    return ET.parse(path, parser=parser).getroot()


def tag_name(elem: ET.Element) -> str:
    return elem.tag.split("}", 1)[-1].lower()


def iter_by_tag(root: ET.Element, name: str) -> Iterable[ET.Element]:
    needle = name.lower()
    for elem in root.iter():
        if tag_name(elem) == needle:
            yield elem


def first_attr(elem: ET.Element, *names: str, default: str | None = None) -> Optional[str]:
    for n in names:
        if n in elem.attrib:
            return elem.attrib[n]
    return default


def text_of(elem: ET.Element) -> str:
    if elem.text:
        return elem.text.strip()
    return ""


def local_id_from_name(value: str | None) -> str:
    if not value:
        return ""
    return value.strip("[]")
