# Agent Researcher — migration vers une instance OpenClaw

Ce dépôt est le **workspace** de l'agent `researcher` : instructions, persona, pipeline de
veille scientifique (`projects/decentralized-ai-governance/`) et skill `arxiv-reader`.
Il ne contient **ni l'état du gateway, ni les secrets, ni l'automatisation** : ils se
recréent sur la nouvelle instance en suivant ce document.

Référence : OpenClaw `2026.11.5` (docs : `install/migrating`, `cli/cron`, `cli/agents`,
`automation/cron-jobs/*`, `channels/slack/*`). Les commandes ci-dessous ont été relevées
dans l'aide du CLI de cette version ; en cas de doute : `openclaw <commande> --help`.

## 1. Ce qui est (et n'est pas) dans le dépôt

| Dans le dépôt | Hors dépôt : à recréer sur la cible |
|---|---|
| `AGENTS.md`, `SOUL.md`, `IDENTITY.md` | Entrée d'agent `researcher` dans `openclaw.json` |
| `projects/decentralized-ai-governance/` : scope, workflow, scripts, `weekly-config.json` | Authentification du fournisseur de modèle |
| `skills/arxiv-reader/` | Canal Slack (tokens) et binding de l'agent |
| | **Le job d'automatisation** (stocké dans la base SQLite du gateway, pas dans les fichiers) |
| | `.venv/` Python |

Volontairement **non versionnés** (voir `.gitignore`) : `runs/`, `corpus/`, `archive/`,
`digests/` (état de la veille : la veille repart de zéro), `memory/` et `DREAMS.md` (sorties de
Dreaming, contiennent des extraits de conversations), `USER.md` (profil personnel),
`research-repos/` (clones tiers), toute base `*.sqlite*`, tout `.env`/token.
Les sessions de l'ancien agent ne sont pas migrées : le job de veille tourne en session
`isolated` et ne dépend d'aucune conversation passée.

## 2. Prérequis sur la cible

- OpenClaw installé, idéalement **la même version** (`openclaw --version`), Gateway démarré
  et **en fonctionnement continu** (sinon aucun job ne se déclenche) : `openclaw status`.
- `git`, `python3` (avec `venv`) et **Node ≥ 22.6** (le lecteur arXiv utilise le « type
  stripping » de Node). Si l'étape source du lecteur échoue (ex. `bad option:
  --experimental-strip-types`), `read_paper.py` bascule sur l'extraction PDF : la lecture
  reste possible, mais vérifiez `node --version`.
- Un accès réseau sortant vers arXiv et OpenAlex.

## 3. Récupérer le workspace

```bash
git clone https://github.com/iExecBlockchainComputing/openclaw-researcher.git \
  ~/.openclaw/workspace-researcher
