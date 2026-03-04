<!-- 
==============================================================================
META-INFORMATIONS (Usage interne)

Fichier      : task_protocol.md
Description  : Manuel d'exécution des tâches. Définit le cycle technique strict de 
               passage d'une tâche de l'état "À Faire" (Task_App1) à "Validé" (Task_App2).
==============================================================================
-->

# 🛠 PROTOCOLE D'EXÉCUTION DES TÂCHES
**Version :** 1.1
**Framework :** Speckit.Factory

> Ce protocole dicte la chaîne de responsabilité de la production de code. Aucune étape ne peut être contournée ou fusionnée.

## 1. CYCLE DE VIE ARCHITECTURAL (LA BOUCLE LANGGRAPH)
Toute tâche soumise au framework traverse obligatoirement les 4 étapes de l'orchestrateur (`core/graph.py`) :

1. **Extraction & Cadrage** (Agent: `subagent_analysis`)
   - Analyse de la tâche cible au regard de la Constitution.
   - Vérification de l'absence de conflits avec le code existant (`Task_App2`).
   - Découpage atomique de la tâche.
2. **Production** (Agent: `subagent_impl`)
   - Écriture du code brut, froid, sans dériver du plan fourni par l'Analyste.
   - Les sorties LLM sont contraintes par les schémas stricts Pydantic (`core/guard.py`).
3. **Audit de Conformité** (Agent: `subagent_verify`)
   - Double vérification de sécurité par un agent indépendant.
   - En cas de REJET (Faille, Hallucination librairie), retour automatique à l'étape 2 (Production) avec les retours de l'Auditeur.
4. **Sanctuarisation** (CLI)
   - Si l'Audit est APPROUVÉ, l'Utilisateur valide. 
   - La tâche est marquée `[x]` dans `etapes.md` et son code/résumé déplacé dans l'Historique Technique (`Task_App2/`).

## 2. STANDARD DE TRAÇABILITÉ DU CODE
Pour garantir la cohérence dans le temps, chaque fichier source majeur créé ou modifié par l'agent `IMPL` doit comporter ce bloc de métadonnées en en-tête (adapté selon le langage) :

```text
/**
 * @SPEC-KIT-TASK: [ID_DE_LA_TACHE ou NOM]
 * @CONSTITUTION-HASH: [HASH_ACTUEL depuis .spec-lock.json]
 * @STATUS: VALIDATED
 */
```

## 3. GESTION DES DÉPENDANCES ET IMPORTS
* L'ajout d'un import externe non déclaré dans `CONSTITUTION.md` entraîne l'échec immédiat de l'Audit (Étape 3).
* Si l'Agent d'implémentation est bloqué par manque d'une dépendance critique, il doit écrire un code d'erreur formaté obligeant l'Utilisateur à amender la Constitution au préalable.