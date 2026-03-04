<!-- 
==============================================================================
META-INFORMATIONS (Usage interne)

Fichier      : CONSTITUTION.template.md
Description  : Le modèle de base pour toute nouvelle Constitution.
               Lorsqu'un utilisateur tape `spec init`, ce fichier est copié
               dans le répertoire `Constitution/CONSTITUTION.md` de son projet.
               C'est la Loi Absolue que les agents IA devront respecter.
==============================================================================
-->

# 📜 CONSTITUTION DU PROJET
**Nom du Projet :** [NOM_DU_PROJET]
**Version :** 1.0
**Date d'initialisation :** [DATE]

> **Préliminaire** : Ce document est la source de vérité absolue pour tous les Agents (Analyste, Implémenteur, Auditeur) du framework Speckit.Factory. Toute instruction contredisant ce fichier doit être rejetée. L'intégrité de ce fichier est garantie par `.spec-lock.json`.

---

## 1. STACK TECHNIQUE IMPOSÉE (ANTI-HALLUCINATION)
Les agents ont l'interdiction formelle d'ajouter, de suggérer ou d'installer des bibliothèques non listées ici.

### 1.1 Backend
* **Langage** : [Ex: Python 3.12, Node.js 20, Rust]
* **Framework Core** : [Ex: FastAPI, Express, Actix]
* **Base de données** : [Ex: PostgreSQL 16 via SQLAlchemy, MongoDB]
* **Authentification** : [Ex: JWT, OAuth2]

### 1.2 Frontend (Si applicable)
* **Langage** : [Ex: TypeScript]
* **Framework** : [Ex: React 18, Vue 3, Svelte]
* **Styling** : [Ex: Tailwind CSS, Vanilla CSS]

### 1.3 Outillage & Tests
* **Linter/Formatter** : [Ex: Ruff, ESLint, Prettier]
* **Tests** : [Ex: Pytest, Jest]

---

## 2. RÈGLES D'ARCHITECTURE (LE SANCTUAIRE)
### 2.1 Sanctuarisation du Code (`Task_App2`)
* Le dossier `Task_App2` (ou le dossier principal de votre code) représente l'**Historique Validé**.
* **Règle d'Or** : Un agent ne peut JAMAIS modifier ou refactoriser une fonction existante dans l'historique validé sans un ordre explicite de l'utilisateur ("Bugfix" ou "Refactor"). Le code généré doit toujours être "additif" ou "complémentaire" par défaut.

### 2.2 Structure des Fichiers
* Les contrôleurs / routes doivent toujours se trouver dans : `[CHEMIN_SPECIFIQUE]`
* Les modèles de données doivent se trouver dans : `[CHEMIN_SPECIFIQUE]`

---

## 3. RÈGLES DE SÉCURITÉ ET QUALITÉ STRICTES
Chaque agent `VERIFY` (Auditeur) rejettera automatiquement le travail de l'agent `IMPL` s'il viole ces règles :
1. **Zéro Placeholder** : Interdiction absolue des `FIXME`, `TODO` ou des fonctions mockées du style `pass` ou `return "à implémenter"`.
2. **Validation des Entrées** : Toute donnée provenant de l'utilisateur ou d'une API externe doit être typée et validée (Ex: *Pydantic*, *Zod*).
3. **Séparation des Responsabilités (SOLID)** : Pas de logique métier complexe directement dans les routes de l'API.

---

## 4. FORMAT TÂCHES ET TRAÇABILITÉ
Lors de la création d'un nouveau fichier source, celui-ci doit intégrer l'en-tête de traçabilité officiel :
```text
/**
 * @SPEC-KIT-TASK: [NOM_OU_ID_DE_LA_TACHE]
 * @CONSTITUTION-HASH: [HASH_LU_DEPUIS_.SPEC-LOCK]
 * @STATUS: VALIDATED
 */
```

---
*Ce document peut être amendé par l'humain. Toute modification du texte ci-dessus nécessitera une ré-exécution de l'utilitaire de verrouillage (`spec.py lock`) pour mettre à jour le `.spec-lock.json`.*
