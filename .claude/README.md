# Claude Code Workflow Configuration

This directory contains the Claude Code workflow configuration following Boris Cherny's best practices for AI-assisted development.

## Overview

The ImageTagger project now uses Claude Code's advanced workflow features to maximize development velocity and code quality. This includes:

- **CLAUDE.md files** - Project-specific and organization-wide coding standards
- **Slash commands** - Automated workflows for common tasks
- **Subagents** - Specialized AI assistants for specific responsibilities
- **Teleport commands** - Seamless handoff between CLI and web
- **Configuration** - Optimized settings for this project

## Directory Structure

```
.claude/
├── README.md              # This file
├── settings.json          # Claude Code configuration
├── commands/              # Custom slash commands
│   ├── commit-push-pr.md         # Full git workflow automation
│   ├── test-and-verify.md        # Comprehensive testing
│   ├── review-pr.md              # Automated PR review
│   ├── refactor-simplify.md      # Code quality improvements
│   ├── verify-metadata-sync.md   # Check PNG/DB consistency
│   ├── build-electron.md         # Electron packaging
│   ├── e2e-quick-test.md        # Quick E2E smoke tests
│   ├── teleport-to-web.md        # Hand off to claude.ai
│   └── teleport-from-web.md      # Resume from claude.ai
└── agents/                # Specialized subagents
    ├── code-simplifier.md        # Post-development cleanup
    ├── verify-app.md             # QA and testing
    ├── documentation.md          # Doc maintenance
    └── metadata-guardian.md      # PNG-first contract enforcement
```

## Quick Start

### Using Slash Commands

Invoke custom workflows with `/command-name`:

```bash
# Automate git workflow
/commit-push-pr

# Run full test suite
/test-and-verify

# Review a PR
/review-pr

# Refactor complex code
/refactor-simplify

# Project-specific: Check metadata sync
/verify-metadata-sync

# Project-specific: Build Electron app
/build-electron

# Project-specific: Quick E2E test
/e2e-quick-test
```

### Using Subagents

Launch specialized agents for specific tasks:

```
I need to simplify the code in app.py
→ Claude Code will use the code-simplifier agent

I want to verify the app is ready to ship
→ Claude Code will use the verify-app agent

Update the documentation after my changes
→ Claude Code will use the documentation agent

Check if PNG metadata matches the database
→ Claude Code will use the metadata-guardian agent
```

### Teleporting Between CLI and Web

For long-running or complex tasks, hand off to claude.ai:

```bash
# Start handoff to web
/teleport-to-web

# (Work on claude.ai with full context)

# Resume in CLI
/teleport-from-web SESSION_ID
```

## CLAUDE.md Files

### CLAUDE-shared.md (Organization-Wide)
Located in project root. Contains universal conventions:
- Code style guidelines (Python PEP 8, JavaScript)
- Git workflow and commit message format
- Testing best practices
- Security guidelines
- Common mistakes to avoid
- Deployment checklist

### CLAUDE.md (Project-Specific)
Located in project root. Contains ImageTagger specifics:
- Architecture overview (Flask + Electron hybrid)
- PNG-first metadata contract
- Dual-mode operation (Reference vs Copy)
- Image type system (6 types)
- API endpoint documentation
- Testing strategies (Unit + E2E)
- Common pitfalls specific to this codebase

**These files are automatically referenced by Claude Code** to maintain consistency.

## Slash Commands

### Core Workflow Commands

#### /commit-push-pr
Automates the entire git workflow:
1. Analyzes changes
2. Creates conventional commit message
3. Stages files
4. Commits with co-author
5. Pushes to remote
6. Creates pull request

**When to use**: Ready to commit your changes

#### /test-and-verify
Comprehensive testing:
1. Runs unit tests with coverage
2. Runs Chrome E2E tests
3. Checks Python syntax
4. Verifies app startup
5. Reports results with recommendations

**When to use**: Before committing, before deploying

#### /review-pr
Automated code review:
1. Checks code style against CLAUDE.md
2. Verifies test coverage
3. Looks for security issues
4. Checks performance implications
5. Suggests improvements
6. Updates CLAUDE.md if needed

**When to use**: Reviewing your own or others' PRs

#### /refactor-simplify
Code quality improvements:
1. Identifies complex code
2. Suggests simplifications
3. Removes duplicate logic
4. Improves organization
5. Ensures tests pass

**When to use**: After feature implementation, during cleanup

### Project-Specific Commands

#### /verify-metadata-sync
ImageTagger-specific: Ensures PNG metadata and database are consistent
1. Checks database integrity
2. Finds missing files
3. Verifies metadata matches
4. Suggests recovery procedures

**When to use**: Troubleshooting data issues, after major changes

#### /build-electron
Packages the Electron desktop app:
1. Checks dependencies
2. Builds app
3. Packages for distribution
4. Verifies artifacts
5. Prepares release

**When to use**: Creating releases, testing packaging

#### /e2e-quick-test
Quick smoke test of critical paths:
1. Tests upload workflow
2. Tests search and filter
3. Tests editing
4. Tests bulk operations
5. Verifies UI interactions

**When to use**: Quick verification before shipping

## Subagents

Subagents are specialized AI assistants that handle specific responsibilities.

### code-simplifier
**Runs after**: Feature implementation
**Purpose**: Remove unnecessary complexity
**Focus**:
- Simplify nested logic
- Extract duplicate code
- Apply SOLID principles
- Maintain functionality

**Invoke explicitly**: "Simplify the code in app.py"

### verify-app
**Runs before**: Deployment
**Purpose**: Ensure production readiness
**Focus**:
- Test all user flows
- Check edge cases
- Verify error handling
- Test on different contexts
- Check console for errors

