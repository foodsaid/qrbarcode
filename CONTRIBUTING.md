# Contributing to QRBarcode

Thank you for considering contributing to QRBarcode! This document provides guidelines and instructions for contributing.

## Code of Conduct

Be respectful and inclusive. We welcome contributions from everyone.

## Getting Started

### Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/foodsaid/qrbarcode.git
   cd qrbarcode
   ```

2. **Set up Python environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```

4. **Install pre-commit hooks**
   ```bash
   pre-commit install
   ```

## Development Workflow

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=main --cov-report=html

# Run specific test file
pytest tests/test_main.py

# Run specific test
pytest tests/test_main.py::TestGenerateEndpoint::test_generate_qrcode_success
```

### Code Quality

```bash
# Format code with black
black main.py tests/

# Lint with flake8
flake8 main.py tests/

# Type check with mypy
mypy main.py

# Security scan with bandit
bandit -r main.py

# Check dependency vulnerabilities
safety check
```

### Running Locally

```bash
# Method 1: Direct Python
python main.py

# Method 2: With gunicorn
gunicorn --bind 0.0.0.0:8080 main:app

# Method 3: Docker
./run_local.sh
```

## Making Changes

### Branch Naming

- Feature: `feature/description`
- Bug fix: `fix/description`
- Documentation: `docs/description`
- Refactor: `refactor/description`

Examples:
- `feature/add-svg-support`
- `fix/barcode-validation-error`
- `docs/update-api-reference`

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

Examples:
```
feat(api): add SVG output format support

fix(validation): correct barcode alphanumeric check

docs(readme): add troubleshooting section

test(generate): add edge case tests for empty input
```

### Code Style

- Follow PEP 8 guidelines
- Use type hints for function signatures
- Write docstrings for all functions and classes
- Maximum line length: 100 characters
- Use meaningful variable names

Example:
```python
def validate_input(content: str, generate_type: str) -> Tuple[bool, str]:
    """
    Validate user input for content and type parameters.

    Args:
        content: The text content to encode
        generate_type: Type of code to generate ('qrcode' or 'barcode')

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Implementation
```

### Testing Requirements

- All new features must include tests
- Aim for >90% code coverage
- Include both positive and negative test cases
- Test edge cases and error conditions

Test file structure:
```python
class TestFeatureName:
    """Tests for feature description."""

    def test_positive_case(self, client):
        """Test that feature works correctly."""
        # Arrange
        # Act
        # Assert

    def test_negative_case(self, client):
        """Test that feature handles errors."""
        # Arrange
        # Act
        # Assert
```

## Pull Request Process

1. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Write code
   - Add tests
   - Update documentation

3. **Run quality checks**
   ```bash
   black main.py tests/
   flake8 main.py tests/
   pytest --cov=main
   ```

4. **Commit your changes**
   ```bash
   git add .
   git commit -m "feat: add your feature description"
   ```

5. **Push to your fork**
   ```bash
   git push origin feature/your-feature-name
   ```

6. **Create Pull Request**
   - Provide clear description of changes
   - Reference any related issues
   - Ensure CI passes
   - Request review

### Pull Request Checklist

- [ ] Code follows project style guidelines
- [ ] Tests added for new functionality
- [ ] All tests pass locally
- [ ] Documentation updated (README, docstrings)
- [ ] CHANGELOG.md updated
- [ ] Commit messages follow conventional commits
- [ ] No merge conflicts

## Reporting Bugs

### Before Submitting

1. Check existing issues
2. Try latest version
3. Gather relevant information

### Bug Report Template

```markdown
**Describe the bug**
Clear description of the issue

**To Reproduce**
Steps to reproduce:
1. Send request to...
2. With parameters...
3. See error...

**Expected behavior**
What you expected to happen

**Actual behavior**
What actually happened

**Environment**
- Python version:
- OS:
- Docker version (if applicable):

**Logs**
Relevant log output or error messages
```

## Feature Requests

We welcome feature requests! Please provide:

1. **Use case**: Why is this feature needed?
2. **Proposed solution**: How should it work?
3. **Alternatives**: Other approaches you've considered
4. **Additional context**: Any other relevant information

## Documentation

- Update README.md for user-facing changes
- Update docstrings for API changes
- Add examples for new features
- Update CHANGELOG.md

## Questions?

- Open an issue with the `question` label
- Check existing documentation first

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
