"""LlamaIndex adapter tests (functional tests skip without the llamaindex extra)."""

from __future__ import annotations

import importlib
import importlib.util

import pytest


def test_llamaindex_adapter_requires_extra():
    if importlib.util.find_spec("llama_index") is not None:
        pytest.skip("llama-index is installed; the ImportError path is unreachable")
    with pytest.raises(RuntimeError, match="llamaindex' extra"):
        importlib.import_module("purestrata.adapters.llamaindex")


def test_retriever_returns_nodes_with_provenance(corpus):
    pytest.importorskip("llama_index.core")
    from llama_index.core import QueryBundle

    from purestrata.adapters.llamaindex import PureStrataRetriever

    retriever = PureStrataRetriever(corpus, top_k=3)
    nodes = retriever.retrieve("spindle vibration")

    assert nodes
    for hit in nodes:
        node = hit.node
        assert node.metadata["chunk_id"] == node.id_
        provenance = node.metadata["provenance"]
        assert provenance["source_path"]
        assert provenance["locator"]
        assert isinstance(node.metadata["record_metadata"], dict)

    hits = retriever._retrieve(QueryBundle(query_str="ブレーキ 停止時間"))
    assert hits


def test_retriever_kind_filter_and_hybrid_passthrough(corpus):
    pytest.importorskip("llama_index.core")

    from purestrata.adapters.llamaindex import PureStrataRetriever

    retriever = PureStrataRetriever(corpus, top_k=5, kinds="failure_case")
    nodes = retriever.retrieve("brake")
    assert nodes
    assert all(hit.node.metadata["kind"] == "failure_case" for hit in nodes)

    # hybrid=None defers to the corpus default (BM25 here); hybrid=False forces BM25.
    for hybrid in (None, False):
        retriever = PureStrataRetriever(corpus, top_k=5, hybrid=hybrid)
        assert retriever.retrieve("spindle vibration")

    # hybrid=True passes through unchanged: the corpus enforces the encoder rule.
    retriever = PureStrataRetriever(corpus, top_k=5, hybrid=True)
    with pytest.raises(ValueError, match="requires a local embedding encoder"):
        retriever.retrieve("spindle vibration")
