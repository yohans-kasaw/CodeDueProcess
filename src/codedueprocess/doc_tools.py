import hashlib
import logging
from datetime import datetime
from pathlib import Path

import chromadb
import pypdf
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import OllamaEmbeddings
from pydantic import BaseModel

from .cache import Cache
from .config import settings

logger = logging.getLogger(__name__)


class RAGLiteChunk(BaseModel):
    id: str
    content: str
    metadata: dict
    source_file: str
    page_number: int
    chunk_index: int


class DocumentTools:
    def __init__(self):
        self.cache = Cache()
        self.embeddings = OllamaEmbeddings(
            model="nomic-embed-text", base_url=settings.LANGCHAIN_ENDPOINT
        )
        self.chroma_client = chromadb.PersistentClient(path="./chroma_db")
        self.collection = self.chroma_client.get_or_create_collection(
            name="codedueprocess_docs", metadata={"hnsw:space": "cosine"}
        )
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000, chunk_overlap=200, separators=["\n\n", "\n", ". ", " ", ""]
        )

    def ingest_pdf(self, pdf_path: str | Path) -> list[RAGLiteChunk]:
        pdf_path = Path(pdf_path)

        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        cache_key = f"pdf_ingest:{pdf_path}:{pdf_path.stat().st_mtime}"
        cached = self.cache.get(cache_key)

        if cached:
            logger.info(f"Using cached PDF ingestion for {pdf_path}")
            return [RAGLiteChunk(**chunk) for chunk in cached]

        logger.info(f"Ingesting PDF: {pdf_path}")
        chunks = []

        with open(pdf_path, "rb") as f:
            reader = pypdf.PdfReader(f)

            for page_num, page in enumerate(reader.pages, 1):
                text = page.extract_text()

                if not text.strip():
                    continue

                doc_chunks = self.text_splitter.split_text(text)

                for chunk_idx, chunk in enumerate(doc_chunks):
                    chunk_id = self._generate_chunk_id(
                        pdf_path.name, page_num, chunk_idx, chunk
                    )

                    rag_chunk = RAGLiteChunk(
                        id=chunk_id,
                        content=chunk,
                        metadata={
                            "source": str(pdf_path),
                            "page": page_num,
                            "total_pages": len(reader.pages),
                            "chunk_index": chunk_idx,
                            "total_chunks": len(doc_chunks),
                            "ingestion_time": datetime.utcnow().isoformat(),
                        },
                        source_file=pdf_path.name,
                        page_number=page_num,
                        chunk_index=chunk_idx,
                    )
                    chunks.append(rag_chunk)

        self.cache.set(cache_key, [chunk.model_dump() for chunk in chunks])
        logger.info(f"Successfully ingested {len(chunks)} chunks from {pdf_path}")

        return chunks

    async def ingest_pdfs_async(
        self, pdf_paths: list[str | Path]
    ) -> dict[str, list[RAGLiteChunk]]:
        results = {}
        for path in pdf_paths:
            chunks = self.ingest_pdf(path)
            results[str(path)] = chunks
        return results

    def _generate_chunk_id(
        self, filename: str, page: int, chunk_idx: int, content: str
    ) -> str:
        content_hash = hashlib.md5(content.encode()).hexdigest()[:8]
        return f"{filename}_p{page}_c{chunk_idx}_{content_hash}"

    def semantic_search(
        self, query: str, top_k: int = 5, score_threshold: float = 0.7
    ) -> list[tuple[RAGLiteChunk, float]]:
        cache_key = f"search:{hashlib.md5(query.encode()).hexdigest()}:{top_k}:{score_threshold}"
        cached = self.cache.get(cache_key)

        if cached:
            logger.info(f"Using cached search results for query: {query[:50]}...")
            return [(RAGLiteChunk(**chunk), score) for chunk, score in cached]

        logger.info(f"Performing semantic search for: {query[:50]}...")

        query_embedding = self.embeddings.embed_query(query)

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k * 2,
            include=["documents", "metadatas", "distances"],
        )

        semantic_results = []

        if results["documents"] and len(results["documents"]) > 0:
            for doc, metadata, distance in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            ):
                similarity = 1 - distance

                if similarity >= score_threshold:
                    chunk = RAGLiteChunk(
                        id=metadata.get("id", ""),
                        content=doc,
                        metadata=metadata,
                        source_file=metadata.get("source", "").split("/")[-1],
                        page_number=metadata.get("page", 0),
                        chunk_index=metadata.get("chunk_index", 0),
                    )
                    semantic_results.append((chunk, similarity))

        semantic_results.sort(key=lambda x: x[1], reverse=True)
        semantic_results = semantic_results[:top_k]

        self.cache.set(
            cache_key,
            [(chunk.model_dump(), score) for chunk, score in semantic_results],
        )

        logger.info(f"Found {len(semantic_results)} relevant chunks")

        return semantic_results

    def index_chunks(self, chunks: list[RAGLiteChunk]) -> list[str]:
        if not chunks:
            logger.warning("No chunks to index")
            return []

        documents = []
        metadatas = []
        ids = []

        for chunk in chunks:
            documents.append(chunk.content)
            metadatas.append(
                {**chunk.metadata, "id": chunk.id, "source_file": chunk.source_file}
            )
            ids.append(chunk.id)

        embeddings = self.embeddings.embed_documents(documents)

        self.collection.add(
            embeddings=embeddings, documents=documents, metadatas=metadatas, ids=ids
        )

        logger.info(f"Indexed {len(chunks)} chunks to ChromaDB")
        return ids

    def clear_index(self):
        try:
            self.chroma_client.delete_collection("codedueprocess_docs")
            self.collection = self.chroma_client.create_collection(
                name="codedueprocess_docs", metadata={"hnsw:space": "cosine"}
            )
            logger.info("Cleared and recreated ChromaDB collection")
        except Exception as e:
            logger.error(f"Error clearing index: {e}")
