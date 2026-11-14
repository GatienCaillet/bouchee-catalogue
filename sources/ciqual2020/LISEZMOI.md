# Table CIQUAL 2020 : liste des aliments

`aliments.tsv` contient le code et le nom français des 3 185 aliments de la table de composition nutritionnelle CIQUAL 2020. Les valeurs nutritionnelles n'y figurent pas.

- **Source** : Anses. 2020. Table de composition nutritionnelle des aliments Ciqual. https://ciqual.anses.fr/
- **Licence** : Licence Ouverte (Etalab), confirmée sur la fiche data.gouv.fr du jeu de données (identifiant `5369a15fa3a729239d2065b7`).
- **Fichier d'origine** : `XML_2020_07_07.zip` (fichier `alim_2020_07_07.xml`, encodage windows-1252), téléchargé le 14 novembre 2026. Le site de l'Anses étant en maintenance ce jour-là, la copie vient de l'archive du même fichier officiel sur archive.org (capture du 23 février 2026).
- **Transformation** : extraction des champs `alim_code` et `alim_nom_fr`, conversion en UTF-8. Le XML d'origine contient des `<` non échappés (« Panaché préemballé (<1° alc.) ») ; il est donc lu par expression régulière, et le nombre d'aliments extraits est contrôlé.

Ce fichier sert à vérifier que chaque code `ciqual` du référentiel désigne un aliment réel. L'import des valeurs nutritionnelles viendra avec le module de nutrition (V1).
