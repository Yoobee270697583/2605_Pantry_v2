import re
import unicodedata

# works out a pantry category (fruit_veg, meat_seafood...) from an ingredient's
# name. TheMealDB doesn't give ingredients a category its strType is empty for
# nearly all of them, so we set one ourselves when the ingredient is imported.
# users can't pick the category any more that's how sirloin steak ended up
# as a drink in V1 because the users were able to select the category for it. Also if a guess is wrong this can be fixed in the admin (Ingredients ->
# Category) and it updates for everyone.
#
# how this will works:
#   1. two-or-more word phrases first, longest first, e.g. "chicken stock" or
#      "red pepper flakes" these catch the names a single word would get wrong
#   2. then single words, checked category by category in TIER order, so
#      "fish sauce" is a sauce before it's a fish and "beef stock" is a staple
#      before it's meat
#   3. nothing matched -> "other"
# plurals don't matter - "tomatoes" and "tomato" both become "tomato"


# --- 1. phrases that a single word would get wrong ---
PHRASES = {
    # tinned/jarred, not fresh
    "chopped tomato": "pantry_staples",
    "canned tomato": "pantry_staples",
    "tinned tomato": "pantry_staples",
    "diced tomato": "pantry_staples",
    "crushed tomato": "pantry_staples",
    "tomato puree": "pantry_staples",
    "coconut milk": "pantry_staples",
    "coconut cream": "pantry_staples",
    "peanut butter": "pantry_staples",
    "cream of tartar": "pantry_staples",
    "baking powder": "pantry_staples",
    "custard powder": "pantry_staples",
    "egg noodle": "pantry_staples",
    "taco shell": "pantry_staples",
    "tortilla chip": "pantry_staples",
    "bread flour": "pantry_staples",
    "dried fruit": "pantry_staples",
    "kidney bean": "pantry_staples",
    "fruit mix": "pantry_staples",
    "mars bar": "pantry_staples",
    "turkish delight": "pantry_staples",
    "vine leaves": "pantry_staples",
    "dulce de leche": "condiments",

    # fresh, not a spice or a tin
    "garlic clove": "fruit_veg",
    "red pepper": "fruit_veg",
    "green pepper": "fruit_veg",
    "yellow pepper": "fruit_veg",
    "bell pepper": "fruit_veg",
    "sweet pepper": "fruit_veg",
    "egg plant": "fruit_veg",
    "green bean": "fruit_veg",
    "runner bean": "fruit_veg",
    "broad bean": "fruit_veg",
    "french bean": "fruit_veg",
    "bean sprout": "fruit_veg",
    "spring onion": "fruit_veg",
    "lemon juice": "fruit_veg",
    "lime juice": "fruit_veg",
    "chestnut mushroom": "fruit_veg",   # not chestnuts the nut
    "chinese leaf": "fruit_veg",
    "morning glory": "fruit_veg",
    "scotch bonnet": "fruit_veg",
    "stir fry": "fruit_veg",            # stir-fry vegetables, not fries

    # spices, not the fresh thing
    "red pepper flake": "herbs_spices",
    "chilli flake": "herbs_spices",
    "chili flake": "herbs_spices",
    "chilli powder": "herbs_spices",
    "chili powder": "herbs_spices",
    "garlic powder": "herbs_spices",
    "onion powder": "herbs_spices",
    "ground ginger": "herbs_spices",
    "mustard powder": "herbs_spices",
    "mustard seed": "herbs_spices",
    "fennel seed": "herbs_spices",
    "coriander seed": "herbs_spices",
    "cumin seed": "herbs_spices",
    "caraway seed": "herbs_spices",
    "nigella seed": "herbs_spices",
    "celery seed": "herbs_spices",
    "lime leave": "herbs_spices",
    # dried chillies are used like a spice, fresh ones are fruit & veg
    "dried chillies": "herbs_spices",
    "dried red chillies": "herbs_spices",
    "ancho chillies": "herbs_spices",
    "birds eye chillies": "herbs_spices",
    "bouquet garni": "herbs_spices",
    "ras el hanout": "herbs_spices",

    # sauces/vinegars named after a drink
    "wine vinegar": "condiments",
    "cider vinegar": "condiments",

    # dairy named like something else
    "ice cream": "frozen",
    "sour cream": "dairy_eggs",
    "almond milk": "dairy_eggs",
    "oat milk": "dairy_eggs",
    "soy milk": "dairy_eggs",
    "soya milk": "dairy_eggs",
    "rice milk": "dairy_eggs",
    "cream cheese": "dairy_eggs",
    "fromage frais": "dairy_eggs",
    "queso fresco": "dairy_eggs",
    "black pudding": "meat_seafood",

    "burger bun": "bakery",
    "bread roll": "bakery",
}


