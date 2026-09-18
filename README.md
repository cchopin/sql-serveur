# sql-serveur

Cours SQL Server : performance à grande échelle (SQL Server 2019 et 2022).

- `cours/cours-sql-server-performance.md` : le cours, en Markdown. Partie 1 : 15 épisodes de théorie qui suivent et prolongent *How to Think Like the SQL Server Engine* de Brent Ozar. Partie 2 : 13 chapitres pratiques (commandes, diagnostic, exercices sur un lab StackOverflow).
- `docs/index.html` : la même chose en page HTML autonome (sommaire latéral, coloration T-SQL, boutons copier, thème clair et sombre, mise en page d'impression). Compatible GitHub Pages en pointant sur le dossier `docs/`.
- `build.py` : régénère `docs/index.html` à partir du Markdown.

## Régénérer la version HTML

```bash
pip install markdown      # une seule fois
python3 build.py
```

Le script ne dépend que de `python-markdown`. La coloration SQL et la navigation sont produites au build, la page n'a besoin d'aucune bibliothèque JavaScript externe (seules les polices sont chargées depuis Google Fonts, avec repli sur les polices système).
