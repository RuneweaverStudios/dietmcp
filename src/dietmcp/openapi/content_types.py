"""Content type handling for OpenAPI requests and responses."""

import json
import xml.etree.ElementTree as ET
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlencode


class ContentType(str, Enum):
    """Supported content types."""
    JSON = "application/json"
    JSON_API = "application/vnd.api+json"
    XML = "application/xml"
    XML_TEXT = "text/xml"
    FORM_URLENCODED = "application/x-www-form-urlencoded"
    FORM_DATA = "multipart/form-data"
    TEXT = "text/plain"
    HTML = "text/html"


def serialize_request_body(
    data: Dict[str, Any],
    content_type: ContentType
) -> Union[str, bytes, Dict[str, Any]]:
    """Serialize request body according to content type.

    Args:
        data: Data to serialize
        content_type: Target content type

    Returns:
        Serialized body (string, bytes, or dict for form-data)
    """
    if content_type == ContentType.JSON:
        return json.dumps(data)

    elif content_type == ContentType.FORM_URLENCODED:
        return urlencode(data, doseq=True)

    elif content_type == ContentType.FORM_DATA:
        # Return dict, let httpx encode as multipart/form-data
        return data

    elif content_type in (ContentType.XML, ContentType.XML_TEXT):
        # Convert dict to XML
        return _dict_to_xml(data)

    elif content_type == ContentType.TEXT:
        return str(data)

    else:
        return str(data)


def _dict_to_xml(data: Dict[str, Any], root: str = "root") -> str:
    """Convert dict to XML string."""
    parts = []
    for key, value in data.items():
        if isinstance(value, dict):
            nested = _dict_to_xml(value, key)
            parts.append(f"<{key}>{nested}</{key}>")
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    nested = _dict_to_xml(item, "item")
                    parts.append(f"<{key}>{nested}</{key}>")
                else:
                    # Escape XML special characters
                    escaped = str(item).replace("&", "&amp;").replace("<", "&lt;")
                    parts.append(f"<{key}>{escaped}</{key}>")
        else:
            # Escape XML special characters
            escaped = str(value).replace("&", "&amp;").replace("<", "&lt;")
            parts.append(f"<{key}>{escaped}</{key}>")
    return "".join(parts)


def parse_response_body(
    response_text: str,
    content_type: str,
    is_error: bool = False
) -> Dict[str, Any]:
    """Parse response body based on content type.

    Args:
        response_text: Raw response body
        content_type: Content-Type header value
        is_error: Whether this is an error response

    Returns:
        Parsed response as dict
    """
    # Strip charset from content type if present
    content_type_base = content_type.split(";")[0].strip()

    if "application/json" in content_type_base:
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            # If not valid JSON, return as text
            return {"text": response_text, "_raw": response_text}

    elif content_type_base in ("application/xml", "text/xml"):
        try:
            root = ET.fromstring(response_text)
            return _xml_to_dict(root)
        except ET.ParseError:
            return {"text": response_text, "_raw": response_text}

    elif "application/x-www-form-urlencoded" in content_type_base:
        from urllib.parse import parse_qs
        return parse_qs(response_text)

    elif content_type_base in ("text/plain", "text/html"):
        return {"text": response_text}

    else:
        # Unknown content type
        return {"text": response_text, "_raw": response_text}


def _xml_to_dict(element: ET.Element) -> Dict[str, Any]:
    """Convert XML element to dict.

    Args:
        element: XML element

    Returns:
        Parsed dictionary
    """
    result = {}

    # Handle attributes
    if element.attrib:
        result.update(element.attrib)

    # Handle child elements
    for child in element:
        child_data = _xml_to_dict(child)

        # Handle multiple children with same tag
        if child.tag in result:
            # Convert to list if needed
            existing = result[child.tag]
            if isinstance(existing, list):
                existing.append(child_data)
            else:
                result[child.tag] = [existing, child_data]
        else:
            result[child.tag] = child_data

    # Handle text content
    if element.text and element.text.strip():
        if len(result) == 0:
            # Only text content
            return element.text.strip()
        else:
            # Mixed content and children
            result["#text"] = element.text.strip()

    return result


def format_response_for_llm(
    response_data: Dict[str, Any],
    content_type: str,
    max_chars: int = 500
) -> str:
    """Format response for LLM consumption.

    Args:
        response_data: Parsed response data
        content_type: Response content type
        max_chars: Maximum characters to include

    Returns:
        Formatted string for LLM
    """
    if "text" in response_data:
        # Text response
        text = response_data["text"]
        if len(text) > max_chars:
            return f"{text[:max_chars]}..."
        return text

    elif content_type == "application/json":
        # JSON response - extract key fields
        if isinstance(response_data, dict):
            # Get first 3-5 keys with their values
            items = []
            for key, value in list(response_data.items())[:5]:
                if isinstance(value, str):
                    items.append(f"{key}={value[:50]}")
                elif isinstance(value, (int, float, bool)):
                    items.append(f"{key}={value}")
                elif isinstance(value, dict):
                    items.append(f"{key}=...")
            return ", ".join(items)
        return str(response_data)

    else:
        # Fallback to string representation
        return str(response_data)[:max_chars]
