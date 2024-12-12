# reports

## Installation for development

```bash
git clone <url> reports
cd reports

python3.12.4 -m venv .venv  # or `python -m venv .venv` if u use pyenv
. .venv/bin/activate

poetry install
pre-commit install

# copy env variables to .env and change it
cp .env.example .env

# this command runs all checks (linter, type-checker, migrations check, pytest)
make
```
