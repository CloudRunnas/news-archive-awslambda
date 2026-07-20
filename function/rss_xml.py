"""RSS/Atom-XML in ein JSON-Array von Feed-Items konvertieren."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any

_ITEM_TAGS = frozenset({"item", "entry"})
_XMLNS_DECL_RE = re.compile(r'xmlns:([A-Za-z_][\w.-]*)="([^"]+)"')


def _local_tag(tag: str) -> str:
    if tag.startswith("{"):
        return tag.rsplit("}", 1)[-1]
    return tag


def _build_ns_map(root: ET.Element, xml_text: str) -> dict[str, str]:
    ns_map: dict[str, str] = {}
    for prefix, uri in _XMLNS_DECL_RE.findall(xml_text):
        ns_map[uri] = prefix
    for elem in root.iter():
        for key, value in elem.attrib.items():
            if key.startswith("xmlns:"):
                ns_map[value] = key.split(":", 1)[1]
    return ns_map


def _tag_key(elem: ET.Element, ns_map: dict[str, str]) -> str:
    tag = elem.tag
    if not tag.startswith("{"):
        return tag
    uri, local = tag[1:].split("}", 1)
    prefix = ns_map.get(uri)
    if prefix:
        return f"{prefix}:{local}"
    return local


def _element_to_value(elem: ET.Element, ns_map: dict[str, str]) -> Any:
    attrs = {f"@{k}": v for k, v in elem.attrib.items()}
    children = list(elem)

    if children:
        child_values = _collect_child_elements(elem, ns_map)
        if attrs:
            return {**attrs, **child_values}
        return child_values

    text = (elem.text or "").strip()
    if attrs and text:
        return {**attrs, "#text": text}
    if attrs:
        return attrs
    return text


def _collect_child_elements(
    parent: ET.Element,
    ns_map: dict[str, str],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for child in parent:
        key = _tag_key(child, ns_map)
        value = _element_to_value(child, ns_map)
        if key in result:
            existing = result[key]
            if isinstance(existing, list):
                existing.append(value)
            else:
                result[key] = [existing, value]
        else:
            result[key] = value
    return result


def _item_to_dict(item: ET.Element, ns_map: dict[str, str]) -> dict[str, Any]:
    return _collect_child_elements(item, ns_map)


def rss_xml_to_feed_items(xml_text: str) -> list[dict[str, Any]]:
    """Parst RSS- oder Atom-XML und liefert ein JSON-Array der Feed-Items."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        raise ValueError(f"invalid RSS XML: {e}") from e

    ns_map = _build_ns_map(root, xml_text)
    items: list[dict[str, Any]] = []

    for elem in root.iter():
        if _local_tag(elem.tag) in _ITEM_TAGS:
            items.append(_item_to_dict(elem, ns_map))

    return items
