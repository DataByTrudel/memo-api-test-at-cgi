# corpus_post.py
def statutes_prefer_base_sections(results):
    """
    Sorts statutes retrieval results so base numeric sections (e.g., §28)
    are ranked before lettered subsections (e.g., §28A, §28M).
    Keeps original BM25 order within each group.
    """
    def sort_key(r):
        title = r.get("title", "")
        # Extract the bit after '§'
        part = title.split("§")[-1].strip()
        # Any alphabetic char immediately following digits = lettered subsection
        is_lettered = any(ch.isalpha() for ch in part.split()[0])
        # False sorts before True (numeric before lettered)
        return (is_lettered, )

    return sorted(results, key=sort_key)
