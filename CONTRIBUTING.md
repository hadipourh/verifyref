# Contributing to VerifyRef

Thank you for considering contributing to VerifyRef! We welcome contributions from the community.

## Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/user/verifyref.git
   cd verifyref
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   pip install -e .  # Install in development mode
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

## Code Style

- Follow PEP 8 style guidelines
- Use type hints where appropriate
- Write docstrings for all functions and classes
- Keep line length under 100 characters
- Use meaningful variable and function names

## Testing

1. **Run existing tests**
   ```bash
   python -m pytest tests/
   ```

2. **Add tests for new features**
   - Unit tests for individual functions
   - Integration tests for complete workflows
   - Performance tests for optimization features

3. **Test coverage**
   ```bash
   python -m pytest --cov=verifyref tests/
   ```

## Performance Considerations

- **Parallel Processing**: Ensure thread safety in concurrent operations
- **Caching**: Use the existing caching system for database operations
- **Memory Usage**: Optimize for large batch processing
- **API Rate Limits**: Respect database API limitations

## Database Integration

When adding new database support:

1. **Create a new verifier class** in `verifier/`
2. **Implement required methods**: `search()`, `verify_reference()`
3. **Add rate limiting** and error handling
4. **Update configuration** in `config.py`
5. **Add tests** for the new integration

## AI Features

When working with AI components:

1. **API Key Security**: Never commit API keys
2. **Cost Optimization**: Minimize API calls through caching
3. **Error Handling**: Graceful degradation when AI is unavailable
4. **Privacy**: Ensure no sensitive data is sent to external APIs

## Documentation

- Update README.md for new features
- Add docstrings to all new functions
- Update CHANGELOG.md with changes
- Include usage examples

## Pull Request Process

1. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Write clear, concise commit messages
   - Include tests for new functionality
   - Update documentation as needed

3. **Test your changes**
   ```bash
   python -m pytest tests/
   python verifyref.py --cite "test query" --verbose
   ```

4. **Submit pull request**
   - Describe the changes clearly
   - Reference any related issues
   - Include performance impact notes

## Code Review Criteria

- **Functionality**: Does the code work as intended?
- **Performance**: Are there any performance regressions?
- **Security**: Are API keys and sensitive data handled properly?
- **Documentation**: Is the code well-documented?
- **Tests**: Are there adequate tests for the changes?

## Issues and Bug Reports

When reporting issues:

1. **Use descriptive titles**
2. **Include system information** (OS, Python version)
3. **Provide reproduction steps**
4. **Include error messages** and stack traces
5. **Attach sample files** if relevant (remove sensitive data)

## Feature Requests

For new features:

1. **Describe the use case** clearly
2. **Explain the expected behavior**
3. **Consider performance implications**
4. **Suggest implementation approach** if possible

## Security

- Report security vulnerabilities privately
- Don't include sensitive data in issues or PRs
- Use environment variables for API keys
- Follow secure coding practices

## Community Guidelines

- Be respectful and inclusive
- Help others learn and contribute
- Provide constructive feedback
- Focus on the technical aspects

## License

By contributing to VerifyRef, you agree that your contributions will be licensed under the GNU General Public License v3 (GPLv3).

## Getting Help

- Check existing issues and documentation
- Ask questions in GitHub Discussions
- Contact maintainers for complex issues

Thank you for contributing to VerifyRef! 🎓✅
