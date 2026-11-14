"""Validateur strict (fail-closed) : une recette est-elle compatible avec un profil de goûts ?

Règle (SPECIFICATIONS.md, section 3.1) : une recette est compatible seulement si
- elle a au moins une ligne d'ingrédient ;
- chaque ligne est résolue vers des ingrédients connus, avec une confiance suffisante ;
- aucun ingrédient résolu, ni aucun de ses parents, composants ou descendants, n'est refusé
  ou interdit, et aucun ne porte un allergène du profil.

Pourquoi les descendants : une ligne résolue vers une catégorie (« fruits de mer ») peut
désigner n'importe lequel de ses membres ; on suppose donc le pire.
Pourquoi pas les descendants des parents : le parmesan est un fromage, mais il n'est pas
de l'emmental. On remonte vers les parents sans redescendre vers leurs autres enfants.

Le même jeu de cas (tests/cas/validateur.json) sert au validateur TypeScript de l'app.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Mapping

from bouchee.referentiel import Referentiel

SEUIL_CONFIANCE = 0.9


class ProfilInvalide(ValueError):
    """Le profil cite un ingrédient ou un allergène inconnu. On refuse de deviner."""


@dataclass(frozen=True)
class Raison:
    type: str  # recette_vide, ligne_non_resolue, confiance_faible, ingredient_inconnu, refus, interdit, allergie
    ligne: int | None = None
    ingredient: str | None = None
    allergene: str | None = None
    chemin: tuple[str, ...] = ()

    def en_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"type": self.type}
        for cle in ("ligne", "ingredient", "allergene"):
            if getattr(self, cle) is not None:
                d[cle] = getattr(self, cle)
        if self.chemin:
            d["chemin"] = list(self.chemin)
        return d


@dataclass
class Resultat:
    compatible: bool
    raisons: list[Raison] = field(default_factory=list)


@dataclass(frozen=True)
class Profil:
    allergies: frozenset[str] = frozenset()
    interdits: frozenset[str] = frozenset()
    refus: frozenset[str] = frozenset()

    @classmethod
    def depuis_dict(cls, d: Mapping[str, Any], ref: Referentiel) -> "Profil":
        inconnus_cles = set(d) - {"allergies", "interdits", "refus"}
        if inconnus_cles:
            raise ProfilInvalide(f"clés inconnues : {sorted(inconnus_cles)}")
        profil = cls(
            allergies=frozenset(d.get("allergies") or []),
            interdits=frozenset(d.get("interdits") or []),
            refus=frozenset(d.get("refus") or []),
        )
        allergenes_inconnus = profil.allergies - set(ref.allergenes)
        if allergenes_inconnus:
            raise ProfilInvalide(f"allergènes inconnus : {sorted(allergenes_inconnus)}")
        ids_inconnus = (profil.interdits | profil.refus) - set(ref.ingredients)
        if ids_inconnus:
            raise ProfilInvalide(f"ingrédients inconnus : {sorted(ids_inconnus)}")
        return profil


def fermeture(ref: Referentiel, ident: str) -> dict[str, tuple[str, ...]]:
    """Tout ce qu'implique un ingrédient, avec le chemin le plus court depuis lui.

    Depuis un nœud « concret » (l'ingrédient de la ligne, un composant, un descendant) :
    parent, composants et enfants. Depuis un parent : son propre parent et ses composants.
    """
    chemins: dict[str, tuple[str, ...]] = {ident: (ident,)}
    concrets: set[str] = {ident}
    file: deque[tuple[str, bool]] = deque([(ident, True)])
    while file:
        noeud, concret = file.popleft()
        ing = ref[noeud]
        suivants: list[tuple[str, bool]] = []
        if ing.parent:
            suivants.append((ing.parent, False))
        suivants.extend((c, True) for c in ing.composants)
        if concret:
            suivants.extend((e, True) for e in ref.enfants[noeud])
        for s, s_concret in suivants:
            deja = s in chemins
            if deja and (s in concrets or not s_concret):
                continue
            if not deja:
                chemins[s] = chemins[noeud] + (s,)
            if s_concret:
                concrets.add(s)
            file.append((s, s_concret))
    return chemins


def verifier_recette(
    ref: Referentiel,
    recette: Mapping[str, Any],
    profil: Profil | Mapping[str, Any],
    seuil: float = SEUIL_CONFIANCE,
) -> Resultat:
    if not isinstance(profil, Profil):
        profil = Profil.depuis_dict(profil, ref)
    exclus = {i: "interdit" for i in profil.interdits}
    exclus.update({i: "refus" for i in profil.refus if i not in exclus})

    raisons: list[Raison] = []
    vues: set[tuple[Any, ...]] = set()

    def ajouter(r: Raison) -> None:
        cle = (r.type, r.ligne, r.ingredient, r.allergene)
        if cle not in vues:
            vues.add(cle)
            raisons.append(r)

    lignes = recette.get("lignes") or []
    if not lignes:
        ajouter(Raison("recette_vide"))

    for n, ligne in enumerate(lignes):
        ids = ligne.get("ingredients") or []
        if not ids:
            ajouter(Raison("ligne_non_resolue", n))
            continue
        confiance = ligne.get("confiance")
        if isinstance(confiance, bool) or not isinstance(confiance, (int, float)) or confiance < seuil:
            ajouter(Raison("confiance_faible", n))
        for ident in ids:
            if ident not in ref:
                ajouter(Raison("ingredient_inconnu", n, ingredient=str(ident)))
                continue
            for noeud, chemin in fermeture(ref, ident).items():
                if noeud in exclus:
                    ajouter(Raison(exclus[noeud], n, ingredient=noeud, chemin=chemin))
                for allergene in sorted(ref[noeud].allergenes & profil.allergies):
                    ajouter(Raison("allergie", n, ingredient=noeud, allergene=allergene, chemin=chemin))

    return Resultat(compatible=not raisons, raisons=raisons)
