## CSS Guide — Structure & Template Conventions

Purpose: document where styles live and how templates load them, so the team stays consistent. Pantry uses **Bootstrap 5.3.8** for as much as possible, with our own styles added only where Bootstrap can't do the job.

---

### 1) File responsibilities (what goes where)

| File | Loaded by | Responsibility |
|---|---|---|
| Bootstrap 5.3.8 (CDN) | `base.html` (always) | Layout, grid, components, utilities |
| `static/css/base.css` | `base.html` (always) | Brand colour overrides, and custom components shared across pages |
| `static/css/<page>.css` | One template only | Rules only that page needs |

Guideline: use a Bootstrap component or utility class first. If a custom class is genuinely shared across 3+ pages, it belongs in `base.css`, not duplicated.

Django needs to know where `static/` is. In `config/settings.py`:

```python
STATICFILES_DIRS = [BASE_DIR / "static"]
```

---

### 2) Template pattern (blocks & ordering)

`templates/base.html` loads Bootstrap, then our shared CSS, then exposes a block for page CSS:

```django
{% load static %}
<head>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/css/bootstrap.min.css" integrity="sha384-<CSS-HASH>" crossorigin="anonymous">
    <link rel="stylesheet" href="{% static 'css/base.css' %}">
    {% block extra_css %}{% endblock %}
</head>
<body>
    {% block content %}{% endblock %}
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/js/bootstrap.bundle.min.js" integrity="sha384-<JS-HASH>" crossorigin="anonymous"></script>
</body>
```

Generate each hash once and paste it after `sha384-`:

```bash
curl -s https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/css/bootstrap.min.css | openssl dgst -sha384 -binary | openssl base64 -A; echo
curl -s https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/js/bootstrap.bundle.min.js | openssl dgst -sha384 -binary | openssl base64 -A; echo
```

A typical page extends `base.html` and loads only the page CSS it needs:

```django
{% extends "base.html" %}
{% load static %}
{% block title %}Shopping List — Pantry{% endblock %}
{% block extra_css %}
<link rel="stylesheet" href="{% static 'css/shopping.css' %}">
{% endblock %}
{% block content %}
  <!-- page markup -->
{% endblock %}
```

Why: Bootstrap and the brand overrides are applied consistently, while pages opt into extra CSS only when needed. `{% load static %}` is needed in every template that uses `{% static %}`.

---

### 3) Adding a new page (step-by-step)

1. Create the template, extend `base.html`, and build it from Bootstrap components and utilities.
2. Only if needed, add `static/css/<page>.css` and load it in the `extra_css` block — check `base.css` first in case it already covers it.
3. Add the view in the app's `views.py` and its URL in the app's `urls.py`.
4. If the page should appear in the navigation, add the link in `templates/base.html`.

---

### 4) Naming and organization rules

- Prefix our own classes with what they belong to: `.pantry-expiry-badge`, `.recipe-missing-list`, instead of generic names like `.box` or `.item`.
- Use Bootstrap's grid and responsive utilities for layout. If you must write a media query, use Bootstrap's breakpoints (576px, 768px, 992px, 1200px, 1400px) and keep it next to the component it changes.
- No CSS resets — Bootstrap already includes one.

---

### 5) Design tokens

`base.css` defines the brand colours and points Bootstrap's primary colour at them:

```css
:root {
    --pantry-brand: #0f6e56;
    --pantry-brand-hover: #1d9e75;

    --bs-primary: #0f6e56;
    --bs-primary-rgb: 15, 110, 86;
}

.btn-primary {
    --bs-btn-bg: var(--pantry-brand);
    --bs-btn-border-color: var(--pantry-brand);
    --bs-btn-hover-bg: var(--pantry-brand-hover);
    --bs-btn-hover-border-color: var(--pantry-brand-hover);
}
```

Notes:
- New CSS should use `var(--...)` tokens, not hardcoded hex values.
- Add new tokens to `base.css` only.
