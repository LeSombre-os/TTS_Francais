# TTS Français local

Synthèse vocale française réaliste, 100 % locale (aucun cloud, rien ne quitte la machine). Interface web simple : tu colles du texte, tu écoutes, tu télécharges. Moteur **Chatterbox** (finetune français 1400 h) + clonage de voix en bonus.

## Fonctionnalités

- **Voix française naturelle** : modèle `Thomcles/Chatterbox-TTS-French` par défaut, repli multilingue sélectionnable
- **Voix fixes** : dépose des `*.wav` dans `voices/` → ils apparaissent dans la liste
- **Clonage** : upload d'une référence vocale (5-10 s de voix claire) pour parler avec cette voix
- **Réglages** : expressivité, stabilité (CFG), variabilité + vitesse de lecture côté client
- **Textes longs** : découpage auto par phrases, audio concaténé (max 2000 caractères / requête)
- **Historique** de session + téléchargement WAV 24 kHz

## Prérequis

- Python 3.10+
- ~5 Go libres (modèles en cache dans `~/.cache/huggingface`, venvs dans `~/.venvs/`)
- CPU seul : ça marche. GPU AMD (ROCm) : ~10× plus rapide si dispo, sinon repli auto sur CPU

## Installation

```bash
python3 -m venv ~/.venvs/tts
~/.venvs/tts/bin/pip install -r requirements-cpu.txt
~/.venvs/tts/bin/pip install --no-deps -r requirements.txt
```

> `--no-deps` évite que pip remplace torch CPU par le build CUDA. Astuce : les venvs sont hors du dossier projet car la clé USB (FAT) ne supporte pas leurs liens symboliques.

### GPU AMD (optionnel, ~10× plus rapide)

```bash
python3 -m venv ~/.venvs/tts-rocm
~/.venvs/tts-rocm/bin/pip install -r requirements-rocm.txt
~/.venvs/tts-rocm/bin/pip install --no-deps -r requirements.txt
```

> `device-gfx1032` = RX 6600/6600 XT. Autre carte : remplace par ton arch (`device-gfx1030`, `device-gfx1100`…). Sans ce venv, tout marche en CPU.

## Lancement

### Double-clic (comme une app)

**`TTS-Francais.desktop`** : double-clic → terminal visible + navigateur auto. **Premier usage : clic droit → *Autoriser le lancement*** (sinon GNOME l'ouvre en éditeur de texte). Un 2ᵉ double-clic réutilise le serveur déjà lancé au lieu d'en créer un autre.

Pour l'avoir dans le menu / sur le bureau : copie le `.desktop` dans `~/.local/share/applications/` (menu) ou `~/Bureau`, puis à nouveau clic droit → *Autoriser le lancement* sur la copie. Le nom du fichier est volontairement sans espaces ni accents (exigé par le format `.desktop`).

### Avec terminal

```bash
./lancer.sh          # auto : GPU si dispo, sinon CPU (http://127.0.0.1:8901)
./lancer.sh --gpu    # force GPU (erreur si pas de CG)
./lancer.sh --cpu    # force CPU
./lancer.sh stop     # arrête le serveur
```

## Usage

1. Colle ton texte en français (liaisons, accents et ponctuation pris en charge).
2. Choisis le modèle (**Français premium** recommandé), une voix fixe ou un fichier de clonage.
3. Ajuste expressivité / stabilité si besoin → **Générer** → écoute → ⬇ télécharge.

Temps constatés (90 caractères → ~4 s d'audio) : CPU Ryzen 5 5600G ~90 s au 1er chargement ; **GPU RX 6600 ~9 s à chaud** (44 s au tout 1er chargement : poids + kernels).

## Structure

```
TTS/
├── app.py                 # serveur FastAPI (modèles lazy, chunking phrases)
├── index.html             # UI (vanilla, sans build)
├── voices/                # presets *.wav perso (vide par défaut)
├── lancer.sh              # lancement 1-clic : auto (GPU si dispo sinon CPU), --cpu, --gpu, stop
├── TTS-Francais.desktop   # lanceur Linux portable (clic droit → Autoriser le lancement)
├── requirements.txt       # deps app (torch exclu, --no-deps) + requirements-cpu.txt / requirements-rocm.txt
└── LICENSE                # MIT
```

## En cas de problème

- **Port occupé** → relance simplement : le 2ᵉ lancement détecte le serveur existant et ouvre juste le navigateur.
- **Double-clic qui ouvre un éditeur** → le `.desktop` n'est pas autorisé : clic droit → *Autoriser le lancement*. Sur clé USB (FAT), préfère la copie dans `~/.local/share/applications/`.
- **1er lancement lent** → normal : téléchargement des modèles (~2 Go) puis chargement (~1 min). Les suivants sont directs.
- **`Venv introuvable`** → refais l'étape Installation (venv CPU attendu dans `~/.venvs/tts`).
- **Lent malgré la CG** → vérifie `/api/status` : `"device":"cuda"` = GPU actif. Sinon le lanceur a replié sur CPU (GPU invisible → `HIP_VISIBLE_DEVICES` vide ? driver ?). Force le diagnostic : `./lancer.sh --gpu`.
- **Voix anglaise / accent bizarre** → vérifie que le modèle **Français premium** est sélectionné (pas Multilingue), et pour le clonage utilise une référence française claire de 5-10 s.
- **Erreur HF (rate limit)** → les téléchargements anonymes sont limités ; réessaie 1 min après.
- **Sorties tatouées** → watermark inaudible PerTh imposé par Resemble AI, c'est normal.

## Notes

Serveur sur `127.0.0.1` uniquement : garde-le en local, ne l'expose pas. Modèle de base sous licence MIT, données du finetune FR sous CC-BY-4.0.
