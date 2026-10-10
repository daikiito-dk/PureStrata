"""distilabel adapter: feed reviewed PureStrata records into distilabel pipelines.

Requires the optional ``distilabel`` extra for :func:`to_dataset`:

    pip install 'purestrata[distilabel]'

Supported: ``distilabel >= 1.0``. :func:`records_to_examples` is
dependency-free and returns plain dicts ready for distilabel's
``LoadDataFromDicts`` step; :func:`to_dataset` additionally builds a
Hugging Face ``datasets.Dataset``.

Provenance is the contract: every example keeps the full ``sources`` list
and gains flat ``purestrata_*`` columns, so source IDs and locators survive
LLM augmentation steps and end up in the final dataset.
"""

from __future__ import annotations

REVIEWED_FORMATS = ("chat", "tool_trace", "cot")

_PAYLOAD_FIELDS = {
    "chat": ("messages",),
    "tool_trace": ("messages",),
    "cot": ("instruction", "reasoning", "output"),
}

__all__ = ["records_to_examples", "to_dataset"]


def records_to_examples(records: list[dict], format: str | None = None) -> list[dict]:
    """Convert provider-format records into distilabel-ready example rows.

    Accepts records from ``purestrata export`` or from a review bundle's
    approved output (``approved_records``). Each example keeps the provider
    payload (``messages`` or ``instruction``/``reasoning``/``output``) plus
    the full ``sources`` list, and gains flat provenance columns:
    ``purestrata_chunk_ids``, ``purestrata_record_kinds``,
    ``purestrata_doc_ids``, ``purestrata_source_paths``,
    ``purestrata_locators``, ``purestrata_source_sha256``.

    ``format`` ("chat", "tool_trace", or "cot") validates the payload shape
    up front so mismatches fail before a pipeline run, not after.
    """
    if format is not None and format not in REVIEWED_FORMATS:
        raise ValueError(f"Unsupported format: {format}. Use one of {REVIEWED_FORMATS}.")
    examples: list[dict] = []
    for index, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            raise ValueError(f"Record {index} is not a JSON object.")
        sources = record.get("sources")
        if not isinstance(sources, list) or not sources:
            raise ValueError(
                f"Record {index} has no 'sources'; provenance is required for distilabel."
            )
        if format is not None:
            missing = [field for field in _PAYLOAD_FIELDS[format] if field not in record]
            if missing:
                raise ValueError(
                    f"Record {index} does not match the {format} format "
                    f"(missing: {', '.join(missing)})."
                )
        example = dict(record)
        example["purestrata_chunk_ids"] = [source.get("chunk_id") for source in sources]
        example["purestrata_record_kinds"] = [source.get("record_kind") for source in sources]
        example["purestrata_doc_ids"] = [source.get("doc_id") for source in sources]
        example["purestrata_source_paths"] = [source.get("source_path") for source in sources]
        example["purestrata_locators"] = [source.get("locator") for source in sources]
        example["purestrata_source_sha256"] = [source.get("source_sha256") for source in sources]
        examples.append(example)
    return examples


def to_dataset(records: list[dict], format: str | None = None):
    """Build a Hugging Face ``datasets.Dataset`` from provider-format records.

    The dataset can back distilabel pipeline steps that accept a dataset
    input. Rows are exactly what :func:`records_to_examples` returns.
    """
    try:
        from datasets import Dataset
    except ImportError as exc:  # pragma: no cover - exercised via tests when the extra is absent
        raise RuntimeError(
            "The distilabel adapter's dataset conversion requires the 'distilabel' extra. "
            "Install it with: pip install 'purestrata[distilabel]'"
        ) from exc
    return Dataset.from_list(records_to_examples(records, format=format))
