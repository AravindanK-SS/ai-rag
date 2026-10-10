"""
Lexical (BM25) retriever over the chunks already persisted in vectorstore/current.

Why this exists: the project venv is dead on this machine, so langchain/chroma/MiniLM can't
be loaded. The chunk text and source_file metadata ARE readable straight from Chroma's SQLite
file, so both race arms use this one retriever. Same ruler for both arms; absolute retrieval
quality is lower than the Week 5 dense retriever, and that is disclosed in race_table.md.
"""
import math
import re
import sqlite3
from collections import Counter, defaultdict
from typing import Dict, List

STOP = {"the", "and", "for", "with", "that", "this", "from", "have", "has", "are", "was", "were",
        "can", "what", "who", "how", "does", "did", "you", "your", "our", "not", "but", "any",
        "all", "get", "about", "will", "shall", "may", "must", "its", "their", "there", "than"}


def _stem(w: str) -> str:
    for suf in ("ing", "ed", "es", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            return w[: -len(suf)]
    return w


def tokenize(text: str) -> List[str]:
    return [_stem(w) for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 2 and w not in STOP]


class ChunkIndex:
    def __init__(self, db_path: str = "vectorstore/current/chroma.sqlite3"):
        con = sqlite3.connect(db_path)
        rows: Dict[int, Dict] = defaultdict(dict)
        for cid, key, sval, ival in con.execute(
                "select id,key,string_value,int_value from embedding_metadata "
                "where key in ('chroma:document','source_file','page')"):
            rows[cid][key] = ival if key == "page" else sval
        con.close()
        self.chunks: List[Dict] = []
        for r in rows.values():
            text = r.get("chroma:document") or ""
            if text.count(".") > 0.15 * max(len(text), 1):   # table-of-contents leader dots
                continue
            self.chunks.append({"text": " ".join(text.split()), "source": r.get("source_file", "?"),
                                "page": r.get("page")})
        self._tf = [Counter(tokenize(c["text"])) for c in self.chunks]
        self._len = [sum(tf.values()) for tf in self._tf]
        self._avg = sum(self._len) / max(len(self._len), 1)
        df = Counter()
        for tf in self._tf:
            df.update(tf.keys())
        n = len(self.chunks)
        self._idf = {t: math.log(1 + (n - d + 0.5) / (d + 0.5)) for t, d in df.items()}

    def search(self, query: str, k: int = 3) -> List[Dict]:
        q = tokenize(query)
        scored = []
        for i, tf in enumerate(self._tf):
            s = 0.0
            for t in q:
                f = tf.get(t, 0)
                if f:
                    s += self._idf.get(t, 0) * f * 2.5 / (f + 1.5 * (0.25 + 0.75 * self._len[i] / self._avg))
            if s > 0:
                scored.append((s, i))
        scored.sort(reverse=True)
        return [self.chunks[i] for _, i in scored[:k]]
