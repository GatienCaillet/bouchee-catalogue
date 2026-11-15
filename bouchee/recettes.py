"""Recettes sources : chargement, contrôle, normalisation des lignes (chaîne C + D).

Format : un fichier YAML par recette dans `recettes/`, nommé d'après son identifiant.

    id: epinards-a-la-creme
    titre: Épinards à la crème
    portions: 4
    temps: {preparation: 15, cuisson: 20}        # minutes
    ingredients:
      - 800 g d'épinards frais                    # ligne normalisée automatiquement
      - texte: 1 c. à soupe de crème              # ligne résolue à la main, après relecture
        ingredients: [creme_fraiche]
      - texte: 2 c. à soupe d'huile               # catégorie gardée telle quelle (import en lot) :
        ingredients: [huile]                      # le validateur vérifie toutes les huiles
        categorie: true
    etapes: [...]
    decouverte:                                   # facultatif : recette d'un parcours « Nouvel aliment »
      aliment: epinard
      niveau: 4                                   # 1 fondu, 2 discret, 3 identifiable, 4 accompagnement, 5 vedette
      pourquoi: La crème adoucit le goût de l'épinard.
      conseil: Bien presser les épinards pour éviter le côté aqueux.
    photo: {fichier, auteur, licence, url}        # facultatif ; Wikimedia Commons, licence vérifiée
    source: {titre, url, revision, date, auteurs, historique, licence, modifications}

Une recette est publiable si toutes ses lignes sont résolues (automatiquement avec une
confiance suffisante, ou à la main) et si le validateur strict l'accepte pour un profil vide.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from bouchee.normaliseur import LigneNormalisee, Normaliseur
from bouchee.referentiel import RACINE, Referentiel, charger
from bouchee.validateur import verifier_recette

DOSSIER_RECETTES = RACINE / "recettes"
LICENCES_PHOTO = re.compile(r"^(CC0|Public domain|Domaine public|PD.*|CC BY(-SA)? \d\.\d.*)$", re.I)
LICENCES_SOURCE = {"CC BY-SA 3.0", "CC BY-SA 4.0", "CC BY-SA 4.0 (Bouchée)"}
FORMAT_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
NIVEAUX = {1: "fondu", 2: "discret", 3: "identifiable", 4: "accompagnement", 5: "vedette"}


@dataclass
class RecetteControlee:
    fichier: str
    donnees: dict[str, Any]
    lignes: list[LigneNormalisee] = field(default_factory=list)
    erreurs: list[str] = field(default_factory=list)

    @property
    def lignes_a_relire(self) -> list[LigneNormalisee]:
        return [l for l in self.lignes if l.statut != "resolue"]

    @property
    def publiable(self) -> bool:
        return not self.erreurs and not self.lignes_a_relire

    def pour_validateur(self) -> dict[str, Any]:
        return {"lignes": [{"texte": l.texte, "ingredients": l.ingredients, "confiance": l.confiance} for l in self.lignes]}


def lire_recettes(dossier: Path = DOSSIER_RECETTES) -> list[tuple[str, dict[str, Any]]]:
    recettes = []
    for chemin in sorted(dossier.glob("*.yaml")):
        with open(chemin, encoding="utf-8") as f:
            recettes.append((chemin.name, yaml.safe_load(f) or {}))
    return recettes


def _normaliser_ligne(ligne: Any, n: Normaliseur, ref: Referentiel) -> tuple[LigneNormalisee, str | None]:
    if isinstance(ligne, str):
        return n.normaliser(ligne), None
    if isinstance(ligne, dict) and isinstance(ligne.get("texte"), str):
        ids = ligne.get("ingredients")
        if not ids:  # dictionnaire sans résolution : simple précision (facultatif, note)
            resultat = n.normaliser(ligne["texte"])
        else:
            inconnus = [i for i in ids if i not in ref]
            if inconnus:
                return LigneNormalisee(texte=ligne["texte"], motif="résolution manuelle invalide"), (
                    f"ligne « {ligne['texte']} » : identifiants inconnus {inconnus}"
                )
            auto = n.normaliser(ligne["texte"])
            motif = "catégorie acceptée" if ligne.get("categorie") else "résolue à la relecture"
            resultat = LigneNormalisee(
                texte=ligne["texte"], quantite=auto.quantite, quantite_max=auto.quantite_max, unite=auto.unite,
                nom=auto.nom, ingredients=list(ids), confiance=1.0, statut="resolue", motif=motif,
            )
        resultat.facultatif = resultat.facultatif or bool(ligne.get("facultatif"))
        return resultat, None
    return LigneNormalisee(texte=str(ligne), motif="ligne illisible"), f"ligne illisible : {ligne!r}"


def controler(fichier: str, d: dict[str, Any], n: Normaliseur, ref: Referentiel) -> RecetteControlee:
    r = RecetteControlee(fichier, d)
    e = r.erreurs

    ident = d.get("id")
    if not isinstance(ident, str) or not FORMAT_ID.match(ident):
        e.append(f"identifiant mal formé : {ident!r}")
    elif fichier != f"{ident}.yaml":
        e.append(f"le fichier devrait s'appeler {ident}.yaml")
    if not isinstance(d.get("titre"), str) or not d["titre"].strip():
        e.append("titre absent")
    if not isinstance(d.get("portions"), int) or d["portions"] < 1:
        e.append("portions : entier positif attendu")
    temps = d.get("temps")
    if not isinstance(temps, dict) or not all(isinstance(temps.get(k, 0), int) for k in ("preparation", "cuisson", "repos")):
        e.append("temps : {preparation, cuisson, repos} en minutes")
    if not d.get("etapes") or not all(isinstance(x, str) and x.strip() for x in d["etapes"]):
        e.append("etapes : liste de phrases attendue")

    for ligne in d.get("ingredients") or []:
        resultat, erreur = _normaliser_ligne(ligne, n, ref)
        r.lignes.append(resultat)
        if erreur:
            e.append(erreur)
    if not r.lignes:
        e.append("aucune ligne d'ingrédient")

    source = d.get("source") or {}
    for cle in ("titre", "url", "auteurs", "licence", "modifications"):
        if not source.get(cle):
            e.append(f"source.{cle} absent (attribution obligatoire)")
    if source.get("licence") and source["licence"] not in LICENCES_SOURCE:
        e.append(f"source.licence inattendue : {source['licence']}")

    photo = d.get("photo")  # facultative : l'app affiche une illustration par défaut
    if photo is not None and not isinstance(photo, dict):
        e.append("photo : dictionnaire {fichier, auteur, licence, url} attendu")
        photo = {}
    photo = photo or {}
    for cle in ("fichier", "auteur", "licence", "url"):
        if photo and not photo.get(cle):
            e.append(f"photo.{cle} absent")
    if photo.get("licence") and not LICENCES_PHOTO.match(str(photo["licence"])):
        e.append(f"photo.licence non libre ou inconnue : {photo['licence']}")

    decouverte = d.get("decouverte")
    if decouverte is not None:
        aliment, niveau = decouverte.get("aliment"), decouverte.get("niveau")
        if aliment not in ref:
            e.append(f"decouverte.aliment inconnu : {aliment}")
        elif not any(aliment in l.ingredients for l in r.lignes):
            e.append(f"decouverte.aliment {aliment} absent des ingrédients")
        if niveau not in NIVEAUX:
            e.append("decouverte.niveau : entier de 1 à 5")
        if not decouverte.get("pourquoi"):
            e.append("decouverte.pourquoi absent (note « Pourquoi ici ? »)")

    if not e and not r.lignes_a_relire:
        verdict = verifier_recette(ref, r.pour_validateur(), {})
        if not verdict.compatible:
            e.append("refusée par le validateur strict : " + ", ".join(x.type for x in verdict.raisons))
    return r


def controler_tout(dossier: Path = DOSSIER_RECETTES) -> list[RecetteControlee]:
    ref = charger()
    n = Normaliseur(ref)
    return [controler(f, d, n, ref) for f, d in lire_recettes(dossier)]


def main() -> int:
    recettes = controler_tout()
    total_lignes = sum(len(r.lignes) for r in recettes)
    auto = sum(1 for r in recettes for l in r.lignes if l.statut == "resolue" and l.motif not in ("résolue à la relecture", "catégorie acceptée"))
    manuelles = sum(1 for r in recettes for l in r.lignes if l.motif == "résolue à la relecture")
    categories = sum(1 for r in recettes for l in r.lignes if l.motif == "catégorie acceptée")
    for r in recettes:
        for err in r.erreurs:
            print(f"ERREUR {r.fichier} : {err}")
        for l in r.lignes_a_relire:
            print(f"À RELIRE {r.fichier} : « {l.texte} » ({l.motif})")
    a_relire = sum(len(r.lignes_a_relire) for r in recettes)
    publiables = sum(1 for r in recettes if r.publiable)
    print(
        f"\n{len(recettes)} recettes, {publiables} publiables ; {total_lignes} lignes : "
        f"{auto} résolues automatiquement, {manuelles} résolues à la relecture, {categories} catégories acceptées, "
        f"{a_relire} à relire"
    )
    return 0 if publiables == len(recettes) else 1


if __name__ == "__main__":
    sys.exit(main())
