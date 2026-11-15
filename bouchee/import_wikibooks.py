"""Import en lot des recettes du *Livre de cuisine* de Wikibooks (fr).

    python -m bouchee.import_wikibooks telecharger <dossier>    # wikitexte des pages, via l'API
    python -m bouchee.import_wikibooks photos <dossier>         # licences des photos, via l'API de Commons
    python -m bouchee.import_wikibooks importer <dossier>       # écrit recettes/*.yaml et un rapport

Règles :
- seules les pages qui ont une section « Ingrédients » et une section « Préparation » sont
  retenues ; les cocktails et les boissons sont écartés (l'app propose des repas) ;
- le balisage wiki est retiré, le texte des lignes et des étapes est gardé tel quel ;
- **une recette n'est écrite que si toutes ses lignes sont résolues automatiquement** par le
  normaliseur, et si le validateur strict l'accepte (règle *fail-closed*, rien n'est deviné).
  Les autres sont listées dans le rapport avec les noms non reconnus, par fréquence, pour
  compléter le référentiel ;
- portions et temps sont lus dans la page quand elle les donne, sinon estimés, et l'estimation
  est écrite dans `source.modifications` ;
- la photo est la première image de la page, gardée seulement si Commons donne une licence libre
  et un auteur, et si son nom de fichier reprend un mot du titre de la recette ;
- la licence de la révision suit la date : CC BY-SA 3.0 avant le 1er juin 2023, 4.0 ensuite.

Une recette déjà présente dans `recettes/` (même identifiant, ou même page source) n'est jamais
écrasée : les recettes relues à la main restent prioritaires.
"""

from __future__ import annotations

import html
import json
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

from bouchee.normaliseur import Normaliseur
from bouchee.recettes import DOSSIER_RECETTES, LICENCES_PHOTO, controler, lire_recettes
from bouchee.referentiel import charger, normaliser_nom

API_WB = "https://fr.wikibooks.org/w/api.php"
API_COMMONS = "https://commons.wikimedia.org/w/api.php"
UA = "bouchee-catalogue-import/0.1 (recipe import script)"
PREFIXE = "Livre de cuisine/"
DATE_CC4 = "2023-06-01"

# Catégories qu'une recette importée peut garder telles quelles (« 2 c. à soupe d'huile ») : le
# validateur vérifie alors toute la famille (fail-closed). Les catégories trop larges pour cuisiner
# (« viande », « légume », « sauce », « assaisonnement ») restent bloquantes.
CATEGORIES_ACCEPTEES = {
    "huile", "levure", "vinaigre", "celeri", "chocolat", "champignon", "moutarde", "creme", "coriandre",
    "bouillon", "jambon", "pates", "chou", "fromage", "herbe_aromatique", "epice", "poisson", "fruit_rouge",
    "fruit_a_coque", "fruit_de_mer", "crustace", "mollusque", "pate_a_tarte", "viande_hachee", "volaille", "porc",
    "agrume", "courge", "salade", "legume_feuille", "fruit_sec", "graine", "confiture", "biscuit", "liqueur",
    "matiere_grasse", "produit_sucrant", "cereale", "allium", "sesame", "algue", "gibier", "poisson_d_eau_douce", "vin",
}
# Lignes qui ne sont pas des ingrédients : ustensiles glissés dans la liste, titres de sous-section
USTENSILES = {
    "saladier", "sauteuse", "torchon", "papier sulfurise", "papier aluminium", "papier d'aluminium", "film alimentaire",
    "casserole", "poele", "moule", "fouet", "ficelle", "ficelle de cuisine", "cure-dents", "pique", "piques",
    "brochettes", "pics a brochette", "cocotte", "plat a gratin", "mixeur", "robot", "four", "cuit-vapeur",
    "poche a douille", "emporte-piece", "rouleau a patisserie", "passoire", "ecumoire", "spatule", "louche",
}
CATEGORIES_EXCLUES = re.compile(r"Cocktail|Boisson|Vodka|Rhum|Whisky|Gin\b|Tequila|Liqueur|Vin chaud|Bière", re.I)
NOMBRES = {"un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "six": 6, "sept": 7, "huit": 8,
           "neuf": 9, "dix": 10, "douze": 12, "quinze": 15, "vingt": 20}


# --- téléchargement --------------------------------------------------------------------------

