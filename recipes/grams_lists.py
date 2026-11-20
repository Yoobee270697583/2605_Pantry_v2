# ============================================================================
# INGREDIENTS STORED IN GRAMS
# ============================================================================
# the import stores each ingredient in whichever unit recipes use most, so dry
# goods that recipes measure in tsp, tbsp or cups (salt, cumin, flour...) ended
# up in ml - but nobody knows how many ml of cumin they have, the packet says
# grams. so these are stored in grams instead. "1 tsp" still converts, using the
# ingredient's grams per cup/tbsp from USDA (import_usda_portions).
# store_in_grams switches ingredients that are already in ml or each.


# the most-used ones - each has its own USDA food in import_usda_portions
MAIN = {
    "Salt", "Sugar", "Brown Sugar", "Baking Powder", "Bicarbonate Of Soda", "Cornstarch",
    "Corn Flour", "Black Pepper", "Cumin", "Cumin Seeds", "Cinnamon", "Paprika", "Smoked Paprika",
    "Allspice", "Oregano", "Turmeric", "Chilli Powder", "Nutmeg", "Cayenne Pepper",
    "Ground Ginger", "Curry Powder", "Garlic Powder", "Cardamom", "Parsley", "Coriander", "Mint",
    "Ginger", "Raisins", "Unsalted Butter", "Greek Yogurt",
}

# rarer ones that have their own USDA food in import_usda_portions too
WITH_OWN_USDA_FOOD = {
    "Bamboo Shoot", "Broad Beans", "Capers", "Flank Steak", "Ground Onion", "Lemon Zest",
    "Mung Bean Sprouts", "Pimento Stuffed Olives", "Pineapple Chunks", "Raw Yucca", "Rhubarb",
    "Sour Pork Sausage", "Tofu",
}

