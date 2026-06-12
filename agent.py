"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

Complete tools.py and test each tool in isolation before implementing this file.

Usage (once implemented):
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe

    result = run_agent(
        query="vintage graphic tee under $30, size M",
        wardrobe=get_example_wardrobe(),
    )
    print(result["fit_card"])
    print(result["error"])   # None on success
"""

import re

from tools import search_listings, suggest_outfit, create_fit_card


# ── query parsing ─────────────────────────────────────────────────────────────

# Common filler words to drop from the search description so they don't inflate
# keyword scores in search_listings (which matches by substring).
_STOPWORDS = {
    "i", "im", "i'm", "a", "an", "the", "for", "me", "looking", "look",
    "want", "wanting", "need", "find", "some", "something", "in", "of",
    "to", "with", "and", "please", "show", "get",
}

# Known size tokens we recognize as a standalone size in a query.
_SIZE_TOKENS = {"xxs", "xs", "s", "m", "l", "xl", "xxl", "xxxl"}


def _parse_query(query: str) -> dict:
    """
    Extract a search description, size, and max_price from a natural-language
    query using regex and string matching (no LLM call — keeps parsing fast,
    free, and deterministic).

    Returns a dict: {"description": str, "size": str | None, "max_price": float | None}
    """
    text = query.strip()
    lowered = text.lower()

    # max_price: "under $30", "below 30", "$30", "under 30 dollars".
    max_price = None
    price_match = re.search(
        r"(?:under|below|less than|max|up to|<)\s*\$?\s*(\d+(?:\.\d+)?)",
        lowered,
    )
    if not price_match:
        price_match = re.search(r"\$\s*(\d+(?:\.\d+)?)", lowered)
    if price_match:
        max_price = float(price_match.group(1))

    # size: explicit "size M" / "size 8", else a standalone size token.
    size = None
    size_match = re.search(r"\bsize\s+([a-z0-9/]+)", lowered)
    if size_match:
        size = size_match.group(1).upper()
    else:
        # Keep contractions intact (e.g. "i'm" stays one token) so the "m" in
        # "I'm" isn't mistaken for size M.
        for token in re.findall(r"[a-z]+(?:'[a-z]+)?", lowered):
            if token in _SIZE_TOKENS:
                size = token.upper()
                break

    # description: drop price/size phrases and filler words, keep the rest.
    description = lowered
    description = re.sub(
        r"(?:under|below|less than|max|up to|<)\s*\$?\s*\d+(?:\.\d+)?(?:\s*dollars)?",
        " ",
        description,
    )
    description = re.sub(r"\$\s*\d+(?:\.\d+)?", " ", description)
    description = re.sub(r"\bsize\s+[a-z0-9/]+", " ", description)
    # Strip punctuation, then remove stopwords and standalone size tokens.
    words = re.findall(r"[a-z0-9']+", description)
    keep = [
        w for w in words
        if w not in _STOPWORDS and w not in _SIZE_TOKENS and len(w) > 1
    ]
    description = " ".join(keep).strip()

    # Fall back to the raw query if parsing stripped everything.
    if not description:
        description = text

    return {"description": description, "size": size, "max_price": max_price}


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """
    Initialize and return a fresh session dict for one user interaction.

    The session dict is the single source of truth for everything that happens
    during a run — it stores the original query, parsed parameters, tool results,
    and any error that caused early termination.

    You may add fields to this dict as needed for your implementation.
    """
    return {
        "query": query,              # original user query
        "parsed": {},                # extracted description / size / max_price
        "search_results": [],        # list of matching listing dicts
        "selected_item": None,       # top result, passed into suggest_outfit
        "wardrobe": wardrobe,        # user's wardrobe dict
        "outfit_suggestion": None,   # string returned by suggest_outfit
        "fit_card": None,            # string returned by create_fit_card
        "error": None,               # set if the interaction ended early
    }


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.

    Args:
        query:    Natural language user request
                  (e.g., "vintage graphic tee under $30, size M")
        wardrobe: User's wardrobe dict — use get_example_wardrobe() or
                  get_empty_wardrobe() from utils/data_loader.py

    Returns:
        The session dict after the interaction completes. Check session["error"]
        first — if it is not None, the interaction ended early and the other
        output fields (outfit_suggestion, fit_card) will be None.

    TODO — implement this function using the planning loop you designed in planning.md:

        Step 1: Initialize the session with _new_session().

        Step 2: Parse the user's query to extract a description, size, and
                max_price. You can use regex, string splitting, or ask the LLM
                to parse it — document your choice in planning.md.
                Store the result in session["parsed"].

        Step 3: Call search_listings() with the parsed parameters.
                Store results in session["search_results"].
                If no results: set session["error"] to a helpful message and
                return the session early. Do NOT proceed to suggest_outfit
                with empty input.

        Step 4: Select the item to use (e.g., the top result).
                Store it in session["selected_item"].

        Step 5: Call suggest_outfit() with the selected item and wardrobe.
                Store the result in session["outfit_suggestion"].

        Step 6: Call create_fit_card() with the outfit suggestion and selected item.
                Store the result in session["fit_card"].

        Step 7: Return the session.

    Before writing code, complete the Planning Loop and State Management sections
    of planning.md — your implementation should match what you described there.
    """
    # Step 1: Initialize the session — the single source of truth for this run.
    session = _new_session(query, wardrobe)

    # Step 2: Parse the query into search parameters and store them in state.
    parsed = _parse_query(query)
    session["parsed"] = parsed

    # Step 3: Search for matching listings. Branch on the result — if nothing
    # matched, set an error and STOP. Do not call the LLM tools with empty input.
    session["search_results"] = search_listings(
        description=parsed["description"],
        size=parsed["size"],
        max_price=parsed["max_price"],
    )
    if not session["search_results"]:
        session["error"] = (
            "No listings matched your search. Try raising the price, dropping "
            "the size filter, or using different keywords."
        )
        return session

    # Step 4: Select the top (best-match) result to style.
    session["selected_item"] = session["search_results"][0]

    # Step 5: Suggest an outfit using the selected item and the user's wardrobe.
    #         (suggest_outfit handles an empty wardrobe on its own.)
    session["outfit_suggestion"] = suggest_outfit(
        session["selected_item"], session["wardrobe"]
    )

    # Step 6: Turn the outfit into a shareable fit-card caption.
    session["fit_card"] = create_fit_card(
        session["outfit_suggestion"], session["selected_item"]
    )

    # Step 7: Return the completed session.
    return session


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")
