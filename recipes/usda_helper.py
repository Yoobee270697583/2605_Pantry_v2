import os
import requests

# everything here talks to USDA FoodData Central. needs USDA_API_KEY in .env -
# DEMO_KEY works but is limited to 30 requests an hour, so foods are fetched
# in batches instead of one at a time

BASE_URL = "https://api.nal.usda.gov/fdc/v1/"

# the most foods the api will give back in one request
BATCH_SIZE = 20

# portion names that mean "one of the thing", in the order we'd rather use them
# e.g. for onions we want "medium" (110g) before "large" (150g)
EACH_WORDS = ["medium", "whole", "clove", "large", "small", "piece", "slice", "thigh", "breast", "fillet"]


def get_headers():
    # the key goes in a header instead of the url, so it doesn't get printed
    # if a request fails and the error message shows the url
    return {"X-Api-Key": os.environ.get("USDA_API_KEY", "DEMO_KEY")}


def search_foods(query):
    # searches USDA foods by name - handy in the django shell for looking up
    # the fdc id of an ingredient. only searches SR Legacy because those foods
    # have household portions like "1 cup" or "1 medium"

    try:
        url = BASE_URL + "foods/search"
        params = {"query": query, "dataType": "SR Legacy", "pageSize": 10}
        response = requests.get(url, headers=get_headers(), params=params, timeout=10)
        response.raise_for_status()

        return response.json().get("foods", [])

    except Exception as error:
        print(f"couldnt search USDA for '{query}': {error}")
        return []


def get_foods(fdc_ids):
    # gets full details (including portion weights) for a list of fdc ids,
    # 20 at a time since that's the most the api allows per request

    foods = []

    for start in range(0, len(fdc_ids), BATCH_SIZE):
        batch = fdc_ids[start:start + BATCH_SIZE]

        try:
            url = BASE_URL + "foods"
            params = {"fdcIds": ",".join(str(fdc_id) for fdc_id in batch)}
            response = requests.get(url, headers=get_headers(), params=params, timeout=10)

            if response.status_code == 429:
                print("hit the USDA rate limit - wait an hour or put your own USDA_API_KEY in .env")
                return foods

            response.raise_for_status()
            foods += response.json()

        except requests.exceptions.ConnectionError:
            print("no internet connection")
            return foods

        except requests.exceptions.Timeout:
            print("request timed out")

        except Exception as error:
            print(f"couldnt get foods from USDA: {error}")

    return foods


def find_portion_grams(portions, words):
    """Finds the first portion whose name starts with one of the words (checked in order) and returns the grams for one. None if there isn't one."""
    for word in words:
        for portion in portions:
            # SR Legacy foods keep the portion name in "modifier" e.g. "cup, chopped" or "tbsp"
            name = (portion.get("modifier") or "").strip().lower()
            amount = portion.get("amount") or 1
            grams = portion.get("gramWeight")

            if name.startswith(word) and grams:
                # some portions are for more than one e.g. "3 cloves", so divide to get one
                return round(grams / amount, 2)

    return None


def get_portion_weights(food):
    """Pulls grams per cup, tbsp and each out of a USDA food. Anything it can't find stays None."""
    portions = food.get("foodPortions", [])

    grams_per_cup = find_portion_grams(portions, ["cup"])
    grams_per_tbsp = find_portion_grams(portions, ["tbsp", "tablespoon"])

    # no tablespoon weight but there's a teaspoon one - a tbsp is 3 tsp
    if grams_per_tbsp is None:
        grams_per_tsp = find_portion_grams(portions, ["tsp", "teaspoon"])
        if grams_per_tsp:
            grams_per_tbsp = round(grams_per_tsp * 3, 2)

    grams_per_each = find_portion_grams(portions, EACH_WORDS)

    return {
        "grams_per_cup": grams_per_cup,
        "grams_per_tbsp": grams_per_tbsp,
        "grams_per_each": grams_per_each,
    }
