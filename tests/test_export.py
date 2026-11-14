from __future__ import annotations

import hashlib
import json
from pathlib import Path

from bouchee.export import exporter


def test_export(tmp_path: Path) -> None:
    sortie = tmp_path / "site"
    m = exporter(sortie)
    v1 = sortie / "v1"
    noms = {f["chemin"] for f in m["fichiers"]}
    assert noms == {"ingredients.json", "recettes.json", "cas-validateur.json"}
    for f in m["fichiers"]:
        assert hashlib.sha256((v1 / f["chemin"]).read_bytes()).hexdigest() == f["sha256"]
    recettes = json.loads((v1 / "recettes.json").read_text(encoding="utf-8"))["recettes"]
    assert len(recettes) >= 30
    assert all(l["ingredients"] for r in recettes for l in r["lignes"])
    assert (sortie / "hello.json").exists()
    credits = (sortie / "CREDITS").read_text(encoding="utf-8")
    assert all(r["titre"] in credits for r in recettes)


def test_export_reproductible(tmp_path: Path) -> None:
    """Même contenu, même version : l'app ne retélécharge rien si rien n'a changé."""
    assert exporter(tmp_path / "a")["version"] == exporter(tmp_path / "b")["version"]
