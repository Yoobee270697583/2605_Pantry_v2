# Pantry V2.0

A Django web app for managing your pantry, recipes, meal planning, and shopping. A rebuild of [Pantry V1.0](https://github.com/Yoobee270697583/pantry-2603-assessment2-2026) on a new stack.

**Tagline:** Use More. Waste Less.

---

## Tech Stack

- **Backend:** Python 3.12 / Django 5.2 LTS
- **Database:** PostgreSQL
- **Frontend:** Django templates, Bootstrap 5.3.8
- **Hosting:** AWS

---

## Project Structure

```
config/             Django project settings and root URLs
manage.py           Django management commands
requirements.txt    Python dependencies
.env.example        Template for your local .env file
```

---

## Setup & Running Locally

### 1. Clone the repository

```
git clone https://github.com/Yoobee270697583/2605_Pantry_v2.git
cd 2605_Pantry_v2
```

### 2. Create a virtual environment

**Mac / Linux**

```
python3.12 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```
pip install -r requirements.txt
```

### 4. Set up the database and `.env`

Create an empty PostgreSQL database called `pantry`, then copy `.env.example` to `.env` and fill in your own values (database password and a `SECRET_KEY`). Never commit `.env`.

Generate a `SECRET_KEY` with:

```
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### 5. Run the application

```
python manage.py migrate
python manage.py runserver
```

The app will be available at:

```
http://127.0.0.1:8000
```

### 6. Deactivate the virtual environment

```
deactivate
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the branching/PR workflow and [CSS_GUIDE.md](CSS_GUIDE.md) for stylesheet structure and conventions.

---

## Team

- **Allan** — Product Owner & Scrum Master
- **Adam** — Lead Developer
- **Brix** — Database Administrator
