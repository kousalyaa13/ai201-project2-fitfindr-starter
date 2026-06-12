# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
This tool searches the mock listings dataset for second-hand items that match what the user asked for. It triggers first, as soon as a user sends a query. It filters out items that cost too much or are the wrong size, ranks the rest by how well they match the keywords, and returns the best matches first.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `description` (str): keywords describing what the user wants (e.g., "vintage graphic tee").
- `size` (str | None): the size to filter by (case-insensitive), or None to skip size filtering.
- `max_price` (float | None): the highest price allowed (inclusive), or None to skip price filtering.

**What it returns:**
<!-- Describe the return value — what fields does a result contain? -->
A list of matching listing dicts, sorted best-match first. Each dict has these fields: `id`, `title`, `description`, `category`, `style_tags` (list), `size`, `condition`, `price` (float), `colors` (list), `brand`, and `platform`.

**What happens if it fails or returns nothing:**
<!-- What should the agent do if no listings match? -->
It returns an empty list instead of crashing. The agent then stops, sets `session["error"]` to a friendly message, and returns early. It does NOT call the next tool with empty input.

---

### Tool 2: suggest_outfit

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->
This tool takes the item the user is considering and styles it with the clothes they already own. It triggers after search_listings returns at least one item. It asks the LLM to combine the new item with named pieces from the user's wardrobe and describe 1–2 complete outfits.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `new_item` (dict): the listing dict for the item the user wants to style (the top search result).
- `wardrobe` (dict): the user's wardrobe, with an `items` key holding a list of their clothing pieces. May be empty.

**What it returns:**
<!-- Describe the return value -->
A non-empty string describing 1–2 outfit ideas that pair the new item with specific pieces from the wardrobe.

**What happens if it fails or returns nothing:**
<!-- What should the agent do if the wardrobe is empty or no outfit can be suggested? -->
If the wardrobe has no items, the tool does NOT crash. Instead it returns general styling advice for the new item (what kinds of pieces and what vibe pair well with it). The agent saves whatever string comes back and keeps going.

---

### Tool 3: create_fit_card

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->
This tool writes a short, shareable caption for the outfit. It triggers after suggest_outfit produces an outfit string. It asks the LLM for a casual 2–4 sentence post (like a real OOTD caption) that names the item, its price, and the platform, and captures the outfit's vibe.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `outfit` (str): the outfit suggestion string from suggest_outfit().
- `new_item` (dict): the listing dict for the thrifted item, so the caption can mention its name, price, and platform.

**What it returns:**
<!-- Describe the return value -->
A 2–4 sentence string usable as an Instagram/TikTok caption.

**What happens if it fails or returns nothing:**
<!-- What should the agent do if the outfit data is incomplete? -->
If the outfit string is empty or blank, the tool does NOT crash. It returns a plain error message string instead of a caption, so the agent always has something safe to show.

---

### Additional Tools (if any)

<!-- Copy the block above for any tools beyond the required three -->

---

## Planning Loop

**How does your agent decide which tool to call next?**
<!-- Describe the logic your planning loop uses. What does it look at? What conditions change its behavior? How does it know when it's done? -->
The agent runs the three tools in a fixed order, and each step depends on the one before it. First it parses the query and calls search_listings. If the search returns nothing, it stops and reports an error — it does not move on. If the search found items, it picks the top one and calls suggest_outfit. Once it has an outfit string, it calls create_fit_card. The agent is done when the fit card is created, or when any step sets an error.

**Query parsing choice:** the agent parses the query with regex and string matching, not an LLM call. It pulls out `max_price` (e.g. "under $30"), `size` (e.g. "size M" or a standalone size token like "XS"), and uses the remaining words — minus filler words like "looking for a" — as the search `description`. This keeps parsing fast, free, and deterministic, and avoids a second model call before the search even runs.

---

## State Management

**How does information from one tool get passed to the next?**
<!-- Describe how your agent stores and accesses state within a session. What data is tracked? How is it passed between tool calls? -->
All information lives in one `session` dict created at the start of the run. Each step reads what it needs from the session and writes its result back: `parsed` (the extracted description/size/max_price), `search_results`, `selected_item`, `outfit_suggestion`, `fit_card`, and `error`. Because every tool reads from and writes to this one dict, the output of one tool becomes the input of the next. The agent checks `session["error"]` to decide whether to stop early.

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query | Tool returns an empty list. The agent sets `session["error"]` to a friendly message and stops — it does not call the next tool. |
| suggest_outfit | Wardrobe is empty | Tool returns general styling advice for the item instead of crashing. The agent saves the string and continues. |
| create_fit_card | Outfit input is missing or incomplete | Tool returns a plain error message string instead of a caption. The agent still has safe text to show the user. |

---

## Architecture