cd ~/.openclaw/workspace-researcher/projects/decentralized-ai-governance
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-reader.txt
mkdir -p corpus runs digests && touch corpus/references.jsonl   # état vide (reset accepté)
```

`weekly.py` lit `corpus/references.jsonl` sans vérifier son existence : d'où le `touch`.
Le chemin du workspace est libre ; remplacez `<WORKSPACE>` plus bas par le chemin absolu choisi.

## 4. Créer l'agent

```bash
openclaw agents add researcher --workspace <WORKSPACE> --non-interactive
openclaw agents set-identity --workspace <WORKSPACE> --from-identity   # nom/emoji/thème depuis IDENTITY.md
openclaw agents list --bindings
```

Les options `--bind`, `--agent-dir` et le mode interactif exigent que le Gateway local soit
arrêté (doc `cli/agents`). Sur l'instance d'origine, `subagents.allowAgents` était `[]`
(pas de délégation) : à reproduire dans la config si besoin (`AGENTS.md` interdit déjà la
délégation).

## 5. Modèle et authentification

Le job d'origine n'avait **aucun modèle explicite** : il suivait `agents.defaults.model`
(`openai/gpt-6.1-sol` sur l'ancienne instance). Sur la cible, ce défaut peut différer.
**Fixez toujours le modèle du job explicitement** (voir §7) et authentifiez le fournisseur
correspondant (`openclaw configure` ou `openclaw onboard`). Notez l'identifiant du profil
créé (`auth.profiles` dans `openclaw.json`, de la forme `<provider>:<profileId>`).

## 6. Canal Slack

1. Configurez le compte Slack **`default`** (Socket Mode par défaut : `appToken` + `botToken`,
   cf. `channels/slack/setup`). Fournissez les tokens par variables d'environnement du
   service Gateway ou par références de secrets (`{ source: "env", ... }`) ; **jamais** dans
   le dépôt, ni dans un message.
2. Invitez le bot dans le canal de destination (`C0CFAVAV91N`, cf. `weekly-config.json`).
3. Liez l'agent au canal Slack, puis vérifiez :
   ```bash
   openclaw agents bind --agent researcher --bind 'slack:*'
   openclaw agents list --bindings
   ```
4. **Une seule instance par application Slack** : en Socket Mode, il y a « une session par
   app et par hôte ; plusieurs Gateways nécessitent des apps Slack distinctes »
   (`channels/slack/transports`). Avant la bascule, soit désactivez Slack sur l'ancien
   Gateway, soit utilisez une autre app Slack pour la cible.

## 7. Activer l'automatisation correctement

Le job est la seule pièce qui ne se « clone » pas. Principe : **le recréer sur la cible
(ne pas copier celui de l'ancienne instance), le valider sans livraison, puis seulement
activer la livraison Slack**.

### 7.1 Pourquoi ne pas reprendre l'ancien job tel quel

Un job `agentTurn` isolé conserve en privé le **compte d'inférence** choisi à sa création
(`automation/cron-jobs/payloads`, « Inference account continuity »). L'erreur
`Automation candidate is incompatible with its recorded inference account and route`
signifie que le modèle sélectionné utilise un autre fournisseur, ou que son runtime utilise
une connexion CLI qui ne peut pas remplacer le compte enregistré (`troubleshooting`).
`doctor --fix` ne répare pas ce cas. Sur la cible : **passez un modèle explicite avec son
profil** (`--model <provider/model>@<profileId>`) et ne mélangez pas un compte stocké avec un
runtime CLI natif.

### 7.2 Créer le job — désactivé et sans livraison

Le prompt est celui du job d'origine ; seul le chemin du workspace est paramétré.
`archive/reset-20261117/` cité dedans n'existe pas sur la cible (non versionné) : sans effet.

```bash
openclaw automations create "0 9 * * 1" "$(cat <<'EOF'
Run the authorized weekly scientific monitoring. Workspace <WORKSPACE>. Read projects/decentralized-ai-governance/RESEARCH_SCOPE.md, WORKFLOW.md, WEEKLY.md and weekly-config.json, including the final 'Editorial rules' section, which takes precedence. The corpus was reset on 2026-11-17 (previous material archived in archive/reset-20261117/, which must not be used to decide novelty): the registry starts empty and the first run collects the initial 30-day window. Collect and screen, perform up to 10 new critical readings, select up to 5 relevant evidence-supported papers. Exclude only papers already read in the current registry or already in a digest from a run recorded as delivered. Preserve traceability internally; never equate extraction with reading. Public final answer: a readable, human French message that opens with a short greeting (e.g. 'Bonjour à tous,') and one sentence introducing the selection, then numbered paper notices (title + link, what it studies, contribution/result, principal limitation), then a brief friendly closing line. No internal counters, test history, process or queue/status commentary. Follow scheduler announce delivery contract: save and validate the digest, return the full digest as final; do not message send. Check the previous run's delivery status to avoid duplicates. No delegation. On failures report honestly.
EOF
)" \
  --name "Veille scientifique — gouvernance IA décentralisée" \
  --agent researcher \
  --session isolated \
  --tz Europe/Paris \
  --model <provider/model>@<profileId> \
  --timeout-seconds 7200 \
  --disabled --no-deliver