# --- 2. single words, checked in this order ---
TIERS = [
    ("frozen", [
        "frozen", "ice", "sorbet",
        "fries", "tequenos",
    ]),
    ("drinks", [
        "wine", "brandy", "rum", "vodka", "whisky", "whiskey", "gin", "beer", "ale",
        "stout", "cider", "sherry", "port", "sake", "cordial", "juice", "lemonade",
        "cola", "coffee", "espresso", "tea", "water", "champagne", "prosecco",
        "vermouth", "liqueur", "kirsch", "amaretto", "tequila", "cognac", "marsala",
        "marnier", "cafe",
    ]),
    ("condiments", [
        "sauce", "hotsauce", "ketchup", "mustard", "mayonnaise", "mayo", "vinegar",
        "salsa", "dressing", "vinaigrette", "jam", "marmalade", "honey", "syrup",
        "treacle", "molasses", "pesto", "paste", "chutney", "relish", "pickle", "dip",
        "gravy", "tahini", "hummus", "mirin", "aioli", "glaze", "horseradish",
        "doubanjiang", "gochujang", "sriracha", "nutella", "stroop", "sirop", "prahok",
    ]),
    ("bakery", [
        "bread", "bun", "brioche", "naan", "tortilla", "wrap", "pitta", "pita",
        "bagel", "croissant", "muffin", "baguette", "ciabatta", "focaccia",
        "sourdough", "crumpet", "pastry", "biscuit", "cookie", "cookies", "cake",
        "shortbread", "brownie", "brownies", "waffle", "pancake", "crepe",
        "flatbread", "chapati", "roti", "meringue", "sponge",
        "pudding", "toast", "dough", "phyllo", "filo", "knafeh", "casabe",
        "colouring", "coloring",
    ]),
    ("pantry_staples", [
        "flour", "sugar", "rice", "pasta", "spaghetti", "penne", "macaroni",
        "fettuccine", "fettucine", "linguine", "tagliatelle", "lasagne", "lasagna",
        "farfalle", "rigatoni", "fusilli", "orzo", "noodle", "vermicelli", "couscous",
        "khus", "bulgur", "quinoa", "oat", "barley", "polenta", "semolina", "lentil",
        "chickpea", "bean", "dal", "daal", "oil", "stock", "broth", "bouillon",
        "yeast", "cornstarch", "cornflour", "starch", "gelatine", "gelatin", "cocoa",
        "cacao", "chocolate", "almond", "cashew", "peanut", "walnut", "pecan",
        "hazelnut", "pistachio", "macadamia", "nut", "sesame", "seed", "breadcrumb",
        "panko", "cracker", "cereal", "raisin", "sultana", "currant", "prune",
        "marshmallow", "sprinkle", "vanilla", "bicarbonate", "tamarind", "coconut",
        "passata", "puree", "olive", "caper", "evaporated", "gnocchi", "ramen",
        "udon", "soba", "tofu", "lard", "suet",
        "tempeh", "buckwheat", "cornmeal", "freekeh", "grit", "farine", "fideo",
        "masarepa", "oatmeal", "rye", "wheat", "grain", "tapioca", "shortening",
        "marzipan", "nougatine", "caramel", "toffee", "popcorn", "pretzel",
        "mincemeat", "peel", "chestnut", "palm", "sauerkraut", "papelon",
        "sevaiiya", "wonton", "hazlenut", "hail",
    ]),
    ("herbs_spices", [
        "salt", "pepper", "peppercorn", "basil", "thyme", "rosemary", "oregano",
        "parsley", "coriander", "cilantro", "mint", "dill", "sage", "bay",
        "tarragon", "chive", "marjoram", "chervil", "cumin", "turmeric", "paprika",
        "cinnamon", "nutmeg", "clove", "cardamom", "saffron", "cayenne", "masala",
        "curry", "seasoning", "spice", "allspice", "fenugreek", "anise", "caraway",
        "sumac", "zaatar", "mace", "cajun", "harissa", "powder",
        "ancho", "savoury", "sorrel", "annatto", "cardomom", "mahleb", "jerk",
        "panch", "pandan", "biber", "sazon",
    ]),
    ("meat_seafood", [
        "chicken", "beef", "pork", "lamb", "mutton", "mince", "steak", "bacon", "ham",
        "sausage", "chorizo", "salami", "pepperoni", "pancetta", "prosciutto", "veal",
        "turkey", "duck", "goose", "venison", "brisket", "rib", "oxtail", "kidney",
        "liver", "goat", "rabbit", "pheasant", "quail", "doner", "meat", "meatball",
        "fish", "salmon", "tuna", "cod", "haddock", "hake", "pollock", "mackerel",
        "sardine", "anchovy", "trout", "tilapia", "halibut", "bass", "bream",
        "monkfish", "prawn", "shrimp", "squid", "calamari", "octopus", "mussel",
        "clam", "scallop", "crab", "lobster", "oyster", "crayfish", "seafood",
        "kipper", "herring",
        "barramundi", "snapper", "pilchard", "codfish", "conch", "frog", "tripe",
        "trotter", "shank", "chuck", "roast", "kielbasa", "kabanos", "morcilla",
        "jamon", "falafel",
    ]),
    ("dairy_eggs", [
        "milk", "cream", "cheese", "butter", "ghee", "yogurt", "yoghurt", "creme",
        "fraiche", "egg", "buttermilk", "custard", "quark", "kefir", "cheddar",
        "mozzarella", "parmesan", "parmigiano", "feta", "gouda", "gruyere",
        "pecorino", "mascarpone", "ricotta", "brie", "camembert", "halloumi",
        "paneer", "stilton", "emmental", "provolone", "manchego", "burrata", "colby",
        "malai",
    ]),
    ("fruit_veg", [
        "onion", "garlic", "shallot", "leek", "potato", "tomato", "carrot", "celery",
        "celeriac", "spinach", "kale", "lettuce", "rocket", "arugula", "cabbage",
        "broccoli", "cauliflower", "courgette", "zucchini", "aubergine", "eggplant",
        "mushroom", "chilli", "chili", "jalapeno", "cucumber", "avocado", "beetroot",
        "beet", "pea", "corn", "sweetcorn", "squash", "pumpkin", "parsnip", "turnip",
        "swede", "radish", "asparagus", "artichoke", "fennel", "okra", "ginger",
        "lemongrass", "lemon", "lime", "orange", "apple", "banana", "berry",
        "strawberry", "raspberry", "blueberry", "blackberry", "cranberry", "cherry",
        "grape", "mango", "pineapple", "peach", "nectarine", "pear", "plum",
        "apricot", "fig", "date", "kiwi", "melon", "watermelon", "pomegranate",
        "papaya", "rhubarb", "salad", "green", "vegetable", "veg", "choy", "pak",
        "scallion", "watercress", "chard", "sprout", "edamame", "plantain", "yam",
        "cassava",
        # plural chillies, and spellings TheMealDB gets wrong (Avacado, Challots...)
        "chillies", "avacado", "challot", "choi", "fruit", "ackee", "bamboo",
        "breadfruit", "callaloo", "cassaba", "galangal", "grapefruit", "longan",
        "mulukhiyah", "passion", "pois", "redcurrant", "yucca", "yuca", "taro",
        "shatkora", "yautia",
    ]),
]


