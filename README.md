# 🛡️ Speckit.Factory: Framework Constitutional DevOps 

**Créé:** 2026
**Status:** ✅ Prêt à l'emploi
**Licence:** ⚠️ Propriétaire (Tous droits réservés)
**Communauté:** [Rejoindre le Discord](https://discord.gg/votre-lien)

---

### ✨ Système Automatisé Complet

**Speckit.Factory** est un framework **Constitutional DevOps AI** conçu pour gérer le cycle de vie complet de votre développement, de l'architecture aux tâches techniques, tout en garantissant le respect de vos principes fondamentaux (Constitution).

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
```

---

## 📁 Structure Créée

```text
📁 Votre-Projet/
├── 📜 .spec-lock.json       ← Verrou d'intégrité de votre projet
├── 🏛️ Constitution/
│   ├── CONSTITUTION.md      ← VOS PRINCIPES FONDAMENTAUX
│   └── etapes.md            ← Suivi des étapes
├── 🏗️ Task_App1/            ← Architecture (Tâches non réalisées)
├── 🏗️ Task_App2/            ← Architecture (Tâches réalisées)
├── 📝 Task_Function1/       ← Spécifications (Non réalisées)
├── 📝 Task_Function2/       ← Spécifications (Réalisées)
├── 🛠️ Task1/                ← Tâches Techniques (Non réalisées)
└── 🛠️ Task2/                ← Tâches Techniques (Réalisées)
```

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

*   **Division du Travail en Parallèle** : Vous pouvez demander à **Claude** de travailler sur une spécification dans `Task_Function1` pendant que **Gemini** implémente une tâche technique dans `Task1`

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

## ⚙️ Configuration des Clés API

Pour que Speckit.Factory puisse communiquer avec les IA, vous devez configurer vos clés API :

1.  **Récupérez le template** : Copiez le fichier `.env.example` à la racine de votre projet vers un nouveau fichier nommé `.env`.
    ```bash
    cp .env.example .env
    ```
2.  **Remplissez vos clés** : Ouvrez le fichier `.env` et insérez vos clés (Google, Anthropic ou OpenAI).
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
