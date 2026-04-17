.PHONY: test-unit test-integration

test-unit:
	python -m pytest -m unit

test-integration:
	cd tests && docker compose up -d --build
	python -m pytest -m integration
