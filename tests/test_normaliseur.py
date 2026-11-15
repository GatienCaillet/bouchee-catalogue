from __future__ import annotations

from typing import Any

import pytest

from bouchee.normaliseur import Normaliseur
from bouchee.referentiel import charger
from bouchee.validateur import SEUIL_CONFIANCE


@pytest.fixture(scope="module")
def n() -> Normaliseur:
    return Normaliseur(charger())


# texte, quantité, quantité max, unité, ingrédients attendus
# Depuis l'extension du référentiel, une ligne précise se résout vers l'enfant le plus précis
# (« pavé de saumon » plutôt que « saumon ») : il hérite des allergènes et du refus de son parent.
RESOLUES: list[tuple[str, Any, Any, Any, list[str]]] = [
    ("2 c. à soupe de pesto maison", 2, None, "c. à soupe", ["pesto"]),
    ("1 gousse d'ail", 1, None, "gousse", ["ail"]),
    ("2-3 gousses d'ail", 2, 3, "gousse", ["ail"]),
    ("sel, poivre", None, None, None, ["sel", "poivre"]),
    ("Sel et poivre du moulin", None, None, None, ["sel", "poivre_noir"]),
    ("200g de lardons fumés", 200, None, "g", ["lardon"]),
    ("3 œufs", 3, None, None, ["oeuf"]),
    ("un oeuf battu", 1, None, None, ["oeuf"]),
    ("1 boîte de tomates concassées (400 g)", 1, None, "boîte", ["sauce_tomate"]),
    ("1 noix de beurre", 1, None, "noix", ["beurre"]),
    ("50 g de noix de cajou", 50, None, "g", ["noix_de_cajou"]),
    ("100 g de cerneaux de noix", 100, None, "g", ["cerneau_de_noix"]),
    ("1 pincée de noix de muscade", 1, None, "pincée", ["muscade"]),
    ("2 à 3 carottes", 2, 3, None, ["carotte"]),
    ("1 1/2 l de lait", 1.5, None, "l", ["lait"]),
    ("1 et demi verre de lait", 1.5, None, "verre", ["lait"]),
    ("½ botte de persil plat, ciselé", 0.5, None, "botte", ["persil_plat"]),
    ("1 oignon, émincé", 1, None, None, ["oignon"]),
    ("beurre ou margarine", None, None, None, ["beurre", "margarine"]),
    ("un peu d'huile d'olive", None, None, "un peu", ["huile_d_olive"]),
    ("quelques feuilles de basilic", None, None, "quelques", ["basilic"]),
    ("3 poireaux", 3, None, None, ["poireau"]),
    ("250 g de champignons de Paris, émincés", 250, None, "g", ["champignon_de_paris"]),
    ("1 cube de bouillon de volaille", 1, None, None, ["bouillon_de_volaille"]),
    ("10 cl de crème liquide", 10, None, "cl", ["creme_liquide"]),
    ("1 c. à café de cumin en poudre", 1, None, "c. à café", ["cumin"]),
    ("2 petites courgettes", 2, None, None, ["courgette"]),
    ("huile d'olive pour la cuisson", None, None, None, ["huile_d_olive"]),
    ("1 kg de moules", 1, None, "kg", ["moule"]),
    ("100 g de parmesan râpé", 100, None, "g", ["parmesan"]),
    ("6 feuilles de lasagnes", 6, None, "feuille", ["pates_aux_oeufs"]),
    ("400 g de pois chiches égouttés", 400, None, "g", ["pois_chiche_en_boite"]),
    ("500 g d'échine de porc", 500, None, "g", ["echine_de_porc"]),
    ("3 tranches de pain de mie", 3, None, "tranche", ["pain_de_mie"]),
    ("3 oignons verts", 3, None, None, ["oignon_nouveau"]),  # pas « oignon » : la couleur compte ici
    ("2 ou 3 œufs", 2, 3, None, ["oeuf"]),
    ("300 g. de pavé de saumon frais", 300, None, "g", ["pave_de_saumon"]),
    ("1 cuiller à café de coriandre en poudre", 1, None, "c. à café", ["coriandre_graine"]),
    ("150 g de haricots blancs secs", 150, None, "g", ["haricot_blanc"]),
    ("Sel - poivre", None, None, None, ["sel", "poivre"]),
    ("2 grandes boîtes de haricots rouges", 2, None, "boîte", ["haricot_rouge"]),
    ("Sel, poivre noir, 3 g de paprika", None, None, None, ["sel", "poivre_noir", "paprika"]),
    ("le jus d'un citron", None, None, None, ["jus_de_citron"]),
    ("1/4 de litre de lait", 0.25, None, "l", ["lait"]),
    ("[1/2 c. à thé] de sel", 0.5, None, "c. à café", ["sel"]),
    ("sel & poivre", None, None, None, ["sel", "poivre"]),
    ("200 g de pruneaux dénoyautés", 200, None, "g", ["pruneau"]),
]


@pytest.mark.parametrize("texte,quantite,quantite_max,unite,ingredients", RESOLUES, ids=[r[0] for r in RESOLUES])
def test_lignes_resolues(n: Normaliseur, texte: str, quantite: Any, quantite_max: Any, unite: Any, ingredients: list[str]) -> None:
    r = n.normaliser(texte)
    assert r.statut == "resolue", r.motif
    assert r.ingredients == ingredients
    assert r.quantite == quantite
    assert r.quantite_max == quantite_max
    if unite is not None:
        assert r.unite == unite
    assert r.confiance >= SEUIL_CONFIANCE


A_RELIRE = [
    "un trait de sauce maison",  # catégorie trop générale
    "2 c. à soupe d'huile",  # quelle huile ?
    "2 c. à soupe de crème",  # fraîche ou liquide ?
    "400 g de fruits de mer",
    "1 kg de porc",
    "4 tranches de jambon",  # cuit ou cru ?
    "1 bouquet de coriandre",  # feuilles ou graines ?
    "2 jaunes",
    "Pour la sauce :",
    "1 pitaya",
    "",
]


@pytest.mark.parametrize("texte", A_RELIRE)
def test_lignes_a_relire(n: Normaliseur, texte: str) -> None:
    r = n.normaliser(texte)
    assert r.statut == "a_relire"
    assert r.motif
    assert r.confiance < SEUIL_CONFIANCE


def test_jamais_de_resolution_partielle(n: Normaliseur) -> None:
    """Un mot inconnu dans une ligne à plusieurs ingrédients bloque toute la ligne."""
    r = n.normaliser("sel, poivre, dragée")
    assert r.statut == "a_relire" and r.ingredients == []


def test_facultatif(n: Normaliseur) -> None:
    assert n.normaliser("Coriandre fraîche (facultatif)").facultatif
    assert not n.normaliser("Coriandre fraîche").facultatif


def test_poivre_n_est_pas_poivron(n: Normaliseur) -> None:
    assert n.normaliser("1 poivron rouge").ingredients == ["poivron"]
    assert n.normaliser("poivre").ingredients == ["poivre"]
