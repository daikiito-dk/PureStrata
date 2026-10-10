"""Optional framework adapters.

Adapters live in this subpackage so the dependency-free core is untouched:
``import purestrata`` never imports a framework. Import a specific adapter
module to use it, e.g.::

    from purestrata.adapters.llamaindex import PureStrataRetriever
    from purestrata.adapters.distilabel import records_to_examples

Each adapter requires its optional extra (``purestrata[llamaindex]`` or
``purestrata[distilabel]``) and raises a clear install hint when the
framework is missing. None of them send corpus data anywhere; they turn
PureStrata records into local framework objects.
"""
