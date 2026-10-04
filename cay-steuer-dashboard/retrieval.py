"""Small, deterministic query helpers shared by document and law retrieval."""
import re
STOP = set('aber alle alles also anhand auch auf aus bei bitte das dass datum deine deinen dem den der des die diese dieser diesen doch ein eine einem einen einer es etwas für habe haben hier ich im in ist kann keine letzten letzte zuletzt mein meine meinen mit nach nicht noch oder ohne sind sie so soll und uns vom von vor war was welche welchen wie wird wurde wurden zu zum zur über bereits erfasst gespeichert daten buchung zahlung betrag nenne sage ausdrücklich falls findest'.split())

def terms(query):
    return {fold(t) for t in re.findall(r'[a-zäöüß]{3,}', query.casefold()) if t not in STOP}

def fold(value):
    return value.casefold().translate(str.maketrans({'ä':'a','ö':'o','ü':'u','ß':'ss'}))

def relevance(query_terms, text):
    words = set(re.findall(r'[a-z]{3,}', fold(text)))
    return sum(any(w == t or (len(t) >= 6 and w.startswith(t[:max(5,len(t)-2)])) for w in words) for t in query_terms)
