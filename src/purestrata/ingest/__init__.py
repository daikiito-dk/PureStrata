"""Ingestion adapters: manuals, CAD drawings, and failure logs."""

from .cad import ingest_dxf
from .failures import ingest_failures
from .manual import ingest_manual

__all__ = ["ingest_dxf", "ingest_failures", "ingest_manual"]
