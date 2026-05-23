# Contributing

Thank you for taking the time to contribute to **ytdlp-pro**!

---

## Getting started

```bash
# 1. Fork and clone
git clone https://github.com/YOUR_USERNAME/ytdlp-pro.git
cd ytdlp-pro

# 2. Create a virtual environment
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# 3. Install in editable mode with dev extras
pip install -e ".[dev]"
```

---

## Development workflow

| Task | Command |
|------|---------|
| Run tests | `pytest` |
| Run tests with coverage | `pytest --cov=ytdlp_pro` |
| Lint | `ruff check .` |
| Auto-fix lint | `ruff check --fix .` |
| Format | `ruff format .` |
| Type-check | `mypy ytdlp_pro/` |

All checks must pass before opening a pull request.  The CI pipeline runs them automatically.

---

## Submitting a pull request

1. Create a feature branch: `git checkout -b feat/my-feature`
2. Make your changes and add/update tests.
3. Run the full check suite locally (see table above).
4. Commit with a clear message: `git commit -m "feat: add X"`
5. Push and open a PR against `main`.

---

## Code style

- Python 3.10+ syntax (use `match`, `X | Y` unions, etc. freely).
- Type annotations on all public functions and methods.
- Docstrings on all public symbols (NumPy style preferred).
- Line length ≤ 100 characters (enforced by Ruff).

---

## Reporting bugs

Please open a GitHub issue and include:

- Your Python version (`python --version`)
- Your yt-dlp version (`yt-dlp --version`)
- The full command you ran
- The complete error output
