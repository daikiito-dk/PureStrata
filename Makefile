.PHONY: setup lint format test demo scenes clean

PY := uv run

setup:
	uv sync

lint:
	$(PY) ruff check src tests
	$(PY) ruff format --check src tests

format:
	$(PY) ruff format src tests
	$(PY) ruff check --fix src tests

test:
	$(PY) pytest

demo:
	$(PY) purestrata ingest-manual examples/data/manuals/lathe_mk3_maintenance.md \
		examples/data/manuals/ja/cnc_press_maintenance.md --out examples/corpus
	$(PY) purestrata ingest-dxf examples/data/cad/bracket_mk3.dxf --out examples/corpus
	$(PY) purestrata ingest-step examples/data/cad/bracket_assy_mk3.step --out examples/corpus
	$(PY) purestrata ingest-failures examples/data/failures/plant_failures.csv \
		--out examples/corpus
	$(PY) purestrata inspect --corpus examples/corpus
	$(PY) purestrata search "spindle vibration" --corpus examples/corpus
	$(PY) purestrata search "ブレーキ" --corpus examples/corpus

scenes:
	$(PY) python examples/scenes/run_scenes.py

clean:
	rm -rf examples/corpus examples/output
