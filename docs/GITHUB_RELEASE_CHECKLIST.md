# GitHub Release Checklist

## Repository name

```text
safesku
```

## Keep in Git

- application source code
- tests
- SAM template
- Docker/local infrastructure definitions
- compact demo artifacts and manifests
- scripts
- README and documentation
- evaluation summaries
- Mermaid diagrams

## Keep out of Git

```text
.venv/
.aws-sam/
.git/
data/runtime/
data/runtime*/
data/raw/
data/processed/large/
data/amazon/full/
node_modules/
__pycache__/
*.pyc
```

Never commit the full Amazon metadata corpus or local runtime databases.

## First clean push

```powershell
git status --short
git diff --stat
python -m pytest -q apps\api\tests
sam validate --template-file infra\build-it\template.yaml --region ap-south-1
git add README.md docs apps/api/tests/conftest.py
git commit -m "docs: prepare Build It submission"
git push origin HEAD
```

## Optional GitHub CLI route

If GitHub CLI is installed and authenticated:

```powershell
gh repo create safesku --public --source=. --remote=origin --push
```

## Final repository quality bar

The repository landing page should answer, in order:

1. What problem does SafeSKU solve?
2. What is the single strongest product insight?
3. What real data does it use?
4. How does the Build It AWS stack fit?
5. What happens in one investigation?
6. How is unsafe model autonomy prevented?
7. What results have been measured?
8. How do I run the demo?
