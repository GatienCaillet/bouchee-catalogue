"""Recettes rédigées pour Bouchée, déclinées à partir de bases de cuisine courantes.

    python -m bouchee.generer_recettes            # écrit recettes/*.yaml (sans écraser l'existant)
    python -m bouchee.generer_recettes --essai    # contrôle seulement

Chaque base (velouté, gratin, quiche, curry, papillote, crumble...) est écrite une fois, avec
ses étapes, puis déclinée avec des garnitures choisies pour aller ensemble. Les lignes
d'ingrédients sont écrites dans les mots du référentiel : elles passent le normaliseur sans
relecture, et chaque recette passe la même chaîne de contrôle que les autres (`controler`).

Les recettes sont publiées sous CC BY-SA 4.0, comme le reste du catalogue. Elles n'ont pas
encore été testées en cuisine : `source.modifications` le dit, et une relecture culinaire
reste à faire (quantités, temps).

Une recette dont l'identifiant existe déjà dans `recettes/` n'est jamais écrasée.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Any, Iterator

import yaml

from bouchee.normaliseur import Normaliseur
from bouchee.recettes import DOSSIER_RECETTES, controler, lire_recettes
from bouchee.referentiel import charger
from bouchee.import_wikibooks import slug

SOURCE = {
    "titre": "Recette Bouchée",
    "url": "https://github.com/GatienCaillet/bouchee-catalogue",
    "auteurs": "Bouchée",
    "licence": "CC BY-SA 4.0 (Bouchée)",
}


@dataclass
class R:
    titre: str
    lignes: list[Any]
    etapes: list[str]
    prep: int
    cuisson: int
    base: str
    portions: int = 4
    repos: int = 0
    decouverte: dict[str, Any] | None = None
    id: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def en_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "id": self.id or slug(self.titre),
            "titre": self.titre,
            "portions": self.portions,
            "temps": {"preparation": self.prep, "cuisson": self.cuisson, "repos": self.repos},
            "ingredients": self.lignes,
            "etapes": self.etapes,
        }
        if self.decouverte:
            d["decouverte"] = self.decouverte
        d["source"] = {**SOURCE, "modifications": f"Recette rédigée pour Bouchée (base « {self.base} »), "
                                                  "pas encore testée en cuisine : quantités et temps à confirmer."}
        return d


# --- Légumes : forme du nom, ligne d'ingrédient, préparation -------------------------------
# slug, « de ... » pour les titres, ligne pour 800 g, « les ... », préparation, usages
@dataclass
class Leg:
    slug: str
    de: str
    ligne: str
    les: str
    prep: str
    usages: str  # s soupe, g gratin, r rôti, p purée, o poêlée
    aliment: str = ""


LEGUMES = [
    Leg("carotte", "de carottes", "800 g de carottes", "les carottes", "Éplucher les carottes et les couper en rondelles.", "sgrpo", "carotte"),
    Leg("potiron", "de potiron", "1 kg de potiron", "le potiron", "Peler le potiron, retirer les graines et le couper en cubes.", "sgrp", "potiron"),
    Leg("butternut", "de butternut", "1 courge butternut", "la courge", "Peler la courge, retirer les graines et la couper en cubes.", "sgrp", "butternut"),
    Leg("courgette", "de courgettes", "800 g de courgettes", "les courgettes", "Laver les courgettes et les couper en rondelles.", "sgro", "courgette"),
    Leg("poireau", "de poireaux", "4 poireaux", "les poireaux", "Fendre les poireaux, les laver soigneusement et les émincer.", "sgo", "poireau"),
    Leg("champignon", "de champignons", "600 g de champignons de Paris", "les champignons", "Nettoyer les champignons et les émincer.", "so", "champignon_de_paris"),
    Leg("chou-fleur", "de chou-fleur", "1 chou-fleur", "le chou-fleur", "Détacher le chou-fleur en petits bouquets et les laver.", "sgrp", "chou_fleur"),
    Leg("brocoli", "de brocoli", "600 g de brocoli", "le brocoli", "Détacher le brocoli en petits bouquets et les laver.", "sgro", "brocoli"),
    Leg("petits-pois", "de petits pois", "600 g de petits pois", "les petits pois", "Écosser les petits pois, ou les décongeler s'ils sont surgelés.", "sp", "petit_pois"),
    Leg("patate-douce", "de patates douces", "800 g de patates douces", "les patates douces", "Éplucher les patates douces et les couper en cubes.", "sgrp", "patate_douce"),
    Leg("panais", "de panais", "800 g de panais", "les panais", "Éplucher les panais et les couper en tronçons.", "srp", "panais"),
    Leg("celeri-rave", "de céleri-rave", "1 céleri-rave", "le céleri", "Peler le céleri-rave et le couper en cubes.", "sgp", "celeri_rave"),
    Leg("topinambour", "de topinambours", "800 g de topinambours", "les topinambours", "Éplucher les topinambours et les couper en morceaux.", "sp", "topinambour"),
    Leg("epinard", "d'épinards", "600 g d'épinards", "les épinards", "Laver les épinards et retirer les tiges dures.", "sgo", "epinard"),
    Leg("tomate", "de tomates", "1 kg de tomates", "les tomates", "Laver les tomates et les couper en quartiers.", "sr", "tomate"),
    Leg("betterave", "de betteraves", "600 g de betteraves", "les betteraves", "Éplucher les betteraves et les couper en cubes.", "sr", "betterave"),
    Leg("navet", "de navets", "800 g de navets", "les navets", "Éplucher les navets et les couper en cubes.", "sro", "navet"),
    Leg("fenouil", "de fenouil", "3 bulbes de fenouil", "le fenouil", "Retirer la base et les tiges du fenouil, puis l'émincer.", "sgro", "fenouil"),
    Leg("aubergine", "d'aubergines", "3 aubergines", "les aubergines", "Laver les aubergines et les couper en cubes.", "gro", "aubergine"),
    Leg("poivron", "de poivrons", "4 poivrons", "les poivrons", "Épépiner les poivrons et les couper en lanières.", "sro", "poivron"),
    Leg("haricot-vert", "de haricots verts", "600 g de haricots verts", "les haricots verts", "Équeuter les haricots verts.", "o", "haricot_vert"),
    Leg("asperge", "d'asperges", "800 g d'asperges", "les asperges", "Éplucher les asperges et couper la base dure.", "sgr", "asperge"),
    Leg("endive", "d'endives", "6 endives", "les endives", "Retirer le cône amer à la base des endives et les couper en deux.", "gro", "endive"),
    Leg("chou-vert", "de chou vert", "1 chou vert", "le chou", "Retirer les grosses côtes du chou et l'émincer finement.", "so", "chou_vert"),
    Leg("lentille-corail", "de lentilles corail", "250 g de lentilles corail", "les lentilles", "Rincer les lentilles corail.", "s", "lentille_corail"),
    Leg("cresson", "de cresson", "2 bottes de cresson", "le cresson", "Laver le cresson et retirer les plus grosses tiges.", "s", "cresson"),
    Leg("artichaut", "d'artichauts", "400 g de cœurs d'artichaut", "les cœurs d'artichaut", "Égoutter les cœurs d'artichaut et les couper en quartiers.", "sg", "artichaut"),
    Leg("chou-de-bruxelles", "de choux de Bruxelles", "600 g de choux de Bruxelles", "les choux de Bruxelles", "Retirer les premières feuilles des choux de Bruxelles et les couper en deux.", "ro", "chou_de_bruxelles"),
    Leg("radis", "de radis", "2 bottes de radis", "les radis", "Laver les radis et les couper en deux.", "ro", "radis"),
    Leg("pomme-de-terre", "de pommes de terre", "1 kg de pommes de terre", "les pommes de terre", "Éplucher les pommes de terre et les couper en morceaux.", "sgr", "pomme_de_terre"),
]


def avec(u: str) -> list[Leg]:
    return [l for l in LEGUMES if u in l.usages]


# --- Bases salées ----------------------------------------------------------------------------

def veloutes() -> Iterator[R]:
    finitions = [
        ("", ["10 cl de crème liquide"], "Ajouter la crème, mixer finement et rectifier l'assaisonnement.", "velouté à la crème"),
        (" au lait de coco et au curry", ["20 cl de lait de coco", "1 c. à café de curry"],
         "Ajouter le lait de coco et le curry, mixer finement et rectifier l'assaisonnement.", "velouté au lait de coco"),
        (" au cumin", ["1 c. à café de cumin en poudre", "4 c. à soupe de yaourt nature"],
         "Mixer finement avec le cumin, rectifier l'assaisonnement et servir avec une cuillerée de yaourt.", "velouté au cumin"),
    ]
    for l in avec("s"):
        for suffixe, lignes, finale, base in finitions:
            if l.slug in ("tomate", "betterave") and "coco" in suffixe:
                continue
            yield R(
                titre=f"Velouté {l.de}{suffixe}",
                lignes=[l.ligne, "1 oignon", "2 c. à soupe d'huile d'olive", "1 l de bouillon de légumes", *lignes, "sel, poivre"],
                etapes=[
                    l.prep,
                    "Émincer l'oignon et le faire revenir 3 minutes dans l'huile d'olive, dans une grande casserole.",
                    f"Ajouter {l.les}, mélanger, puis verser le bouillon.",
                    "Porter à ébullition et laisser cuire 20 à 25 minutes à feu moyen, jusqu'à ce que les légumes soient tendres.",
                    finale,
                ],
                prep=15, cuisson=30, base=base,
            )


def gratins() -> Iterator[R]:
    for l in avec("g"):
        if l.slug == "pomme-de-terre":
            continue
        yield R(
            titre=f"Gratin {l.de} à la béchamel",
            lignes=[l.ligne, "40 g de beurre", "40 g de farine", "50 cl de lait", "1 pincée de muscade", "80 g d'emmental râpé", "sel, poivre"],
            etapes=[
                l.prep,
                f"Cuire {l.les} 10 minutes à l'eau bouillante salée, puis bien égoutter.",
                "Préparer la béchamel : faire fondre le beurre, ajouter la farine, puis verser le lait petit à petit en fouettant jusqu'à épaississement. Saler, poivrer, ajouter la muscade.",
                f"Disposer {l.les} dans un plat à gratin beurré, napper de béchamel et parsemer d'emmental.",
                "Enfourner 25 minutes à 200 °C, jusqu'à ce que le dessus soit doré.",
            ],
            prep=20, cuisson=35, base="gratin à la béchamel",
        )
        yield R(
            titre=f"Gratin {l.de} au parmesan",
            lignes=[l.ligne, "20 cl de crème fraîche", "2 œufs", "50 g de parmesan râpé", "1 gousse d'ail", "sel, poivre"],
            etapes=[
                l.prep,
                f"Cuire {l.les} 10 minutes à la vapeur ou à l'eau bouillante salée, puis bien égoutter.",
                "Frotter un plat à gratin avec la gousse d'ail coupée en deux.",
                "Battre les œufs avec la crème, saler et poivrer.",
                f"Disposer {l.les} dans le plat, verser la crème aux œufs et parsemer de parmesan.",
                "Enfourner 25 minutes à 190 °C.",
            ],
            prep=15, cuisson=35, base="gratin à la crème",
        )


def rotis() -> Iterator[R]:
    styles = [
        (" rôtis aux herbes de Provence", ["1 c. à soupe d'herbes de Provence"], "Parsemer d'herbes de Provence", "légumes rôtis aux herbes"),
        (" rôtis au cumin et au paprika", ["1 c. à café de cumin en poudre", "1 c. à café de paprika"], "Saupoudrer de cumin et de paprika", "légumes rôtis aux épices"),
    ]
    for l in avec("r"):
        for suffixe, lignes, geste, base in styles:
            nom = l.de.replace("de ", "", 1).replace("d'", "", 1)
            titre = f"{nom[0].upper()}{nom[1:]}{suffixe}"
            if not nom.endswith("s") and nom not in ("chou-fleur",):
                titre = titre.replace("rôtis", "rôti")
            if nom in ("patates douces", "betteraves", "tomates", "courgettes", "aubergines", "carottes", "asperges", "endives", "pommes de terre"):
                titre = titre.replace("rôtis", "rôties")
            yield R(
                titre=titre,
                lignes=[l.ligne, "3 c. à soupe d'huile d'olive", *lignes, "2 gousses d'ail", "sel, poivre"],
                etapes=[
                    "Préchauffer le four à 210 °C.",
                    l.prep,
                    f"Étaler {l.les} sur une plaque, arroser d'huile d'olive et ajouter les gousses d'ail entières.",
                    f"{geste}, saler, poivrer et bien mélanger.",
                    "Enfourner 30 à 40 minutes en remuant à mi-cuisson, jusqu'à ce que les légumes soient dorés et tendres.",
                ],
                prep=10, cuisson=35, base=base,
            )


def purees() -> Iterator[R]:
    for l in avec("p"):
        yield R(
            titre=f"Purée {l.de} et pommes de terre",
            lignes=[l.ligne, "400 g de pommes de terre", "30 g de beurre", "10 cl de lait", "sel, poivre"],
            etapes=[
                l.prep,
                "Éplucher les pommes de terre et les couper en morceaux.",
                f"Cuire {l.les} et les pommes de terre 20 à 25 minutes à l'eau bouillante salée.",
                "Égoutter, puis écraser au presse-purée avec le beurre et le lait chaud.",
                "Saler, poivrer et servir aussitôt.",
            ],
            prep=15, cuisson=25, base="purée",
        )


def poelees() -> Iterator[R]:
    for l in avec("o"):
        nom = l.de.replace("de ", "", 1).replace("d'", "", 1)
        yield R(
            titre=f"Poêlée {l.de} à l'ail et au persil",
            lignes=[l.ligne, "2 c. à soupe d'huile d'olive", "2 gousses d'ail", "1/2 botte de persil", "sel, poivre"],
            etapes=[
                l.prep,
                f"Faire chauffer l'huile dans une grande poêle et y faire sauter {l.les} 10 à 15 minutes à feu vif, en remuant souvent.",
                "Hacher l'ail et le persil.",
                "Ajouter l'ail et le persil en fin de cuisson, saler, poivrer et cuire encore 2 minutes.",
            ],
            prep=10, cuisson=15, base="poêlée",
        )


QUICHES = [
    ("aux poireaux et aux lardons", ["3 poireaux", "150 g de lardons"], "Émincer les poireaux et les faire fondre 10 minutes à la poêle avec les lardons."),
    ("au saumon et aux épinards", ["200 g de saumon fumé", "200 g d'épinards"], "Faire tomber les épinards à la poêle, les presser, puis les mélanger au saumon coupé en lanières."),
    ("aux courgettes et au chèvre", ["2 courgettes", "150 g de fromage de chèvre"], "Couper les courgettes en rondelles et les faire revenir 8 minutes à la poêle ; couper le chèvre en rondelles."),
    ("au thon et à la tomate", ["1 boîte de thon (140 g)", "2 tomates", "1 c. à soupe de moutarde de Dijon"], "Émietter le thon, couper les tomates en rondelles et tartiner le fond de pâte de moutarde."),
    ("aux champignons", ["400 g de champignons de Paris", "1 échalote"], "Émincer les champignons et l'échalote et les faire revenir 10 minutes à la poêle."),
    ("au brocoli et à la feta", ["300 g de brocoli", "100 g de feta"], "Cuire les bouquets de brocoli 5 minutes à la vapeur et émietter la feta."),
    ("aux poivrons", ["2 poivrons", "1 oignon"], "Couper les poivrons en lanières, émincer l'oignon et faire revenir le tout 10 minutes."),
    ("au jambon et au fromage", ["150 g de jambon blanc", "100 g d'emmental râpé"], "Couper le jambon en dés."),
    ("à la courge et au chèvre", ["400 g de courge butternut", "100 g de fromage de chèvre"], "Couper la courge en petits cubes, les cuire 10 minutes à la vapeur et émietter le chèvre."),
    ("à la tomate et à la moutarde", ["4 tomates", "2 c. à soupe de moutarde de Dijon", "1 c. à café d'herbes de Provence"], "Tartiner le fond de pâte de moutarde et couper les tomates en rondelles."),
    ("aux asperges", ["400 g d'asperges vertes"], "Couper les asperges en tronçons et les cuire 5 minutes à l'eau bouillante salée."),
    ("au chou-fleur et au curry", ["400 g de chou-fleur", "1 c. à café de curry"], "Cuire les bouquets de chou-fleur 8 minutes à la vapeur et ajouter le curry à l'appareil."),
    ("aux carottes et au cumin", ["400 g de carottes", "1 c. à café de cumin en poudre"], "Râper les carottes et les faire revenir 5 minutes à la poêle avec le cumin."),
    ("aux épinards et à la ricotta", ["300 g d'épinards", "150 g de ricotta"], "Faire tomber les épinards à la poêle, les presser et les mélanger à la ricotta."),
    ("aux oignons", ["4 oignons", "20 g de beurre"], "Émincer les oignons et les faire fondre 15 minutes au beurre à feu doux."),
    ("au poulet et aux champignons", ["250 g de blanc de poulet", "200 g de champignons de Paris"], "Couper le poulet en dés, émincer les champignons et les faire revenir 8 minutes à la poêle."),
    ("au saumon et au poireau", ["200 g de pavé de saumon", "2 poireaux"], "Émincer les poireaux et les faire fondre ; couper le saumon en dés."),
    ("aux tomates cerises et au basilic", ["250 g de tomates cerises", "1/2 botte de basilic", "50 g de parmesan râpé"], "Couper les tomates cerises en deux et ciseler le basilic."),
]


def quiches() -> Iterator[R]:
    for titre, garniture, geste in QUICHES:
        yield R(
            titre=f"Quiche {titre}",
            lignes=["1 pâte brisée", *garniture, "3 œufs", "20 cl de crème fraîche", "10 cl de lait", "1 pincée de muscade", "sel, poivre"],
            etapes=[
                "Préchauffer le four à 180 °C et garnir un moule à tarte de la pâte brisée.",
                geste,
                "Battre les œufs avec la crème et le lait ; saler, poivrer et ajouter la muscade.",
                "Répartir la garniture sur la pâte et verser l'appareil par-dessus.",
                "Enfourner 35 à 40 minutes, jusqu'à ce que la quiche soit dorée et prise.",
            ],
            prep=20, cuisson=40, base="quiche",
        )


OMELETTES = [
    ("aux champignons", ["200 g de champignons de Paris"], "Émincer les champignons et les faire revenir 5 minutes à la poêle."),
    ("aux fines herbes", ["1/2 botte de ciboulette", "1/2 botte de persil"], "Ciseler la ciboulette et le persil."),
    ("au fromage", ["80 g d'emmental râpé"], ""),
    ("aux pommes de terre et à l'oignon", ["3 pommes de terre", "1 oignon"], "Couper les pommes de terre en fines rondelles et l'oignon en lamelles ; les cuire 15 minutes à la poêle."),
    ("aux courgettes", ["2 courgettes"], "Râper les courgettes, les presser et les faire revenir 5 minutes."),
    ("aux épinards et à la feta", ["150 g d'épinards", "80 g de feta"], "Faire tomber les épinards à la poêle et émietter la feta."),
    ("au jambon", ["100 g de jambon blanc"], "Couper le jambon en dés."),
    ("aux poivrons", ["1 poivron rouge", "1 oignon"], "Couper le poivron en lanières et l'oignon en lamelles, et les faire revenir 8 minutes."),
    ("au saumon fumé", ["100 g de saumon fumé", "1/2 botte d'aneth"], "Couper le saumon en lanières et ciseler l'aneth."),
    ("aux tomates et au basilic", ["2 tomates", "quelques feuilles de basilic"], "Couper les tomates en dés et ciseler le basilic."),
    ("aux lardons", ["100 g de lardons"], "Faire dorer les lardons à la poêle sans matière grasse."),
    ("aux asperges", ["200 g d'asperges vertes"], "Couper les asperges en tronçons et les faire revenir 5 minutes."),
]


def omelettes() -> Iterator[R]:
    for titre, garniture, geste in OMELETTES:
        etapes = [geste] if geste else []
        etapes += [
            "Battre les œufs en omelette avec le lait ; saler et poivrer.",
            "Faire chauffer le beurre dans une grande poêle, ajouter la garniture puis verser les œufs.",
            "Cuire à feu moyen 5 à 8 minutes en ramenant les bords vers le centre, jusqu'à ce que l'omelette soit prise mais encore moelleuse.",
        ]
        yield R(
            titre=f"Omelette {titre}",
            lignes=["8 œufs", "5 cl de lait", "20 g de beurre", *garniture, "sel, poivre"],
            etapes=etapes, prep=10, cuisson=10, base="omelette",
        )


RISOTTOS = [
    ("aux champignons", ["300 g de champignons de Paris"], "Émincer les champignons et les faire revenir à part 5 minutes."),
    ("au potiron", ["400 g de potiron"], "Couper le potiron en petits cubes et les ajouter avec le riz."),
    ("aux asperges", ["400 g d'asperges vertes"], "Couper les asperges en tronçons et les ajouter 8 minutes avant la fin."),
    ("aux petits pois et à la menthe", ["300 g de petits pois", "quelques feuilles de menthe"], "Ajouter les petits pois 8 minutes avant la fin et la menthe ciselée au moment de servir."),
    ("au citron", ["1 citron"], "Ajouter le zeste et le jus du citron en fin de cuisson."),
    ("aux épinards", ["200 g d'épinards"], "Ajouter les épinards hachés 3 minutes avant la fin."),
    ("à la tomate", ["300 g de tomates cerises", "2 c. à soupe de concentré de tomate"], "Ajouter le concentré avec le riz et les tomates cerises coupées en deux à mi-cuisson."),
    ("au poulet", ["300 g de blanc de poulet"], "Couper le poulet en dés et le faire dorer avant le riz."),
    ("aux courgettes", ["2 courgettes"], "Couper les courgettes en petits dés et les ajouter à mi-cuisson."),
    ("à la betterave", ["300 g de betteraves cuites"], "Mixer la moitié des betteraves et couper le reste en dés ; les ajouter à mi-cuisson."),
    ("aux crevettes", ["300 g de crevettes décortiquées"], "Ajouter les crevettes 4 minutes avant la fin."),
    ("au poireau", ["2 poireaux"], "Émincer finement les poireaux et les faire fondre avec l'oignon."),
]


def risottos() -> Iterator[R]:
    for titre, garniture, geste in RISOTTOS:
        yield R(
            titre=f"Risotto {titre}",
            lignes=["300 g de riz arborio", "1 oignon", "2 c. à soupe d'huile d'olive", "10 cl de vin blanc sec", "1 l de bouillon de légumes", *garniture, "50 g de parmesan râpé", "30 g de beurre", "sel, poivre"],
            etapes=[
                "Faire chauffer le bouillon et le garder frémissant.",
                "Émincer l'oignon et le faire revenir dans l'huile d'olive. Ajouter le riz et le nacrer 2 minutes en remuant.",
                "Verser le vin blanc et laisser évaporer.",
                geste,
                "Ajouter le bouillon louche par louche, en remuant, chaque louche étant absorbée avant la suivante (environ 18 minutes).",
                "Hors du feu, ajouter le beurre et le parmesan, mélanger, saler, poivrer et servir aussitôt.",
            ],
            prep=10, cuisson=25, base="risotto",
        )


PATES = [
    ("Spaghettis à l'ail et à l'huile d'olive", "400 g de spaghettis", ["4 gousses d'ail", "6 c. à soupe d'huile d'olive", "1/2 botte de persil", "1 pincée de piment d'Espelette"], "Faire dorer l'ail émincé dans l'huile à feu doux, ajouter le piment, puis mélanger aux pâtes avec le persil haché."),
    ("Penne à la sauce tomate et au basilic", "400 g de penne", ["800 g de tomates pelées", "1 oignon", "2 c. à soupe d'huile d'olive", "quelques feuilles de basilic"], "Faire revenir l'oignon émincé dans l'huile, ajouter les tomates et laisser mijoter 20 minutes, puis le basilic."),
    ("Tagliatelles au saumon", "400 g de tagliatelles", ["200 g de saumon fumé", "20 cl de crème liquide", "1 citron", "1/2 botte d'aneth"], "Chauffer la crème avec le zeste de citron, ajouter le saumon en lanières et l'aneth ciselé."),
    ("Pâtes aux courgettes et au citron", "400 g de penne", ["3 courgettes", "1 citron", "2 c. à soupe d'huile d'olive", "50 g de parmesan râpé"], "Faire sauter les courgettes en dés dans l'huile 8 minutes, ajouter le zeste et le jus du citron."),
    ("Spaghettis à la bolognaise", "400 g de spaghettis", ["400 g de bœuf haché", "1 oignon", "1 carotte", "800 g de tomates pelées", "2 c. à soupe d'huile d'olive"], "Faire revenir l'oignon et la carotte hachés, ajouter le bœuf, puis les tomates, et laisser mijoter 30 minutes."),
    ("Pâtes aux champignons et à la crème", "400 g de tagliatelles", ["400 g de champignons de Paris", "1 échalote", "20 cl de crème liquide", "20 g de beurre"], "Faire revenir l'échalote et les champignons émincés au beurre, puis ajouter la crème."),
    ("Pâtes au brocoli et à l'ail", "400 g de penne", ["400 g de brocoli", "3 gousses d'ail", "4 c. à soupe d'huile d'olive", "50 g de parmesan râpé"], "Cuire le brocoli avec les pâtes, puis le faire sauter avec l'ail émincé dans l'huile."),
    ("Spaghettis aux palourdes", "400 g de spaghettis", ["1 kg de palourdes", "3 gousses d'ail", "10 cl de vin blanc sec", "4 c. à soupe d'huile d'olive", "1/2 botte de persil"], "Faire ouvrir les palourdes avec l'ail, l'huile et le vin blanc à couvert, puis ajouter le persil."),
    ("Pâtes aux épinards et à la ricotta", "400 g de penne", ["300 g d'épinards", "200 g de ricotta", "1 gousse d'ail", "1 pincée de muscade"], "Faire tomber les épinards avec l'ail, puis les mélanger à la ricotta et à la muscade."),
    ("Pâtes au thon et aux câpres", "400 g de penne", ["2 boîtes de thon (280 g)", "2 c. à soupe de câpres", "400 g de tomates pelées", "2 c. à soupe d'huile d'olive"], "Faire chauffer les tomates dans l'huile 10 minutes, puis ajouter le thon émietté et les câpres."),
    ("Pâtes aux légumes du soleil", "400 g de penne", ["1 courgette", "1 aubergine", "1 poivron rouge", "1 oignon", "3 c. à soupe d'huile d'olive"], "Couper les légumes en dés et les faire sauter 15 minutes dans l'huile."),
    ("Pâtes au poulet et au pesto", "400 g de penne", ["300 g de blanc de poulet", "4 c. à soupe de pesto", "1 c. à soupe d'huile d'olive"], "Faire dorer le poulet en dés dans l'huile, puis mélanger aux pâtes avec le pesto."),
    ("Pâtes aux lentilles et à la tomate", "300 g de penne", ["150 g de lentilles corail", "800 g de tomates pelées", "1 oignon", "2 c. à soupe d'huile d'olive", "1 c. à café de cumin en poudre"], "Faire revenir l'oignon, ajouter les lentilles, les tomates, le cumin et 30 cl d'eau, et cuire 20 minutes."),
    ("Pâtes au chou-fleur et aux raisins secs", "400 g de penne", ["1/2 chou-fleur", "40 g de raisins secs", "30 g de pignons de pin", "3 c. à soupe d'huile d'olive"], "Faire dorer les bouquets de chou-fleur précuits dans l'huile avec les raisins et les pignons."),
    ("Pâtes aux crevettes et à l'ail", "400 g de spaghettis", ["300 g de crevettes décortiquées", "3 gousses d'ail", "4 c. à soupe d'huile d'olive", "1 citron"], "Faire sauter les crevettes avec l'ail 3 minutes, puis ajouter le jus du citron."),
    ("Pâtes aux poivrons rôtis", "400 g de penne", ["3 poivrons rouges", "2 gousses d'ail", "3 c. à soupe d'huile d'olive", "50 g de parmesan râpé"], "Rôtir les poivrons au four 25 minutes, les peler, les mixer avec l'ail et l'huile."),
    ("Pâtes à la courge et à la sauge", "400 g de penne", ["500 g de courge butternut", "40 g de beurre", "6 feuilles de sauge", "50 g de parmesan râpé"], "Cuire la courge en dés à la vapeur 12 minutes, puis la faire revenir au beurre avec la sauge."),
    ("Spaghettis aux tomates cerises", "400 g de spaghettis", ["500 g de tomates cerises", "2 gousses d'ail", "4 c. à soupe d'huile d'olive", "quelques feuilles de basilic"], "Faire éclater les tomates cerises dans l'huile avec l'ail 10 minutes."),
    ("Pâtes au jambon et aux petits pois", "400 g de coquillettes", ["150 g de jambon blanc", "200 g de petits pois", "20 cl de crème liquide"], "Cuire les petits pois 8 minutes, puis les chauffer avec le jambon en dés et la crème."),
    ("Pâtes aux sardines", "400 g de spaghettis", ["2 boîtes de sardines à l'huile", "1 oignon", "2 c. à soupe de chapelure", "1 citron"], "Faire revenir l'oignon, ajouter les sardines émiettées et le jus du citron ; parsemer de chapelure grillée."),
    ("Pâtes au chèvre et aux noix", "400 g de penne", ["150 g de fromage de chèvre frais", "50 g de cerneaux de noix", "10 cl de crème liquide"], "Faire fondre le chèvre dans la crème et ajouter les noix concassées."),
    ("Pâtes aux poireaux et aux lardons", "400 g de tagliatelles", ["3 poireaux", "150 g de lardons", "20 cl de crème liquide"], "Faire fondre les poireaux émincés avec les lardons 10 minutes, puis ajouter la crème."),
    ("Pâtes aux aubergines et à la tomate", "400 g de penne", ["2 aubergines", "400 g de tomates pelées", "4 c. à soupe d'huile d'olive", "1 boule de mozzarella"], "Faire dorer les aubergines en dés dans l'huile, ajouter les tomates et cuire 15 minutes ; ajouter la mozzarella en dés."),
    ("Pâtes au saumon et aux épinards", "400 g de tagliatelles", ["2 pavés de saumon", "150 g d'épinards", "20 cl de crème liquide"], "Cuire le saumon en dés 4 minutes, ajouter les épinards et la crème."),
]


def pates() -> Iterator[R]:
    for titre, pate, lignes, sauce in PATES:
        yield R(
            titre=titre,
            lignes=[pate, *lignes, "sel, poivre"],
            etapes=[
                "Porter une grande casserole d'eau salée à ébullition.",
                sauce,
                "Cuire les pâtes selon les indications du paquet, les égoutter en gardant un peu d'eau de cuisson.",
                "Mélanger les pâtes à la sauce, détendre si besoin avec l'eau de cuisson, poivrer et servir.",
            ],
            prep=10, cuisson=20, base="pâtes",
        )


CURRY_PROT = [
    ("poulet", "500 g de blanc de poulet", "Couper le poulet en morceaux et le faire dorer 5 minutes.", 15),
    ("crevettes", "400 g de crevettes décortiquées", "Ajouter les crevettes 5 minutes avant la fin.", 0),
    ("pois chiches", "2 boîtes de pois chiches (800 g)", "Égoutter et rincer les pois chiches, puis les ajouter avec les légumes.", 0),
    ("tofu", "400 g de tofu ferme", "Couper le tofu en cubes et le faire dorer à part.", 0),
    ("cabillaud", "500 g de cabillaud", "Couper le cabillaud en gros morceaux et les ajouter 6 minutes avant la fin.", 0),
    ("lentilles", "200 g de lentilles corail", "Rincer les lentilles et les ajouter avec 30 cl d'eau.", 0),
]
CURRY_LEG = [
    ("courgettes", ["2 courgettes"], "les courgettes en dés"),
    ("patate douce", ["1 patate douce"], "la patate douce en cubes"),
    ("épinards", ["200 g d'épinards"], "les épinards"),
    ("chou-fleur", ["1/2 chou-fleur"], "le chou-fleur en petits bouquets"),
    ("aubergine", ["1 aubergine"], "l'aubergine en dés"),
    ("poivrons", ["2 poivrons"], "les poivrons en lanières"),
    ("potiron", ["500 g de potiron"], "le potiron en cubes"),
]


def curries() -> Iterator[R]:
    for prot, ligne_p, geste_p, _ in CURRY_PROT:
        for leg, lignes_l, geste_l in CURRY_LEG:
            if prot == "lentilles" and leg in ("aubergine",):
                continue
            yield R(
                titre=f"Curry de {prot} au lait de coco et aux {leg}" if leg.endswith("s") else f"Curry de {prot} au lait de coco et à la {leg}" if leg in ("patate douce", "aubergine") else f"Curry de {prot} au lait de coco et au {leg}",
                lignes=[ligne_p, *lignes_l, "1 oignon", "2 gousses d'ail", "1 morceau de gingembre frais", "2 c. à soupe d'huile de colza", "1 c. à soupe de curry", "400 ml de lait de coco", "1/2 botte de coriandre fraîche", "sel"],
                etapes=[
                    "Émincer l'oignon, hacher l'ail et râper le gingembre.",
                    "Faire revenir l'oignon dans l'huile 5 minutes, puis ajouter l'ail, le gingembre et le curry et cuire 1 minute en remuant.",
                    geste_p,
                    f"Ajouter {geste_l} et le lait de coco ; saler, couvrir et laisser mijoter 20 minutes.",
                    "Parsemer de coriandre ciselée et servir avec du riz.",
                ],
                prep=15, cuisson=30, base="curry au lait de coco",
            )


SAUTE_PROT = [
    ("poulet", "500 g de blanc de poulet", "le poulet"),
    ("bœuf", "500 g de rumsteck", "le bœuf"),
    ("porc", "500 g de filet mignon de porc", "le porc"),
    ("tofu", "400 g de tofu ferme", "le tofu"),
    ("crevettes", "400 g de crevettes décortiquées", "les crevettes"),
]
SAUTE_LEG = [
    ("au brocoli", ["400 g de brocoli"]),
    ("aux poivrons et à l'oignon", ["2 poivrons", "1 oignon"]),
    ("au pak-choï et aux champignons", ["2 pak-choï", "200 g de champignons shiitake"]),
    ("aux haricots verts", ["400 g de haricots verts"]),
    ("aux carottes et aux courgettes", ["2 carottes", "2 courgettes"]),
    ("au chou chinois", ["1/2 chou chinois", "2 oignons nouveaux"]),
    ("aux pois gourmands", ["300 g de pois gourmands", "1 poivron rouge"]),
]


def sautes() -> Iterator[R]:
    for prot, ligne_p, le_p in SAUTE_PROT:
        for suffixe, lignes in SAUTE_LEG:
            yield R(
                titre=f"Sauté de {prot} {suffixe}, sauce soja",
                lignes=[ligne_p, *lignes, "2 gousses d'ail", "1 morceau de gingembre frais", "3 c. à soupe de sauce soja", "1 c. à café de fécule de maïs", "2 c. à soupe d'huile de colza", "1 c. à soupe de graines de sésame"],
                etapes=[
                    f"Couper {le_p} en lanières ou en morceaux, et les légumes en morceaux de même taille.",
                    "Hacher l'ail et le gingembre. Délayer la fécule dans la sauce soja avec 5 cl d'eau.",
                    f"Faire sauter {le_p} 3 à 5 minutes à feu vif dans l'huile, au wok ou dans une grande poêle, puis le réserver.",
                    "Faire sauter les légumes 5 minutes avec l'ail et le gingembre, en les gardant croquants.",
                    f"Remettre {le_p}, verser la sauce et mélanger jusqu'à ce qu'elle nappe. Parsemer de sésame et servir avec du riz.",
                ],
                prep=15, cuisson=12, base="sauté au wok",
            )


PAPI_POISSON = [
    ("cabillaud", "4 dos de cabillaud"), ("saumon", "4 pavés de saumon"), ("lieu", "4 filets de lieu"),
    ("colin", "4 filets de colin"), ("truite", "4 filets de truite"), ("merlan", "4 filets de merlan"), ("dorade", "4 filets de dorade"),
]
PAPI_GARN = [
    ("au citron et au fenouil", ["1 bulbe de fenouil", "1 citron", "2 c. à soupe d'huile d'olive"], "Émincer finement le fenouil et couper le citron en rondelles."),
    ("aux tomates et aux olives", ["2 tomates", "50 g d'olives noires", "1 c. à café d'origan", "2 c. à soupe d'huile d'olive"], "Couper les tomates en dés et les olives en rondelles."),
    ("aux poireaux", ["2 poireaux", "10 cl de crème liquide"], "Émincer les poireaux et les faire fondre 8 minutes à la poêle."),
    ("aux courgettes et au thym", ["2 courgettes", "4 brins de thym", "2 c. à soupe d'huile d'olive"], "Couper les courgettes en fines rondelles."),
    ("à l'orange et au gingembre", ["2 oranges", "1 morceau de gingembre frais", "1 c. à soupe de sauce soja"], "Peler une orange à vif et la couper en rondelles ; râper le gingembre et le mélanger au jus de l'autre orange et à la sauce soja."),
]


def papillotes() -> Iterator[R]:
    for poisson, ligne_p in PAPI_POISSON:
        for suffixe, lignes, geste in PAPI_GARN:
            yield R(
                titre=f"Papillote de {poisson} {suffixe}",
                lignes=[ligne_p, *lignes, "sel, poivre"],
                etapes=[
                    "Préchauffer le four à 200 °C.",
                    geste,
                    "Découper 4 grandes feuilles de papier cuisson. Répartir la moitié de la garniture au centre, poser le poisson, puis le reste de la garniture.",
                    "Saler, poivrer, arroser d'huile ou de crème, puis fermer hermétiquement les papillotes.",
                    "Enfourner 15 à 20 minutes selon l'épaisseur du poisson et servir dans la papillote.",
                ],
                prep=15, cuisson=20, base="papillote",
            )


SALADES = [
    ("Salade de lentilles aux carottes et au persil", ["250 g de lentilles vertes", "2 carottes", "1 échalote", "1/2 botte de persil"], "Cuire les lentilles 25 minutes à l'eau non salée ; râper les carottes, ciseler l'échalote et le persil."),
    ("Salade de lentilles au saumon fumé", ["250 g de lentilles vertes", "150 g de saumon fumé", "1 échalote", "1/2 botte d'aneth"], "Cuire les lentilles 25 minutes ; couper le saumon en lanières."),
    ("Salade de lentilles à la feta et aux tomates", ["250 g de lentilles vertes", "150 g de feta", "250 g de tomates cerises", "1 oignon rouge"], "Cuire les lentilles 25 minutes ; couper les tomates en deux et émietter la feta."),
    ("Salade de quinoa à l'avocat et au maïs", ["200 g de quinoa", "2 avocats", "1 boîte de maïs (285 g)", "1 citron vert"], "Cuire le quinoa 12 minutes ; couper les avocats en dés."),
    ("Salade de quinoa aux légumes croquants", ["200 g de quinoa", "1 concombre", "1 poivron rouge", "2 carottes", "1/2 botte de menthe"], "Cuire le quinoa 12 minutes ; couper les légumes en petits dés."),
    ("Salade de quinoa à la betterave et au chèvre", ["200 g de quinoa", "2 betteraves cuites", "100 g de fromage de chèvre frais", "30 g de cerneaux de noix"], "Cuire le quinoa 12 minutes ; couper les betteraves en dés."),
    ("Taboulé à la menthe et au citron", ["200 g de semoule de blé", "4 tomates", "1 concombre", "1 botte de persil", "1/2 botte de menthe", "2 citrons"], "Faire gonfler la semoule dans 20 cl d'eau bouillante ; couper les légumes en petits dés et ciseler les herbes."),
    ("Salade de boulgour aux pois chiches", ["200 g de boulgour", "1 boîte de pois chiches (400 g)", "2 tomates", "1/2 botte de persil"], "Cuire le boulgour 12 minutes ; égoutter les pois chiches."),
    ("Salade de boulgour aux légumes grillés", ["200 g de boulgour", "1 courgette", "1 poivron", "1 aubergine"], "Cuire le boulgour 12 minutes ; griller les légumes en tranches à la poêle."),
    ("Salade de pâtes au thon et aux tomates", ["300 g de penne", "1 boîte de thon (140 g)", "250 g de tomates cerises", "50 g d'olives noires"], "Cuire les pâtes, les rincer à l'eau froide ; émietter le thon."),
    ("Salade de pâtes au poulet et au pesto", ["300 g de penne", "250 g de blanc de poulet", "3 c. à soupe de pesto", "100 g de roquette"], "Cuire les pâtes et le poulet en dés, puis laisser refroidir."),
    ("Salade de pâtes à la grecque", ["300 g de penne", "150 g de feta", "1 concombre", "1 oignon rouge", "50 g d'olives noires"], "Cuire les pâtes, les rincer ; couper le concombre en dés et émietter la feta."),
    ("Salade de riz au thon et aux œufs", ["250 g de riz", "1 boîte de thon (140 g)", "3 œufs", "2 tomates", "1 boîte de maïs (285 g)"], "Cuire le riz et les œufs 10 minutes ; écaler et couper les œufs."),
    ("Salade de riz aux crevettes et à l'ananas", ["250 g de riz", "250 g de crevettes cuites", "200 g d'ananas", "1 poivron rouge"], "Cuire le riz et le laisser refroidir ; couper l'ananas et le poivron en dés."),
    ("Salade de pois chiches au concombre", ["2 boîtes de pois chiches (800 g)", "1 concombre", "1 oignon rouge", "1/2 botte de coriandre fraîche", "1 citron"], "Égoutter les pois chiches ; couper le concombre en dés."),
    ("Salade de pommes de terre aux harengs", ["800 g de pommes de terre", "4 filets de hareng fumé", "1 oignon rouge", "1/2 botte de persil"], "Cuire les pommes de terre 20 minutes ; couper les harengs en morceaux."),
    ("Salade de pommes de terre à la moutarde", ["800 g de pommes de terre", "2 échalotes", "1/2 botte de ciboulette", "1 c. à soupe de moutarde de Dijon"], "Cuire les pommes de terre 20 minutes et les couper tièdes."),
    ("Salade de haricots verts aux noisettes", ["500 g de haricots verts", "40 g de noisettes", "1 échalote"], "Cuire les haricots verts 8 minutes à l'eau salée et les refroidir ; concasser les noisettes."),
    ("Salade de chou rouge à la pomme", ["1/2 chou rouge", "2 pommes", "30 g de raisins secs"], "Émincer très finement le chou et râper les pommes."),
    ("Salade de carottes au cumin et à l'orange", ["600 g de carottes", "2 oranges", "1 c. à café de cumin en poudre", "1/2 botte de coriandre fraîche"], "Râper les carottes et prélever les suprêmes des oranges."),
    ("Salade de concombre au yaourt et à la menthe", ["2 concombres", "2 yaourts nature", "1/2 botte de menthe", "1 gousse d'ail"], "Couper le concombre en fines rondelles et ciseler la menthe."),
    ("Salade d'endives aux noix et au roquefort", ["6 endives", "50 g de cerneaux de noix", "100 g de roquefort", "1 poire"], "Émincer les endives, couper la poire en lamelles et émietter le roquefort."),
    ("Salade de mâche aux betteraves", ["150 g de mâche", "2 betteraves cuites", "30 g de cerneaux de noix"], "Couper les betteraves en dés."),
    ("Salade de fenouil à l'orange", ["2 bulbes de fenouil", "2 oranges", "50 g d'olives noires"], "Émincer finement le fenouil et peler les oranges à vif."),
]


def salades() -> Iterator[R]:
    for titre, lignes, geste in SALADES:
        vinaigre = "1 c. à soupe de jus de citron" if "citron" in " ".join(lignes) else "2 c. à soupe de vinaigre de vin"
        yield R(
            titre=titre,
            lignes=[*lignes, "4 c. à soupe d'huile d'olive", vinaigre, "sel, poivre"],
            etapes=[
                geste,
                "Préparer la vinaigrette en mélangeant l'huile, l'acidité, le sel et le poivre.",
                "Réunir tous les ingrédients dans un saladier, arroser de vinaigrette et mélanger délicatement.",
                "Laisser reposer 15 minutes au frais avant de servir.",
            ],
            prep=20, cuisson=20 if "Cuire" in geste else 0, repos=15, base="salade composée",
        )


SOUPES = [
    ("Minestrone", ["1 oignon", "2 carottes", "150 g de céleri branche", "1 courgette", "400 g de tomates pelées", "1 boîte de haricots blancs (400 g)", "80 g de petites pâtes", "1,5 l de bouillon de légumes", "2 c. à soupe d'huile d'olive", "50 g de parmesan râpé", "sel, poivre"],
     ["Couper tous les légumes en petits dés.", "Les faire revenir 5 minutes dans l'huile d'olive.", "Ajouter les tomates et le bouillon, et cuire 20 minutes.", "Ajouter les haricots et les pâtes et cuire encore 10 minutes.", "Servir parsemé de parmesan."], 40),
    ("Soupe de lentilles au cumin", ["250 g de lentilles corail", "1 oignon", "2 carottes", "1 c. à café de cumin en poudre", "1,2 l de bouillon de légumes", "1 citron", "2 c. à soupe d'huile d'olive", "sel"],
     ["Émincer l'oignon et couper les carottes en rondelles.", "Les faire revenir dans l'huile avec le cumin.", "Ajouter les lentilles rincées et le bouillon, et cuire 20 minutes.", "Mixer et servir avec un filet de jus de citron."], 25),
    ("Soupe de pois cassés", ["400 g de pois cassés", "1 oignon", "2 carottes", "100 g de lardons", "1 bouquet garni", "sel, poivre"],
     ["Rincer les pois cassés.", "Faire revenir les lardons et l'oignon émincé.", "Ajouter les pois, les carottes, le bouquet garni et 1,5 l d'eau, et cuire 1 heure à petits frémissements.", "Retirer le bouquet garni, mixer et assaisonner."], 60),
    ("Soupe à l'oignon gratinée", ["6 oignons", "50 g de beurre", "1 c. à soupe de farine", "1,5 l de bouillon de bœuf", "8 tranches de baguette", "100 g de gruyère râpé", "sel, poivre"],
     ["Émincer finement les oignons et les faire dorer 20 minutes au beurre à feu doux.", "Saupoudrer de farine, mélanger, puis verser le bouillon et cuire 20 minutes.", "Verser dans des bols allant au four, poser les tranches de pain et couvrir de gruyère.", "Gratiner 5 minutes sous le gril."], 45),
    ("Gaspacho", ["1 kg de tomates", "1 concombre", "1 poivron rouge", "1 gousse d'ail", "4 c. à soupe d'huile d'olive", "2 c. à soupe de vinaigre de Xérès", "sel, poivre"],
     ["Couper les légumes en morceaux.", "Les mixer finement avec l'ail, l'huile et le vinaigre.", "Saler, poivrer et réserver au moins 2 heures au frais."], 0),
    ("Soupe de poulet aux vermicelles", ["2 blancs de poulet", "2 carottes", "1 poireau", "80 g de vermicelles", "1,5 l de bouillon de volaille", "1/2 botte de persil", "sel, poivre"],
     ["Couper les carottes en rondelles et émincer le poireau.", "Pocher les blancs de poulet 15 minutes dans le bouillon avec les légumes.", "Retirer le poulet, l'effilocher et le remettre dans la soupe.", "Ajouter les vermicelles et cuire 5 minutes. Parsemer de persil."], 25),
    ("Soupe de haricots blancs au romarin", ["2 boîtes de haricots blancs (800 g)", "1 oignon", "2 gousses d'ail", "2 branches de romarin", "1 l de bouillon de légumes", "3 c. à soupe d'huile d'olive", "sel, poivre"],
     ["Faire revenir l'oignon et l'ail émincés dans l'huile.", "Ajouter les haricots égouttés, le romarin et le bouillon, et cuire 15 minutes.", "Retirer le romarin et mixer la moitié de la soupe pour l'épaissir."], 20),
    ("Soupe miso aux légumes", ["2 c. à soupe de miso", "100 g de tofu soyeux", "2 oignons nouveaux", "100 g de champignons shiitake", "1 c. à soupe de wakamé", "1 l d'eau"],
     ["Réhydrater le wakamé 5 minutes dans de l'eau froide.", "Faire frémir l'eau avec les champignons émincés 5 minutes.", "Hors du feu, délayer le miso dans un peu de bouillon puis l'ajouter.", "Ajouter le tofu en dés, le wakamé et les oignons nouveaux émincés."], 10),
]


def soupes() -> Iterator[R]:
    for titre, lignes, etapes, cuisson in SOUPES:
        yield R(titre=titre, lignes=lignes, etapes=etapes, prep=20, cuisson=cuisson,
                repos=120 if titre == "Gaspacho" else 0, base="soupe")


PLATS = [
    ("Boulettes de bœuf à la sauce tomate", ["500 g de bœuf haché", "1 œuf", "50 g de chapelure", "1 oignon", "800 g de tomates pelées", "2 c. à soupe d'huile d'olive", "1/2 botte de persil", "sel, poivre"],
     ["Mélanger le bœuf, l'œuf, la chapelure, la moitié de l'oignon haché et le persil ; saler, poivrer.", "Former des boulettes et les faire dorer dans l'huile.", "Ajouter le reste de l'oignon et les tomates, et laisser mijoter 25 minutes."], 30),
    ("Boulettes d'agneau aux épices", ["500 g d'agneau haché", "1 oignon", "1 c. à café de cumin en poudre", "1 c. à café de coriandre en poudre", "1/2 botte de menthe", "2 c. à soupe d'huile d'olive", "sel, poivre"],
     ["Mélanger l'agneau, l'oignon râpé, les épices et la menthe ciselée.", "Former des boulettes allongées.", "Les cuire 10 à 12 minutes à la poêle dans l'huile, en les retournant."], 12),
    ("Hachis parmentier au potiron", ["400 g de bœuf haché", "600 g de potiron", "400 g de pommes de terre", "1 oignon", "30 g de beurre", "50 g d'emmental râpé", "sel, poivre"],
     ["Cuire le potiron et les pommes de terre 20 minutes à l'eau salée, puis les écraser avec le beurre.", "Faire revenir l'oignon et le bœuf.", "Étaler la viande dans un plat, couvrir de purée et d'emmental.", "Gratiner 20 minutes à 200 °C."], 40),
    ("Chili con carne aux haricots rouges", ["500 g de bœuf haché", "2 boîtes de haricots rouges (800 g)", "800 g de tomates pelées", "1 oignon", "1 poivron rouge", "1 c. à café de cumin en poudre", "1 c. à café de paprika", "2 c. à soupe d'huile d'olive", "sel"],
     ["Faire revenir l'oignon et le poivron émincés dans l'huile.", "Ajouter la viande et la faire dorer.", "Ajouter les épices, les tomates et les haricots égouttés, et laisser mijoter 40 minutes."], 45),
    ("Chili végétarien aux patates douces", ["2 patates douces", "2 boîtes de haricots rouges (800 g)", "800 g de tomates pelées", "1 oignon", "1 c. à café de cumin en poudre", "1 c. à café de paprika fumé", "2 c. à soupe d'huile d'olive", "sel"],
     ["Faire revenir l'oignon émincé dans l'huile avec les épices.", "Ajouter les patates douces en cubes, les tomates et les haricots égouttés.", "Laisser mijoter 35 minutes, jusqu'à ce que les patates douces soient tendres."], 40),
    ("Tajine de poulet au citron confit et aux olives", ["1 poulet en morceaux", "2 citrons confits", "100 g d'olives vertes", "2 oignons", "1 c. à café de gingembre en poudre", "1 dosette de safran", "1/2 botte de coriandre fraîche", "3 c. à soupe d'huile d'olive", "sel, poivre"],
     ["Faire dorer les morceaux de poulet dans l'huile, puis les oignons émincés.", "Ajouter les épices et 30 cl d'eau, couvrir et cuire 40 minutes.", "Ajouter les citrons confits en quartiers et les olives, et cuire encore 15 minutes.", "Parsemer de coriandre."], 60),
    ("Tajine d'agneau aux pruneaux", ["1 kg d'épaule d'agneau", "250 g de pruneaux", "2 oignons", "1 c. à café de cannelle", "1 c. à café de gingembre en poudre", "1 c. à soupe de miel", "30 g d'amandes", "3 c. à soupe d'huile d'olive", "sel, poivre"],
     ["Couper l'agneau en morceaux et le faire dorer dans l'huile avec les oignons émincés.", "Ajouter les épices et 50 cl d'eau, couvrir et cuire 1 heure 15.", "Ajouter les pruneaux et le miel, et cuire encore 20 minutes.", "Servir parsemé d'amandes grillées."], 95),
    ("Tajine de légumes aux pois chiches", ["2 carottes", "2 courgettes", "1 navet", "1 boîte de pois chiches (400 g)", "1 oignon", "1 c. à café de ras el hanout", "400 g de tomates pelées", "3 c. à soupe d'huile d'olive", "sel"],
     ["Faire revenir l'oignon émincé dans l'huile avec le ras el hanout.", "Ajouter les légumes en gros morceaux, les tomates et 20 cl d'eau.", "Couvrir et cuire 35 minutes, puis ajouter les pois chiches et cuire encore 10 minutes."], 45),
    ("Poulet rôti au citron et au thym", ["1 poulet entier", "2 citrons", "1 bouquet de thym", "4 gousses d'ail", "30 g de beurre", "sel, poivre"],
     ["Préchauffer le four à 200 °C.", "Glisser un citron coupé en deux, l'ail et la moitié du thym dans le poulet.", "Badigeonner le poulet de beurre, saler, poivrer et ajouter le reste du thym autour.", "Rôtir 1 heure 15 en arrosant régulièrement avec le jus, puis arroser du jus du second citron."], 75),
    ("Poulet basquaise aux poivrons", ["4 cuisses de poulet", "3 poivrons", "2 oignons", "400 g de tomates pelées", "2 gousses d'ail", "1 c. à café de piment d'Espelette", "3 c. à soupe d'huile d'olive", "sel"],
     ["Faire dorer les cuisses de poulet dans l'huile, puis les réserver.", "Faire revenir les oignons et les poivrons émincés.", "Ajouter l'ail, les tomates et le piment, puis remettre le poulet.", "Couvrir et laisser mijoter 45 minutes."], 55),
    ("Blanquette de veau", ["1 kg de veau à blanquette", "2 carottes", "1 oignon", "250 g de champignons de Paris", "1 bouquet garni", "40 g de beurre", "40 g de farine", "20 cl de crème fraîche", "1 jaune d'œuf", "1 citron", "sel, poivre"],
     ["Couvrir le veau d'eau froide, porter à ébullition et écumer.", "Ajouter les carottes, l'oignon et le bouquet garni, et cuire 1 heure 30 à frémissements.", "Faire un roux avec le beurre et la farine, le mouiller avec 50 cl de bouillon de cuisson.", "Ajouter les champignons, puis hors du feu la crème mélangée au jaune et au jus de citron.", "Remettre la viande et les carottes dans la sauce et servir avec du riz."], 100),
    ("Bœuf bourguignon", ["1,2 kg de bœuf à braiser", "75 cl de vin rouge", "150 g de lardons", "2 oignons", "2 carottes", "250 g de champignons de Paris", "2 c. à soupe de farine", "1 bouquet garni", "2 c. à soupe d'huile d'olive", "sel, poivre"],
     ["Faire dorer la viande en morceaux dans l'huile, puis les lardons et les oignons.", "Saupoudrer de farine, mélanger, puis verser le vin.", "Ajouter les carottes et le bouquet garni, couvrir et cuire 2 heures 30 à feu doux.", "Ajouter les champignons 20 minutes avant la fin."], 150),
    ("Filet mignon de porc à la moutarde", ["2 filets mignons de porc", "2 c. à soupe de moutarde à l'ancienne", "20 cl de crème fraîche", "1 échalote", "20 g de beurre", "sel, poivre"],
     ["Faire dorer les filets mignons au beurre sur toutes les faces.", "Ajouter l'échalote hachée, couvrir et cuire 20 minutes à feu doux.", "Retirer la viande, ajouter la moutarde et la crème et faire réduire.", "Trancher la viande et la napper de sauce."], 25),
    ("Escalopes de dinde à la crème et aux champignons", ["4 escalopes de dinde", "300 g de champignons de Paris", "20 cl de crème fraîche", "1 échalote", "20 g de beurre", "sel, poivre"],
     ["Faire dorer les escalopes au beurre 4 minutes de chaque côté, puis les réserver.", "Faire revenir l'échalote et les champignons émincés.", "Ajouter la crème, laisser réduire, puis remettre les escalopes 2 minutes."], 20),
    ("Saumon poêlé, sauce au yaourt et à l'aneth", ["4 pavés de saumon", "2 yaourts nature", "1/2 botte d'aneth", "1 citron", "1 c. à soupe d'huile d'olive", "sel, poivre"],
     ["Mélanger les yaourts, l'aneth ciselé et le jus de citron ; saler, poivrer.", "Cuire les pavés de saumon côté peau 6 minutes dans l'huile, puis 2 minutes de l'autre côté.", "Servir avec la sauce froide."], 10),
    ("Cabillaud au four en croûte d'herbes", ["4 dos de cabillaud", "50 g de chapelure", "1/2 botte de persil", "1 gousse d'ail", "30 g de beurre", "1 citron", "sel, poivre"],
     ["Préchauffer le four à 200 °C.", "Mélanger la chapelure, le persil et l'ail hachés et le beurre mou.", "Poser le cabillaud dans un plat, saler, poivrer et couvrir de ce mélange.", "Enfourner 15 minutes et servir avec le citron."], 15),
    ("Lentilles aux saucisses", ["300 g de lentilles vertes", "4 saucisses de Toulouse", "2 carottes", "1 oignon", "1 bouquet garni", "sel, poivre"],
     ["Faire dorer les saucisses à la cocotte, puis les réserver.", "Faire revenir l'oignon et les carottes en dés.", "Ajouter les lentilles, le bouquet garni et 1 l d'eau, et cuire 25 minutes.", "Remettre les saucisses et cuire encore 10 minutes ; saler en fin de cuisson."], 40),
    ("Dahl de lentilles corail", ["300 g de lentilles corail", "1 oignon", "2 gousses d'ail", "1 morceau de gingembre frais", "1 c. à café de curcuma", "1 c. à café de cumin en poudre", "400 ml de lait de coco", "400 g de tomates pelées", "2 c. à soupe d'huile de colza", "sel"],
     ["Faire revenir l'oignon, l'ail et le gingembre hachés dans l'huile avec les épices.", "Ajouter les lentilles rincées, les tomates, le lait de coco et 30 cl d'eau.", "Cuire 25 minutes à feu doux en remuant ; saler."], 30),
    ("Dahl d'épinards", ["250 g de lentilles corail", "200 g d'épinards", "1 oignon", "2 gousses d'ail", "1 c. à café de garam masala", "1 c. à café de curcuma", "2 c. à soupe d'huile de colza", "sel"],
     ["Faire revenir l'oignon et l'ail dans l'huile avec les épices.", "Ajouter les lentilles et 80 cl d'eau, et cuire 20 minutes.", "Ajouter les épinards et cuire encore 3 minutes."], 25),
    ("Pois chiches rôtis aux épices", ["2 boîtes de pois chiches (800 g)", "2 c. à soupe d'huile d'olive", "1 c. à café de paprika fumé", "1 c. à café de cumin en poudre", "sel"],
     ["Préchauffer le four à 200 °C.", "Égoutter, rincer et bien sécher les pois chiches.", "Les mélanger avec l'huile et les épices, et les étaler sur une plaque.", "Rôtir 30 minutes en remuant à mi-cuisson, jusqu'à ce qu'ils soient croustillants."], 30),
    ("Houmous", ["1 boîte de pois chiches (400 g)", "2 c. à soupe de tahini", "1 citron", "1 gousse d'ail", "3 c. à soupe d'huile d'olive", "1 c. à café de cumin en poudre", "sel"],
     ["Égoutter les pois chiches en gardant un peu de liquide.", "Les mixer avec le tahini, le jus du citron, l'ail, le cumin et le sel.", "Ajouter l'huile en filet puis un peu de liquide jusqu'à obtenir une texture lisse."], 0),
    ("Galettes de courgettes à la feta", ["3 courgettes", "100 g de feta", "2 œufs", "60 g de farine", "1/2 botte de menthe", "3 c. à soupe d'huile d'olive", "sel, poivre"],
     ["Râper les courgettes, les saler et les presser pour retirer l'eau.", "Mélanger avec la feta émiettée, les œufs, la farine et la menthe ciselée.", "Cuire des petites galettes 3 minutes de chaque côté dans l'huile chaude."], 15),
    ("Galettes de pommes de terre", ["800 g de pommes de terre", "1 oignon", "2 œufs", "2 c. à soupe de farine", "4 c. à soupe d'huile de tournesol", "sel, poivre"],
     ["Râper les pommes de terre et l'oignon, puis les presser dans un torchon.", "Mélanger avec les œufs et la farine ; saler, poivrer.", "Cuire des galettes fines 4 minutes de chaque côté dans l'huile chaude."], 20),
    ("Galettes de carottes au cumin", ["500 g de carottes", "2 œufs", "60 g de farine", "1 c. à café de cumin en poudre", "3 c. à soupe d'huile d'olive", "sel"],
     ["Râper finement les carottes.", "Les mélanger avec les œufs, la farine et le cumin ; saler.", "Cuire des galettes 3 minutes de chaque côté dans l'huile chaude."], 15),
    ("Falafels maison", ["250 g de pois chiches secs", "1 oignon", "2 gousses d'ail", "1 botte de persil", "1/2 botte de coriandre fraîche", "1 c. à café de cumin en poudre", "1 c. à café de bicarbonate de soude", "huile de friture", "sel"],
     ["Faire tremper les pois chiches 12 heures dans l'eau froide, puis les égoutter.", "Les mixer grossièrement avec l'oignon, l'ail, les herbes, le cumin, le bicarbonate et le sel.", "Former des boulettes et les frire 3 à 4 minutes dans l'huile chaude."], 15),
    ("Pizza margherita aux tomates cerises", ["1 pâte à pizza", "200 g de coulis de tomate", "1 boule de mozzarella", "200 g de tomates cerises", "quelques feuilles de basilic", "2 c. à soupe d'huile d'olive", "sel"],
     ["Préchauffer le four à 250 °C.", "Étaler la pâte sur une plaque et la napper de coulis.", "Ajouter la mozzarella en tranches et les tomates cerises coupées en deux.", "Arroser d'huile et enfourner 12 minutes. Ajouter le basilic à la sortie du four."], 12),
    ("Pizza aux champignons et au jambon", ["1 pâte à pizza", "200 g de coulis de tomate", "200 g de champignons de Paris", "150 g de jambon blanc", "1 boule de mozzarella", "1 c. à café d'origan"],
     ["Préchauffer le four à 250 °C.", "Étaler la pâte et la napper de coulis.", "Garnir de champignons émincés, de jambon et de mozzarella, puis d'origan.", "Enfourner 12 minutes."], 12),
    ("Pizza aux légumes grillés", ["1 pâte à pizza", "200 g de coulis de tomate", "1 courgette", "1 poivron rouge", "1 aubergine", "1 boule de mozzarella", "2 c. à soupe d'huile d'olive"],
     ["Préchauffer le four à 250 °C.", "Griller les légumes en tranches fines à la poêle avec l'huile.", "Étaler la pâte, la napper de coulis, puis garnir de légumes et de mozzarella.", "Enfourner 12 minutes."], 20),
    ("Pizza blanche au chèvre et au miel", ["1 pâte à pizza", "15 cl de crème fraîche", "150 g de fromage de chèvre", "2 c. à soupe de miel", "1 c. à café de thym"],
     ["Préchauffer le four à 250 °C.", "Étaler la pâte et la napper de crème.", "Ajouter le chèvre en rondelles et le thym.", "Enfourner 12 minutes, puis arroser de miel."], 12),
    ("Tarte fine aux tomates et au pesto", ["1 pâte feuilletée", "4 tomates", "3 c. à soupe de pesto", "2 c. à soupe d'huile d'olive", "sel, poivre"],
     ["Préchauffer le four à 200 °C.", "Étaler la pâte sur une plaque et la tartiner de pesto.", "Disposer les tomates en fines rondelles, arroser d'huile, saler et poivrer.", "Enfourner 25 minutes."], 25),
    ("Tarte fine aux oignons et aux anchois", ["1 pâte feuilletée", "6 oignons", "8 filets d'anchois", "50 g d'olives noires", "2 c. à soupe d'huile d'olive", "1 c. à café de thym"],
     ["Faire fondre les oignons émincés 30 minutes dans l'huile à feu doux.", "Étaler la pâte, la couvrir d'oignons, puis disposer les anchois et les olives.", "Parsemer de thym et cuire 25 minutes à 200 °C."], 55),
    ("Croque-monsieur au four", ["8 tranches de pain de mie", "4 tranches de jambon blanc", "100 g d'emmental râpé", "20 g de beurre", "10 cl de crème fraîche"],
     ["Préchauffer le four à 200 °C.", "Beurrer les tranches de pain, poser le jambon et un peu d'emmental entre deux tranches.", "Napper le dessus de crème et du reste de fromage.", "Enfourner 12 minutes."], 12),
    ("Wraps au poulet et aux crudités", ["4 tortillas de blé", "300 g de blanc de poulet", "1 avocat", "2 tomates", "1 laitue", "4 c. à soupe de fromage blanc", "1 citron vert", "sel, poivre"],
     ["Cuire le poulet en lanières à la poêle 6 minutes.", "Écraser l'avocat avec le jus du citron vert ; couper les tomates en dés.", "Tartiner les tortillas de fromage blanc, garnir et rouler serré."], 6),
    ("Galettes de sarrasin jambon, œuf, fromage", ["250 g de farine de sarrasin", "1 œuf", "50 cl d'eau", "4 tranches de jambon blanc", "4 œufs", "100 g d'emmental râpé", "20 g de beurre", "sel"],
     ["Mélanger la farine, l'œuf, l'eau et le sel ; laisser reposer 1 heure.", "Cuire une galette fine dans une poêle beurrée.", "Casser un œuf au centre, ajouter le jambon et l'emmental, et replier les bords.", "Cuire jusqu'à ce que le blanc soit pris."], 20),
    ("Riz cantonais aux petits pois", ["300 g de riz", "3 œufs", "150 g de jambon blanc", "150 g de petits pois", "3 oignons nouveaux", "2 c. à soupe de sauce soja", "2 c. à soupe d'huile de colza"],
     ["Cuire le riz la veille, ou le laisser bien refroidir.", "Cuire les œufs battus en omelette fine, puis la couper en lanières.", "Faire sauter le riz dans l'huile avec les petits pois, le jambon en dés et les oignons nouveaux.", "Ajouter l'omelette et la sauce soja et mélanger."], 15),
    ("Nouilles sautées aux légumes", ["300 g de nouilles chinoises", "2 carottes", "1 poivron rouge", "200 g de germes de soja", "2 gousses d'ail", "3 c. à soupe de sauce soja", "2 c. à soupe d'huile de colza"],
     ["Cuire les nouilles selon le paquet et les égoutter.", "Faire sauter l'ail et les légumes en julienne 4 minutes à feu vif.", "Ajouter les nouilles, les germes de soja et la sauce soja, et faire sauter 2 minutes."], 10),
    ("Gratin de pâtes au jambon", ["400 g de coquillettes", "200 g de jambon blanc", "40 g de beurre", "40 g de farine", "60 cl de lait", "100 g d'emmental râpé", "sel, poivre"],
     ["Cuire les pâtes et les égoutter.", "Préparer une béchamel avec le beurre, la farine et le lait.", "Mélanger pâtes, jambon en dés et béchamel dans un plat, et couvrir d'emmental.", "Gratiner 20 minutes à 200 °C."], 30),
    ("Gratin de pâtes au brocoli", ["400 g de penne", "400 g de brocoli", "20 cl de crème fraîche", "100 g de comté râpé", "sel, poivre"],
     ["Cuire les pâtes avec le brocoli en petits bouquets, puis égoutter.", "Mélanger avec la crème dans un plat et couvrir de comté.", "Gratiner 20 minutes à 200 °C."], 30),
    ("Gratin dauphinois aux poireaux", ["1 kg de pommes de terre", "2 poireaux", "50 cl de lait", "20 cl de crème fraîche", "1 gousse d'ail", "1 pincée de muscade", "sel, poivre"],
     ["Éplucher les pommes de terre et les couper en fines rondelles ; émincer les poireaux.", "Les cuire 10 minutes dans le lait avec l'ail, la muscade, le sel et le poivre.", "Verser dans un plat, ajouter la crème et cuire 1 heure à 170 °C."], 70),
    ("Ratatouille au four", ["2 aubergines", "3 courgettes", "2 poivrons", "4 tomates", "2 oignons", "3 gousses d'ail", "1 c. à soupe d'herbes de Provence", "5 c. à soupe d'huile d'olive", "sel, poivre"],
     ["Préchauffer le four à 180 °C.", "Couper tous les légumes en morceaux.", "Les mélanger dans un grand plat avec l'ail, les herbes et l'huile ; saler, poivrer.", "Cuire 1 heure en remuant de temps en temps."], 60),
    ("Shakshuka", ["6 œufs", "800 g de tomates pelées", "2 poivrons rouges", "1 oignon", "2 gousses d'ail", "1 c. à café de cumin en poudre", "1 c. à café de paprika", "3 c. à soupe d'huile d'olive", "1/2 botte de coriandre fraîche", "sel"],
     ["Faire revenir l'oignon, l'ail et les poivrons émincés dans l'huile 10 minutes.", "Ajouter les épices et les tomates, et laisser mijoter 15 minutes.", "Creuser 6 puits, y casser les œufs, couvrir et cuire 6 à 8 minutes.", "Parsemer de coriandre."], 35),
    ("Œufs cocotte aux épinards", ["4 œufs", "150 g d'épinards", "10 cl de crème fraîche", "20 g de beurre", "sel, poivre"],
     ["Préchauffer le four à 180 °C.", "Faire tomber les épinards au beurre.", "Les répartir dans 4 ramequins, ajouter une cuillerée de crème et casser un œuf dans chacun.", "Cuire 12 minutes au bain-marie au four."], 15),
    ("Croquettes de thon", ["2 boîtes de thon (280 g)", "400 g de pommes de terre", "1 œuf", "50 g de chapelure", "1/2 botte de persil", "3 c. à soupe d'huile de tournesol", "sel, poivre"],
     ["Cuire les pommes de terre et les écraser.", "Mélanger avec le thon émietté, l'œuf et le persil ; saler, poivrer.", "Former des croquettes, les rouler dans la chapelure et les dorer à la poêle."], 30),
    ("Brochettes de poulet marinées au yaourt", ["600 g de blanc de poulet", "2 yaourts nature", "1 citron", "2 gousses d'ail", "1 c. à café de paprika", "1 c. à café de cumin en poudre", "sel"],
     ["Couper le poulet en cubes.", "Le mélanger au yaourt, au jus de citron, à l'ail et aux épices, et laisser mariner 2 heures au frais.", "Enfiler sur des brochettes et griller 10 à 12 minutes en les retournant."], 12),
    ("Porc au caramel", ["600 g d'échine de porc", "4 c. à soupe de sucre", "3 c. à soupe de nuoc-mâm", "2 échalotes", "2 gousses d'ail", "1 c. à soupe d'huile de colza"],
     ["Couper le porc en cubes.", "Faire un caramel brun avec le sucre et 3 c. à soupe d'eau, puis ajouter 10 cl d'eau chaude.", "Faire dorer le porc dans l'huile avec l'ail et les échalotes.", "Ajouter le caramel et le nuoc-mâm, et cuire 40 minutes à feu doux, jusqu'à ce que la sauce soit sirupeuse."], 45),
    ("Poulet teriyaki", ["600 g de cuisses de poulet", "4 c. à soupe de sauce soja", "2 c. à soupe de mirin", "1 c. à soupe de sucre", "1 c. à soupe de graines de sésame", "1 c. à soupe d'huile de colza"],
     ["Mélanger la sauce soja, le mirin et le sucre.", "Faire dorer le poulet en morceaux dans l'huile.", "Ajouter la sauce et cuire jusqu'à ce qu'elle nappe le poulet.", "Parsemer de sésame."], 20),
]


def plats() -> Iterator[R]:
    for titre, lignes, etapes, cuisson in PLATS:
        repos = 120 if "mariner 2 heures" in " ".join(etapes) else 60 if "reposer 1 heure" in " ".join(etapes) else 720 if "12 heures" in " ".join(etapes) else 0
        yield R(titre=titre, lignes=lignes, etapes=etapes, prep=20, cuisson=cuisson, repos=repos, base="plat")


# --- Desserts --------------------------------------------------------------------------------

FRUITS_CUITS = [
    ("pommes", "de pommes", "1 kg de pommes", "les pommes", "Éplucher les pommes et les couper en morceaux."),
    ("poires", "de poires", "1 kg de poires", "les poires", "Éplucher les poires et les couper en morceaux."),
    ("abricots", "d'abricots", "800 g d'abricots", "les abricots", "Dénoyauter les abricots et les couper en deux."),
    ("prunes", "de prunes", "800 g de prunes", "les prunes", "Dénoyauter les prunes et les couper en deux."),
    ("rhubarbe", "de rhubarbe", "800 g de rhubarbe", "la rhubarbe", "Éplucher la rhubarbe et la couper en tronçons."),
    ("pêches", "de pêches", "800 g de pêches", "les pêches", "Peler les pêches, les dénoyauter et les couper en quartiers."),
    ("fruits rouges", "de fruits rouges", "600 g de fruits rouges mélangés", "les fruits rouges", "Rincer rapidement les fruits rouges."),
    ("pommes et poires", "de pommes et poires", "500 g de pommes", "les fruits", "Éplucher les pommes et les poires et les couper en morceaux."),
    ("mirabelles", "de mirabelles", "800 g de mirabelles", "les mirabelles", "Dénoyauter les mirabelles."),
    ("mangue", "de mangue", "2 mangues", "la mangue", "Peler les mangues et couper la chair en cubes."),
    ("cerises", "de cerises", "800 g de cerises", "les cerises", "Équeuter et dénoyauter les cerises."),
    ("bananes", "de bananes", "4 bananes", "les bananes", "Peler les bananes et les couper en rondelles."),
]


def crumbles() -> Iterator[R]:
    for nom, de, ligne, les, prep in FRUITS_CUITS:
        lignes = [ligne] + (["500 g de poires"] if nom == "pommes et poires" else [])
        yield R(
            titre=f"Crumble {de}",
            lignes=[*lignes, "150 g de farine", "100 g de beurre", "100 g de sucre roux", "1 c. à café de cannelle"],
            etapes=[
                "Préchauffer le four à 180 °C.",
                prep,
                f"Disposer {les} dans un plat beurré et saupoudrer de cannelle.",
                "Mélanger du bout des doigts la farine, le sucre et le beurre froid en dés jusqu'à obtenir une pâte sableuse.",
                f"Répartir sur {les} et enfourner 35 minutes, jusqu'à ce que le dessus soit doré.",
            ],
            prep=20, cuisson=35, base="crumble",
        )


def compotes() -> Iterator[R]:
    for nom, de, ligne, les, prep in FRUITS_CUITS:
        if nom in ("bananes", "fruits rouges", "cerises"):
            continue
        lignes = [ligne] + (["500 g de poires"] if nom == "pommes et poires" else [])
        yield R(
            titre=f"Compote {de} à la vanille",
            lignes=[*lignes, "40 g de sucre", "1 gousse de vanille", "10 cl d'eau"],
            etapes=[
                prep,
                f"Mettre {les} dans une casserole avec l'eau, le sucre et la gousse de vanille fendue.",
                "Couvrir et cuire 20 minutes à feu doux en remuant de temps en temps.",
                "Retirer la vanille, écraser à la fourchette ou mixer selon la texture voulue, et laisser refroidir.",
            ],
            prep=15, cuisson=20, base="compote",
        )


def clafoutis() -> Iterator[R]:
    for nom, de, ligne, les, prep in FRUITS_CUITS:
        if nom in ("rhubarbe", "mangue", "pommes et poires", "bananes"):
            continue
        yield R(
            titre=f"Clafoutis {de}" if nom != "cerises" else "Clafoutis aux cerises",
            lignes=[ligne, "3 œufs", "80 g de sucre", "60 g de farine", "30 cl de lait", "20 g de beurre", "1 sachet de sucre vanillé"],
            etapes=[
                "Préchauffer le four à 180 °C et beurrer un plat.",
                prep,
                f"Disposer {les} dans le plat.",
                "Fouetter les œufs avec le sucre et le sucre vanillé, ajouter la farine puis le lait petit à petit.",
                f"Verser sur {les} et enfourner 40 minutes.",
            ],
            prep=15, cuisson=40, base="clafoutis",
        )


def tartes_fruits() -> Iterator[R]:
    for nom, de, ligne, les, prep in FRUITS_CUITS:
        if nom in ("fruits rouges", "mangue", "bananes", "pommes et poires"):
            continue
        yield R(
            titre=f"Tarte aux {nom}" if not nom.startswith("rhubarbe") else "Tarte à la rhubarbe",
            lignes=["1 pâte sablée", ligne, "2 œufs", "60 g de sucre", "15 cl de crème fraîche", "1 c. à soupe de poudre d'amande"],
            etapes=[
                "Préchauffer le four à 180 °C et garnir un moule de la pâte.",
                "Piquer le fond à la fourchette et le saupoudrer de poudre d'amande.",
                prep,
                f"Disposer {les} sur la pâte.",
                "Battre les œufs avec le sucre et la crème, verser sur les fruits et enfourner 40 minutes.",
            ],
            prep=20, cuisson=40, base="tarte aux fruits",
        )


GATEAUX = [
    ("Gâteau au yaourt", ["1 yaourt nature", "3 œufs", "150 g de sucre", "200 g de farine", "1 sachet de levure chimique", "5 cl d'huile de tournesol"], "Mélanger le yaourt, les œufs et le sucre, puis la farine, la levure et l'huile."),
    ("Gâteau au yaourt et au citron", ["1 yaourt nature", "3 œufs", "150 g de sucre", "200 g de farine", "1 sachet de levure chimique", "5 cl d'huile de tournesol", "1 citron"], "Mélanger le yaourt, les œufs, le sucre et le zeste du citron, puis la farine, la levure, l'huile et le jus du citron."),
    ("Gâteau au chocolat fondant", ["200 g de chocolat noir", "150 g de beurre", "150 g de sucre", "4 œufs", "50 g de farine"], "Faire fondre le chocolat et le beurre, ajouter le sucre, les œufs un à un, puis la farine."),
    ("Cake à la banane", ["3 bananes", "2 œufs", "100 g de sucre roux", "200 g de farine", "1 sachet de levure chimique", "80 g de beurre"], "Écraser les bananes, ajouter les œufs, le sucre et le beurre fondu, puis la farine et la levure."),
    ("Cake aux pommes et à la cannelle", ["2 pommes", "3 œufs", "120 g de sucre", "200 g de farine", "1 sachet de levure chimique", "100 g de beurre", "1 c. à café de cannelle"], "Mélanger les œufs, le sucre et le beurre fondu, puis la farine, la levure et la cannelle ; ajouter les pommes en dés."),
    ("Cake marbré", ["200 g de farine", "180 g de sucre", "4 œufs", "180 g de beurre", "1 sachet de levure chimique", "2 c. à soupe de cacao amer"], "Préparer la pâte avec le beurre mou, le sucre, les œufs, la farine et la levure, puis ajouter le cacao à la moitié de la pâte et alterner les deux pâtes dans le moule."),
    ("Muffins aux myrtilles", ["250 g de farine", "120 g de sucre", "2 œufs", "20 cl de lait", "80 g de beurre", "1 sachet de levure chimique", "150 g de myrtilles"], "Mélanger les ingrédients secs d'un côté, les liquides de l'autre, réunir sans trop travailler la pâte et ajouter les myrtilles."),
    ("Muffins aux pépites de chocolat", ["250 g de farine", "120 g de sucre", "2 œufs", "20 cl de lait", "80 g de beurre", "1 sachet de levure chimique", "100 g de pépites de chocolat"], "Mélanger les ingrédients secs d'un côté, les liquides de l'autre, réunir sans trop travailler la pâte et ajouter les pépites."),
    ("Gâteau à l'orange", ["2 oranges", "3 œufs", "150 g de sucre", "200 g de farine", "1 sachet de levure chimique", "100 g de beurre"], "Mélanger les œufs, le sucre, le zeste et le jus des oranges et le beurre fondu, puis la farine et la levure."),
    ("Moelleux aux amandes", ["150 g de poudre d'amande", "3 œufs", "120 g de sucre", "80 g de beurre", "40 g de farine"], "Mélanger les œufs et le sucre, puis la poudre d'amande, la farine et le beurre fondu."),
    ("Gâteau aux carottes", ["300 g de carottes", "3 œufs", "150 g de sucre roux", "200 g de farine", "1 sachet de levure chimique", "10 cl d'huile de tournesol", "1 c. à café de cannelle", "50 g de cerneaux de noix"], "Râper les carottes ; mélanger les œufs, le sucre et l'huile, puis la farine, la levure, la cannelle, les carottes et les noix."),
    ("Quatre-quarts au citron", ["3 œufs", "150 g de sucre", "150 g de farine", "150 g de beurre", "1 citron", "1/2 sachet de levure chimique"], "Battre le beurre mou avec le sucre, ajouter les œufs un à un, le zeste du citron, puis la farine et la levure."),
]


def gateaux() -> Iterator[R]:
    for titre, lignes, geste in GATEAUX:
        muffin = titre.startswith("Muffins")
        yield R(
            titre=titre,
            lignes=lignes,
            etapes=[
                "Préchauffer le four à 180 °C et beurrer le moule." if not muffin else "Préchauffer le four à 180 °C et garnir un moule à muffins de caissettes.",
                geste,
                "Verser dans le moule." if not muffin else "Remplir les caissettes aux trois quarts.",
                "Enfourner 20 minutes pour les muffins, 35 à 40 minutes pour un gâteau : la lame d'un couteau doit ressortir sèche." if not muffin else "Enfourner 20 minutes.",
                "Laisser tiédir avant de démouler.",
            ],
            prep=15, cuisson=20 if muffin else 40, base="gâteau",
        )


DESSERTS = [
    ("Riz au lait à la vanille", ["150 g de riz rond", "1 l de lait", "100 g de sucre", "1 gousse de vanille"], ["Faire chauffer le lait avec la gousse de vanille fendue.", "Ajouter le riz et cuire 40 minutes à feu très doux en remuant souvent.", "Ajouter le sucre en fin de cuisson et laisser refroidir."], 40),
    ("Riz au lait à la cannelle et aux raisins", ["150 g de riz rond", "1 l de lait", "100 g de sucre", "1 c. à café de cannelle", "50 g de raisins secs"], ["Faire chauffer le lait avec la cannelle.", "Ajouter le riz et cuire 40 minutes à feu très doux en remuant souvent.", "Ajouter le sucre et les raisins en fin de cuisson."], 40),
    ("Panna cotta au coulis de fruits rouges", ["50 cl de crème liquide", "60 g de sucre", "3 feuilles de gélatine", "1 gousse de vanille", "300 g de fruits rouges mélangés", "40 g de sucre glace"], ["Ramollir la gélatine dans l'eau froide.", "Chauffer la crème avec le sucre et la vanille, puis y faire fondre la gélatine essorée.", "Verser dans des verrines et réserver 4 heures au frais.", "Mixer les fruits rouges avec le sucre glace et napper au moment de servir."], 5),
    ("Panna cotta à la mangue", ["50 cl de crème liquide", "60 g de sucre", "3 feuilles de gélatine", "1 mangue", "1 citron vert"], ["Ramollir la gélatine dans l'eau froide.", "Chauffer la crème avec le sucre, puis y faire fondre la gélatine essorée.", "Verser dans des verrines et réserver 4 heures au frais.", "Mixer la mangue avec le jus du citron vert et napper au moment de servir."], 5),
    ("Mousse au chocolat", ["200 g de chocolat noir", "6 œufs", "1 pincée de sel"], ["Faire fondre le chocolat au bain-marie.", "Séparer les blancs des jaunes ; mélanger les jaunes au chocolat tiédi.", "Monter les blancs en neige ferme avec le sel et les incorporer délicatement.", "Réserver au moins 4 heures au frais."], 5),
    ("Crème au chocolat", ["50 cl de lait", "100 g de chocolat noir", "3 jaunes d'œufs", "60 g de sucre", "20 g de fécule de maïs"], ["Faire chauffer le lait et y faire fondre le chocolat.", "Fouetter les jaunes avec le sucre et la fécule.", "Verser le lait chocolaté dessus, remettre sur le feu et cuire en remuant jusqu'à épaississement.", "Verser dans des ramequins et réserver au frais."], 10),
    ("Crème brûlée à la vanille", ["50 cl de crème liquide", "5 jaunes d'œufs", "80 g de sucre", "1 gousse de vanille", "4 c. à soupe de sucre roux"], ["Préchauffer le four à 100 °C.", "Chauffer la crème avec la vanille fendue.", "Fouetter les jaunes avec le sucre, puis verser la crème chaude dessus.", "Répartir dans des ramequins et cuire 1 heure. Laisser refroidir.", "Saupoudrer de sucre roux et caraméliser au chalumeau ou sous le gril."], 60),
    ("Flan pâtissier", ["1 pâte brisée", "75 cl de lait", "4 œufs", "150 g de sucre", "80 g de fécule de maïs", "1 gousse de vanille"], ["Préchauffer le four à 180 °C et garnir un moule de pâte.", "Chauffer le lait avec la vanille.", "Fouetter les œufs avec le sucre et la fécule, verser le lait dessus et cuire en remuant jusqu'à épaississement.", "Verser sur la pâte et enfourner 45 minutes."], 50),
    ("Pommes au four à la cannelle", ["4 pommes", "40 g de beurre", "4 c. à soupe de sucre roux", "1 c. à café de cannelle"], ["Préchauffer le four à 180 °C.", "Évider les pommes sans les percer jusqu'au fond.", "Les garnir de beurre, de sucre et de cannelle.", "Cuire 35 minutes en arrosant avec le jus."], 35),
    ("Poires pochées au sirop d'épices", ["4 poires", "100 g de sucre", "1 bâton de cannelle", "2 étoiles de badiane", "1 gousse de vanille", "75 cl d'eau"], ["Porter l'eau à ébullition avec le sucre et les épices.", "Éplucher les poires en gardant la queue.", "Les pocher 25 minutes dans le sirop frémissant.", "Les laisser refroidir dans le sirop."], 30),
    ("Bananes poêlées au miel", ["4 bananes", "30 g de beurre", "2 c. à soupe de miel", "1 citron vert"], ["Couper les bananes en deux dans la longueur.", "Les faire dorer 3 minutes de chaque côté au beurre.", "Ajouter le miel et le jus du citron vert et laisser caraméliser 1 minute."], 8),
    ("Salade de fruits frais à la menthe", ["2 oranges", "2 kiwis", "1 mangue", "250 g de fraises", "1 c. à soupe de miel", "quelques feuilles de menthe"], ["Peler et couper tous les fruits en morceaux.", "Les mélanger avec le miel et la menthe ciselée.", "Réserver 30 minutes au frais."], 0),
    ("Fraises au sucre et à la menthe", ["500 g de fraises", "2 c. à soupe de sucre", "1 citron", "quelques feuilles de menthe"], ["Équeuter et couper les fraises.", "Les mélanger avec le sucre, le jus de citron et la menthe ciselée.", "Laisser macérer 30 minutes au frais."], 0),
    ("Crêpes sucrées", ["250 g de farine", "4 œufs", "50 cl de lait", "50 g de beurre", "1 c. à soupe de sucre", "1 pincée de sel"], ["Mélanger la farine, le sucre et le sel, puis ajouter les œufs et le lait petit à petit.", "Ajouter le beurre fondu et laisser reposer 1 heure.", "Cuire les crêpes une à une dans une poêle chaude légèrement beurrée."], 30),
    ("Pancakes", ["200 g de farine", "2 œufs", "25 cl de lait", "30 g de sucre", "1 sachet de levure chimique", "30 g de beurre"], ["Mélanger la farine, le sucre et la levure, puis les œufs et le lait.", "Ajouter le beurre fondu.", "Cuire de petites louches de pâte 2 minutes de chaque côté dans une poêle chaude."], 20),
    ("Porridge aux pommes et à la cannelle", ["120 g de flocons d'avoine", "50 cl de lait", "1 pomme", "1 c. à café de cannelle", "2 c. à soupe de sirop d'érable"], ["Porter le lait à frémissement avec la cannelle.", "Ajouter les flocons et cuire 5 minutes en remuant.", "Servir avec la pomme râpée et le sirop d'érable."], 5),
    ("Yaourt glacé aux fruits rouges", ["500 g de yaourt grec", "300 g de fruits rouges mélangés", "60 g de miel"], ["Mixer les fruits rouges avec le miel.", "Mélanger au yaourt.", "Mettre au congélateur 3 heures en remuant toutes les 30 minutes."], 0),
    ("Sablés au beurre", ["250 g de farine", "125 g de beurre", "100 g de sucre", "1 œuf", "1 pincée de sel"], ["Sabler la farine avec le beurre froid, puis ajouter le sucre, le sel et l'œuf.", "Former un boudin et le réserver 1 heure au frais.", "Couper en rondelles et cuire 12 minutes à 180 °C."], 12),
    ("Cookies aux flocons d'avoine", ["150 g de flocons d'avoine", "100 g de farine", "100 g de beurre", "100 g de sucre roux", "1 œuf", "1/2 sachet de levure chimique", "50 g de raisins secs"], ["Mélanger le beurre mou et le sucre, puis l'œuf.", "Ajouter la farine, la levure, les flocons et les raisins.", "Former des petits tas sur une plaque et cuire 12 minutes à 180 °C."], 12),
]


def desserts() -> Iterator[R]:
    for titre, lignes, etapes, cuisson in DESSERTS:
        texte = " ".join(etapes)
        repos = 240 if "4 heures" in texte else 180 if "3 heures" in texte else 60 if "1 heure" in texte else 30 if "30 minutes" in texte else 0
        yield R(titre=titre, lignes=lignes, etapes=etapes, prep=15, cuisson=cuisson, repos=repos, base="dessert")


# --- Parcours de découverte : un aliment, de fondu (1) à vedette (5) -------------------------
# Les niveaux 4 et 5 reprennent souvent des recettes déjà déclinées ci-dessus (poêlée, gratin) :
# on leur ajoute la note « Pourquoi ici ? » ; les niveaux 1 à 3 sont écrits pour le parcours.

PARCOURS = {
    "brocoli": [
        (1, "Sauce verte au brocoli pour les pâtes", ["400 g de penne", "300 g de brocoli", "10 cl de crème liquide", "50 g de parmesan râpé", "1 gousse d'ail", "sel, poivre"],
         ["Cuire le brocoli 10 minutes à l'eau salée, puis le mixer très finement avec la crème, l'ail et le parmesan.", "Cuire les pâtes et les mélanger à la sauce."],
         "Mixé avec la crème et le parmesan, le brocoli donne une couleur verte mais très peu de goût.", "Mixer longtemps pour une sauce bien lisse."),
        (2, "Gratin de pâtes au brocoli en petits morceaux", ["400 g de coquillettes", "150 g de brocoli", "20 cl de crème fraîche", "100 g d'emmental râpé", "sel, poivre"],
         ["Cuire les pâtes avec le brocoli coupé en tout petits morceaux.", "Mélanger avec la crème dans un plat, couvrir d'emmental et gratiner 20 minutes à 200 °C."],
         "De tout petits morceaux pris dans les pâtes et le fromage : on le voit, mais il se mêle au reste.", None),
        (3, "Quiche au brocoli et au jambon", ["1 pâte brisée", "300 g de brocoli", "150 g de jambon blanc", "3 œufs", "20 cl de crème fraîche", "sel, poivre"],
         ["Cuire le brocoli 5 minutes à la vapeur.", "Le répartir sur la pâte avec le jambon en dés.", "Couvrir des œufs battus avec la crème et cuire 35 minutes à 180 °C."],
         "Des bouquets entiers, bien identifiables, adoucis par la crème et le jambon.", "Une cuisson courte garde le brocoli vert et moins soufré."),
    ],
    "epinard": [],  # déjà couvert par les recettes relues à la main (niveaux 1 à 4)
    "courgette": [
        (1, "Cake moelleux à la courgette cachée", ["1 courgette", "3 œufs", "150 g de farine", "1 sachet de levure chimique", "10 cl d'huile d'olive", "100 g d'emmental râpé", "sel, poivre"],
         ["Râper finement la courgette et bien la presser.", "Mélanger les œufs, l'huile, la farine et la levure, puis la courgette et l'emmental.", "Cuire 40 minutes à 180 °C dans un moule à cake."],
         "Râpée et pressée, la courgette disparaît dans la pâte : elle apporte surtout du moelleux.", None),
        (2, "Bolognaise aux courgettes râpées", ["400 g de spaghettis", "400 g de bœuf haché", "1 courgette", "1 oignon", "800 g de tomates pelées", "2 c. à soupe d'huile d'olive", "sel, poivre"],
         ["Faire revenir l'oignon, puis le bœuf.", "Ajouter la courgette râpée et les tomates, et laisser mijoter 30 minutes.", "Servir avec les spaghettis."],
         "Râpée dans une sauce tomate, la courgette fond presque complètement.", None),
        (3, "Tian de courgettes et tomates", ["3 courgettes", "4 tomates", "1 oignon", "3 c. à soupe d'huile d'olive", "1 c. à café de thym", "sel, poivre"],
         ["Couper les légumes en rondelles fines.", "Les disposer en alternance dans un plat sur l'oignon émincé.", "Arroser d'huile, parsemer de thym et cuire 45 minutes à 180 °C."],
         "Les rondelles se voient, mais la tomate et le thym donnent le goût principal.", None),
    ],
    "betterave": [
        (1, "Houmous rose à la betterave", ["1 boîte de pois chiches (400 g)", "1 betterave cuite", "2 c. à soupe de tahini", "1 citron", "2 c. à soupe d'huile d'olive", "sel"],
         ["Mixer tous les ingrédients jusqu'à obtenir une crème lisse."],
         "Une petite betterave colore le houmous en rose ; le pois chiche et le citron dominent.", None),
        (2, "Risotto à la betterave et au parmesan", ["300 g de riz arborio", "150 g de betteraves cuites", "1 oignon", "1 l de bouillon de légumes", "50 g de parmesan râpé", "30 g de beurre", "sel, poivre"],
         ["Faire revenir l'oignon, nacrer le riz.", "Mouiller de bouillon louche par louche pendant 18 minutes en ajoutant la betterave mixée à mi-cuisson.", "Finir avec le beurre et le parmesan."],
         "Mixée dans le riz, la betterave colore et adoucit, le parmesan reste en premier plan.", None),
        (3, "Salade de betteraves à l'orange", ["4 betteraves cuites", "2 oranges", "1 c. à soupe de miel", "3 c. à soupe d'huile d'olive", "sel"],
         ["Couper les betteraves en dés et peler les oranges à vif.", "Assaisonner avec le miel, l'huile et le sel."],
         "La betterave est bien là, mais l'orange et le miel répondent à son goût de terre.", None),
    ],
    "chou_fleur": [
        (1, "Purée de pommes de terre au chou-fleur", ["600 g de pommes de terre", "200 g de chou-fleur", "30 g de beurre", "10 cl de lait", "sel, poivre"],
         ["Cuire les pommes de terre et le chou-fleur 20 minutes à l'eau salée.", "Les écraser finement avec le beurre et le lait chaud."],
         "Écrasé avec les pommes de terre, le chou-fleur passe inaperçu dans une purée classique.", None),
        (2, "Gratin de chou-fleur et pommes de terre", ["400 g de pommes de terre", "300 g de chou-fleur", "20 cl de crème fraîche", "80 g d'emmental râpé", "sel, poivre"],
         ["Cuire les légumes 15 minutes à l'eau salée.", "Les mettre dans un plat avec la crème, couvrir d'emmental et gratiner 20 minutes à 200 °C."],
         "Mêlé aux pommes de terre sous le fromage, il se fait discret.", None),
        (3, "Chou-fleur rôti au curry", ["1 chou-fleur", "3 c. à soupe d'huile d'olive", "1 c. à café de curry", "sel"],
         ["Couper le chou-fleur en bouquets, les mélanger à l'huile et au curry.", "Rôtir 30 minutes à 210 °C."],
         "Rôti, le chou-fleur devient doux et croustillant, et le curry change son goût.", None),
    ],
    "poivron": [
        (1, "Sauce tomate aux poivrons mixés", ["400 g de penne", "1 poivron rouge", "800 g de tomates pelées", "1 oignon", "2 c. à soupe d'huile d'olive", "sel"],
         ["Faire revenir l'oignon et le poivron émincés, ajouter les tomates et cuire 20 minutes.", "Mixer finement la sauce et la servir avec les pâtes."],
         "Mixé dans la tomate, le poivron rouge apporte de la douceur sans se voir.", "Le poivron rouge est plus doux que le vert."),
        (3, "Poivrons rouges marinés à l'huile d'olive", ["4 poivrons rouges", "4 c. à soupe d'huile d'olive", "1 gousse d'ail", "sel"],
         ["Rôtir les poivrons entiers 30 minutes à 220 °C, les laisser tiédir dans un sac et les peler.", "Les couper en lanières et les arroser d'huile et d'ail."],
         "Rôti et pelé, le poivron perd sa peau et une partie de son amertume.", None),
    ],
    "aubergine": [
        (1, "Caviar d'aubergine", ["2 aubergines", "1 gousse d'ail", "1 citron", "3 c. à soupe d'huile d'olive", "sel"],
         ["Rôtir les aubergines entières 40 minutes à 200 °C.", "Récupérer la chair et la mixer avec l'ail, le jus du citron et l'huile."],
         "Rôtie puis mixée, l'aubergine devient une crème fumée, sans sa texture spongieuse.", None),
        (3, "Aubergines rôties au miel et au thym", ["2 aubergines", "3 c. à soupe d'huile d'olive", "1 c. à soupe de miel", "1 c. à café de thym", "sel"],
         ["Couper les aubergines en tranches épaisses, les badigeonner d'huile.", "Rôtir 25 minutes à 210 °C, puis arroser de miel et de thym."],
         "Bien dorée, l'aubergine devient fondante ; le miel arrondit son amertume.", None),
    ],
    "patate_douce": [
        (1, "Velouté de carottes et patate douce", ["600 g de carottes", "1 patate douce", "1 oignon", "1 l de bouillon de légumes", "10 cl de crème liquide", "sel"],
         ["Cuire les légumes 25 minutes dans le bouillon avec l'oignon.", "Mixer avec la crème."],
         "Dans un velouté de carottes, la patate douce ajoute seulement de la douceur.", None),
        (3, "Frites de patates douces au four", ["800 g de patates douces", "2 c. à soupe d'huile d'olive", "1 c. à café de paprika", "sel"],
         ["Couper les patates douces en bâtonnets, les mélanger à l'huile et au paprika.", "Cuire 30 minutes à 220 °C en les retournant à mi-cuisson."],
         "En frites, la patate douce garde une forme familière.", None),
    ],
    "champignon_de_paris": [
        (1, "Sauce bolognaise aux champignons hachés", ["400 g de spaghettis", "300 g de bœuf haché", "150 g de champignons de Paris", "1 oignon", "800 g de tomates pelées", "2 c. à soupe d'huile d'olive", "sel"],
         ["Hacher très finement les champignons.", "Faire revenir l'oignon, le bœuf et les champignons, puis ajouter les tomates et mijoter 30 minutes."],
         "Hachés très fin, les champignons se confondent avec la viande.", None),
        (3, "Champignons farcis au fromage frais", ["12 gros champignons de Paris", "150 g de fromage frais", "1/2 botte de persil", "1 gousse d'ail", "sel, poivre"],
         ["Retirer les pieds des champignons.", "Les garnir de fromage frais mélangé à l'ail et au persil.", "Cuire 20 minutes à 200 °C."],
         "Le champignon est entier, mais le fromage frais adoucit le tout.", None),
    ],
    "petit_pois": [
        (1, "Velouté de petits pois et pommes de terre", ["300 g de petits pois", "2 pommes de terre", "1 oignon", "80 cl de bouillon de légumes", "10 cl de crème liquide", "sel"],
         ["Cuire les légumes 20 minutes dans le bouillon.", "Mixer finement avec la crème."],
         "Mixés avec les pommes de terre, les petits pois donnent une soupe douce et verte.", None),
        (3, "Petits pois à la française", ["600 g de petits pois", "1 laitue", "6 oignons nouveaux", "30 g de beurre", "1 c. à café de sucre", "sel"],
         ["Faire fondre les oignons au beurre, ajouter les petits pois, la laitue émincée, le sucre et 10 cl d'eau.", "Couvrir et cuire 20 minutes à feu doux."],
         "Cuits doucement avec la laitue et un peu de sucre, ils sont tendres et sucrés.", None),
    ],
}
# Niveaux 4 et 5 : recettes déclinées plus haut, identifiées par leur titre
PARCOURS_EXISTANTS = {
    "brocoli": [(4, "Poêlée de brocoli à l'ail et au persil", "En accompagnement, le brocoli est servi à part : on peut le goûter à son rythme."),
                (5, "Gratin de brocoli à la béchamel", "Le brocoli est la vedette du plat, simplement gratiné.")],
    "courgette": [(4, "Poêlée de courgettes à l'ail et au persil", "En accompagnement, la courgette poêlée garde un goût doux."),
                  (5, "Gratin de courgettes au parmesan", "La courgette est le cœur du plat.")],
    "betterave": [(4, "Betteraves rôties aux herbes de Provence", "Rôtie, la betterave est servie seule, en accompagnement."),
                  (5, "Velouté de betteraves", "La betterave fait tout le plat, adoucie par la crème.")],
    "chou_fleur": [(4, "Purée de chou-fleur et pommes de terre", "Une purée où le chou-fleur pèse autant que la pomme de terre."),
                   (5, "Gratin de chou-fleur à la béchamel", "Le grand classique : le chou-fleur en vedette.")],
    "poivron": [(2, "Quiche aux poivrons", "Fondus avec l'oignon et pris dans l'appareil, les poivrons sont discrets."),
                (4, "Poêlée de poivrons à l'ail et au persil", "Poêlés, les poivrons deviennent fondants et plus doux."),
                (5, "Poivrons rôtis aux herbes de Provence", "Le poivron seul, rôti, en plat de légumes.")],
    "aubergine": [(2, "Pâtes aux aubergines et à la tomate", "Les dés d'aubergine se fondent dans la sauce tomate."),
                  (4, "Poêlée d'aubergines à l'ail et au persil", "En accompagnement, l'aubergine poêlée reste fondante."),
                  (5, "Gratin d'aubergines au parmesan", "L'aubergine est la vedette du gratin.")],
    "patate_douce": [(2, "Chili végétarien aux patates douces", "Les cubes de patate douce se mêlent aux haricots et aux épices."),
                     (4, "Patates douces rôties aux herbes de Provence", "Rôties, servies en accompagnement."),
                     (5, "Purée de patates douces et pommes de terre", "La patate douce donne son goût et sa couleur à la purée.")],
    "champignon_de_paris": [(2, "Quiche aux champignons", "Émincés et pris dans l'appareil, les champignons se font discrets."),
                            (4, "Poêlée de champignons à l'ail et au persil", "Poêlés, en accompagnement."),
                            (5, "Velouté de champignons", "Les champignons font tout le goût du velouté.")],
    "petit_pois": [(2, "Riz cantonais aux petits pois", "Quelques petits pois dans le riz sauté, au milieu des autres ingrédients."),
                   (4, "Pâtes au jambon et aux petits pois", "Les petits pois accompagnent les pâtes et le jambon."),
                   (5, "Velouté de petits pois au cumin", "Les petits pois en vedette, relevés de cumin.")],
}


def parcours() -> Iterator[R]:
    for aliment, recettes in PARCOURS.items():
        for niveau, titre, lignes, etapes, pourquoi, conseil in recettes:
            d = {"aliment": aliment, "niveau": niveau, "pourquoi": pourquoi}
            if conseil:
                d["conseil"] = conseil
            yield R(titre=titre, lignes=lignes, etapes=etapes, prep=15, cuisson=30, base="parcours de découverte", decouverte=d)


EN_PLUS = [
    ("Tartines tomate, basilic et huile d'olive", ["8 tranches de pain de campagne", "4 tomates", "1 gousse d'ail", "quelques feuilles de basilic", "4 c. à soupe d'huile d'olive", "sel"],
     ["Griller les tranches de pain et les frotter d'ail.", "Les garnir de tomates en dés, arroser d'huile, saler et parsemer de basilic."], 5, "tartine"),
    ("Tartines avocat et œuf", ["8 tranches de pain complet", "2 avocats", "4 œufs", "1 citron", "1 pincée de piment d'Espelette", "sel"],
     ["Cuire les œufs 6 minutes à l'eau bouillante, puis les écaler.", "Écraser les avocats avec le jus du citron et le sel.", "Tartiner le pain grillé, poser un demi-œuf et une pincée de piment."], 6, "tartine"),
    ("Tartines au chèvre et au miel", ["8 tranches de pain de campagne", "200 g de fromage de chèvre", "3 c. à soupe de miel", "1 c. à café de thym", "30 g de cerneaux de noix"],
     ["Poser le chèvre en rondelles sur le pain.", "Passer 5 minutes sous le gril.", "Arroser de miel et parsemer de thym et de noix."], 5, "tartine"),
    ("Tartines aux champignons et à l'ail", ["8 tranches de pain de campagne", "400 g de champignons de Paris", "2 gousses d'ail", "1/2 botte de persil", "30 g de beurre", "sel, poivre"],
     ["Faire revenir les champignons émincés au beurre 8 minutes avec l'ail haché.", "Ajouter le persil, saler, poivrer et répartir sur le pain grillé."], 10, "tartine"),
    ("Tartines au saumon fumé et au fromage frais", ["8 tranches de pain de seigle", "200 g de saumon fumé", "150 g de fromage frais", "1/2 botte d'aneth", "1 citron"],
     ["Tartiner le pain de fromage frais.", "Poser le saumon, l'aneth ciselé et quelques gouttes de citron."], 0, "tartine"),
    ("Tartines au houmous et aux crudités", ["8 tranches de pain complet", "200 g de houmous", "1 carotte", "1/2 concombre", "8 radis"],
     ["Tartiner le pain de houmous.", "Garnir de carotte râpée, de concombre et de radis en fines rondelles."], 0, "tartine"),
    ("Tartines aux sardines et à la tomate", ["8 tranches de pain de campagne", "2 boîtes de sardines à l'huile", "2 tomates", "1 citron", "sel, poivre"],
     ["Griller le pain et le couvrir de rondelles de tomate.", "Poser les sardines, arroser de citron, saler et poivrer."], 5, "tartine"),
    ("Tartines ricotta, épinards et noisettes", ["8 tranches de pain de campagne", "250 g de ricotta", "100 g de pousses d'épinards", "30 g de noisettes", "1 c. à soupe de miel"],
     ["Tartiner le pain grillé de ricotta.", "Garnir de pousses d'épinards et de noisettes concassées, puis arroser de miel."], 5, "tartine"),
    ("Brochettes de bœuf marinées", ["600 g de rumsteck", "3 c. à soupe de sauce soja", "2 c. à soupe d'huile d'olive", "1 c. à soupe de miel", "1 gousse d'ail", "1 poivron rouge", "1 oignon"],
     ["Couper le bœuf en cubes et le faire mariner 1 heure avec la sauce soja, l'huile, le miel et l'ail.", "Enfiler sur des brochettes en alternant avec le poivron et l'oignon.", "Griller 8 minutes en retournant."], 8, "brochettes"),
    ("Brochettes d'agneau au cumin", ["600 g de gigot d'agneau", "1 c. à café de cumin en poudre", "1 c. à café de paprika", "3 c. à soupe d'huile d'olive", "1 citron", "sel"],
     ["Couper l'agneau en cubes et le mariner 1 heure avec les épices, l'huile et le jus du citron.", "Enfiler sur des brochettes et griller 10 minutes."], 10, "brochettes"),
    ("Brochettes de crevettes à l'ail", ["500 g de crevettes décortiquées", "3 gousses d'ail", "3 c. à soupe d'huile d'olive", "1/2 botte de persil", "1 citron"],
     ["Mélanger les crevettes avec l'ail haché, l'huile et le persil.", "Les enfiler sur des brochettes et griller 3 minutes de chaque côté.", "Servir avec le citron."], 6, "brochettes"),
    ("Brochettes de légumes grillés", ["2 courgettes", "2 poivrons", "250 g de champignons de Paris", "1 oignon rouge", "4 c. à soupe d'huile d'olive", "1 c. à café d'herbes de Provence", "sel"],
     ["Couper les légumes en gros morceaux et les mélanger à l'huile et aux herbes.", "Les enfiler sur des brochettes et griller 12 minutes en retournant."], 12, "brochettes"),
    ("Brochettes de saumon au citron", ["600 g de pavé de saumon", "2 citrons", "2 c. à soupe d'huile d'olive", "1/2 botte d'aneth", "sel, poivre"],
     ["Couper le saumon en cubes et les mélanger à l'huile, au zeste d'un citron et à l'aneth.", "Enfiler sur des brochettes avec des quartiers de citron et griller 6 minutes."], 6, "brochettes"),
    ("Burgers maison au bœuf", ["4 pains à burger", "500 g de bœuf haché", "4 tranches de cheddar", "1 tomate", "4 feuilles de laitue", "1 oignon rouge", "4 c. à soupe de ketchup", "sel, poivre"],
     ["Former 4 steaks avec le bœuf, saler et poivrer.", "Les cuire 3 à 4 minutes de chaque côté, en posant le cheddar à la fin.", "Garnir les pains toastés de ketchup, laitue, tomate, oignon et steak."], 8, "burger"),
    ("Burgers de poulet croustillant", ["4 pains à burger", "2 blancs de poulet", "1 œuf", "80 g de chapelure panko", "4 feuilles de laitue", "4 c. à soupe de mayonnaise", "3 c. à soupe d'huile de tournesol", "sel"],
     ["Couper les blancs en deux dans l'épaisseur, les passer dans l'œuf battu puis dans la chapelure.", "Les dorer 4 minutes de chaque côté dans l'huile.", "Garnir les pains de mayonnaise, laitue et poulet."], 10, "burger"),
    ("Burgers végétariens aux pois chiches", ["4 pains à burger", "1 boîte de pois chiches (400 g)", "1 carotte", "1 œuf", "40 g de chapelure", "1 c. à café de cumin en poudre", "4 feuilles de laitue", "3 c. à soupe d'huile d'olive", "sel"],
     ["Écraser les pois chiches avec la carotte râpée, l'œuf, la chapelure et le cumin.", "Former 4 galettes et les dorer 4 minutes de chaque côté dans l'huile.", "Garnir les pains de laitue et de galette."], 10, "burger"),
    ("Galettes de sarrasin au chèvre et aux épinards", ["250 g de farine de sarrasin", "1 œuf", "50 cl d'eau", "200 g d'épinards", "150 g de fromage de chèvre", "20 g de beurre", "sel"],
     ["Mélanger la farine, l'œuf, l'eau et le sel, et laisser reposer 1 heure.", "Faire tomber les épinards à la poêle.", "Cuire les galettes, les garnir d'épinards et de chèvre, et les replier."], 20, "galette garnie"),
    ("Galettes de sarrasin au saumon et aux poireaux", ["250 g de farine de sarrasin", "1 œuf", "50 cl d'eau", "2 poireaux", "150 g de saumon fumé", "10 cl de crème fraîche", "20 g de beurre", "sel"],
     ["Préparer la pâte et la laisser reposer 1 heure.", "Faire fondre les poireaux émincés au beurre, ajouter la crème.", "Cuire les galettes et les garnir de poireaux et de saumon."], 25, "galette garnie"),
    ("Galettes de sarrasin aux champignons", ["250 g de farine de sarrasin", "1 œuf", "50 cl d'eau", "300 g de champignons de Paris", "1 échalote", "10 cl de crème fraîche", "80 g d'emmental râpé", "20 g de beurre", "sel"],
     ["Préparer la pâte et la laisser reposer 1 heure.", "Faire revenir l'échalote et les champignons au beurre, ajouter la crème.", "Cuire les galettes, les garnir de champignons et d'emmental et les replier."], 25, "galette garnie"),
    ("Galettes de sarrasin à l'andouille et aux pommes", ["250 g de farine de sarrasin", "1 œuf", "50 cl d'eau", "150 g d'andouille", "2 pommes", "20 g de beurre", "sel"],
     ["Préparer la pâte et la laisser reposer 1 heure.", "Faire dorer les pommes en lamelles au beurre.", "Cuire les galettes et les garnir d'andouille en rondelles et de pommes."], 25, "galette garnie"),
    ("Galettes de sarrasin à la ratatouille", ["250 g de farine de sarrasin", "1 œuf", "50 cl d'eau", "1 courgette", "1 aubergine", "1 poivron", "2 tomates", "3 c. à soupe d'huile d'olive", "sel"],
     ["Préparer la pâte et la laisser reposer 1 heure.", "Cuire les légumes en petits dés 25 minutes dans l'huile.", "Cuire les galettes et les garnir de légumes."], 35, "galette garnie"),
    ("Soupe froide de concombre à la menthe", ["2 concombres", "2 yaourts nature", "1/2 botte de menthe", "1 gousse d'ail", "1 citron", "2 c. à soupe d'huile d'olive", "sel"],
     ["Éplucher les concombres et les couper en morceaux.", "Les mixer avec les yaourts, la menthe, l'ail, le jus du citron et l'huile.", "Saler et réserver 1 heure au frais."], 0, "soupe froide"),
    ("Soupe froide de petits pois à la menthe", ["500 g de petits pois", "1 oignon nouveau", "60 cl de bouillon de légumes", "10 cl de crème liquide", "quelques feuilles de menthe", "sel"],
     ["Cuire les petits pois et l'oignon 10 minutes dans le bouillon.", "Mixer avec la crème et la menthe, saler et réserver 2 heures au frais."], 10, "soupe froide"),
    ("Soupe froide de melon au basilic", ["1 melon", "quelques feuilles de basilic", "1 citron vert", "2 c. à soupe d'huile d'olive", "sel, poivre"],
     ["Mixer la chair du melon avec le basilic et le jus du citron vert.", "Ajouter l'huile, saler, poivrer et réserver 1 heure au frais."], 0, "soupe froide"),
    ("Parmentier de canard", ["4 cuisses de canard confites", "1 kg de pommes de terre", "2 échalotes", "20 cl de lait", "30 g de beurre", "sel, poivre"],
     ["Cuire les pommes de terre 20 minutes et les écraser avec le lait et le beurre.", "Effilocher le canard et le faire revenir avec les échalotes.", "Monter le parmentier dans un plat et gratiner 20 minutes à 200 °C."], 40, "parmentier"),
    ("Parmentier de poisson", ["600 g de cabillaud", "1 kg de pommes de terre", "50 cl de lait", "30 g de beurre", "1 gousse d'ail", "50 g de gruyère râpé", "sel, poivre"],
     ["Pocher le cabillaud 8 minutes dans le lait, puis l'émietter.", "Cuire les pommes de terre et les écraser avec un peu de lait de cuisson et le beurre.", "Monter le parmentier, couvrir de gruyère et gratiner 20 minutes à 200 °C."], 40, "parmentier"),
    ("Parmentier végétarien aux lentilles", ["250 g de lentilles vertes", "1 kg de pommes de terre", "2 carottes", "1 oignon", "20 cl de lait", "30 g de beurre", "50 g de comté râpé", "sel, poivre"],
     ["Cuire les lentilles 25 minutes avec les carottes en dés et l'oignon.", "Cuire les pommes de terre et les écraser avec le lait et le beurre.", "Monter le parmentier, couvrir de comté et gratiner 20 minutes à 200 °C."], 45, "parmentier"),
    ("Quiche aux lardons et au fromage", ["1 pâte brisée", "200 g de lardons", "100 g de comté râpé", "3 œufs", "20 cl de crème fraîche", "10 cl de lait", "sel, poivre"],
     ["Préchauffer le four à 180 °C et garnir un moule de pâte.", "Faire dorer les lardons à la poêle.", "Répartir les lardons et le comté sur la pâte, couvrir des œufs battus avec la crème et le lait.", "Enfourner 35 minutes."], 35, "quiche"),
    ("Quiche aux légumes du soleil", ["1 pâte brisée", "1 courgette", "1 poivron rouge", "1 tomate", "3 œufs", "20 cl de crème fraîche", "50 g de parmesan râpé", "sel, poivre"],
     ["Préchauffer le four à 180 °C et garnir un moule de pâte.", "Faire revenir les légumes en dés 10 minutes.", "Les répartir sur la pâte, couvrir des œufs battus avec la crème et le parmesan.", "Enfourner 35 minutes."], 35, "quiche"),
    ("Salade de pâtes aux légumes grillés et à la mozzarella", ["300 g de penne", "1 courgette", "1 poivron rouge", "1 boule de mozzarella", "quelques feuilles de basilic", "4 c. à soupe d'huile d'olive", "sel, poivre"],
     ["Cuire les pâtes et les refroidir.", "Griller les légumes en lanières à la poêle.", "Mélanger avec la mozzarella en dés, le basilic et l'huile."], 15, "salade composée"),
    ("Salade niçoise au thon frais", ["2 steaks de thon", "4 tomates", "200 g de haricots verts", "4 œufs", "50 g d'olives noires", "8 filets d'anchois", "4 c. à soupe d'huile d'olive", "1 c. à soupe de vinaigre de vin", "sel, poivre"],
     ["Cuire les haricots verts 8 minutes et les œufs 10 minutes.", "Saisir le thon 2 minutes de chaque côté et le couper en tranches.", "Disposer tous les ingrédients et arroser de vinaigrette."], 15, "salade composée"),
    ("Endives braisées au jambon et à la béchamel", ["6 endives", "6 tranches de jambon blanc", "40 g de beurre", "40 g de farine", "50 cl de lait", "80 g d'emmental râpé", "sel, poivre"],
     ["Braiser les endives 20 minutes à couvert avec 20 g de beurre.", "Préparer une béchamel avec le reste du beurre, la farine et le lait.", "Rouler chaque endive dans une tranche de jambon, napper de béchamel, couvrir d'emmental et gratiner 20 minutes à 200 °C."], 40, "gratin"),
    ("Poireaux vinaigrette", ["8 poireaux", "1 c. à soupe de moutarde de Dijon", "2 c. à soupe de vinaigre de vin", "6 c. à soupe d'huile de colza", "1 échalote", "sel, poivre"],
     ["Cuire les poireaux 15 minutes à l'eau bouillante salée et les égoutter.", "Préparer la vinaigrette avec la moutarde, le vinaigre, l'huile et l'échalote hachée.", "Napper les poireaux tièdes."], 15, "entrée"),
    ("Carottes râpées au citron", ["600 g de carottes", "1 citron", "3 c. à soupe d'huile d'olive", "1/2 botte de persil", "sel"],
     ["Râper finement les carottes.", "Les assaisonner avec le jus du citron, l'huile, le sel et le persil ciselé."], 0, "entrée"),
    ("Œufs mimosa", ["6 œufs", "3 c. à soupe de mayonnaise", "1/2 botte de ciboulette", "sel, poivre"],
     ["Cuire les œufs 10 minutes, les refroidir et les écaler.", "Les couper en deux, écraser les jaunes avec la mayonnaise et la ciboulette.", "Garnir les blancs de ce mélange."], 10, "entrée"),
    ("Taboulé de chou-fleur", ["1/2 chou-fleur", "2 tomates", "1/2 concombre", "1 botte de persil", "1/2 botte de menthe", "1 citron", "4 c. à soupe d'huile d'olive", "sel"],
     ["Mixer le chou-fleur cru en semoule.", "Ajouter les légumes en petits dés et les herbes ciselées.", "Assaisonner de jus de citron, d'huile et de sel."], 0, "salade composée"),
    ("Velouté de carottes à l'orange", ["800 g de carottes", "2 oranges", "1 oignon", "1 l de bouillon de légumes", "1 c. à café de gingembre en poudre", "sel"],
     ["Faire revenir l'oignon émincé, ajouter les carottes en rondelles et le bouillon.", "Cuire 25 minutes, puis mixer avec le jus des oranges et le gingembre."], 30, "velouté"),
    ("Soupe de potiron aux châtaignes", ["1 kg de potiron", "200 g de marrons", "1 oignon", "1 l de bouillon de légumes", "10 cl de crème liquide", "sel, poivre"],
     ["Faire revenir l'oignon, ajouter le potiron en cubes, les marrons et le bouillon.", "Cuire 25 minutes et mixer avec la crème."], 30, "velouté"),
    ("Salade de lentilles corail au citron", ["250 g de lentilles corail", "1 oignon rouge", "1 citron", "1/2 botte de coriandre fraîche", "4 c. à soupe d'huile d'olive", "1 c. à café de cumin en poudre", "sel"],
     ["Cuire les lentilles 8 minutes en les gardant fermes, puis les refroidir.", "Mélanger avec l'oignon émincé, la coriandre, le jus du citron, l'huile et le cumin."], 8, "salade composée"),
    ("Poulet au curry et aux pommes", ["4 blancs de poulet", "2 pommes", "1 oignon", "1 c. à soupe de curry", "20 cl de crème fraîche", "2 c. à soupe d'huile de colza", "sel"],
     ["Faire dorer le poulet en morceaux dans l'huile avec l'oignon.", "Ajouter le curry et les pommes en dés, puis la crème.", "Laisser mijoter 15 minutes."], 25, "plat"),
    ("Saumon au four, pommes de terre et aneth", ["4 pavés de saumon", "800 g de pommes de terre grenaille", "1/2 botte d'aneth", "1 citron", "3 c. à soupe d'huile d'olive", "sel, poivre"],
     ["Rôtir les pommes de terre coupées en deux 25 minutes à 200 °C avec l'huile.", "Ajouter le saumon, l'aneth et des rondelles de citron, et cuire encore 12 minutes."], 37, "plat"),
    ("Semoule aux légumes et aux pois chiches", ["250 g de semoule de blé", "2 courgettes", "2 carottes", "1 boîte de pois chiches (400 g)", "1 c. à café de ras el hanout", "3 c. à soupe d'huile d'olive", "sel"],
     ["Faire revenir les légumes en dés avec le ras el hanout dans l'huile 15 minutes.", "Ajouter les pois chiches égouttés.", "Faire gonfler la semoule dans 25 cl d'eau bouillante salée et servir avec les légumes."], 20, "plat"),
    ("Tarte Tatin", ["1 pâte brisée", "1 kg de pommes", "120 g de sucre", "60 g de beurre"],
     ["Faire un caramel avec le sucre et le beurre dans un moule allant sur le feu.", "Y serrer les pommes en quartiers et cuire 10 minutes.", "Couvrir de pâte, rentrer les bords et cuire 30 minutes à 200 °C. Retourner tiède."], 40, "tarte aux fruits"),
    ("Salade de poulet, mangue et avocat", ["2 blancs de poulet", "1 mangue", "2 avocats", "150 g de mesclun", "1 citron vert", "3 c. à soupe d'huile d'olive", "sel"],
     ["Cuire le poulet en lanières à la poêle 6 minutes.", "Couper la mangue et les avocats en dés.", "Mélanger avec le mesclun et assaisonner de jus de citron vert et d'huile."], 6, "salade composée"),
]


def en_plus() -> Iterator[R]:
    for titre, lignes, etapes, cuisson, base in EN_PLUS:
        texte = " ".join(etapes)
        repos = 120 if "2 heures" in texte else 60 if "1 heure" in texte else 0
        yield R(titre=titre, lignes=lignes, etapes=etapes, prep=15, cuisson=cuisson, repos=repos, base=base)


GENERATEURS = [veloutes, gratins, rotis, purees, poelees, quiches, omelettes, risottos, pates, curries, sautes,
               papillotes, salades, soupes, plats, crumbles, compotes, clafoutis, tartes_fruits, gateaux, desserts, en_plus, parcours]


def toutes() -> list[R]:
    recettes: list[R] = []
    vus: set[str] = set()
    for g in GENERATEURS:
        for r in g():
            ident = r.id or slug(r.titre)
            if ident in vus:
                raise SystemExit(f"identifiant en double dans le générateur : {ident}")
            vus.add(ident)
            recettes.append(r)
    par_titre = {r.titre: r for r in recettes}
    for aliment, liste in PARCOURS_EXISTANTS.items():
        for niveau, titre, pourquoi in liste:
            if titre not in par_titre:
                raise SystemExit(f"parcours {aliment} : recette introuvable « {titre} »")
            par_titre[titre].decouverte = {"aliment": aliment, "niveau": niveau, "pourquoi": pourquoi}
    return recettes


def main() -> int:
    essai = "--essai" in sys.argv
    ref = charger()
    n = Normaliseur(ref)
    existants = {d.get("id") for _, d in lire_recettes()}
    ecrites = ignorees = 0
    erreurs = 0
    for r in toutes():
        d = r.en_dict()
        c = controler(f"{d['id']}.yaml", d, n, ref)
        if not c.publiable:
            erreurs += 1
            print(f"NON PUBLIABLE {d['id']} : {c.erreurs} {[ (l.texte, l.motif) for l in c.lignes_a_relire]}")
            continue
        if d["id"] in existants:
            ignorees += 1
            continue
        ecrites += 1
        if not essai:
            (DOSSIER_RECETTES / f"{d['id']}.yaml").write_text(
                yaml.safe_dump(d, allow_unicode=True, sort_keys=False, width=110), encoding="utf-8")
    print(f"{ecrites} recettes {'publiables' if essai else 'écrites'}, {ignorees} déjà présentes, {erreurs} non publiables")
    return 1 if erreurs else 0


if __name__ == "__main__":
    sys.exit(main())