def _appel(api: str, params: dict[str, Any]) -> dict[str, Any]:
    url = api + "?" + urllib.parse.urlencode({**params, "format": "json", "formatversion": "2"})
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for essai in range(8):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except Exception as e:  # noqa: BLE001 : on réessaie, l'API limite le débit
            print("nouvel essai :", e, file=sys.stderr)
            time.sleep(30 * (essai + 1))
    raise RuntimeError(url)


def telecharger(dossier: Path) -> None:
    dossier.mkdir(parents=True, exist_ok=True)
    fichier = dossier / "pages.json"
    titres: list[str] = []
    suite: dict[str, str] = {}
    while True:
        d = _appel(API_WB, {"action": "query", "list": "allpages", "apprefix": "Livre_de_cuisine/", "apnamespace": 0,
                            "apfilterredir": "nonredirects", "aplimit": 500, **suite})
        titres += [p["title"] for p in d["query"]["allpages"]]
        if "continue" not in d:
            break
        suite = {"apcontinue": d["continue"]["apcontinue"]}
    pages = json.loads(fichier.read_text(encoding="utf-8")) if fichier.exists() else []
    deja = {p["titre"] for p in pages}
    reste = [t for t in titres if t not in deja]
    for i in range(0, len(reste), 20):
        d = _appel(API_WB, {"action": "query", "prop": "revisions|categories", "rvprop": "ids|timestamp|content",
                            "rvslots": "main", "cllimit": "max", "titles": "|".join(reste[i:i + 20])})
        for p in d["query"]["pages"]:
            if "revisions" in p:
                rev = p["revisions"][0]
                pages.append({"titre": p["title"], "revision": rev["revid"], "date": rev["timestamp"][:10],
                              "categories": [c["title"] for c in p.get("categories", [])],
                              "texte": rev["slots"]["main"]["content"]})
        fichier.write_text(json.dumps(pages, ensure_ascii=False), encoding="utf-8")
        time.sleep(4)
    print(f"{len(pages)} pages dans {fichier}")


# --- nettoyage du wikitexte --------------------------------------------------------------------

def _modele_i(m: re.Match[str]) -> str:
    params = [p for p in m.group(1).split("|") if "=" not in p]
    return params[-1] if params else ""


def nettoyer(t: str) -> str:
    t = re.sub(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", "", t, flags=re.S)
    t = re.sub(r"<!--.*?-->", "", t, flags=re.S)
    for _ in range(3):
        t = re.sub(r"\{\{\s*(?:i'?|ingrédient|ingredient|Ustensile|ustensile)\s*\|([^{}]*)\}\}", _modele_i, t)
        t = re.sub(r"\{\{\s*[Uu]nité\s*\|([^{}|]*)\|([^{}|]*)[^{}]*\}\}", r"\1 \2", t)
        t = re.sub(r"\{\{\s*(?:fraction|frac)\s*\|(\d+)\|(\d+)\}\}", r"\1/\2", t)
        t = re.sub(r"\{\{[^{}]*\}\}", "", t)
    t = re.sub(r"\[\[(?:Image|Fichier|File):[^\[\]]*(?:\[\[[^\]]*\]\][^\[\]]*)*\]\]", "", t, flags=re.I)
    t = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", t)
    t = re.sub(r"\[https?://\S+\s*([^\]]*)\]", r"\1", t)
    t = re.sub(r"'{2,}", "", t)
    t = re.sub(r"<[^>]+>", " ", t)
    t = html.unescape(t).replace(" ", " ").replace("’", "'")
    t = re.sub(r"\s+", " ", t).strip()
    return t.strip(" ,;")


def sections(texte: str) -> list[tuple[int, str, str]]:
    """(niveau, titre, contenu) de chaque section."""
    parties = re.split(r"^(={2,})\s*([^=\n]+?)\s*\1\s*$", texte, flags=re.M)
    sortie = [(1, "", parties[0])]
    for i in range(1, len(parties) - 2, 3):
        sortie.append((len(parties[i]), parties[i + 1].strip(), parties[i + 2]))
    return sortie


def _bloc(texte: str, motif: str) -> str | None:
    """Contenu d'une section (avec ses sous-sections) dont le titre commence par le motif."""
    secs = sections(texte)
    for i, (niveau, titre, contenu) in enumerate(secs):
        if re.match(motif, normaliser_nom(titre)):
            morceaux = [contenu]
            for n2, t2, c2 in secs[i + 1:]:
                if n2 <= niveau:
                    break
                morceaux.append(f"\n;{t2}\n{c2}")
            return "\n".join(morceaux)
    return None


def puces(bloc: str) -> list[str]:
    return [nettoyer(m) for m in re.findall(r"^[*#:]+\s*(.+)$", bloc, flags=re.M)]


# --- extraction d'une recette --------------------------------------------------------------------

def slug(titre: str) -> str:
    t = unicodedata.normalize("NFKD", titre.replace("œ", "oe").replace("Œ", "oe").replace("æ", "ae"))
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:70].strip("-")


