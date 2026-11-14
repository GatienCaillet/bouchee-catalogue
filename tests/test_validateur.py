from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from bouchee.referentiel import Referentiel, charger
from bouchee.validateur import SEUIL_CONFIANCE, ProfilInvalide, fermeture, verifier_recette

CAS = json.loads((Path(__file__).parent / "cas" / "validateur.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def ref() -> Referentiel:
    return charger()


def test_seuil_partage() -> None:
    assert CAS["seuil_confiance"] == SEUIL_CONFIANCE


def test_au_moins_25_cas() -> None:
    assert len(CAS["cas"]) >= 25
    ids = [c["id"] for c in CAS["cas"]]
    assert len(ids) == len(set(ids)), "identifiants de cas en double"


def _contient(raisons: list[dict[str, Any]], attendue: dict[str, Any]) -> bool:
    return any(all(r.get(k) == v for k, v in attendue.items()) for r in raisons)


@pytest.mark.parametrize("cas", CAS["cas"], ids=[c["id"] for c in CAS["cas"]])
def test_cas(ref: Referentiel, cas: dict[str, Any]) -> None:
    attendu = cas["attendu"]
    if "erreur" in attendu:
        assert attendu["erreur"] == "profil_invalide"
        with pytest.raises(ProfilInvalide):
            verifier_recette(ref, cas["recette"], cas["profil"])
        return

    resultat = verifier_recette(ref, cas["recette"], cas["profil"])
    raisons = [r.en_dict() for r in resultat.raisons]
    assert resultat.compatible is attendu["compatible"], raisons
    if attendu["compatible"]:
        assert raisons == []
    for r in attendu.get("raisons", []):
        assert _contient(raisons, r), f"raison attendue absente : {r}\nobtenues : {raisons}"


def test_ligne_inconnue_toujours_exclue(ref: Referentiel) -> None:
    """Critère de fin de C : un ingrédient inconnu rend la recette non compatible, quel que soit le profil."""
    recette = {"lignes": [
        {"texte": "riz", "ingredients": ["riz"], "confiance": 1},
        {"texte": "x", "ingredients": ["riz", "ingredient_qui_n_existe_pas"], "confiance": 1},
    ]}
    for profil in ({}, {"refus": ["poivron"]}, {"allergies": ["lait"]}):
        assert not verifier_recette(ref, recette, profil).compatible


def test_chemin_explique_l_exclusion(ref: Referentiel) -> None:
    resultat = verifier_recette(
        ref, {"lignes": [{"ingredients": ["pesto"], "confiance": 1}]}, {"refus": ["parmesan"]}
    )
    (raison,) = resultat.raisons
    assert raison.chemin == ("pesto", "parmesan")


def test_fermeture_remonte_sans_redescendre(ref: Referentiel) -> None:
    f = fermeture(ref, "parmesan")
    assert "fromage" in f and "produit_laitier" in f
    assert "emmental" not in f


def test_fermeture_d_une_categorie_inclut_ses_descendants(ref: Referentiel) -> None:
    f = fermeture(ref, "fruit_de_mer")
    assert {"crevette", "moule", "crustace", "mollusque"} <= set(f)


def test_chaque_allergene_est_atteignable(ref: Referentiel) -> None:
    """Chacun des 14 allergènes est porté par au moins un ingrédient du référentiel."""
    portes = set().union(*(i.allergenes for i in ref.ingredients.values()))
    assert portes == set(ref.allergenes)


@pytest.mark.parametrize("confiance", [True, "1", None, 0.89])
def test_confiances_invalides(ref: Referentiel, confiance: Any) -> None:
    recette = {"lignes": [{"ingredients": ["riz"], "confiance": confiance}]}
    assert not verifier_recette(ref, recette, {}).compatible
