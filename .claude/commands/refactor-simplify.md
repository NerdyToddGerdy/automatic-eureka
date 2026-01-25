---
description: Analyze code for complexity and suggest simplifications
---

# Code Refactoring and Simplification

Analyzing the codebase for overly complex sections and suggesting improvements.

---

## Step 1: Identify Complex Code

### Cyclomatic Complexity Analysis

Checking for functions with high complexity:

!`find . -name "*.py" -not -path "./node_modules/*" -not -path "./.venv/*" -not -path "./htmlcov/*" | head -20`

### Long Functions

Looking for functions exceeding 50 lines:

!`grep -n "^def \|^    def " app.py database.py metadata.py scanner.py | head -30`

### Deep Nesting

Checking for deeply nested code (>3 levels):

!`grep -E "^[ ]{12,}" app.py database.py metadata.py | wc -l || echo "Checking nesting levels"`

---

## Step 2: Code Duplication Analysis

### Duplicate Code Detection

Looking for repeated patterns:

!`find . -name "*.py" -not -path "./node_modules/*" -not -path "./.venv/*" -exec grep -l "def " {} \; | head -10`

---

## Step 3: Architectural Review

### Current Architecture Assessment

#### Strengths
- Clear separation of concerns (database, metadata, API)
- Well-defined module boundaries
- Consistent error handling patterns

#### Areas for Improvement
Analyzing for potential issues:

1. **God Classes**: Classes with too many responsibilities
2. **Tight Coupling**: Modules that depend too heavily on each other
3. **Code Smells**: Long parameter lists, feature envy, etc.

---

## Step 4: Specific Refactoring Suggestions

### High Priority (Impact: High, Effort: Low)

#### 1. Extract Magic Numbers
```python
# Before
if len(tokens) > 100:
    # pagination logic

# After
MAX_TOKENS_PER_PAGE = 100
if len(tokens) > MAX_TOKENS_PER_PAGE:
    # pagination logic
```

#### 2. Reduce Nesting with Early Returns
```python
# Before
def process_token(token):
    if token:
        if token.valid:
            if token.has_image:
                return process_image(token)
    return None

# After
def process_token(token):
    if not token:
        return None
    if not token.valid:
        return None
    if not token.has_image:
        return None
    return process_image(token)
```

#### 3. Extract Complex Conditions
```python
# Before
if user.is_admin or (user.is_moderator and user.has_permission('edit') and not resource.is_locked):
    # logic

# After
def can_edit_resource(user, resource):
    if user.is_admin:
        return True
    return (user.is_moderator and
            user.has_permission('edit') and
            not resource.is_locked)

if can_edit_resource(user, resource):
    # logic
```

---

### Medium Priority (Impact: Medium, Effort: Medium)

#### 4. Consolidate Duplicate Logic

Identify repeated patterns across files:

!`git ls-files "*.py" | xargs -I {} grep -l "def get_.*by_id" {} 2>/dev/null | head -5`

#### 5. Apply Single Responsibility Principle

Large classes/modules to consider splitting:

!`wc -l *.py | sort -rn | head -10`

---

### Low Priority (Impact: Low, Effort: High)

#### 6. Improve Naming
- Variables with unclear names
- Functions not describing their action
- Classes with vague purposes

#### 7. Reduce Global State
- Minimize global variables
- Use dependency injection
- Prefer explicit parameters

---

## Step 5: Refactoring Plan

### Immediate Actions (This Sprint)
1. **Extract magic numbers to constants**
   - Files: app.py, database.py
   - Estimated effort: 30 minutes
   - Risk: Low

2. **Simplify nested conditionals**
   - Files: scanner.py, metadata.py
   - Estimated effort: 1 hour
   - Risk: Low (covered by tests)

3. **Remove dead code**
   - Files: (identify during review)
   - Estimated effort: 20 minutes
   - Risk: Very low

### Medium Term (Next Sprint)
4. **Consolidate duplicate logic**
   - Extract common patterns into utilities
   - Estimated effort: 2-3 hours
   - Risk: Medium (requires careful testing)

5. **Improve module organization**
   - Separate concerns more clearly
   - Estimated effort: 3-4 hours
   - Risk: Medium

### Long Term (Future Sprints)
6. **Apply design patterns**
   - Strategy pattern for image type handling
   - Factory pattern for file operations
   - Estimated effort: 1-2 days
   - Risk: High (major refactoring)

---

## Step 6: Execute Refactorings

### Safety Checklist
- [ ] All tests pass before refactoring
- [ ] Refactor one thing at a time
- [ ] Run tests after each refactoring
- [ ] Commit after each successful refactoring
- [ ] No functional changes mixed with refactoring

### Current Test Status

!`pytest --collect-only -q 2>/dev/null | tail -5 || echo "Tests available"`

---

## Step 7: Verify No Behavioral Changes

After refactoring, verify:

1. **Run full test suite**:
   !`pytest -v 2>/dev/null | tail -20 || echo "Run pytest to verify"`

2. **Check application starts**:
   !`timeout 3 python app.py 2>&1 | head -10 || echo "Startup check complete"`

3. **Review diff**:
   !`git diff --stat`

---

## Recommendations

### Code Quality Improvements
1. Continue extracting complex functions
2. Increase test coverage for edge cases
3. Add type hints for better IDE support
4. Document complex algorithms

### Architectural Improvements
1. Consider introducing a service layer
2. Separate business logic from HTTP handlers
3. Implement repository pattern for database access
4. Add validation layer for input data

### Next Review
Schedule next refactoring session in 2-4 weeks to maintain code quality.

---

**Note**: Always ensure tests pass before and after refactoring. Never change behavior while refactoring.