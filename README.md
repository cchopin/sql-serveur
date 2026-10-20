# sql-serveur

Cours SQL Server : performance à grande échelle. Parcours de trois mois, lab
sur SQL Server 2025, pour passer du tuning approximatif à l'expertise sur une
base volumineuse.

**[Lire le cours](https://cchopin.github.io/sql-serveur/)**

23 modules répartis en quatre phases, et un programme de 60 séances d'une heure
sur 12 semaines. Chaque module se lit la veille, chaque séance se termine sur
une mesure. La progression (modules acquis, séances faites) se garde dans le
navigateur du lecteur.

| Phase | Modules | Objet |
|---|---|---|
| 1 · Fondations | 1 à 5 | pages, buffer pool, types, lecture d'un plan |
| 2 · Index et requêtes | 6 à 13 | index, sargabilité, jointures, statistiques, mémoire |
| 3 · Grande échelle | 14 à 19 | parallélisme, verrous, partitionnement, columnstore |
| 4 · Exploitation | 20 à 23 | Query Store, wait stats, configuration, prise de poste |

## Organisation du dépôt

- `docs/index.html` : **le cours**, page autonome publiée par GitHub Pages.
  Sommaire latéral, coloration T-SQL, boutons copier, thème clair et sombre,
  mise en page d'impression, suivi de progression. Aucune dépendance autre que
  les polices Google, avec repli sur les polices système.
La page est la seule source : elle s'édite directement, il n'y a ni Markdown
ni étape de build. Une édition précédente existait, 15 épisodes générés depuis
un fichier Markdown par un script `build.py` ; elle a été retirée le 20 octobre
2026, ses scripts T-SQL ayant été corrigés depuis sans l'être là, et le script
écrasait la page publiée s'il était relancé. L'historique git la conserve, au
commit `6afdc39` et avant.
