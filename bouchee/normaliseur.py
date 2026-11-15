"""Normaliseur de lignes d'ingrédients en français, à base de règles (tâche D du sprint 1).

Pour une ligne comme « 2 c. à soupe de pesto maison », il extrait la quantité, l'unité et
le nom, puis résout le nom vers des identifiants du référentiel par le dictionnaire d'alias.

Règle d'or : ne jamais deviner. Un nom est résolu seulement s'il correspond exactement à un
nom ou un alias du référentiel, après des transformations sûres et listées ici :
- retrait des précisions entre parenthèses et des mentions de préparation (« émincé ») ;
- passage au singulier, mot à mot ;
- découpage des lignes à plusieurs ingrédients (« sel, poivre », « beurre ou margarine »).
Tout le reste est signalé pour relecture humaine (statut « a_relire »).

« Beurre ou margarine » est résolu vers les deux ingrédients : on ne sait pas lequel sera
utilisé, donc le validateur strict les vérifie tous les deux.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from fractions import Fraction

from bouchee.referentiel import Referentiel, normaliser_nom

CONFIANCE_EXACTE = 1.0
CONFIANCE_TRANSFORMEE = 0.95
CONFIANCE_GENERIQUE = 0.8  # sous le seuil du validateur : la ligne doit être relue

NOMBRES_EN_LETTRES = {
    "un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "six": 6, "sept": 7,
    "huit": 8, "neuf": 9, "dix": 10, "onze": 11, "douze": 12, "quinze": 15, "vingt": 20,
    "demi": 0.5, "demie": 0.5,
}
FRACTIONS_UNICODE = {"½": 0.5, "¼": 0.25, "¾": 0.75, "⅓": 1 / 3, "⅔": 2 / 3}

# Unités : forme canonique -> variantes (déjà normalisées : minuscules, sans accents)
UNITES: dict[str, list[str]] = {
    "g": ["g", "g.", "gr", "gr.", "grammes", "gramme"],
    "kg": ["kg", "kilo", "kilos", "kilogramme", "kilogrammes"],
    "mg": ["mg"],
    "ml": ["ml", "millilitres", "millilitre"],
    "cl": ["cl", "centilitres", "centilitre"],
    "dl": ["dl", "decilitres", "decilitre"],
    "l": ["l", "litre", "litres"],
    "c. à soupe": [
        "c. a soupe", "c.a soupe", "c a soupe", "c. a s.", "c.a.s.", "c.a.s", "cas", "cs", "c.s.", "c.s",
        "cuillere a soupe", "cuilleres a soupe", "cuil. a soupe", "cuill. a soupe", "cuillerees a soupe",
        "cuilleree a soupe", "grosse cuillere", "grosses cuilleres", "cuiller a soupe", "cuillers a soupe",
        "c. soupe", "cuil. soupe", "c a s", "c. a table", "c a table", "c.a.t.", "cuillere a table", "cuilleres a table",
        "cuiller a table", "cuillers a table", "cuilleree a table", "cuillerees a table", "cuil.soupe", "a soupe", "a table",
    ],
    "c. à café": [
        "c. a cafe", "c.a cafe", "c a cafe", "c. a c.", "c.a.c.", "c.a.c", "cac", "cc", "c.c.", "c.c",
        "cuillere a cafe", "cuilleres a cafe", "cuil. a cafe", "cuill. a cafe", "cuilleree a cafe",
        "cuillerees a cafe", "petite cuillere", "petites cuilleres", "cuiller a cafe", "cuillers a cafe",
        "cuillere a the", "cuilleres a the", "cuiller a the", "c. a the", "c. cafe", "c a c", "c a the", "cuil.cafe", "a cafe", "a the",
    ],
    "c. à dessert": ["c. a dessert", "c a dessert", "cuillere a dessert", "cuilleres a dessert", "cuiller a dessert",
                     "cuillers a dessert", "cuilleree a dessert", "cuillerees a dessert", "a dessert"],
    "cuillère": ["cuillere", "cuilleres", "cuiller", "cuillers", "cuilleree", "cuillerees"],
    "plaque": ["plaque", "plaques"],
    "pied": ["pied", "pieds"],
    "goutte": ["goutte", "gouttes"],
    "barquette": ["barquette", "barquettes"],
    "pincée": ["pincee", "pincees", "prise", "prises", "pointe de couteau", "pointe", "soupcon"],
    "gousse": ["gousse", "gousses"],
    "tranche": ["tranche", "tranches"],
    "boîte": ["boite", "boites"],
    "sachet": ["sachet", "sachets"],
    "brin": ["brin", "brins"],
    "branche": ["branche", "branches"],
    "feuille": ["feuille", "feuilles"],
    "botte": ["botte", "bottes"],
    "bouquet": ["bouquet", "bouquets"],
    "verre": ["verre", "verres"],
    "tasse": ["tasse", "tasses"],
    "bol": ["bol", "bols"],
    "noix": ["noix"],
    "noisette": ["noisette", "noisettes"],
    "morceau": ["morceau", "morceaux"],
    "poignée": ["poignee", "poignees"],
    "filet": ["filet", "filets"],
    "trait": ["trait", "traits"],
    "pot": ["pot", "pots"],
    "paquet": ["paquet", "paquets"],
    "rouleau": ["rouleau", "rouleaux"],
    "bocal": ["bocal", "bocaux"],
    "cube": ["cube", "cubes"],
    "louche": ["louche", "louches"],
    "tige": ["tige", "tiges"],
    "zeste": ["zeste", "zestes"],
    "pavé": ["pave", "paves"],
    "boule": ["boule", "boules"],
    "quelques": ["quelques"],
    "un peu": ["un peu", "un petit peu", "peu"],
}
_UNITES_INVERSE = sorted(((v, k) for k, vs in UNITES.items() for v in vs), key=lambda x: -len(x[0]))

# Mentions de préparation ou d'état, retirées du nom (comparées sur la forme normalisée)
QUALIFICATIFS = sorted({
    "frais", "fraiche", "fraiches", "hache", "hachee", "haches", "hachees", "finement", "grossierement",
    "emince", "emincee", "emincees", "eminces", "cisele", "ciselee", "ciselees", "rape", "rapee", "rapes",
    "rapees", "coupe", "coupee", "coupes", "coupees", "en des", "en petits des", "en cubes", "en rondelles",
    "en lamelles", "en morceaux", "en quartiers", "en tranches", "en julienne", "en batonnets", "en fines lamelles",
    "en fines rondelles", "en deux", "en 2", "en 4", "en quatre", "pele", "pelee", "peles", "pelees",
    "epepine", "epepinee", "epepines", "epepinees", "egoutte", "egouttee", "egouttes", "egouttees", "mur",
    "mure", "murs", "mures", "gros", "grosse", "grosses", "petit", "petite", "petits", "petites", "moyen",
    "moyenne", "moyens", "moyennes", "bio", "entier", "entiere", "entiers", "entieres", "fondu", "fondue",
    "mou", "molle", "ramolli", "pommade", "tiede", "froid", "froide", "bien", "environ", "surgele",
    "surgelee", "surgeles", "surgelees", "en conserve", "en boite", "nature", "battu", "battus", "battue",
    "cuit", "cuite", "cuits", "cuites", "sec", "seche", "secs", "seches", "concasse", "concassee", "ecrase",
    "ecrasee", "ecrases", "presse", "pressee", "tranche", "tranchee", "lave", "lavee", "laves", "lavees",
    "de saison", "a temperature ambiante", "au gout", "selon le gout", "a votre gout", "facultatif",
    "facultative", "maison", "du commerce", "de bonne qualite", "extra", "vierge", "tres", "beau", "belle",
    "beaux", "belles", "jeunes", "jeune", "frit", "dore", "doree", "torrefie", "torrefies", "grille",
    "grilles", "grillee", "grillees", "effeuille", "effeuillee", "equeute", "equeutees", "dessale",
    "dessalee", "decortique", "decortiquees", "decortiques", "nettoye", "nettoyes", "nettoyees", "rouge",
    "rouges", "vert", "verts", "jaune", "jaunes", "blanc", "blancs", "blanche", "blanches",
    "en poudre", "moulu", "moulue", "moulus", "fruite", "fruitee", "monde", "mondee", "mondees", "dur", "durs",
    "fume", "fumee", "fumes", "fumees", "sechee", "sechees", "vegetal", "vegetale",
    "a chair ferme", "a chair farineuse", "de taille moyenne", "du pays", "en lanieres", "multicolores",
    "eventuellement", "de preference",
    "fraichement moulu", "fraichement moulue", "fraichement rape", "fraichement rapee", "du moulin", "au moulin",
    "moulu fraichement", "denoyaute", "denoyautee", "denoyautes", "denoyautees", "non sale", "non salee", "non sales",
    "non salees", "non sucre", "non sucree", "rassis", "rassie", "tamise", "tamisee", "tamises", "epluche", "epluchee",
    "epluches", "epluchees", "ecrasees", "lyophilise", "lyophilisee", "emiette", "emiettee", "pile", "pilee", "piles",
    "pilees", "roti", "roties", "rotis", "rince", "rinces", "rincee", "rincees", "cremeux", "cremeuse", "en feuilles",
    "en languettes", "en morceau", "en lanieres", "en petits morceaux", "en gros morceaux", "decoupe", "decoupee",
    "decoupes", "decoupees", "verte", "vertes", "bien mur", "bien mure", "bien murs", "bien mures", "de bonne taille",
    "decongele", "decongelee", "precuit", "precuite", "precuits", "egrene", "egrenee", "effile", "effilee", "effilees",
    "suivant gout", "suivant le gout", "a volonte", "pour decorer", "pour la decoration", "fondus", "fondues",
    "grand", "grande", "grands", "grandes", "cru", "crue", "crus", "crues", "pressees", "presses", "menu",
}, key=lambda x: -len(x))
# Débuts de précisions d'usage : tout ce qui suit est retiré (« beurre pour le moule »)
COUPURES = ("pour ", "+ ", "a peu pres", "plus ", "selon ")
MOTS_LIAISON = ("de la ", "de l'", "des ", "du ", "de ", "d'")
ARTICLES = ("le ", "la ", "les ", "l'", "un ", "une ")
PREFIXES_IGNORES = ("environ ", "eventuellement ", "pas plus d'", "pas plus de ", "au moins ")
TAILLES = ("grandes ", "grande ", "grands ", "grand ", "petites ", "petite ", "petits ", "petit ",
           "grosses ", "grosse ", "gros ", "belles ", "belle ", "beaux ", "beau ", "bonne ", "bonnes ")

SEPARATEURS = re.compile(r"\s*(?:,|;|&|\bet\b|\bou\b|/|\s-\s)\s*")
# « le jus d'un citron », « le zeste de 2 oranges » : le nombre de fruits ne change pas l'ingrédient
JUS_DE = re.compile(r"^(?:le |la |les )?(jus|zeste|zestes|ecorce|pulpe) (?:d'un |d'une |de \d+(?:[.,]\d+)? |d'\d+ |d'(?=[aeiouy]))(?:demi-|demi )?")


@dataclass
class LigneNormalisee:
    texte: str
    quantite: float | None = None
    quantite_max: float | None = None
    unite: str | None = None
    nom: str = ""
    ingredients: list[str] = field(default_factory=list)
    confiance: float = 0.0
    facultatif: bool = False
    statut: str = "a_relire"  # "resolue" ou "a_relire"
    motif: str | None = None

    def en_dict(self) -> dict[str, object]:
        return {k: v for k, v in self.__dict__.items() if v not in (None, [], "")}


class Normaliseur:
    def __init__(self, ref: Referentiel):
        self.ref = ref
        self.index: dict[str, str] = {}
        for ing in ref.ingredients.values():
            for nom in (ing.nom, *ing.alias_fr, *ing.alias_en):
                self.index.setdefault(normaliser_nom(nom), ing.id)

    # --- quantité et unité -------------------------------------------------

    @staticmethod
    def _nombre(jeton: str) -> float | None:
        jeton = jeton.strip()
        if jeton in FRACTIONS_UNICODE:
            return FRACTIONS_UNICODE[jeton]
        if jeton in NOMBRES_EN_LETTRES:
            return float(NOMBRES_EN_LETTRES[jeton])
        try:
            if "/" in jeton:
                return float(Fraction(jeton))
            return float(jeton.replace(",", "."))
        except (ValueError, ZeroDivisionError):
            return None

    _NOMBRE = (
        r"(?:\d+(?:[.,]\d+)?(?:\s*/\s*\d+)?(?!\d)|[½¼¾⅓⅔]"
        r"|(?:une|un|deux|trois|quatre|cinq|six|sept|huit|neuf|dix|onze|douze|quinze|vingt|demie|demi)\b)"
    )
    _QUANTITE = re.compile(
        rf"^(?P<a>{_NOMBRE})(?:\s+(?P<frac>\d+/\d+))?(?:\s*(?:a|-|ou)\s*(?P<b>{_NOMBRE}))?(?:\s+et\s+demie?\b)?\s*"
    )

    def _extraire_quantite(self, t: str) -> tuple[float | None, float | None, str]:
        m = self._QUANTITE.match(t)
        if not m:
            return None, None, t
        a = self._nombre(m.group("a"))
        if a is None:
            return None, None, t
        if m.group("frac"):
            a += self._nombre(m.group("frac")) or 0
        if re.search(r"\bet\s+demie?\s*$", m.group(0)):
            a += 0.5
        b = self._nombre(m.group("b")) if m.group("b") else None
        reste = t[m.end():]
        # « une demi-botte », « 1/2 »
        if reste.startswith("demi-") or reste.startswith("demi "):
            a *= 0.5
            reste = reste[5:]
        return a, b, reste.strip()

    @staticmethod
    def _extraire_unite(t: str) -> tuple[str | None, str]:
        for taille in TAILLES:  # « 1 petite boîte de maïs »
            if t.startswith(taille):
                unite, reste = Normaliseur._extraire_unite(t[len(taille):])
                if unite:
                    return unite, reste
                break
        for variante, canonique in _UNITES_INVERSE:
            if t == variante:
                return canonique, ""
            if t.startswith(variante) and len(t) > len(variante):
                suite = t[len(variante):]
                if suite[0] in " '" or (variante.endswith(".") and suite[0].isalpha()):
                    reste = suite.strip()
                    for liaison in MOTS_LIAISON:
                        if reste.startswith(liaison):
                            reste = reste[len(liaison):]
                            break
                    return canonique, reste.strip()
        return None, t

    # --- résolution du nom -------------------------------------------------

    @staticmethod
    def _singulier(t: str) -> str:
        mots = []
        for mot in t.split(" "):
            if len(mot) > 3 and mot.endswith("aux") and mot not in ("noix",):
                mot = mot[:-1]  # poireaux -> poireau
            elif len(mot) > 3 and (mot.endswith("s") or mot.endswith("x")) and not mot.endswith(("ss", "us", "noix")):
                mot = mot[:-1]
            mots.append(mot)
        return " ".join(mots)

    @staticmethod
    def _sans_qualificatifs(t: str) -> str:
        precedent = None
        while precedent != t:
            precedent = t
            for coupure in COUPURES:
                i = t.find(coupure)
                if i > 0:
                    t = t[:i].strip()
            for q in QUALIFICATIFS:
                t = re.sub(rf"(?:^|\s){re.escape(q)}(?=$|\s)", " ", t).strip()
                t = re.sub(r"\s+", " ", t)
            t = t.strip(" ,.-")
        return t

    @staticmethod
    def _retirer_fin(t: str) -> str | None:
        """Retire un seul qualificatif en fin de nom (« haricots blancs secs » -> « haricots blancs »)."""
        for q in QUALIFICATIFS:
            if t.endswith(" " + q):
                return t[: -len(q) - 1].strip(" ,")
        return None

    def _chercher(self, nom: str) -> tuple[str | None, float]:
        """Résout un nom exactement, sinon après transformations sûres. Jamais d'approximation."""
        nom = nom.strip(" ,.;")
        for liaison in MOTS_LIAISON + ARTICLES:
            if nom.startswith(liaison):
                nom = nom[len(liaison):]
                break
        essais = [(nom, CONFIANCE_EXACTE), (self._singulier(nom), CONFIANCE_TRANSFORMEE)]
        partiel: str | None = nom
        while partiel := self._retirer_fin(partiel):
            essais += [(partiel, CONFIANCE_TRANSFORMEE), (self._singulier(partiel), CONFIANCE_TRANSFORMEE)]
        nettoye = self._sans_qualificatifs(nom)
        essais += [(nettoye, CONFIANCE_TRANSFORMEE), (self._singulier(nettoye), CONFIANCE_TRANSFORMEE)]
        for essai, confiance in essais:
            if essai and essai in self.index:
                return self.index[essai], confiance
        return None, 0.0

    def _resoudre_segment(self, segment: str) -> tuple[list[str], float, str | None, str]:
        """Renvoie (ingrédients, confiance, motif d'échec, nom retenu) pour un segment sans quantité."""
        segment = segment.strip(" ,.;")
        if not segment:
            return [], 1.0, None, ""
        _, _, sans_quantite = self._extraire_quantite(segment)  # « 3 g de paprika »
        if sans_quantite and sans_quantite != segment:
            return self._resoudre_segment(sans_quantite)
        # Le nom entier d'abord : « noix de cajou » n'est pas « 1 noix de… cajou »
        ident, confiance = self._chercher(segment)
        if ident:
            return [ident], confiance, None, segment
        unite, reste = self._extraire_unite(segment)
        if unite and reste:
            ident, confiance = self._chercher(reste)
            if ident:
                return [ident], confiance, None, reste
        if not self._sans_qualificatifs(segment):
            return [], 1.0, None, ""  # segment purement descriptif (« émincé »)
        return [], 0.0, f"nom non reconnu : « {segment} »", segment

    # --- point d'entrée ----------------------------------------------------

    def est_generique(self, ident: str) -> bool:
        """Catégorie sans aliment de référence (« sauce », « crème », « huile », « porc »).

        Une ligne résolue vers une telle catégorie est trop vague pour être acceptée sans
        relecture : « un trait de sauce » ne dit pas quelle sauce. Les catégories qui sont aussi
        un aliment précis (tomate, saumon) ont un code CIQUAL et ne sont pas concernées.
        """
        return bool(self.ref.enfants[ident]) and not self.ref[ident].ciqual

    def normaliser(self, texte: str) -> LigneNormalisee:
        ligne = self._normaliser(texte)
        generiques = [i for i in ligne.ingredients if self.est_generique(i)]
        if ligne.statut == "resolue" and generiques:
            ligne.statut = "a_relire"
            ligne.confiance = min(ligne.confiance, CONFIANCE_GENERIQUE)
            noms = ", ".join(self.ref[i].nom for i in generiques)
            ligne.motif = f"catégorie trop générale ({noms}) : préciser l'ingrédient ou confirmer à la relecture"
        return ligne

    def _normaliser(self, texte: str) -> LigneNormalisee:
        ligne = LigneNormalisee(texte=texte)
        t = normaliser_nom(texte).replace("⁄", "/")  # « ½ » devient « 1⁄2 » après NFKD
        if t.endswith(":"):
            ligne.motif = "titre de section, pas un ingrédient"
            return ligne
        if any(m in t for m in ("facultatif", "facultative", "si vous aimez", "eventuellement", "si desire")):
            ligne.facultatif = True
        t = re.sub(r"\([^)]*\)", " ", t)
        t = t.replace("[", " ").replace("]", " ").replace("®", "").replace("`", "'")
        t = re.sub(r"^sel-poivre\b", "sel, poivre", t)
        t = re.sub(r"\s+", " ", t).strip(" .,;")
        for prefixe in PREFIXES_IGNORES:
            if t.startswith(prefixe):
                t = t[len(prefixe):]
        if not t:
            ligne.motif = "ligne vide"
            return ligne

        quantite, quantite_max, reste = self._extraire_quantite(t)
        reste = JUS_DE.sub(lambda m: m.group(1) + " de ", reste)
        unite, apres_unite = self._extraire_unite(reste)
        if unite is None and quantite is not None:  # « 1/4 de litre de lait », « 1/2 d'une tasse »
            for liaison in ("de ", "d'une ", "d'un ", "d'"):
                if reste.startswith(liaison):
                    u2, a2 = self._extraire_unite(reste[len(liaison):])
                    if u2:
                        unite, apres_unite = u2, a2
                    break
        if unite == "un peu":  # « un peu de » : le « un » n'est pas une quantité
            quantite = quantite_max = None
        ligne.quantite, ligne.quantite_max = quantite, quantite_max

        # Le nom entier, avec ou sans l'unité (« gousses d'ail » est aussi un alias)
        for candidat, unite_retenue in ((apres_unite, unite), (reste, None)) if unite else ((reste, None),):
            ident, confiance = self._chercher(candidat)
            if ident:
                ligne.unite, ligne.nom = unite_retenue, candidat
                ligne.ingredients, ligne.confiance, ligne.statut = [ident], confiance, "resolue"
                return ligne

        # Plusieurs ingrédients dans la ligne
        ligne.unite = unite
        ids: list[str] = []
        confiances: list[float] = []
        noms: list[str] = []
        for segment in SEPARATEURS.split(apres_unite):
            seg_ids, seg_conf, motif, nom = self._resoudre_segment(segment)
            if motif:
                ligne.nom = apres_unite
                ligne.motif = motif
                return ligne
            for i in seg_ids:
                if i not in ids:
                    ids.append(i)
            if seg_ids:
                confiances.append(seg_conf)
                noms.append(nom)
        if not ids:
            ligne.nom = apres_unite
            ligne.motif = f"aucun ingrédient reconnu dans « {apres_unite} »"
            return ligne
        ligne.nom = ", ".join(noms)
        ligne.ingredients = ids
        ligne.confiance = min(confiances)
        ligne.statut = "resolue"
        return ligne