def _portions(texte: str) -> int | None:
    m = re.search(r"(?:pour|recette pour)\s+(\d+|" + "|".join(NOMBRES) + r")(?:\s*(?:à|-|ou)\s*\d+)?\s+(?:personnes|parts|convives|gourmands|pers\.)",
                  normaliser_nom(nettoyer(texte)))
    if not m:
        m = re.search(r"\b(\d+|" + "|".join(NOMBRES) + r")\s+(?:personnes|parts|convives)\b", normaliser_nom(nettoyer(texte)))
    if not m:
        return None
    v = m.group(1)
    n = int(v) if v.isdigit() else NOMBRES[v]
    return n if 1 <= n <= 24 else None


DUREE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:a\s*\d+\s*)?(h\b|heures?|min\b|mn\b|minutes?)")


DUREES_EN_LETTRES = [
    (r"\bune demi-heure\b|\bune demi heure\b", "30 min"), (r"\bun quart d'heure\b", "15 min"),
    (r"\bune heure et demie\b", "90 min"), (r"\bune heure\b", "1 h"), (r"\bdeux heures\b", "2 h"),
    (r"\btrois heures\b", "3 h"), (r"\bquatre heures\b", "4 h"), (r"\b(?:toute )?la nuit\b|\bune nuit\b", "8 h"),
    (r"\bquelques minutes\b", "5 min"), (r"\bdix minutes\b", "10 min"), (r"\bcinq minutes\b", "5 min"),
    (r"\bvingt minutes\b", "20 min"), (r"\btrente minutes\b", "30 min"), (r"\bquinze minutes\b", "15 min"),
]


def _minutes(phrase: str) -> int:
    for motif, valeur in DUREES_EN_LETTRES:
        phrase = re.sub(motif, valeur, phrase)
    total = 0
    for v, u in DUREE.findall(phrase):
        x = float(v.replace(",", "."))
        total += int(x * 60) if u.startswith("h") else int(x)
    return total


def _temps(etapes: list[str], nb_lignes: int) -> dict[str, int]:
    cuisson = repos = 0
    for e in etapes:
        n = normaliser_nom(e)
        m = _minutes(n)
        if not m:
            continue
        if re.search(r"repos|reposer|mariner|refrigerateur|frigo|au frais|macerer|lever|pousser", n):
            repos += m
        else:
            cuisson += m
    return {"preparation": min(10 + 3 * nb_lignes, 45), "cuisson": min(cuisson, 300), "repos": min(repos, 48 * 60)}


def _premiere_image(texte: str) -> str | None:
    m = re.search(r"\[\[\s*(?:Image|Fichier|File)\s*:\s*([^|\]]+\.(?:jpe?g|png|webp))", texte, flags=re.I)
    return m.group(1).strip().replace("_", " ") if m else None


