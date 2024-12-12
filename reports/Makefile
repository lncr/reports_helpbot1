all: fmt lint

fmt:
	poetry run black src
	poetry run isort src

lint:
	poetry run dotenv-linter .env.example
	poetry run ruff check .
	poetry run mypy .
	poetry run poetry check
