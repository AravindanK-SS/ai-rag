from src.loader import load_documents
from chunkers.current_chunker import current_chunker
from chunkers.structure_chunker import structure_chunker
from src.embedding import get_embedding_model
from src.vectordb import create_vectorstore
from src.metadata import enrich_metadata

# ==========================================
# Step 1: Load Documents
# ==========================================
print("\nLoading Documents...\n")

documents = load_documents()

# ==========================================
# Step 2: Create Chunks
# ==========================================
print("\nCreating Chunks...\n")

current_chunks = current_chunker(documents)
structure_chunks = structure_chunker(documents)

print(f"Current Chunks   : {len(current_chunks)}")
print(f"Structure Chunks : {len(structure_chunks)}")

# ==========================================
# Step 3: Enrich Metadata
# ==========================================
print("\nEnriching Metadata...\n")

current_chunks = enrich_metadata(
    current_chunks,
    chunk_type="current"
)

structure_chunks = enrich_metadata(
    structure_chunks,
    chunk_type="structure"
)

# Verify metadata
print("Sample Metadata:\n")
print(current_chunks[0].metadata)

# ==========================================
# Step 4: Load Embedding Model
# ==========================================
print("\nLoading Embedding Model...\n")

embedding_model = get_embedding_model()

# ==========================================
# Step 5: Create Vector Databases
# ==========================================
print("\nCreating Current Vector Database...\n")

create_vectorstore(
    current_chunks,
    embedding_model,
    "vectorstore/current"
)

print("✅ Current Vector Database Created")

print("\nCreating Structure Vector Database...\n")

create_vectorstore(
    structure_chunks,
    embedding_model,
    "vectorstore/structure"
)

print("✅ Structure Vector Database Created")

print("\n🎉 Both Vector Databases Created Successfully!")