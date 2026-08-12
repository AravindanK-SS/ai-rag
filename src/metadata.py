from pathlib import Path


def enrich_metadata(chunks, chunk_type="current"):
    """
    Enrich every chunk with additional metadata.
    """

    for index, chunk in enumerate(chunks, start=1):

        source = chunk.metadata.get("source", "")
        filename = Path(source).name

        chunk.metadata["chunk_id"] = f"{chunk_type}_{index:04d}"

        chunk.metadata["source_file"] = filename

        chunk.metadata["policy_id"] = filename.replace(".pdf", "")

        chunk.metadata["region"] = "GLOBAL"

        chunk.metadata["effective_date"] = chunk.metadata.get(
            "creationdate",
            "Unknown"
        )

        if "section" not in chunk.metadata:
            chunk.metadata["section"] = "Unknown"

    return chunks