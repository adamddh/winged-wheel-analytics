.PHONY: setup pipeline test lint fmt app clean

setup:
	uv sync

pipeline: setup
	uv run wings pipeline

test:
	uv run pytest -q

lint:
	uv run ruff check .
	uv run ruff format --check .

fmt:
	uv run ruff check --fix .
	uv run ruff format .

app:
	uv run --with streamlit streamlit run app/streamlit_app.py

clean:
	rm -rf data/warehouse.duckdb
