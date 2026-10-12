# Pantry V2.0 - Branching & Contribution Guide

## Overview

To keep development organised and reduce merge conflicts, all team members should follow the workflow outlined below.

---

## Branch Structure

### Main Branch

`main`

The main branch should always contain stable and working code.

Do not commit directly to `main`. Direct pushes are blocked, so all changes, including documentation, go through a Pull Request.

---

## Feature Branches

All development work should be completed in its own branch.

Use `feature/` for new functionality and `fix/` for bug fixes.

Examples:

```text
feature/household-pantry
feature/near-miss-suggestions
feature/expiry-warnings
feature/recipe-privacy
feature/social-auth
fix/expired-items-hidden
```

Create a new branch before starting work:

```bash
git switch main
git pull origin main
git switch -c feature/your-feature-name
```

---

## Development Workflow

### 1. Pull Latest Changes

Before starting work:

```bash
git switch main
git pull origin main
```

### 2. Create Feature Branch

```bash
git switch -c feature/your-feature-name
```

### 3. Complete Work

Make changes related only to the feature assigned.

### 4. Commit Changes

Use clear and descriptive commit messages.

Examples:

```bash
git commit -m "Add Google login"
git commit -m "Create household pantry model"
git commit -m "Show expired items on home screen"
```

### 5. Push Branch

```bash
git push -u origin feature/your-feature-name
```

### 6. Create Pull Request

Open a Pull Request into `main`.

### Pull Request Process

1. Create a feature branch from `main`
2. Complete the assigned task
3. Push the branch to GitHub
4. Open a Pull Request into `main`
5. Get it reviewed:
   - Allan's and Brix's Pull Requests are reviewed by Adam
   - Adam's Pull Requests are reviewed by Allan and Brix together
6. Merge using **Squash and Merge**
7. The feature branch is deleted automatically after merging

### Merge Strategy

The Pantry project uses **Squash and Merge** for all Pull Requests.

This keeps the commit history clean and prevents multiple small development commits from cluttering the `main` branch.

Example:

Feature Branch Commits:

```text
Fix navbar spacing
Fix navbar spacing again
Update CSS
Remove unused code
```

After Squash and Merge:

```text
Add responsive navigation layout
```

This results in a cleaner and more readable project history.

---

## Commit Message Guidelines

Use short, descriptive commit messages.

Good Examples:

```text
Add Facebook login
Create household pantry model
Implement near-miss recipe suggestions
Fix expired items missing from pantry list
Update README setup instructions
```

Avoid:

```text
stuff
update
changes
fixed things
```

---

## Django Rules

### Migrations

Commit your migrations. They are how everyone's database ends up with the same schema.

```bash
# After changing a model, create the migration
python manage.py makemigrations

# Apply it to your local database
python manage.py migrate

# Stage the new migration file(s) with your model changes
git add <app>/migrations/
git commit -m "Add household pantry model"
```

Never edit or delete a migration that is already on `main`. If a model needs to change again, make a new migration.

```bash
# Change the model in models.py, then create a NEW migration on top
python manage.py makemigrations

# Check which migrations exist and which are applied
python manage.py showmigrations <app>
```

Pull the latest `main` before running `makemigrations`.

```bash
# Bring your branch up to date with main first
git switch main
git pull origin main
git switch feature/your-feature-name
git merge main

# Apply any migrations other people have merged
python manage.py migrate

# Now create your own migration
python manage.py makemigrations
```

If Django reports "Conflicting migrations detected", the second branch to merge fixes it:

```bash
# 1. Pull main into your branch
git switch main
git pull origin main
git switch feature/your-feature-name
git merge main

# 2. Roll back your own migration locally
#    (use the number of the last migration that came from main)
python manage.py migrate <app> <last-merged-migration-number>

# 3. Delete ONLY your own unmerged migration file
rm <app>/migrations/<your-migration-file>.py

# 4. Recreate your migration on top of main's, and apply it
python manage.py makemigrations
python manage.py migrate
```

### Dependencies and Settings

When you install a new package, update `requirements.txt` in the same Pull Request.

```bash
# Install the package with your virtual environment active
pip install <package-name>

# Record the exact versions of everything installed
pip freeze > requirements.txt

# Commit it alongside the code that uses the package
git add requirements.txt
```

When you add a new setting to `.env`, add its key to `.env.example` with a placeholder value.

```bash
# Add the real value to your own .env (never committed)
nano .env

# Add the same key with a placeholder to .env.example, e.g. NEW_SETTING=change-me
nano .env.example

# Commit only the example file
git add .env.example
```

### Before Opening a Pull Request

```bash
# Check the project for configuration problems
python manage.py check

# Fail if a model changed without a matching migration
python manage.py makemigrations --check --dry-run
```

---

## Project Standards

- Pull latest changes before starting work.
- Keep commits focused on a single task.
- Test changes before pushing.
- Do not commit `.venv`, database dumps, or `.env` files.
- Resolve merge conflicts immediately.

---

## Files Ignored by Git

The following files should never be committed:

```text
__pycache__/
*.pyc
.venv/
venv/
env/
.env

*.sql
*.dump

staticfiles/
media/

.vscode/
.idea/
.DS_Store
Thumbs.db
```
