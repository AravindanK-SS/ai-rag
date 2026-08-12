import re
from copy import deepcopy
from langchain_core.documents import Document

HEADING_PATTERN = re.compile(
    r'(?im)^('
    r'(?:\d+(?:\.\d+)*)|'            # 1, 1.1, 2.3
    r'(?:[IVXLCDM]+\.)|'             # I. II. III.
    r'(?:CHAPTER\s+\d+)|'            # CHAPTER 1
    r'(?:SECTION\s+\d+)|'            # SECTION 4
    r'(?:ARTICLE\s+\d+)'             # ARTICLE 2
    r').*'
)


def structure_chunker(documents):

    chunks = []
    chunk_counter = 1

    for document in documents:

        text = document.page_content

        matches = list(HEADING_PATTERN.finditer(text))

        if not matches:

            metadata = deepcopy(document.metadata)
            metadata["chunk_id"] = f"structure_{chunk_counter}"

            chunks.append(
                Document(
                    page_content=text,
                    metadata=metadata
                )
            )

            chunk_counter += 1
            continue

        for i, match in enumerate(matches):

            start = match.start()

            end = (
                matches[i + 1].start()
                if i + 1 < len(matches)
                else len(text)
            )

            section = match.group().strip()

            metadata = deepcopy(document.metadata)

            metadata["section"] = section

            metadata["chunk_id"] = f"structure_{chunk_counter}"

            chunks.append(
                Document(
                    page_content=text[start:end].strip(),
                    metadata=metadata
                )
            )

            chunk_counter += 1

    return chunks