"""Contrôle du référentiel d'ingrédients : `python -m bouchee.verifier`.

Code de sortie 1 s'il y a au moins une erreur (la publication est alors bloquée).
"""

from __future__ import annotations

import sys
from collections import Counter

from bouchee.referentiel import (
    DOSSIER_REFERENTIEL,
    charger_allergenes,
    construire,
    lire_entrees,
    verifier_entrees,
)


def main() -> int:
    allergenes = charger_allergenes(DOSSIER_REFERENTIEL)
    entrees = lire_entrees(DOSSIER_REFERENTIEL)
    problemes = verifier_entrees(entrees, allergenes)
    erreurs = [p for p in problemes if p.niveau == "erreur"]
    for p in problemes:
        print(p)

    if not erreurs:
        ref = construire(entrees, allergenes)
        familles = Counter(i.famille for i in ref.ingredients.values())
        categories = sum(1 for i in ref.ingredients if ref.enfants[i])
        composes = sum(1 for i in ref.ingredients.values() if i.composants)
        variables = sum(1 for i in ref.ingredients.values() if i.composition_variable)
        print(
            f"\n{len(ref)} ingrédients dont {categories} catégories, "
            f"{composes} composés ({variables} à composition variable)"
        )
        for famille, n in sorted(familles.items()):
            print(f"  {famille} : {n}")

    print(f"\n{len(erreurs)} erreur(s), {len(problemes) - len(erreurs)} avertissement(s)")
    return 1 if erreurs else 0


if __name__ == "__main__":
    sys.exit(main())
