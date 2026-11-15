"""Règles de détection d'injection directe et de jailbreak, en français et en anglais.

Les motifs s'appliquent à un texte *plié* (minuscule, sans accents, voir ``core.text.fold``).
Chaque règle porte un poids dans [0 ; 1] ; les poids se combinent en « ou bruité »
(1 - Π(1 - wᵢ)), plafonné : plusieurs signaux faibles convergent vers un score élevé,
sans qu'un seul mot-clé suffise à atteindre le seuil de blocage.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Rule:
    id: str
    category: str  # override | exfiltration | jailbreak | role_hijack | delimiter
    weight: float
    pattern: re.Pattern[str]


def _r(rule_id: str, category: str, weight: float, regex: str) -> Rule:
    return Rule(rule_id, category, weight, re.compile(regex, re.IGNORECASE))


_ADJ = r"(?:\w+\s+){0,3}"  # jusqu'à trois mots intercalés (« toutes tes », « all of your »…)
_NOUN_FR = r"(?:regles?|instructions?|consignes?|directives?|contraintes?|restrictions?|limites?|securite|garde-?fous?|filtres?|politiques?|protections?|verifications?|blocages?)"
_NOUN_EN = r"(?:instructions?|rules?|guidelines?|prompts?|restrictions?|constraints?|safeguards?|filters?|guardrails?|programming)"
_SECRET = r"(?:cles?(?:\s+api)?|api[ _-]?keys?|mots?\s+de\s+passe|passwords?|secrets?|tokens?|jetons?|prompt\s+(?:systeme|initial)|system\s+prompt|instructions?\s+systeme|identifiants?|credentials?|configuration\s+interne|instructions?\s+(?:internes?|cachees?|initiales?)|donnees\s+confidentielles|informations?\s+confidentielles|memoire\s+secrete)"

RULES: tuple[Rule, ...] = (
    # --- Contournement des consignes ------------------------------------------------
    _r("override_fr", "override", 0.80,
       rf"\b(?:ignore|ignores|ignorez|ignorer|oublie|oubliez|oublier|neglige|negligez|desobeis|desobeissez|desobeir|abandonne|abandonnez|annule|annulez|contourne|contournez|contourner|desactive|desactivez|remplace|remplacez|ignorant|oubliant|contournant|desactivant|mets?\s+de\s+cote|fais\s+abstraction\s+de)\b\s+{_ADJ}{_NOUN_FR}"),
    _r("stop_following", "override", 0.70,
       rf"\b(?:ne\s+(?:respecte|respectez|suis|suivez|tiens|tenez)\s+plus|ne\s+(?:fais|faites)\s+pas\s+attention\s+(?:a|aux?)|n'obeis\s+plus\s+(?:a|aux?)|ne\s+tiens?\s+plus\s+compte)\b\s+{_ADJ}{_NOUN_FR}"),
    _r("replace_with_these", "override", 0.60,
       r"\b(?:remplace|remplacez|replace)\b[^.!?\n]{0,40}\b(?:instructions?|consignes?|regles?)\b[^.!?\n]{0,30}\b(?:par\s+celles?-ci|by\s+these|with\s+these|par\s+les\s+suivantes)"),
    _r("override_en", "override", 0.80,
       rf"\b(?:ignore|disregard|forget|override|bypass|drop|discard)\b\s+{_ADJ}{_NOUN_EN}"),
    _r("override_prev", "override", 0.70,
       r"\b(?:ignore|disregard|forget)\b\s+(?:everything|all)\s+(?:above|before|previous|prior|that)"),
    _r("override_prev_fr", "override", 0.70,
       r"\b(?:ignore|oublie|oubliez)\b\s+tout\s+(?:ce\s+qui|ce\s+que)\s+(?:precede|a\s+ete\s+dit|est\s+ecrit)"),
    _r("new_instructions", "override", 0.55,
       r"\b(?:nouvelles?\s+(?:instructions?|consignes?|regles?|directives?)|nouvel\s+objectif|new\s+(?:instructions?|rules?|task))\b\s*(?::|=|-)"),
    _r("from_now_on", "override", 0.45,
       r"\b(?:a\s+partir\s+de\s+maintenant|desormais|from\s+now\s+on)\b[^.!?\n]{0,60}\b(?:tu\s+(?:dois|vas|es)|you\s+(?:must|will|are|shall)|obeis|obey)\b"),
    # --- Exfiltration de secrets ------------------------------------------------------
    _r("reveal_fr", "exfiltration", 0.70,
       rf"\b(?:revel\w*|affich\w*|donn\w*|montr\w*|communiqu\w*|divulgu\w*|devoil\w*|exfiltr\w*|transm\w*|recopi\w*|imprim\w*|ecri\w+|list\w*|recit\w*|remet\w*|dis[- ]moi|envoie[- ]moi)\b(?!-t-|-il\b|-elle\b)[^.!?\n]{{0,40}}\b{_SECRET}"),
    _r("reveal_possessive", "exfiltration", 0.70,
       rf"\b(?:revel\w*|affich\w*|donn\w*|montr\w*|communiqu\w*|divulgu\w*|devoil\w*|transm\w*|recopi\w*|imprim\w*|ecri\w+|recit\w*|contenir|inclure|include|contain|fournis\w*|remets?\w*)\b(?!-t-|-il\b|-elle\b)[^.!?\n]{{0,70}}\b(?:ta|ton|tes|votre|vos|your)\s+(?:\w+\s+){{0,2}}{_SECRET}"),
    _r("secret_possessive", "exfiltration", 0.50,
       r"\b(?:ta|ton|tes|votre|vos|your)\s+(?:\w+\s+){0,1}(?:cles?(?:\s+(?:api|secrete|privee))?|api[ _-]?keys?|mots?\s+de\s+passe|prompt\s+(?:systeme|initial)|system\s+prompt|instructions?\s+(?:secretes?|cachees?|systeme))"),
    _r("what_is_secret", "exfiltration", 0.55,
       rf"\b(?:quelle?s?\s+(?:est|sont)|what\s+(?:is|are))\s+(?:la\s+|le\s+|ta\s+|tes\s+|your\s+|the\s+)?{_SECRET}[^.!?\n]{{0,30}}\b(?:ton|ta|tes|votre|systeme|system|your)\b"),
    _r("secret_instructions_probe", "exfiltration", 0.60,
       r"\b(?:quelles?\s+(?:sont\s+)?(?:tes\s+|vos\s+)?instructions?\s+(?:secretes?|cachees?|initiales?|internes?)|que\s+(?:contient|dit|renferme)\s+(?:ton|tes|votre)\s+(?:prompt|instructions?|contexte)|what\s+(?:are|were)\s+your\s+(?:secret|hidden|initial)\s+instructions?)"),
    _r("env_file", "exfiltration", 0.55,
       r"\b(?:lis|lire|lisez|envoie\w*|recopi\w*|affich\w*|copie\w*|montr\w*|read|send|print|show|cat)\b[^.!?\n]{0,40}\.env(?![.\w])"),
    _r("exfiltrate_word", "exfiltration", 0.60, r"\bexfiltr\w+"),
    _r("reveal_en", "exfiltration", 0.70,
       rf"\b(?:reveal|show|print|display|leak|expose|output|tell\s+me|give\s+me|share|send\s+me|repeat|dump|write\s+out|recite)\b[^.!?\n]{{0,40}}\b{_SECRET}"),
    _r("system_prompt_probe", "exfiltration", 0.65,
       r"\b(?:what|quel(?:le)?s?|quoi)\b[^.!?\n]{0,25}\b(?:your|ton|tes|votre|vos)\b[^.!?\n]{0,15}\b(?:system\s+prompt|initial\s+instructions?|prompt\s+systeme|instructions?\s+initiales?)"),
    _r("repeat_above", "exfiltration", 0.60,
       r"\b(?:repeat|repete|repeter|repetez|recite|reciter)\b[^.!?\n]{0,30}\b(?:above|everything\s+before|mots?\s+ci-dessus|tout\s+ce\s+qui\s+precede|your\s+instructions)"),
    # --- Jailbreak / jeu de rôle -------------------------------------------------------
    _r("dan", "jailbreak", 0.75, r"\b(?:dan\s+mode|do\s+anything\s+now|\bdan\b\s+(?:prompt|jailbreak)|tu\s+es\s+dan|you\s+are\s+dan)\b"),
    _r("dev_mode", "jailbreak", 0.65,
       r"\b(?:active\w*|activate|enable|passe\w*\s+en|tu\s+es\s+(?:maintenant\s+)?en|you\s+are\s+(?:now\s+)?in|enter|entre\w*\s+en)\b\s+(?:le\s+|the\s+)?(?:mode\s+(?:developpeur|dieu|debug|maintenance|test\s+interne|sans\s+(?:filtre|garde-?fous?|limites?|restrictions?))|developer\s+mode|god\s+mode|jailbreak)"),
    _r("jailbreak_word", "jailbreak", 0.30, r"\b(?:jailbreak(?:ed)?|debridage)\b"),
    _r("no_restrictions", "jailbreak", 0.70,
       r"\b(?:sans\s+(?:aucune?\s+)?(?:restriction|limite|filtre|censure|regle)s?|n'as\s+(?:pas\s+de|aucune?|plus\s+de)\s+(?:regles?|limites?|restrictions?|filtres?)|libre\s+de\s+toute\s+(?:regle|restriction|limite|contrainte)|(?:regles?|restrictions?|limites?)\b[^.!?\n]{0,30}\bn'existent?\s+pas|aucune\s+(?:restriction|limite|regle|contrainte)|no\s+(?:restrictions?|limits?|rules?|filters?|censorship|ethical\s+guidelines?)|without\s+(?:any\s+)?(?:restrictions?|limits?|rules?|filters?|censorship))\b"),
    _r("pretend", "jailbreak", 0.50,
       r"\b(?:fais\s+comme\s+si|fais\s+semblant|pretend\s+(?:that\s+)?(?:you|to\s+be)|imagine\s+que\s+tu|act\s+as\s+(?:if|though)|simule\s+(?:que|un|une))\b[^.!?\n]{0,60}\b(?:aucune?\s+(?:regle|restriction|limite)|sans\s+(?:regle|limite|restriction)|no\s+(?:rules?|restrictions?|limits?)|libre|unrestricted|illimite|jamais\s+refuse|never\s+refuse)"),
    _r("persona", "jailbreak", 0.45,
       r"\b(?:tu\s+es\s+maintenant|you\s+are\s+now|joue\s+le\s+role\s+d|play\s+the\s+role\s+of|agis\s+comme|act\s+as)\b[^.!?\n]{0,60}\b(?:sans\s+(?:filtre|limite|restriction)|unfiltered|uncensored|unrestricted|evil|malveillant|hacker|pirate)"),
    _r("fake_mode", "jailbreak", 0.55,
       r"\b(?:fais\s+semblant|pretend|simule\w*|imagine\w*)\b[^.!?\n]{0,40}\b(?:maintenance|mode\s+debug|mode\s+admin\w*|mode\s+developpeur)\b|\bdans\s+ce\s+mode\b[^.!?\n]{0,30}\b(?:affich|revel|donn|montr)\w*"),
    _r("instructions_replace_yours", "override", 0.60,
       r"\b(?:mes|ces|nos)\s+(?:instructions?|consignes?|ordres?|directives?)\s+(?:remplacent|prevalent|priment|ont\s+(?:la\s+)?priorite)|\binstruction\s+prioritaire\b"),
    _r("explicit_tool_call", "tool", 0.55,
       r"\b(?:appelle|appelez|utilise|utilisez|call|use|invoke|execute|run|lance)\b[^.!?\n]{0,25}\b(?:send_email|delete_file|read_file|browse_web|read_email)\b"),
    _r("cover_tracks", "exfiltration", 0.50,
       r"\b(?:efface\w*|supprim\w+|vide\w*|delete|erase|clear)\b[^.!?\n]{0,30}\b(?:historique|journal|journaux|logs?|traces?|audit)\b[^.!?\n]{0,40}\b(?:securite|audit|evenements|security)"),
    _r("never_refuse", "jailbreak", 0.50,
       r"\b(?:ne\s+refuse\s+jamais|ne\s+dis\s+jamais\s+non|never\s+refuse|never\s+say\s+no|answer\s+everything|reponds?\s+a\s+tout)\b"),
    # --- Détournement du rôle / délimiteurs --------------------------------------------
    _r("role_tag", "delimiter", 0.50,
       r"(?:^|\n|\s)(?:\[/?(?:system|inst|assistant)\]|<\|?(?:system|im_start|endoftext)\|?>|#{2,}\s*(?:system|instruction)|<<\s*sys\s*>>|system\s*:\s*you\s+are)"),
    _r("end_of_prompt", "delimiter", 0.50,
       r"\b(?:fin\s+(?:des?\s+)?(?:instructions?|du\s+prompt)|end\s+of\s+(?:instructions?|prompt|system)|---\s*end\s*---)\b"),
    # --- Actions dangereuses demandées directement --------------------------------------
    _r("forward_all_mails", "exfiltration", 0.55,
       r"\b(?:transfere|transferez|forward|redirige|redirigez|envoie|envoyez|send)\b[^.!?\n]{0,30}\b(?:tous?\s+(?:les\s+)?(?:mails?|emails?|courriels?|messages?|fichiers?)|all\s+(?:the\s+)?(?:mails?|emails?|messages?|files?))\b"),
    _r("delete_all", "exfiltration", 0.55,
       r"\b(?:supprime\w*|suppression|efface\w*|delete|erase|wipe)\b[^.!?\n]{0,30}\b(?:tous?\s+(?:les\s+)?fichiers?|all\s+(?:the\s+)?files?|everything)\b"),
)

MAX_RULE_SCORE = 0.98


@dataclass(frozen=True)
class RuleHit:
    rule_id: str
    category: str
    weight: float


_QUOTES = re.compile(r"[«»\"“”‘’`]")
_LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s"})


def _variants(folded_text: str) -> list[str]:
    base = _QUOTES.sub(" ", folded_text)
    base = re.sub(r"\s+", " ", base)
    variants = [base]
    leet = base.translate(_LEET)
    if leet != base:
        variants.append(leet)
    return variants


def match_rules(folded_text: str) -> list[RuleHit]:
    """Retourne les règles déclenchées par un texte déjà plié (variante leetspeak incluse)."""
    seen: dict[str, RuleHit] = {}
    for text in _variants(folded_text):
        for r in RULES:
            if r.id not in seen and r.pattern.search(text):
                seen[r.id] = RuleHit(r.id, r.category, r.weight)
    return list(seen.values())


def combine(weights: list[float]) -> float:
    """Combinaison « ou bruité » plafonnée à ``MAX_RULE_SCORE``."""
    prob_none = 1.0
    for w in weights:
        prob_none *= 1.0 - w
    return min(MAX_RULE_SCORE, 1.0 - prob_none)
