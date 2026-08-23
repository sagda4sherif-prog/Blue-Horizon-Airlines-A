import os
import sys
import time

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

sys.path.append(PROJECT_ROOT)

from rag.rag_pipeline import OperationalRAGPipeline


TEST_CASES = [
    {
        "question": (
            "What is the standard fasting or reporting window "
            "before operational flight duties?"
        ),
        "keywords": [
            "fasting",
            "reporting",
            "flight duties",
        ],
    },
    {
        "question": (
            "What does Protocol 4.2b specify regarding severe "
            "weather delay protocols?"
        ),
        "keywords": [
            "protocol 4.2b",
            "severe weather",
            "delay",
        ],
    },
    {
        "question": (
            "For a flight facing both a crew duty-hour limit and "
            "an aircraft maintenance hold, what steps and approvals "
            "are required before it can depart?"
        ),
        "keywords": [
            "crew",
            "duty",
            "maintenance",
            "approval",
        ],
    },
]


def estimate_tokens(text):
    words = text.split()
    return max(1, int(len(words) * 1.3))


def keyword_accuracy(question_data, documents):
    if not documents:
        return False

    context = " ".join(documents).lower()

    matched = sum(
        1
        for keyword in question_data["keywords"]
        if keyword.lower() in context
    )

    required = max(
        1,
        len(question_data["keywords"]) // 2
    )

    return matched >= required


def run_retrieval_evaluation():
    print("\n" + "=" * 70)
    print("BLUE HORIZON AIRLINES - RAG EVALUATION")
    print("=" * 70)

    try:
        rag = OperationalRAGPipeline()
    except Exception as error:
        print(
            f"Error initializing RAG Pipeline: {error}"
        )
        return

    metrics = {
        "Naive RAG": {
            "correct": 0,
            "latency": 0.0,
            "tokens": 0,
        },
        "Hybrid Search": {
            "correct": 0,
            "latency": 0.0,
            "tokens": 0,
        },
        "Agentic RAG": {
            "correct": 0,
            "latency": 0.0,
            "tokens": 0,
        },
    }

    total_questions = len(TEST_CASES)

    for index, test_case in enumerate(TEST_CASES, 1):
        question = test_case["question"]

        print(
            f"\nQuestion {index}/{total_questions}:"
        )
        print(question)

        start = time.perf_counter()

        naive_docs = rag.naive_rag(
            question,
            top_k=3,
        )

        naive_latency = (
            time.perf_counter() - start
        )

        naive_correct = keyword_accuracy(
            test_case,
            naive_docs,
        )

        metrics["Naive RAG"]["correct"] += int(
            naive_correct
        )

        metrics["Naive RAG"]["latency"] += (
            naive_latency
        )

        metrics["Naive RAG"]["tokens"] += (
            estimate_tokens(
                question
                + " "
                + " ".join(naive_docs)
            )
        )

        start = time.perf_counter()

        hybrid_docs = rag.hybrid_search(
            question,
            top_k=3,
        )

        hybrid_latency = (
            time.perf_counter() - start
        )

        hybrid_correct = keyword_accuracy(
            test_case,
            hybrid_docs,
        )

        metrics["Hybrid Search"]["correct"] += int(
            hybrid_correct
        )

        metrics["Hybrid Search"]["latency"] += (
            hybrid_latency
        )

        metrics["Hybrid Search"]["tokens"] += (
            estimate_tokens(
                question
                + " "
                + " ".join(hybrid_docs)
            )
        )

        start = time.perf_counter()

        agentic_docs = rag.agentic_rag(
            question
        )

        agentic_latency = (
            time.perf_counter() - start
        )

        agentic_correct = keyword_accuracy(
            test_case,
            agentic_docs,
        )

        metrics["Agentic RAG"]["correct"] += int(
            agentic_correct
        )

        metrics["Agentic RAG"]["latency"] += (
            agentic_latency
        )

        metrics["Agentic RAG"]["tokens"] += (
            estimate_tokens(
                question
                + " "
                + " ".join(agentic_docs)
                + " "
                + question
            )
        )

    print("\n" + "=" * 70)
    print("RAG ARCHITECTURE COMPARISON")
    print("=" * 70)

    print(
        f"{'Architecture':<20}"
        f"| {'Accuracy':<12}"
        f"| {'Avg Latency':<15}"
        f"| {'Avg Tokens':<12}"
    )

    print("-" * 70)

    for architecture, data in metrics.items():
        accuracy = (
            data["correct"] / total_questions
            if total_questions
            else 0
        )

        avg_latency = (
            data["latency"] / total_questions
            if total_questions
            else 0
        )

        avg_tokens = (
            data["tokens"] / total_questions
            if total_questions
            else 0
        )

        print(
            f"{architecture:<20}"
            f"| {accuracy:.2%}      "
            f"| {avg_latency:.3f}s"
            f"        | {avg_tokens:.0f}"
        )

    print("=" * 70)


if __name__ == "__main__":
    run_retrieval_evaluation()
