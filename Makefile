PY ?= python
VENV ?= .venv

ifeq ($(OS),Windows_NT)
	PYBIN := $(VENV)/Scripts/python.exe
else
	PYBIN := $(VENV)/bin/python
endif

.PHONY: help venv install seed train eval api web test lint fmt clean docker-up docker-down

help:
	@echo "make venv      - create the local Python virtualenv"
	@echo "make install   - install Python dependencies"
	@echo "make seed      - generate synthetic data, images, and documents"
	@echo "make train     - train the vision and forecast baselines"
	@echo "make eval      - run evaluation and write reports"
	@echo "make api       - run the FastAPI server on :8000"
	@echo "make web       - run the Next.js app on :3000"
	@echo "make test      - run the test suite"
	@echo "make lint      - run ruff"

venv:
	uv venv --python 3.11 $(VENV)

install:
	uv pip install -r requirements-dev.txt

seed:
	$(PYBIN) -m scripts.seed

train:
	$(PYBIN) -m training.vision.train

eval:
	$(PYBIN) -m evaluation.run_all

api:
	$(PYBIN) -m uvicorn app.main:app --app-dir apps/api --reload --port 8000

web:
	cd apps/web && npm run dev

test:
	$(PYBIN) -m pytest

lint:
	$(PYBIN) -m ruff check src apps/api training evaluation tests

fmt:
	$(PYBIN) -m ruff format src apps/api training evaluation tests

clean:
	rm -rf data/*.db artifacts/* uploads/* .pytest_cache

docker-up:
	docker compose up --build

docker-down:
	docker compose down -v
