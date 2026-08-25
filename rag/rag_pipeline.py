import os
import re
import uuid
import warnings
from typing import Any

from dotenv import load_dotenv

from langchain_google_genai import (
    ChatGoogleGenerativeAI,
    GoogleGenerativeAIEmbeddings,
)
from langchain_chroma import Chroma
from rank_bm25 import BM25Okapi


# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

load_dotenv()


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = os.path.dirname(
    os.path.abspath(__file__)
)

DEFAULT_DATA_PATH = os.path.join(
    PROJECT_ROOT,
    "rag_data",
    "operational_policies.txt",
)

PARENT_ROOT = os.path.dirname(
    PROJECT_ROOT
)

DEFAULT_VECTOR_DB_PATH = os.path.join(
    PARENT_ROOT,
    "vector_db",
)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

EMBEDDING_MODEL = "models/gemini-embedding-001"
LLM_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

CHUNK_SIZE = 700
CHUNK_OVERLAP = 100


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _normalize_text(text: str) -> str:
    """
    Normalize whitespace without destroying paragraph structure.
    """

    if not text:
        return ""

    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    # Remove excessive spaces but preserve newlines.
    text = re.sub(
        r"[ \t]+",
        " ",
        text,
    )

    # Collapse 3+ newlines into 2.
    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text,
    )

    return text.strip()


def _tokenize(text: str) -> list[str]:
    """
    Tokenizer used by BM25.

    Keeps useful policy identifiers such as:
        4.2b
        FDP
        High/Critical
        90
        45
    """

    if not text:
        return []

    return re.findall(
        r"[A-Za-z0-9]+(?:[./_-][A-Za-z0-9]+)*",
        text.lower(),
    )


def _split_text(text: str) -> list[str]:
    """
    Policy-aware text splitter.

    The previous implementation used a pure character window, which could
    split a policy heading from the rules immediately following it.

    This version first preserves paragraphs and then combines them into
    reasonably sized chunks.
    """

    text = _normalize_text(text)

    if not text:
        return []

    paragraphs = [
        paragraph.strip()
        for paragraph in text.split("\n\n")
        if paragraph.strip()
    ]

    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:

        # If adding this paragraph still fits, keep it together.
        if not current:
            current = paragraph
            continue

        candidate = f"{current}\n\n{paragraph}"

        if len(candidate) <= CHUNK_SIZE:
            current = candidate
            continue

        # Save the current chunk.
        chunks.append(current.strip())

        # Keep a small overlap from the previous chunk.
        overlap = current[-CHUNK_OVERLAP:].strip()

        if overlap:
            current = f"{overlap}\n\n{paragraph}"
        else:
            current = paragraph

        # If a single paragraph is huge, split it locally.
        if len(current) > CHUNK_SIZE * 1.5:

            while len(current) > CHUNK_SIZE:

                split_at = current.rfind(
                    " ",
                    0,
                    CHUNK_SIZE,
                )

                if split_at < CHUNK_SIZE // 2:
                    split_at = CHUNK_SIZE

                piece = current[:split_at].strip()

                if piece:
                    chunks.append(piece)

                remainder = current[split_at:].strip()

                overlap = piece[-CHUNK_OVERLAP:].strip()

                if overlap:
                    current = f"{overlap} {remainder}"
                else:
                    current = remainder

    if current.strip():
        chunks.append(current.strip())

    return chunks


# ---------------------------------------------------------------------------
# Operational RAG Pipeline
# ---------------------------------------------------------------------------

