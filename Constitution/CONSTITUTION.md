# 1. PILIER ARCHITECTURAL
Ce projet est un framework d'automatisation des tâches de développement. 
Il utilise Python, LangChain, et LangGraph comme orchestrateur. 
Les interactions se font via CLI (Click).

# 2. PILIER DE SÉCURITÉ
Seul le fichier `.spec-lock.json` fait autorité pour le verrouillage de contexte.
Aucun `eval()` ne doit être utilisé pour parser le retour des LLMs.

# 3. PILIER DE PERFORMANCE
Tous les échanges LLM doivent utiliser les modèles définis dynamiquement.

# 4. PILIER DE MAINTENANCE
Le code source est dans `core/` et les prompts dans `agents/`.
Architecture modulaire et agnostique.