**Invoke explicitly**: "Verify the app is ready to ship"

### documentation
**Runs when**: Code changes
**Purpose**: Keep docs in sync
**Focus**:
- Update README
- Update API documentation
- Add/update code comments
- Keep CHANGELOG current
- Update CLAUDE.md with patterns

**Invoke explicitly**: "Update the documentation"

### metadata-guardian
**Runs**: Monitoring/verification
**Purpose**: Enforce PNG-first contract
**Focus**:
- Verify metadata consistency
- Detect violations
- Check missing files
- Audit data operations
- Provide recovery procedures

**Invoke explicitly**: "Check metadata sync" or "Verify PNG-first contract"

## Configuration (settings.json)

Key settings for this project:

```json
{
  "defaultModel": "opus-4.5",           // Use Opus 4.5 by default
  "thinkingMode": "auto",               // Enable thinking for complex problems
  "autoAccept": {
    "enabled": true,
    "riskLevel": "low"                  // Auto-accept low-risk operations
  },
  "git": {
    "conventionalCommits": true,        // Enforce conventional commits
    "requireCoAuthor": true             // Add Claude as co-author
  },
  "projectSpecific": {
    "metadataContract": "png-first",    // Enforce PNG-first pattern
    "dualModeSupport": true,            // Reference + Copy modes
    "requireMetadataSync": true         // Verify sync regularly
  }
}
```

## Workflow Examples

### Example 1: Feature Development

```
1. Write feature code
2. Run /test-and-verify to ensure quality
3. Invoke code-simplifier: "Simplify the new code"
4. Invoke documentation: "Update docs for new feature"
5. Run /commit-push-pr to create PR
6. Run /review-pr to self-review
7. Request team review
```

### Example 2: Bug Fix

```
1. Identify and fix bug
2. Add test to prevent regression
3. Run /test-and-verify
4. Run /verify-metadata-sync (if data-related)
5. Run /commit-push-pr with "fix:" prefix
6. Invoke documentation: "Update CHANGELOG"
```

### Example 3: Refactoring

```
1. Run /refactor-simplify to identify complex code
2. Make incremental improvements
3. Run /test-and-verify after each change
4. Invoke code-simplifier for final cleanup
5. Run /commit-push-pr with "refactor:" prefix
```

### Example 4: Release Preparation

```
1. Invoke verify-app: "Verify app is ready to ship"
2. Run /e2e-quick-test for smoke tests
3. Run /build-electron to package app
4. Invoke documentation: "Update CHANGELOG for release"
5. Create release tag
6. Deploy
```

### Example 5: Long-Running Task

```
1. Start task in CLI
2. Run /teleport-to-web when hitting complexity
3. Continue on claude.ai with full context
4. Complete work on web
5. Run /teleport-from-web SESSION_ID to return
6. Integrate changes
7. Run /commit-push-pr
```

## Best Practices

### DO
✅ Use slash commands for common workflows
✅ Invoke subagents for specialized tasks
✅ Reference CLAUDE.md when uncertain
✅ Run tests before committing
✅ Use teleport for long-running work
✅ Keep CLAUDE.md updated with patterns
✅ Follow conventional commit format

### DON'T
❌ Skip testing before commits
❌ Ignore CLAUDE.md guidelines
❌ Violate PNG-first metadata contract
❌ Commit directly without PR (except hotfixes)
❌ Mix refactoring with features
❌ Forget to update documentation
❌ Bypass code review process

## Project-Specific Guidelines

### ImageTagger Critical Patterns

1. **PNG-First Contract**
   - ALWAYS write to PNG before database
   - Use metadata-guardian to verify
   - PNG files are source of truth

2. **Dual-Mode Support**
   - Test both Reference and Copy modes
   - Handle file paths appropriately
   - Consider Electron vs Browser

3. **Image Type System**
   - 6 types with different schemas
   - Don't hardcode type-specific logic
   - Use tagSchemas configuration

4. **Testing Strategy**
   - Unit tests for business logic
   - E2E tests for workflows
   - Use Page Object Model
   - Multi-level verification (UI + API + DB)

## Troubleshooting

### Slash Command Not Found
- Check `.claude/commands/` directory exists
- Verify command file ends with `.md`
- Check `settings.json` has commands enabled

### Subagent Not Running
- Invoke explicitly: "Use the X agent to..."
- Check `.claude/agents/` directory exists
- Verify agent file ends with `.md`

### CLAUDE.md Not Referenced
- Ensure files are in project root
- Check `settings.json` contextFiles setting
- Verify file names are correct

### Teleport Issues
- Ensure session ID is captured
- Check git status before teleporting
- Commit or stash work in progress

## Contributing

### Adding New Slash Commands
1. Create `.claude/commands/your-command.md`
2. Add frontmatter with description
3. Use `!` for bash commands
4. Document expected behavior
5. Test thoroughly

### Adding New Subagents
1. Create `.claude/agents/your-agent.md`
2. Define mission and responsibilities
3. Specify when to invoke
4. Provide clear examples
5. Include success criteria

### Updating CLAUDE.md
- Add new patterns as discovered
- Document anti-patterns encountered
- Update architecture decisions
- Keep examples current
- Date your updates

## Resources

- [Boris Cherny's Claude Code Workflow](https://github.com/bcherny/claude-code-best-practices)
- [Claude Code Documentation](https://claude.com/claude-code)
- [Conventional Commits](https://www.conventionalcommits.org/)
- [ImageTagger Documentation](../README.md)

---

**Questions?** Check CLAUDE.md or CLAUDE-shared.md for guidance, or ask Claude Code directly!

**Last Updated**: 2026-01-08
**Maintained By**: ImageTagger Team + Claude Code