class OperationalRAGPipeline:
    """
    Production-oriented RAG pipeline for Blue Horizon Airlines.

    Architecture:

        operational_policies.txt
                  |
                  v
             Chunking
                  |
          +-------+-------+
          |               |
          v               v
      Gemini Vector     BM25
       Retrieval       Retrieval
          |               |
          +-------+-------+
                  |
                 RRF
                  |
                  v
             Top-K chunks
                  |
                  v
                Gemini
                  |
                  v
             Final answer
    """

    COLLECTION_NAME = "blue_horizon_operational_policies"

    def __init__(
        self,
        file_path: str = DEFAULT_DATA_PATH,
        persist_directory: str = DEFAULT_VECTOR_DB_PATH,
    ):

        self.file_path = file_path
        self.persist_directory = persist_directory

        # ---------------------------------------------------------------
        # API key
        # ---------------------------------------------------------------

        self.api_key = (
            os.getenv("GEMINI_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
        )

        if not self.api_key:
            raise ValueError(
                "GEMINI_API_KEY or GOOGLE_API_KEY "
                "environment variable is not set."
            )

        # ---------------------------------------------------------------
        # Embeddings
        # ---------------------------------------------------------------

        self.embeddings = GoogleGenerativeAIEmbeddings(
            model=EMBEDDING_MODEL,
            google_api_key=self.api_key,
        )

        # ---------------------------------------------------------------
        # Runtime state
        # ---------------------------------------------------------------

        self.vector_store: Chroma | None = None

        self.documents_cache: list[str] = []

        self.metadata_cache: list[dict] = []

        self.chunk_ids: list[str] = []

        self.metadata_index: dict[str, dict[str, set[int]]] = {}

        self.bm25_index: BM25Okapi | None = None

        self.llm: ChatGoogleGenerativeAI | None = None

        # ---------------------------------------------------------------
        # Initialize
        # ---------------------------------------------------------------

        self._initialize_pipeline()

    # -------------------------------------------------------------------
    # Seed documents
    # -------------------------------------------------------------------

    def _resolve_data_path(self) -> str:

        candidates = [
            self.file_path,

            os.path.join(
                PARENT_ROOT,
                "agent",
                "rag_data",
                "operational_policies.txt",
            ),

            os.path.join(
                PARENT_ROOT,
                "operational_policies.txt",
            ),
        ]

        for path in candidates:
            if os.path.exists(path):
                return path

        raise FileNotFoundError(
            "Operational manual not found. Checked:\n"
            + "\n".join(candidates)
        )

    def _load_seed_documents(
        self,
    ) -> tuple[list[str], list[dict]]:

        self.file_path = self._resolve_data_path()

        with open(
            self.file_path,
            "r",
            encoding="utf-8",
        ) as file:
            text = file.read()

        chunks = _split_text(text)

        source = os.path.basename(
            self.file_path
        )

        documents: list[str] = []
        metadatas: list[dict] = []

        for index, chunk in enumerate(chunks):

            documents.append(chunk)

            metadatas.append(
                {
                    "source": source,
                    "title": source,
                    "chunk_id": index,
                    "document_type": "operational_policy",
                }
            )

        return documents, metadatas

    # -------------------------------------------------------------------
    # Vector store
    # -------------------------------------------------------------------

    def _create_vector_store(
        self,
        documents: list[str],
        metadatas: list[dict],
        ids: list[str],
    ) -> Chroma:

        if not documents:
            raise ValueError(
                "Cannot create vector store without documents."
            )

        return Chroma.from_texts(
            texts=documents,
            embedding=self.embeddings,
            metadatas=metadatas,
            ids=ids,
            collection_name=self.COLLECTION_NAME,
            persist_directory=self.persist_directory,
        )

    def _open_existing_vector_store(self) -> Chroma:

        return Chroma(
            collection_name=self.COLLECTION_NAME,
            persist_directory=self.persist_directory,
            embedding_function=self.embeddings,
        )

    def _load_existing_documents(
        self,
    ) -> tuple[list[str], list[dict], list[str]]:

        if not os.path.exists(
            self.persist_directory
        ):
            return [], [], []

        try:

            store = self._open_existing_vector_store()

            data = store.get(
                include=[
                    "documents",
                    "metadatas",
                ],
            )

            documents = data.get(
                "documents"
            ) or []

            metadatas = data.get(
                "metadatas"
            ) or []

            ids = data.get(
                "ids"
            ) or []

            if not documents:
                return [], [], []

            normalized_metadatas = [
                dict(metadata or {})
                for metadata in metadatas
            ]

            return (
                list(documents),
                normalized_metadatas,
                list(ids),
            )

        except Exception as exc:

            warnings.warn(
                "Could not read existing Chroma collection. "
                f"Reason: {type(exc).__name__}: {exc}. "
                "The collection will be rebuilt.",
                stacklevel=2,
            )

            return [], [], []

    # -------------------------------------------------------------------
    # Collection validation
    # -------------------------------------------------------------------

    def _seed_signature(
        self,
        documents: list[str],
    ) -> str:

        import hashlib

        joined = "\n---CHUNK---\n".join(
            documents
        )

        return hashlib.sha256(
            joined.encode("utf-8")
        ).hexdigest()

    def _get_collection_signature(
        self,
        store: Chroma,
    ) -> str | None:

        try:
            metadata = store._collection.metadata or {}

            value = metadata.get(
                "seed_signature"
            )

            return (
                str(value)
                if value
                else None
            )

        except Exception:
            return None

    def _set_collection_signature(
        self,
        store: Chroma,
        signature: str,
    ) -> None:

        try:

            collection = store._collection

            metadata = dict(
                collection.metadata or {}
            )

            metadata["seed_signature"] = signature

            collection.modify(
                metadata=metadata
            )

        except Exception:
            # Metadata is useful but not required for operation.
            pass

    # -------------------------------------------------------------------
    # Initialization
    # -------------------------------------------------------------------

    def _initialize_pipeline(self) -> None:

        seed_documents, seed_metadatas = (
            self._load_seed_documents()
        )

        seed_signature = self._seed_signature(
            seed_documents
        )

        # ---------------------------------------------------------------
        # Try existing collection first.
        # ---------------------------------------------------------------

        existing_documents = []
        existing_metadatas = []
        existing_ids = []

        if os.path.exists(
            self.persist_directory
        ):

            (
                existing_documents,
                existing_metadatas,
                existing_ids,
            ) = self._load_existing_documents()

        # ---------------------------------------------------------------
        # Existing collection is usable.
        # ---------------------------------------------------------------

        if existing_documents:

            documents = existing_documents

            metadatas = existing_metadatas

            ids = existing_ids

            # Make sure metadata has expected fields.
            for index, metadata in enumerate(
                metadatas
            ):

                metadata.setdefault(
                    "source",
                    os.path.basename(
                        self.file_path
                    ),
                )

                metadata.setdefault(
                    "title",
                    metadata.get(
                        "source",
                        os.path.basename(
                            self.file_path
                        ),
                    ),
                )

                metadata["chunk_id"] = index

            self.vector_store = (
                self._open_existing_vector_store()
            )

            # -----------------------------------------------------------
            # Detect changed source corpus.
            # -----------------------------------------------------------

            existing_signature = (
                self._get_collection_signature(
                    self.vector_store
                )
            )

            if (
                existing_signature
                and existing_signature == seed_signature
            ):

                # Perfect match: reuse DB.
                pass

            elif (
                not existing_signature
                and len(existing_documents)
                == len(seed_documents)
            ):

                # Legacy collection.
                #
                # Do NOT rebuild automatically. The collection is already
                # readable with the current embedding function.
                #
                # Mark it with the current signature.
                self._set_collection_signature(
                    self.vector_store,
                    seed_signature,
                )

            else:

                # Seed changed or collection incompatible.
                self._rebuild_from_seed(
                    seed_documents,
                    seed_metadatas,
                    seed_signature,
                )

                (
                    existing_documents,
                    existing_metadatas,
                    existing_ids,
                ) = self._load_existing_documents()

                documents = existing_documents
                metadatas = existing_metadatas
                ids = existing_ids

        # ---------------------------------------------------------------
        # No existing DB.
        # ---------------------------------------------------------------

        else:

            documents = seed_documents

            metadatas = seed_metadatas

            ids = [
                (
                    f"seed::"
                    f"{os.path.basename(self.file_path)}::"
                    f"{index}"
                )
                for index in range(
                    len(documents)
                )
            ]

            self.vector_store = (
                self._create_vector_store(
                    documents=documents,
                    metadatas=metadatas,
                    ids=ids,
                )
            )

            self._set_collection_signature(
                self.vector_store,
                seed_signature,
            )

        # ---------------------------------------------------------------
        # Final runtime caches.
        # ---------------------------------------------------------------

        if not documents:
            raise ValueError(
                "No documents are available "
                "for the RAG vector store."
            )

        self.documents_cache = list(
            documents
        )

        self.metadata_cache = [
            dict(metadata or {})
            for metadata in metadatas
        ]

        self.chunk_ids = list(ids)

        self._rebuild_metadata_index()

        self._rebuild_bm25_index()

    # -------------------------------------------------------------------
    # Rebuild
    # -------------------------------------------------------------------

    def _rebuild_from_seed(
        self,
        documents: list[str],
        metadatas: list[dict],
        signature: str,
    ) -> None:

        try:

            old_store = (
                self._open_existing_vector_store()
            )

            old_store.delete_collection()

        except Exception:
            pass

        ids = [
            (
                f"seed::"
                f"{os.path.basename(self.file_path)}::"
                f"{index}"
            )
            for index in range(
                len(documents)
            )
        ]

        self.vector_store = (
            self._create_vector_store(
                documents=documents,
                metadatas=metadatas,
                ids=ids,
            )
        )

        self._set_collection_signature(
            self.vector_store,
            signature,
        )

    # -------------------------------------------------------------------
    # BM25
    # -------------------------------------------------------------------

    def _rebuild_bm25_index(self) -> None:

        tokenized_corpus = [
            _tokenize(document)
            for document in self.documents_cache
        ]

        if tokenized_corpus:

            self.bm25_index = BM25Okapi(
                tokenized_corpus
            )

        else:

            self.bm25_index = None

    # -------------------------------------------------------------------
    # LLM
    # -------------------------------------------------------------------

    def _get_llm(
        self,
    ) -> ChatGoogleGenerativeAI:

        if self.llm is None:

            self.llm = ChatGoogleGenerativeAI(
                model=LLM_MODEL,
                google_api_key=self.api_key,
                temperature=0,
            )

        return self.llm

    # -------------------------------------------------------------------
    # Metadata
    # -------------------------------------------------------------------

    def _matches_metadata(
        self,
        index: int,
        metadata_filter: dict | None,
    ) -> bool:

        if not metadata_filter:
            return True

        metadata = self.metadata_cache[
            index
        ]

        for key, expected_value in (
            metadata_filter.items()
        ):

            if str(
                metadata.get(key)
            ) != str(expected_value):

                return False

        return True

    # -------------------------------------------------------------------
    # Naive RAG
    # -------------------------------------------------------------------

    def naive_rag(
        self,
        query: str,
        top_k: int = 3,
        metadata_filter: dict | None = None,
    ) -> list[str]:

        if not self.vector_store:
            return []

        results = self.vector_store.similarity_search(
            query,
            k=top_k,
            filter=(
                metadata_filter
                if metadata_filter
                else None
            ),
        )

        return [
            document.page_content
            for document in results
        ]

    # -------------------------------------------------------------------
    # Hybrid Search
    # -------------------------------------------------------------------

    def hybrid_search(
        self,
        query: str,
        top_k: int = 3,
        metadata_filter: dict | None = None,
    ) -> list[str]:

        if not query or not query.strip():
            return []

        if not self.vector_store:
            return []

        # ---------------------------------------------------------------
        # Candidate size
        # ---------------------------------------------------------------

        candidate_k = max(
            top_k * 3,
            8,
        )

        # ---------------------------------------------------------------
        # Vector retrieval
        # ---------------------------------------------------------------

        vector_results = (
            self.vector_store.similarity_search(
                query,
                k=candidate_k,
                filter=(
                    metadata_filter
                    if metadata_filter
                    else None
                ),
            )
        )

        vector_docs = [
            document.page_content
            for document in vector_results
        ]

        # ---------------------------------------------------------------
        # BM25 retrieval
        # ---------------------------------------------------------------

        tokenized_query = _tokenize(
            query
        )

        if (
            self.bm25_index is not None
            and tokenized_query
        ):

            bm25_scores = (
                self.bm25_index.get_scores(
                    tokenized_query
                )
            )

        else:

            bm25_scores = [
                0.0
                for _ in self.documents_cache
            ]

        candidate_indices = list(
            range(
                len(
                    bm25_scores
                )
            )
        )

        if metadata_filter:

            candidate_indices = [
                index
                for index in candidate_indices
                if self._matches_metadata(
                    index,
                    metadata_filter,
                )
            ]

        top_bm25_indices = sorted(
            candidate_indices,
            key=lambda index:
                bm25_scores[index],
            reverse=True,
        )[:candidate_k]

        bm25_docs = [
            self.documents_cache[index]
            for index in top_bm25_indices
        ]

        # ---------------------------------------------------------------
        # Reciprocal Rank Fusion
        # ---------------------------------------------------------------

        rrf_scores: dict[str, float] = {}

        def add_ranks(
            documents: list[str],
        ) -> None:

            for rank, document in enumerate(
                documents
            ):

                rrf_scores.setdefault(
                    document,
                    0.0,
                )

                rrf_scores[document] += (
                    1.0
                    / (
                        60
                        + rank
                        + 1
                    )
                )

        add_ranks(vector_docs)
        add_ranks(bm25_docs)

        sorted_docs = sorted(
            rrf_scores.keys(),
            key=lambda document:
                rrf_scores[document],
            reverse=True,
        )

        return sorted_docs[:top_k]

    # -------------------------------------------------------------------
    # Agentic RAG
    # -------------------------------------------------------------------

    def agentic_rag(
        self,
        query: str,
        metadata_filter: dict | None = None,
    ) -> list[str]:

        initial_docs = self.hybrid_search(
            query,
            top_k=4,
            metadata_filter=metadata_filter,
        )

        if not initial_docs:
            return []

        try:

            llm = self._get_llm()

            context = "\n\n---\n\n".join(
                initial_docs
            )

            critique_prompt = f"""
You are a retrieval-quality evaluator for
Blue Horizon Airlines operational policies.

User question:
{query}

Retrieved policy context:
{context}

Determine whether the retrieved context is sufficient
to answer the question.

If it is sufficient, reply exactly:
SUFFICIENT

If it is not sufficient, provide ONLY a better search
query that should retrieve the missing policy information.

Do not answer the user's question.
"""

            response = llm.invoke(
                critique_prompt
            )

            response_text = str(
                response.content
            ).strip()

            if (
                response_text
                and "SUFFICIENT"
                not in response_text.upper()
            ):

                refined_query = (
                    response_text
                )

                additional_docs = (
                    self.hybrid_search(
                        refined_query,
                        top_k=3,
                        metadata_filter=metadata_filter,
                    )
                )

                initial_docs = list(
                    dict.fromkeys(
                        initial_docs
                        + additional_docs
                    )
                )

            return initial_docs

        except Exception as exc:

            warnings.warn(
                "Agentic RAG refinement failed: "
                f"{type(exc).__name__}: {exc}. "
                "Falling back to hybrid search.",
                stacklevel=2,
            )

            return initial_docs

    # -------------------------------------------------------------------
    # Self-RAG Verification
    # -------------------------------------------------------------------

    def self_rag_verification(
        self,
        query: str,
        retrieved_docs: list[str],
    ) -> bool:

        if not retrieved_docs:
            return False

        try:

            llm = self._get_llm()

            context = (
                "\n\n---\n\n".join(
                    retrieved_docs
                )
            )

            prompt = f"""
You are validating retrieval for Blue Horizon Airlines.

Question:
{query}

Retrieved operational policy:
{context}

Is this context directly relevant and sufficient
to answer the question without inventing information?

Respond with ONLY:
YES
or
NO
"""

            response = llm.invoke(
                prompt
            )

            content = response.content

            if isinstance(
                content,
                list,
            ):

                raw_text = " ".join(
                    (
                        item
                        if isinstance(
                            item,
                            str,
                        )
                        else item.get(
                            "text",
                            str(item),
                        )
                        if isinstance(
                            item,
                            dict,
                        )
                        else str(item)
                    )
                    for item in content
                )

            else:

                raw_text = str(
                    content
                )

            return (
                raw_text.strip().upper()
                == "YES"
            )

        except Exception as exc:

            warnings.warn(
                "Self-RAG verification failed: "
                f"{type(exc).__name__}: {exc}",
                stacklevel=2,
            )

            return False

    # -------------------------------------------------------------------
    # Document Management
    # -------------------------------------------------------------------

    def add_document(
        self,
        title: str,
        content: str,
    ) -> None:

        if not title or not title.strip():
            raise ValueError(
                "Document title must not be empty."
            )

        if not content or not content.strip():
            raise ValueError(
                "Document content must not be empty."
            )

        raw_chunks = _split_text(
            content
        )

        if not raw_chunks:
            raise ValueError(
                "Document produced no chunks."
            )

        new_ids = [
            (
                f"doc::{title}::"
                f"{uuid.uuid4().hex}"
            )
            for _ in raw_chunks
        ]

        new_metadatas = [
            {
                "source": title,
                "title": title,
                "chunk_id": None,
                "document_type": "operational_policy",
            }
            for _ in raw_chunks
        ]

        if not self.vector_store:
            raise RuntimeError(
                "Vector store is not initialized."
            )

        self.vector_store.add_texts(
            texts=raw_chunks,
            metadatas=new_metadatas,
            ids=new_ids,
        )

        self.documents_cache.extend(
            raw_chunks
        )

        self.metadata_cache.extend(
            new_metadatas
        )

        self.chunk_ids.extend(
            new_ids
        )

        self._rebuild_metadata_index()

        self._rebuild_bm25_index()

    def remove_document(
        self,
        title: str,
    ) -> None:

        if not self.vector_store:
            return

        keep_indices = [
            index
            for index, metadata
            in enumerate(
                self.metadata_cache
            )
            if metadata.get(
                "title"
            ) != title
        ]

        removed_ids = [
            self.chunk_ids[index]
            for index in range(
                len(
                    self.chunk_ids
                )
            )
            if index not in keep_indices
        ]

        if not removed_ids:
            return

        self.vector_store.delete(
            ids=removed_ids
        )

        self.documents_cache = [
            self.documents_cache[index]
            for index in keep_indices
        ]

        self.metadata_cache = [
            self.metadata_cache[index]
            for index in keep_indices
        ]

        self.chunk_ids = [
            self.chunk_ids[index]
            for index in keep_indices
        ]

        self._rebuild_metadata_index()

        self._rebuild_bm25_index()

    # -------------------------------------------------------------------
    # Metadata Index
    # -------------------------------------------------------------------

    def _rebuild_metadata_index(
        self,
    ) -> None:

        self.metadata_index = {}

        for index, metadata in enumerate(
            self.metadata_cache
        ):

            metadata["chunk_id"] = index

            for key, value in metadata.items():

                self.metadata_index.setdefault(
                    key,
                    {},
                )

                self.metadata_index[
                    key
                ].setdefault(
                    str(value),
                    set(),
                )

                self.metadata_index[
                    key
                ][str(value)].add(index)

    def get_metadata_index(
        self,
    ) -> dict:

        return {
            key: {
                value: sorted(
                    indices
                )
                for value, indices
                in values.items()
            }
            for key, values
            in self.metadata_index.items()
        }

    # -------------------------------------------------------------------
    # Diagnostics
    # -------------------------------------------------------------------

    def info(self) -> dict[str, Any]:

        return {
            "file_path": self.file_path,
            "persist_directory": self.persist_directory,
            "collection_name": self.COLLECTION_NAME,
            "embedding_model": EMBEDDING_MODEL,
            "llm_model": LLM_MODEL,
            "chunks": len(
                self.documents_cache
            ),
            "bm25_enabled": (
                self.bm25_index is not None
            ),
        }
