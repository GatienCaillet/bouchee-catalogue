"""Export du catalogue publié sur GitHub Pages (tâche F) : `python -m bouchee.export _site`.

Produit, dans le dossier de sortie :
- `v1/ingredients.json` et `v1/recettes.json` : le catalogue, lignes d'ingrédients déjà résolues ;
- `v1/cas-validateur.json` : les cas pièges, pour que l'app vérifie son validateur sur les mêmes cas ;
- `v1/manifest.json` : version, liste des fichiers, empreinte SHA-256 et taille de chacun.
  L'app lit le manifeste et ne télécharge que les fichiers dont l'empreinte a changé ;
- `CREDITS` : sources des recettes et des photos, licences ;
- les fichiers statiques de `public/` (copiés tels quels).

Les photos ne sont pas recopiées : l'app les charge à la demande depuis Wikimedia Commons, à
la taille voulue (`Special:FilePath?width=`), et les garde en cache. Toute recette non publiable
bloque l'export.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bouchee.recettes import RecetteControlee, controler_tout
from bouchee.referentiel import RACINE, Referentiel, charger

FORMAT = 1


def url_photo(fichier: str, largeur: int) -> str:
    nom = urllib.parse.quote(fichier.replace(" ", "_"))
    return f"https://commons.wikimedia.org/wiki/Special:FilePath/{nom}?width={largeur}"


def exporter_ingredients(ref: Referentiel) -> list[dict[str, Any]]:
    sortie = []
    for i in sorted(ref.ingredients.values(), key=lambda x: x.id):
        d: dict[str, Any] = {"id": i.id, "nom": i.nom, "famille": i.famille}
        if i.parent:
            d["parent"] = i.parent
        if i.alias_fr or i.alias_en:
            d["alias"] = list(i.alias_fr) + list(i.alias_en)
        if i.allergenes:
            d["allergenes"] = sorted(i.allergenes)
        if i.composants:
            d["composants"] = list(i.composants)
        if i.composition_variable:
            d["composition_variable"] = True
        if i.sensoriel:
            d["sensoriel"] = i.sensoriel
        if i.ciqual:
            d["ciqual"] = i.ciqual
        sortie.append(d)
    return sortie


def exporter_recette(r: RecetteControlee) -> dict[str, Any]:
    d = r.donnees
    lignes = []
    for l in r.lignes:
        ligne: dict[str, Any] = {"texte": l.texte, "ingredients": l.ingredients, "confiance": l.confiance}
        if l.quantite is not None:
            ligne["quantite"] = l.quantite
        if l.quantite_max is not None:
            ligne["quantite_max"] = l.quantite_max
        if l.unite:
            ligne["unite"] = l.unite
        if l.facultatif:
            ligne["facultatif"] = True
        lignes.append(ligne)
    temps = {k: v for k, v in d["temps"].items() if v}
    photo = d["photo"]
    sortie: dict[str, Any] = {
        "id": d["id"],
        "titre": d["titre"],
        "portions": d["portions"],
        "temps": temps,
        "temps_total": sum(v for k, v in temps.items() if k != "repos"),
        "lignes": lignes,
        "etapes": d["etapes"],
        "photo": {
            "vignette": url_photo(photo["fichier"], 320),
            "image": url_photo(photo["fichier"], 1024),
            "page": photo["url"],
            "auteur": photo["auteur"],
            "licence": photo["licence"],
        },
        "source": {k: d["source"][k] for k in ("titre", "url", "auteurs", "licence", "modifications")},
    }
    if d.get("decouverte"):
        sortie["decouverte"] = d["decouverte"]
    return sortie


def credits(recettes: list[RecetteControlee]) -> str:
    lignes = [
        "Catalogue Bouchée : crédits",
        "",
        "Recettes : adaptations de pages du « Livre de cuisine » de Wikibooks (https://fr.wikibooks.org),",
        "par les contributeurs de Wikibooks. Les adaptations sont publiées sous CC BY-SA 4.0.",
        "Photos : Wikimedia Commons ; chaque photo garde sa licence et son auteur.",
        "Données nutritionnelles de référence : Anses, table Ciqual 2020 (Licence Ouverte).",
        "",
    ]
    for r in sorted(recettes, key=lambda x: x.donnees["titre"]):
        d = r.donnees
        s, p = d["source"], d["photo"]
        lignes += [
            d["titre"],
            f"  Recette : « {s['titre']} », {s['auteurs']}, {s['licence']}, {s['url']}",
            f"  Modifications : {s['modifications']}",
            f"  Photo : « {p['fichier']} », {p['auteur']}, {p['licence']}, {p['url']}",
            "",
        ]
    return "\n".join(lignes)


def ecrire_json(chemin: Path, donnees: Any) -> None:
    chemin.write_text(json.dumps(donnees, ensure_ascii=False, separators=(",", ":"), sort_keys=True), encoding="utf-8")


def exporter(sortie: Path) -> dict[str, Any]:
    recettes = controler_tout()
    bloquees = [r.fichier for r in recettes if not r.publiable]
    if bloquees:
        raise SystemExit(f"Export bloqué, recettes non publiables : {', '.join(bloquees)}")
    ref = charger()

    if sortie.exists():
        shutil.rmtree(sortie)
    shutil.copytree(RACINE / "public", sortie)
    v1 = sortie / "v1"
    v1.mkdir()
    ecrire_json(v1 / "ingredients.json", {"format": FORMAT, "allergenes": ref.allergenes, "ingredients": exporter_ingredients(ref)})
    ecrire_json(v1 / "recettes.json", {"format": FORMAT, "recettes": [exporter_recette(r) for r in recettes]})
    shutil.copy(RACINE / "tests" / "cas" / "validateur.json", v1 / "cas-validateur.json")
    (sortie / "CREDITS").write_text(credits(recettes), encoding="utf-8")

    fichiers = []
    for f in sorted(v1.iterdir()):
        contenu = f.read_bytes()
        fichiers.append({"chemin": f.name, "sha256": hashlib.sha256(contenu).hexdigest(), "taille": len(contenu)})
    empreinte = hashlib.sha256("".join(f["sha256"] for f in fichiers).encode()).hexdigest()[:12]
    manifeste = {
        "format": FORMAT,
        "version": empreinte,
        "genere_le": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "commit": os.environ.get("GITHUB_SHA", "local"),
        "fichiers": fichiers,
    }
    ecrire_json(v1 / "manifest.json", manifeste)
    return manifeste


def main() -> int:
    sortie = Path(sys.argv[1] if len(sys.argv) > 1 else "_site")
    m = exporter(sortie)
    print(f"Catalogue {m['version']} exporté dans {sortie} : " + ", ".join(f"{f['chemin']} ({f['taille']} o)" for f in m["fichiers"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
