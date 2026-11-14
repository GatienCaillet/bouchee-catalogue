# bouchee-catalogue

Catalogue de recettes et d'ingrédients de l'app Bouchée, publié en fichiers statiques sur GitHub Pages.

## Contenu

- `referentiel/allergenes.yaml` : les 14 allergènes réglementaires de l'UE.
- `referentiel/ingredients/*.yaml` : le référentiel d'ingrédients, un fichier par famille. Le format est décrit en tête de `bouchee/referentiel.py`.
- `bouchee/verifier.py` : contrôle du référentiel (parents et composants existants, allergènes valides, pas de cycle, pas d'alias ambigu).
- `bouchee/validateur.py` : validateur strict (*fail-closed*), qui dit si une recette est compatible avec un profil de goûts.
- `tests/cas/validateur.json` : cas pièges partagés avec le validateur TypeScript de l'app.
- `sources/ciqual2020/` : codes et noms des aliments CIQUAL 2020 (Anses, Licence Ouverte), pour vérifier les codes du référentiel.
- `public/` : fichiers publiés sur GitHub Pages.

## Commandes

```bash
pip install -e ".[dev]"
python -m bouchee.verifier
pytest
```

GitHub Actions lance le contrôle et les tests à chaque commit ; une erreur bloque la publication.

## À compléter

- Identifiants FoodOn des ingrédients ; codes CIQUAL des 17 ingrédients sans équivalent clair (liste affichée par `python -m bouchee.verifier`).
- Double relecture humaine des allergènes (SPECIFICATIONS.md, section 3.5).
- Attributs sensoriels : première estimation, à relire.

## Licence

Les recettes sont publiées sous CC BY-SA 4.0, avec l'attribution de leur source dans chaque fichier.
