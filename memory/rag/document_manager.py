from pathlib import Path


class RAGDocumentManager:
    def __init__(self, rag_pipeline):
        self.rag_pipeline = rag_pipeline

    def add_document(self, file_path: str):
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(
                f"Document not found: {file_path}"
            )

        if not path.is_file():
            raise ValueError(
                f"Path is not a file: {file_path}"
            )

        self.rag_pipeline.file_path = str(path)
        self.rag_pipeline._initialize_pipeline()

        return {
            "status": "added",
            "file": path.name,
        }

    def remove_document(self, file_path: str):
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(
                f"Document not found: {file_path}"
            )

        if str(path.resolve()) != str(
            Path(self.rag_pipeline.file_path).resolve()
        ):
            raise ValueError(
                "The requested document is not the active RAG document."
            )

        if self.rag_pipeline.vector_store is not None:
            self.rag_pipeline.vector_store.delete_collection()

        self.rag_pipeline.vector_store = None
        self.rag_pipeline.documents_cache = []
        self.rag_pipeline.metadata_cache = []
        self.rag_pipeline.metadata_index = {}
        self.rag_pipeline.bm25_index = None

        return {
            "status": "removed",
            "file": path.name,
        }

    def refresh(self):
        self.rag_pipeline._initialize_pipeline()

        return {
            "status": "refreshed",
            "file": Path(
                self.rag_pipeline.file_path
            ).name,
        }
