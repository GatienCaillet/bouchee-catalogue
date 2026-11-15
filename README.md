# bouchee-catalogue

Catalogue de recettes et d'ingrédients de l'app Bouchée, publié en fichiers statiques sur GitHub Pages.

## Contenu

- `referentiel/allergenes.yaml` : les 14 allergènes réglementaires de l'UE.
- `referentiel/ingredients/*.yaml` : le référentiel d'ingrédients, un fichier par famille. Le format est décrit en tête de `bouchee/referentiel.py`.
- `bouchee/verifier.py` : contrôle du référentiel (parents et composants existants, allergènes valides, pas de cycle, pas d'alias ambigu).
- `bouchee/validateur.py` : validateur strict (*fail-closed*), qui dit si une recette est compatible avec un profil de goûts.
- `bouchee/normaliseur.py` : normaliseur de lignes d'ingrédients en français (quantité, unité, nom, résolution par les alias). Il ne devine jamais : une ligne douteuse est signalée pour relecture.
- `recettes/*.yaml` : 1 010 recettes, de trois origines (attribution dans chaque fichier) :
  - 31 adaptées et relues à la main depuis le *Livre de cuisine* de Wikibooks ;
  - 431 importées en lot depuis le même livre par `bouchee/import_wikibooks.py` : seules les pages dont toutes les lignes se résolvent sans relecture sont gardées ; portions et temps sont estimés quand la page ne les donne pas (c'est écrit dans `source.modifications`) ;
  - 548 rédigées pour Bouchée par `bouchee/generer_recettes.py`, à partir de bases courantes (velouté, gratin, quiche, curry, papillote, crumble...) et de parcours de découverte sur 5 niveaux pour une dizaine d'aliments. **Elles n'ont pas encore été testées en cuisine.**

  Le format est décrit en tête de `bouchee/recettes.py`. La photo est facultative : 120 recettes en ont une (Wikimedia Commons, licence lue par l'API) ; l'app affiche sinon une planche gravée ou l'initiale du titre.
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

# Ré-importer Wikibooks (téléchargement lent : l'API limite le débit)
python -m bouchee.import_wikibooks telecharger <dossier>
python -m bouchee.import_wikibooks photos <dossier>
python -m bouchee.import_wikibooks importer <dossier>   # n'écrase jamais une recette existante
python -m bouchee.generer_recettes                        # idem
```

GitHub Actions lance le contrôle et les tests à chaque commit ; une erreur bloque la publication.

## À compléter

- Relecture culinaire des recettes rédigées (quantités, temps) et des temps estimés des recettes importées.
- Les 145 lignes gardées au niveau d'une catégorie (`categorie: true`, par exemple « 2 c. à soupe d'huile ») : sûres pour le filtre, à préciser pour les courses et la nutrition.
- Les ~690 ingrédients ajoutés en novembre 2026 (référentiel passé de 354 à 1 003) : allergènes et composants à relire deux fois comme les autres ; 154 codes CIQUAL sont approchés (`ciqual_approche: true`).

- Identifiants FoodOn des ingrédients ; codes CIQUAL des 17 ingrédients sans équivalent clair (liste affichée par `python -m bouchee.verifier`).
- Double relecture humaine des allergènes (SPECIFICATIONS.md, section 3.5).
- Attributs sensoriels : première estimation, à relire.

## Licence

Les recettes sont des adaptations de pages du *Livre de cuisine* de Wikibooks, publiées sous CC BY-SA. Chaque fichier cite la page, la révision utilisée, son historique (les auteurs) et la licence de cette révision (CC BY-SA 3.0 avant juin 2023, 4.0 ensuite). Les adaptations sont publiées sous CC BY-SA 4.0, ce que permet la clause de partage à l'identique de la version 3.0.

Les photos viennent de Wikimedia Commons ; chacune garde sa propre licence et son auteur, indiqués dans la recette.
