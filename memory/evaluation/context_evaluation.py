from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable


@dataclass
class RetrievalEvaluation:
    query: str
    retrieved: list[str]
    relevant: list[str]
    precision: float
    recall: float
    f1: float


def _normalize(value: str) -> str:
    return " ".join(value.lower().split())


def _is_relevant(document: str, relevant_documents: Iterable[str]) -> bool:
    normalized_document = _normalize(document)

    for relevant in relevant_documents:
        normalized_relevant = _normalize(relevant)

        if (
            normalized_document == normalized_relevant
            or normalized_relevant in normalized_document
            or normalized_document in normalized_relevant
        ):
            return True

    return False


def evaluate_retrieval(
    query: str,
    retrieved_documents: list[str],
    relevant_documents: list[str],
) -> RetrievalEvaluation:
    retrieved = list(retrieved_documents)
    relevant = list(relevant_documents)

    if not retrieved:
        precision = 0.0
    else:
        relevant_retrieved = sum(
            _is_relevant(document, relevant)
            for document in retrieved
        )
        precision = relevant_retrieved / len(retrieved)

    if not relevant:
        recall = 1.0 if not retrieved else 0.0
    else:
        retrieved_relevant = sum(
            _is_relevant(document, retrieved)
            for document in relevant
        )
        recall = retrieved_relevant / len(relevant)

    if precision + recall == 0:
        f1 = 0.0
    else:
        f1 = (
            2 * precision * recall
            / (precision + recall)
        )

    return RetrievalEvaluation(
        query=query,
        retrieved=retrieved,
        relevant=relevant,
        precision=precision,
        recall=recall,
        f1=f1,
    )


def evaluate_rag_method(
    rag_method: Callable[[str], list[str]],
    dataset: list[dict],
) -> dict:
    evaluations = []

    for sample in dataset:
        query = sample["query"]
        relevant_documents = sample.get(
            "relevant_documents",
            [],
        )

        retrieved_documents = rag_method(query)

        evaluations.append(
            evaluate_retrieval(
                query=query,
                retrieved_documents=retrieved_documents,
                relevant_documents=relevant_documents,
            )
        )

    if not evaluations:
        return {
            "queries": 0,
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
            "details": [],
        }

    precision = sum(
        item.precision for item in evaluations
    ) / len(evaluations)

    recall = sum(
        item.recall for item in evaluations
    ) / len(evaluations)

    f1 = sum(
        item.f1 for item in evaluations
    ) / len(evaluations)

    return {
        "queries": len(evaluations),
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "details": evaluations,
    }


def compare_rag_methods(
    methods: dict[str, Callable[[str], list[str]]],
    dataset: list[dict],
) -> dict:
    results = {}

    for name, method in methods.items():
        results[name] = evaluate_rag_method(
            method,
            dataset,
        )

    return results
