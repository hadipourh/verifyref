# Contributing to VerifyRef

Thank you for considering contributing to VerifyRef!

## Quick Start

```bash
git clone https://github.com/user/verifyref.git
cd verifyref
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && pip install -e .
cp .env.example .env  # Edit with your API keys
```

## Code Standards

- Follow PEP 8, use type hints and docstrings
- Keep lines under 100 characters
- Ensure thread safety for parallel operations
- Respect API rate limits and add proper error handling

## Testing

```bash
python -m pytest tests/                    # Run tests
python -m pytest --cov=verifyref tests/   # Check coverage
```

Add tests for new features: unit tests, integration tests, and performance tests.

## Adding Database Support

1. Create verifier class in `verifier/` with `search()` and `verify_reference()` methods
2. Add rate limiting and error handling
3. Update `config.py` and add tests

## AI Features Guidelines

- Never commit API keys (use environment variables)
- Minimize API calls through caching
- Ensure graceful degradation when AI unavailable
- Don't send sensitive data to external APIs

## Pull Request Process

1. Create feature branch: `git checkout -b feature/your-feature`
2. Make changes with clear commits and tests
3. Update documentation as needed
4. Submit PR with clear description and performance notes

## Issues and Security

**Bug Reports**: Include system info, reproduction steps, error messages, and sample files (sanitized)

**Security**: Report vulnerabilities privately to maintainers

## License

Contributions are licensed under GNU GPL v3.

## Getting Help

Check existing issues, documentation, or contact maintainers for complex questions.