<!-- Draw a diagram of your agent showing how the components connect:
     User input → Planning Loop → Tools (search_listings, suggest_outfit, create_fit_card)
                                                                          ↕
                                                                   State / Session
     Show what triggers each tool, how state flows between them, and where error paths branch off.
     ASCII art, a Mermaid diagram (https://mermaid.js.org/syntax/flowchart.html), or an embedded
     sketch are all fine. You'll share this diagram with an AI tool when asking it to implement
     the planning loop and each individual tool. -->

```
        User query
            │
            ▼
   ┌─────────────────┐
   │  Planning Loop  │◄──────────────┐
   └─────────────────┘               │
            │                        │
            │ parse query            │ reads/writes
            ▼                        ▼
   ┌─────────────────┐        ┌──────────────┐
   │ search_listings │        │   session    │
   └─────────────────┘        │   (state)    │
            │                 │              │
   empty? ──┴── yes ─► set error, STOP ──►   │  query, parsed,
            │                 │  search_results, selected_item,
            no                │  wardrobe, outfit_suggestion,
            ▼                 │  fit_card, error
   ┌─────────────────┐        │              │
   │  suggest_outfit │◄───────┤              │
   └─────────────────┘  (empty wardrobe →    │
            │            general advice)     │
            ▼                                │
   ┌─────────────────┐                       │
   │ create_fit_card │◄──────────────────────┘
   └─────────────────┘  (blank outfit → error string)
            │
            ▼
   Final output to user
```

---

## AI Tool Plan

<!-- For each part of the implementation below, describe:
     - Which AI tool you plan to use (Claude, Copilot, ChatGPT, etc.)
     - What you'll give it as input (which sections of this planning.md, your agent diagram)
     - What you expect it to produce
     - How you'll verify the output matches your spec before moving on

     "I'll use AI to help me code" is not a plan.
     "I'll give Claude my Tool 1 spec (inputs, return value, failure mode) and ask it to implement
     search_listings() using load_listings() from the data loader — then test it against 3 queries
     before trusting it" is a plan. -->

**Milestone 3 — Individual tool implementations:**
I'll use Claude. For each tool I'll give it that tool's section from this planning.md (the inputs, return value, and failure mode) plus the matching function stub and docstring from tools.py, and the field lists from utils/data_loader.py. I expect it to produce a working function body. I'll verify by testing each tool on its own before trusting it: search_listings against a query that matches and one that matches nothing, suggest_outfit with a full wardrobe and an empty wardrobe, and create_fit_card with a real outfit string and a blank one.

**Milestone 4 — Planning loop and state management:**
I'll use Claude again. I'll give it the Planning Loop, State Management, and Architecture sections above plus the run_agent stub and _new_session dict from agent.py. I expect it to produce the run_agent loop that calls the three tools in order and passes data through the session dict. I'll verify by running the CLI test in agent.py and checking both the happy path (a fit card is produced) and the no-results path (an error message is set and the later tools are skipped).

---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**What FitFindr needs to do:** FitFindr finds a second-hand clothing item that matches what the user asked for. Then it styles that item with the clothes the user already owns and writes a short, fun caption for the look. It does all three steps in order, passing the result of each step into the next.

**Step 1 — search_listings (Tool 1):**
The agent first reads the query and pulls out the parts it can search on: `description` = "vintage graphic tee", `max_price` = 30, and `size` if one was given (here none, so size is skipped). **Trigger:** this tool always runs first, as soon as the user sends a query. The agent calls `search_listings("vintage graphic tee", size=None, max_price=30)`, which loads all listings, drops anything over $30 or the wrong size, scores the rest by how many keywords match, and returns the matching items best-match first.
**If it fails / returns nothing:** the tool returns an empty list (it does not crash). The agent then stops, sets `session["error"]` to a helpful message like "No listings matched — try a higher price or different keywords," and returns early. It does NOT call the next tool with empty input.

**Step 2 — suggest_outfit (Tool 2):**
From Step 1's results, the agent picks the top item (say, a $24 vintage band tee) and saves it as `session["selected_item"]`. **Trigger:** this tool runs only after Step 1 returns at least one item. The agent calls `suggest_outfit(selected_item, wardrobe)`, passing in the chosen tee plus the user's wardrobe (which includes their baggy jeans and chunky sneakers). The tool asks the LLM to combine the new tee with named pieces the user already owns and returns 1–2 outfit ideas as a string.
**If it fails / wardrobe is empty:** if the wardrobe has no items, the tool does NOT crash — instead it returns general styling advice for the tee (what kinds of pieces and vibe pair well). The agent saves whatever string comes back as `session["outfit_suggestion"]`.

**Step 3 — create_fit_card (Tool 3):**
**Trigger:** this tool runs only after Step 2 produces an outfit string. The agent calls `create_fit_card(outfit_suggestion, selected_item)`, which asks the LLM to write a short, casual 2–4 sentence caption that names the item, its price, and the platform, and captures the outfit's vibe. The result is saved as `session["fit_card"]`.
**If it fails / outfit is missing:** if the outfit string is empty or blank, the tool does NOT crash — it returns a plain error message string instead of a caption, so the agent still has something safe to show.

**Final output to user:**
The user sees the chosen item (title, price, platform), the suggested outfit built from their own baggy jeans and chunky sneakers, and the shareable fit-card caption. If Step 1 found nothing, the user instead sees the friendly error message and a suggestion to adjust their search.
