# sql-serveur

Cours SQL Server publié en page unique sur GitHub Pages.

## Ton et rédaction

L'auteur est francophone. Vouvoiement, ton neutre, pas d'emoji, **jamais de
tiret long**. Le cours lui-même est en français, sobre, et explique les
mécanismes avant les recettes : une notion se tient par la chaîne de causalité
qui la relie à une mesure, pas par une liste de bonnes pratiques.

## Une seule source

`docs/index.html` **est** le cours : 23 modules en quatre phases, un programme
de 60 séances sur 12 semaines, 2,2 Mo. Il n'y a ni Markdown, ni étape de build,
ni dépendance à installer.

Une édition précédente existait, 15 épisodes générés depuis un fichier Markdown
par `build.py`. Elle a été retirée le 20 octobre 2026 : ses scripts T-SQL
avaient été corrigés dans la page sans l'être dans le Markdown, et le script
écrasait la page s'il était relancé. L'historique la conserve au commit
`5204aa1`. **Ne pas réintroduire d'étape de build** : deux sources divergent
toujours, et c'est précisément ce qui a produit des scripts faux.

## La page s'édite comme artefact

Le travail de fond se fait dans un artefact Claude, puis la version vivante est
rapatriée ici. La procédure, à refaire à chaque reprise :

1. lire l'artefact (l'URL est dans la mémoire de projet, pas ici : le dépôt est
   public) ;
2. copier le HTML dans `docs/index.html` ;
3. **retirer le bloc `window.claude.use('db')`**, une douzaine de lignes juste
   avant le commentaire « replier et deplier les reponses ». Il synchronisait la
   progression par le stockage d'artefact, runtime qui n'existe pas hors de
   claude.ai. La page écrit déjà dans `localStorage`, donc le retrait ne change
   rien au fonctionnement ;
4. vérifier qu'il ne reste aucune occurrence de `window.claude`, puis pousser.

`highlight.js` est embarqué dans la page, d'où sa taille. Les seules ressources
externes sont les polices Google, avec repli sur les polices système.

## Publication

GitHub Pages sert `main` + `/docs` sur <https://cchopin.github.io/sql-serveur/>,
HTTPS forcé. Le dépôt est public depuis le 20 octobre 2026 : son historique
entier a été vérifié avant la bascule, aucun secret ni nom d'hôte.

`.claude/` et `CLAUDE.local.md` sont exclus par `.gitignore`. La mémoire
automatique de Claude n'est jamais dans ce dépôt : elle vit dans
`~/.claude/projects/<clé>/memory`, versionnée dans un dépôt privé.

## Vérifier après publication

Pages met une à deux minutes à servir une nouvelle version, et sert l'ancienne
entre-temps. Attendre que la taille corresponde, pas seulement le code 200 :

```sh
curl -s -o /dev/null -w '%{http_code} · %{size_download}\n' \
  "https://cchopin.github.io/sql-serveur/?cb=$RANDOM"
```
