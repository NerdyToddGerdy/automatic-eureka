---
description: Automate the full git workflow - stage, commit, push, and create PR
---

# Git Workflow Automation

## Current Git Status

!`git status --short`

## Current Branch

!`git branch --show-current`

## Recent Commits

!`git log --oneline -5`

---

Based on the changes shown above, I'll now:

1. **Analyze Changes**: Review the modifications to understand what was done
2. **Create Commit Message**: Write a clear, conventional commit message
3. **Stage Changes**: Add relevant files to staging
4. **Commit**: Create the commit with the message
5. **Push**: Push to remote repository
6. **Create PR**: Generate a pull request with a comprehensive description

Please proceed with the following workflow:

### Step 1: Review Changes

Let me analyze the git diff to understand what changed:

!`git diff --stat`

### Step 2: Stage and Commit

Based on the changes, I'll create an appropriate conventional commit message following the format:

```
<type>: <short description>

<optional body explaining what and why>

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

**Types to consider:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `test`: Adding or updating tests
- `refactor`: Code refactoring
- `chore`: Maintenance tasks

Now staging and committing:

!`git add .`

### Step 3: Create Commit

I'll now create the commit with an appropriate message based on the changes.

### Step 4: Push to Remote

!`git push origin $(git branch --show-current) -u`

### Step 5: Create Pull Request

!`gh pr create --title "PR_TITLE_HERE" --body "PR_DESCRIPTION_HERE" --web || echo "Note: 'gh' CLI not installed or not authenticated. Please create PR manually at GitHub."`

---

## Summary

The git workflow has been completed. Here's what was done:

1. ✅ Changes analyzed
2. ✅ Files staged
3. ✅ Commit created with conventional commit message
4. ✅ Pushed to remote
5. ✅ Pull request created (or instructions provided)

Please review the PR on GitHub and request reviews from team members.
