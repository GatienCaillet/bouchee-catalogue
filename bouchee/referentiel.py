"""Référentiel d'ingrédients : chargement des fichiers YAML et contrôles de cohérence.

Format source : un fichier YAML par famille dans `referentiel/ingredients/`, de la forme

    famille: legumes
    ingredients:
      - id: epinard
        nom: épinard
        parent: legume_feuille
        alias_fr: [épinards]
        alias_en: [spinach]

Champs d'un ingrédient (seuls `id` et `nom` sont obligatoires) :
- id : identifiant canonique, en minuscules ASCII et tirets bas ;
- nom : nom français au singulier ;
- parent : identifiant du parent dans la taxonomie (un seul) ;
- alias_fr, alias_en : autres noms, utilisés par le normaliseur ;
- allergenes : codes parmi les 14 allergènes de l'UE (`referentiel/allergenes.yaml`).
  Ils s'héritent : un ingrédient porte aussi les allergènes de ses parents et de ses composants ;
- composants : identifiants des ingrédients qui le composent (ingrédients composés) ;
- composition_variable : vrai pour un produit industriel dont la recette change selon la marque.
  Ses composants sont alors l'union des composants courants de toutes les marques connues ;
- sensoriel : {amer: 0 à 3, piquant: 0 à 3, odeur_forte: booléen, textures: [...]} ;
- ciqual, foodon : codes des sources ouvertes, à compléter ;
- note : remarque libre (justification d'un allergène, d'une composition).

Un ingrédient qui a des enfants est une catégorie : une ligne de recette résolue vers une
catégorie peut désigner n'importe lequel de ses descendants (voir validateur.py).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import yaml

RACINE = Path(__file__).resolve().parent.parent
DOSSIER_REFERENTIEL = RACINE / "referentiel"

CHAMPS_CONNUS = {
    "id", "nom", "parent", "alias_fr", "alias_en", "allergenes", "composants",
    "composition_variable", "sensoriel", "ciqual", "foodon", "note",
}
TEXTURES = {
    "croquant", "fondant", "filandreux", "gluant", "granuleux", "elastique",
    "cremeux", "fibreux", "farineux", "juteux", "moelleux", "spongieux",
}
FORMAT_ID = re.compile(r"^[a-z][a-z0-9_]*$")


def normaliser_nom(texte: str) -> str:
    """Forme de comparaison d'un nom : minuscules, sans accents, espaces simples."""
    sans_accents = unicodedata.normalize("NFKD", texte)
    sans_accents = "".join(c for c in sans_accents if not unicodedata.combining(c))
    sans_accents = sans_accents.replace("’", "'").replace("œ", "oe").replace("Œ", "oe").replace("æ", "ae").lower()
    return " ".join(sans_accents.split())


@dataclass(frozen=True)
class Probleme:
    niveau: str  # "erreur" ou "avertissement"
    message: str
    fichier: str = ""
    ingredient: str = ""

    def __str__(self) -> str:
        lieu = " ".join(x for x in (self.fichier, self.ingredient and f"[{self.ingredient}]") if x)
        return f"{self.niveau.upper()} {lieu} : {self.message}" if lieu else f"{self.niveau.upper()} : {self.message}"


@dataclass(frozen=True)
class Ingredient:
    id: str
    nom: str
    famille: str
    parent: str | None = None
    alias_fr: tuple[str, ...] = ()
    alias_en: tuple[str, ...] = ()
    allergenes: frozenset[str] = frozenset()
    composants: tuple[str, ...] = ()
    composition_variable: bool = False
    sensoriel: dict[str, Any] = field(default_factory=dict, hash=False, compare=False)
    ciqual: str | None = None
    foodon: str | None = None
    note: str | None = None


@dataclass
class Entree:
    """Ingrédient tel que lu dans un fichier, avant contrôle."""

    fichier: str
    famille: str
    donnees: dict[str, Any]


def charger_allergenes(dossier: Path = DOSSIER_REFERENTIEL) -> dict[str, str]:
    with open(dossier / "allergenes.yaml", encoding="utf-8") as f:
        brut = yaml.safe_load(f)
    return {a["code"]: a["nom"] for a in brut["allergenes"]}


def lire_entrees(dossier: Path = DOSSIER_REFERENTIEL) -> list[Entree]:
    entrees: list[Entree] = []
    for chemin in sorted((dossier / "ingredients").glob("*.yaml")):
        with open(chemin, encoding="utf-8") as f:
            brut = yaml.safe_load(f) or {}
        famille = brut.get("famille", chemin.stem)
        for donnees in brut.get("ingredients") or []:
            entrees.append(Entree(chemin.name, famille, donnees if isinstance(donnees, dict) else {"_invalide": donnees}))
    return entrees