def extraire(page: dict[str, Any]) -> dict[str, Any] | str:
    """La recette extraite, ou le motif d'exclusion."""
    titre_page = page["titre"]
    if any(CATEGORIES_EXCLUES.search(c) for c in page["categories"]) or "/Boissons" in titre_page:
        return "boisson"
    texte = page["texte"]
    if re.match(r"\s*#(?:REDIRECT|REDIRECTION)", texte, re.I):
        return "redirection"
    bloc_ing = _bloc(texte, r"ingredient")
    bloc_prep = _bloc(texte, r"(preparation|recette|realisation)")
    if not bloc_ing or not bloc_prep:
        return "sans sections Ingrédients et Préparation"
    brutes = [l for l in puces(bloc_ing) if l and len(l) < 160]
    lignes = [l for l in brutes if not l.rstrip().endswith(":") and normaliser_nom(l).strip(" .") not in USTENSILES
              and not re.match(r"^(duree|temps) de (preparation|cuisson)", normaliser_nom(l))]
    retirees = len(brutes) - len(lignes)
    copies = {normaliser_nom(l) for l in lignes}
    etapes = [e for e in puces(bloc_prep) if len(e) > 3 and normaliser_nom(e) not in copies]
    if not etapes:
        etapes = [nettoyer(p) for p in re.split(r"\n\s*\n", bloc_prep) if len(nettoyer(p)) > 20]
    if len(lignes) < 2 or not etapes:
        return "trop peu d'ingrédients ou d'étapes"
    nom = titre_page[len(PREFIXE):].split("/")[-1]
    portions = _portions(bloc_ing) or _portions(texte)
    temps = _temps(etapes, len(lignes))
    estimations = []
    if portions is None:
        portions = 4
        estimations.append("portions estimées à 4")
    estimations.append("temps estimés d'après les étapes")
    if retirees:
        estimations.append(f"{retirees} ligne(s) retirée(s) de la liste (ustensiles, titres de sous-section)")
    url_titre = urllib.parse.quote(titre_page.replace(" ", "_"), safe="/")
    licence = "CC BY-SA 4.0" if page["date"] >= DATE_CC4 else "CC BY-SA 3.0"
    return {
        "id": slug(nom),
        "titre": re.sub(r"\s+(?:variante\s+)?\d+$", "", nom[0].upper() + nom[1:]),  # « Cookies 2 » : page de variante
        "portions": portions,
        "temps": temps,
        "ingredients": lignes,
        "etapes": etapes,
        "_image": _premiere_image(texte),
        "source": {
            "titre": nom,
            "url": f"https://fr.wikibooks.org/w/index.php?title={url_titre}&oldid={page['revision']}",
            "revision": page["revision"],
            "date": page["date"],
            "auteurs": "Contributeurs de Wikibooks",
            "historique": f"https://fr.wikibooks.org/w/index.php?title={url_titre}&action=history",
            "licence": licence,
            "modifications": "Import automatique pour Bouchée : balisage wiki retiré, lignes d'ingrédients résolues "
                             "par le normaliseur sans correction manuelle ; " + ", ".join(estimations) + ".",
        },
    }


# --- photos --------------------------------------------------------------------------------

def photos(dossier: Path) -> None:
    pages = json.loads((dossier / "pages.json").read_text(encoding="utf-8"))
    fichiers = sorted({f for p in pages if isinstance(r := extraire(p), dict) and (f := r["_image"])})
    cache_f = dossier / "photos.json"
    cache: dict[str, Any] = json.loads(cache_f.read_text(encoding="utf-8")) if cache_f.exists() else {}
    reste = [f for f in fichiers if f not in cache]
    for i in range(0, len(reste), 40):
        lot = reste[i:i + 40]
        d = _appel(API_COMMONS, {"action": "query", "prop": "imageinfo", "iiprop": "extmetadata|url",
                                 "titles": "|".join("File:" + f for f in lot)})
        normalises = {n["to"]: n["from"] for n in d["query"].get("normalized", [])}
        for p in d["query"]["pages"]:
            demande = normalises.get(p["title"], p["title"])[5:]
            info = (p.get("imageinfo") or [{}])[0]
            meta = info.get("extmetadata") or {}
            cache[demande.replace("_", " ")] = {
                "licence": (meta.get("LicenseShortName") or {}).get("value"),
                "auteur": nettoyer((meta.get("Artist") or {}).get("value") or ""),
                "page": info.get("descriptionurl"),
            }
        cache_f.write_text(json.dumps(cache, ensure_ascii=False, indent=0), encoding="utf-8")
        time.sleep(2)
    print(f"{len(cache)} photos décrites dans {cache_f}")


def _mots(texte: str) -> set[str]:
    return {m[:-1] if m.endswith(("s", "x")) else m for m in re.findall(r"[a-z]{4,}", normaliser_nom(texte))}


def _photo(fichier: str | None, cache: dict[str, Any], titre: str = "") -> dict[str, str] | None:
    """La première image de la page, si sa licence est libre et si son nom de fichier reprend un
    mot du titre : la première image d'une page n'est pas toujours le plat (boisson, ustensile)."""
    if titre and fichier and not (_mots(fichier.rsplit(".", 1)[0]) & _mots(titre)):
        return None
    info = cache.get(fichier or "")
    if not info or not info.get("licence") or not info.get("auteur") or not info.get("page"):
        return None
    licence = info["licence"].replace("Public domain", "Domaine public")
    if not LICENCES_PHOTO.match(licence) or len(info["auteur"]) > 120:
        return None
    return {"fichier": fichier, "auteur": info["auteur"], "licence": licence, "url": info["page"],
            "verification": "licence et auteur lus par l'API de Wikimedia Commons ; image de la page source de la recette"}


