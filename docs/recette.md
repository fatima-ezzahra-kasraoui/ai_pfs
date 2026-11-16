# Recette R1 / R3 / R5 — volet détection (É1)

Les chiffres et captures sont à produire pendant la recette, avec l'agent réel et l'interface ; ce document ne contient aucun résultat.

| Scénario | Preuve automatisable (modules d'É1) | Preuve à collecter en recette |
|---|---|---|
| R1 injection directe | `python -m evaluation.demo_scenarios` : Guard A score > seuil de blocage | capture de l'Overview + entrée Audit Trail |
| R3 injection indirecte | idem : Guard B bloque l'e-mail piégé (commentaire HTML) | capture Audit Trail avec la raison du verdict |
| R5 fuite de faux secret | idem : Guard D masque `sk-****`, canary détecté | capture de la réponse masquée ; vérifier qu'aucune valeur brute n'apparaît dans l'interface |

Mode opératoire : lancer le script avec l'agent réel d'É2 (`--agent http`) une fois disponible, noter date, commit et résultat ;
un échec est noté tel quel avec son identifiant de scénario.