def _liste(valeur: Any) -> list[Any]:
    if valeur is None:
        return []
    return list(valeur) if isinstance(valeur, (list, tuple)) else [valeur]


def _cycles(aretes: dict[str, list[str]]) -> list[list[str]]:
    """Cycles d'un graphe orienté (parcours en profondeur, un cycle signalé par composante)."""
    BLANC, GRIS, NOIR = 0, 1, 2
    couleur = {n: BLANC for n in aretes}
    trouves: list[list[str]] = []

    for depart in aretes:
        if couleur[depart] != BLANC:
            continue
        pile: list[tuple[str, Iterable[str]]] = [(depart, iter(aretes[depart]))]
        chemin = [depart]
        couleur[depart] = GRIS
        while pile:
            noeud, suivants = pile[-1]
            avance = False
            for s in suivants:
                if s not in couleur:
                    continue
                if couleur[s] == GRIS:
                    trouves.append(chemin[chemin.index(s):] + [s])
                elif couleur[s] == BLANC:
                    couleur[s] = GRIS
                    pile.append((s, iter(aretes[s])))
                    chemin.append(s)
                    avance = True
                    break
            if not avance:
                couleur[noeud] = NOIR
                pile.pop()
                chemin.pop()
    return trouves


def verifier_entrees(entrees: list[Entree], allergenes: dict[str, str]) -> list[Probleme]:
    """Tous les contrôles du référentiel. Une erreur bloque la publication."""
    problemes: list[Probleme] = []

    def erreur(e: Entree, message: str) -> None:
        problemes.append(Probleme("erreur", message, e.fichier, str(e.donnees.get("id", ""))))

    def avertissement(e: Entree, message: str) -> None:
        problemes.append(Probleme("avertissement", message, e.fichier, str(e.donnees.get("id", ""))))

    par_id: dict[str, Entree] = {}
    for e in entrees:
        d = e.donnees
        ident = d.get("id")
        if not isinstance(ident, str) or not FORMAT_ID.match(ident):
            erreur(e, f"identifiant absent ou mal formé : {ident!r} (minuscules ASCII et tirets bas)")
            continue
        if ident in par_id:
            erreur(e, f"identifiant en double (déjà dans {par_id[ident].fichier})")
            continue
        par_id[ident] = e
        if not isinstance(d.get("nom"), str) or not d["nom"].strip():
            erreur(e, "nom français absent")
        inconnus = set(d) - CHAMPS_CONNUS
        if inconnus:
            erreur(e, f"champs inconnus : {', '.join(sorted(inconnus))}")

    # Références, allergènes, sensoriel
    for ident, e in par_id.items():
        d = e.donnees
        parent = d.get("parent")
        if parent is not None and parent not in par_id:
            erreur(e, f"parent inconnu : {parent}")
        if parent == ident:
            erreur(e, "est son propre parent")
        for c in _liste(d.get("composants")):
            if c not in par_id:
                erreur(e, f"composant inconnu : {c}")
            if c == ident:
                erreur(e, "est son propre composant")
        for a in _liste(d.get("allergenes")):
            if a not in allergenes:
                erreur(e, f"allergène invalide : {a} (attendus : {', '.join(sorted(allergenes))})")
        variable = d.get("composition_variable", False)
        if not isinstance(variable, bool):
            erreur(e, "composition_variable doit valoir true ou false")
        elif variable and not _liste(d.get("composants")) and not _liste(d.get("allergenes")):
            erreur(e, "composition variable sans composants ni allergènes")
        s = d.get("sensoriel")
        if s is not None:
            if not isinstance(s, dict):
                erreur(e, "sensoriel doit être un dictionnaire")
            else:
                for cle in ("amer", "piquant"):
                    v = s.get(cle)
                    if v is not None and (not isinstance(v, int) or isinstance(v, bool) or not 0 <= v <= 3):
                        erreur(e, f"sensoriel.{cle} doit être un entier de 0 à 3")
                if "odeur_forte" in s and not isinstance(s["odeur_forte"], bool):
                    erreur(e, "sensoriel.odeur_forte doit valoir true ou false")
                for t in _liste(s.get("textures")):
                    if t not in TEXTURES:
                        erreur(e, f"texture inconnue : {t}")
                autres = set(s) - {"amer", "piquant", "odeur_forte", "textures"}
                if autres:
                    erreur(e, f"clés sensorielles inconnues : {', '.join(sorted(autres))}")

    # Cycles : taxonomie, puis taxonomie et composition ensemble
    taxo = {i: [p] if (p := e.donnees.get("parent")) in par_id else [] for i, e in par_id.items()}
    for cycle in _cycles(taxo):
        problemes.append(Probleme("erreur", "cycle dans la taxonomie : " + " -> ".join(cycle)))
    compo = {
        i: [c for c in _liste(e.donnees.get("composants")) if c in par_id] + taxo[i]
        for i, e in par_id.items()
    }
    if not _cycles(taxo):
        for cycle in _cycles(compo):
            problemes.append(Probleme("erreur", "cycle entre composition et taxonomie : " + " -> ".join(cycle)))

    # Noms et alias : chacun ne doit désigner qu'un seul ingrédient
    noms: dict[str, str] = {}
    for ident, e in par_id.items():
        d = e.donnees
        vus: set[str] = set()
        for nom in [d.get("nom")] + _liste(d.get("alias_fr")) + _liste(d.get("alias_en")):
            if not isinstance(nom, str) or not nom.strip():
                erreur(e, f"nom ou alias vide ou invalide : {nom!r}")
                continue
            cle = normaliser_nom(nom)
            if cle in vus:
                continue
            vus.add(cle)
            if cle in noms and noms[cle] != ident:
                erreur(e, f"le nom « {nom} » désigne déjà {noms[cle]}")
            else:
                noms[cle] = ident

    # Avertissement global (un par ingrédient noierait la sortie) : codes CIQUAL à compléter
    sans_ciqual = sum(1 for i, e in par_id.items() if not e.donnees.get("ciqual") and not _a_des_enfants(i, par_id))
    if sans_ciqual:
        problemes.append(Probleme("avertissement", f"{sans_ciqual} ingrédients sans code CIQUAL"))
    return problemes