def to_words(text):
    """Lower case, accents removed (gruyère -> gruyere), split into words, each made singular."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return [singular(word) for word in re.findall(r"[a-z]+", text.lower())]


def singular(word):
    """Rough singular so plurals match: tomatoes -> tomato, berries -> berry, radishes -> radish.
    Doesn't need to be proper English, just the same for the rule and the name."""
    if len(word) <= 3:
        return word
    if word.endswith("ies"):
        return word[:-3] + "y"
    if word.endswith("oes"):
        return word[:-2]
    if word.endswith(("ches", "shes", "sses", "xes")):
        return word[:-2]
    # asparagus, couscous, hummus, swiss - not plurals
    if word.endswith("s") and not word.endswith(("ss", "us")):
        return word[:-1]
    return word


# the rules above, run through to_words once so they match the same way as names.
# longest phrases first so "red pepper flake" wins over "red pepper"
_PHRASES = sorted(
    ((" ".join(to_words(phrase)), category) for phrase, category in PHRASES.items()),
    key=lambda rule: -len(rule[0].split()),
)
_TIERS = [(category, {to_words(word)[0] for word in words}) for category, words in TIERS]


def guess_category(name):
    """Returns the category value (e.g. "meat_seafood") for an ingredient name, or "other"."""
    words = to_words(name)
    # spaces at both ends so " pepper " can't match inside "peppercorn"
    padded = " " + " ".join(words) + " "

    for phrase, category in _PHRASES:
        if f" {phrase} " in padded:
            return category

    for category, keywords in _TIERS:
        for word in words:
            if word in keywords:
                return category

    return "other"
