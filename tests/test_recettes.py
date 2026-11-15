from __future__ import annotations

from collections import defaultdict

import pytest

from bouchee.recettes import RecetteControlee, controler_tout
from bouchee.referentiel import Referentiel, charger
from bouchee.validateur import verifier_recette

DEMO = {"refus": ["parmesan", "poivron"], "allergies": ["arachides"]}


@pytest.fixture(scope="module")
def recettes() -> list[RecetteControlee]:
    return controler_tout()


@pytest.fixture(scope="module")
def ref() -> Referentiel:
    return charger()


def test_au_moins_1000_recettes(recettes: list[RecetteControlee]) -> None:
    assert len(recettes) >= 1000


def test_categories_acceptees_restent_rares(recettes: list[RecetteControlee]) -> None:
    """Les lignes gardées au niveau d'une catégorie (« huile ») sont sûres pour le filtre mais
    imprécises pour la cuisine et la nutrition : elles doivent rester l'exception."""
    lignes = [l for r in recettes for l in r.lignes]
    categories = [l for l in lignes if l.motif == "catégorie acceptée"]
    assert len(categories) / len(lignes) < 0.05


def test_toutes_publiables(recettes: list[RecetteControlee]) -> None:
    """Critère de fin de E : toutes les recettes passent C et D, sans ligne en suspens."""
    problemes = [(r.fichier, r.erreurs, [l.texte for l in r.lignes_a_relire]) for r in recettes if not r.publiable]
    assert problemes == []


def test_au_moins_5_recettes_avec_un_compose(recettes: list[RecetteControlee], ref: Referentiel) -> None:
    avec = [r for r in recettes if any(ref[i].composants for l in r.lignes for i in l.ingredients)]
    assert len(avec) >= 5


def test_parcours_de_decouverte(recettes: list[RecetteControlee]) -> None:
    """Au moins un aliment décliné dans 3 recettes, à au moins 3 niveaux de visibilité différents."""
    niveaux: dict[str, set[int]] = defaultdict(set)
    nombre: dict[str, int] = defaultdict(int)
    for r in recettes:
        d = r.donnees.get("decouverte")
        if d:
            niveaux[d["aliment"]].add(d["niveau"])
            nombre[d["aliment"]] += 1
    assert any(nombre[a] >= 3 and len(niveaux[a]) >= 3 for a in niveaux)


def test_attribution_complete(recettes: list[RecetteControlee]) -> None:
    for r in recettes:
        s = r.donnees["source"]
        assert s["auteurs"] and s["licence"].startswith("CC BY-SA"), r.fichier
        if s["licence"] != "CC BY-SA 4.0 (Bouchée)":  # adaptation : page et révision citées
            assert s["url"].startswith("https://fr.wikibooks.org/") and "oldid=" in s["url"], r.fichier
        p = r.donnees.get("photo")
        if p:
            assert p["url"].startswith("https://commons.wikimedia.org/"), r.fichier


def test_identifiants_uniques(recettes: list[RecetteControlee]) -> None:
    ids = [r.donnees["id"] for r in recettes]
    assert len(ids) == len(set(ids))


def test_demo_de_fin_de_sprint(recettes: list[RecetteControlee], ref: Referentiel) -> None:
    """Profil de démo : aucune recette proposée ne contient parmesan, poivron ou arachide ;
    les recettes au pesto réapparaissent quand on retire le refus du parmesan."""
    au_pesto = {r.donnees["id"] for r in recettes if any("pesto" in l.ingredients for l in r.lignes)}
    assert au_pesto

    compatibles = {r.donnees["id"] for r in recettes if verifier_recette(ref, r.pour_validateur(), DEMO).compatible}
    assert compatibles, "la démo doit proposer des recettes"
    assert not compatibles & au_pesto

    sans_parmesan = {**DEMO, "refus": ["poivron"]}
    compatibles_bis = {r.donnees["id"] for r in recettes if verifier_recette(ref, r.pour_validateur(), sans_parmesan).compatible}
    sans_poivron = {r.donnees["id"] for r in recettes if not any("poivron" in l.ingredients for l in r.lignes)}
    assert au_pesto & sans_poivron <= compatibles_bis
    assert compatibles < compatibles_bis
