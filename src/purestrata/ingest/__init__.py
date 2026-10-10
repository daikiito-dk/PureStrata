"""Ingestion adapters: manuals, CAD drawings, 3D models, and failure logs."""

from .cad import ingest_dxf
from .failures import ingest_failures
from .manual import ingest_manual
from .step import ingest_step

__all__ = ["ingest_dxf", "ingest_failures", "ingest_manual", "ingest_step"]
