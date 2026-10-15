import requests

# everything here talks to TheMealDB's free api - no api key needed

BASE_URL = "https://www.themealdb.com/api/json/v1/1/"


def fetch_ingredient_list():
    # gets the full ingredient list from TheMealDB, used by the
    # import_ingredients command to fill our Ingredient table

    try:
        url = BASE_URL + "list.php"
        response = requests.get(url, params={"i": "list"}, timeout=10)
        response.raise_for_status()

        data = response.json()

        # api returns null if nothing is found
        if data["meals"] is None:
            return []

        return data["meals"]

    except requests.exceptions.ConnectionError:
        print("no internet connection")
        return []

    except requests.exceptions.Timeout:
        print("request timed out")
        return []

    except Exception as error:
        print(f"something went wrong: {error}")
        return []


def search_recipes_by_letter(letter):
    # returns every recipe whose name starts with the given letter
    # the free api doesn't have a "list all recipes" endpoint, so the
    # import_recipes command calls this once for each letter a-z

    try:
        url = BASE_URL + "search.php"
        response = requests.get(url, params={"f": letter}, timeout=10)
        response.raise_for_status()

        data = response.json()

        if data["meals"] is None:
            return []

        return data["meals"]

    except requests.exceptions.ConnectionError:
        print("no internet connection")
        return []

    except requests.exceptions.Timeout:
        print(f"request timed out for '{letter}'")
        return []

    except Exception as error:
        print(f"couldnt get recipes for '{letter}': {error}")
        return []


def get_ingredients(meal):
    # the api stores ingredients as strIngredient1, strIngredient2 etc up to 20
    # this turns that into a normal list

    ingredients = []

    for i in range(1, 21):
        # these can come back as None as well as "", so fall back to ""
        name = meal.get(f"strIngredient{i}") or ""
        measure = meal.get(f"strMeasure{i}") or ""

        # skip empty slots
        if name.strip():
            ingredients.append({
                "name": name.strip(),
                "measure": measure.strip()
            })

    return ingredients