# --- import ------------------------------------------------------------------------------------

def importer(dossier: Path, ecrire: bool = True) -> None:
    pages = json.loads((dossier / "pages.json").read_text(encoding="utf-8"))
    cache_f = dossier / "photos.json"
    cache = json.loads(cache_f.read_text(encoding="utf-8")) if cache_f.exists() else {}
    ref = charger()
    n = Normaliseur(ref)
    existantes = lire_recettes()
    ids = {d.get("id") for _, d in existantes}
    pages_connues = {urllib.parse.unquote(str((d.get("source") or {}).get("url", ""))).split("title=")[-1].split("&")[0].replace("_", " ")
                     for _, d in existantes}
    motifs: Counter[str] = Counter()
    inconnus: Counter[str] = Counter()
    bloquees: list[tuple[int, str, list[str]]] = []
    ecrites = 0
    for page in sorted(pages, key=lambda p: p["titre"]):
        r = extraire(page)
        if isinstance(r, str):
            motifs[r] += 1
            continue
        if page["titre"] in pages_connues:
            motifs["déjà adaptée à la main"] += 1
            continue
        if not r["id"] or r["id"] in ids:
            motifs["identifiant déjà pris"] += 1
            continue
        image = r.pop("_image")
        photo = _photo(image, cache, r["titre"])
        if photo:
            r["photo"] = photo
        controlee = controler(f"{r['id']}.yaml", r, n, ref)
        if not controlee.erreurs and controlee.lignes_a_relire and all(
            l.ingredients and l.motif and l.motif.startswith("catégorie trop générale")
            and all(i in CATEGORIES_ACCEPTEES or not n.est_generique(i) for i in l.ingredients)
            for l in controlee.lignes_a_relire
        ):
            a_garder = {l.texte for l in controlee.lignes_a_relire}
            r["ingredients"] = [
                {"texte": t, "ingredients": next(l.ingredients for l in controlee.lignes if l.texte == t), "categorie": True}
                if t in a_garder else t for t in r["ingredients"]
            ]
            r["source"]["modifications"] = r["source"]["modifications"][:-1] + (
                " ; catégories gardées telles quelles : " + ", ".join(sorted({ref[i].nom for l in controlee.lignes_a_relire for i in l.ingredients})) + "."
            )
            controlee = controler(f"{r['id']}.yaml", r, n, ref)
        if not controlee.publiable:
            a_relire = [l for l in controlee.lignes_a_relire]
            for l in a_relire:
                inconnus[normaliser_nom(l.nom or l.texte)] += 1
            motifs["lignes non résolues" if a_relire else "refusée au contrôle"] += 1
            bloquees.append((len(a_relire), page["titre"], [l.texte for l in a_relire] or controlee.erreurs))
            continue
        ids.add(r["id"])
        ecrites += 1
        if ecrire:
            chemin = DOSSIER_RECETTES / f"{r['id']}.yaml"
            chemin.write_text(yaml.safe_dump(r, allow_unicode=True, sort_keys=False, width=110), encoding="utf-8")
    rapport = [f"{ecrites} recettes importées", "", "Pages écartées :"]
    rapport += [f"  {v:5d}  {k}" for k, v in motifs.most_common()]
    rapport += ["", "Noms non reconnus, par fréquence :"] + [f"  {v:4d}  {k}" for k, v in inconnus.most_common()]
    rapport += ["", "Recettes bloquées (nombre de lignes à relire) :"]
    rapport += [f"  {k:2d}  {t} : {' | '.join(l)}" for k, t, l in sorted(bloquees)]
    (dossier / "rapport.txt").write_text("\n".join(rapport), encoding="utf-8")
    print(f"{ecrites} recettes importées ; rapport dans {dossier / 'rapport.txt'}")


def main() -> int:
    if len(sys.argv) != 3 or sys.argv[1] not in ("telecharger", "photos", "importer", "essai"):
        print(__doc__)
        return 2
    dossier = Path(sys.argv[2])
    {"telecharger": telecharger, "photos": photos, "importer": importer,
     "essai": lambda d: importer(d, ecrire=False)}[sys.argv[1]](dossier)
    return 0


if __name__ == "__main__":
    sys.exit(main())
