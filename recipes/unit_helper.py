import re

# ============================================================================
# AMOUNT PARSING / UNIT CONVERSION
# ============================================================================
# recipe amounts come from TheMealDB as free text like "400g", "2 cups",
# "to taste". these helpers turn that text into a number + unit, then
# convert it into the one unit the ingredient is stored in (g, ml or each)
# so every recipe line lines up with the pantry. anything we can't convert
# cleanly comes back as None so the import can skip that recipe.

# tried in order: mixed number ("1 1/2 cups"), fraction ("1/2 cup"),
# then plain decimal/integer ("400g", "2 cups")
MIXED_NUMBER_RE = re.compile(r"^\s*(\d+)\s+(\d+)\s*/\s*(\d+)\s*([a-zA-Z]*)")
FRACTION_RE = re.compile(r"^\s*(\d+)\s*/\s*(\d+)\s*([a-zA-Z]*)")
DECIMAL_RE = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*([a-zA-Z]*)")

# some measures use the single fraction characters, swap them for normal text
UNICODE_FRACTIONS = {
    "½": " 1/2", "¼": " 1/4", "¾": " 3/4",
    "⅓": " 1/3", "⅔": " 2/3", "⅛": " 1/8",
}

# measures that aren't a real amount - these lines still show on the recipe
# but don't get tracked against the pantry
UNTRACKED_WORDS = [
    "pinch", "to taste", "to serve", "garnish", "dash", "splash", "drizzle",
    "sprinkling", "sprinkle", "sprinking",  # sprinking is a typo that's in the data
    "for frying", "for greasing", "for brushing", "to glaze", "topping",
    "handful", "knob", "dusting", "as required",
]

# maps free-text unit words/synonyms onto the units we know how to convert
UNIT_SYNONYMS = {
    "g": "g", "gram": "g", "grams": "g", "gm": "g",
    "kg": "kg", "kilogram": "kg", "kilograms": "kg",
    "oz": "oz", "ounce": "oz", "ounces": "oz",
    "lb": "lb", "lbs": "lb", "pound": "lb", "pounds": "lb",
    "ml": "ml", "millilitre": "ml", "milliliter": "ml", "millilitres": "ml",
    "l": "l", "litre": "l", "liter": "l", "litres": "l",
    "tsp": "tsp", "teaspoon": "tsp", "teaspoons": "tsp",
    "tbsp": "tbsp", "tbs": "tbsp", "tblsp": "tbsp", "tbls": "tbsp",
    "tablespoon": "tbsp", "tablespoons": "tbsp",
    "cup": "cup", "cups": "cup",
}

# words that just mean "this many of the thing" e.g. "2 cloves", "1 large",
# "3 chopped" - all of these get counted as each
COUNT_WORDS = {
    "each", "x", "whole", "large", "medium", "small",
    "clove", "cloves", "slice", "slices", "sprig", "sprigs", "leaf", "leaves",
    "can", "cans", "tin", "tins", "stalk", "stalks", "stick", "sticks",
    "piece", "pieces",
    "chopped", "diced", "sliced", "minced", "crushed", "grated", "ground",
    "peeled", "drained", "melted", "softened", "beaten", "sifted", "fresh",
    "frozen", "ripe", "halved", "quartered", "cooked", "raw", "thinly",
    "finely", "roughly",
}

# how much of the base unit each unit is worth - only units with a known, safe conversion
MASS_TO_GRAMS = {"g": 1, "kg": 1000, "oz": 28, "lb": 454}
VOLUME_TO_ML = {"ml": 1, "l": 1000, "tsp": 5, "tbsp": 15, "cup": 240}


def normalize_unit(unit_text):
    """Maps a unit word onto our known units. Returns None for words we don't know, like "bunch"."""
    # just a number on its own e.g. "2" means 2 of the thing
    if not unit_text:
        return "each"
    if unit_text in UNIT_SYNONYMS:
        return UNIT_SYNONYMS[unit_text]
    if unit_text in COUNT_WORDS:
        return "each"
    return None


