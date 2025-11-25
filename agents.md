# **agents.md**

## **Purpose**

This document defines how agents (contributors, assistants, and automated helpers) should work on the **mkdocs → Notion** feature for Ultimate Notion. It ensures consistent code quality, reproducible testing, and compliance with Ultimate Notion’s contribution standards.

---

# **1. Guiding Principles**

1. Always work inside a fresh **feature branch**, never on `main`.
2. Keep every change **small, tested, and documented**.
3. Do not skip linting, type checking, or pre-commit validation.
4. Write clear commit messages and add/update tests with every feature.
5. Structure work as explicit steps with a status (`pending`, `in_progress`, `complete`).
   There should always be **exactly one** `in_progress` step.

---

# **2. Development Workflow**

## **2.1. Environment Setup**

The following must be installed globally via `pipx`:

```bash
pipx install hatch
pipx install pre-commit
```

Install pre-commit hooks:

```bash
pre-commit install
```

---

## **2.2. Branch Workflow**

1. Create a feature branch:

   ```bash
   git checkout -b feature/mkdocs-import
   ```
2. Implement the feature in small, reviewable increments.
3. Add Google-style docstrings to all new public modules, classes, and functions.

---

## **2.3. Testing Requirements**

### Full test suite (Notion API calls included):

```bash
hatch run test
```

Every PR must include:

* tests for every new feature or behavior,
* updated tests when modifying existing logic,
* coverage for markdown parsing, directory operations, and mkdocs.yml parsing.

---

## **2.4. Linting and Type Checking**

Run before any commit or PR:

```bash
hatch run lint-fix
hatch run checks
```

All code must satisfy:

* **ruff** (style + lint),
* **mypy** (types).

---

## **2.5. Commit Requirements**

Each commit must:

* pass pre-commit,
* include descriptive messages,
* reference issues when appropriate,
* never leave failing tests behind.

---

# **3. Execution Pattern (For AI Agents)**

## **3.1. Task Structure**

Every task must be divided into sequential steps with statuses:

| Step | Description               | Status  |
| ---- | ------------------------- | ------- |
| 1    | Identify module to modify | pending |
| 2    | Implement logic           | pending |
| 3    | Write tests               | pending |
| 4    | Add docs                  | pending |
| 5    | Run lint & type checks    | pending |
| 6    | Run offline + full tests  | pending |
| 7    | Commit changes            | pending |

Rules:

* Only **one step** may be `in_progress` at a time.
* Do not skip ahead.
* Mark completed steps as `complete` before proceeding.

---

## **3.2. Agent Behavioral Rules**

Agents must:

* Keep changes small and incremental.
* Update documentation when modifying or adding APIs.
* Avoid large sweeping changes unless previously approved.
* Use best judgment when ambiguity is low.

Agents must not:

* bypass linting, typing, or tests,
* commit directly to `main`,
* write undocumented public APIs,
* create code that touches the Notion API without tests.

---

# **4. Deliverables Required in Every PR**

A valid pull request must include:

1. **Code** — typed, documented, structured.
2. **Tests** — new and updated as required.
3. **Docs** — updates to public API docs and `docs/` materials.
4. **Changelog entry** (if requested by maintainers).
5. **Clear PR description** listing:

   * purpose,
   * approach,
   * touched files,
   * limitations,
   * follow-up tasks.

---

# **5. Validation Checklist**

Before opening a PR:

* [ ] Branch is not `main`
* [ ] All public code has Google-style docstrings
* [ ] New features have tests
* [ ] Updated behavior has updated tests
* [ ] `hatch run test` passes
* [ ] `hatch run lint` passes
* [ ] All pre-commit hooks pass
* [ ] Docs updated
* [ ] PR description is complete

---

# **6. Project-Specific Rules (mkdocs → Notion Feature)**

1. Markdown parsing must integrate with the existing stub in Ultimate Notion.
2. Directory import logic must be modular and testable offline.
3. mkdocs.yml navigation parsing must:

   * be optional,
   * fail gracefully,
   * not require mkdocs to be installed.
4. Page ID mapping must follow patterns maintainers approve (local map file or metadata).
5. Hierarchical structures should match mkdocs nav when provided.
6. Tests should simulate common mkdocs patterns:

   * nested folders,
   * custom nav,
   * relative links,
   * code blocks,
   * images.

---

# **7. Agent Test Suite**

This suite ensures agents follow the rules.
It can be run manually, or embedded into future automation.

---

## **7.1. Pre-Work Tests**

* **Environment Ready**

  * [ ] Can run `hatch`
  * [ ] Can run `pre-commit`
  * [ ] `pre-commit install` completed

* **Repository State**

  * [ ] Current branch is *not* `main`
  * [ ] Feature branch name follows pattern `feature/...`

---

## **7.2. Code Quality Tests**

* **Docstring Enforcement**

  * [ ] Every new function/class/module has a Google-style docstring
  * [ ] Public APIs have parameter + return doc sections

* **Type Enforcement**

  * [ ] All functions have type hints
  * [ ] `mypy` passes

* **Lint Enforcement**

  * [ ] `ruff` passes
  * [ ] Code autoformatted where possible

---

## **7.3. Testing Suite Enforcement**

* Online:

  * [ ] `hatch run test` passes

* Coverage checks:

  * [ ] Markdown conversion tested
  * [ ] Directory walk tested
  * [ ] mkdocs.yml parsing tested
  * [ ] Page hierarchy creation tested

---

## **7.4. Documentation Tests**

* [ ] New APIs are documented in `docs/`
* [ ] Example usage added where appropriate
* [ ] mkdocs.yml integration documented
* [ ] Markdown feature coverage documented (supported elements listed)

---

## **7.5. PR Readiness Tests**

* [ ] PR description includes purpose, approach, files, limitations
* [ ] Branch up to date with `main`
* [ ] No debug prints or temporary code
* [ ] Small, review-ready commits

---

## **7.6. Agent Behavior Compliance**

* [ ] Steps tracked with `pending / in_progress / complete`
* [ ] Exactly one step in `in_progress`
* [ ] No steps skipped
* [ ] No assumptions made without checking the codebase
* [ ] Work done incrementally