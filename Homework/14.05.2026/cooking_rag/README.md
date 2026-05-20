# Smart Cookbook - RAG-Based Culinary Assistant

## Why This Project

Me and my girlfriend always found ourselves opening ChatGPT and asking things
like "what can we make with chicken, rice and onions?" or looking for new
recipes based on whatever we had at home. So when prompted to make a RAG web app
I thought - why not make the topic specifically for help in the kitchen?

So I built a RAG-based cooking assistant where users can upload or save recipe
sources, manage their own recipe collections, and ask natural questions about
meals they can make with the ingredients they already have or about recipes they
have saved / new ones. The app retrieves relevant recipes and cooking
information from its knowledge base and uses an LLM to generate personalized
recipes, suggestions and answers.

---

## Getting Started

### Prerequisites

- [Docker](https://www.docker.com/products/docker-desktop) installed and running
- A [MongoDB Atlas](https://www.mongodb.com/atlas) account with a free cluster
  (or a local MongoDB instance)
- A [Google Gemini API key](https://aistudio.google.com/app/apikey) (free tier
  works)
- A [HuggingFace account](https://huggingface.co/settings/tokens) with a read
  token (free tier works)

### 1. Clone the repository

```bash
git clone <repository-url>
cd my_rag_app
```

### 2. Create a `.env` file

Create a file named `.env` in the project root with the following contents:

```
GEMINI_API_KEY=your_gemini_api_key
HF_TOKEN=your_huggingface_token
MONGO_URI=mongodb+srv://<user>:<password>@<cluster>.mongodb.net/
MONGO_DB=cooking_book_rag
SECRET_KEY=any_long_random_string
```

> **MongoDB note:** The database and all collections are created automatically
> on first run — no manual setup required. A local URI
> (`mongodb://localhost:27017/`) works just as well as Atlas.

### 3. Build the Docker image

```bash
docker build -t smart-cookbook .
```

This only needs to be done once (or after changing code/dependencies). It
installs all dependencies and pre-downloads the NLTK tokenizer data into the
image.

### 4. Run the app

```bash
docker run -p 5001:5001 --env-file .env smart-cookbook
```

Then open **http://localhost:5001** in your browser.

To stop the app press `Ctrl+C`.

---

## Architecture

```
┌─────────────┐     JWT cookie       ┌────────────────────────────┐
│   Browser   │ ◄──────────────────► │     Flask (app.py)         │
│  (HTML/CSS/ │                      │   Blueprints:              │
│    JS)      │                      │   /auth  /recipes          │
└─────────────┘                      │   /chat  /pantry           │
                                     └────────────┬───────────────┘
                                                  │
                   ┌──────────────────────────────┼──────────────────────────┐
                   │                              │                          │
          ┌────────▼────────┐          ┌──────────▼───────────┐    ┌─────────▼──────────┐
          │  MongoDB Atlas  │          │    RAG Engine        │    │   Gemini (LLM)     │
          │                 │          │   (rag/engine.py)    │    │  gemini-2.5-flash  │
          │  users          │          │                      │    │                    │
          │  recipes        │          │  1. Load .md/.txt    │    │  - Chat answers    │
          │  conversations  │          │  2. Embed chunks     │    │  - Recipe parsing  │
          │  (with message  │          │     (HuggingFace)    │    │    from uploads    │
          │   embeddings)   │          │  3. FAISS index      │    └────────────────────┘
          └─────────────────┘          │  4. Retrieve top-K   │
                                       │  5. Cosine history   │
                                       │     search           │
                                       └──────────────────────┘
```

### Key Components

| Layer               | Technology                                                                      | Role                                                                        |
| ------------------- | ------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| Web framework       | Flask 3 + Blueprints                                                            | Routing, auth, template rendering                                           |
| Database            | MongoDB Atlas                                                                   | Users, recipes, conversations + message embeddings                          |
| Auth                | PyJWT + bcrypt                                                                  | Stateless JWT tokens in httponly cookies                                    |
| Embeddings          | HuggingFace Inference API (`ibm-granite/granite-embedding-97m-multilingual-r2`) | Convert text to 768-dim vectors for semantic search                         |
| Vector index        | FAISS `IndexFlatL2` (in-memory)                                                 | Fast nearest-neighbour retrieval of relevant recipe chunks                  |
| Conversation memory | Cosine similarity on MongoDB-stored embeddings                                  | Surfaces semantically relevant past messages without re-sending all history |
| LLM                 | Google Gemini `gemini-2.5-flash`                                                | Generates answers, new recipes, extracts structure from uploaded files      |
| Frontend            | Jinja2 templates + vanilla JS + marked.js                                       | Chat UI, recipe CRUD, pantry management, dark mode                          |

### Request Flow (Chat)

1. User sends a question → `/chat/ask`
2. Question is embedded via HuggingFace API
3. Cosine similarity search finds the 3 most relevant past user messages from
   MongoDB
4. FAISS index retrieves the top-3 most relevant recipe chunks
5. All context (history snippets + recipe chunks + pantry) is assembled into a
   single prompt
6. Gemini generates a response; if it includes a new recipe, a structured
   `recipe-json` block is appended
7. The JS frontend detects the block, hides it, and shows an "Add to My
   Cookbook" button
8. Both the question and answer (with their embeddings) are stored in MongoDB
   for future recall

---

## Reflection

### What Went Well

- **RAG pipeline is genuinely useful** - the app correctly retrieves relevant
  cookbook sections and uses them as grounding, so answers are specific rather
  than generic.
- **Conversation memory via embeddings** - storing and cosine-searching
  per-message embeddings gives the assistant context across long conversations
  without blowing up the token budget.
- **Full-stack integration** - JWT auth, MongoDB CRUD, FAISS, HuggingFace
  embeddings, and Gemini are all wired together in a coherent way with clean
  blueprint separation.
- **UX touches** - dark mode, collapsible sidebar, sort/favourites on recipes,
  PDF upload with AI parsing, and the "Add AI recipe to Cookbook" button make it
  feel like a real product rather than a demo.

### What Could Be Improved

- **Token budget management** - Gemini's free tier 503 errors stem from the
  per-request prompt being large (system prompt + pantry + recipe chunks +
  history). Mitigation applied (history truncation + retry backoff), but a
  proper token-counting pre-flight check would be more robust.
- **FAISS persistence** - the index is rebuilt from scratch on every server
  start. For a larger recipe library this adds startup latency; persisting the
  index to disk (`.faiss` file) would fix this.
- **Embeddings API latency** - every question embeds synchronously via
  HuggingFace's free Inference API, which can add 1–2 seconds. Caching
  embeddings for repeated queries or moving to a locally-hosted model would
  help.
- **Single-user-per-conversation** - each user has one flat conversation
  document. Adding named conversation threads would improve usability.
- **Test coverage** - there are no automated tests. Unit tests for the RAG
  pipeline and integration tests for the auth/recipe routes would make the
  codebase safer to extend.

---

## Example Queries and Outputs

- Refer to the video provided via email.