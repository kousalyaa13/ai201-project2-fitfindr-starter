# FitFindr 🛍️

FitFindr is an agent that helps you shop secondhand. You tell it what you want. It finds a matching listing, styles it with clothes you already own, and writes a short caption you could post online.

## Setup

```bash
pip install -r requirements.txt
```

Set your Groq API key in a `.env` file (get a free key at [console.groq.com](https://console.groq.com)):
```
GROQ_API_KEY=your_key_here
```

## How to Run

Run the web app:
```bash
python app.py
```
Then open the localhost URL it prints (usually http://localhost:7860).

Run the agent from the command line:
```bash
python agent.py
```

Run the tests:
```bash
python -m pytest tests/
```

## The Data

`data/listings.json` has 40 mock secondhand listings. Each listing has these fields: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, and `platform`.

`data/wardrobe_schema.json` holds the wardrobe format, an example wardrobe with 10 items, and an empty wardrobe for new users. Load these with the helpers in `utils/data_loader.py`.

---

## Tool Inventory

FitFindr uses three tools. They live in `tools.py`.

### 1. `search_listings`
- **Purpose:** Find secondhand listings that match what the user asked for.
- **Inputs:**
  - `description` (str): keywords describing the item, like "vintage graphic tee".
  - `size` (str or None): a size to filter by, or None to skip size filtering.
  - `max_price` (float or None): the highest price allowed, or None to skip price filtering.
- **Output:** A list of listing dicts, sorted with the best match first. The list is empty if nothing matches.

### 2. `suggest_outfit`
- **Purpose:** Style the chosen item with clothes the user already owns.
- **Inputs:**
  - `new_item` (dict): the listing the user is thinking about buying.
  - `wardrobe` (dict): the user's wardrobe, which has an `items` list. It may be empty.
- **Output:** A string with 1–2 outfit ideas. This tool calls the LLM (Groq `llama-3.3-70b-versatile`).

### 3. `create_fit_card`
- **Purpose:** Write a short, casual caption for the outfit, like an OOTD post.
- **Inputs:**
  - `outfit` (str): the outfit text from `suggest_outfit`.
  - `new_item` (dict): the listing, so the caption can name the item, its price, and the platform.
- **Output:** A 2–4 sentence caption string. This tool also calls the LLM.

---

## Planning Loop

The planning loop lives in `run_agent()` in `agent.py`. It runs the three tools in a fixed order. Each step depends on the step before it.

1. It makes a fresh `session` dict to hold everything.
2. It parses the user's query into a `description`, a `size`, and a `max_price`. I use simple regex and string matching here, not the LLM, so parsing is fast and free.
3. It calls `search_listings` with those parameters.
4. **It checks the search result.** If the list is empty, it writes an error message and stops. It does not call the other two tools.
5. If there are results, it picks the top one as the item to style.
6. It calls `suggest_outfit` with that item and the wardrobe.
7. It calls `create_fit_card` with the outfit and the item.
8. It returns the session. The agent is done when the fit card is made, or when a step sets an error.

---

## State Management

All the data for one run lives in a single `session` dict. It is the one source of truth.

Each step reads what it needs from the session and writes its result back. The fields are:
- `query`: the original user text
- `parsed`: the extracted description, size, and max_price
- `search_results`: the list of matching listings
- `selected_item`: the top listing, which gets passed to `suggest_outfit`
- `wardrobe`: the user's wardrobe
- `outfit_suggestion`: the string from `suggest_outfit`
- `fit_card`: the string from `create_fit_card`
- `error`: set if the run stopped early, otherwise None

Because every step reads from and writes to this one dict, the output of one tool becomes the input of the next. Nothing is hardcoded between steps, and the user is never asked again mid-run. I tested this by checking that the exact same item dict passed into `suggest_outfit` is the same object stored in `session["selected_item"]`, and that the same outfit string went into `create_fit_card`.

---

## Error Handling

Each tool handles one main failure mode. None of them crash.

| Tool | Failure mode | What happens |
|------|-------------|--------------|
| `search_listings` | Nothing matches the query | Returns an empty list. The agent sets `session["error"]` and stops. It does NOT call the other tools. |
| `suggest_outfit` | The wardrobe is empty | Does not crash. Returns general styling advice for the item instead. |
| `create_fit_card` | The outfit string is empty or blank | Does not crash. Returns a plain error message string. |

**Concrete example from my testing:**
I ran the query `"designer ballgown size XXS under $5"`. No listing matched, so `search_listings` returned `[]`. The agent set `session["error"]` to *"No listings matched your search. Try raising the price, dropping the size filter, or using different keywords."*, and `session["fit_card"]` stayed `None`. To be sure the agent really stopped, I replaced `suggest_outfit` with a function that raises an error if called. The run finished cleanly with no error raised, which proved the LLM tools were never reached on the no-results path.

---

## Spec Reflection

My plan and my code matched closely. The fixed three-step order from my planning.md (search → suggest → caption) was easy to follow, and the single `session` dict made state simple to track.

Two things came up while building:
- My planning.md said `create_fit_card` only took the outfit. The real stub also needed `new_item` so the caption could mention the price and platform. I updated my plan to match.
- My query parser had a bug I did not plan for. The word "I'm" was being split on the apostrophe, and the leftover "m" was read as size "M". This wrongly filtered the listings. I fixed the parser so it keeps contractions in one piece.

If I did it again, I would write the parsing rules into planning.md up front, since that is where most of my surprises were.

---

## AI Usage

I used Claude to help write the code. I gave it my planning.md spec and reviewed everything before keeping it.

**Instance 1 — Implementing the three tools.**
I gave Claude the Tool 1, 2, and 3 sections from my planning.md (the inputs, outputs, and failure modes) plus the function stubs and docstrings in `tools.py`. It produced working bodies for all three tools, and it added a shared `_call_llm` helper and picked the `llama-3.3-70b-versatile` model, since I had not named one. I reviewed the output and tested it. For `create_fit_card`, I ran it three times on the same input to check the captions were different. They were, so I kept the temperature as is instead of raising it.

**Instance 2 — Implementing the planning loop.**
I gave Claude the Planning Loop and State Management sections of my planning.md, my architecture diagram, and the `run_agent` stub in `agent.py`. It produced the loop and a `_parse_query` helper to read the query. I checked it against my spec: it branched on the search result, it stored values in the session dict, and it did not call all three tools unconditionally. But when I ran it, the parser read size "M" from the word "I'm". I overrode that part and fixed the tokenizer myself so contractions stay together. After the fix the parsing was correct.
