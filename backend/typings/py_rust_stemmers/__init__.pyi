"""Type the stemmer API used by workshop search."""

class SnowballStemmer:
    """Stem words using the selected language."""

    def __init__(self, lang: str) -> None:
        """Select the stemming language."""
        ...

    def stem_word(self, /, input: str) -> str:
        """Return the stem of one word."""
        ...
