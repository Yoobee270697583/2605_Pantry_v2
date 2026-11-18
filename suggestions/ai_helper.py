import json
import os

import anthropic

# everything here talks to the Claude API (Anthropic), for the AI swap tips on
# Suggested Recipes. needs ANTHROPIC_API_KEY in .env - without it get_swaps just
# returns None and the page says the tips aren't available

# Claude Haiku 5.5 - the fast, cheap model, plenty for a few swap ideas
MODEL = "claude-haiku-5-5"

# give up after 25 seconds. on AWS, CloudFront gives up on the whole page after 30,
# so this has to be less than that
TIMEOUT = 25

# the swaps are only a few short sentences, so this is plenty
MAX_TOKENS = 1024

# only send the start of really long methods - it's enough to see how each ingredient is used
MAX_METHOD_LENGTH = 1500

# what we want back from Claude. structured outputs make the reply JSON that matches
# this exactly, so we never have to pick the swaps out of normal text
SWAP_SCHEMA = {
    "type": "object",
    "properties": {
        "swaps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    # the missing ingredient this swap is for
                    "missing": {"type": "string"},
                    # what to use instead
                    "swap": {"type": "string"},
                    # one short sentence on how to use it
                    "tip": {"type": "string"},
                },
                "required": ["missing", "swap", "tip"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["swaps"],
    "additionalProperties": False,
}

# the instructions Claude gets with every request
SYSTEM_PROMPT = """You help home cooks make a recipe when they're missing an ingredient or two.
You'll get the recipe, the ingredients they're missing, and what's in their pantry.

For each missing ingredient, suggest 1 or 2 swaps that would work in this recipe:
- Use what's in their pantry first. When you suggest a pantry item, write its name exactly as it appears in the pantry list, because the app matches your answer against their pantry.
- Only suggest something that isn't in their pantry if nothing in it would work, and keep it to things a normal supermarket sells.
- Don't suggest the missing ingredient itself.
- Each tip is one short sentence on how to use the swap, like how much to use or what it changes. If the dish works fine without the ingredient, the tip can say it can be left out."""


def build_prompt(recipe, missing, pantry):
    """The message we send Claude - the recipe, what's missing from it, and what's in the pantry."""
    lines = []
    for line in recipe.ingredients.select_related("ingredient"):
        # TheMealDB lines have the original measure, custom recipes only have the amount
        if line.measure_text:
            lines.append(f"- {line.ingredient.name}: {line.measure_text}")
        elif line.quantity is not None:
            # :g drops the .0, so 500.0 shows as 500
            lines.append(f"- {line.ingredient.name}: {line.quantity:g} {line.ingredient.get_unit_display().lower()}")
        else:
            lines.append(f"- {line.ingredient.name}")

    missing_names = ", ".join(ingredient.name for ingredient in missing)
    pantry_names = ", ".join(ingredient.name for ingredient in pantry)

    prompt = f"Recipe: {recipe.name}\n\n"
    prompt += "Ingredients:\n" + "\n".join(lines) + "\n\n"
    prompt += f"Method:\n{recipe.instructions[:MAX_METHOD_LENGTH]}\n\n"
    prompt += f"Missing: {missing_names}\n\n"
    prompt += f"Pantry: {pantry_names}"
    return prompt


def get_swaps(recipe, missing, pantry):
    """Asks Claude what the household could use instead of the ingredients a recipe is missing.

    recipe  - the Recipe
    missing - the Ingredients it needs that aren't in the pantry
    pantry  - the Ingredients that are in the pantry

    Returns a list of dicts like {"missing": "Semolina", "swap": "Plain Flour", "tip": "..."},
    or None if Claude couldn't be reached or didn't give a proper answer, so the page
    can say the tips aren't available instead of crashing.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    # no key, so don't even try
    if not api_key:
        print("no ANTHROPIC_API_KEY in .env, so no AI swap tips")
        return None

    try:
        # max_retries=0 so a failed request isn't tried again, which could go past the 25 seconds
        client = anthropic.Anthropic(api_key=api_key, timeout=TIMEOUT, max_retries=0)
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            # swaps don't need Claude to think it through first, and the answer comes back quicker
            thinking={"type": "disabled"},
            output_config={
                # low effort is plenty for a few swap ideas
                "effort": "low",
                # makes the reply JSON that matches SWAP_SCHEMA
                "format": {"type": "json_schema", "schema": SWAP_SCHEMA},
            },
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": build_prompt(recipe, missing, pantry)}],
        )

    # timeout has to come before connection error, because a timeout is a kind of connection error
    except anthropic.APITimeoutError:
        print("Claude took too long to answer")
        return None

    except anthropic.APIConnectionError:
        print("couldnt connect to Claude")
        return None

    except anthropic.APIStatusError as error:
        # e.g. 401 bad key, 429 too many requests, 529 overloaded
        print(f"Claude API error {error.status_code}: {error.message}")
        return None

    except Exception as error:
        print(f"couldnt get swaps from Claude: {error}")
        return None

    # Claude can refuse, and Haiku has no backup model to try instead, so just give up
    if response.stop_reason == "refusal":
        print("Claude wouldn't suggest swaps for this recipe")
        return None

    # the answer got cut off, so the JSON won't be complete
    if response.stop_reason == "max_tokens":
        print("Claude's answer got cut off")
        return None

    # the JSON comes back as the text block
    text = ""
    for block in response.content:
        if block.type == "text":
            text = block.text
            break

    try:
        swaps = json.loads(text)["swaps"]
    except (ValueError, KeyError) as error:
        print(f"couldnt read Claude's answer: {error}")
        return None

    # tidy up the spaces, and skip any that are empty or just the missing ingredient again
    tidy_swaps = []
    for swap in swaps:
        missing_name = swap["missing"].strip()
        swap_name = swap["swap"].strip()
        if not swap_name or swap_name.lower() == missing_name.lower():
            continue
        tidy_swaps.append({"missing": missing_name, "swap": swap_name, "tip": swap["tip"].strip()})

    return tidy_swaps
