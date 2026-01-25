---
description: Automated PR review against CLAUDE.md guidelines
---

# Pull Request Review

Conducting a comprehensive review of this PR against our coding standards and guidelines.

---

## PR Information

!`gh pr view --json title,body,number,author,headRefName 2>/dev/null || echo "PR info not available via gh CLI"`

---

## Changes Overview

!`git diff main --stat`

---

## Review Checklist

### 1. Code Style and Conventions

Checking against CLAUDE.md and CLAUDE-shared.md guidelines:

#### Python Code Style (PEP 8)
- [ ] 4 spaces for indentation
- [ ] Maximum line length (88 characters)
- [ ] snake_case for functions/variables
- [ ] PascalCase for classes
- [ ] Docstrings for public functions
- [ ] Type hints where appropriate

#### JavaScript Code Style
- [ ] 2 spaces for indentation
- [ ] camelCase for variables/functions
- [ ] const over let
- [ ] JSDoc comments for complex functions

#### Naming Conventions
- [ ] Function names are verb phrases
- [ ] Class names are noun phrases
- [ ] Boolean variables use predicates (is_, has_)
- [ ] Constants use UPPER_CASE

---

### 2. Architecture Compliance

#### ImageTagger-Specific Patterns
- [ ] PNG metadata written before database updates
- [ ] Dual-mode (Reference/Copy) handling correct
- [ ] Image type schemas used (not hardcoded)
- [ ] File existence checks before operations
- [ ] Electron context checked when using browser APIs

#### Database Operations
- [ ] Context managers (`with`) used for connections
- [ ] Parameterized queries (no string concatenation)
- [ ] Proper error handling

#### API Endpoints
- [ ] Consistent JSON response format
- [ ] Error handling with appropriate status codes
- [ ] Logging for debugging

---

### 3. Test Coverage

Analyzing test coverage:

!`pytest --cov --cov-report=term-missing -q 2>/dev/null | tail -20 || echo "Run pytest --cov to check coverage"`

#### Requirements
- [ ] Unit tests for new functions
- [ ] Integration tests for API endpoints
- [ ] E2E tests for UI changes
- [ ] Edge cases covered
- [ ] Tests are independent and don't rely on order

---

### 4. Security Review

#### Common Security Issues
- [ ] No hardcoded credentials or API keys
- [ ] Input validation for user-provided data
- [ ] Parameterized SQL queries (no injection risk)
- [ ] Proper authentication/authorization
- [ ] Sensitive data not logged
- [ ] Dependencies up to date

#### File Security
!`grep -r "password\|api_key\|secret\|token" --include="*.py" --include="*.js" . 2>/dev/null | grep -v "# " | grep -v "//" | head -10 || echo "No obvious secrets found"`

---

### 5. Performance Implications

#### Potential Performance Issues
- [ ] No N+1 queries
- [ ] Database queries use indexes
- [ ] Large datasets paginated
- [ ] Caching used appropriately
- [ ] No blocking operations in main thread

#### Changed Files Analysis
!`git diff main --name-only`

---

### 6. Documentation

#### Documentation Requirements
- [ ] README updated if API/features changed
- [ ] CHANGELOG.md updated
- [ ] Code comments for complex logic
- [ ] CLAUDE.md updated if new patterns discovered
- [ ] API documentation current

---

## Detailed Review

### Files Changed

Analyzing each changed file for issues:

!`git diff main --name-status`

### Specific Feedback

#### Positive Observations
- (List good practices observed)

#### Concerns and Suggestions
- (List specific issues with file:line references)

#### Required Changes
- (List must-fix issues before merge)

#### Optional Improvements
- (List nice-to-have improvements)

---

## CLAUDE.md Updates

Based on this PR, consider updating CLAUDE.md with:

### New Patterns Discovered
- (Document any new architectural patterns)

### Anti-Patterns Encountered
- (Document mistakes to avoid in future)

### Best Practices Reinforced
- (Document proven approaches)

---

## Final Recommendation

### Approval Status
- [ ] ✅ **Approve** - Ready to merge
- [ ] 🟡 **Request Changes** - Address issues before merge
- [ ] ❌ **Reject** - Significant problems need resolution

### Summary
(Provide overall assessment)

### Next Steps for Author
1. (Action item)
2. (Action item)
3. (Action item)

---

## Automated Checks

!`echo "Checking if CI/CD tests pass..." && gh pr checks 2>/dev/null || echo "Run 'gh pr checks' to see CI status"`

---

Review complete! Please address any concerns before merging.