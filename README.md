# 🛡️ Speckit.Factory: Framework Constitutional DevOps 

**Créé:** 2026
**Status:** ✅ Prêt à l'emploi
**Licence:** ⚠️ Propriétaire (Tous droits réservés)
**Communauté:** [Rejoindre le Discord](https://discord.gg/votre-lien)

---

### ✨ Système Automatisé Complet

**Speckit.Factory** est un framework **Constitutional DevOps AI** conçu pour gérer le cycle de vie complet de votre développement, de l'architecture aux tâches techniques, tout en garantissant le respect de vos principes fondamentaux (Constitution).

---

### 🎨 La Spécialité Speckit.Factory : Design & Monitoring

L'une des grandes forces de Speckit.Factory réside dans son architecture multi-agents :
1. **Agent Designer (GraphicDesign)** : En amont de l'implémentation, un agent spécialisé transforme votre intention UI en spécifications visuelles "Premium" (systèmes Standard ou premium).
2. **Monitoring & Audit** : Le framework ne se contente pas de générer du code ; il monitore en temps réel l'exécution du LLM, s'assurant que chaque ligne produite respecte scrupuleusement votre Constitution et vos standards de qualité.

---

**Voici comment ça marche:**

```text
1⃣️  Vous initialisez le projet
     → speckit init
        ↓
2⃣️  SPECKIT configure l'arborescence et votre Constitution
     (Vous définissez vos principes dans Constitution/CONSTITUTION.md)
        ↓
3⃣️  Vous organisez vos Tâches / Spécifications (App, Function, Tech)
        ↓
4⃣️  SPECKIT Exécute une tâche sous verrouillage strict
     → speckit run --task ID
        ↓
5⃣️  L'IA valide que la Constitution est respectée avant toute action!
```

---

## 🚀 Les Commandes du Workflow

L'interface en ligne de commande professionnelle vous simplifie la vie :

```bash
# Étape 1 : Initialiser le projet dans un nouveau dossier
speckit init MonProjet

# Optionnel : Initialiser directement dans le dossier courant
speckit init --here

# Étape 2 : Lancer une tâche sous verrouillage contextuel
speckit run --task 03_02

# CAS PROJET EXISTANT : Ajouter une fonctionnalité (Composante)
speckit component "Ajouter un module de chat"
speckit run --component 04_chat
```

---

## 📁 Structure Créée

```text
📁 Votre-Projet/
├── 📜 .spec-lock.json       ← Verrou d'intégrité de votre projet
├── 🏛️ Constitution/
│   ├── CONSTITUTION.md      ← VOS PRINCIPES FONDAMENTAUX
│   └── etapes.md            ← Suivi des étapes
```

---

## 📋 Prérequis Obligatoires

Avant de pouvoir utiliser Speckit.Factory, assurez-vous que votre machine possède:

### 1️⃣ Python 3.12 (Minimum)
Speckit.Factory nécessite **Python 3.12 ou supérieur** pour fonctionner correctement.

Vérifiez votre version:
```bash
python --version
```

Si vous n'avez pas Python 3.12, téléchargez-le depuis [python.org](https://www.python.org/downloads/).

### 2️⃣ Installer `uv` (Gestionnaire de Paquets Python)
`uv` est un gestionnaire de paquets ultra-rapide requuis pour exécuter les commandes `speckit`.

Installez-le avec:
```bash
pip install uv
```

> **⚠️ Important:** Sans `uv` installé, les commandes `speckit` ne marcheront pas et vous obtiendrez une erreur: `uvx: The term 'uvx' is not recognized...`

---

## ⚡ Démarrage Ultra Rapide (5 Minutes)

### Étape 1: Initialiser le projet
```bash
# Dans votre terminal
speckit init --here
```

**BOUM!** SPECKIT génère automatiquement l'arborescence sécurisée.

### Étape 2: Personnaliser Votre Constitution
```bash
code Constitution/CONSTITUTION.md
```
Remplacez le contenu par **VOS VRAIS PRINCIPES**.
*Exemple: "Principe 1: Tout le code doit être typé."*

### Étape 3: Lancer l'exécution
```bash
speckit run --task 01_01
```
L'agent d'exécution charge un contexte **strictement verrouillé** (Constitution + Etape + Architecture) pour s'assurer d'aligner le travail avec vos règles absolues.

---

## 🏃‍♂️ Démarrer votre application générée

Une fois que Speckit a généré votre code (par exemple, le backend), vous voudrez sûrement le lancer localement pour le tester. 

**Important :** Speckit vérifie la robustesse du code, mais c'est à vous de lancer le serveur de développement.

1. **Placez-vous dans le dossier généré** :
```bash
cd backend/  # ou cd frontend/
```

2. **Installez les dépendances** :
Même si Speckit les gère en interne, votre environnement local en a besoin (surtout si vous clonez le projet ou venez de le créer) :
```bash
npm install
```

3. **Démarrez le serveur de développement** :
Vous n'avez pas besoin de compiler le TypeScript à la main, un script est prévu pour ça :
```bash
npm start
# ou npm run dev
```

---

## ⚡ Optimisation : Cache Intelligent des Dépendances

Speckit.Factory intègre un **système de cache basé sur hash** pour accélérer drastiquement les exécutions successives.

### Comment ça marche :

Chaque dossier (`backend/`, `frontend/`, racine) contient un fichier `.speckit_hash` qui stocke le hash MD5 de son `package.json`. 

À chaque exécution :
- ✅ Si le hash du `package.json` **n'a pas changé**, `npm install` est **skippé** (gain 5-10x plus rapide)
- 🔄 Si le hash **a changé**, `npm install` s'exécute et le cache est mis à jour

```bash
# Première exécution (npm install normal)
⏳ npm install (30-60s)

# Deuxième exécution (même package.json)
⚡ CACHE HIT pour backend (hash identique). Skip npm install
✨ Quasiment instantané!
```

### Fichiers `.speckit_hash` :
```text
backend/.speckit_hash     # Tracking des changements de dépendances backend
frontend/.speckit_hash    # Tracking des changements de dépendances frontend
.speckit_hash             # Tracking des changements à la racine
```

**💡 Conseil :** Ne mettez **PAS** ces fichiers dans `.gitignore` ! Ils vous permettent de tracker **quand vos dépendances ont réellement été modifiées** et constituent un audit trail utile pour votre équipe.

---

## 🎯 Architecture Multi-Module Intelligente

Speckit.Factory détecte automatiquement **quel module** votre tâche cible (`backend`, `frontend`, `mobile`, etc.) et adapte l'exécution en conséquence.

### Comment ça fonctionne :

Quand vous exécutez une tâche comme `03_setup_frontend`, le framework:

1. **Identifie le module cible** : Parse le task ID pour extraire `frontend`
2. **Limite les installations** : `npm install` s'exécute **uniquement dans `frontend/`**, pas dans `backend/`
3. **Diagnostique le bon outil** :
   - Frontend avec Vite ? → Exécute `npm run build` (Vite)
   - Backend avec TypeScript ? → Exécute `tsc --noEmit` (TypeScript)
4. **Évite les faux positifs** : Plus de "TypeError TypeScript non installé en backend" quand vous travaillez sur le frontend

### Le Gain pour Vous :

```bash
# AVANT (bug classique)
speckit run --task 03_setup_frontend
❌ Vérifie le backend au lieu du frontend
❌ Lance npm install backend (inutile)
❌ Erreur : "TypeScript non installé" dans le mauvais module
❌ Boucle infinie

# APRÈS (architecture intelligente)
speckit run --task 03_setup_frontend
✅ Détecte que c'est du frontend
✅ npm install frontend uniquement
✅ Lance vite build (pas tsc)
✅ Succès en quelques secondes
```

### Scalabilité :

Grâce à cette approche modulaire, Speckit.Factory peut maintenant gérer des projets complexes avec:
- ✅ **Backend** + **Frontend** (configuration classique)
- ✅ **Backend** + **Frontend** + **Mobile** (Monorepo multistacks)
- ✅ **Microservices** (API Gateway + Services)
- ✅ **Infrastructure as Code** (Terraform, Docker)

Chaque module a sa Constitution, ses dépendances, et son cycle de vie propre, **complètement isolé**.

### ⚙️ Gestion Intelligente des Dépendances Cross-Module

Qu'est-ce qui se passe si votre **frontend dépend du backend** (cas monorepo classique)?

**Speckit gère cette situation automatiquement** :

- ✅ Continue l'installation du **module cible** (frontend/) normalement
- 🔄 **Détecte** la dépendance manquante via `package.json`
- 📌 **Ajoute automatiquement** une tâche à `Constitution/etapes.md` (étape backend)
- 📣 **Informe l'utilisateur** du bon ordre à suivre

**Résultat**: Ordre des dépendances respecté + roadmap toujours à jour.

### 🔎 Détection Proactive des Imports Manquants (Dependency Resolver)

**Nouveau:** Speckit.Factory intègre un **nœud `dependency_resolver`** qui scanne vos fichiers source AVANT la compilation TypeScript.

**Ce qu'il fait :**
1. **Parse tous les imports** (`import { x } from 'zod'`, `require('express')`, etc.)
2. **Vérifie** si les modules sont dans `package.json`
3. **Détecte les manquants** avant que TypeScript ne plante
4. **Installe directement** via `npm install zod` (sans bloquer sur le cache)

**Avantage :**
- ✅ Zéro erreur `"Cannot find module 'zod'"` (détecté + installé proactivement)
- ✅ Pas de boucles infinies sur dépendances manquantes
- ✅ Build réussit dès le premier essai

**Pipeline optimisé :**
```
Analysis → Design → Implementation → Persist
  ↓
Dependency Resolver (détecte zod, express, etc.)
  ↓
npm install (modules détectés + modules TSC manquants)
  ↓
Diagnostics (build réussit → no more errors)
```

---

## 🛠️ Travailler sur un Projet Existant (Mode Composante)

Si vous utilisez Speckit sur un projet qui contient déjà du code, suivez ce workflow pour ne pas écraser votre travail :

1. **Initialisez (si ce n'est pas fait)** : `speckit init --here`
   *   Speckit détectera automatiquement si votre dossier n'est pas vide et vous guidera.
2. **Ajoutez une fonctionnalité** : `speckit component "Ma demande"`
   *   Speckit scanne votre code existant (**Semantic Code Map**).
   *   Il amende la `CONSTITUTION.md` sans l'écraser.
   *   Il génère une **feuille de route intelligente** : il analyse ce qui est déjà codé et marque ces étapes comme faites `[x]`, puis ajoute les nouvelles étapes nécessaires (en plusieurs étapes si la demande est complexe).
3. **Exécutez** : `speckit run --component ID`

> [!TIP]
> Si vous utilisez `speckit plan` sur un projet existant, il sera également "intelligent" et ne vous proposera que les étapes réellement manquantes.

---

## 🔒 La Force de la "Constitution"

Imaginez que votre `CONSTITUTION.md` dicte :
```markdown
## Sécurité
Aucun mot de passe en texte clair ne doit passer par l'API.
```

Avant toute exécution de `--task`, le **SpecValidator** vérifie l'intégrité et garantit que l'IA ne génèrera jamais de code ou de plan d'action qui viole ce principe inviolable.
**Résultat:** Code robuste dès le premier essai, aligné à vos standards. Zéro régression.

---

## 🤖 Architecture Multi-IA Simultanée

Contrairement à d'autres Spec-Kit souvent limités à une seule instance ou un seul modèle à la fois, **Speckit.Factory permet une collaboration SIMULTANÉE entre plusieurs IA**.

Parce que le framework repose sur un système de fichiers strict et un verrou d'intégrité, vous pouvez ouvrir votre projet dans **3 IA différentes au même moment** (ex: Gemini, Claude et Codex) sans conflit :

*   **Synchronisation par le Fichier** : Toutes les IA lisent la même `CONSTITUTION.md`. Si vous modifiez un principe dans une IA, les autres en héritent immédiatement dès la prochaine lecture.

*   **Division du Travail en Parallèle** : Vous pouvez utiliser différentes IA pour des tâches distinctes, le tout synchronisé par le `.spec-lock.json`.

*   **Intelligence Collective** : Utilisez la force de chaque modèle selon la tâche :
    *   **Gemini** pour l'analyse de code massive.
    *   **Claude** pour la rédaction de spécifications précises.
    *   **Codex / Copilot** pour l'écriture de code rapide.

**Speckit.Factory n'est pas un outil pour UNE IA, c'est un protocole pour TOUTES vos IA travaillant ensemble.**

---

## 🎓 Ce Que Vous Allez Apprendre

Après avoir utilisé Speckit.Factory :

✅ Comment structurer hermétiquement le cycle de vie d'une App (Architecture → Specs → Tech)
✅ Comment imposer des règles d'IA strictes grâce au pattern "Constitutional"
✅ Comment verrouiller le contexte de Prompting pour éviter les hallucinations
✅ Comment orchestrer **simultanément** plusieurs IA (Multi-Agent Sync) sans perdre la trace du projet

---

## 🔒 Confidentialité & Propriété Intellectuelle

**IMPORTANT :** Bien que ce dépôt soit public pour faciliter l'utilisation via `uv` ou `pip`, **Speckit.Factory n'est pas un projet Open Source.** 

- ⚖️ **Propriété :** Tous les droits sont réservés à **Didier KAZITALA**.
- 🚫 **Copie :** Le clonage, la redistribution ou la modification non autorisée du code source à des fins de création de dérivés sont interdits.
- 🤝 **Contributions :** Si vous souhaitez contribuer au projet ou suggérer des fonctionnalités, ne faites pas de Pull Request. Le développement est centralisé.

## 👥 Communauté & Collaboration

Pour bâtir une communauté forte autour de **Speckit.Factory**, rejoignez-nous sur Discord !

👉 **[Rejoindre le serveur Discord Speckit](https://discord.gg/votre-lien)**

C'est ici que nous discutons des évolutions, de la roadmap et que vous pouvez proposer votre aide pour faire grandir cet écosystème.

---

## 🔧 Dépannage : Corriger une Étape Incomplète

Si une étape a été marquée comme terminée (`[x]`) alors que certaines sous-tâches n'ont pas été réalisées, vous pouvez la **réinitialiser manuellement** pour la relancer.

### Étape 1 : Décocher l'étape dans `etapes.md`

Ouvrez `Constitution/etapes.md` dans votre projet et modifiez le header de l'étape concernée :

```diff
-## [x] 01_backend_setup : Configuration initiale du backend
+## [ ] 01_backend_setup : Configuration initiale du backend
```

Décochez également les sous-tâches manquantes :

```diff
-- [x] Créer un fichier `backend/.env` de base
+- [ ] Créer un fichier `backend/.env` de base
-- [x] Créer un fichier `backend/.gitignore`
+- [ ] Créer un fichier `backend/.gitignore`
```

> [!TIP]
> Vous pouvez laisser les sous-tâches déjà réalisées cochées `[x]`. Seules les `[ ]` seront traitées au prochain lancement.

### Étape 2 : Retirer la tâche du verrou

Ouvrez `.spec-lock.json` à la racine du projet et retirez l'ID de la tâche de la liste `completed_tasks` :

```diff
  "completed_tasks": [
-     "01_backend_setup"
  ]
```

### Étape 3 : Relancer la tâche

```bash
speckit run --task 01_backend_setup
```

L'IA reprendra le travail sur les sous-tâches non-cochées et l'Auditeur vérifiera que **chaque livrable** est bien présent avant d'approuver.

---

## 🌐 Providers IA Supportés

Speckit.Factory fonctionne avec une variété de providers IA pour s'adapter à votre contexte géographique, vos préférences et vos besoins :

| Provider | API directe | Contourne géoblocage | Modèles |
|----------|:---:|:---:|---|
| **Google** (Gemini) | ✅ | ❌ | Gemini 2.5 Flash, Pro, etc. |
| **OpenAI** (GPT) | ✅ | ❌ | GPT-4o, GPT-4 Turbo, etc. |
| **Anthropic** (Claude) | ✅ | ❌ | Claude 3.5 Sonnet, Opus, etc. |
| **DeepSeek** | ✅ | ❌ | DeepSeek V3, Coder, etc. |
| **Grok** (xAI) | ✅ | ❌ | Grok-3, Grok-2, etc. |
| **OpenRouter** | Passerelle | ✅ | 100+ modèles (accès universel) |

### 💡 Quand Utiliser Quoi ?

- **API directe** : Utiliser si vous avez accès à ces services dans votre région.
- **OpenRouter (passerelle)** : Idéal pour contourner les blocages géographiques ou tester rapidement plusieurs modèles avec une seule clé.

---

## ⚙️ Configuration des Clés API

Pour que Speckit.Factory puisse communiquer avec les IA, vous devez configurer vos clés API :

1.  **Récupérez le template** : Copiez le fichier `.env.example` à la racine de votre projet vers un nouveau fichier nommé `.env`.
    ```bash
    cp .env.example .env
    ```
2.  **Remplissez vos clés** : Ouvrez le fichier `.env` et insérez vos clés (Google, Anthropic, OpenAI, DeepSeek, Grok ou OpenRouter).
    ```text
    GOOGLE_API_KEY=votre_cle_ici
    ```

> [!IMPORTANT]
> Ne commitez **JAMAIS** votre fichier `.env` sur Git. Il est déjà ajouté au `.gitignore` par défaut pour protéger vos secrets.

---

## 🛠️ Installation & Utilisation

### Méthode 1 : Utilisation directe (Recommandée - via ⚡ [uv](https://astral.sh/uv/))
Pas besoin de cloner le repo, exécutez simplement :
```bash
uvx --from git+https://github.com/didierarchangel/Speckit.Factory.git speckit init --here
```

#### ⚡ Raccourci Pro (PowerShell)
Pour ne plus taper toute l'URL, ajoutez cet alias à votre session (ou votre profil `$PROFILE`) :
```powershell
function speckit { uvx --from git+https://github.com/didierarchangel/Speckit.Factory.git speckit @args }
```
Désormais, utilisez simplement : `speckit specify "votre demande"`

### Méthode 2 : Installation via Git (Pour les utilisateurs)
```bash
pip install git+https://github.com/didierarchangel/Speckit.Factory.git
```

### Méthode 3 : Développement Local (Si vous avez cloné le repo)
Pour utiliser `speckit` tout en modifiant le code source :
```bash
# Dans le dossier Speckit.Factory
pip install -e .
```

---

*Speckit.Factory : Constitutional DevOps AI Framework.*
