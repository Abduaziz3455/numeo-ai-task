import chromadb
from models import KnowledgeBase
from services.gemini_service import GeminiService


class RAGService:
    def __init__(self):
        # ChromaDB saves to local directory ./chroma_db (not a server)
        self.client = chromadb.PersistentClient(
            path="./chroma_db"  # Local directory storage
        )
        self.collection = self.client.get_or_create_collection(
            name="knowledge_base",
            metadata={"description": "Customer support knowledge base"}
        )
        self.gemini_service = GeminiService()

    async def add_knowledge(self, title: str, content: str) -> str:
        """Add knowledge to the vector database and PostgreSQL"""
        try:
            # Get embedding for document storage
            embedding = await self.gemini_service.get_embedding(content)
            
            # Create record in PostgreSQL
            kb_record = await KnowledgeBase.create(
                title=title,
                content=content,
                embedding_id=f"kb_{title.lower().replace(' ', '_')}"
            )
            
            # Add to ChromaDB (local directory storage)
            self.collection.add(
                embeddings=[embedding],
                documents=[content],
                metadatas=[{"title": title, "id": kb_record.id}],
                ids=[str(kb_record.id)]
            )
            
            print(f"Added knowledge '{title}' to local ChromaDB")
            return str(kb_record.id)
        except Exception as e:
            print(f"Error adding knowledge: {e}")
            return None

    async def search_knowledge(self, query: str, n_results: int = 3) -> list:
        """Search for relevant knowledge based on query"""
        try:
            # Get query embedding (optimized for search)
            query_embedding = await self.gemini_service.get_query_embedding(query)
            
            # Search in local ChromaDB
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results
            )
            
            return results['documents'][0] if results['documents'] else []
        except Exception as e:
            print(f"Error searching knowledge: {e}")
            return []

    async def answer_question(self, question: str) -> tuple[str, bool]:
        """
        Answer a question using RAG
        Returns: (answer, can_answer)
        """
        try:
            # Search for relevant knowledge
            relevant_docs = await self.search_knowledge(question)
            
            if not relevant_docs:
                return None, False
            
            # Combine relevant documents
            context = "\n\n".join(relevant_docs)
            
            # Generate answer using Gemini with context
            prompt = f"""
            Based on the following knowledge base information, answer the customer's question.
            If the information provided doesn't contain enough details to answer the question accurately, respond with "INSUFFICIENT_INFO".
            
            Knowledge Base:
            {context}
            
            Customer Question: {question}
            
            Provide a helpful and accurate answer based only on the knowledge base information.
            """
            
            response = await self.gemini_service.generate_response(question, context)
            
            # Check if the response indicates insufficient information
            if "INSUFFICIENT_INFO" in response:
                return None, False
            
            return response, True
            
        except Exception as e:
            print(f"Error answering question: {e}")
            return None, False

    async def load_initial_knowledge(self):
        """Load initial knowledge from files, split into chunks"""
        try:
            # Load from knowledge_base/sample_knowledge.txt if it exists
            with open("knowledge_base/sample_knowledge.txt", "r") as f:
                content = f.read()
                await self.split_and_add_knowledge(content)
                print("Loaded and chunked sample knowledge for testing")
        except FileNotFoundError:
            print("No sample knowledge file found - starting with empty knowledge base")
            pass

    async def split_and_add_knowledge(self, content: str):
        """Split content into chunks and add each as separate knowledge"""
        try:
            # Split by double newlines (sections)
            sections = [section.strip() for section in content.split('\n\n') if section.strip()]
            
            for section in sections:
                lines = section.split('\n')
                if len(lines) >= 2:
                    # First line is the title
                    title = lines[0].strip()
                    # Rest is the content
                    section_content = '\n'.join(lines[1:]).strip()
                    
                    if title and section_content:
                        await self.add_knowledge(title, section_content)
                        print(f"Added knowledge chunk: '{title}'")
                else:
                    # Single line sections, use first few words as title
                    words = section.split()
                    if len(words) > 3:
                        title = ' '.join(words[:3]) + "..."
                        await self.add_knowledge(title, section)
                        print(f"Added knowledge chunk: '{title}'")
                        
        except Exception as e:
            print(f"Error splitting knowledge: {e}")

    async def add_knowledge_from_text(self, title: str, content: str, chunk_size: int = 500):
        """Add knowledge with optional chunking for large content"""
        try:
            # If content is small, add as single chunk
            if len(content) <= chunk_size:
                return await self.add_knowledge(title, content)
            
            # Split large content into smaller chunks
            chunks = self.split_text_into_chunks(content, chunk_size)
            chunk_ids = []
            
            for i, chunk in enumerate(chunks):
                chunk_title = f"{title} (Part {i+1})"
                chunk_id = await self.add_knowledge(chunk_title, chunk)
                if chunk_id:
                    chunk_ids.append(chunk_id)
                    print(f"Added chunk: '{chunk_title}'")
            
            return chunk_ids
            
        except Exception as e:
            print(f"Error adding chunked knowledge: {e}")
            return None

    def split_text_into_chunks(self, text: str, chunk_size: int = 500) -> list:
        """Split text into chunks by sentences/paragraphs"""
        # Split by paragraphs first
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        
        chunks = []
        current_chunk = ""
        
        for paragraph in paragraphs:
            # If adding this paragraph exceeds chunk_size, save current chunk
            if len(current_chunk + "\n\n" + paragraph) > chunk_size and current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = paragraph
            else:
                if current_chunk:
                    current_chunk += "\n\n" + paragraph
                else:
                    current_chunk = paragraph
        
        # Add the last chunk
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks

    def get_collection_info(self) -> dict:
        """Get information about the ChromaDB collection"""
        try:
            count = self.collection.count()
            return {
                "total_documents": count,
                "collection_name": "knowledge_base",
                "storage_path": "./chroma_db",
                "storage_type": "local_directory"
            }
        except Exception as e:
            print(f"Error getting collection info: {e}")
            return {"error": str(e)}