"""Relevance ranking for retrieved document chunks using TF-IDF cosine similarity."""

from typing import Optional

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from utils.chunker import Chunk


def rank_chunks(
    query: str,
    chunks: list[Chunk],
    top_k: int = 5,
) -> list[tuple[Chunk, float]]:
    """
    Rank chunks by TF-IDF cosine similarity to the query.

    Args:
        query: The user's question or prompt.
        chunks: All available chunks across loaded documents.
        top_k: Number of top chunks to return.

    Returns:
        List of (Chunk, score) tuples sorted by descending relevance.
    """
    if not chunks:
        return []

    texts = [query] + [c.text for c in chunks]

    vectorizer = TfidfVectorizer(
        stop_words="english",
        ngram_range=(1, 2),
        max_features=20_000,
        sublinear_tf=True,
    )

    try:
        tfidf_matrix = vectorizer.fit_transform(texts)
    except ValueError:
        # Edge case: all tokens are stop words or corpus is empty
        return [(c, 0.0) for c in chunks[:top_k]]

    query_vec = tfidf_matrix[0]
    chunk_vecs = tfidf_matrix[1:]

    scores = cosine_similarity(query_vec, chunk_vecs).flatten()

    # Pair chunks with scores and sort descending
    ranked = sorted(zip(chunks, scores.tolist()), key=lambda x: x[1], reverse=True)

    return ranked[:top_k]


def get_context_chunks(
    query: str,
    chunks: list[Chunk],
    mode: str = "qa",
) -> list[tuple[Chunk, float]]:
    """
    Select context chunks appropriate for the given mode.

    Args:
        query: User query or essay prompt.
        chunks: All loaded document chunks.
        mode: "qa" (top 3-5 chunks) or "essay" (top 10 chunks).

    Returns:
        Ranked list of (Chunk, score) tuples.
    """
    top_k = 10 if mode == "essay" else 5
    return rank_chunks(query, chunks, top_k=top_k)


def format_context_for_prompt(ranked_chunks: list[tuple[Chunk, float]]) -> str:
    """
    Format ranked chunks into a context block for the Claude prompt.
    Each chunk is labelled with its citation.
    """
    if not ranked_chunks:
        return "No relevant document context found."

    parts = []
    for i, (chunk, score) in enumerate(ranked_chunks, start=1):
        parts.append(
            f"[Source {i}: {chunk.citation}]\n{chunk.text}"
        )

    return "\n\n---\n\n".join(parts)
