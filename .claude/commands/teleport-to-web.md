---
description: Hand off this task to claude.ai for long-running work
---

# Teleport to Claude.ai

Preparing to continue this work session on claude.ai for extended context and long-running tasks.

---

## Session Information

### Current Working Directory
!`pwd`

### Current Branch
!`git branch --show-current`

### Recent Changes
!`git status --short`

---

## Session Summary

### What We've Been Working On
(I'll summarize the current state of work, including:
- The task or feature being implemented
- Progress made so far
- Files that have been modified
- Any pending decisions or blockers
)

### Files Modified in This Session
!`git diff --name-status`

### Key Files and Their Locations
(I'll list all relevant files with their absolute paths:
- Main files being edited
- Related test files
- Configuration files affected
- Documentation that needs updating
)

---

## Context for Web Session

### Project Overview
- **Name**: ImageTagger (Image Vault)
- **Type**: Flask + Electron hybrid app for RPG token management
- **Key Concept**: PNG files as source of truth for metadata
- **Location**: `/Users/toddgerdy/PycharmProjects/ImageTagger`

### Important Patterns to Remember
1. **PNG-first contract**: Always write metadata to PNG before database
2. **Dual-mode**: Reference mode (files stay in place) vs Copy mode (files copied to vault)
3. **Image types**: Six types with different tag schemas (Token, Map, Handout, Portrait, Scene, Item)
4. **Test strategy**: Unit tests + Chrome E2E tests with Page Object Model

### Current Task Details
(Detailed description of what needs to be done next, including:
- Specific goals and acceptance criteria
- Technical approach or architecture decisions
- Known constraints or dependencies
- Any research or investigation needed
)

### Next Steps
1. (First action to take)
2. (Second action to take)
3. (Third action to take)
...

### Open Questions / Decisions Needed
- (Question 1)
- (Question 2)
- (Question 3)

### Files to Focus On
- **Primary**: (Main files to edit)
- **Related**: (Files that might need updates)
- **Tests**: (Test files to run/update)
- **Docs**: (Documentation to update)

---

## Technical Context

### Dependencies Used
!`pip list | head -20`

### Recent Commits
!`git log --oneline -10`

### Environment
- **Python**: !`python --version`
- **Node**: !`node --version 2>/dev/null || echo "Not in PATH"`
- **OS**: !`uname -s`

---

## Session ID

**Session ID**: `imagetagger-$ARGUMENTS-$(date +%Y%m%d-%H%M%S)`

Use this session ID when returning from claude.ai to resume this exact context.

---

## Handoff Checklist

Before moving to web:
- [ ] All current work committed or stashed
- [ ] Session context documented above
- [ ] File paths are absolute and correct
- [ ] Next steps are clear
- [ ] Open questions noted
- [ ] Session ID generated

---

## Command to Resume from Web

When you return from claude.ai, use:
```
/teleport-from-web SESSION_ID
```

---

## Background This Task

Use the `&` command to background this work and continue on claude.ai:

```
& SESSION_ID
```

This will:
1. Save the current context
2. Generate a resumable session state
3. Free up the CLI for other work
4. Allow continuation on claude.ai with full context

---

**Ready to teleport!** Copy the Session ID and session summary to claude.ai to continue working there.

When you're ready to bring the work back, use `/teleport-from-web SESSION_ID`.