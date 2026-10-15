#!/usr/bin/env python3
"""BM25 + 向量 混合索引（纯 Python + numpy，无 torch 依赖）。

向量 = 字符 bigram 特征哈希 + IDF 加权 + L2 归一化（中文可用的轻量稠密向量）；
BM25 = 自实现。检索时用倒数排名融合(RRF) 合并两者。
"""
from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from pathlib import Path

import numpy as np


def tokenize(text: str) -> list[str]:
    """中文按「双字 + 三字」切（不用单字，避免“芯/国”这类噪声），英文按词、数字按串。"""
    words = re.findall(r"[a-zA-Z]+|\d+(?:\.\d+)?%?", text.lower())
    chars = re.findall(r"[\u4e00-\u9fa5]", text)
    bigrams = [chars[i] + chars[i + 1] for i in range(len(chars) - 1)]
    trigrams = [chars[i] + chars[i + 1] + chars[i + 2] for i in range(len(chars) - 2)]
    return words + bigrams + trigrams


def bigrams(text: str) -> list[str]:
    chars = re.sub(r"[^\u4e00-\u9fa5]", "", text)
    return [chars[i : i + 2] for i in range(len(chars) - 1)]


class BM25:
    def __init__(self, docs: list[str], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.docs = [tokenize(d) for d in docs]
        self.n = len(self.docs)
        self.avgdl = sum(len(d) for d in self.docs) / max(1, self.n)
        self.df: Counter = Counter()
        for d in self.docs:
            for t in set(d):
                self.df[t] += 1
        self.idf = {t: math.log(1 + (self.n - c + 0.5) / (c + 0.5)) for t, c in self.df.items()}

    def scores(self, query: str) -> np.ndarray:
        q = tokenize(query)
        out = np.zeros(self.n, dtype=np.float32)
        for i, d in enumerate(self.docs):
            if not d:
                continue
            f = Counter(d)
            dl = len(d)
            s = 0.0
            for t in q:
                if t in self.idf:
                    tf = f.get(t, 0)
                    s += self.idf[t] * tf * (self.k1 + 1) / (
                        tf + self.k1 * (1 - self.b + self.b * dl / self.avgdl)
                    )
            out[i] = s
        return out


class HashingVectorIndex:
    def __init__(self, docs: list[str], dim: int = 4096):
        self.dim = dim
        self.docs = docs
        # 统计每个 bigram 的 DF 以计算 IDF
        df: Counter = Counter()
        for d in docs:
            for g in set(bigrams(d)):
                df[g] += 1
        n = max(1, len(docs))
        self.idf = {g: math.log(1 + n / (c + 1)) for g, c in df.items()}

    def _embed(self, text: str) -> np.ndarray:
        vec = np.zeros(self.dim, dtype=np.float32)
        for g in bigrams(text):
            h = int(hashlib.md5(g.encode()).hexdigest()[:8], 16)
            vec[h % self.dim] += self.idf.get(g, 1.0)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        return vec

    def build(self) -> np.ndarray:
        return np.vstack([self._embed(d) for d in self.docs]).astype(np.float32)

    def query_vec(self, text: str) -> np.ndarray:
        return self._embed(text)


class HybridIndex:
    def __init__(self, records: list[dict], rrf_k: int = 60):
        self.records = records
        self.texts = [r["text"] for r in records]
        self.bm25 = BM25(self.texts)
        self.vec = HashingVectorIndex(self.texts)
        self.vectors = self.vec.build()
        self.rrf_k = rrf_k
        # 公司别名 -> 公司名，用于把问题里点名的公司做元数据加权重排序
        self.aliases: list[tuple[str, str]] = []
        for r in records:
            self.aliases.append((r["company"], r["company"]))
            self.aliases.append((r["code"], r["company"]))
        self.aliases = sorted(set(self.aliases), key=lambda x: -len(x[0]))
        # 每家公司的本地 BM25：公司名在“页眉”里重复，全局 IDF 会把它当强信号，
        # 本地 IDF 才能让“营业收入/净利润”这类词在公司内部起作用
        self.company_indices: dict[str, list[int]] = {}
        self.company_bm25: dict[str, BM25] = {}
        for i, r in enumerate(records):
            self.company_indices.setdefault(r["company"], []).append(i)
        for company, idxs in self.company_indices.items():
            self.company_bm25[company] = BM25([self.texts[i] for i in idxs])

    def _rank(self, scores: np.ndarray) -> np.ndarray:
        order = np.argsort(-scores, kind="stable")
        ranks = np.empty_like(order, dtype=np.float64)
        ranks[order] = np.arange(1, len(scores) + 1)
        return ranks

    def query(self, q: str, top_k: int = 5) -> list[dict]:
        matched = {c for a, c in self.aliases if a in q}
        if matched:
            # 点名公司：先公司过滤，再在公司内部用本地 BM25 精排
            scored: list[tuple[float, int]] = []
            for company in matched:
                local = self.company_bm25[company].scores(q)
                for gi, s in zip(self.company_indices[company], local):
                    scored.append((float(s), gi))
            scored.sort(key=lambda x: x[0], reverse=True)
            out = []
            for s, gi in scored[:top_k]:
                r = self.records[gi]
                out.append({**r, "bm25": s, "dense": 0.0, "fused": 0.5})
            return out

        bm = self.bm25.scores(q)
        dense = self.vectors @ self.vec.query_vec(q)
        bm_rank = self._rank(bm)
        d_rank = self._rank(dense)
        fused = 1.0 / (self.rrf_k + bm_rank) + 1.0 / (self.rrf_k + d_rank)
        top = np.argsort(-fused)[:top_k]
        return [
            {
                **self.records[i],
                "bm25": float(bm[i]),
                "dense": float(dense[i]),
                "fused": float(fused[i]),
            }
            for i in top
        ]


def load_chunks(path: str) -> list[dict]:
    import json
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]