```

Remplacez `<WORKSPACE>` (chemin absolu, **dans le texte du prompt** aussi) et le modèle.
Notez l'`id` renvoyé (`<JOB_ID>`).

### 7.3 Vérifier le job enregistré

```bash
openclaw automations show <JOB_ID>
```

À contrôler : agent `researcher`, session `isolated`, cron `0 9 * * 1` en `Europe/Paris`,
timeout 7200 s, modèle et compte d'inférence attendus, livraison **désactivée** pour
l'instant. Le job d'origine avait `toolsAllow: ["*"]` : vérifiez que les outils du pipeline
(lecture/écriture de fichiers, exec, accès web) sont bien autorisés pour l'agent, sinon
précisez `--tools` (`openclaw automations edit <JOB_ID> --tools ...`).

### 7.4 Run d'essai (sans Slack)

```bash
openclaw automations run <JOB_ID> --wait --wait-timeout 2h
openclaw automations runs <JOB_ID> --limit 5
```

Un run manuel d'un job désactivé ne l'active pas et n'en programme aucun autre. Ce premier
run collecte la fenêtre initiale de 30 jours, fait jusqu'à 10 lectures critiques et consomme
des tokens : prévoyez du temps et du budget. Contrôles : statut `ok`, un `digests/<date>-*.md`
produit, `runs/weekly-*/run.json` et `validation.json` cohérents, aucune erreur d'outil dans
`openclaw automations show <JOB_ID>` (rubrique `diagnostic:`).

### 7.5 Remise à zéro avant la mise en production

Règle éditoriale : seuls sont exclus les papiers **déjà lus dans le registre** ou présents
dans un digest **livré**. Les papiers lus pendant le run d'essai seraient donc exclus des
digests futurs sans jamais avoir été publiés. Après un essai concluant, repartez d'un état vide :

```bash
cd <WORKSPACE>/projects/decentralized-ai-governance
rm -rf runs corpus digests && mkdir -p runs corpus digests && touch corpus/references.jsonl
```

(Si vous sautez l'essai, cette étape est inutile.)

### 7.6 Activer la livraison Slack et le planning

```bash
openclaw automations edit <JOB_ID> --announce --channel slack \
  --to channel:C0CFAVAV91N --account default --enable
openclaw automations show <JOB_ID>
openclaw automations list --agent researcher
```

`show` doit afficher une livraison `announce -> slack:C0CFAVAV91N` et `list` un prochain run
le lundi à 09:00 (Europe/Paris). Mode `announce` : le scheduler publie lui-même le texte
final, l'agent **ne doit pas** appeler `message send` (contrat de `WEEKLY.md`) ; le run
suivant vérifie le statut de livraison du run précédent via `automations runs`.

### 7.7 Mettre à jour la référence du job

`weekly-config.json` contient un `automation_id` (celui d'un ancien job). Remplacez-le par
`<JOB_ID>`, puis commitez.

### 7.8 Éviter les doublons

Deux jobs de veille actifs (ancien et nouveau) publieraient deux fois sur Slack. Sur
**l'ancienne instance**, désactivez le sien : `openclaw automations disable <ancien_id>`
(ne supprimez rien avant d'avoir validé la cible).

### 7.9 Dépannage

| Symptôme | Piste |
|---|---|
| `incompatible with its recorded inference account and route` | Voir §7.1 : `openclaw automations edit <JOB_ID> --model <provider/model>@<profileId>` |
| `Automation has no recorded inference account` | `openclaw doctor --fix`, ou même `edit --model ...@<profileId>` |
| Rien ne se déclenche | Gateway arrêté ? Job désactivé (`automations list --all`) ? Fuseau (`--tz`) ? |
| Exécuté mais rien dans Slack | Bot non invité dans le canal, mauvais `--account`/`--to`, ou mode livraison ≠ `announce` : `automations show` |
| Échec de lecture arXiv | `node --version` (≥ 22.6), `.venv` présent, accès réseau |

## 8. Checklist finale

- [ ] `openclaw status` : Gateway actif ; `openclaw agents list --bindings` : `researcher` lié à Slack
- [ ] `.venv` créé, `corpus/references.jsonl` présent (vide après remise à zéro)
- [ ] Job recréé avec modèle explicite ; `automations show` cohérent
- [ ] Run d'essai `ok`, puis remise à zéro (§7.5)
- [ ] Livraison `announce -> slack:C0CFAVAV91N` activée, job `--enable`
- [ ] `automation_id` mis à jour dans `weekly-config.json`
- [ ] Ancien job désactivé (et Slack coupé côté ancien Gateway)
- [ ] Premier digest du lundi reçu dans le canal ; statut de livraison confirmé dans `automations runs`

## 9. Notes

- Rien d'exécuté ici ne supprime l'ancienne instance : la retirer est une décision
  distincte, à prendre après validation.
- Si le dépôt est partagé : ne jamais y committer tokens, `*.sqlite*`, `memory/`, `USER.md`
  rempli ou archives de backup (elles contiennent les secrets d'auth).