def _a_des_enfants(ident: str, par_id: dict[str, Entree]) -> bool:
    return any(e.donnees.get("parent") == ident for e in par_id.values())


class ReferentielInvalide(Exception):
    def __init__(self, problemes: list[Probleme]):
        self.problemes = problemes
        super().__init__("\n".join(str(p) for p in problemes))


class Referentiel:
    def __init__(self, ingredients: Iterable[Ingredient], allergenes: dict[str, str]):
        self.ingredients: dict[str, Ingredient] = {i.id: i for i in ingredients}
        self.allergenes = allergenes
        self.enfants: dict[str, list[str]] = {i: [] for i in self.ingredients}
        for ing in self.ingredients.values():
            if ing.parent:
                self.enfants[ing.parent].append(ing.id)

    def __contains__(self, ident: object) -> bool:
        return ident in self.ingredients

    def __getitem__(self, ident: str) -> Ingredient:
        return self.ingredients[ident]

    def __len__(self) -> int:
        return len(self.ingredients)

    def ancetres(self, ident: str) -> list[str]:
        resultat: list[str] = []
        parent = self.ingredients[ident].parent
        while parent and parent not in resultat:
            resultat.append(parent)
            parent = self.ingredients[parent].parent
        return resultat

    def descendants(self, ident: str) -> list[str]:
        resultat: list[str] = []
        a_voir = list(self.enfants[ident])
        while a_voir:
            e = a_voir.pop()
            if e not in resultat:
                resultat.append(e)
                a_voir.extend(self.enfants[e])
        return resultat


def construire(entrees: list[Entree], allergenes: dict[str, str]) -> Referentiel:
    ingredients = []
    for e in entrees:
        d = e.donnees
        ingredients.append(Ingredient(
            id=d["id"],
            nom=d["nom"],
            famille=e.famille,
            parent=d.get("parent"),
            alias_fr=tuple(_liste(d.get("alias_fr"))),
            alias_en=tuple(_liste(d.get("alias_en"))),
            allergenes=frozenset(_liste(d.get("allergenes"))),
            composants=tuple(_liste(d.get("composants"))),
            composition_variable=bool(d.get("composition_variable", False)),
            sensoriel=dict(d.get("sensoriel") or {}),
            ciqual=None if d.get("ciqual") is None else str(d["ciqual"]),
            foodon=d.get("foodon"),
            note=d.get("note"),
        ))
    return Referentiel(ingredients, allergenes)


def charger(dossier: Path = DOSSIER_REFERENTIEL) -> Referentiel:
    """Charge le référentiel ; lève ReferentielInvalide s'il contient la moindre erreur."""
    allergenes = charger_allergenes(dossier)
    entrees = lire_entrees(dossier)
    erreurs = [p for p in verifier_entrees(entrees, allergenes) if p.niveau == "erreur"]
    if erreurs:
        raise ReferentielInvalide(erreurs)
    return construire(entrees, allergenes)
