# Chennai Smart Travel AI

Multi-modal journey planning for Chennai (metro, local train, MTC bus, share auto, pink auto, bike taxi, cab) with
**machine-learning traffic prediction, deep learning, SQL analytics, RAG, tool-using AI agents, a REST API, an MCP server and
LoRA/QLoRA fine-tuning**.

> Data honesty: routes, fares and times come from the CSV files in `data/` (a prototype dataset). The traffic history used to
> train the delay models is **simulated** from documented assumptions (`ml/traffic_data.py`): rush hours, north-east monsoon,
> mode sensitivity. Nothing here is live fares, live timings or live traffic. Replace `data/processed/traffic_history.csv`
> with real observations and run `python setup_project.py --retrain` to get a real model.

## Run it (VS Code terminal, project folder open)

```
python -m venv .venv                  # skip if you already have one (copy your old .venv here, or recreate)
.venv\Scripts\activate                # Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env                # then paste your GROQ_API_KEY (optional, the app also works without it)
python setup_project.py               # database + traffic data + models (~20 s; the app also does this by itself on first run)
streamlit run frontend/app.py
```

Extras: `uvicorn backend.api.main:app --reload` (API docs at /docs) · `python mcp_server.py` (needs `pip install mcp`) ·
`python tests/test_smart_travel_ai.py` (23 tests) · `python tests/smoke_pages.py --click` (runs every page without a browser).

## What was already there, and what was added

| Area | Before | Now |
|---|---|---|
| Route engine | NetworkX multi-modal graph, CMRL fares, fastest/cheapest/shortest | same, plus optional `traffic=` argument for **traffic-aware routing** (`transport_engine.py`) |
| Machine learning | empty `ml/` folder | `ml/`: simulator, feature engineering, Ridge / Random Forest / Gradient Boosting / **neural network (MLP)**, metrics + feature importance, predictor with safe fallback |
| Deep learning | none | scikit-learn MLP (runs everywhere) and a PyTorch version (`ml/training/train_torch_mlp.py`) |
| SQL | one table | `db/schema.sql`: 6 tables, constraints, indexes, 2 views; `analytics_service.py`: GROUP BY, CASE, CTEs, window functions (RANK/COUNT OVER) |
| Backend | empty `backend/` | `backend/services/` (route, traffic, analytics, assistant, bootstrap) and a FastAPI app `backend/api/main.py` |
| Generative AI | Groq explanation + regex agent | **RAG** knowledge base, **tool-calling agent** (Groq, offline fallback), **4-agent planner**, **MCP server** |
| Fine-tuning | none | `genai/finetune/`: chat dataset built from the verified engine + LoRA/QLoRA script |
| UI | Route Planner, AI assistant, placeholders | all placeholders are real pages: Traffic Prediction, Fare Calculator, Analytics, Live Map, Admin; assistant has 3 new tabs |

### How it fits your 51-day syllabus
| Topic | Where |
|---|---|
| Python, pandas, SQL | `db/`, `backend/services/`, `analytics_service.py` |
| ML (regression, evaluation, feature importance) | `ml/training/train_delay_model.py` |
| Deep learning | MLP in the same script; PyTorch net in `train_torch_mlp.py` |
| NLP | request parsing (`smart_agent.parse_request`), TF-IDF retrieval |
| LLMs, prompt engineering | `genai/llm_client.py`, system prompts in the agents, grounded explanations |
| RAG | `genai/rag/` (documents built from your data + anything you drop in `data/knowledge/`) |
| LoRA / QLoRA | `genai/finetune/` |
| Agents, tool calling | `genai/agents/tools.py`, `smart_agent.py` |
| CrewAI-style multi-agent | `multi_agent.py` (plain Python: Planner → Route Analyst → Critic → Explainer) |
| MCP | `mcp_server.py` |
| A2A | the agents pass structured `AgentMessage` objects (inspired by A2A; it is not the formal A2A protocol) |
| LangChain | not used on purpose: the tool loop is ~40 lines in plain Python, so you can explain every step. Easy to port. |
| Computer vision | not part of this project (no image data). A natural extension: read bus route boards or station signs with OCR. |

## How the ML works
1. `ml/traffic_data.py` simulates 30,000 journeys on your real routes. `delay_ratio = actual_time / scheduled_time`.
2. `ml/features.py` encodes hour and month as sin/cos, flags weekday peak hours, one-hot encodes the mode.
3. Four models are trained on 80 % of the data and compared on 20 % (MAE in ratio and in minutes, R²) against a naive average.
4. The best model is saved to `ml/models/delay_model.joblib`; metrics go to `metrics.json` (shown on the Traffic and Admin pages).
5. `ml/predictor.py` multiplies every edge time of the route graph by the predicted ratio, so Dijkstra finds the best route for
   *that* hour, weekday, month and rain level. If the model file is missing it falls back to the simulation formula.

Example result on this machine: Naive MAE ≈ 0.15, Gradient Boosting MAE ≈ 0.073 (≈ 1.7 min), R² ≈ 0.75. The remaining error is
the random noise built into the simulation, so do not read the score as real-world accuracy.

## Folder map
```
frontend/        Streamlit app (app.py + pages 1-7, common.py)
backend/         services/ (business logic)  api/main.py (FastAPI)
db/              schema.sql, database.py
ml/              traffic_data.py, features.py, predictor.py, training/
genai/           llm_client.py, rag/, agents/ (tools, smart_agent, multi_agent), finetune/
data/            raw/ processed/ knowledge/   (put official CMRL/MTC notes in knowledge/)
transport_engine.py  metro_engine.py  map_engine.py   (your original engines)
mcp_server.py  setup_project.py  settings.py
tests/           test_smart_travel_ai.py, smoke_pages.py, plus your original test scripts
```

## Changes made to your original files
- `transport_engine.py`: optional `traffic=` argument on `find_best_route`, `compare_routes`, `find_route_within_budget` (defaults keep old behaviour).
- `metro_engine.py`: the two metro CSVs are read once and cached (route search is much faster).
- `data/processed/location_coordinates.csv`: added **T Nagar** (approximate 13.0418, 80.2341); it was used by a bus route but had no coordinates, so map drawing would fail for it.
- `frontend/app.py`: placeholder pages replaced by a real dashboard; the other pages are now Streamlit multipage files.
- `frontend/pages/2_AI_Travel_Assistant.py`: Groq is optional now (the page no longer crashes without a key); three tabs added.
- `chennai_travel.db`: rebuilt by `setup_project.py`. The old `transport_routes` table contained duplicate rows (42 → 33 unique), and now has a UNIQUE key.
- Known, not caused by this work: `tests/test_metro_engine_fares.py` expects discounted metro fares from the database; metro fares now come from `metro_engine`, so that one assertion fails (same on your original zip).

## Tested vs not tested
Tested here (sandbox with pandas, NumPy, scikit-learn, NetworkX, SQLite): data simulation, model training, predictor and fallback,
traffic-aware routing, all SQL, retrieval, both agents (LLM loop with a scripted fake LLM, plus offline mode), fine-tuning dataset,
and every Streamlit page executed against a fake `streamlit` module (`tests/smoke_pages.py`).

**Not run here, so check them on your machine:** the real Groq calls, the FastAPI server, `mcp_server.py`, the PyTorch script, the
LoRA/QLoRA script (needs a GPU), maps (need internet for road routing), and the pages in a real browser.

## Security
Your `.env` holds live API keys. It is not included in this zip. Never upload it or commit it; if it was shared anywhere, rotate the Groq and MapTiler keys.