# ingredient -> a similar ingredient in import_usda_portions whose weights it borrows,
# like "Caster Sugar" already uses granulated sugar's USDA food. close enough for
# ingredients that only a few recipes use - e.g. pine nuts weigh about what almonds do.
# import_usda_portions copies the weights across
BORROWED_WEIGHTS = {
    # weigh about the same as almonds
    "Cashews": "Almonds",
    "Pine Nuts": "Almonds",
    "Roasted Peanut": "Almonds",
    "Shelled Hazelnuts": "Almonds",
    "Unsalted Peanuts": "Almonds",
    "Unsalted Pistachio": "Almonds",
    # weigh about the same as cardamom
    "Ground Cardomom": "Cardamom",
    # weigh about the same as cumin
    "Achiote Seeds": "Cumin",
    "All-purpose Seasoning": "Cumin",
    "Biryani Masala": "Cumin",
    "Cajun": "Cumin",
    "Caraway Seed": "Cumin",
    "Chilli Flakes": "Cumin",
    "Chinese five spice powder": "Cumin",
    "Coriander Seeds": "Cumin",
    "Fennel Seeds": "Cumin",
    "Fenugreek": "Cumin",
    "Five Spice Powder": "Cumin",
    "Garam Masala": "Cumin",
    "Gingerbread Spice": "Cumin",
    "Ground Annatto": "Cumin",
    "Ground Clove": "Cumin",
    "Ground Coriander": "Cumin",
    "Ground Mahleb": "Cumin",
    "Harissa Spice": "Cumin",
    "Hot smoked paprika": "Cumin",
    "Italian Seasoning": "Cumin",
    "Kabse Spice": "Cumin",
    "Kampot Pepper": "Cumin",
    "Mixed Spice": "Cumin",
    "Poppy Seeds": "Cumin",
    "Pul Biber": "Cumin",
    "Ras el hanout": "Cumin",
    "Saffron": "Cumin",
    "Sazon Goya With Azafran": "Cumin",
    "Seasoning": "Cumin",
    "Sesame Seed": "Cumin",
    "Sichuan Pepper": "Cumin",
    "Smoky Paprika": "Cumin",
    "Sumac": "Cumin",
    "sweet smoked paprika": "Cumin",
    "Szechuan Peppercorns": "Cumin",
    "Turmeric Powder": "Cumin",
    "Vanilla Powder": "Cumin",
    "Whole black peppercorns": "Cumin",
    # weigh about the same as mozzarella
    "Cheese Curds": "Mozzarella",
    "Farmers Cheese": "Mozzarella",
    "Panquehue Cheese": "Mozzarella",
    "Queso Fresco": "Mozzarella",
    "Shredded Mexican Cheese": "Mozzarella",
    "Shredded Monterey Jack Cheese": "Mozzarella",
    # weigh about the same as dried oregano (dried herbs)
    "Dried Dill": "Oregano",
    "Dried Leaves Of Summer Savoury": "Oregano",
    "Dried Mint": "Oregano",
    "Dried Sorrel": "Oregano",
    "Marjoram": "Oregano",
    "Sage": "Oregano",
    "Summer Savoury": "Oregano",
    # weigh about the same as fresh parsley (fresh herbs)
    "Basil": "Parsley",
    "Chives": "Parsley",
    "Chopped Chive": "Parsley",
    "Dill": "Parsley",
    "Hot Mint": "Parsley",
    # weigh about the same as plain flour
    "Almond Flour": "Plain Flour",
    "Cacao": "Plain Flour",
    "Cassava Flour": "Plain Flour",
    "Chocolate Chips": "Plain Flour",
    "Cocoa": "Plain Flour",
    "Coconut": "Plain Flour",
    "Cornmeal": "Plain Flour",
    "Custard Powder": "Plain Flour",
    "Farine": "Plain Flour",
    "Fine Yellow Cornmeal": "Plain Flour",
    "Graham Cracker Crumbs": "Plain Flour",
    "Grits": "Plain Flour",
    "Potato Starch": "Plain Flour",
    "Rice Flour": "Plain Flour",
    "Rye Flour": "Plain Flour",
    "Semolina Flour": "Plain Flour",
    "Shredded Coconut": "Plain Flour",
    "Starch": "Plain Flour",
    "Tapioca": "Plain Flour",
    "Tempura Flour": "Plain Flour",
    "Wheat Flour": "Plain Flour",
    "White Chocolate": "Plain Flour",
    "White Chocolate Chips": "Plain Flour",
    "White Cornmeal": "Plain Flour",
    "White Masarepa": "Plain Flour",
    "Yellow Masarepa": "Plain Flour",
    # weigh about the same as raisins
    "Dried Cherries": "Raisins",
    "Dried cranberries": "Raisins",
    "Pitted Dates": "Raisins",
    # weigh about the same as red pepper
    "Sweet Red Peppers": "Red Pepper",
    # weigh about the same as rice
    "Arabic Rice": "Rice",
    "Brown Lentils": "Rice",
    "Brown Rice": "Rice",
    "Buckwheat": "Rice",
    "Dried White Navy Beans": "Rice",
    "Fermented Black Beans": "Rice",
    "Freekeh": "Rice",
    "French Lentils": "Rice",
    "Glutinous Rice": "Rice",
    "Grape Nut Cereal": "Rice",
    "Green Red Lentils": "Rice",
    "Jasmine Rice": "Rice",
    "Khus Khus": "Rice",
    "Lima Beans": "Rice",
    "Mixed Grain": "Rice",
    "Oats": "Rice",
    "Toor Dal": "Rice",
    "Yellow Split Peas": "Rice",
    # weigh about the same as salt
    "Celery Salt": "Salt",
    "Coarse Salt": "Salt",
    "Kosher Salt": "Salt",
    "Onion Salt": "Salt",
    "Sea Salt": "Salt",
    # weigh about the same as sugar
    "Golden Caster Sugar": "Sugar",
    "Ground Sugar": "Sugar",
    "Palm Sugar": "Sugar",
    # weigh about the same as unsalted butter
    "Ghee": "Unsalted Butter",
    "Peanut Butter": "Unsalted Butter",
    "Shortening": "Unsalted Butter",
    "Vegetable Shortening": "Unsalted Butter",
    # weigh about the same as yeast
    "Fast action yeast": "Yeast",
    "Instant Yeast": "Yeast",
    "Unflavoured Gelatin": "Yeast",
}

# no USDA weight to convert them with. recipes count most of these ("1 packet
# of pasta"), so those lines become not tracked, but "500g pasta" still converts
WITHOUT_WEIGHT = {
    "Fideo", "Pappardelle Pasta", "Penne Pasta", "Tagliatelle", "Toffee Popcorn",
}

STORE_IN_GRAMS = MAIN | WITH_OWN_USDA_FOOD | set(BORROWED_WEIGHTS) | WITHOUT_WEIGHT
