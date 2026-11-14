"""TF-IDF retriever (works offline, no embedding API needed).

To upgrade to semantic search later, replace `KnowledgeRetriever` with a sentence-transformer + FAISS/Chroma version
that exposes the same `search()` method; nothing else in the project has to change.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from genai.rag.knowledge_base import Document, build_documents


@dataclass
class Passage:
    source: str
    title: str
    text: str
    score: float

    def to_dict(self) -> dict:
        return {"source": self.source, "title": self.title, "text": self.text, "score": round(self.score, 3)}


def chunk(doc: Document, max_words: int = 90) -> list[tuple[Document, str]]:
    pieces, cur, n = [], [], 0
    for para in re.split(r"\n\s*\n", doc.text):
        words = para.split()
        if not words:
            continue
        if n + len(words) > max_words and cur:
            pieces.append(" ".join(cur)); cur, n = [], 0
        while len(words) > max_words:                     # very long paragraph (e.g. a station list)
            pieces.append(" ".join(words[:max_words])); words = words[max_words:]
        cur.extend(words); n += len(words)
    if cur:
        pieces.append(" ".join(cur))
    return [(doc, p) for p in pieces]


class KnowledgeRetriever:
    def __init__(self, documents: list[Document]):
        self.chunks = [c for d in documents for c in chunk(d)]
        self.vec = self.matrix = None
        if self.chunks:
            self.vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True)
            self.matrix = self.vec.fit_transform([f"{d.title}. {t}" for d, t in self.chunks])

    def search(self, query: str, k: int = 4, min_score: float = 0.04) -> list[Passage]:
        if not self.vec or not query.strip():
            return []
        sims = cosine_similarity(self.vec.transform([query]), self.matrix)[0]
        order = sims.argsort()[::-1][:k]
        return [Passage(self.chunks[i][0].source, self.chunks[i][0].title, self.chunks[i][1], float(sims[i]))
                for i in order if sims[i] >= min_score]


_retriever: KnowledgeRetriever | None = None


def get_retriever(rebuild: bool = False) -> KnowledgeRetriever:
    global _retriever
    if _retriever is None or rebuild:
        _retriever = KnowledgeRetriever(build_documents())
    return _retriever
