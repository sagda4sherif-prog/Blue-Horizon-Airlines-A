import os
import warnings

from dotenv import load_dotenv

from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_chroma import Chroma
from rank_bm25 import BM25Okapi


load_dotenv()


PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

DEFAULT_DATA_PATH = os.path.join(
    PROJECT_ROOT,
    "rag_data",
    "operational_policies.txt",
)

PARENT_ROOT = os.path.dirname(PROJECT_ROOT)

DEFAULT_VECTOR_DB_PATH = os.path.join(
    PARENT_ROOT,
    "vector_db",
)


class OperationalRAGPipeline:
    def __init__(
        self,
        file_path: str = DEFAULT_DATA_PATH,
        persist_directory: str = DEFAULT_VECTOR_DB_PATH,
    ):
        self.file_path = file_path
        self.persist_directory = persist_directory

        self.embeddings = HuggingFaceEmbeddings(
            model_name="all-MiniLM-L6-v2"
        )

        self.vector_store = None
        self.documents_cache = []
        self.metadata_cache = []
        self.metadata_index = {}
        self.bm25_index = None
        self.llm = None

        self._initialize_pipeline()

    def _load_documents(self):
        if not os.path.exists(self.file_path):
            alt_path = os.path.join(
                PARENT_ROOT,
                "agent",
                "rag_data",
                "operational_policies.txt",
            )

            if os.path.exists(alt_path):
                self.file_path = alt_path
            else:
                alt_path_root = os.path.join(
                    PARENT_ROOT,
                    "operational_policies.txt",
                )

                if os.path.exists(alt_path_root):
                    self.file_path = alt_path_root
                else:
                    raise FileNotFoundError(
                        f"Operational manual not found at: {self.file_path}"
                    )

        loader = TextLoader(
            self.file_path,
            encoding="utf-8",
        )

        raw_docs = loader.load()

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=400,
            chunk_overlap=60,
        )

        return splitter.split_documents(raw_docs)

    def _build_metadata_index(self, chunks):
        self.metadata_index = {}

        for index, document in enumerate(chunks):
            metadata = document.metadata or {}

            metadata["source"] = os.path.basename(self.file_path)
            metadata["chunk_id"] = index

            document.metadata = metadata

            for key, value in metadata.items():
                self.metadata_index.setdefault(key, {})
                self.metadata_index[key].setdefault(
                    str(value),
                    set(),
                )
                self.metadata_index[key][str(value)].add(index)

    def _initialize_pipeline(self):
        chunks = self._load_documents()

        self._build_metadata_index(chunks)

        self.documents_cache = [
            document.page_content
            for document in chunks
        ]

        self.metadata_cache = [
            document.metadata
            for document in chunks
        ]

        tokenized_corpus = [
            document.split()
            for document in self.documents_cache
        ]

        self.bm25_index = BM25Okapi(tokenized_corpus)

        existing_store = (
            os.path.exists(self.persist_directory)
            and os.listdir(self.persist_directory)
        )

        if existing_store:
            self.vector_store = Chroma(
                persist_directory=self.persist_directory,
                embedding_function=self.embeddings,
            )

            existing_data = self.vector_store.get(
                include=["documents", "metadatas"]
            )

            existing_metadatas = existing_data.get(
                "metadatas",
                [],
            )

            if (
                not existing_metadatas
                or any(
                    not metadata or "chunk_id" not in metadata
                    for metadata in existing_metadatas
                )
            ):
                self.vector_store.delete_collection()

                self.vector_store = Chroma.from_documents(
                    documents=chunks,
                    embedding=self.embeddings,
                    persist_directory=self.persist_directory,
                )

        else:
            self.vector_store = Chroma.from_documents(
                documents=chunks,
                embedding=self.embeddings,
                persist_directory=self.persist_directory,
            )

    def _get_llm(self):
        if self.llm is None:
            api_key = (
                os.getenv("GEMINI_API_KEY")
                or os.getenv("GOOGLE_API_KEY")
            )

            if not api_key:
                raise ValueError(
                    "GEMINI_API_KEY or GOOGLE_API_KEY "
                    "environment variable is not set."
                )

            # gemini-1.5-flash is no longer available.
            # Keep the replacement used by the project evaluation code.
            self.llm = ChatGoogleGenerativeAI(
                model="gemini-3.5-flash-lite",
                google_api_key=api_key,
                temperature=0,
            )

        return self.llm

    def _matches_metadata(self, index, metadata_filter):
        if not metadata_filter:
            return True

        metadata = self.metadata_cache[index]

        for key, expected_value in metadata_filter.items():
            if str(metadata.get(key)) != str(expected_value):
                return False

        return True

    def naive_rag(
        self,
        query: str,
        top_k: int = 3,
        metadata_filter: dict | None = None,
    ) -> list[str]:

        if metadata_filter:
            results = self.vector_store.similarity_search(
                query,
                k=top_k,
                filter=metadata_filter,
            )
        else:
            results = self.vector_store.similarity_search(
                query,
                k=top_k,
            )

        return [
            document.page_content
            for document in results
        ]

    def hybrid_search(
        self,
        query: str,
        top_k: int = 3,
        metadata_filter: dict | None = None,
    ) -> list[str]:

        vector_k = top_k * 2

        vector_results = self.vector_store.similarity_search(
            query,
            k=vector_k,
            filter=metadata_filter if metadata_filter else None,
        )

        vector_docs = [
            document.page_content
            for document in vector_results
        ]

        tokenized_query = query.split()

        bm25_scores = self.bm25_index.get_scores(
            tokenized_query
        )

        candidate_indices = list(range(len(bm25_scores)))

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
            key=lambda index: bm25_scores[index],
            reverse=True,
        )[:vector_k]

        bm25_docs = [
            self.documents_cache[index]
            for index in top_bm25_indices
        ]

        rrf_scores = {}

        def add_ranks(documents):
            for rank, document in enumerate(documents):
                if document not in rrf_scores:
                    rrf_scores[document] = 0

                rrf_scores[document] += (
                    1 / (60 + rank + 1)
                )

        add_ranks(vector_docs)
        add_ranks(bm25_docs)

        sorted_docs = sorted(
            rrf_scores.keys(),
            key=lambda document: rrf_scores[document],
            reverse=True,
        )

        return sorted_docs[:top_k]

    def agentic_rag(
        self,
        query: str,
        metadata_filter: dict | None = None,
    ) -> list[str]:

        try:
            llm = self._get_llm()

            initial_docs = self.hybrid_search(
                query,
                top_k=3,
                metadata_filter=metadata_filter,
            )

            context_str = "\n".join(initial_docs)

            critique_prompt = (
                "Analyze if the retrieved policy context is fully "
                "sufficient to answer the query: "
                f"'{query}'.\n"
                f"Context:\n{context_str}\n"
                "Reply with 'SUFFICIENT' or provide a refined "
                "search query if more information is needed."
            )

            response = llm.invoke(
                critique_prompt
            ).content

            response_text = str(response)

            if (
                "SUFFICIENT" not in response_text.upper()
                and len(response_text.strip()) > 5
            ):
                refined_query = response_text.strip()

                additional_docs = self.hybrid_search(
                    refined_query,
                    top_k=2,
                    metadata_filter=metadata_filter,
                )

                initial_docs = list(
                    dict.fromkeys(
                        initial_docs + additional_docs
                    )
                )

            return initial_docs

        except Exception as exc:
            warnings.warn(
                "agentic_rag: critique/refine step failed "
                f"({type(exc).__name__}: {exc}); "
                "falling back to plain hybrid_search for this query.",
                stacklevel=2,
            )

            return self.hybrid_search(
                query,
                top_k=3,
                metadata_filter=metadata_filter,
            )

    def self_rag_verification(
        self,
        query: str,
        retrieved_docs: list[str],
    ) -> bool:

        if not retrieved_docs:
            return False

        try:
            llm = self._get_llm()

            context = "\n".join(retrieved_docs)

            prompt = (
                f"Given the operational query: '{query}', "
                "is the following retrieved manual context relevant "
                "and sufficient to formulate an answer?\n"
                f"Context: {context}\n"
                "Respond ONLY with YES or NO."
            )

            response = llm.invoke(prompt)
            content = response.content

            if isinstance(content, list):
                raw_text = " ".join(
                    item
                    if isinstance(item, str)
                    else item.get("text", str(item))
                    if isinstance(item, dict)
                    else str(item)
                    for item in content
                )
            else:
                raw_text = str(content)

            return raw_text.strip().upper() == "YES"

        except Exception as exc:
            warnings.warn(
                "self_rag_verification: verification call failed "
                f"({type(exc).__name__}: {exc}); "
                "treating as NOT verified rather than silently passing.",
                stacklevel=2,
            )

            return False

    def get_metadata_index(self):
        return {
            key: {
                value: sorted(indices)
                for value, indices in values.items()
            }
            for key, values in self.metadata_index.items()
        }