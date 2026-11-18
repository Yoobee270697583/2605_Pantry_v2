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
recipes/            Ingredient and recipe models, TheMealDB helpers and import commands
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

### 5. Create the tables and load the recipe data

```
python manage.py migrate
python manage.py import_ingredients
python manage.py merge_ingredients
python manage.py import_usda_portions
python manage.py import_recipes
```

- `import_ingredients` loads TheMealDB's ingredient list
- `merge_ingredients` merges ingredients TheMealDB lists more than once (e.g. Onions and Yellow Onion into Onion) and saves the other names as aliases, plus a few spellings only some recipes use (e.g. Gruyere)
- `import_usda_portions` adds USDA gram weights for common ingredients, so amounts like "1 cup flour" can be converted. The `DEMO_KEY` from `.env.example` works for this
- `import_ingredients` also sets each ingredient's pantry category (Fruit & Vegetables, Meat & Seafood...) from its name, since TheMealDB doesn't give one. Fix a wrong one in the admin under Ingredients. After adding words to `recipes/category_helper.py`, run `python manage.py categorise_ingredients` to apply them to ingredients still marked Other
- `import_recipes` loads TheMealDB's recipes. Amounts it can't convert into the ingredient's unit (like "1 bunch") still show on the recipe, they just aren't tracked against the pantry

They're all safe to run again. If you already have a database set up, just run `migrate`, `merge_ingredients` and `import_recipes` to pick up new ingredient names and recipes.

### 6. Run the application

```
python manage.py runserver
```

The app will be available at:

```
http://127.0.0.1:8000
```

### 7. Deactivate the virtual environment

```
deactivate
```

---

## Data Sources

### TheMealDB

Recipes and the ingredient list come from [TheMealDB](https://www.themealdb.com/api.php).

### USDA FoodData Central

Gram weights for common ingredients come from [USDA FoodData Central](https://fdc.nal.usda.gov/). Put your own free key from [api.data.gov](https://api.data.gov/signup/) in `.env` as `USDA_API_KEY`, or leave it as `DEMO_KEY`.

Source: U.S. Department of Agriculture, Agricultural Research Service. FoodData Central. fdc.nal.usda.gov. Public domain (CC0 1.0).

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the branching/PR workflow and [CSS_GUIDE.md](CSS_GUIDE.md) for stylesheet structure and conventions.

---

## Team

- **Allan** — Product Owner & Scrum Master
- **Adam** — Lead Developer
- **Brix** — Database Administrator
