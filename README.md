# bouchee-catalogue

Catalogue de recettes et d'ingrédients de l'app Bouchée, publié en fichiers statiques sur GitHub Pages.

## Contenu

- `referentiel/allergenes.yaml` : les 14 allergènes réglementaires de l'UE.
- `referentiel/ingredients/*.yaml` : le référentiel d'ingrédients, un fichier par famille. Le format est décrit en tête de `bouchee/referentiel.py`.
- `bouchee/verifier.py` : contrôle du référentiel (parents et composants existants, allergènes valides, pas de cycle, pas d'alias ambigu).
- `bouchee/validateur.py` : validateur strict (*fail-closed*), qui dit si une recette est compatible avec un profil de goûts.
- `bouchee/normaliseur.py` : normaliseur de lignes d'ingrédients en français (quantité, unité, nom, résolution par les alias). Il ne devine jamais : une ligne douteuse est signalée pour relecture.
- `recettes/*.yaml` : les recettes, adaptées du *Livre de cuisine* de Wikibooks (attribution dans chaque fichier). Le format est décrit en tête de `bouchee/recettes.py`.
- `bouchee/recettes.py` : chaîne de contrôle des recettes (`python -m bouchee.recettes`) : normalisation, validation, attribution, photo.
- `tests/cas/validateur.json` : cas pièges partagés avec le validateur TypeScript de l'app.
- `sources/ciqual2020/` : codes et noms des aliments CIQUAL 2020 (Anses, Licence Ouverte), pour vérifier les codes du référentiel.
- `public/` : fichiers publiés sur GitHub Pages.

## Commandes

```bash
pip install -e ".[dev]"
python -m bouchee.verifier
python -m bouchee.recettes
pytest
```

GitHub Actions lance le contrôle et les tests à chaque commit ; une erreur bloque la publication.

## À compléter

- Identifiants FoodOn des ingrédients ; codes CIQUAL des 17 ingrédients sans équivalent clair (liste affichée par `python -m bouchee.verifier`).
- Double relecture humaine des allergènes (SPECIFICATIONS.md, section 3.5).
- Attributs sensoriels : première estimation, à relire.

## Licence

Les recettes sont des adaptations de pages du *Livre de cuisine* de Wikibooks, publiées sous CC BY-SA. Chaque fichier cite la page, la révision utilisée, son historique (les auteurs) et la licence de cette révision (CC BY-SA 3.0 avant juin 2023, 4.0 ensuite). Les adaptations sont publiées sous CC BY-SA 4.0, ce que permet la clause de partage à l'identique de la version 3.0.

Les photos viennent de Wikimedia Commons ; chacune garde sa propre licence et son auteur, indiqués dans la recette.
