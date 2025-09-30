import xml.etree.ElementTree as ET

from .settings import NAMESPACES


""" def _ns(ns: str, name: str) -> str:
    return f'{{{NAMESPACES[ns]}}}{name}' """


def _register_namespaces() -> None:
    for prefix, uri in NAMESPACES.items():
        ET.register_namespace(prefix, uri)
