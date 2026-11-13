"""Language-drift heuristic for Sofia's turns (Spanish vs English, no dependency).

Counts function words ("stopwords") of each language in a turn. Words that are valid in both
languages ("a", "me", "no", "he", "son", "come", "once", ...) are left out of both lists. A
turn is judged only when it has enough evidence: with fewer than `MIN_HITS` stopwords of
either language (a name, a date, "Vale.", "Perfect, thanks") it is "unknown", never drift.
This is a smoke alarm, not a classifier: mixed sentences are reported as "mixed".
"""

import re
import unicodedata
from dataclasses import dataclass

MIN_HITS = 3  # stopword hits of the winning language needed to call a turn
MIXED_RATIO = 0.34  # the loser has at least this share of the winner's hits: "mixed"


def _words(text: str) -> frozenset[str]:
    return frozenset(text.split())


_ES = _words(
    """
    adios ahora al alli aqui aun bien buenas buenos claro clase clases como con cual cuando
    cuanto cuenta cuentame de del desde dias digame dime dinos disponibilidad disponible
    domingo donde el empezar empiezas entonces entre era eres es esas ese eso esta estabas
    estamos estan estar estas este esto estos estoy experiencia fue genial gracias habia
    hace hacer haces hasta hay hemos hizo hola horario horarios jueves la las le les llamada
    llamando llamo lo los luego lunes manana martes mas menos mi miercoles mis muy noches
    nombre nos nuestro o os para perfecto pero podemos por porque puede pueden puedes puedo
    que quien quiere quieres quiero sabado se semana semanas ser si sin sobre sois somos soy
    su sus tambien tarde tardes te tenemos tengo tiene tienen tienes todavia trabajar
    trabajo tu tus un una unas unos vale viernes y ya
    """
)
_EN = _words(
    """
    a about after afternoon also am an and are as at availability available be because been
    before being but by bye call called calling can class classes could did do does evening
    experience for friday from good goodbye great had has have he hello her here his how i
    if in into is it its just less let may me might monday more morning must my name no not
    now of okay on or our over perfect please said saturday say schedule shall she should so
    start starting still sunday sure tell than thank thanks that the their them then there
    these they this those thursday to today tomorrow tonight tuesday until us very was we
    wednesday week weeks were what when where which while who will with without work working
    would yes you your
    """
)
# Words that are real words in both languages: never evidence for either.
_SHARED = frozenset(
    {"a", "no", "me", "he", "son", "come", "once", "sin", "hay", "mi", "tu", "o", "y", "si"}
)
ES_WORDS = _ES - _SHARED
EN_WORDS = _EN - _SHARED

_TOKEN = re.compile(r"[a-z]+")


def fold(text: str) -> str:
    """Lowercase and strip accents ("adiós" -> "adios")."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


@dataclass(frozen=True)
class Detection:
    lang: str  # "es" | "en" | "mixed" | "unknown"
    es_hits: int
    en_hits: int
    tokens: int

    def drifted(self, expected: str) -> bool:
        """True when the turn is clearly not (only) in the expected language."""
        return self.lang in ("mixed", "en", "es") and self.lang != expected


def detect(text: str) -> Detection:
    tokens = _TOKEN.findall(fold(text))
    es = sum(1 for t in tokens if t in ES_WORDS)
    en = sum(1 for t in tokens if t in EN_WORDS)
    top, low = max(es, en), min(es, en)
    if top < MIN_HITS:
        lang = "unknown"
    elif low >= MIXED_RATIO * top and low >= 2:
        lang = "mixed"
    else:
        lang = "es" if es > en else "en"
    return Detection(lang, es, en, len(tokens))
