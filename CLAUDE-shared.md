# CLAUDE-shared.md
## Universal Development Conventions

> This file contains organization-wide coding conventions and best practices.
> It should be symlinked from a central location across all projects.

---

## Common Commands

### Development
```bash
# Start development server
python app.py

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Run in development mode with auto-reload
FLASK_ENV=development python app.py
```

### Testing
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov --cov-report=html

# Run specific test file
pytest tests/test_filename.py

# Run tests with verbose output
pytest -v

# Run tests matching a pattern
pytest -k "test_pattern"
```

### Linting & Formatting
```bash
# Format code with black (if installed)
black .

# Check code style with flake8 (if installed)
flake8 .

# Type checking with mypy (if installed)
mypy .
```

### Git Workflow
```bash
# Check status
git status --short

# Create feature branch
git checkout -b feature/description

# Stage and commit
git add .
git commit -m "type: description"

# Push to remote
git push origin branch-name

# Pull latest changes
git pull origin main
```

---

## Code Style Guidelines

### General Principles
1. **DRY (Don't Repeat Yourself)** - Extract duplicate code into functions/classes
2. **KISS (Keep It Simple, Stupid)** - Prefer simple solutions over complex ones
3. **YAGNI (You Aren't Gonna Need It)** - Don't add functionality until needed
4. **SOLID Principles** - Follow object-oriented design principles
5. **Separation of Concerns** - Keep related code together, unrelated code apart

### Python Style (PEP 8)
- Use 4 spaces for indentation (never tabs)
- Maximum line length: 88 characters (Black formatter default)
- Use snake_case for functions and variables
- Use PascalCase for classes
- Use UPPER_CASE for constants
- Add docstrings to all public functions and classes
- Use type hints where appropriate

### JavaScript Style
- Use 2 spaces for indentation
- Use camelCase for variables and functions
- Use PascalCase for classes and constructors
- Use UPPER_CASE for constants
- Prefer const over let, avoid var
- Use arrow functions for callbacks
- Add JSDoc comments for complex functions

### Naming Conventions
- Functions/methods: Verb phrases (`get_user`, `calculate_total`)
- Classes: Noun phrases (`User`, `OrderProcessor`)
- Booleans: Predicate phrases (`is_valid`, `has_permission`)
- Constants: Descriptive nouns (`MAX_RETRIES`, `API_ENDPOINT`)
- Private members: Prefix with underscore (`_internal_method`)

---

## Repository Etiquette

### Branch Naming
```
main            - Production-ready code
develop         - Integration branch for features
feature/name    - New features
bugfix/name     - Bug fixes
hotfix/name     - Urgent production fixes
refactor/name   - Code refactoring
docs/name       - Documentation updates
test/name       - Test additions/fixes
```

### Commit Messages (Conventional Commits)
```
<type>: <short description>

[optional body]

[optional footer]
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, no logic change)
- `refactor`: Code refactoring (no feature change or bug fix)
- `test`: Adding or updating tests
- `chore`: Maintenance tasks (dependencies, config)
- `perf`: Performance improvements

**Examples:**
```
feat: add user authentication system
fix: resolve memory leak in image processing
docs: update API documentation for new endpoints
refactor: simplify database query logic
test: add unit tests for token management
```

