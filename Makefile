.PHONY: kur calistir test demo lint temizle

kur:
	pip install -r requirements-dev.txt
	pip install -e .

calistir:
	uvicorn smartclinical.main:app --reload --host 0.0.0.0 --port 8000

demo:
	python -m smartclinical.scripts.demo_veri --sifirla

test:
	pytest -q

lint:
	ruff check smartclinical ml tests

temizle:
	rm -rf veri/*.db yuklemeler/* .pytest_cache
