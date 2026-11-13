"""Text a model claims to cite is checked in code (citations.py): quotes shown as someone's
words must be theirs."""

from hr_screener.citations import verified_quotes

TURN = "Matemáticas, también te lo dije. ¿Esto va a tardar mucho? Tengo prisa."


def test_only_quotes_found_in_the_source_are_kept():
    quotes = [
        "matematicas tambien te lo dije",  # case, accents and punctuation may differ
        "Matemáticas… tengo prisa",  # an ellipsis marks an omission
        "Tengo prisa… Matemáticas",  # out of order
        "Estoy harta de esta llamada",  # invented
        "también te lo dijo",  # a changed word
    ]
    assert verified_quotes(quotes, [TURN]) == quotes[:2]
