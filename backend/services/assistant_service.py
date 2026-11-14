"""One entry point for every assistant mode: 'agent' (tool calling), 'multi' (4-agent pipeline), 'rag' (knowledge Q&A)."""
from __future__ import annotations

from db import database as dbm
from genai.agents import formatting as fmt
from genai.agents.multi_agent import MultiAgentTripPlanner
from genai.agents.smart_agent import SmartTravelAgent
from genai.llm_client import get_llm
from genai.rag.retriever import get_retriever

MODES = {"agent": "Smart agent (tools)", "multi": "Multi-agent planner", "rag": "Knowledge base Q&A"}


def llm_status() -> str:
    return "Groq LLM connected" if get_llm() is not None else "Offline mode (no GROQ_API_KEY): rule-based agent"


def answer_with_rag(question: str, llm=None) -> dict:
    passages = get_retriever().search(question, k=4)
    if llm is not None and passages:
        try:
            ctx = "\n\n".join(f"[{p.title}] {p.text}" for p in passages)
            r = llm.chat([{"role": "system", "content": "Answer ONLY from the context. If it is not there, say you do not know. "
                                                         "Keep it short and mention that figures are prototype estimates."},
                          {"role": "user", "content": f"Context:\n{ctx}\n\nQuestion: {question}"}])
            if r.content:
                return {"answer": r.content, "used_llm": True, "sources": [p.to_dict() for p in passages]}
        except Exception as exc:
            print(f"[assistant] RAG LLM failed: {exc}")
    return {"answer": fmt.format_passages([p.to_dict() for p in passages]), "used_llm": False,
            "sources": [p.to_dict() for p in passages]}


def ask(question: str, mode: str = "agent", history: list[dict] | None = None, log: bool = True) -> dict:
    llm = get_llm()
    if mode == "multi":
        res = MultiAgentTripPlanner(llm).run(question)
        out = {"answer": res.answer, "used_llm": res.used_llm, "transcript": res.transcript(), "tools": []}
    elif mode == "rag":
        out = answer_with_rag(question, llm); out["tools"] = ["search_knowledge"]
    else:
        res = SmartTravelAgent(llm).run(question, history)
        out = {"answer": res.answer, "used_llm": res.used_llm, "tools": [s["tool"] for s in res.steps],
               "steps": res.steps, "error": res.error}
    out["mode"] = mode
    if log:
        try:
            dbm.log_chat(mode, question, out["answer"], out.get("tools"))
        except Exception as exc:
            print(f"[assistant] could not log chat: {exc}")
    return out
