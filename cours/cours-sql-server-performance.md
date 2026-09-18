# Cours SQL Server : performance à grande échelle

Parcours progressif pour devenir opérationnel sur le tuning d'une base SQL Server volumineuse (tables de plusieurs centaines de millions à plusieurs milliards de lignes). Le cours est en deux parties : la première explique les mécaniques internes du moteur, de manière à comprendre et pouvoir réexpliquer chaque concept ; la seconde donne les commandes, les méthodes de diagnostic et des exercices sur un lab. La première partie suit la démarche de la formation gratuite How to Think Like the SQL Server Engine de Brent Ozar et la prolonge.

Prérequis : bonne connaissance du T-SQL et de l'administration de base d'une instance SQL Server. Versions visées : SQL Server 2019 et 2022, avec mention des différences quand elles comptent.

## Sommaire

Partie 1 : penser comme le moteur (théorie, d'après la démarche de Brent Ozar)

- Épisode 1\. L'index cluster : la table est une pile de pages  
- Épisode 2\. SELECT \*, ORDER BY et la mémoire  
- Épisode 3\. L'index non-cluster : une deuxième pile  
- Épisode 4\. Key lookups, tipping point et colonnes incluses  
- Épisode 5\. Les statistiques : comment le moteur a deviné  
- Épisode 6\. Sargabilité et conversions  
- Épisode 7\. Les jointures : deux piles à la fois  
- Épisode 8\. Trop d'index, page splits et fragmentation  
- Épisode 9\. Édition Big Data : la pile fait un milliard de lignes  
- Épisode 10\. Le partitionnement : plusieurs piles pour une seule table  
- Épisode 11\. Le columnstore : découper les feuilles en colonnes  
- Épisode 12\. Le Query Store : le carnet de bord  
- Épisode 13\. La compression rowstore : des feuilles plus denses  
- Épisode 14\. Plusieurs lecteurs sur les mêmes feuilles : verrous et isolation  
- Épisode 15\. Synthèse : les chaînes de causalité

Partie 2 : la pratique (commandes, diagnostic, exercices)

1. Le lab d'entraînement  
2. Méthodologie de diagnostic : par où commencer  
3. Lire un plan d'exécution  
4. Query Store  
5. Statistiques et estimateur de cardinalité  
6. Index rowstore : conception, usage, maintenance  
7. Partitionnement  
8. Index columnstore  
9. Compression de données  
10. Verrouillage, isolation et concurrence  
11. Configuration de l'instance  
12. Checklist de prise en main d'une instance inconnue  
13. Programme d'entraînement

Parcours conseillé : regarder la vidéo How to Think Like the SQL Server Engine (gratuite sur brentozar.com, pages à imprimer fournies) en lisant les épisodes 1 à 6, qui en suivent la progression ; poursuivre avec les épisodes 7 à 15, qui prolongent la même métaphore vers les sujets propres aux très gros volumes ; puis alterner épisode théorique et chapitre pratique correspondant : 1 et 2 avec le chapitre 3, 3 et 4 avec le 6, 5 avec le 5, 9 avec les chapitres 2 et 11, 10 avec le 7, 11 avec le 8, 12 avec le 4, 13 avec le 9, 14 avec le 10\. Les sections "Ce qu'il faut pouvoir expliquer" servent de test : si une réponse ne vient pas en deux ou trois phrases, relire la section.

---

# Partie 1 : penser comme le moteur

Cette partie reprend la pédagogie de la formation gratuite de Brent Ozar, How to Think Like the SQL Server Engine (vidéo d'environ deux heures, version écrite et édition Big Data disponibles sur brentozar.com après inscription gratuite). Le principe est un jeu de rôle : l'utilisateur envoie des requêtes, et le lecteur joue le rôle du moteur SQL Server, avec pour seul matériel les pages de la base imprimées sur du papier. Chaque concept est introduit au moment où le moteur en a besoin pour répondre à une requête, jamais avant.

Il est fortement conseillé de regarder la vidéo en parallèle des six premiers épisodes, avec les pages imprimées (le PDF de cinq pages fourni par l'auteur) ; ce cours en reprend la démarche avec ses propres exemples et la prolonge ensuite vers les sujets que la vidéo ne couvre pas (très gros volumes, partitionnement, columnstore, Query Store, compression, concurrence), en gardant la même métaphore.

Les chiffres donnés (nombre de pages, de lignes par page) sont indicatifs et arrondis pour raisonner ; les vrais se lisent dans `sys.dm_db_partition_stats` sur le lab.

---

## Épisode 1\. L'index cluster : la table est une pile de pages

### Le matériel

La table `dbo.Users` de StackOverflow (version 2013\) contient environ 2,5 millions de lignes avec, entre autres, les colonnes `Id`, `DisplayName`, `Location`, `Reputation`, `CreationDate`, `LastAccessDate`, `Age`, `UpVotes`, `DownVotes`, `Views`, `WebsiteUrl`, `AboutMe`. Elle a une clé primaire cluster sur `Id`.

Ce que cela signifie physiquement : les lignes sont rangées, triées par `Id`, dans des pages de 8 Ko. Une page est une feuille de papier. Sur chaque feuille tiennent, disons, une trentaine d'utilisateurs (la ligne fait environ 250 octets en moyenne, `AboutMe` étant souvent vide). La table, c'est donc une pile d'environ 80 000 feuilles, triées par `Id` : la feuille 1 contient les Id 1 à 30, la suivante 31 à 62, et ainsi de suite jusqu'à la dernière.

Point essentiel, souvent mal compris : il n'y a pas "la table" d'un côté et "l'index cluster" de l'autre. L'index cluster est la table. C'est le nom que porte la pile de feuilles quand elle est triée. Une table sans index cluster (un heap) est la même pile dans le désordre.

Ce que contient une feuille :

\+------------------------------------------------+

| En-tête (96 octets) : numéro de page, objet,   |

| nombre de lignes, espace libre, page suivante  |

| et précédente dans l'ordre des Id              |

\+------------------------------------------------+

| Id 1     | DisplayName ... | Reputation ...    |

| Id 2     | ...                                  |

| ...                                             |

| Id 30    | ...                                  |

|                 (espace libre)                  |

| tableau des positions des lignes (2 o / ligne) |

\+------------------------------------------------+

Le tableau en bas de page donne l'ordre logique des lignes : quand une ligne s'insère entre deux autres, seul ce tableau est réordonné, la ligne est écrite dans l'espace libre. Tant que la page n'est pas pleine, insérer est bon marché.

### Requête 1 : tout lire

SELECT Id FROM dbo.Users ORDER BY Id;

Le moteur (le lecteur) a la pile de 80 000 feuilles devant lui. La requête veut tous les Id, dans l'ordre. Il n'y a qu'une façon de faire : prendre la première feuille, recopier les Id, prendre la suivante, jusqu'à la dernière. Le tri est gratuit puisque la pile est déjà triée par Id.

Ce que SQL Server dit de cette exécution :

Table 'Users'. Scan count 1, logical reads 80000, physical reads ...

Une lecture logique est une feuille consultée. C'est la mesure fondamentale du travail : elle ne dépend ni de la vitesse du disque, ni de ce qui est en cache, ni de la charge du serveur. Deux requêtes, ou deux versions d'une requête, se comparent d'abord sur leurs lectures logiques.

L'opérateur du plan d'exécution est un Clustered Index Scan : parcourir toutes les feuilles de l'index cluster. Le mot "scan" n'est pas péjoratif : ici, la requête demande toute la table, le scan est la seule réponse correcte.

### Où sont les feuilles : le buffer pool

Le moteur ne lit jamais une feuille directement sur le disque. Toute feuille doit d'abord être en mémoire, dans le buffer pool, que l'on peut se représenter comme le bureau sur lequel le moteur travaille : les feuilles y sont posées, il les consulte à volonté (lecture logique), et quand une feuille manque, il va la chercher dans l'armoire (le disque) : c'est une lecture physique, des centaines de fois plus lente, pendant laquelle le moteur attend (`PAGEIOLATCH_SH`).

Le bureau a une taille finie (`max server memory`). Quand il est plein, les feuilles les moins utilisées récemment sont rangées pour faire de la place. La Page Life Expectancy mesure combien de temps une feuille reste sur le bureau sans être consultée avant d'être rangée.

Pour un scan, SQL Server anticipe : il ramène des paquets de feuilles consécutives (read-ahead, jusqu'à 512 Ko ou 4 Mo à la fois) plutôt qu'une par une.

### Pourquoi la même requête est rapide en développement et lente en production

Première leçon pratique de la vidéo, et qui revient sans cesse en poste : la requête 1 s'exécute en 2 secondes sur le poste du développeur et en 3 minutes en production, avec exactement le même plan. Trois raisons possibles :

- en développement, la table fait 50 000 lignes et 1 600 feuilles ; le même scan coûte 50 fois moins ;  
- en développement, la base entière est sur le bureau ; en production, le bureau de 128 Go doit accueillir 2 To de feuilles, et la plupart des lectures sont physiques ;  
- en développement, une seule requête tourne ; en production, 300 sessions se partagent le bureau et les processeurs.

Le plan d'exécution ne montre rien de tout cela : il ne connaît ni la taille du bureau ni ce qui s'y trouve. Le nombre de lectures logiques, lui, est le même dans les deux environnements si le volume de données est le même. C'est pourquoi le tuning se fait sur les lectures logiques, sur un volume représentatif.

### Requête 2 : une seule ligne

SELECT \* FROM dbo.Users WHERE Id \= 26837;

Le moteur pourrait scanner les 80 000 feuilles. Mais la pile est triée par Id : il suffit de trouver la bonne feuille. Comment, sans les feuilleter toutes ? Grâce à une table des matières.

Au-dessus de la pile, SQL Server maintient des pages intermédiaires qui listent, pour chaque feuille, le premier Id qu'elle contient : "feuille 1 : Id 1, feuille 2 : Id 31, ...". Une page intermédiaire contient quelques centaines de ces entrées (environ 600 pour une clé `BIGINT` avec son pointeur). Pour 80 000 feuilles, il faut environ 140 pages intermédiaires. Et au-dessus d'elles, une page racine qui liste le premier Id de chacune des 140 pages intermédiaires.

                    \[ racine : 1 page \]

                   /        |         \\

     \[ interm. 1 \]   \[ interm. 2 \] ... \[ interm. 140 \]

     /    |    \\

 \[f. 1\] \[f. 2\] ... \[f. 600\]  ...                 \[f. 80000\]

C'est un arbre B+ : la racine, un ou plusieurs niveaux intermédiaires, et les feuilles chaînées entre elles. Trouver l'Id 26837 : lire la racine (1 lecture), qui renvoie vers la page intermédiaire couvrant 26 000 à 27 000 ; la lire (1 lecture), qui renvoie vers la feuille exacte ; la lire (1 lecture). Trois lectures logiques au lieu de 80 000\. L'opérateur est un Clustered Index Seek.

La puissance de l'arbre est logarithmique : 80 000 feuilles → 3 niveaux ; 2,5 millions de feuilles (une table de 1 milliard de lignes à 400 par page) → 4 niveaux, donc 4 lectures. Passer de 2,5 millions à 1 milliard de lignes ajoute une seule lecture par recherche. Et les pages du haut de l'arbre, consultées par toutes les requêtes, sont toujours sur le bureau.

### Requête 3 : un filtre sur une autre colonne

SELECT Id FROM dbo.Users WHERE LastAccessDate \>= '2013-01-01';

La table des matières est par Id. Elle ne dit rien sur `LastAccessDate`. Le moteur n'a aucun moyen de savoir dans quelles feuilles sont les utilisateurs récemment actifs : ils sont dispersés dans toute la pile, puisque l'ordre est celui des Id. Seule solution : lire les 80 000 feuilles et, pour chaque ligne, regarder la date. Clustered Index Scan, 80 000 lectures, avec un prédicat appliqué ligne par ligne.

Même si la requête ne ramène que 1 000 utilisateurs, elle a coûté autant que la requête 1 qui en ramenait 2,5 millions. Le coût d'une requête ne dépend pas du nombre de lignes qu'elle retourne, mais du nombre de feuilles qu'il a fallu consulter pour les trouver.

### Lire le plan

Sur ces trois requêtes, le plan d'exécution (le plan réel, obtenu avec l'option "Include Actual Execution Plan") montre un seul opérateur d'accès. En survolant l'opérateur ou en ouvrant ses propriétés :

- Estimated Number of Rows : combien de lignes le moteur pensait trouver avant d'exécuter ;  
- Actual Number of Rows : combien il en a réellement produit ;  
- Number of Rows Read : combien il en a examinées (pour la requête 3 : 2,5 millions lues, 1 000 produites) ;  
- Estimated Operator Cost : un nombre abstrait sans unité, qui servait de secondes sur un poste de 1997, et qui ne sert qu'à comparer des plans entre eux.

Tout le reste du tuning consiste à lire ces quatre chiffres sur chaque opérateur et à comprendre pourquoi ils sont ce qu'ils sont.

### Ce qu'il faut pouvoir expliquer

- Pourquoi l'index cluster est la table, et ce qu'est un heap.  
- Ce qu'est une lecture logique et pourquoi c'est la bonne unité de mesure.  
- Pourquoi un scan n'est pas toujours mauvais ni un seek toujours bon.  
- Comment l'arbre B+ permet de trouver une ligne parmi un milliard en quatre lectures.  
- Pourquoi une requête peut coûter autant en ramenant 1 000 lignes qu'en ramenant 2,5 millions.  
- Pourquoi la même requête est lente en production et rapide en développement.

---

## Épisode 2\. SELECT \*, ORDER BY et la mémoire

### Requête 4 : trier sur une colonne non triée

SELECT \* FROM dbo.Users WHERE LastAccessDate \>= '2013-01-01' ORDER BY LastAccessDate;

Le moteur scanne les 80 000 feuilles (comme en requête 3\) et recopie sur un brouillon toutes les lignes qui passent le filtre, avec toutes leurs colonnes puisque la requête demande `*`. Puis il doit trier ce brouillon par `LastAccessDate`. Rien dans la pile ne l'aide : la pile est triée par Id.

Le plan gagne un opérateur : Sort. Et le Sort introduit un nouveau problème : où se fait le tri ?

### La memory grant

Trier demande de l'espace de travail. Avant de démarrer la requête, le moteur réserve une quantité de mémoire pour ce tri : la memory grant. Mais il ne sait pas encore combien de lignes vont passer le filtre, ni leur taille : il l'estime. L'estimation vient des statistiques (épisode 5\) pour le nombre de lignes, et de la définition des colonnes pour leur largeur.

Ici, deux difficultés :

- `SELECT *` inclut `AboutMe`, une colonne `NVARCHAR(MAX)`. Le moteur ne connaît pas la longueur réelle des textes ; il suppose une largeur moyenne (pour un `VARCHAR(n)`, la moitié de n ; pour un `MAX`, une valeur fixe de plusieurs Ko). La grant est donc calculée pour des lignes bien plus larges que la réalité ;  
- le nombre de lignes estimé est celui de l'histogramme au moment de la compilation.

Si la réserve est trop petite, le brouillon ne tient pas : le moteur écrit une partie du tri sur une table d'appoint, TempDB, et le relit. C'est un spill, signalé par un triangle jaune sur l'opérateur Sort. Le tri devient plusieurs fois plus lent, et TempDB, partagée par toutes les sessions de l'instance, encaisse le trafic.

Si la réserve est trop grande, la requête réserve pour rien de la mémoire que les autres n'ont plus. Chaque requête ne peut réserver au plus qu'un quart de la mémoire disponible pour les tris et hachages ; quatre rapports mal estimés lancés ensemble suffisent à faire attendre le cinquième (`RESOURCE_SEMAPHORE`), et à évincer les feuilles du bureau pour libérer cet espace.

Dans les deux cas, la cause est la même : une estimation fausse. Le plan indique la grant réservée (`Memory Grant`), la mémoire réellement utilisée (`MaxUsedMemory`) et prévient si l'écart est grand (`ExcessiveGrant`).

### Le tri coûte à chaque exécution

Si cette requête tourne 500 fois par minute (une page web qui affiche les derniers utilisateurs actifs), le moteur scanne 80 000 feuilles et refait le tri 500 fois par minute. C'est 40 millions de lectures logiques par minute pour produire à chaque fois les mêmes 1 000 lignes. Il n'y a pas de réglage d'instance, de mémoire ou de disque qui rende cela acceptable. Le problème est structurel : la pile est triée par la mauvaise colonne pour cette requête. Il faut une deuxième pile.

### Opérateurs bloquants

Le Sort a une autre propriété importante : il ne peut rien produire avant d'avoir tout reçu. Tant que la dernière feuille n'a pas été lue, la première ligne triée n'est pas connue. C'est un opérateur bloquant, comme le Hash Match (épisode 7). À l'inverse, un Filter, un Compute Scalar, un Nested Loops laissent passer les lignes une à une. Un `TOP 10 ... ORDER BY LastAccessDate` sans index sur cette colonne doit donc lire et examiner toute la table pour rendre 10 lignes : le TOP ne fait pas d'économie de lecture, seulement de mémoire (Top N Sort ne conserve que les 10 meilleures).

### Ce qu'il faut pouvoir expliquer

- Pourquoi un `ORDER BY` sur une colonne non indexée ajoute un Sort et ce que ce Sort coûte.  
- Ce qu'est une memory grant, d'où viennent ses deux composantes (lignes, largeur), et pourquoi `SELECT *` la fausse.  
- Ce qu'est un spill et pourquoi il pénalise tout le serveur.  
- Pourquoi une grant surestimée est aussi un problème.  
- Ce qu'est un opérateur bloquant et pourquoi un `TOP` n'économise pas les lectures.

---

## Épisode 3\. L'index non-cluster : une deuxième pile

### Créer la pile

CREATE INDEX IX\_LastAccessDate ON dbo.Users (LastAccessDate);

SQL Server fabrique une deuxième pile de feuilles, séparée de la première, triée par `LastAccessDate`. Que contient chaque ligne de cette pile ? La colonne clé, `LastAccessDate`, et automatiquement la clé cluster, `Id`, qui sert d'adresse pour retrouver la ligne complète dans la grande pile. Rien d'autre.

Pile 1 (index cluster, triée par Id)         Pile 2 (IX\_LastAccessDate, triée par LastAccessDate)

| Id | DisplayName | Location | ... | \~30/p   | LastAccessDate      | Id     |   \~400/page

| 1  | Jeff        | El Paso  | ... |         | 2008-07-31 14:22:31 | 1      |

| 2  | Geoff       | Corvallis| ... |         | 2008-07-31 14:22:31 | 2      |

| ...                                         | ...                          |

80 000 feuilles                               environ 6 500 feuilles

La pile 2 est dix fois plus petite, parce que ses lignes sont dix fois plus étroites : deux colonnes au lieu de douze. Elle a sa propre table des matières (racine et niveau intermédiaire) par `LastAccessDate`.

### Requête 5 : la pile 2 suffit

SELECT Id, LastAccessDate FROM dbo.Users WHERE LastAccessDate \>= '2013-01-01' ORDER BY LastAccessDate;

Le moteur a maintenant un choix. La requête filtre et trie sur `LastAccessDate`, et ne demande que `Id` et `LastAccessDate`. La pile 2 contient exactement ces deux colonnes et est triée dans le bon ordre. Descendre la table des matières de la pile 2 jusqu'à la première ligne de 2013 (2 ou 3 lectures), puis lire les feuilles suivantes jusqu'à la fin (quelques dizaines de feuilles). Index Seek, pas de Sort, environ 30 lectures au lieu de 80 000 plus un tri.

On dit que l'index couvre la requête : il contient toutes les colonnes dont elle a besoin. C'est le cas idéal.

### Ce que la pile 2 coûte

Rien n'est gratuit. Désormais :

- chaque nouvel utilisateur est écrit dans les deux piles ;  
- chaque changement de `LastAccessDate` (à chaque connexion d'un utilisateur, donc en permanence) modifie la ligne dans la pile 1, et dans la pile 2 la ligne doit être supprimée de sa feuille actuelle et réinsérée dans la feuille correspondant à la nouvelle date, tout à l'autre bout de la pile puisque la nouvelle date est la plus récente. Deux feuilles modifiées, tout journalisé ;  
- chaque suppression d'utilisateur touche les deux piles ;  
- la pile 2 occupe de la place sur le bureau (buffer pool), sur le disque, dans les sauvegardes.

Avec 12 index sur une table, un `INSERT` écrit dans 13 piles. C'est pourquoi la question à se poser pour chaque index est toujours la même : ses lectures justifient-elles ses écritures ?

### Une remarque sur la clé cluster

La pile 2 contient `Id` dans chaque ligne parce que `Id` est la clé cluster. Si la clé cluster avait été un `UNIQUEIDENTIFIER` (16 octets) au lieu d'un `INT` (4), chaque ligne de chaque index non-cluster serait 12 octets plus large, donc chaque pile plus haute, donc chaque recherche un peu plus coûteuse. Si la clé cluster avait été `DisplayName` (non unique), SQL Server aurait dû ajouter un numéro (uniquifier, 4 octets) pour distinguer les homonymes. La règle "clé cluster étroite, unique, croissante et jamais modifiée" vient directement de là : elle est copiée partout.

### Ce qu'il faut pouvoir expliquer

- Ce que contient physiquement un index non-cluster et pourquoi il est plus petit que la table.  
- Pourquoi la clé cluster se retrouve dans tous les index non-cluster, et ce que cela implique pour son choix.  
- Ce qu'est un index couvrant.  
- Ce que coûte un index à chaque écriture, et pourquoi la mise à jour d'une colonne indexée est plus chère qu'il n'y paraît.

---

## Épisode 4\. Key lookups, tipping point et colonnes incluses

### Requête 6 : une colonne de plus

SELECT Id, LastAccessDate, DisplayName FROM dbo.Users WHERE LastAccessDate \>= '2013-01-01';

Une colonne de plus, `DisplayName`, et tout change. La pile 2 ne la contient pas. Le moteur a deux stratégies :

Stratégie A : utiliser la pile 2 pour trouver les utilisateurs de 2013 (30 lectures), puis, pour chacun d'eux, aller chercher `DisplayName` dans la pile 1 grâce à l'Id : descendre la table des matières de la pile 1 (3 lectures) autant de fois qu'il y a d'utilisateurs. Pour 1 000 utilisateurs : 30 \+ 3 000 \= 3 030 lectures. C'est le Key Lookup : un Index Seek suivi, dans une boucle (Nested Loops), d'un Clustered Index Seek par ligne.

Stratégie B : ignorer la pile 2 et scanner la pile 1 : 80 000 lectures, mais en une seule passe séquentielle.

Pour 1 000 utilisateurs, A gagne largement. Pour 100 000 utilisateurs (si le filtre était `>= '2010-01-01'`) : A coûte 300 000 lectures aléatoires, B toujours 80 000 séquentielles. B gagne.

### Le tipping point

Le moteur doit choisir entre A et B avant d'exécuter, donc sur la base du nombre de lignes estimé. Le seuil où B devient meilleur que A, le tipping point, est très bas : de l'ordre de 25 à 30 % du nombre de feuilles de la table, en nombre de lignes. Ici, environ 20 000 à 25 000 utilisateurs sur 2,5 millions, soit à peine 1 % des lignes. Autrement dit : dès qu'une requête ramène plus de 1 % de la table, un index non couvrant est ignoré au profit d'un scan. C'est ce qui surprend le plus les développeurs : "j'ai créé l'index et SQL Server ne l'utilise pas". Il l'a évalué et a jugé que les lookups coûteraient plus cher que le scan.

Le tipping point explique aussi les plans qui basculent d'un jour à l'autre : la même requête avec un paramètre légèrement différent, ou après quelques insertions, passe d'un côté à l'autre du seuil et change de plan.

### Les colonnes incluses

La solution n'est ni un hint pour forcer l'index, ni un troisième index : c'est d'élargir la pile 2 pour qu'elle couvre à nouveau la requête.

CREATE INDEX IX\_LastAccessDate ON dbo.Users (LastAccessDate) INCLUDE (DisplayName) WITH (DROP\_EXISTING \= ON);

`DisplayName` est ajouté dans les feuilles de la pile 2, mais pas dans la table des matières : la pile reste triée par `LastAccessDate` seul, et la colonne incluse est juste transportée. La pile 2 devient plus large (peut-être 12 000 feuilles au lieu de 6 500), mais la requête 6 redevient un seek couvrant de quelques dizaines de lectures, quel que soit le nombre de lignes ramenées : il n'y a plus de tipping point.

La contrepartie est la même que toujours : plus la pile est large, plus elle coûte en écriture et en mémoire, et chaque colonne incluse doit aussi être maintenue quand elle change. La règle de conception pratique : inclure les colonnes nécessaires aux requêtes critiques, et pas `SELECT *`. Un index qui inclut toutes les colonnes est une deuxième copie de la table.

### Clé ou INCLUDE ?

Une colonne va dans la clé si elle sert à filtrer (égalité, plage) ou à trier ; elle va en `INCLUDE` si elle est seulement lue. Dans la clé, les colonnes sont ordonnées : `(LastAccessDate, DisplayName)` trie par date puis par nom pour une même date ; cela ne sert que si une requête filtre sur les deux ou trie par les deux. Une colonne en clé grossit aussi la table des matières ; une colonne en `INCLUDE` ne grossit que les feuilles.

### Ce qu'il faut pouvoir expliquer

- Ce qu'est un Key Lookup, combien il coûte, et pourquoi il est exécuté dans une boucle.  
- Le tipping point : pourquoi il existe, pourquoi il est si bas, et le symptôme qu'il produit.  
- Ce que change une colonne incluse dans la structure de l'index, et la différence avec une colonne clé.  
- Pourquoi la réponse à un index ignoré n'est ni un hint ni un index supplémentaire.

---

## Épisode 5\. Les statistiques : comment le moteur a deviné

### Deux requêtes, deux plans

SELECT Id, LastAccessDate, Location FROM dbo.Users WHERE LastAccessDate \>= '2013-01-01';   \-- Index Seek \+ Key Lookup

SELECT Id, LastAccessDate, Location FROM dbo.Users WHERE LastAccessDate \>= '2010-01-01';   \-- Clustered Index Scan

Même requête, deux plans différents. Le moteur a prédit que la première ramènerait quelques milliers de lignes (sous le tipping point) et la seconde des centaines de milliers (au-dessus). Comment a-t-il prédit cela sans lire la table ?

### L'histogramme

Quand l'index `IX_LastAccessDate` a été créé, SQL Server a calculé une statistique sur sa première colonne : un résumé de la distribution de `LastAccessDate` en au plus 200 pas. Pour chaque pas, il a retenu une date frontière, le nombre de lignes exactement égales à cette date, le nombre de lignes comprises entre cette frontière et la précédente, et le nombre de valeurs distinctes dans cet intervalle.

RANGE\_HI\_KEY          RANGE\_ROWS   EQ\_ROWS   DISTINCT\_RANGE\_ROWS   AVG\_RANGE\_ROWS

2008-07-31 14:22:31   0            2         0                     1

2009-03-15 08:10:44   64 000       1         63 900                1.0

2010-01-02 11:03:12   98 000       1         97 950                1.0

...

2012-12-30 22:14:09   150 000      1         149 800               1.0

2013-01-04 09:55:31   3 200        1         3 190                 1.0

...

Pour estimer `>= '2013-01-01'`, le moteur additionne les lignes de tous les pas au-delà de cette date (en interpolant dans le pas qui contient la borne) : disons 4 500\. Pour `>= '2010-01-01'`, la somme est de plusieurs centaines de milliers. Il compare aux 80 000 feuilles de la table, applique son modèle de coût (une lecture aléatoire de lookup coûte plus cher qu'une lecture de scan), et choisit.

Ces 200 pas sont toute la connaissance que le moteur a de la colonne. Sur 2,5 millions de lignes, chaque pas résume en moyenne 12 000 lignes par une seule moyenne. Sur 1 milliard de lignes, 5 millions par pas. Une valeur atypique à l'intérieur d'un pas est invisible ; l'algorithme de construction donne heureusement un pas propre aux valeurs très fréquentes (un `EQ_ROWS` élevé).

### La densité

L'histogramme n'existe que sur la première colonne de la statistique. Pour les combinaisons de colonnes, et pour les cas où la valeur cherchée n'est pas connue à la compilation, le moteur dispose d'un second chiffre : la densité, égale à 1 divisé par le nombre de valeurs distinctes. Multipliée par le nombre de lignes, elle donne le nombre moyen de lignes par valeur. C'est une moyenne aveugle : pour `Location`, si 500 000 valeurs distinctes existent, la densité dit "5 lignes par ville", ce qui est vrai en moyenne et faux pour Londres (30 000\) comme pour Villefollet (1).

### Quand la valeur n'est pas connue à la compilation

DECLARE @d DATETIME \= '2013-01-01';

SELECT Id, LastAccessDate, Location FROM dbo.Users WHERE LastAccessDate \>= @d;

Le moteur compile la requête avant d'exécuter le `DECLARE` : au moment de choisir le plan, il ne connaît pas la valeur de `@d`. Il ne peut pas consulter l'histogramme. Pour une inégalité sur une valeur inconnue, il applique une règle fixe : 30 % des lignes. 750 000 lignes estimées, très au-dessus du tipping point : scan, alors qu'un seek aurait été parfait. Avec `OPTION (RECOMPILE)`, la requête est compilée après l'affectation, la valeur est connue, l'histogramme est utilisé.

Dans une procédure stockée, c'est différent : le paramètre est connu au moment de la compilation, parce que la procédure est compilée à sa première exécution, avec les valeurs passées à ce moment-là. C'est le parameter sniffing : le moteur renifle les paramètres et optimise pour eux.

### Le parameter sniffing

CREATE PROCEDURE GetUsersSince @d DATETIME AS

SELECT Id, LastAccessDate, Location FROM dbo.Users WHERE LastAccessDate \>= @d;

Première exécution avec `@d = '2013-01-01'` : histogramme, 4 500 lignes, plan Seek \+ Lookup, mis en cache. Deuxième exécution avec `@d = '2008-01-01'` : le plan est en cache, il est réutilisé, Seek \+ Lookup pour 2,5 millions de lignes, 7,5 millions de lectures aléatoires au lieu d'un scan à 80 000\. Ou l'inverse, si la première exécution était celle de 2008 : un scan de 80 000 feuilles pour ramener 4 500 lignes, à chaque appel.

Ce n'est pas un défaut : compiler une fois et réutiliser est ce qui rend les procédures rapides, et pour une distribution régulière le plan est bon pour tout le monde. Le problème n'apparaît que sur les distributions asymétriques, quand le meilleur plan dépend fortement de la valeur. Le plan en cache garde la trace de la valeur avec laquelle il a été compilé (`ParameterCompiledValue`), ce qui rend le diagnostic possible ; le Query Store montre la même requête avec des durées très variables selon les exécutions.

Les réponses vont du plus ciblé au plus général : recompiler à chaque exécution (`OPTION (RECOMPILE)`, au prix d'une compilation par appel), optimiser pour une valeur représentative ou pour la densité (`OPTIMIZE FOR`), rendre le plan insensible en couvrant la requête (plus de tipping point, donc plus de dilemme), séparer les cas dans le code, forcer un plan via le Query Store, et depuis SQL 2022, laisser le moteur garder plusieurs plans par requête (Parameter Sensitive Plan optimization) pour les prédicats d'égalité sur colonnes asymétriques.

### Des statistiques périmées

L'histogramme a été construit à un instant donné. Depuis, des utilisateurs se sont connectés, leur `LastAccessDate` a changé. SQL Server compte les modifications de la colonne et recalcule la statistique quand un seuil est franchi (environ racine carrée de 1 000 fois le nombre de lignes depuis SQL 2016 en compatibilité 130 ; 20 % des lignes avant, ce qui sur une très grosse table revenait à jamais). Entre deux recalculs, l'histogramme ne connaît pas les nouvelles valeurs.

Cas typique : les dates les plus récentes sont au-delà du dernier pas. Une requête sur "les dernières 24 heures" trouve dans l'histogramme zéro ligne au-delà de la dernière frontière : estimation 1 ligne, plan Seek \+ Lookup, memory grant minuscule ; réalité 500 000 lignes, lookups par millions et tris qui débordent. Le nouvel estimateur (compatibilité 120 et plus) atténue cela en supposant que les lignes ajoutées depuis le calcul sont au-delà de la dernière frontière, mais il extrapole. C'est le problème de la clé ascendante, et le motif du "c'est lent le lundi matin après le chargement du week-end".

Le recalcul se fait par échantillonnage (une fraction des feuilles, de plus en plus faible quand la table grossit), et par défaut de façon synchrone : la requête qui déclenche le recalcul attend qu'il finisse. Sur une table d'un milliard de lignes, cela peut prendre des minutes, aléatoirement, au milieu de la journée. Le mode asynchrone laisse la requête utiliser l'ancienne statistique pendant que le recalcul se fait en arrière-plan. Et un recalcul invalide les plans en cache qui utilisaient la statistique : c'est ce qui fait qu'un plan "change tout seul" une nuit.

### Ce qu'il faut pouvoir expliquer

- Ce qu'est l'histogramme, comment le moteur l'utilise pour estimer une plage, et pourquoi 200 pas ne suffisent pas toujours.  
- Ce qu'est la densité et dans quel cas elle sert.  
- Pourquoi une variable locale et un paramètre de procédure donnent des plans différents.  
- Le mécanisme du parameter sniffing, pourquoi ce n'est pas un bug, et les niveaux de réponse.  
- Le problème de la clé ascendante et son symptôme.  
- Pourquoi un plan change sans que personne n'ait rien fait.

---

## Épisode 6\. Sargabilité et conversions

### Requête 7 : une fonction sur la colonne

SELECT Id FROM dbo.Users WHERE YEAR(LastAccessDate) \= 2013;

La pile 2 est triée par `LastAccessDate`. Pour utiliser sa table des matières, le moteur doit pouvoir dire "descends jusqu'à la première valeur supérieure ou égale à X". Mais la requête ne dit pas cela : elle dit "les lignes pour lesquelles une fonction appliquée à la colonne renvoie 2013". Le moteur ne sait pas inverser `YEAR()` ; il ne peut pas transformer cela en une plage sur la colonne. Il doit lire chaque ligne, calculer `YEAR()`, comparer. Il utilisera peut-être la pile 2 plutôt que la pile 1 parce qu'elle est plus petite (Index Scan, 6 500 lectures), mais c'est un scan.

Un prédicat est SARGable (Search ARGument able) quand la colonne est seule d'un côté de la comparaison, sans fonction ni calcul : `LastAccessDate >= '2013-01-01' AND LastAccessDate < '2014-01-01'` fait le même travail en seek. Autres cas classiques non SARGables : `CONVERT(DATE, col) = ...`, `ISNULL(col, x) = ...`, `col + 1 = ...`, `LIKE '%texte'`, `LEFT(col, 3) = ...`. Le correctif est toujours la réécriture du prédicat, jamais un index.

### Requête 8 : la conversion implicite

DECLARE @name NVARCHAR(40) \= N'Brent Ozar';

SELECT Id FROM dbo.Users WHERE DisplayName \= @name;

Supposons un index sur `DisplayName`, colonne définie en `VARCHAR(40)`. Le paramètre est `NVARCHAR`. SQL Server ne compare pas un `VARCHAR` à un `NVARCHAR` directement : il convertit le type de plus faible précédence vers l'autre, donc la colonne `VARCHAR` vers `NVARCHAR`, pour chaque ligne. La colonne se retrouve à l'intérieur d'une fonction de conversion : le prédicat n'est plus SARGable, l'index sur `DisplayName` est scanné entièrement. Le plan affiche un avertissement `Implicit Conversion` sur l'opérateur d'accès. Il est fréquent qu'une application entière fonctionne ainsi sans que personne le sache, parce que les pilotes .NET et Java envoient les chaînes en `NVARCHAR` par défaut : la requête la plus exécutée de l'application coûte 10 000 fois ce qu'elle devrait. Le correctif est côté application (typer le paramètre) ou côté schéma (colonne en `NVARCHAR`). La conversion dans l'autre sens (paramètre `VARCHAR`, colonne `NVARCHAR`) ne pose pas ce problème : c'est le paramètre qui est converti, une fois.

Même mécanisme pour `INT` contre `VARCHAR` : `WHERE CodeClient = 12345` sur une colonne `VARCHAR` convertit chaque ligne en entier, et échoue en plus si une valeur n'est pas numérique.

### Ce qu'il faut pouvoir expliquer

- Ce que signifie SARGable et pourquoi une fonction sur la colonne empêche le seek.  
- Le mécanisme de la conversion implicite, dans quel sens elle est nocive, et pourquoi elle est si fréquente.

---

## Épisode 7\. Les jointures : deux piles à la fois

### Le matériel

Ajoutons la table `dbo.Posts` : 17 millions de lignes, clé cluster sur `Id`, et la colonne `OwnerUserId` qui référence `Users.Id`. Une pile de plusieurs centaines de milliers de feuilles.

SELECT u.DisplayName, p.Title

FROM dbo.Users u JOIN dbo.Posts p ON p.OwnerUserId \= u.Id

WHERE u.LastAccessDate \>= '2013-01-01';

Le moteur a trois façons de rapprocher deux piles, et il en choisit une selon les tailles estimées.

### Nested Loops : pour chaque ligne, chercher

Prendre les utilisateurs de 2013 dans la pile `IX_LastAccessDate` (quelques milliers). Pour chacun, chercher ses posts dans `Posts`. S'il existe un index sur `Posts (OwnerUserId)`, chaque recherche coûte 3 ou 4 lectures : 4 500 utilisateurs × 4 \= 18 000 lectures. Sans cet index, chaque recherche est un scan de toute la pile Posts : 4 500 scans de plusieurs centaines de milliers de feuilles, des milliards de lectures. Nested Loops est excellent quand le côté externe est petit et le côté interne indexé, et catastrophique dans tous les autres cas. Son coût est le produit du nombre de lignes externes par le coût d'une recherche interne : si l'estimation du côté externe dit 1 ligne et que la réalité est 2 millions, c'est le mécanisme de la quasi-totalité des plans qui "explosent".

### Hash Match : construire un répertoire

Lire entièrement la plus petite des deux entrées (les utilisateurs filtrés) et construire en mémoire un répertoire indexé par `Id` (la table de hachage, phase build). Puis lire l'autre entrée (Posts) en une seule passe et, pour chaque post, consulter le répertoire (phase probe). Coût : un scan de chaque côté, plus la mémoire du répertoire. C'est le choix par défaut dès que les deux côtés sont gros, et c'est un opérateur bloquant qui demande une memory grant : sous-estimé, le répertoire ne tient pas et déborde dans TempDB, avec des partitions écrites puis relues, parfois plusieurs fois (spill de niveau 2 ou 3).

### Merge Join : deux piles déjà triées

Si les deux entrées arrivent triées sur la clé de jointure (parce qu'un index les fournit dans cet ordre), il suffit de les parcourir en parallèle comme deux listes alphabétiques que l'on fusionne : une passe sur chaque, pas de mémoire, pas de boucle. C'est le plus économique quand les tris existent déjà, et le moteur ajoute des Sort devant s'ils n'existent pas, ce qui annule souvent l'intérêt.

### Ce que le choix révèle

Le type de jointure dans un plan est un indice sur ce que le moteur a estimé : un Nested Loops sur un côté externe qui produit en réalité des millions de lignes signale une estimation basse ; un Hash Match pour joindre 10 lignes signale une estimation haute. La correction n'est pas de forcer le type de jointure par un hint, mais de corriger l'estimation qui l'a produit. Depuis SQL 2017 en mode batch, l'Adaptive Join reporte le choix entre Nested Loops et Hash à l'exécution, quand le nombre réel de lignes du côté build est connu.

### Ce qu'il faut pouvoir expliquer

- Les trois algorithmes de jointure, leur coût et leur cas d'usage.  
- Pourquoi un Nested Loops peut être le meilleur ou le pire opérateur possible selon l'estimation.  
- Pourquoi un Hash Match a besoin de mémoire et ce qui se passe quand elle manque.  
- Pourquoi le type de jointure est un symptôme et non la cause.

---

## Épisode 8\. Trop d'index, page splits et fragmentation

### Le dilemme de l'index de plus

Chaque requête lente de l'application pourrait avoir son index couvrant. Après un an de ce régime, la table `Users` a 15 index. Chaque insertion écrit 16 feuilles dans 16 piles, chaque mise à jour de `Reputation` (qui change à chaque vote) touche les 6 piles qui la contiennent, et les 15 piles occupent trois fois plus de place que la table sur le bureau. La règle pratique de la formation : autour de 5 index par table et 5 colonnes par index comme point de départ, à dépasser en connaissance de cause, jamais par accumulation. La DMV `sys.dm_db_index_usage_stats` compte lectures et écritures par index depuis le dernier redémarrage : un index avec des millions d'écritures et zéro lecture est un candidat à la suppression (après vérification sur une période longue, les traitements mensuels existent).

Deux index qui commencent par les mêmes colonnes (`(LastAccessDate)` et `(LastAccessDate, DisplayName)`) sont redondants : le second sert toutes les requêtes du premier. Les index manquants suggérés par SQL Server sont proposés requête par requête, sans consolidation : dix suggestions sur la même table sont souvent un seul index à concevoir.

### Le page split

Une feuille de la pile 2 est pleine. Un utilisateur se connecte, sa `LastAccessDate` devient la plus récente, sa ligne doit être insérée tout en bas de la pile : la dernière feuille est pleine, SQL Server en ajoute une, c'est indolore. Mais si la clé de l'index était aléatoire (un `UNIQUEIDENTIFIER` généré par `NEWID()`), chaque insertion tomberait dans une feuille quelconque, pleine une fois sur deux : SQL Server doit alors allouer une nouvelle feuille, y déplacer la moitié des lignes, chaîner les deux feuilles et mettre à jour la table des matières. C'est le page split : plusieurs feuilles modifiées et journalisées pour une seule insertion.

Après des milliers de splits, la pile a deux défauts : les feuilles sont physiquement dans le désordre (fragmentation logique, qui gêne le read-ahead lors des scans, peu sur SSD), et surtout elles sont à moitié vides (fragmentation interne) : la pile occupe deux fois plus de place sur le bureau qu'elle ne devrait, donc deux fois moins de feuilles utiles tiennent en mémoire.

Le fill factor laisse volontairement de la place libre dans chaque feuille à la reconstruction de l'index, pour absorber les insertions aléatoires sans split. Sur une clé croissante il ne sert à rien : les insertions ne vont jamais dans les feuilles existantes, et l'espace réservé est du gaspillage de mémoire.

À l'inverse, une clé croissante sous très forte concurrence d'insertion crée une file d'attente sur la dernière feuille : toutes les sessions veulent écrire au même endroit et se disputent son verrou physique (`PAGELATCH_EX`, la hot page). SQL 2019 introduit `OPTIMIZE_FOR_SEQUENTIAL_KEY` pour ordonner cette file.

### Reconstruire ou pas

Reconstruire un index recrée la pile à neuf, triée, pleine au fill factor, et recalcule ses statistiques avec un échantillon complet. Le réorganiser remet les feuilles dans l'ordre et les compacte, en ligne, sans toucher aux statistiques. La règle historique (réorganiser entre 5 et 30 % de fragmentation, reconstruire au-dessus) date de 2008 et des disques mécaniques. Sur une base volumineuse, un rebuild nocturne de tout ce qui dépasse 30 % génère des téraoctets de journal, retarde les secondaires Always On, et invalide tous les plans en cache (par la mise à jour des statistiques). Ce qui améliore réellement les plans, c'est la mise à jour des statistiques ; la reconstruction n'est rentable que sur les index volumineux dont les feuilles sont très peu remplies, rarement, hors heures ouvrées, en ligne et de manière reprenable.

### Ce qu'il faut pouvoir expliquer

- Pourquoi chaque index a un coût permanent et comment décider d'en supprimer.  
- Le mécanisme du page split et ses deux conséquences.  
- Pourquoi le fill factor est inutile sur une clé croissante, et le problème inverse de la hot page.  
- Pourquoi le rebuild systématique est une mauvaise habitude et ce qui compte vraiment.

---

## Épisode 9\. Édition Big Data : la pile fait un milliard de lignes

La formation d'origine propose une édition Big Data qui reprend les mêmes idées sur des volumes où les goulets d'étranglement changent. Reprenons `Users` en imaginant 1 milliard de lignes.

### Les ordres de grandeur

À 30 lignes par feuille, la pile 1 fait 33 millions de feuilles, soit 260 Go. Chaque index non-cluster étroit fait 2,5 millions de feuilles (20 Go). L'arbre de la pile 1 a 4 niveaux : chercher un utilisateur coûte toujours 4 lectures. Mais scanner la table coûte 33 millions de lectures, et si le bureau fait 128 Go, la table n'y tient pas : un scan est une lecture physique de bout en bout, à la vitesse du stockage, et il évince tout ce que les autres requêtes utilisaient. Un seul rapport mal indexé lancé à 9h vide le bureau pour tout le monde, et les dix minutes suivantes sont un festival de `PAGEIOLATCH`.

La largeur de ligne devient un sujet majeur : passer de 250 à 125 octets par ligne (types mieux dimensionnés, colonnes rarement lues déplacées ailleurs) divise par deux le nombre de feuilles, donc les lectures, la mémoire nécessaire, la durée des sauvegardes et des scans. Un `NCHAR(200)` pour stocker un code de 3 caractères, un `DATETIME` là où `DATE` suffit, un `BIGINT` pour un compteur qui ne dépassera jamais 100 000 : autant de feuilles supplémentaires payées à chaque lecture.

### Comment le moteur se partage les processeurs

Sous le moteur relationnel et le moteur de stockage, SQLOS ordonnance lui-même le travail. Chaque cœur logique a un ordonnanceur ; un seul travail s'exécute dessus à la fois. Une tâche (une requête, ou une branche d'une requête parallèle) est toujours dans l'un de trois états :

- RUNNING : elle utilise le cœur ;  
- SUSPENDED : elle attend quelque chose (une feuille depuis le disque, un verrou, une allocation mémoire) ; le type d'attente enregistré est celui des `PAGEIOLATCH`, `LCK_M_*`, `RESOURCE_SEMAPHORE` ;  
- RUNNABLE : ce qu'elle attendait est arrivé, elle attend son tour sur le cœur. Le temps passé dans cet état est le signal wait time.

L'ordonnancement est coopératif : une tâche rend le cœur après 4 ms (`SOS_SCHEDULER_YIELD`) ou dès qu'elle doit attendre. Les wait stats cumulent le temps passé en SUSPENDED par type d'attente : elles disent de quoi l'instance manque (IO, mémoire, verrous, CPU si le signal wait time est élevé). C'est pour cela qu'un diagnostic commence par elles et non par une requête désignée coupable.

Quand toutes les tâches disponibles (les workers, quelques centaines) sont occupées, par exemple parce que 500 sessions attendent un verrou tenu par une transaction oubliée, les nouvelles connexions ne peuvent même plus démarrer : `THREADPOOL`, l'instance semble figée. Une connexion d'administration dédiée (DAC) réserve un ordonnanceur pour que le DBA puisse intervenir.

### Écrire : le journal d'abord

Modifier une ligne ne modifie pas la feuille sur le disque. Le moteur charge la feuille sur le bureau, la modifie là, la marque comme sale, et écrit dans le journal de transactions une description de la modification, avec un numéro de séquence croissant (LSN). Au `COMMIT`, seul le journal est écrit sur disque, de manière synchrone (`WRITELOG`) : la transaction est durable dès que le journal l'est. La feuille sale sera écrite plus tard, par le checkpoint (toutes les 60 secondes environ) ou par le lazy writer quand il faut libérer de la place sur le bureau. Une feuille modifiée mille fois entre deux checkpoints n'est écrite qu'une fois. C'est le principe du Write-Ahead Logging : les écritures de données sont presque gratuites, le journal est le point critique de latence en écriture.

Trois conséquences pratiques :

- mille `INSERT` d'une ligne en autocommit font mille écritures synchrones du journal ; un `INSERT` de mille lignes en fait une. Le traitement par lots de quelques milliers de lignes est le compromis entre débit du journal et verrous (épisode 14\) ;  
- le journal est découpé en fichiers virtuels (VLF) réutilisés circulairement dès qu'ils ne contiennent plus rien d'utile (transaction ouverte, feuille sale, sauvegarde de journal non faite, secondaire Always On en retard). Un journal qui grossit sans fin a toujours l'une de ces causes, visible dans `log_reuse_wait_desc` ; le réduire ne sert à rien tant qu'elle est là. Un journal qui a grossi par petits incréments contient des milliers de VLF, ce qui ralentit la récupération, la restauration et les sauvegardes ;  
- au redémarrage, le moteur rejoue le journal (redo des transactions validées non écrites, undo des transactions ouvertes). Un `UPDATE` de 200 millions de lignes interrompu à 90 % met à peu près autant de temps à s'annuler qu'il en avait mis à s'exécuter.

### TempDB : les toilettes publiques

TempDB est la base d'appoint que tout le monde partage : les tris et hachages qui débordent, les tables temporaires, les variables table, le version store (épisode 14), les tris de création d'index. Sur une base volumineuse elle travaille en permanence. Deux problèmes classiques :

- la contention d'allocation : quand des centaines de sessions créent des objets temporaires en même temps, elles modifient toutes les mêmes quelques pages spéciales qui tiennent le registre de l'espace libre (PFS, GAM, SGAM), en début de fichier ; ajouter des fichiers de données à TempDB (jusqu'à 8, de taille égale) multiplie ces pages et répartit la contention. SQL 2022 supprime une partie du problème ;  
- les spills : chaque tri ou hachage sous-estimé s'y déverse. TempDB doit être sur le stockage le plus rapide disponible et pré-dimensionnée pour ne jamais grossir en journée.

### Ce qu'il faut pouvoir expliquer

- Comment le nombre de feuilles se déduit de la largeur de ligne et pourquoi le typage est un sujet de performance.  
- Pourquoi un scan de grosse table pénalise tout le monde pendant plusieurs minutes.  
- Les trois états d'une tâche, ce que mesurent les wait stats et le signal wait time.  
- Le Write-Ahead Logging : pourquoi écrire est rapide et commiter peut être lent.  
- Pourquoi un journal grossit, et pourquoi une annulation est aussi longue que l'exécution.  
- Ce qui passe par TempDB et pourquoi on lui donne plusieurs fichiers.

---

## Épisode 10\. Le partitionnement : plusieurs piles pour une seule table

### L'idée

Découpons la pile `Users` (ou plutôt une table de faits `Events` chargée par dates) en piles mensuelles : une pile pour janvier 2024, une pour février, etc. Chaque pile est un arbre B+ complet, avec sa racine, sa table des matières et ses feuilles, rangée dans son propre classeur (groupe de fichiers), éventuellement avec sa propre compression. La "table" n'est plus qu'une étiquette : une fonction de partition (les bornes de dates) et un schéma (quelle pile va dans quel classeur). Un index aligné est partitionné de la même façon : lui aussi devient N piles.

Tout le comportement du partitionnement découle du fait qu'il s'agit de N arbres indépendants.

### Ce que cela permet

Retirer janvier 2024 de la table : `SWITCH` déplace l'étiquette de la pile de janvier vers une autre table de structure identique. Aucune feuille n'est lue ni écrite, quelques millisecondes pour 30 millions de lignes, là où un `DELETE` aurait pris des heures, saturé le journal et tenu des verrous tout ce temps. Charger un mois : construire la pile dans une table de staging, puis `SWITCH` dans la partition vide correspondante. Reconstruire un index : par pile, seulement les piles actives. Compresser : les piles anciennes fortement, la pile courante peu. Mettre à jour les statistiques : par pile (`INCREMENTAL`), en ne relisant que celles qui ont changé.

Le `SWITCH` exige que les deux structures soient strictement identiques (colonnes, index, compression, classeur) et qu'une contrainte garantisse que les données correspondent à la plage cible : SQL Server doit pouvoir accepter la pile sans la lire. Il prend un verrou de schéma très bref, mais doit l'obtenir : il attend la fin des requêtes en cours, et bloque celles qui arrivent derrière (d'où `WAIT_AT_LOW_PRIORITY`).

### Ce qui peut mal tourner

Ajouter une borne (`SPLIT`) scinde une pile en deux : si elle est vide, c'est une étiquette ; si elle contient 30 millions de lignes, SQL Server relit chaque ligne, la recopie dans la bonne nouvelle pile, journalise tout, sous verrou exclusif : un incident de production. Idem pour `MERGE`. D'où la règle absolue : garder des piles vides aux deux extrémités et scinder toujours des piles vides, plusieurs mois d'avance, par un job automatique.

### Ce que cela n'apporte pas

Chercher `WHERE EventId = 123456789` sans préciser la date : le moteur ne sait pas dans quelle pile mensuelle est cet événement, il doit descendre la table des matières de chacune des 100 piles : 100 seeks au lieu d'un seul (qui n'aurait eu qu'un niveau de plus). Le partitionnement ne remplace pas un index ; il ralentit les requêtes qui ne filtrent pas sur la colonne de partition. Il ne les accélère vraiment que par l'élimination de partitions : quand la requête filtre sur la date, le moteur ne consulte que les piles concernées, à condition que le prédicat soit SARGable et du type exact de la colonne (un paramètre `DATETIME` contre une colonne `DATETIME2` empêche le calcul de la partition à la compilation). L'élimination est statique quand la valeur est connue à la compilation, dynamique (décidée pendant l'exécution) quand elle vient d'une variable ou d'une jointure.

Autre effet de bord : chaque pile est triée indépendamment. Un `TOP 10 ... ORDER BY` sur une autre colonne, ou un `MIN` / `MAX` sans filtre de date, doit lire un morceau de chaque pile puis fusionner : des requêtes triviales sur la table non partitionnée deviennent visiblement plus lentes. Il faut les repérer (Query Store) et les borner sur la date.

Le partitionnement est donc un outil de gestion du cycle de vie des données à grande échelle, presque toujours pertinent à un milliard de lignes ; comme outil d'accélération des requêtes, c'est presque toujours une déception.

### Ce qu'il faut pouvoir expliquer

- Pourquoi une table partitionnée est N arbres et tout ce qui en découle.  
- Pourquoi `SWITCH` est instantané et ce qu'il exige.  
- Pourquoi `SPLIT` sur une pile pleine est un incident et la règle des piles tampons.  
- Élimination statique et dynamique, et ce qui l'empêche.  
- Pourquoi partitionner peut ralentir des requêtes et lesquelles.

---

## Épisode 11\. Le columnstore : découper les feuilles en colonnes

### L'idée

Pour calculer `SUM(Amount)` sur 100 millions de lignes de 40 colonnes, le rowstore oblige à lire toutes les feuilles, donc les 39 colonnes inutiles : 50 Go lus pour 800 Mo d'information utile. Le columnstore découpe la table autrement : par paquets de 1 048 576 lignes (les rowgroups), et dans chaque paquet, chaque colonne est stockée séparément dans un segment. Pour `SUM(Amount)`, on lit seulement les 100 segments de la colonne Amount.

Un segment est une suite de valeurs de même type, souvent proches ou répétitives, et cela se compresse extraordinairement bien : dictionnaire pour les valeurs répétées (une colonne `Pays` devient une suite de petits entiers), soustraction d'une base commune pour les numériques, stockage sur le nombre minimal de bits, et run-length encoding pour les suites de valeurs identiques consécutives. Un facteur 7 à 10 par rapport au rowstore non compressé est courant. Et beaucoup d'opérations (compter, comparer) se font sur les valeurs encodées, sans les décompresser.

Chaque segment enregistre sa valeur minimale et maximale : `WHERE EventDate >= '2024-06-01'` saute d'un coup tous les rowgroups dont le maximum est antérieur. C'est l'élimination de segments, équivalent de l'élimination de partition à grain d'un million de lignes, qui ne fonctionne que si les données ont été chargées dans l'ordre de la colonne filtrée (sinon chaque segment couvre toute la plage). L'ordre de chargement, ou l'option `ORDER` de SQL 2022, est le premier paramètre de conception d'un columnstore ; le partitionnement par date en est le complément naturel.

Le columnstore vient avec le mode batch : au lieu de faire passer les lignes une à une entre les opérateurs du plan (mode ligne, un appel par ligne), le moteur traite des lots de 900 valeurs par colonne avec des boucles serrées. Le CPU des agrégations et jointures est divisé par 3 à 10\. Depuis SQL 2019, le mode batch s'applique aussi au rowstore sur les gros volumes, mais c'est avec le columnstore qu'il donne les gains spectaculaires : un rapport de 10 minutes qui passe à 5 secondes n'est pas une exagération, à condition que la requête soit du type agrégation sur beaucoup de lignes et peu de colonnes.

### Le prix : les écritures

On ne peut pas ajouter une valeur à un segment compressé ; il faut connaître toutes les valeurs pour compresser. Les modifications passent donc par une structure d'à-côté :

- un chargement d'au moins 102 400 lignes en une instruction est compressé directement en rowgroups ;  
- une insertion plus petite va dans un delta rowgroup : une pile rowstore ordinaire, non compressée, lue en mode ligne, sans élimination. Quand elle atteint le million de lignes, un processus d'arrière-plan (tuple mover) la compresse ;  
- un `DELETE` ne supprime rien : il coche la ligne dans un bitmap de suppression ; la ligne reste dans le segment, lue puis écartée à chaque requête, jusqu'à une réorganisation ;  
- un `UPDATE` est un `DELETE` coché plus un `INSERT` dans le delta.

Une table alimentée ligne à ligne accumule des delta rowgroups et des lignes cochées, et ses rapports se dégradent au fil des semaines. Le columnstore cluster convient aux tables de faits chargées par lots ; pour une table OLTP, la réponse est un columnstore non-cluster filtré (indexer seulement les lignes stabilisées, par exemple les commandes clôturées), qui coexiste avec les piles B+ de la table.

Et chercher une ligne par clé dans un columnstore est mauvais : pas de table des matières, il faut lire le segment de la clé de chaque rowgroup candidat. Depuis SQL 2016, des index B+ non-cluster peuvent être ajoutés sur une table columnstore pour ces accès ponctuels.

### Ce qu'il faut pouvoir expliquer

- Pourquoi une agrégation sur peu de colonnes est massivement plus rapide en columnstore.  
- Les encodages et pourquoi l'ordre des données change tout.  
- L'élimination de segments et sa relation avec le partitionnement.  
- Le delta store, le bitmap de suppression, et pourquoi les petites écritures dégradent le columnstore.  
- Pourquoi le mode batch et le columnstore vont ensemble.

---

## Épisode 12\. Le Query Store : le carnet de bord

### Ce que le cache de plans ne peut pas faire

Le moteur garde les plans compilés en mémoire pour ne pas recompiler. Mais ce cache oublie : un plan évincé par manque de mémoire, un redémarrage, un basculement, et l'historique disparaît ; il ne garde qu'un plan à la fois par requête ; il n'a aucune notion de temps. "Pourquoi cette requête est lente depuis hier ?" est sans réponse : le plan d'hier n'existe plus.

### Le carnet

Le Query Store (SQL 2016+) est un carnet de bord persistant, rangé dans la base elle-même (donc sauvegardé et restauré avec elle), qui note trois choses :

1. Pour chaque requête (identifiée par son texte normalisé et son contexte de compilation), tous les plans successifs qui ont été compilés, avec leur XML. Une requête qui a eu trois plans a trois `plan_id` ; c'est ce qui rend une régression visible.  
2. Pour chaque plan et chaque intervalle de temps (15 ou 60 minutes), des agrégats : nombre d'exécutions, durée, CPU, lectures, écritures, mémoire réservée, degré de parallélisme, avec moyenne, minimum, maximum et écart-type. Des agrégats, pas des exécutions individuelles : on sait qu'un plan a tourné 400 fois entre 9h et 9h15 avec un maximum de 40 secondes, pas laquelle des 400\.  
3. Pour chaque plan et intervalle, le temps d'attente par catégorie (CPU, verrous, IO, mémoire...). C'est la seule façon d'attribuer a posteriori les attentes globales à une requête précise.

La capture se fait en mémoire au fil des exécutions (1 à 3 % de CPU), et le carnet est écrit sur disque toutes les quelques minutes.

### Ce qu'on en fait

Comparer une requête avant et après un changement (index, statistiques, montée de version, niveau de compatibilité). Voir le moment où le plan a changé et à quoi il a été recompilé. Attribuer les `PAGEIOLATCH` ou les `LCK_M_S` observés globalement à leurs requêtes. Et, en urgence, forcer un plan : dire au moteur "pour cette requête, utilise le plan numéro 3". Le forçage ne rejoue pas le plan tel quel : à la compilation, l'optimiseur reçoit le plan comme consigne et tente de produire l'équivalent ; si c'est devenu impossible (un index du plan a été supprimé), le forçage échoue silencieusement, la requête est compilée normalement et l'échec est compté (`force_failure_count`). Le forçage stabilise ; il ne corrige pas la cause (statistiques, sniffing, index) et chaque plan forcé doit être documenté et revu.

Deux réglages à surveiller : le mode de capture (capturer toutes les requêtes sur une application qui envoie du SQL non paramétré remplit le carnet de millions d'entrées inutiles) et la taille maximale, au-delà de laquelle le carnet passe en lecture seule sans erreur visible et cesse de noter.

Depuis SQL 2022, le Query Store sert aussi de mémoire aux mécanismes adaptatifs (correction des memory grants, du degré de parallélisme, des hypothèses d'estimation), et permet d'appliquer un hint à une requête sans toucher au code de l'application (Query Store hints), ce qui est décisif quand l'application est un progiciel.

### Ce qu'il faut pouvoir expliquer

- Ce que le cache de plans ne permet pas et ce que le Query Store ajoute.  
- Les trois types d'informations notées et leur granularité.  
- Comment fonctionne réellement le forçage et pourquoi c'est un pansement.  
- Les deux réglages qui, mal surveillés, rendent le carnet inutile.

---

## Épisode 13\. La compression rowstore : des feuilles plus denses

Revenons à la pile 1 et à ses 30 lignes par feuille. Deux techniques pour en mettre davantage.

La compression de ligne (row) remplace le stockage à longueur fixe par un stockage à longueur réelle : un `INT` valant 12 tient sur 1 octet au lieu de 4, un `CHAR(50)` contenant "Niort" sur 5, un `BIGINT` à zéro sur rien. Aucun calcul : le coût CPU est à peine mesurable, le gain dépend du schéma (40 % sur une table de gros types mal dimensionnés, 5 % sur des `VARCHAR` bien taillés).

La compression de page ajoute, feuille par feuille, deux mécanismes : pour chaque colonne, le préfixe commun aux valeurs de la feuille est stocké une fois en haut de la feuille et chaque ligne ne garde que la différence (`2024-06-1` pour des dates du même mois, `FR-79` pour des codes) ; et les valeurs répétées dans la feuille, toutes colonnes confondues, sont stockées une fois dans un dictionnaire de feuille. Le gain (souvent 40 à 70 %) dépend de la redondance à l'intérieur de chaque feuille, donc de l'ordre des données : une pile cluster sur une date, dont chaque feuille contient des lignes du même jour et souvent du même client, se compresse bien mieux qu'une pile cluster sur un identifiant aléatoire. Quelques pourcents de CPU en lecture, davantage en écriture dans les feuilles denses.

Pourquoi c'est une question de performance et pas de disque : les feuilles restent compressées sur le bureau. Une pile de 800 Go compressée à 300 Go, c'est 2,7 fois plus de lignes en mémoire à RAM égale, 2,7 fois moins de lectures physiques pour un scan, des sauvegardes plus courtes. Sur une instance qui manque d'IO ou de mémoire, l'échange est presque toujours gagnant ; sur une instance saturée en CPU dont les données tiennent déjà en mémoire, il est perdant. La compression se choisit par pile et par partition : page sur les partitions froides, row ou rien sur la partition qui reçoit les insertions.

### Ce qu'il faut pouvoir expliquer

- Ce que font la compression de ligne et la compression de page, et pourquoi l'ordre des données influence la seconde.  
- Pourquoi la compression améliore les performances et dans quel cas elle les dégrade.

---

## Épisode 14\. Plusieurs lecteurs sur les mêmes feuilles : verrous et isolation

### Latch et verrou

Deux mécanismes protègent les feuilles, et ils n'ont rien à voir :

- le latch protège la feuille physique, en mémoire, pendant les quelques microsecondes où le moteur la lit ou la modifie. Il ne dépend pas des transactions. Les attentes `PAGELATCH` (feuille sur le bureau) et `PAGEIOLATCH` (feuille en cours de lecture depuis l'armoire) sont des latches. On ne les configure pas ; on les réduit en changeant la structure (fichiers TempDB, `OPTIMIZE_FOR_SEQUENTIAL_KEY`) ou la charge ;  
- le verrou (lock) protège la cohérence logique des données pendant toute une transaction. Les attentes `LCK_M_*` sont des verrous, et leur comportement dépend du niveau d'isolation.

### Le modèle par défaut

En `READ COMMITTED`, le niveau par défaut, un lecteur pose un verrou partagé (S) sur la ligne le temps de la lire ; un écrivain pose un verrou exclusif (X) qu'il garde jusqu'à la fin de sa transaction. Un lecteur qui tombe sur une ligne verrouillée en X attend. Un écrivain qui veut modifier une ligne en cours de lecture attend. Sur une base OLTP où des rapports scannent des millions de lignes pendant que des transactions écrivent, c'est la source principale des attentes `LCK_M_*` et des deadlocks.

Les verrous se posent à plusieurs niveaux (ligne, feuille, pile, table), avec des verrous d'intention aux niveaux supérieurs pour qu'une session qui veut verrouiller toute la table sache immédiatement qu'une ligne est prise en dessous. Et toute requête pose un verrou de schéma (Sch-S) qui empêche de modifier la table pendant son exécution ; un `ALTER TABLE` a besoin de l'inverse (Sch-M), attend la fin des requêtes en cours, et bloque toutes celles qui arrivent derrière lui pendant qu'il attend : un `ALTER` d'une milliseconde peut figer la production une minute.

Quand une instruction dépasse environ 5 000 verrous sur une même pile, le moteur les remplace par un seul verrou de table : l'escalade. Économique pour elle, catastrophique pour les autres, bloquées sur des lignes qu'elles ne touchent pas. Sur une table partitionnée, `LOCK_ESCALATION = AUTO` limite l'escalade à la pile concernée. La réponse structurelle est le traitement par lots sous le seuil.

### Le versionnement : lire le passé plutôt qu'attendre

`READ COMMITTED SNAPSHOT` (RCSI) change la règle : quand un écrivain modifie une ligne, l'ancienne version est copiée dans le version store (TempDB), et la ligne garde un pointeur de 14 octets vers elle. Un lecteur qui rencontre une ligne en cours de modification ne pose aucun verrou et n'attend pas : il lit la dernière version validée. Lecteurs et écrivains ne se bloquent plus ; les écrivains continuent de se bloquer entre eux. C'est le comportement par défaut de la plupart des autres SGBD et d'Azure SQL Database, et le changement au meilleur rapport gain / risque sur une base OLTP qui souffre de blocages.

Deux risques à auditer avant de l'activer : le version store ne peut être nettoyé que jusqu'à la plus ancienne instruction (RCSI) ou transaction (`SNAPSHOT`) en cours, et une transaction ouverte deux heures fait grossir TempDB de toutes les versions produites pendant ce temps ; et une lecture peut voir une valeur validée mais déjà périmée, ce qui casse le schéma "vérifier puis écrire" (`IF NOT EXISTS ... INSERT`, réservation de stock, file d'attente en table) : deux sessions lisent la même chose et écrivent toutes deux. Le hint `UPDLOCK` sur ces lectures précises rétablit le blocage.

`NOLOCK`, souvent utilisé comme "optimisation", n'est pas du versionnement : il lit les feuilles sans verrou, donc y compris des lignes non validées qui seront annulées, et peut lire deux fois ou manquer des lignes déplacées par un page split en cours. Il n'a sa place que sur des données dont l'inexactitude est acceptable.

### Deadlocks

Deux sessions qui attendent chacune un verrou tenu par l'autre. Un thread de surveillance vérifie toutes les 5 secondes, choisit une victime et l'annule (erreur 1205). Ce n'est pas un problème de serveur : c'est deux traitements qui accèdent aux mêmes tables dans un ordre différent, ou des verrous plus larges que nécessaire parce qu'un index manque et qu'un scan verrouille des lignes qu'il ne devait pas toucher. Le graphe de deadlock, capturé automatiquement, désigne presque toujours la solution.

### Ce qu'il faut pouvoir expliquer

- La différence entre un latch et un verrou.  
- Pourquoi un `ALTER` court peut bloquer la production, et le mécanisme de l'escalade.  
- Ce que change le versionnement, et les deux risques qu'il introduit.  
- Pourquoi `NOLOCK` n'est pas une optimisation.  
- Pourquoi un deadlock est un problème d'application.

---

## Épisode 15\. Synthèse : les chaînes de causalité

Pour terminer, les enchaînements qui reviennent le plus souvent en production, à connaître par cœur parce qu'ils relient tous les épisodes :

**Statistiques périmées → plan catastrophique.** Chargement de masse → compteur de modifications sous le seuil → histogramme sans les nouvelles valeurs → estimation 1 ligne → Nested Loops \+ Key Lookup → millions d'exécutions du côté interne → CPU saturé et `SOS_SCHEDULER_YIELD`. Remède : mise à jour des statistiques (le plan est invalidé et recompilé).

**Sous-estimation → spill → TempDB.** Estimation trop basse → memory grant trop petite → Sort ou Hash déborde → écriture et relecture dans TempDB → `PAGEIOLATCH` sur TempDB et contention d'allocation pour toutes les sessions. Remède : corriger l'estimation, ou memory grant feedback en attendant.

**Surestimation → attente mémoire.** Estimation trop haute (variable locale, `SELECT *` avec colonnes `MAX`) → memory grant énorme → 25 % du pool par requête → quatre rapports en parallèle et le cinquième attend `RESOURCE_SEMAPHORE` → feuilles évincées du bureau → `PAGEIOLATCH` partout ensuite.

**Index non couvrant → scan.** Requête retournant 2 % des lignes → Key Lookup estimé au-dessus du tipping point → scan → 200 Go lus → PLE effondrée → tout le monde ralentit dix minutes. Remède : colonnes en `INCLUDE`.

**Conversion implicite → scan.** Paramètre `NVARCHAR` de l'ORM contre colonne `VARCHAR` → prédicat non SARGable → scan au lieu du seek → CPU et lectures multipliés par 10 000 sur la requête la plus fréquente de l'application. Remède côté application ou par type de colonne.

**Transaction longue → blocage → THREADPOOL.** Transaction ouverte (application qui attend une saisie, lot sans commit intermédiaire) → verrou X conservé → lecteurs en `LCK_M_S` (sans RCSI) → escalade éventuelle → centaines de sessions en attente → workers épuisés → instance injoignable. Remède : RCSI pour les lecteurs, lots courts pour les écrivains, DAC pour intervenir.

**Petites insertions → columnstore dégradé.** Insertions ligne à ligne → delta rowgroups ouverts → lectures en mode ligne sans élimination → rapports de plus en plus lents → suppressions accumulées → segments lus pour rien. Remède : chargement par lots, réorganisation planifiée, columnstore non-cluster filtré.

**SPLIT tardif → incident.** Job de création de partitions oublié → la pile tampon reçoit un mois de données → `SPLIT` recopie 30 millions de lignes sous verrou exclusif → application bloquée une heure, journal saturé. Remède : toujours scinder des piles vides, plusieurs mois d'avance.

**Croissance en petits pas → VLF → récupération lente.** Autogrowth par défaut → milliers de VLF → sauvegardes de journal, restauration et basculement ralentis → le RTO promis n'est plus tenu.

---

# Partie 2 : la pratique

---

## 1\. Le lab d'entraînement

### Objectif

Disposer d'une instance et d'une base volumineuse sur laquelle casser des choses sans risque. Tout le reste du cours s'appuie dessus.

### Installation

- SQL Server 2022 Developer Edition (gratuit, fonctionnellement identique à Enterprise, interdit en production).  
- SQL Server Management Studio (SSMS) 20 ou plus récent, et SentryOne Plan Explorer (gratuit) pour la lecture des plans.  
- Base StackOverflow de Brent Ozar. Trois tailles existent : StackOverflow2010 (environ 10 Go), StackOverflow2013 (environ 50 Go) et la complète (plus de 300 Go). La 2013 est le bon compromis : la table Posts dépasse 17 millions de lignes, Votes en compte près de 53 millions, Comments près de 25 millions. Pour simuler un milliard de lignes, une table de démonstration sera générée au chapitre 7\.

Après restauration, passer la base en niveau de compatibilité courant et activer le Query Store :

ALTER DATABASE StackOverflow2013 SET COMPATIBILITY\_LEVEL \= 160;   \-- 150 pour SQL 2019

ALTER DATABASE StackOverflow2013 SET QUERY\_STORE \= ON;

ALTER DATABASE StackOverflow2013 SET QUERY\_STORE (

    OPERATION\_MODE \= READ\_WRITE,

    QUERY\_CAPTURE\_MODE \= AUTO,

    MAX\_STORAGE\_SIZE\_MB \= 2048,

    INTERVAL\_LENGTH\_MINUTES \= 15

);

### Scripts communautaires à installer

Ces scripts sont le quotidien de tout DBA SQL Server orienté performance. Les installer dans une base d'administration dédiée (par exemple `DBA`), jamais dans `master` ni dans la base applicative.

| Script | Auteur | Usage |
| :---- | :---- | :---- |
| First Responder Kit (sp\_Blitz, sp\_BlitzFirst, sp\_BlitzCache, sp\_BlitzIndex, sp\_BlitzLock, sp\_BlitzWho) | Brent Ozar Unlimited | Audit de l'instance, du cache de plans, des index, des deadlocks |
| sp\_WhoIsActive | Adam Machanic | Ce qui tourne maintenant, avec attentes, verrous, plan |
| Diagnostic Information Queries | Glenn Berry | Une centaine de requêtes DMV commentées, par version |
| Scripts de maintenance | Ola Hallengren | Sauvegardes, intégrité, maintenance des index et statistiques |
| sp\_PressureDetector, sp\_HumanEvents | Erik Darling | Pression CPU / mémoire, capture d'événements étendus simplifiée |

\-- Vérifier que tout est en place

EXEC DBA.dbo.sp\_Blitz @CheckServerInfo \= 1;

EXEC DBA.dbo.sp\_WhoIsActive;

### Générer de la charge

Pour observer quelque chose dans les DMV et le Query Store, il faut une activité. SQLQueryStress (gratuit, GitHub) rejoue une requête en parallèle sur N threads avec des paramètres tirés d'une table. C'est l'outil de référence pour reproduire du parameter sniffing ou de la contention.

---

## 2\. Méthodologie de diagnostic : par où commencer

### Concept

Un problème de performance se diagnostique du général au particulier. L'erreur classique est de partir d'une requête que quelqu'un a désignée comme coupable. La méthode inverse est plus fiable :

1. Sur quoi l'instance passe-t-elle son temps ? (wait stats)  
2. Quelles requêtes consomment le plus de la ressource identifiée ? (cache de plans, Query Store)  
3. Pourquoi ces requêtes consomment-elles autant ? (plan d'exécution)  
4. Quel levier corrige la cause : index, statistiques, réécriture, configuration ?

### Les wait stats : le point de départ

Chaque fois qu'une requête ne s'exécute pas sur un processeur, SQL Server enregistre pourquoi elle attend. Les compteurs cumulés depuis le dernier redémarrage sont dans `sys.dm_os_wait_stats`. Ils disent ce dont l'instance manque : CPU, IO, mémoire, verrous.

\-- Wait stats cumulées, sans les attentes bénignes (threads système, timers)

WITH waits AS (

    SELECT wait\_type,

           wait\_time\_ms / 1000.0 AS wait\_time\_s,

           (wait\_time\_ms \- signal\_wait\_time\_ms) / 1000.0 AS resource\_s,

           signal\_wait\_time\_ms / 1000.0 AS signal\_s,

           waiting\_tasks\_count,

           100.0 \* wait\_time\_ms / SUM(wait\_time\_ms) OVER () AS pct

    FROM sys.dm\_os\_wait\_stats

    WHERE wait\_type NOT IN (

        'BROKER\_EVENTHANDLER','BROKER\_RECEIVE\_WAITFOR','BROKER\_TASK\_STOP','BROKER\_TO\_FLUSH',

        'BROKER\_TRANSMITTER','CHECKPOINT\_QUEUE','CHKPT','CLR\_AUTO\_EVENT','CLR\_MANUAL\_EVENT',

        'CLR\_SEMAPHORE','DBMIRROR\_DBM\_EVENT','DBMIRROR\_EVENTS\_QUEUE','DBMIRROR\_WORKER\_QUEUE',

        'DBMIRRORING\_CMD','DIRTY\_PAGE\_POLL','DISPATCHER\_QUEUE\_SEMAPHORE','EXECSYNC',

        'FSAGENT','FT\_IFTS\_SCHEDULER\_IDLE\_WAIT','FT\_IFTSHC\_MUTEX','HADR\_CLUSAPI\_CALL',

        'HADR\_FILESTREAM\_IOMGR\_IOCOMPLETION','HADR\_LOGCAPTURE\_WAIT','HADR\_NOTIFICATION\_DEQUEUE',

        'HADR\_TIMER\_TASK','HADR\_WORK\_QUEUE','KSOURCE\_WAKEUP','LAZYWRITER\_SLEEP','LOGMGR\_QUEUE',

        'MEMORY\_ALLOCATION\_EXT','ONDEMAND\_TASK\_QUEUE','PARALLEL\_REDO\_DRAIN\_WORKER',

        'PARALLEL\_REDO\_LOG\_CACHE','PARALLEL\_REDO\_TRAN\_LIST','PARALLEL\_REDO\_WORKER\_SYNC',

        'PARALLEL\_REDO\_WORKER\_WAIT\_WORK','PREEMPTIVE\_OS\_FLUSHFILEBUFFERS','PREEMPTIVE\_XE\_GETTARGETSTATE',

        'PWAIT\_ALL\_COMPONENTS\_INITIALIZED','PWAIT\_DIRECTLOGCONSUMER\_GETNEXT','PWAIT\_EXTENSIBILITY\_CLEANUP\_TASK',

        'QDS\_PERSIST\_TASK\_MAIN\_LOOP\_SLEEP','QDS\_ASYNC\_QUEUE','QDS\_CLEANUP\_STALE\_QUERIES\_TASK\_MAIN\_LOOP\_SLEEP',

        'QDS\_SHUTDOWN\_QUEUE','REDO\_THREAD\_PENDING\_WORK','REQUEST\_FOR\_DEADLOCK\_SEARCH','RESOURCE\_QUEUE',

        'SERVER\_IDLE\_CHECK','SLEEP\_BPOOL\_FLUSH','SLEEP\_DBSTARTUP','SLEEP\_DCOMSTARTUP','SLEEP\_MASTERDBREADY',

        'SLEEP\_MASTERMDREADY','SLEEP\_MASTERUPGRADED','SLEEP\_MSDBSTARTUP','SLEEP\_SYSTEMTASK','SLEEP\_TASK',

        'SLEEP\_TEMPDBSTARTUP','SNI\_HTTP\_ACCEPT','SOS\_WORK\_DISPATCHER','SP\_SERVER\_DIAGNOSTICS\_SLEEP',

        'SQLTRACE\_BUFFER\_FLUSH','SQLTRACE\_INCREMENTAL\_FLUSH\_SLEEP','SQLTRACE\_WAIT\_ENTRIES','VDI\_CLIENT\_OTHER',

        'WAIT\_FOR\_RESULTS','WAITFOR','WAITFOR\_TASKSHUTDOWN','WAIT\_XTP\_RECOVERY','WAIT\_XTP\_HOST\_WAIT',

        'WAIT\_XTP\_OFFLINE\_CKPT\_NEW\_LOG','WAIT\_XTP\_CKPT\_CLOSE','XE\_DISPATCHER\_JOIN','XE\_DISPATCHER\_WAIT',

        'XE\_TIMER\_EVENT')

      AND waiting\_tasks\_count \> 0

)

SELECT TOP 15 wait\_type, CAST(wait\_time\_s AS DECIMAL(16,1)) AS wait\_time\_s,

       CAST(resource\_s AS DECIMAL(16,1)) AS resource\_s, CAST(signal\_s AS DECIMAL(16,1)) AS signal\_s,

       waiting\_tasks\_count, CAST(pct AS DECIMAL(5,2)) AS pct

FROM waits

ORDER BY wait\_time\_s DESC;

Lecture des types d'attente les plus fréquents sur une base volumineuse :

| Attente | Signification | Piste |
| :---- | :---- | :---- |
| `SOS_SCHEDULER_YIELD` | La requête a rendu le CPU volontairement (quantum de 4 ms écoulé) | Pression CPU, requêtes trop coûteuses, plans mal estimés |
| `CXPACKET`, `CXCONSUMER` | Parallélisme : les threads s'attendent entre eux | Normal en quantité modérée ; excessif si petites requêtes parallélisées (cost threshold trop bas) ou distribution déséquilibrée (statistiques) |
| `PAGEIOLATCH_SH`, `PAGEIOLATCH_EX` | Attente de lecture d'une page depuis le disque | Mémoire insuffisante pour les données lues, scans évitables, index manquants, stockage lent |
| `PAGELATCH_EX`, `PAGELATCH_UP` | Contention sur une page déjà en mémoire | Contention TempDB (pages PFS/GAM/SGAM), insertion massive sur dernière page (hot page) |
| `LCK_M_*` | Attente d'un verrou détenu par une autre session | Blocage : transactions longues, escalade de verrous, absence de RCSI |
| `WRITELOG` | Attente d'écriture dans le journal de transactions | Stockage du log lent, trop de petites transactions |
| `RESOURCE_SEMAPHORE` | Attente d'une allocation mémoire pour trier ou hacher | Memory grants trop grosses (surestimation) ou trop nombreuses |
| `ASYNC_NETWORK_IO` | Le client ne consomme pas les résultats assez vite | Application qui traite ligne par ligne ; rarement un problème serveur |
| `THREADPOOL` | Plus aucun worker thread disponible | Blocage massif en cascade, urgence |

Le rapport `signal_s / wait_time_s` compte aussi : le temps signal est le délai entre le moment où la ressource est disponible et le moment où la requête reprend le CPU. S'il dépasse 20 à 25 % du total, l'instance manque de CPU.

Les compteurs étant cumulés, deux lectures sont possibles : la photo depuis le redémarrage (tendance de fond) et le delta sur un intervalle (ce qui se passe maintenant). `sp_BlitzFirst @Seconds = 30` fait le delta automatiquement :

EXEC sp\_BlitzFirst @Seconds \= 30, @ExpertMode \= 1;

Il est aussi possible de remettre les compteurs à zéro, par exemple avant un test de charge :

DBCC SQLPERF('sys.dm\_os\_wait\_stats', CLEAR);

### Ce qui tourne maintenant

EXEC sp\_WhoIsActive

    @get\_plans \= 1,          \-- plan d'exécution de chaque session

    @get\_task\_info \= 2,      \-- attentes détaillées

    @find\_block\_leaders \= 1, \-- identifier la tête d'une chaîne de blocage

    @get\_additional\_info \= 1;

Colonnes à lire en priorité : `wait_info`, `blocking_session_id`, `CPU`, `reads`, `tempdb_allocations`, `open_tran_count`. Une session avec `open_tran_count > 0` et un statut `sleeping` est une transaction ouverte oubliée : c'est très souvent la tête d'une chaîne de blocage.

### Le cache de plans : les requêtes les plus coûteuses

`sys.dm_exec_query_stats` agrège les statistiques d'exécution de chaque plan présent en cache. Limite importante : un plan évincé du cache disparaît des statistiques. Le Query Store (chapitre 4\) résout ce problème en persistant l'historique.

\-- Top 20 par CPU total, avec le texte et le plan

SELECT TOP 20

    qs.total\_worker\_time / 1000 AS total\_cpu\_ms,

    qs.execution\_count,

    qs.total\_worker\_time / qs.execution\_count / 1000 AS avg\_cpu\_ms,

    qs.total\_logical\_reads / qs.execution\_count AS avg\_logical\_reads,

    qs.total\_elapsed\_time / qs.execution\_count / 1000 AS avg\_elapsed\_ms,

    qs.max\_grant\_kb,

    qs.last\_execution\_time,

    SUBSTRING(st.text, (qs.statement\_start\_offset/2) \+ 1,

        ((CASE qs.statement\_end\_offset WHEN \-1 THEN DATALENGTH(st.text)

          ELSE qs.statement\_end\_offset END \- qs.statement\_start\_offset)/2) \+ 1\) AS statement\_text,

    qp.query\_plan

FROM sys.dm\_exec\_query\_stats qs

CROSS APPLY sys.dm\_exec\_sql\_text(qs.sql\_handle) st

CROSS APPLY sys.dm\_exec\_query\_plan(qs.plan\_handle) qp

ORDER BY qs.total\_worker\_time DESC;

Changer `ORDER BY` selon la ressource identifiée par les wait stats : `total_logical_reads` si `PAGEIOLATCH`, `total_worker_time` si `SOS_SCHEDULER_YIELD`, `max_grant_kb` ou `total_grant_kb` si `RESOURCE_SEMAPHORE`, `total_spills` si les tris débordent en TempDB.

La version outillée :

EXEC sp\_BlitzCache @SortOrder \= 'cpu', @Top \= 20;

\-- autres tris : 'reads', 'duration', 'executions', 'memory grant', 'spills', 'avg cpu'

`sp_BlitzCache` ajoute une colonne `Warnings` qui signale automatiquement les problèmes courants dans les plans : conversions implicites, index manquants, tri débordé, estimations très éloignées, fonctions scalaires, parallélisme fréquent, plan compilé pour des paramètres atypiques.

### Le fichier de log d'erreur et les compteurs de performance

Deux sources souvent oubliées :

\-- Événements récents : erreurs IO longues (message "taking longer than 15 seconds"), dumps, basculements

EXEC xp\_readerrorlog 0, 1, N'longer than', NULL, NULL, NULL, N'desc';

\-- Compteurs clés

SELECT object\_name, counter\_name, instance\_name, cntr\_value

FROM sys.dm\_os\_performance\_counters

WHERE counter\_name IN ('Page life expectancy', 'Batch Requests/sec', 'SQL Compilations/sec',

                       'SQL Re-Compilations/sec', 'Memory Grants Pending', 'Lock Waits/sec',

                       'Page reads/sec', 'Checkpoint pages/sec');

Page life expectancy (PLE) : durée moyenne de vie d'une page en mémoire. Une PLE qui s'effondre à intervalles réguliers signale un traitement qui scanne une table entière et évince tout le cache. Le seuil historique de 300 secondes n'a plus de sens : sur un serveur de 256 Go de RAM, une PLE de 300 s signifie que toute la mémoire est renouvelée toutes les 5 minutes, ce qui est énorme. Regarder la tendance et les creux plutôt qu'une valeur absolue.

### Exercice

1. Sur le lab, réinitialiser les wait stats.  
2. Lancer avec SQLQueryStress 20 threads exécutant `SELECT COUNT(*) FROM Posts WHERE OwnerUserId = @id` avec des `@id` variés (il n'y a pas d'index sur OwnerUserId par défaut).  
3. Relever les wait stats, identifier la ressource dominante, retrouver la requête dans `sp_BlitzCache`, lire son plan.  
4. Créer l'index, recommencer, comparer.

---

## 3\. Lire un plan d'exécution

### Concept

Le plan d'exécution est l'arbre d'opérateurs choisi par l'optimiseur. Il existe en deux versions :

- le plan estimé : ce que l'optimiseur prévoit, sans exécuter la requête ;  
- le plan réel : le même arbre, enrichi des mesures d'exécution (lignes réellement traitées, temps, IO, avertissements).

Le tuning se fait toujours sur le plan réel. Le plan estimé sert quand la requête est trop longue pour être rejouée.

L'optimiseur ne cherche pas le meilleur plan mais un plan suffisamment bon dans un temps borné. Son choix repose presque entièrement sur les estimations de cardinalité (nombre de lignes attendues à chaque opérateur). Quand les estimations sont fausses, le plan est mauvais : c'est la cause première de la majorité des problèmes de performance.

### Obtenir un plan

\-- Mesures textuelles indispensables

SET STATISTICS IO, TIME ON;

\-- Plan réel dans SSMS : Ctrl+M avant d'exécuter, ou

SET STATISTICS XML ON;

SELECT TOP 100 p.Id, p.Title, u.DisplayName

FROM dbo.Posts p

JOIN dbo.Users u ON u.Id \= p.OwnerUserId

WHERE p.CreationDate \>= '2013-01-01'

ORDER BY p.Score DESC;

SET STATISTICS XML OFF;

SET STATISTICS IO, TIME OFF;

Sortie de `STATISTICS IO` à savoir lire : `logical reads` est la mesure la plus stable du travail effectué (pages de 8 Ko lues en mémoire). `physical reads` et `read-ahead reads` dépendent de l'état du cache et varient d'une exécution à l'autre. Comparer deux versions d'une requête se fait sur les lectures logiques et le temps CPU, pas sur la durée seule.

Pour récupérer le plan d'une requête déjà exécutée sans la rejouer :

\-- Depuis le cache

SELECT qp.query\_plan

FROM sys.dm\_exec\_cached\_plans cp

CROSS APPLY sys.dm\_exec\_query\_plan(cp.plan\_handle) qp

CROSS APPLY sys.dm\_exec\_sql\_text(cp.plan\_handle) st

WHERE st.text LIKE '%OwnerUserId%';

\-- Dernier plan réel (SQL 2019+, nécessite LAST\_QUERY\_PLAN\_STATS)

ALTER DATABASE SCOPED CONFIGURATION SET LAST\_QUERY\_PLAN\_STATS \= ON;

SELECT \* FROM sys.dm\_exec\_query\_plan\_stats(plan\_handle);

### Ordre de lecture

Le plan se lit de droite à gauche (flux de données) et de haut en bas (ordre d'appel). Le premier opérateur en haut à gauche est le dernier à s'exécuter. Les flèches représentent les lignes : leur épaisseur est proportionnelle au nombre de lignes réel dans SSMS, et Plan Explorer permet de la baser sur la taille en octets, ce qui est souvent plus parlant.

Pour chaque opérateur, les propriétés essentielles :

| Propriété | Lecture |
| :---- | :---- |
| Estimated Number of Rows vs Actual Number of Rows | L'écart mesure la qualité de l'estimation. Un facteur 10 ou plus est un problème à traiter |
| Actual Number of Rows Read vs Actual Number of Rows | Sur un scan ou un seek, lignes lues puis filtrées par un prédicat résiduel : si Rows Read est très supérieur, l'index ne couvre pas bien le filtre |
| Estimated Operator Cost | Pourcentage du coût total estimé. Attention : estimé, donc faux si les estimations le sont. Ne pas se fier au "gros pourcentage" comme seule boussole |
| Actual Elapsed Time (SQL 2016 SP1+) | Temps réel par opérateur, cumulé des enfants en mode ligne (row mode), propre à l'opérateur en mode batch |
| Number of Executions | Nombre de fois où l'opérateur a été appelé. Un opérateur interne d'une boucle imbriquée exécuté 5 millions de fois est un signal |
| Warnings | Triangle jaune : à ouvrir systématiquement |

### Les opérateurs à connaître

Accès aux données :

- Clustered Index Scan / Table Scan : lecture complète. Légitime si la requête retourne une grande partie de la table ; problème si elle retourne 10 lignes.  
- Index Seek : accès par la clé. Vérifier le prédicat de seek (Seek Predicates) et le prédicat résiduel (Predicate) : ce dernier est appliqué après lecture, ligne par ligne.  
- Key Lookup / RID Lookup : pour chaque ligne trouvée dans un index non-cluster, aller chercher les colonnes manquantes dans la table. Coût proportionnel au nombre de lignes. Au-delà de quelques milliers d'exécutions, un index couvrant (colonnes en INCLUDE) le supprime.

Jointures :

- Nested Loops : pour chaque ligne du côté externe, chercher dans le côté interne. Excellent quand le côté externe est petit et le côté interne indexé. Catastrophique quand l'optimiseur a estimé 10 lignes externes et qu'il y en a 2 millions.  
- Hash Match : construit une table de hachage sur une entrée (build), sonde avec l'autre (probe). Le choix par défaut pour les gros volumes. Nécessite une allocation mémoire (memory grant) ; si elle est insuffisante, débordement en TempDB (spill).  
- Merge Join : les deux entrées sont triées sur la clé de jointure. Très efficace si les tris sont déjà fournis par des index ; sinon un Sort est ajouté avant.

Autres :

- Sort : toujours coûteux sur un gros volume, nécessite une memory grant, déborde facilement. Se demander si un index peut fournir l'ordre.  
- Filter, Compute Scalar, Stream Aggregate, Hash Aggregate.  
- Parallelism (Gather Streams, Repartition Streams, Distribute Streams).

### Les avertissements

À ouvrir dès qu'un triangle jaune apparaît.

- Implicit conversion : une colonne comparée à une valeur d'un autre type, typiquement `NVARCHAR` de l'application contre `VARCHAR` de la table, ou `INT` contre `VARCHAR`. Résultat : l'index n'est plus utilisable en seek, scan complet. Le correctif est côté application (type du paramètre) ou côté schéma.  
- Spill to TempDB (sur Sort ou Hash Match) : la mémoire allouée était insuffisante, les données ont été écrites sur disque. Cause : estimation de cardinalité trop basse. Niveau de spill 1 à 3, le 3 étant le pire.  
- Excessive Grant : la mémoire allouée était très supérieure au besoin réel. Cause : estimation trop haute. Plusieurs requêtes de ce type concurrentes provoquent `RESOURCE_SEMAPHORE`.  
- No Join Predicate : produit cartésien, presque toujours une erreur d'écriture.  
- Columns With No Statistics : l'optimiseur n'a aucune information sur une colonne filtrée.

### Les mauvais schémas récurrents

Chercher dans un plan lent, par ordre de fréquence :

1. Écart énorme entre estimé et réel sur un opérateur d'accès (statistiques, paramètre atypique, prédicat non-SARGable).  
2. Nested Loops avec un côté interne exécuté des millions de fois.  
3. Key Lookup avec des centaines de milliers d'exécutions.  
4. Sort ou Hash qui déborde.  
5. Scan là où un seek était attendu, à cause d'une fonction sur la colonne (`WHERE YEAR(CreationDate) = 2013`), d'une conversion implicite, ou d'un `LIKE '%xxx'`.  
6. Fonction scalaire utilisateur (UDF) appelée par ligne : coût caché, exécution en série, et jusqu'à SQL 2019 le coût n'apparaît même pas dans le plan. SQL 2019 introduit l'inlining des UDF scalaires (souvent, pas toujours).

### Un prédicat SARGable

SARGable signifie que le prédicat peut utiliser un index en seek. Règle : la colonne doit être seule d'un côté de l'opérateur, sans fonction ni calcul.

\-- Non SARGable : scan

WHERE YEAR(CreationDate) \= 2013

WHERE CONVERT(DATE, CreationDate) \= '2013-06-01'

WHERE ISNULL(ClosedDate, '9999-12-31') \> GETDATE()

WHERE LEFT(Title, 3\) \= 'SQL'

\-- SARGable : seek possible

WHERE CreationDate \>= '2013-01-01' AND CreationDate \< '2014-01-01'

WHERE CreationDate \>= '2013-06-01' AND CreationDate \< '2013-06-02'

WHERE (ClosedDate \> GETDATE() OR ClosedDate IS NULL)

WHERE Title LIKE 'SQL%'

### Exercice

Sur StackOverflow, écrire trois versions d'une même requête (une avec fonction sur la colonne, une avec conversion implicite en déclarant `@name NVARCHAR(40)` contre une colonne `VARCHAR`, une correcte), comparer les plans, les lectures logiques et les avertissements.

---

## 4\. Query Store

### Concept

Le Query Store (SQL 2016+) enregistre dans la base elle-même l'historique des requêtes, de leurs plans et de leurs statistiques d'exécution par intervalle de temps. Contrairement au cache de plans, il survit aux redémarrages et aux évictions. Il permet de :

- retrouver ce qui a changé quand "c'est lent depuis hier" ;  
- détecter une régression de plan (même requête, nouveau plan, plus lent) ;  
- forcer un plan connu comme bon en attendant le correctif de fond ;  
- mesurer l'effet d'un changement (index, statistiques, mise à jour de version).

Sur une base unique en production avec des enjeux de perf, c'est l'outil central et il doit être activé, configuré et surveillé.

### Configuration

ALTER DATABASE \[Prod\] SET QUERY\_STORE \= ON;

ALTER DATABASE \[Prod\] SET QUERY\_STORE (

    OPERATION\_MODE \= READ\_WRITE,

    CLEANUP\_POLICY \= (STALE\_QUERY\_THRESHOLD\_DAYS \= 30),

    DATA\_FLUSH\_INTERVAL\_SECONDS \= 900,

    INTERVAL\_LENGTH\_MINUTES \= 15,        \-- granularité des agrégats ; 15 ou 60 en prod

    MAX\_STORAGE\_SIZE\_MB \= 4096,          \-- passer en lecture seule si atteint : à surveiller

    QUERY\_CAPTURE\_MODE \= CUSTOM,         \-- SQL 2019+ ; AUTO sinon

    QUERY\_CAPTURE\_POLICY \= (

        STALE\_CAPTURE\_POLICY\_THRESHOLD \= 1 HOUR,

        EXECUTION\_COUNT \= 30,

        TOTAL\_COMPILE\_CPU\_TIME\_MS \= 1000,

        TOTAL\_EXECUTION\_CPU\_TIME\_MS \= 100),

    SIZE\_BASED\_CLEANUP\_MODE \= AUTO,

    MAX\_PLANS\_PER\_QUERY \= 200,

    WAIT\_STATS\_CAPTURE\_MODE \= ON          \-- attentes par requête, très utile

);

Pièges connus :

- `QUERY_CAPTURE_MODE = ALL` sur une application qui génère du SQL ad hoc non paramétré fait exploser le Query Store en quelques heures. Utiliser `AUTO` ou `CUSTOM`, et envisager `FORCED PARAMETERIZATION` ou `OPTIMIZE FOR AD HOC WORKLOADS` (chapitre 11).  
- Quand `MAX_STORAGE_SIZE_MB` est atteint, le Query Store passe en `READ_ONLY` silencieusement. Surveiller :

SELECT actual\_state\_desc, readonly\_reason, current\_storage\_size\_mb, max\_storage\_size\_mb

FROM sys.database\_query\_store\_options;

### Les vues

sys.query\_store\_query\_text     texte de la requête

sys.query\_store\_query          requête (une par texte \+ contexte de compilation)

sys.query\_store\_plan           plans associés à chaque requête

sys.query\_store\_runtime\_stats  statistiques d'exécution par plan et par intervalle

sys.query\_store\_runtime\_stats\_interval  bornes des intervalles

sys.query\_store\_wait\_stats     attentes par plan et par intervalle (si activé)

Requête de base : top requêtes par CPU sur les dernières 24 heures.

SELECT TOP 20

    q.query\_id, p.plan\_id,

    SUM(rs.count\_executions) AS executions,

    SUM(rs.avg\_cpu\_time \* rs.count\_executions) / 1000 AS total\_cpu\_ms,

    SUM(rs.avg\_cpu\_time \* rs.count\_executions) / SUM(rs.count\_executions) / 1000 AS avg\_cpu\_ms,

    SUM(rs.avg\_logical\_io\_reads \* rs.count\_executions) / SUM(rs.count\_executions) AS avg\_reads,

    MAX(rs.max\_dop) AS max\_dop,

    LEFT(qt.query\_sql\_text, 200\) AS query\_text

FROM sys.query\_store\_runtime\_stats rs

JOIN sys.query\_store\_runtime\_stats\_interval i ON i.runtime\_stats\_interval\_id \= rs.runtime\_stats\_interval\_id

JOIN sys.query\_store\_plan p ON p.plan\_id \= rs.plan\_id

JOIN sys.query\_store\_query q ON q.query\_id \= p.query\_id

JOIN sys.query\_store\_query\_text qt ON qt.query\_text\_id \= q.query\_text\_id

WHERE i.start\_time \>= DATEADD(HOUR, \-24, SYSUTCDATETIME())

GROUP BY q.query\_id, p.plan\_id, qt.query\_sql\_text

ORDER BY total\_cpu\_ms DESC;

### Détecter une régression de plan

Une requête qui possède plusieurs plans dont les performances diffèrent fortement :

SELECT q.query\_id, p.plan\_id, p.is\_forced\_plan,

       p.last\_compile\_start\_time,

       SUM(rs.count\_executions) AS executions,

       AVG(rs.avg\_duration) / 1000 AS avg\_duration\_ms,

       AVG(rs.avg\_cpu\_time) / 1000 AS avg\_cpu\_ms,

       AVG(rs.avg\_logical\_io\_reads) AS avg\_reads

FROM sys.query\_store\_query q

JOIN sys.query\_store\_plan p ON p.query\_id \= q.query\_id

JOIN sys.query\_store\_runtime\_stats rs ON rs.plan\_id \= p.plan\_id

WHERE q.query\_id IN (

    SELECT query\_id FROM sys.query\_store\_plan GROUP BY query\_id HAVING COUNT(\*) \> 1\)

GROUP BY q.query\_id, p.plan\_id, p.is\_forced\_plan, p.last\_compile\_start\_time

ORDER BY q.query\_id, avg\_duration\_ms DESC;

Dans SSMS, le rapport "Regressed Queries" fait la même chose graphiquement et permet de comparer deux plans côte à côte.

### Forcer un plan

EXEC sp\_query\_store\_force\_plan @query\_id \= 1234, @plan\_id \= 5678;

\-- Annuler

EXEC sp\_query\_store\_unforce\_plan @query\_id \= 1234, @plan\_id \= 5678;

\-- Vérifier les échecs de forçage (index supprimé, schéma modifié...)

SELECT query\_id, plan\_id, is\_forced\_plan, force\_failure\_count, last\_force\_failure\_reason\_desc

FROM sys.query\_store\_plan

WHERE is\_forced\_plan \= 1;

Le forçage est un pansement : il stabilise en attendant de comprendre pourquoi le mauvais plan a été choisi (statistiques, parameter sniffing, changement d'index). Documenter chaque plan forcé et revoir la liste régulièrement. SQL 2017+ propose la correction automatique (`AUTOMATIC_TUNING (FORCE_LAST_GOOD_PLAN = ON)`), qui force le dernier bon plan quand une régression est détectée et annule le forçage si cela ne s'améliore pas. Utile mais à observer via `sys.dm_db_tuning_recommendations` avant de l'activer en aveugle.

### Query Store hints (SQL 2022\)

Appliquer un hint à une requête sans toucher au code applicatif :

EXEC sp\_query\_store\_set\_hints @query\_id \= 1234, @query\_hints \= N'OPTION (RECOMPILE)';

EXEC sp\_query\_store\_set\_hints @query\_id \= 1234, @query\_hints \= N'OPTION (MAXDOP 1)';

EXEC sp\_query\_store\_set\_hints @query\_id \= 1234, @query\_hints \= N'OPTION (USE HINT(''FORCE\_LEGACY\_CARDINALITY\_ESTIMATION''))';

EXEC sp\_query\_store\_clear\_hints @query\_id \= 1234;

SELECT \* FROM sys.query\_store\_query\_hints;

C'est un levier majeur quand l'application est un progiciel dont le SQL ne peut pas être modifié.

### Exercice

1. Créer une procédure `GetPostsByUser @UserId` qui liste les posts d'un utilisateur.  
2. L'exécuter d'abord avec un utilisateur qui a 3 posts, puis avec un utilisateur qui en a 30 000 (utiliser `Users` avec le plus grand `Reputation`).  
3. Retrouver la requête dans le Query Store, constater les deux plans (après `DBCC FREEPROCCACHE` entre les deux appels pour forcer une recompilation), comparer les durées, forcer le plan le plus robuste, puis annuler.

---

## 5\. Statistiques et estimateur de cardinalité

### Concept

Les statistiques décrivent la distribution des valeurs d'une colonne (ou d'un ensemble de colonnes). L'estimateur de cardinalité (CE, cardinality estimator) les lit pour prédire combien de lignes chaque opérateur va produire. Tout le plan en découle : type de jointure, ordre des jointures, allocation mémoire, degré de parallélisme.

Sur une table d'un milliard de lignes, les statistiques posent des problèmes spécifiques : elles sont échantillonnées sur une fraction minuscule, elles se rafraîchissent rarement, et l'histogramme est limité à 200 pas pour décrire la distribution.

### Anatomie d'une statistique

DBCC SHOW\_STATISTICS ('dbo.Posts', 'IX\_Posts\_CreationDate');

Trois blocs :

1. En-tête : date de mise à jour (`Updated`), lignes dans la table (`Rows`), lignes échantillonnées (`Rows Sampled`), nombre de pas (`Steps`), densité moyenne.  
2. Vecteur de densité : pour chaque préfixe de colonnes, `1 / nombre de valeurs distinctes`. Utilisé quand la valeur exacte n'est pas connue à la compilation (variables locales, paramètres optimisés pour UNKNOWN).  
3. Histogramme : jusqu'à 200 pas. Pour chaque pas, `RANGE_HI_KEY` (borne haute), `EQ_ROWS` (lignes égales à la borne), `RANGE_ROWS` (lignes strictement dans l'intervalle), `DISTINCT_RANGE_ROWS`, `AVG_RANGE_ROWS`. Utilisé quand la valeur est connue (littéral, paramètre sniffé).

Pour toutes les statistiques d'une table d'un coup :

SELECT s.name, s.auto\_created, s.user\_created, s.is\_incremental, s.has\_persisted\_sample,

       sp.last\_updated, sp.rows, sp.rows\_sampled,

       CAST(100.0 \* sp.rows\_sampled / NULLIF(sp.rows,0) AS DECIMAL(5,2)) AS sample\_pct,

       sp.modification\_counter, sp.steps, sp.persisted\_sample\_percent

FROM sys.stats s

CROSS APPLY sys.dm\_db\_stats\_properties(s.object\_id, s.stats\_id) sp

WHERE s.object\_id \= OBJECT\_ID('dbo.Posts')

ORDER BY sp.modification\_counter DESC;

`modification_counter` compte les modifications depuis la dernière mise à jour ; c'est lui qui déclenche la mise à jour automatique.

### Le seuil de mise à jour automatique

Depuis SQL 2016 (niveau de compatibilité 130+), le seuil est dynamique : environ `SQRT(1000 * rows)`. Sur une table de 1 milliard de lignes, cela fait environ 1 million de modifications. Avant 2016 (ou en compatibilité inférieure sans trace flag 2371), le seuil était `20 % + 500 lignes`, soit 200 millions de modifications : les statistiques ne se mettaient jamais à jour.

Conséquence pratique : sur une table à un milliard de lignes qui reçoit 5 millions d'insertions par jour, les statistiques se mettent à jour automatiquement plusieurs fois par jour, mais avec un échantillon par défaut très faible (l'échantillon décroît avec la taille de la table, souvent moins de 1 %).

Mise à jour automatique synchrone ou asynchrone : par défaut, la requête qui déclenche la mise à jour attend qu'elle soit terminée. Sur une grosse table, cela peut ajouter plusieurs secondes de manière aléatoire. Le mode asynchrone laisse la requête utiliser les anciennes statistiques et met à jour en arrière-plan :

ALTER DATABASE \[Prod\] SET AUTO\_UPDATE\_STATISTICS\_ASYNC ON;

C'est recommandé sur une base OLTP volumineuse, à condition d'avoir une maintenance planifiée des statistiques en complément.

### Mettre à jour manuellement

\-- Une statistique, avec échantillon complet (long sur un milliard de lignes)

UPDATE STATISTICS dbo.Posts IX\_Posts\_CreationDate WITH FULLSCAN;

\-- Échantillon fixé, et mémorisé pour les mises à jour automatiques suivantes (SQL 2016 SP1 CU4+)

UPDATE STATISTICS dbo.Posts IX\_Posts\_CreationDate WITH SAMPLE 10 PERCENT, PERSIST\_SAMPLE\_PERCENT \= ON;

\-- Toute la table

UPDATE STATISTICS dbo.Posts WITH FULLSCAN;

`PERSIST_SAMPLE_PERCENT` résout un problème classique : le DBA met à jour avec FULLSCAN la nuit, puis la mise à jour automatique en journée repasse à l'échantillon par défaut et détruit la qualité. Avec l'option, l'échantillon choisi est conservé.

Sur les très grosses tables, la stratégie habituelle : mise à jour planifiée avec un échantillon raisonnable (5 à 20 %) et persisté sur les colonnes critiques, FULLSCAN uniquement sur les colonnes dont la distribution est très irrégulière. Les scripts d'Ola Hallengren (`IndexOptimize` avec `@UpdateStatistics = 'ALL'`, `@OnlyModifiedStatistics = 'Y'`) gèrent cela.

### Le problème de la clé ascendante

Sur une table où l'on insère par date ou par identifiant croissant, les nouvelles lignes sont toutes au-delà du dernier pas de l'histogramme. Entre deux mises à jour de statistiques, une requête `WHERE CreationDate >= '(hier)'` est estimée à 1 ligne alors qu'il y en a 5 millions : Nested Loops, memory grant minuscule, spills. C'est le symptôme classique "la requête du matin est lente, elle redevient normale l'après-midi".

Le nouveau CE (SQL 2014+) atténue le problème en supposant que des lignes existent au-delà de l'histogramme (il utilise la densité moyenne). Mais l'estimation reste approximative. Correctifs :

- mise à jour des statistiques plus fréquente sur la colonne ascendante (job toutes les heures, `@OnlyModifiedStatistics`) ;  
- statistique filtrée sur la période récente ;  
- `OPTION (RECOMPILE)` sur les requêtes concernées si elles sont peu fréquentes.

### Statistiques filtrées

Une statistique sur un sous-ensemble de la table, avec ses propres 200 pas :

CREATE STATISTICS ST\_Posts\_Recent ON dbo.Posts (CreationDate)

WHERE CreationDate \>= '2013-01-01'

WITH FULLSCAN;

Utile quand une plage de valeurs est très interrogée et mal décrite par l'histogramme global, ou pour une valeur très fréquente (tous les statuts "actif" contre quelques "supprimé"). Attention : une statistique filtrée n'est utilisée que si le prédicat de la requête est un littéral ou un paramètre sniffé, pas une variable locale.

### Statistiques incrémentales

Sur une table partitionnée (chapitre 7), les statistiques peuvent être maintenues par partition. La mise à jour ne rescanne que les partitions modifiées, et le seuil automatique s'applique par partition :

ALTER DATABASE \[Prod\] SET AUTO\_CREATE\_STATISTICS ON (INCREMENTAL \= ON);

CREATE STATISTICS ST\_Fact\_Date ON dbo.Fact (EventDate) WITH INCREMENTAL \= ON;

UPDATE STATISTICS dbo.Fact ST\_Fact\_Date WITH RESAMPLE ON PARTITIONS (245, 246);

Limite : l'histogramme exposé à l'optimiseur reste unique (les histogrammes par partition sont fusionnés en 200 pas). Le gain est sur le coût de maintenance, pas sur la précision.

### Legacy CE contre nouveau CE

Deux estimateurs coexistent :

- Legacy CE (70) : celui de SQL 7.0 à 2012\. Hypothèse d'indépendance des prédicats : `P(A et B) = P(A) * P(B)`.  
- Nouveau CE (120+) : activé par le niveau de compatibilité 120 ou plus. Hypothèse de corrélation partielle (exponential backoff), estimation différente des jointures, des clés ascendantes, des `DISTINCT`.

Le nouveau CE est meilleur en moyenne, mais une migration de compatibilité fait régresser certaines requêtes. Approche recommandée :

1. Activer le Query Store avant de changer le niveau de compatibilité, laisser tourner une période représentative.  
2. Changer le niveau.  
3. Comparer via le rapport "Regressed Queries".  
4. Corriger chaque régression individuellement, du plus ciblé au plus global :

\-- Sur une requête

SELECT ... OPTION (USE HINT('FORCE\_LEGACY\_CARDINALITY\_ESTIMATION'));

\-- Via Query Store hint (2022) sans toucher au code

EXEC sp\_query\_store\_set\_hints @query\_id \= 42, @query\_hints \= N'OPTION (USE HINT(''FORCE\_LEGACY\_CARDINALITY\_ESTIMATION''))';

\-- Sur toute la base (dernier recours : on garde le nouveau moteur mais l'ancien estimateur)

ALTER DATABASE SCOPED CONFIGURATION SET LEGACY\_CARDINALITY\_ESTIMATION \= ON;

Liste complète des hints disponibles : `SELECT * FROM sys.dm_exec_valid_use_hints;`

### Parameter sniffing

À la première compilation d'une procédure ou d'une requête paramétrée, l'optimiseur lit (sniffe) la valeur des paramètres et construit un plan optimal pour ces valeurs. Le plan est mis en cache et réutilisé pour toutes les valeurs suivantes. Si la distribution est très inégale (un client avec 10 commandes, un autre avec 10 millions), le plan compilé pour l'un est catastrophique pour l'autre.

Ce n'est pas un bug : c'est le comportement souhaitable dans 95 % des cas (compiler une fois, réutiliser). Le problème apparaît sur les distributions asymétriques.

Diagnostic : dans le plan en cache, comparer `Parameter Compiled Value` et `Parameter Runtime Value` (propriétés de l'opérateur racine). Dans le Query Store, une requête avec plusieurs plans aux performances très différentes.

Correctifs, du plus ciblé au plus global :

\-- 1\. Recompiler à chaque exécution (coût de compilation, à réserver aux requêtes peu fréquentes)

SELECT ... OPTION (RECOMPILE);

\-- 2\. Optimiser pour une valeur typique ou pour l'inconnu (densité moyenne)

SELECT ... OPTION (OPTIMIZE FOR (@UserId \= 12345));

SELECT ... OPTION (OPTIMIZE FOR UNKNOWN);

\-- 3\. Séparer les cas dans le code : une procédure pour les gros comptes, une pour les autres

\-- 4\. Réécrire pour rendre le plan moins sensible (index couvrant qui rend le seek \+ lookup inutile)

\-- 5\. Query Store : forcer le plan le plus robuste

\-- 6\. Désactiver le sniffing pour toute la base (rarement une bonne idée)

ALTER DATABASE SCOPED CONFIGURATION SET PARAMETER\_SNIFFING \= OFF;

SQL 2022 introduit Parameter Sensitive Plan optimization (PSP) : pour les prédicats d'égalité sur une colonne dont la distribution est asymétrique, l'optimiseur peut garder jusqu'à trois plans en cache et choisir selon la valeur du paramètre. C'est activé en compatibilité 160\. Cela couvre une partie des cas, pas tous (égalité uniquement, une seule colonne par prédicat).

### Exercice

1. Créer une table `Orders` avec un `CustomerId` très asymétrique : 1 000 clients avec 10 lignes, 1 client avec 5 millions.  
2. Écrire `GetOrders @CustomerId`, l'exécuter pour un petit client, puis pour le gros. Observer le plan (Nested Loops \+ Key Lookup exécuté 5 millions de fois).  
3. Vider le cache, inverser l'ordre : plan de scan utilisé pour un petit client.  
4. Tester chacun des correctifs, mesurer avec `STATISTICS IO`.  
5. Passer en compatibilité 160 et observer si PSP crée deux plans (chercher `Dispatcher` dans le plan XML).

---

## 6\. Index rowstore : conception, usage, maintenance

### Concept

Un index cluster définit l'ordre physique de la table (les feuilles de l'arbre B+ sont les lignes elles-mêmes). Il n'y en a qu'un. Un index non-cluster est une copie triée d'un sous-ensemble de colonnes, chaque entrée pointant vers la ligne via la clé cluster (ou le RID si la table est un heap).

Sur une table d'un milliard de lignes, chaque index non-cluster pèse des dizaines de Go, ralentit chaque insertion, et sa maintenance prend des heures. La discipline est donc : peu d'index, très bien choisis, couvrants pour les requêtes critiques.

### Choisir la clé cluster

Critères classiques : unique, étroite (petite taille), statique (jamais mise à jour), croissante (les insertions se font en fin de table, pas de fragmentation ni de page splits). Un `BIGINT IDENTITY` coche toutes les cases. Un `UNIQUEIDENTIFIER` aléatoire les rate toutes : à un milliard de lignes, c'est une source majeure de fragmentation et de lectures.

Cas à connaître : quand la table est interrogée massivement par plage de dates, une clé cluster `(EventDate, Id)` peut être préférable à `Id` seul, car elle regroupe physiquement les lignes d'une même période. C'est aussi la structure naturelle d'une table partitionnée par date (chapitre 7).

Une insertion très concurrente sur une clé croissante crée une contention sur la dernière page (`PAGELATCH_EX`, "hot page"). SQL 2019 apporte `OPTIMIZE_FOR_SEQUENTIAL_KEY = ON` pour l'atténuer.

### Concevoir un index non-cluster

Ordre des colonnes clés : d'abord les colonnes en égalité, puis celles en inégalité ou plage, et en dernier celles qui servent au tri. Puis les colonnes seulement lues vont en `INCLUDE`.

\-- Requête cible

SELECT Id, Title, Score FROM dbo.Posts

WHERE OwnerUserId \= @UserId AND PostTypeId \= 1 AND CreationDate \>= @Since

ORDER BY CreationDate DESC;

\-- Index adapté : égalités, puis plage (qui fournit aussi le tri), puis colonnes lues

CREATE INDEX IX\_Posts\_Owner\_Type\_Date ON dbo.Posts (OwnerUserId, PostTypeId, CreationDate)

INCLUDE (Title, Score)

WITH (ONLINE \= ON, DATA\_COMPRESSION \= PAGE, SORT\_IN\_TEMPDB \= ON, MAXDOP \= 4);

Un index qui contient toutes les colonnes de la requête est dit couvrant : plus de Key Lookup. Sur une table volumineuse, c'est le gain le plus fréquent et le plus spectaculaire, mais chaque colonne incluse grossit l'index.

Options importantes sur grosse table :

- `ONLINE = ON` (Enterprise) : la table reste accessible pendant la création.  
- `SORT_IN_TEMPDB = ON` : le tri intermédiaire se fait dans TempDB, plus rapide si TempDB est sur un stockage séparé.  
- `RESUMABLE = ON` (SQL 2019+ pour la création) : l'opération peut être interrompue et reprise.  
- `MAXDOP` : limiter pour ne pas saturer les CPU en journée.

### Index filtré

Un index qui ne contient qu'un sous-ensemble de lignes :

CREATE INDEX IX\_Orders\_Pending ON dbo.Orders (CustomerId, OrderDate)

INCLUDE (Amount)

WHERE Status \= 'PENDING';

Idéal quand une requête fréquente ne cible qu'une petite fraction d'une énorme table (commandes en cours parmi un milliard de commandes historisées). L'index est minuscule, ses statistiques sont précises. Contrainte : le prédicat de la requête doit correspondre exactement au filtre, et les paramètres posent problème (l'optimiseur ne peut pas garantir à la compilation que `@Status = 'PENDING'`).

### Diagnostiquer l'usage des index

\-- Usage : combien de seeks, scans, lookups, et combien de mises à jour subies

SELECT OBJECT\_NAME(i.object\_id) AS table\_name, i.name, i.type\_desc, i.is\_unique,

       us.user\_seeks, us.user\_scans, us.user\_lookups, us.user\_updates,

       us.last\_user\_seek, us.last\_user\_scan,

       ps.row\_count, ps.used\_page\_count \* 8 / 1024 AS size\_mb

FROM sys.indexes i

LEFT JOIN sys.dm\_db\_index\_usage\_stats us

       ON us.object\_id \= i.object\_id AND us.index\_id \= i.index\_id AND us.database\_id \= DB\_ID()

JOIN sys.dm\_db\_partition\_stats ps ON ps.object\_id \= i.object\_id AND ps.index\_id \= i.index\_id

WHERE OBJECTPROPERTY(i.object\_id, 'IsUserTable') \= 1

ORDER BY us.user\_updates DESC;

Un index avec des milliers de `user_updates`, zéro `user_seeks` et zéro `user_scans` depuis le dernier redémarrage est un candidat à la suppression (après vérification sur une période longue : les compteurs sont remis à zéro au redémarrage, et certains traitements sont mensuels).

\-- Coût opérationnel : verrous, latches, page splits, par index

SELECT OBJECT\_NAME(os.object\_id) AS table\_name, i.name,

       os.leaf\_insert\_count, os.leaf\_update\_count, os.leaf\_delete\_count,

       os.leaf\_allocation\_count AS page\_splits,

       os.row\_lock\_wait\_in\_ms, os.page\_lock\_wait\_in\_ms,

       os.page\_latch\_wait\_in\_ms, os.page\_io\_latch\_wait\_in\_ms

FROM sys.dm\_db\_index\_operational\_stats(DB\_ID(), NULL, NULL, NULL) os

JOIN sys.indexes i ON i.object\_id \= os.object\_id AND i.index\_id \= os.index\_id

ORDER BY os.page\_io\_latch\_wait\_in\_ms DESC;

### Les index manquants

Les DMV `sys.dm_db_missing_index_*` enregistrent les index que l'optimiseur aurait aimé avoir. À lire avec méfiance :

- les suggestions sont faites requête par requête, jamais consolidées : dix suggestions sur la même table sont souvent un seul bon index ;  
- l'ordre des colonnes proposé n'est pas optimisé (colonnes d'égalité par ordre de position dans la table, pas par sélectivité) ;  
- les colonnes `INCLUDE` proposées peuvent être énormes ;  
- le gain annoncé (`avg_user_impact`) est une estimation.

SELECT TOP 20

    mid.statement AS table\_name,

    migs.avg\_user\_impact, migs.user\_seeks, migs.avg\_total\_user\_cost,

    migs.avg\_total\_user\_cost \* migs.avg\_user\_impact \* (migs.user\_seeks \+ migs.user\_scans) AS score,

    mid.equality\_columns, mid.inequality\_columns, mid.included\_columns

FROM sys.dm\_db\_missing\_index\_groups mig

JOIN sys.dm\_db\_missing\_index\_group\_stats migs ON migs.group\_handle \= mig.index\_group\_handle

JOIN sys.dm\_db\_missing\_index\_details mid ON mid.index\_handle \= mig.index\_handle

WHERE mid.database\_id \= DB\_ID()

ORDER BY score DESC;

`sp_BlitzIndex` fait ce travail de consolidation et signale en plus les index dupliqués, les index jamais utilisés, les tables sans clé cluster, les index très larges :

EXEC sp\_BlitzIndex @DatabaseName \= 'Prod', @Mode \= 0;   \-- diagnostic

EXEC sp\_BlitzIndex @DatabaseName \= 'Prod', @Mode \= 4;   \-- tout, y compris index manquants consolidés

EXEC sp\_BlitzIndex @DatabaseName \= 'Prod', @SchemaName \= 'dbo', @TableName \= 'Posts';  \-- détail d'une table

### Fragmentation et maintenance

La fragmentation logique (pages dans le désordre) et le taux de remplissage (`avg_page_space_used_in_percent`) se mesurent avec :

SELECT OBJECT\_NAME(ps.object\_id) AS table\_name, i.name, ps.partition\_number,

       ps.index\_type\_desc, ps.avg\_fragmentation\_in\_percent, ps.page\_count,

       ps.avg\_page\_space\_used\_in\_percent

FROM sys.dm\_db\_index\_physical\_stats(DB\_ID(), OBJECT\_ID('dbo.Posts'), NULL, NULL, 'LIMITED') ps

JOIN sys.indexes i ON i.object\_id \= ps.object\_id AND i.index\_id \= ps.index\_id

WHERE ps.page\_count \> 1000

ORDER BY ps.avg\_fragmentation\_in\_percent DESC;

Le mode `LIMITED` ne lit que les niveaux intermédiaires et suffit pour la fragmentation ; `SAMPLED` ou `DETAILED` lisent les feuilles et sont très longs sur un milliard de lignes.

Ce qu'il faut savoir sur la fragmentation et qui contredit les habitudes anciennes :

- Sur du stockage SSD ou SAN moderne, la fragmentation logique a un impact très faible sur les lectures. Les scans séquentiels ne le sont plus depuis longtemps au niveau physique.  
- Le vrai coût de la fragmentation est l'espace : des pages à moitié vides occupent deux fois plus de mémoire dans le buffer pool.  
- Un rebuild nocturne de tous les index d'une base de 2 To génère des To de journal de transactions, sature les sauvegardes de log et la réplication (AG), et invalide le cache de plans (le rebuild met à jour les statistiques avec FULLSCAN, ce qui recompile tout).  
- La règle "reorganize entre 5 et 30 %, rebuild au-dessus de 30 %" vient d'un livre blanc de 2008 pour des disques mécaniques. Elle n'est plus pertinente en tant que telle.

Approche recommandée sur grosse base :

1. Mettre à jour les statistiques régulièrement : c'est cela qui améliore les plans, pas le rebuild.  
2. Reconstruire uniquement les index dont le taux de remplissage est faible et qui sont volumineux, rarement, hors heures ouvrées, en online et de manière reprenable.  
3. Sur les tables partitionnées, reconstruire par partition (seulement les partitions actives).  
4. Prévoir un `FILLFACTOR` inférieur à 100 uniquement sur les index qui subissent des insertions aléatoires (pas sur les clés croissantes).

\-- Rebuild online, reprenable, limité dans le temps

ALTER INDEX IX\_Posts\_Owner\_Type\_Date ON dbo.Posts

REBUILD WITH (ONLINE \= ON, RESUMABLE \= ON, MAX\_DURATION \= 120 MINUTES, MAXDOP \= 2);

\-- Suivi et reprise d'une opération reprenable

SELECT name, sql\_text, state\_desc, percent\_complete, start\_time, total\_execution\_time

FROM sys.index\_resumable\_operations;

ALTER INDEX IX\_Posts\_Owner\_Type\_Date ON dbo.Posts PAUSE;

ALTER INDEX IX\_Posts\_Owner\_Type\_Date ON dbo.Posts RESUME WITH (MAX\_DURATION \= 60 MINUTES);

\-- Reorganize : toujours online, interruptible, mais ne met pas à jour les statistiques

ALTER INDEX IX\_Posts\_Owner\_Type\_Date ON dbo.Posts REORGANIZE;

\-- Une seule partition

ALTER INDEX IX\_Fact\_Date ON dbo.Fact REBUILD PARTITION \= 245 WITH (ONLINE \= ON);

Avec Ola Hallengren :

EXECUTE dbo.IndexOptimize

    @Databases \= 'Prod',

    @FragmentationLow \= NULL,

    @FragmentationMedium \= 'INDEX\_REORGANIZE,INDEX\_REBUILD\_ONLINE,INDEX\_REBUILD\_OFFLINE',

    @FragmentationHigh \= 'INDEX\_REBUILD\_ONLINE,INDEX\_REBUILD\_OFFLINE',

    @FragmentationLevel1 \= 30, @FragmentationLevel2 \= 60,

    @MinNumberOfPages \= 10000,

    @UpdateStatistics \= 'ALL', @OnlyModifiedStatistics \= 'Y',

    @TimeLimit \= 14400, @Resumable \= 'Y', @MaxDOP \= 2,

    @LogToTable \= 'Y';

### Exercice

1. Sur `Posts`, lancer `sp_BlitzIndex` et lire chaque avertissement.  
2. Prendre les trois requêtes les plus lues du chapitre 2, concevoir un seul index couvrant qui les sert toutes si possible.  
3. Mesurer l'impact sur les insertions : chronométrer un `INSERT` de 100 000 lignes avant et après.

---

## 7\. Partitionnement

### Concept

Le partitionnement horizontal découpe une table (et ses index) en morceaux physiques distincts selon la valeur d'une colonne, tout en présentant une seule table logique. Chaque partition peut résider dans un groupe de fichiers différent, être compressée différemment, être maintenue séparément.

Ce que le partitionnement apporte réellement sur une table d'un milliard de lignes :

- Gestion des données : purger un mois de données en quelques millisecondes (`SWITCH` puis `TRUNCATE`) au lieu d'un `DELETE` de 30 millions de lignes qui prend des heures et sature le journal. Charger un mois de la même manière. C'est le gain numéro un.  
- Maintenance : reconstruire les index et mettre à jour les statistiques uniquement sur les partitions actives.  
- Stockage à niveaux : partitions anciennes compressées en columnstore ou en page compression sur du stockage lent, partitions récentes en rowstore sur SSD.  
- Élimination de partitions : une requête filtrée sur la colonne de partition ne lit que les partitions concernées.

Ce qu'il n'apporte pas, contrairement à une idée répandue : ce n'est pas un outil de performance des requêtes en général. Une requête qui ne filtre pas sur la colonne de partition et qui cherche une clé unique doit chercher dans chaque partition (un seek par partition). Un bon index non-cluster fait presque toujours mieux qu'une élimination de partition. Partitionner pour accélérer les `SELECT` est en général une erreur ; partitionner pour gérer le cycle de vie des données est presque toujours un bon choix à cette échelle.

Disponible dans toutes les éditions depuis SQL 2016 SP1.

### Mise en place

Trois objets : une fonction de partition (les bornes), un schéma de partition (les groupes de fichiers), puis la table créée ou reconstruite sur le schéma.

\-- 1\. Fonction : RANGE RIGHT signifie que la borne appartient à la partition de droite.

\--    Pour des dates, RANGE RIGHT sur le premier jour du mois est la convention naturelle.

CREATE PARTITION FUNCTION pf\_Monthly (DATETIME2(0))

AS RANGE RIGHT FOR VALUES (

    '2024-01-01', '2024-02-01', '2024-03-01', '2024-04-01', '2024-05-01', '2024-06-01',

    '2024-07-01', '2024-08-01', '2024-09-01', '2024-10-01', '2024-11-01', '2024-12-01',

    '2025-01-01', '2025-02-01', '2025-03-01'

);

\-- 15 bornes donnent 16 partitions : la première (avant 2024-01-01) et la dernière (à partir de 2025-03-01)

\-- doivent rester vides : ce sont les partitions tampons qui permettent SPLIT et MERGE sans mouvement de données.

\-- 2\. Schéma : tout sur PRIMARY pour commencer, ou un groupe de fichiers par année

CREATE PARTITION SCHEME ps\_Monthly AS PARTITION pf\_Monthly ALL TO (\[PRIMARY\]);

\-- 3\. Table partitionnée : la colonne de partition doit faire partie de toute clé unique

CREATE TABLE dbo.Events (

    EventId    BIGINT IDENTITY NOT NULL,

    EventDate  DATETIME2(0) NOT NULL,

    DeviceId   INT NOT NULL,

    Value      DECIMAL(18,4) NOT NULL,

    CONSTRAINT PK\_Events PRIMARY KEY CLUSTERED (EventDate, EventId)

) ON ps\_Monthly (EventDate);

\-- Index aligné : créé sur le même schéma, il est lui aussi partitionné par EventDate

CREATE INDEX IX\_Events\_Device ON dbo.Events (DeviceId, EventDate) ON ps\_Monthly (EventDate);

Un index est aligné quand il est partitionné selon le même schéma que la table. Seuls les index alignés permettent `SWITCH`. Un index non aligné (par exemple un index unique sur `EventId` seul, sans `EventDate`) rend `SWITCH` impossible ; c'est le compromis à connaître : une contrainte d'unicité sur une colonne autre que la colonne de partition ne peut être garantie par un index aligné.

### RANGE LEFT ou RANGE RIGHT

Avec `RANGE LEFT`, la borne appartient à la partition de gauche. Pour des dates, cela oblige à choisir comme borne la dernière valeur du mois à la précision de la colonne (`2024-01-31 23:59:59`), ce qui est fragile. `RANGE RIGHT` avec le premier jour du mois est plus lisible et sans ambiguïté. Le choix est définitif pour la fonction.

### Migrer une table existante

Reconstruire l'index cluster sur le schéma de partition :

\-- Table existante avec PK cluster sur Id

ALTER TABLE dbo.Events DROP CONSTRAINT PK\_Events;

ALTER TABLE dbo.Events ADD CONSTRAINT PK\_Events PRIMARY KEY CLUSTERED (EventDate, EventId)

    WITH (ONLINE \= ON, DATA\_COMPRESSION \= PAGE) ON ps\_Monthly (EventDate);

\-- Puis recréer chaque index non-cluster avec ON ps\_Monthly (EventDate)

Sur un milliard de lignes, cette opération est longue (des heures), génère un journal énorme et nécessite de l'espace libre équivalent à la table. À planifier, en mode simple ou bulk-logged si le contexte le permet, ou par une approche progressive (nouvelle table partitionnée, bascule par lots, renommage).

### Vérifier le partitionnement

\-- Numéro de partition d'une valeur

SELECT $PARTITION.pf\_Monthly('2024-06-15');

\-- Répartition des lignes

SELECT p.partition\_number, p.rows, prv.value AS boundary, fg.name AS filegroup,

       p.data\_compression\_desc

FROM sys.partitions p

JOIN sys.indexes i ON i.object\_id \= p.object\_id AND i.index\_id \= p.index\_id

JOIN sys.partition\_schemes ps ON ps.data\_space\_id \= i.data\_space\_id

JOIN sys.partition\_functions pf ON pf.function\_id \= ps.function\_id

LEFT JOIN sys.partition\_range\_values prv ON prv.function\_id \= pf.function\_id

       AND prv.boundary\_id \= p.partition\_number \- 1     \-- RANGE RIGHT : la borne est celle de gauche

JOIN sys.destination\_data\_spaces dds ON dds.partition\_scheme\_id \= ps.data\_space\_id

       AND dds.destination\_id \= p.partition\_number

JOIN sys.filegroups fg ON fg.data\_space\_id \= dds.data\_space\_id

WHERE p.object\_id \= OBJECT\_ID('dbo.Events') AND i.index\_id \<= 1

ORDER BY p.partition\_number;

### Élimination de partitions

Dans le plan d'exécution, l'opérateur d'accès affiche `Actual Partition Count` et `Partitions Accessed`. Si toutes les partitions sont lues alors que la requête filtre sur la date, vérifier :

- que le prédicat est SARGable sur la colonne de partition ;  
- que le type du paramètre correspond exactement au type de la colonne (un `DATETIME` contre une colonne `DATETIME2` empêche l'élimination à la compilation) ;  
- que la requête ne passe pas par une jointure dont la date vient d'une autre table (l'élimination se fait alors à l'exécution, ce qui reste possible mais dépend du plan).

\-- Élimination visible dans le plan

SELECT COUNT(\*) FROM dbo.Events WHERE EventDate \>= '2024-06-01' AND EventDate \< '2024-07-01';

\-- Requête explicite sur une partition

SELECT COUNT(\*) FROM dbo.Events WHERE $PARTITION.pf\_Monthly(EventDate) \= 7;

### La fenêtre glissante : SPLIT, SWITCH, MERGE

Le cycle mensuel typique : ajouter une partition pour le mois à venir, sortir la partition la plus ancienne.

\-- 1\. Ajouter le mois prochain. NEXT USED indique dans quel groupe de fichiers.

\--    SPLIT ne doit porter que sur une partition vide, sinon les données sont déplacées (très coûteux, verrous longs).

ALTER PARTITION SCHEME ps\_Monthly NEXT USED \[PRIMARY\];

ALTER PARTITION FUNCTION pf\_Monthly() SPLIT RANGE ('2025-04-01');

\-- 2\. Sortir le mois le plus ancien vers une table de staging de structure identique,

\--    même groupe de fichiers, mêmes index, mêmes contraintes, mêmes compressions.

\--    La cible peut être partitionnée sur le même schéma, ou non partitionnée avec une

\--    contrainte CHECK qui garantit la plage.

CREATE TABLE dbo.Events\_Archive\_202401 (

    EventId BIGINT NOT NULL, EventDate DATETIME2(0) NOT NULL, DeviceId INT NOT NULL, Value DECIMAL(18,4) NOT NULL,

    CONSTRAINT PK\_Events\_Archive\_202401 PRIMARY KEY CLUSTERED (EventDate, EventId) WITH (DATA\_COMPRESSION \= PAGE)

) ON \[PRIMARY\];

CREATE INDEX IX\_Events\_Archive\_202401\_Device ON dbo.Events\_Archive\_202401 (DeviceId, EventDate);

\-- SWITCH est une opération de métadonnées : quelques millisecondes quelle que soit la taille

ALTER TABLE dbo.Events SWITCH PARTITION 2 TO dbo.Events\_Archive\_202401;

\-- 3\. Fusionner la borne devenue inutile (la partition 2 est vide, MERGE ne déplace rien)

ALTER PARTITION FUNCTION pf\_Monthly() MERGE RANGE ('2024-01-01');

\-- 4\. Archiver ou supprimer la table de staging

TRUNCATE TABLE dbo.Events\_Archive\_202401;

DROP TABLE dbo.Events\_Archive\_202401;

Depuis SQL 2016, `TRUNCATE TABLE ... WITH (PARTITIONS (2))` permet de vider une partition sans passer par une table de staging, quand le but est la purge pure.

Le chargement en masse suit la logique inverse : charger dans une table de staging non partitionnée avec une contrainte `CHECK` sur la plage de dates, construire les index, puis `SWITCH` dans la partition cible vide.

### Pièges

- `SPLIT` sur une partition non vide : SQL Server déplace physiquement les lignes, sous verrou exclusif, en journalisant tout. Sur 30 millions de lignes, c'est un incident de production. Toujours garder une partition vide à droite et la scinder avant qu'elle ne reçoive des données. Automatiser la création des partitions futures (job mensuel qui maintient trois mois d'avance).  
- Statistiques : sans `INCREMENTAL`, un `UPDATE STATISTICS` rescanne toute la table.  
- Escalade de verrous : par défaut, elle se fait au niveau table. `ALTER TABLE dbo.Events SET (LOCK_ESCALATION = AUTO)` permet l'escalade au niveau partition, ce qui évite qu'un chargement dans la partition courante verrouille les lectures sur l'historique (chapitre 10).  
- Une requête `TOP N ... ORDER BY EventDate DESC` sur une table partitionnée par `EventDate` peut être plus lente que sur une table non partitionnée : l'ordre n'est garanti qu'à l'intérieur de chaque partition, et SQL Server doit lire un peu de chaque partition puis fusionner. Le plan montre alors un Sort ou un Merge inattendu. Contournement : borner la requête sur la colonne de partition.  
- Le nombre maximum de partitions est de 15 000\. Un partitionnement journalier sur dix ans en approche.

### Générer une table de démonstration volumineuse

Pour s'exercer avec un volume réaliste sans attendre des heures : une table de 200 millions de lignes se génère en une vingtaine de minutes sur un poste SSD et suffit à observer tous les phénomènes.

\-- Générateur de nombres sans table auxiliaire

;WITH L0 AS (SELECT 1 AS c UNION ALL SELECT 1), L1 AS (SELECT 1 AS c FROM L0 a CROSS JOIN L0 b),

L2 AS (SELECT 1 AS c FROM L1 a CROSS JOIN L1 b), L3 AS (SELECT 1 AS c FROM L2 a CROSS JOIN L2 b),

L4 AS (SELECT 1 AS c FROM L3 a CROSS JOIN L3 b), L5 AS (SELECT 1 AS c FROM L4 a CROSS JOIN L4 b),

Nums AS (SELECT ROW\_NUMBER() OVER (ORDER BY (SELECT NULL)) AS n FROM L5)

INSERT INTO dbo.Events WITH (TABLOCK) (EventDate, DeviceId, Value)

SELECT DATEADD(SECOND, n % 39398400, '2024-01-01'),      \-- \~15 mois de secondes

       ABS(CHECKSUM(NEWID())) % 50000,

       RAND(CHECKSUM(NEWID())) \* 1000

FROM Nums WHERE n \<= 10000000;

GO 20   \-- 20 lots de 10 millions

Passer la base en mode de récupération `SIMPLE` sur le lab pour éviter la saturation du journal.

### Exercice

1. Créer `Events` partitionnée, la charger avec 200 millions de lignes.  
2. Comparer `DELETE WHERE EventDate < '2024-02-01'` (l'interrompre après deux minutes) et `SWITCH` \+ `TRUNCATE`.  
3. Vérifier l'élimination de partitions dans le plan avec un paramètre `DATETIME2(0)` puis avec un paramètre `DATETIME`.  
4. Créer une statistique incrémentale et mesurer le temps d'un `UPDATE STATISTICS ... ON PARTITIONS` contre la table entière.  
5. Écrire la procédure de fenêtre glissante mensuelle et la tester.

---

## 8\. Index columnstore

### Concept

Un index rowstore stocke les lignes entières page par page. Un index columnstore stocke chaque colonne séparément, par segments d'environ un million de lignes (les rowgroups), fortement compressés. Deux conséquences :

- une requête qui lit 3 colonnes sur 40 ne lit que 3 segments par rowgroup, pas les 40 ;  
- des valeurs d'une même colonne se compressent extrêmement bien (dictionnaire, run-length, bit packing) : un facteur 5 à 10 par rapport au rowstore non compressé est courant.

Ajouté à cela, le moteur traite les données columnstore en mode batch (batch mode) : des lots de 900 lignes à la fois plutôt que ligne par ligne, ce qui divise le coût CPU des agrégations et des jointures par un facteur important.

Résultat : sur une requête analytique (agrégation, filtre sur plage, peu de colonnes, beaucoup de lignes), le columnstore est typiquement 10 à 100 fois plus rapide que le rowstore. Sur une requête OLTP (une ligne par clé), il est nettement plus lent, car il n'a pas d'arbre B+ : il doit scanner les segments, en s'appuyant sur les métadonnées min/max de chaque segment pour en éliminer.

Sur une table d'un milliard de lignes avec des problèmes de perf, le columnstore est très probablement l'un des leviers les plus rentables, à condition que la charge soit au moins en partie analytique.

### Les deux formes

- Clustered columnstore index (CCI) : la table entière est stockée en columnstore. Il n'y a plus de rowstore. Idéal pour une table de faits historique, chargée par lots, interrogée par agrégation. Toutes les éditions depuis 2016 SP1.  
- Nonclustered columnstore index (NCCI) : la table reste en rowstore (avec sa clé cluster et ses index B+), et un index columnstore est ajouté par-dessus, sur les colonnes utiles à l'analyse. C'est l'analytique opérationnelle (HTAP) : la même table sert les transactions via le rowstore et les rapports via le columnstore. Peut être filtré (`WHERE Status = 'CLOSED'`) pour ne pas indexer les lignes chaudes.

\-- CCI sur une table de faits

CREATE CLUSTERED COLUMNSTORE INDEX CCI\_Events ON dbo.Events

WITH (MAXDOP \= 4\) ON ps\_Monthly (EventDate);

\-- NCCI filtré sur une table OLTP

CREATE NONCLUSTERED COLUMNSTORE INDEX NCCI\_Orders ON dbo.Orders (OrderDate, CustomerId, ProductId, Amount, Quantity)

WHERE Status \= 'CLOSED';

\-- Depuis SQL 2016 : des index B+ non-cluster peuvent coexister avec un CCI

CREATE INDEX IX\_Events\_Device ON dbo.Events (DeviceId) ON ps\_Monthly (EventDate);

### Structure interne : rowgroups et delta store

Un rowgroup compressé contient jusqu'à 1 048 576 lignes. Quand des lignes arrivent :

- un `INSERT` de plus de 102 400 lignes en une fois est compressé directement en un ou plusieurs rowgroups (bulk load) ;  
- une insertion plus petite va dans le delta store, une structure rowstore classique attachée à l'index. Quand un delta rowgroup atteint 1 048 576 lignes, il est fermé (`CLOSED`) et le processus d'arrière-plan tuple mover le compresse ;  
- un `DELETE` ne supprime rien : il marque la ligne dans un bitmap de suppression (`deleted rows`). La ligne reste dans le segment et continue d'être lue puis écartée ;  
- un `UPDATE` est un `DELETE` plus un `INSERT` dans le delta store.

Conséquences pour la performance :

- Des insertions ligne à ligne (trickle inserts) créent des delta rowgroups ouverts qui sont lus en mode ligne, sans compression, sans élimination de segment. Une table alimentée en OLTP pur ne convient pas au CCI ; le NCCI filtré ou un chargement par lots sont les réponses.  
- Des rowgroups trop petits (fermés prématurément par pression mémoire, ou issus de chargements de 150 000 lignes) dégradent la compression et multiplient les segments à lire.  
- Des rowgroups avec beaucoup de lignes supprimées gaspillent de l'IO.

### Diagnostic

\-- État des rowgroups d'une table

SELECT OBJECT\_NAME(rg.object\_id) AS table\_name, i.name, rg.partition\_number,

       rg.row\_group\_id, rg.state\_desc, rg.total\_rows, rg.deleted\_rows,

       rg.size\_in\_bytes / 1024 / 1024 AS size\_mb, rg.trim\_reason\_desc

FROM sys.dm\_db\_column\_store\_row\_group\_physical\_stats rg

JOIN sys.indexes i ON i.object\_id \= rg.object\_id AND i.index\_id \= rg.index\_id

WHERE rg.object\_id \= OBJECT\_ID('dbo.Events')

ORDER BY rg.partition\_number, rg.row\_group\_id;

\-- Synthèse par état

SELECT state\_desc, COUNT(\*) AS rowgroups, SUM(total\_rows) AS rows\_total,

       AVG(total\_rows) AS avg\_rows, SUM(deleted\_rows) AS deleted\_rows

FROM sys.dm\_db\_column\_store\_row\_group\_physical\_stats

WHERE object\_id \= OBJECT\_ID('dbo.Events')

GROUP BY state\_desc;

À surveiller : le nombre de rowgroups `OPEN` (delta store), la moyenne de `total_rows` sur les `COMPRESSED` (idéalement proche du million), le ratio `deleted_rows / total_rows` (au-delà de 10 %, réorganiser), et `trim_reason_desc` qui explique pourquoi un rowgroup a été fermé avant d'atteindre le million (`MEMORY_LIMITATION`, `DICTIONARY_SIZE`, `BULKLOAD`).

\-- Segments : min/max par colonne et rowgroup, base de l'élimination de segments

SELECT c.name AS column\_name, s.segment\_id, s.row\_count, s.min\_data\_id, s.max\_data\_id, s.on\_disk\_size / 1024 AS size\_kb

FROM sys.column\_store\_segments s

JOIN sys.partitions p ON p.hobt\_id \= s.hobt\_id

JOIN sys.index\_columns ic ON ic.object\_id \= p.object\_id AND ic.index\_id \= p.index\_id AND ic.index\_column\_id \= s.column\_id

JOIN sys.columns c ON c.object\_id \= ic.object\_id AND c.column\_id \= ic.column\_id

WHERE p.object\_id \= OBJECT\_ID('dbo.Events')

ORDER BY c.name, s.segment\_id;

L'élimination de segments fonctionne quand les données sont physiquement ordonnées sur la colonne filtrée : chaque segment couvre alors une plage étroite de valeurs et la plupart sont ignorés. Si la table a été chargée dans le désordre, chaque segment couvre toute la plage et rien n'est éliminé. Deux méthodes pour ordonner : créer le CCI sur une table déjà ordonnée par un index cluster rowstore (`CREATE CLUSTERED COLUMNSTORE INDEX ... WITH (DROP_EXISTING = ON, MAXDOP = 1)`, le `MAXDOP = 1` préservant l'ordre), ou en SQL 2022, `CREATE CLUSTERED COLUMNSTORE INDEX ... ORDER (EventDate)`.

Dans le plan d'exécution, l'opérateur Columnstore Index Scan affiche `Actual Number of Locally Aggregated Rows` (agrégation poussée dans le scan) et, via `SET STATISTICS IO`, `segment reads` et `segment skipped`. Le second doit être élevé.

### Maintenance

\-- Compresser les delta rowgroups fermés et ouverts, fusionner les petits rowgroups, purger les lignes supprimées

ALTER INDEX CCI\_Events ON dbo.Events REORGANIZE WITH (COMPRESS\_ALL\_ROW\_GROUPS \= ON);

\-- Une partition

ALTER INDEX CCI\_Events ON dbo.Events REORGANIZE PARTITION \= 15 WITH (COMPRESS\_ALL\_ROW\_GROUPS \= ON);

\-- Rebuild complet d'une partition : recrée les rowgroups de manière optimale, offline

ALTER INDEX CCI\_Events ON dbo.Events REBUILD PARTITION \= 15;

`REORGANIZE` est online et suffit dans la majorité des cas. Le rebuild d'un CCI est offline et très gourmand en mémoire et en CPU ; le réserver aux partitions anciennes, une fois, après la dernière modification.

### Mode batch

Le mode batch a d'abord été réservé aux plans contenant un columnstore. Depuis SQL 2019 (compatibilité 150), Batch Mode on Rowstore permet à l'optimiseur de l'utiliser sur des tables rowstore quand il l'estime rentable (grosses agrégations). Dans le plan, la propriété `Actual Execution Mode` de chaque opérateur indique `Row` ou `Batch`. Un plan mixte est courant : scan en batch, jointure en batch, puis tri final en mode ligne.

Astuce historique encore utile sur SQL 2016 et 2017 : créer un NCCI filtré vide (`WHERE 1 = 0` via une colonne toujours fausse) sur une table pour débloquer le mode batch sur le reste du plan.

### Exercice

1. Sur `Events` (200 millions de lignes, rowstore compressé en page), chronométrer `SELECT DeviceId, AVG(Value), COUNT(*) FROM dbo.Events WHERE EventDate >= '2024-06-01' AND EventDate < '2024-09-01' GROUP BY DeviceId`.  
2. Créer le CCI, relancer, comparer temps, CPU et lectures. Observer `segment skipped`.  
3. Insérer 50 000 lignes ligne à ligne (boucle), constater le delta rowgroup, chronométrer à nouveau, puis `REORGANIZE`.  
4. Comparer la taille de la table via `sp_spaceused` avant et après.

---

## 9\. Compression de données

### Concept

Deux niveaux pour le rowstore :

- Row compression : stockage à longueur variable des types à longueur fixe (`INT` stocké sur 1 octet si la valeur le permet, `CHAR(50)` sans les espaces de fin). Gain modeste (10 à 30 %), coût CPU quasi nul.  
- Page compression : row compression, plus déduplication des préfixes communs par colonne dans la page, plus dictionnaire des valeurs répétées dans la page. Gain fréquent de 40 à 70 %, coût CPU de quelques pourcents sur les écritures et lectures décompressées.

L'intérêt principal n'est pas le disque : c'est que les pages compressées restent compressées dans le buffer pool. Une table de 800 Go compressée à 300 Go tient bien mieux dans 256 Go de RAM, et chaque lecture physique ramène deux fois plus de lignes. Sur une instance en `PAGEIOLATCH`, la page compression est souvent le gain le plus simple à obtenir.

Depuis SQL 2016 SP1, disponible dans toutes les éditions.

### Estimer et appliquer

\-- Estimation sur un échantillon, par index et par partition

EXEC sp\_estimate\_data\_compression\_savings

    @schema\_name \= 'dbo', @object\_name \= 'Events',

    @index\_id \= NULL, @partition\_number \= NULL, @data\_compression \= 'PAGE';

\-- Appliquer à toute la table (index cluster) et à un index

ALTER TABLE dbo.Events REBUILD WITH (DATA\_COMPRESSION \= PAGE, ONLINE \= ON);

ALTER INDEX IX\_Events\_Device ON dbo.Events REBUILD WITH (DATA\_COMPRESSION \= PAGE, ONLINE \= ON);

\-- Par partition : les anciennes en PAGE, la partition courante en ROW ou NONE pour les insertions rapides

ALTER TABLE dbo.Events REBUILD PARTITION \= ALL

WITH (DATA\_COMPRESSION \= PAGE ON PARTITIONS (1 TO 14),

      DATA\_COMPRESSION \= ROW  ON PARTITIONS (15 TO 16));

\-- État actuel

SELECT OBJECT\_NAME(p.object\_id) AS table\_name, i.name, p.partition\_number, p.data\_compression\_desc, p.rows

FROM sys.partitions p JOIN sys.indexes i ON i.object\_id \= p.object\_id AND i.index\_id \= p.index\_id

WHERE p.object\_id \= OBJECT\_ID('dbo.Events');

### Quand ne pas compresser

- Colonnes déjà compressées ou aléatoires (`VARBINARY` de fichiers, GUID, données chiffrées) : gain nul, coût CPU pour rien.  
- Instance déjà saturée en CPU et dont la donnée tient entièrement en mémoire : la compression ajoute du CPU sans réduire les IO.  
- Tables très petites et très mises à jour : le gain est négligeable.

Règle pratique : page compression sur les index dont le ratio `user_updates / (user_seeks + user_scans)` est faible (données lues plus qu'écrites), row compression sur les autres, et mesurer avec `sp_estimate_data_compression_savings` avant.

### Exercice

Estimer puis appliquer la page compression sur `Posts`, `Votes` et `Comments`. Mesurer la PLE et les `PAGEIOLATCH` sous la charge de l'exercice du chapitre 2, avant et après.

---

## 10\. Verrouillage, isolation et concurrence

### Concept

Chaque lecture en `READ COMMITTED` (le niveau par défaut) prend un verrou partagé (S) sur la ligne ou la page le temps de la lire ; chaque écriture prend un verrou exclusif (X) jusqu'à la fin de la transaction. Un lecteur bloque un écrivain, un écrivain bloque un lecteur. Sur une base OLTP volumineuse avec des rapports qui scannent des millions de lignes pendant que des transactions écrivent, c'est la source principale des attentes `LCK_M_*` et des deadlocks.

### Diagnostic du blocage

\-- En direct : qui bloque qui

EXEC sp\_WhoIsActive @find\_block\_leaders \= 1, @get\_locks \= 1;

\-- Verrous détenus et attendus

SELECT tl.request\_session\_id, tl.resource\_type, tl.resource\_database\_id,

       OBJECT\_NAME(p.object\_id) AS object\_name, tl.request\_mode, tl.request\_status, tl.resource\_description

FROM sys.dm\_tran\_locks tl

LEFT JOIN sys.partitions p ON p.hobt\_id \= tl.resource\_associated\_entity\_id

WHERE tl.resource\_type \<\> 'DATABASE'

ORDER BY tl.request\_session\_id;

\-- Historique : activer le rapport de processus bloqués (seuil en secondes)

EXEC sp\_configure 'show advanced options', 1; RECONFIGURE;

EXEC sp\_configure 'blocked process threshold (s)', 5; RECONFIGURE;

\-- Puis créer une session d'événements étendus qui capture sqlserver.blocked\_process\_report

\-- et sqlserver.xml\_deadlock\_report vers un fichier. sp\_BlitzLock analyse les deadlocks capturés

\-- (aussi disponibles dans la session system\_health par défaut).

EXEC sp\_BlitzLock;

Les colonnes `row_lock_wait_in_ms` et `page_lock_wait_in_ms` de `sys.dm_db_index_operational_stats` (chapitre 6\) indiquent quels index concentrent les attentes de verrous.

### Escalade de verrous

SQL Server verrouille au niveau ligne ou page. Quand une instruction détient environ 5 000 verrous sur un même objet (ou que la mémoire des verrous dépasse un seuil), il tente de les remplacer par un seul verrou de table : c'est l'escalade. Un `UPDATE` de 100 000 lignes verrouille donc toute la table jusqu'au commit, bloquant toutes les autres sessions, y compris celles qui travaillent sur des lignes sans rapport.

\-- Compter les escalades

SELECT OBJECT\_NAME(object\_id) AS table\_name, index\_id, partition\_number,

       index\_lock\_promotion\_attempt\_count, index\_lock\_promotion\_count

FROM sys.dm\_db\_index\_operational\_stats(DB\_ID(), NULL, NULL, NULL)

WHERE index\_lock\_promotion\_count \> 0

ORDER BY index\_lock\_promotion\_count DESC;

\-- Sur une table partitionnée : escalader au niveau partition plutôt que table

ALTER TABLE dbo.Events SET (LOCK\_ESCALATION \= AUTO);

\-- Interdire l'escalade (le nombre de verrous et la mémoire consommée augmentent)

ALTER TABLE dbo.Events SET (LOCK\_ESCALATION \= DISABLE);

La vraie réponse à l'escalade est de traiter les modifications de masse par lots (batching) : des transactions de 2 000 à 5 000 lignes, sous le seuil, avec une pause éventuelle entre les lots.

DECLARE @rows INT \= 1;

WHILE @rows \> 0

BEGIN

    DELETE TOP (4000) FROM dbo.Events WHERE EventDate \< '2024-01-01';

    SET @rows \= @@ROWCOUNT;

    \-- WAITFOR DELAY '00:00:00.100'; si le journal ou l'AG peine à suivre

END

Sur un milliard de lignes, cette boucle reste lente ; le `SWITCH` de partition (chapitre 7\) est la solution structurelle.

### Read Committed Snapshot Isolation (RCSI)

RCSI change le comportement du niveau `READ COMMITTED` : les lecteurs ne prennent plus de verrous partagés et lisent la dernière version validée de la ligne, conservée dans le version store de TempDB. Les lecteurs ne bloquent plus les écrivains, les écrivains ne bloquent plus les lecteurs. Les écrivains continuent de se bloquer entre eux.

\-- Nécessite qu'aucune autre session ne soit connectée, ou de les couper

ALTER DATABASE \[Prod\] SET READ\_COMMITTED\_SNAPSHOT ON WITH ROLLBACK IMMEDIATE;

\-- Vérifier

SELECT name, is\_read\_committed\_snapshot\_on, snapshot\_isolation\_state\_desc FROM sys.databases;

C'est le comportement par défaut d'Azure SQL Database et de la majorité des autres SGBD (PostgreSQL, Oracle). Sur une base OLTP qui souffre de blocages lecture/écriture, c'est souvent le changement au meilleur rapport gain / risque. Points de vigilance :

- TempDB : le version store y stocke les versions. Une transaction longue empêche le nettoyage et fait grossir TempDB. Surveiller `sys.dm_tran_version_store_space_usage` et `sys.dm_tran_active_snapshot_database_transactions`.  
- 14 octets ajoutés à chaque ligne modifiée (pointeur de version) : léger grossissement et quelques page splits au début.  
- Sémantique : une requête qui lit une valeur pour décider d'une écriture (`IF NOT EXISTS ... INSERT`, files d'attente en table) peut lire une version obsolète. Ces schémas nécessitent des hints `UPDLOCK` ou une logique adaptée. Auditer les procédures de ce type avant d'activer.

`SNAPSHOT ISOLATION` (`ALLOW_SNAPSHOT_ISOLATION ON`) est la variante au niveau transaction : cohérence de toute la transaction à un instant donné, avec détection de conflit d'écriture (erreur 3960). Utile pour les rapports longs, à activer par session avec `SET TRANSACTION ISOLATION LEVEL SNAPSHOT`.

### Deadlocks

Deux sessions qui attendent chacune un verrou détenu par l'autre. SQL Server en détecte un toutes les 5 secondes et tue la victime (celle qui coûte le moins à annuler, ou celle avec `DEADLOCK_PRIORITY` la plus basse). Le graphe est dans `system_health` :

EXEC sp\_BlitzLock @StartDate \= '2026-09-01';

Causes récurrentes : deux procédures qui modifient les mêmes tables dans un ordre différent, un index manquant qui force un scan (donc des verrous sur des lignes non ciblées), des Key Lookups entre index non-cluster et cluster sur des `UPDATE` concurrents. Correctifs : ordre d'accès cohérent, index qui rendent les écritures chirurgicales, RCSI pour retirer les lecteurs de l'équation, transactions plus courtes.

### Exercice

1. Ouvrir une transaction dans une session qui met à jour une ligne de `Users` sans commit. Dans une autre, lire cette table : blocage. Observer avec `sp_WhoIsActive`.  
2. Activer RCSI, recommencer : plus de blocage. Vérifier le version store dans TempDB.  
3. Exécuter un `UPDATE` de 20 000 lignes, constater l'escalade dans `sys.dm_db_index_operational_stats`, puis le réécrire par lots.

---

## 11\. Configuration de l'instance

Ces réglages se vérifient en une heure à l'arrivée sur une instance inconnue. `sp_Blitz` les signale presque tous, mais il faut comprendre pourquoi.

### Parallélisme

SELECT name, value\_in\_use FROM sys.configurations

WHERE name IN ('max degree of parallelism', 'cost threshold for parallelism', 'max server memory (MB)',

               'optimize for ad hoc workloads', 'backup compression default', 'remote admin connections');

- `cost threshold for parallelism` : coût estimé à partir duquel l'optimiseur envisage un plan parallèle. Valeur par défaut : 5, fixée en 1997\. Aujourd'hui, une valeur entre 40 et 75 est le point de départ habituel : les petites requêtes restent en série (moins de `CXPACKET`, moins de threads consommés), les grosses restent parallèles. Ajuster en regardant dans le Query Store le coût des requêtes qui bénéficient réellement du parallélisme.  
- `max degree of parallelism` : nombre de threads maximum par requête. Règle Microsoft : par nœud NUMA, jusqu'à 8 cœurs logiques, MAXDOP \= nombre de cœurs ; au-delà, MAXDOP \= 8 (ou la moitié des cœurs du nœud). Une valeur de 0 (défaut) sur un serveur à 64 cœurs laisse une seule requête analytique saturer tout le serveur. Depuis SQL 2019, l'installation propose une valeur calculée. Peut aussi se régler par base (`ALTER DATABASE SCOPED CONFIGURATION SET MAXDOP = 8`).

EXEC sp\_configure 'show advanced options', 1; RECONFIGURE;

EXEC sp\_configure 'cost threshold for parallelism', 50; RECONFIGURE;

EXEC sp\_configure 'max degree of parallelism', 8; RECONFIGURE;

### Mémoire

- `max server memory` : à fixer pour laisser à Windows et aux autres processus ce dont ils ont besoin. Ordre de grandeur : total moins 4 Go pour l'OS moins 1 Go par tranche de 8 Go au-delà de 16 Go, moins ce que consomment les autres services (agent de sauvegarde, antivirus, autres instances). Ne jamais laisser la valeur par défaut (2 To).  
- Vérifier la pression mémoire : `Memory Grants Pending` supérieur à 0 de manière soutenue, PLE qui s'effondre, `RESOURCE_SEMAPHORE` dans les wait stats.

\-- Allocations mémoire en cours et en attente

SELECT session\_id, requested\_memory\_kb, granted\_memory\_kb, used\_memory\_kb, max\_used\_memory\_kb,

       ideal\_memory\_kb, wait\_time\_ms, query\_cost, dop

FROM sys.dm\_exec\_query\_memory\_grants

ORDER BY requested\_memory\_kb DESC;

\-- Répartition du buffer pool par base

SELECT DB\_NAME(database\_id) AS db, COUNT(\*) \* 8 / 1024 AS cached\_mb

FROM sys.dm\_os\_buffer\_descriptors GROUP BY database\_id ORDER BY cached\_mb DESC;

Une requête reçoit par défaut jusqu'à 25 % de la mémoire de requêtes (`max server memory` moins le buffer pool). Quatre requêtes avec une allocation surestimée suffisent à faire attendre toutes les autres. Correctifs : améliorer les estimations, `OPTION (MAX_GRANT_PERCENT = 10)`, Resource Governor pour plafonner le pool par défaut (`REQUEST_MAX_MEMORY_GRANT_PERCENT`), et depuis SQL 2017/2019 le memory grant feedback qui ajuste automatiquement l'allocation après quelques exécutions (persisté dans le Query Store en 2022).

### TempDB

TempDB sert aux tris, hachages, tables temporaires, version store et reconstructions d'index. Sur une base volumineuse il est sollicité en permanence.

SELECT name, physical\_name, size \* 8 / 1024 AS size\_mb, growth, is\_percent\_growth

FROM sys.master\_files WHERE database\_id \= 2;

\-- Contention d'allocation : attentes PAGELATCH sur les pages PFS/GAM/SGAM de tempdb

SELECT session\_id, wait\_type, wait\_duration\_ms, resource\_description

FROM sys.dm\_os\_waiting\_tasks

WHERE wait\_type LIKE 'PAGELATCH%' AND resource\_description LIKE '2:%';

Réglages : autant de fichiers de données que de cœurs logiques jusqu'à 8, tous de la même taille, même autogrowth en Mo (pas en pourcentage), pré-dimensionnés à la taille maximale observée pour ne jamais grossir en journée, sur le stockage le plus rapide disponible. SQL 2019 ajoute les métadonnées TempDB en mémoire (`ALTER SERVER CONFIGURATION SET MEMORY_OPTIMIZED TEMPDB_METADATA = ON`) pour les charges qui créent des milliers de tables temporaires par seconde. SQL 2022 supprime la contention sur les pages GAM et SGAM.

### Journal de transactions et fichiers

\-- Nombre et taille des VLF : au-delà de quelques centaines, la récupération et les sauvegardes ralentissent

SELECT DB\_NAME(database\_id) AS db, COUNT(\*) AS vlf\_count, MIN(vlf\_size\_mb) AS min\_mb, MAX(vlf\_size\_mb) AS max\_mb

FROM sys.dm\_db\_log\_info(DB\_ID('Prod')) GROUP BY database\_id;

\-- Autogrowth : jamais en pourcentage, jamais 1 Mo (valeurs historiques par défaut)

SELECT DB\_NAME(database\_id), name, type\_desc, size \* 8 / 1024 AS size\_mb,

       CASE is\_percent\_growth WHEN 1 THEN CAST(growth AS VARCHAR) \+ ' %' ELSE CAST(growth \* 8 / 1024 AS VARCHAR) \+ ' MB' END AS growth

FROM sys.master\_files ORDER BY database\_id;

\-- Instant File Initialization : sans lui, chaque croissance de fichier de données remplit de zéros

SELECT servicename, instant\_file\_initialization\_enabled FROM sys.dm\_server\_services;

Un journal qui a grossi par petits incréments contient des milliers de VLF minuscules. Correctif : sauvegarde du log, `DBCC SHRINKFILE` du log à une taille minimale, puis regrossir en une fois par tranches de 8 Go maximum (à cause d'un algorithme interne de découpe des VLF). Fixer ensuite un autogrowth de 1 à 4 Go.

### Options de base

SELECT name, compatibility\_level, is\_auto\_create\_stats\_on, is\_auto\_update\_stats\_on,

       is\_auto\_update\_stats\_async\_on, is\_read\_committed\_snapshot\_on, is\_auto\_shrink\_on,

       is\_auto\_close\_on, page\_verify\_option\_desc, is\_query\_store\_on, recovery\_model\_desc, target\_recovery\_time\_in\_seconds

FROM sys.databases;

`auto_shrink` doit être désactivé (fragmentation garantie), `page_verify` doit être `CHECKSUM`, `target_recovery_time` à 60 (checkpoint indirect, défaut depuis 2016).

### Intelligent Query Processing

Famille de fonctionnalités activées par le niveau de compatibilité, sans changer le code :

| Fonctionnalité | Version | Effet |
| :---- | :---- | :---- |
| Batch mode on rowstore | 2019 (150) | Mode batch sans columnstore |
| Adaptive joins | 2017 (140, columnstore) / 2019 (rowstore) | Choix Nested Loops ou Hash à l'exécution selon le nombre de lignes réel |
| Memory grant feedback | 2017 / 2019 / persisté en 2022 | Corrige l'allocation mémoire d'un plan après quelques exécutions |
| Interleaved execution | 2017 | Estimation correcte des fonctions table multi-instructions |
| Scalar UDF inlining | 2019 | Transforme une fonction scalaire en expression relationnelle |
| Table variable deferred compilation | 2019 | Estime le vrai nombre de lignes d'une variable table au lieu de 1 |
| Parameter sensitive plan optimization | 2022 (160) | Plusieurs plans par requête selon la valeur du paramètre |
| DOP feedback | 2022 | Réduit le degré de parallélisme des requêtes qui en abusent |
| Cardinality estimation feedback | 2022 | Teste des hypothèses CE alternatives et conserve celle qui marche |
| Optimized plan forcing | 2022 | Compilation plus rapide des plans forcés |

Chacune peut être désactivée individuellement par `ALTER DATABASE SCOPED CONFIGURATION` si elle cause une régression, ce qui permet de monter de niveau de compatibilité et de ne reculer que sur une fonctionnalité.

SELECT name, value FROM sys.database\_scoped\_configurations;

ALTER DATABASE SCOPED CONFIGURATION SET PARAMETER\_SENSITIVE\_PLAN\_OPTIMIZATION \= OFF;

### Cache de plans et SQL ad hoc

Si l'application envoie des requêtes non paramétrées (littéraux dans le texte), chaque variante crée un plan en cache utilisé une seule fois. Symptômes : cache de plans de plusieurs Go, `SQL Compilations/sec` élevé, Query Store envahi.

\-- Plans à usage unique dans le cache

SELECT objtype, COUNT(\*) AS plans, SUM(CAST(size\_in\_bytes AS BIGINT)) / 1024 / 1024 AS size\_mb,

       SUM(CASE WHEN usecounts \= 1 THEN 1 ELSE 0 END) AS single\_use

FROM sys.dm\_exec\_cached\_plans GROUP BY objtype;

EXEC sp\_configure 'optimize for ad hoc workloads', 1; RECONFIGURE;   \-- ne stocke un stub qu'à la première exécution

ALTER DATABASE \[Prod\] SET PARAMETERIZATION FORCED;                    \-- remplace les littéraux par des paramètres (à tester : réintroduit le sniffing)

### Exercice

Passer `sp_Blitz` sur le lab avec les réglages par défaut de l'installation, corriger chaque point, relancer. Faire de même avec la liste de ce chapitre, sans `sp_Blitz`, pour s'assurer de savoir retrouver chaque information soi-même.

---

## 12\. Checklist de prise en main d'une instance inconnue

Première journée sur une instance jamais vue. Ordre recommandé, en lecture seule.

### Heure 1 : l'instance

SELECT @@VERSION;

SELECT \* FROM sys.dm\_os\_sys\_info;             \-- cœurs, mémoire physique, date de démarrage, hyperviseur

SELECT \* FROM sys.dm\_os\_nodes;                \-- topologie NUMA

EXEC sp\_Blitz @CheckServerInfo \= 1;

Relever : version et CU (est-elle supportée, y a-t-il des correctifs de perf connus manquants ?), édition, RAM, cœurs, uptime (des wait stats sur 6 mois ne veulent plus rien dire), virtualisation, `max server memory`, MAXDOP, cost threshold, TempDB, IFI, dernière sauvegarde, dernier `CHECKDB`.

### Heure 2 : la base

EXEC sp\_helpdb 'Prod';

SELECT \* FROM sys.database\_scoped\_configurations;

SELECT \* FROM sys.database\_query\_store\_options;

\-- Les 20 plus grosses tables

SELECT TOP 20 OBJECT\_SCHEMA\_NAME(ps.object\_id) \+ '.' \+ OBJECT\_NAME(ps.object\_id) AS table\_name,

       SUM(CASE WHEN ps.index\_id \<= 1 THEN ps.row\_count END) AS rows\_count,

       SUM(ps.reserved\_page\_count) \* 8 / 1024 / 1024 AS reserved\_gb,

       COUNT(DISTINCT ps.index\_id) AS index\_count,

       MAX(CASE WHEN i.type IN (5,6) THEN 1 ELSE 0 END) AS has\_columnstore,

       MAX(CASE WHEN ps.partition\_number \> 1 THEN 1 ELSE 0 END) AS is\_partitioned

FROM sys.dm\_db\_partition\_stats ps

JOIN sys.indexes i ON i.object\_id \= ps.object\_id AND i.index\_id \= ps.index\_id

GROUP BY ps.object\_id ORDER BY reserved\_gb DESC;

Relever : niveau de compatibilité, modèle de récupération, RCSI, statistiques auto (sync/async), Query Store (actif, taille, mode), taille des fichiers et croissance, VLF, les tables qui comptent (volume, index, partitionnement, compression, columnstore).

### Heure 3 : la charge

EXEC sp\_BlitzFirst @Seconds \= 60, @ExpertMode \= 1;    \-- plusieurs fois, à des moments différents de la journée

EXEC sp\_BlitzCache @SortOrder \= 'cpu';

EXEC sp\_BlitzCache @SortOrder \= 'reads';

EXEC sp\_BlitzCache @SortOrder \= 'duration';

EXEC sp\_BlitzIndex @DatabaseName \= 'Prod', @Mode \= 4;

\-- Query Store : top requêtes sur 7 jours, requêtes à plans multiples, plans forcés existants

Relever : profil des attentes, top 10 requêtes par ressource, index manquants consolidés, index inutilisés, plans forcés et leur raison, requêtes à plusieurs plans.

### Heure 4 : la maintenance et l'historique

- Jobs de l'Agent : que fait la maintenance, à quelle heure, combien de temps, échecs récents (`msdb.dbo.sysjobhistory`).  
- Journal des erreurs : erreurs IO longues, dumps, basculements.  
- Historique de croissance des fichiers (trace par défaut : `sys.fn_trace_gettable` sur l'événement 92/93).  
- La question aux équipes : quels sont les traitements qui font mal, à quel moment, depuis quand, et qu'a-t-on déjà tenté. Comment ont été obtenus les gains récents : un index, une réécriture, la compression, le columnstore, un changement de version ou de matériel ? La réponse indique la maturité de l'existant et le prochain levier probable.

### Ce qu'il ne faut pas faire la première semaine

Modifier un réglage d'instance sans mesure avant et après, supprimer un index parce qu'il apparaît inutilisé depuis le dernier redémarrage, lancer un rebuild d'index sur la grosse table, changer le niveau de compatibilité sans Query Store actif depuis au moins une semaine, activer RCSI sans avoir audité les procédures de type "vérifier puis insérer".

---

## 13\. Programme d'entraînement

Sur six semaines à raison de quelques heures par semaine. Chaque semaine se termine par un exercice sur le lab, sans lequel la lecture ne s'ancre pas.

| Semaine | Thème | Lecture | Exercice sur le lab |
| :---- | :---- | :---- | :---- |
| 1 | Lab, méthodologie, wait stats, DMV | Vidéo How to Think Like the SQL Server Engine avec les pages imprimées ; épisodes 1 à 6 ; chapitres 1 et 2 | Charge SQLQueryStress, diagnostic du général au particulier, correction par index |
| 2 | Plans d'exécution | Chapitre 3 ; Grant Fritchey, SQL Server Execution Plans (gratuit chez Redgate) | Dix plans de StackOverflow à annoter : estimé vs réel, avertissements, opérateur coûteux réel |
| 3 | Query Store, statistiques, sniffing | Chapitres 4 et 5 ; Erik Darling et Brent Ozar sur le parameter sniffing | Régression de plan provoquée puis corrigée par forçage, puis par index, puis par PSP en compat 160 |
| 4 | Index rowstore, maintenance | Chapitre 6 ; Kendra Little, Brent Ozar sur l'index tuning | sp\_BlitzIndex sur StackOverflow, dédoublonnage et consolidation, mesure du coût sur les insertions |
| 5 | Partitionnement, compression | Chapitres 7 et 9 ; Kendra Little sur le partitionnement ; Korotkevitch, Pro SQL Server Internals, chapitres partitionnement | Events à 200 M de lignes, fenêtre glissante, comparaison DELETE vs SWITCH, compression par partition |
| 6 | Columnstore, concurrence, configuration | Chapitres 8, 10, 11 ; Niko Neugebauer sur le columnstore ; Paul White sur le mode batch | CCI vs rowstore sur agrégations, delta store et réorganisation, RCSI et version store, checklist complète |

Ressources de référence pour aller plus loin :

- Dmitri Korotkevitch, Pro SQL Server Internals, 2e édition : le meilleur livre sur les structures internes et les grandes tables.  
- Grant Fritchey, SQL Server 2022 Query Performance Tuning : le parcours complet du tuning de requêtes.  
- Itzik Ben-Gan, T-SQL Querying : pour les réécritures de requêtes.  
- sqlperformance.com (Paul White, Aaron Bertrand, Erin Stellato) : articles de référence sur le CE, le mode batch, le Query Store.  
- Brent Ozar, cours Fundamentals of Index Tuning, Query Tuning, Parameter Sniffing.  
- SQLskills (Paul Randal, Kimberly Tripp, Jonathan Kehayias) : statistiques, fragmentation, wait stats.  
- Documentation Microsoft : Query Processing Architecture Guide, Index Architecture and Design Guide, Columnstore indexes design guidance. Trois documents longs et denses qui valent la lecture intégrale.