def parse_measure(measure_text):
    """Splits a free-text measure like '400g' or '1 1/2 cups' into (quantity, unit).

    Returns (None, "untracked") for things like "pinch" or "to taste", and
    (None, None) if we can't make sense of it at all.
    """
    text = (measure_text or "").strip().lower()

    for symbol, replacement in UNICODE_FRACTIONS.items():
        text = text.replace(symbol, replacement)
    text = text.strip()

    # no amount given at all, so there's nothing to track
    if not text:
        return None, "untracked"

    for word in UNTRACKED_WORDS:
        if word in text:
            return None, "untracked"

    # "juice of 1" or "zest of 1" really just means 1 of the fruit
    for prefix in ["zest and juice of", "juice of", "zest of"]:
        if text.startswith(prefix):
            text = text[len(prefix):].strip()

    mixed_match = MIXED_NUMBER_RE.match(text)
    fraction_match = FRACTION_RE.match(text)
    decimal_match = DECIMAL_RE.match(text)

    if mixed_match:
        whole, num, den, unit_text = mixed_match.groups()
        quantity = float(whole) + float(num) / float(den)
    elif fraction_match:
        num, den, unit_text = fraction_match.groups()
        quantity = float(num) / float(den)
    elif decimal_match:
        qty_text, unit_text = decimal_match.groups()
        quantity = float(qty_text.replace(",", "."))
    else:
        # no number at all e.g. "bunch"
        return None, None

    unit = normalize_unit(unit_text)
    if unit is None:
        return None, None

    return quantity, unit


def to_base(quantity, unit):
    """Converts mass units to grams and volume units to mL. each stays as each."""
    if unit in MASS_TO_GRAMS:
        return quantity * MASS_TO_GRAMS[unit], "g"
    if unit in VOLUME_TO_ML:
        return quantity * VOLUME_TO_ML[unit], "ml"
    return quantity, unit


def to_grams(quantity, unit, ingredient):
    """Works out how many grams an amount is. Cups, spoons and each need the ingredient's USDA weights."""
    if unit in MASS_TO_GRAMS:
        return quantity * MASS_TO_GRAMS[unit]

    if unit in VOLUME_TO_ML:
        ml = quantity * VOLUME_TO_ML[unit]
        # 1 cup is 240 ml and 1 tbsp is 15 ml, so either weight tells us grams per ml
        if ingredient.grams_per_cup:
            return ml * ingredient.grams_per_cup / 240
        if ingredient.grams_per_tbsp:
            return ml * ingredient.grams_per_tbsp / 15
        return None

    if unit == "each" and ingredient.grams_per_each:
        return quantity * ingredient.grams_per_each

    return None


def from_grams(grams, ingredient):
    """Turns grams back into whatever unit the ingredient is stored in."""
    if ingredient.unit == "g":
        return grams

    if ingredient.unit == "each" and ingredient.grams_per_each:
        return grams / ingredient.grams_per_each

    if ingredient.unit == "ml":
        if ingredient.grams_per_cup:
            return grams / (ingredient.grams_per_cup / 240)
        if ingredient.grams_per_tbsp:
            return grams / (ingredient.grams_per_tbsp / 15)

    return None


def convert_to_ingredient_unit(quantity, unit, ingredient):
    """Converts a parsed recipe amount into the unit this ingredient is stored in. Returns None if it can't be done."""
    # easy case - the same kind of unit, e.g. kg -> g or tbsp -> ml
    base_quantity, base_unit = to_base(quantity, unit)
    if base_unit == ingredient.unit:
        return round(base_quantity, 2)

    # different kinds of unit (e.g. cups of flour but flour is stored in g)
    # so go through grams using the USDA weights, if we have them
    grams = to_grams(quantity, unit, ingredient)
    if grams is None:
        return None

    result = from_grams(grams, ingredient)
    if result is None:
        return None

    return round(result, 2)
