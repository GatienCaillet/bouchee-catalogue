from __future__ import annotations

from typing import Any

import pytest

from bouchee.referentiel import (
    Entree,
    charger,
    charger_allergenes,
    charger_codes_ciqual,
    lire_entrees,
    normaliser_nom,
    verifier_entrees,
)

ALLERGENES = charger_allergenes()


def erreurs(*ingredients: dict[str, Any]) -> list[str]:
    entrees = [Entree("test.yaml", "test", d) for d in ingredients]
    return [p.message for p in verifier_entrees(entrees, ALLERGENES) if p.niveau == "erreur"]


def test_referentiel_reel_sans_erreur() -> None:
    probs = [p for p in verifier_entrees(lire_entrees(), ALLERGENES, charger_codes_ciqual()) if p.niveau == "erreur"]
    assert probs == [], "\n".join(map(str, probs))


def test_referentiel_reel_se_charge() -> None:
    ref = charger()
    assert len(ref) >= 200
    assert len(ALLERGENES) == 14


def test_ingredients_composes_demandes_par_le_sprint() -> None:
    ref = charger()
    for ident in ("pesto", "bouillon_de_volaille", "sauce_worcestershire", "pate_feuilletee", "mayonnaise", "sauce_soja"):
        assert ref[ident].composants, ident
    assert sum(1 for i in ref.ingredients.values() if i.composants) >= 10


def test_ingredient_valide() -> None:
    assert erreurs({"id": "a", "nom": "a"}, {"id": "b", "nom": "b", "parent": "a", "allergenes": ["lait"]}) == []


def test_parent_inconnu() -> None:
    assert any("parent inconnu" in m for m in erreurs({"id": "a", "nom": "a", "parent": "zzz"}))


def test_composant_inconnu() -> None:
    assert any("composant inconnu" in m for m in erreurs({"id": "a", "nom": "a", "composants": ["zzz"]}))


def test_allergene_invalide() -> None:
    assert any("allergène invalide" in m for m in erreurs({"id": "a", "nom": "a", "allergenes": ["kiwi"]}))


def test_cycle_taxonomie() -> None:
    msgs = erreurs(
        {"id": "a", "nom": "a", "parent": "c"},
        {"id": "b", "nom": "b", "parent": "a"},
        {"id": "c", "nom": "c", "parent": "b"},
    )
    assert any("cycle dans la taxonomie" in m for m in msgs)


def test_cycle_composition() -> None:
    msgs = erreurs(
        {"id": "a", "nom": "a", "composants": ["b"]},
        {"id": "b", "nom": "b", "composants": ["a"]},
    )
    assert any("cycle entre composition" in m for m in msgs)


def test_auto_parent() -> None:
    assert any("son propre parent" in m for m in erreurs({"id": "a", "nom": "a", "parent": "a"}))


def test_identifiant_double() -> None:
    assert any("en double" in m for m in erreurs({"id": "a", "nom": "a"}, {"id": "a", "nom": "b"}))


def test_identifiant_mal_forme() -> None:
    assert any("mal formé" in m for m in erreurs({"id": "Épinard", "nom": "épinard"}))


def test_alias_ambigu() -> None:
    msgs = erreurs(
        {"id": "creme_fraiche", "nom": "crème fraîche", "alias_fr": ["crème"]},
        {"id": "creme_liquide", "nom": "crème liquide", "alias_fr": ["Creme"]},
    )
    assert any("désigne déjà" in m for m in msgs)


def test_champ_inconnu() -> None:
    assert any("champs inconnus" in m for m in erreurs({"id": "a", "nom": "a", "alergenes": ["lait"]}))


def test_composition_variable_vide() -> None:
    assert any("composition variable" in m for m in erreurs({"id": "a", "nom": "a", "composition_variable": True}))


@pytest.mark.parametrize("sensoriel", [{"amer": 4}, {"piquant": -1}, {"odeur_forte": "oui"}, {"textures": ["mou"]}, {"sucre": 1}])
def test_sensoriel_invalide(sensoriel: dict[str, Any]) -> None:
    assert erreurs({"id": "a", "nom": "a", "sensoriel": sensoriel})


def test_normaliser_nom() -> None:
    assert normaliser_nom("  Œufs  Brouillés ") == "oeufs brouilles"
    assert normaliser_nom("pâtes") == normaliser_nom("PATES")


def test_code_ciqual_inconnu() -> None:
    entrees = [Entree("test.yaml", "test", {"id": "a", "nom": "a", "ciqual": 99999999})]
    msgs = [p.message for p in verifier_entrees(entrees, ALLERGENES, {"20059": "Épinard, cru"})]
    assert any("CIQUAL inconnu" in m for m in msgs)


def test_code_ciqual_mal_forme() -> None:
    assert any("mal formé" in m for m in erreurs({"id": "a", "nom": "a", "ciqual": "abc"}))


def test_table_ciqual_complete() -> None:
    codes = charger_codes_ciqual()
    assert len(codes) == 3185
    assert codes["20059"] == "Épinard, cru"


def test_au_moins_90_pourcent_relies_a_ciqual() -> None:
    ref = charger()
    feuilles = [i for i in ref.ingredients.values() if not ref.enfants[i.id]]
    assert sum(1 for i in feuilles if i.ciqual) / len(feuilles) >= 0.9