### Pull Request Guidelines
1. **Title**: Clear, concise description of changes
2. **Description**: What, why, and how
3. **Link Issues**: Reference related issues (#123)
4. **Screenshots**: For UI changes
5. **Testing**: Describe how you tested
6. **Breaking Changes**: Highlight any breaking changes
7. **Checklist**: Tests pass, docs updated, no console errors

---

## Common Mistakes to Avoid

### Code Quality
❌ **Avoid:**
- Magic numbers (use named constants)
- Deep nesting (> 3 levels - extract functions)
- Long functions (> 50 lines - break into smaller functions)
- God classes (classes that do too much - split responsibilities)
- Premature optimization (optimize only when proven necessary)
- Ignoring errors (always handle exceptions properly)
- Hardcoded values (use configuration files)

✅ **Do:**
- Extract magic numbers into constants
- Keep functions small and focused
- Use early returns to reduce nesting
- Follow Single Responsibility Principle
- Profile before optimizing
- Log errors with context
- Use environment variables and config files

### Testing
❌ **Avoid:**
- Testing implementation details
- Brittle tests (break with minor changes)
- Tests that depend on test order
- Tests without assertions
- Slow tests (> 1 second for unit tests)
- Testing third-party libraries
- Ignoring test failures

✅ **Do:**
- Test behavior and outcomes
- Write resilient, maintainable tests
- Ensure tests are independent
- Have clear assertions
- Mock external dependencies
- Test your own code thoroughly
- Fix failing tests immediately

### Git Workflow
❌ **Avoid:**
- Committing directly to main
- Large, monolithic commits
- Vague commit messages ("fix stuff", "update")
- Committing sensitive data (API keys, passwords)
- Force pushing to shared branches
- Leaving branches unmerged for weeks
- Committing generated files (build artifacts)

✅ **Do:**
- Use feature branches
- Make atomic, focused commits
- Write descriptive commit messages
- Use .gitignore for secrets and artifacts
- Rebase or merge cleanly
- Delete merged branches
- Keep .gitignore up to date

### Security
❌ **Never:**
- Commit credentials or API keys
- Store passwords in plain text
- Trust user input without validation
- Use string concatenation for SQL queries
- Expose sensitive data in logs
- Use weak encryption algorithms
- Skip security updates

✅ **Always:**
- Use environment variables for secrets
- Hash passwords with modern algorithms (bcrypt, argon2)
- Validate and sanitize all user input
- Use parameterized queries or ORMs
- Redact sensitive data in logs
- Use strong, modern encryption (AES-256)
- Keep dependencies updated

---

## Testing Guidelines

### Test Structure
```python
# Arrange - Set up test data and preconditions
# Act - Execute the code being tested
# Assert - Verify the expected outcome

def test_user_creation():
    # Arrange
    user_data = {"name": "John", "email": "john@example.com"}

    # Act
    user = create_user(user_data)

    # Assert
    assert user.name == "John"
    assert user.email == "john@example.com"
```

### Test Coverage
- **Unit Tests**: 80%+ coverage for business logic
- **Integration Tests**: Critical workflows and API endpoints
- **E2E Tests**: Main user journeys
- **Edge Cases**: Boundary conditions, error states

### Test Naming
```python
# Pattern: test_<what>_<condition>_<expected_result>
def test_create_user_with_valid_data_succeeds():
    pass

def test_create_user_with_duplicate_email_raises_error():
    pass

def test_calculate_total_with_empty_cart_returns_zero():
    pass
```

---

## Deployment Notes

### Pre-Deployment Checklist
- [ ] All tests passing
- [ ] No console errors or warnings
- [ ] Dependencies up to date
- [ ] Environment variables configured
- [ ] Database migrations applied
- [ ] Static assets built
- [ ] Documentation updated
- [ ] Changelog updated

### Environment Variables
Always use environment variables for:
- Database credentials
- API keys and secrets
- Feature flags
- Third-party service URLs
- Deployment-specific config

### Rollback Plan
- Document rollback procedures
- Keep previous version deployable
- Have database migration rollbacks ready
- Monitor error rates post-deployment

---

## Performance Best Practices

### Backend
- Use database indexes for frequently queried fields
- Implement caching for expensive operations
- Use pagination for large datasets
- Optimize database queries (avoid N+1 queries)
- Use connection pooling
- Profile before optimizing

### Frontend
- Minimize HTTP requests
- Compress and minify assets
- Use lazy loading for images
- Implement virtual scrolling for long lists
- Cache static assets
- Optimize images (WebP, proper sizing)

---

## Documentation Standards

### Code Comments
- **What to comment**: Why, not what
- **When to comment**: Complex algorithms, non-obvious decisions
- **Keep updated**: Remove outdated comments

### README Structure
1. Project Title and Description
2. Features
3. Installation
4. Usage
5. Configuration
6. Testing
7. Deployment
8. Contributing
9. License

### API Documentation
- Document all endpoints
- Include request/response examples
- Specify authentication requirements
- List possible error codes
- Keep in sync with implementation

---

## Collaboration

### Code Reviews
**Reviewer:**
- Be constructive and respectful
- Focus on code, not the person
- Explain your reasoning
- Suggest improvements, don't demand
- Approve when ready, don't nitpick

**Author:**
- Be open to feedback
- Respond to all comments
- Explain your decisions
- Keep PRs small and focused
- Test before requesting review

### Communication
- Ask questions when unclear
- Share knowledge and learnings
- Document decisions and rationale
- Be responsive to messages
- Help onboard new team members

---

**Last Updated**: 2026-01-08
**Version**: 1.0
