# Setting Up GitHub Repository

## Initial Setup

1. **Create a new repository on GitHub**
   - Go to https://github.com/new
   - Name it `RPG_LLM` (or your preferred name)
   - Choose public or private
   - **DO NOT** initialize with README, .gitignore, or license (we already have these)

2. **Add the remote and push**
   ```bash
   git remote add origin https://github.com/YOUR_USERNAME/RPG_LLM.git
   git branch -M main
   git push -u origin main
   ```

## Verify Secrets Are Not Committed

Before pushing, verify no secrets are in the repository:

```bash
# Check for common secret patterns
git grep -i "api.*key" -- ':!*.example' ':!*.md' ':!SECURITY.md'
git grep -i "secret" -- ':!*.example' ':!*.md' ':!SECURITY.md'
git grep -i "password" -- ':!*.example' ':!*.md' ':!SECURITY.md'

# Check what will be committed
git ls-files | grep -E '\.env$|secrets/|credentials'
```

If any secrets are found, remove them and update `.gitignore`.

## After First Push

1. Set up branch protection (optional but recommended):
   - Go to Settings > Branches
   - Add rule for `main` branch
   - Require pull request reviews
   - Require status checks to pass

2. Enable GitHub Actions (if using CI/CD)

3. Add repository topics/tags for discoverability
