# Social Collector

Connecteur Python pour collecter, via les API officielles de Meta, des publications Facebook et Instagram associées à un sujet, puis les enregistrer dans MongoDB.

Le projet récupère le texte, les images et les commentaires lorsque Meta autorise leur accès. Les mots-clés sont filtrés localement sans tenir compte des majuscules ou des accents.

## Fonctionnalités

- Facebook : parcours des publications des Pages indiquées avec `--fb-pages`.
- Instagram : recherche de publications par hashtag et, en option, parcours des médias d’un compte professionnel.
- Images : téléchargement limité à 10 Mo par image, validation du type MIME et déduplication par SHA-256.
- MongoDB : documents de publications et de commentaires; binaires d’images dans GridFS.
- Robustesse : pagination, retries sur les erreurs transitoires, limites de collecte configurables et upserts pour éviter les doublons.
- Tests hors ligne avec des réponses API simulées et `mongomock`.

## Prérequis

- Python 3.9 ou plus récent.
- Un compte Meta et un jeton d’accès Graph API disposant des autorisations requises pour les Pages ou le compte Instagram cible.
- Une instance MongoDB locale ou un cluster MongoDB Atlas.

L’API Graph est l’interface officielle de Meta utilisée par le connecteur. Elle ne permet pas une recherche Facebook globale par mot-clé : le programme parcourt les Pages auxquelles le jeton a accès, puis applique le filtre localement. La recherche Instagram par hashtag requiert un compte professionnel lié à une Page Facebook et reste soumise aux limites et autorisations de Meta.

## Installation

```bash
python -m venv .venv
```

Activez l’environnement virtuel, puis installez les dépendances :

```bash
python -m pip install -r requirements.txt
```

Copiez `.env.example` vers `.env` et renseignez le jeton Meta ainsi que l’URI MongoDB. Le fichier `.env` est exclu du dépôt.

```text
META_ACCESS_TOKEN=your_meta_access_token
GRAPH_API_VERSION=v23.0
MONGO_URI=mongodb://localhost:27017
MONGO_DB=social_collector
```

Pour Atlas, `MONGO_URI` peut contenir l’URI `mongodb+srv://...` fourni par Atlas. Les configurations existantes qui utilisent `MONGODB_URI` sont aussi prises en charge. Les noms d’utilisateur et mots de passe MongoDB doivent être ceux d’un utilisateur de base de données Atlas; les caractères spéciaux du mot de passe doivent être encodés dans l’URI.

## Utilisation

Collecte Facebook :

```bash
python main.py --topic "Décès de Jacques Chirac" \
  --keywords "Jacques Chirac" "Chirac" \
  --platform facebook --fb-pages PAGE_ID --limit 50
```

Collecte Instagram par hashtag :

```bash
python main.py --topic "Décès de Jacques Chirac" \
  --keywords "Jacques Chirac" "Chirac" \
  --platform instagram --ig-user-id INSTAGRAM_ACCOUNT_ID \
  --ig-hashtags jacqueschirac --limit 50
```

`--platform` accepte `facebook`, `instagram` ou `all`. `--ig-own-media` ajoute les médias du compte Instagram professionnel. Chaque plateforme respecte sa propre limite `--limit`.

## Stockage

La base par défaut est `social_collector`. Les collections principales sont :

- `posts` : une publication par couple plateforme/identifiant, avec les identifiants GridFS des images.
- `comments` : commentaires liés à leur publication.
- `images.files` et `images.chunks` : images conservées dans un bucket GridFS.

Les index uniques et les upserts rendent les relances idempotentes. Le smoke test utilise une base temporaire dédiée, vérifie les insertions et les doublons, puis supprime cette base :

```bash
python check_mongo.py
```

Le smoke test écrit et supprime des données dans MongoDB; il ne lance pas de collecte Meta.

## Tests

```bash
python -m pytest
```

Les tests couvrent le client API, la pagination, les collecteurs, le filtrage, le pipeline et le stockage simulé. Ils n’ont besoin ni d’un accès Meta actif ni d’une instance MongoDB réelle.

## Structure

```text
main.py                   Interface en ligne de commande
collector/config.py       Configuration d’environnement
collector/models.py       Modèles Post et Comment
collector/graph_client.py Client HTTP Meta Graph API
collector/facebook.py     Collecteur Facebook
collector/instagram.py    Collecteur Instagram
collector/images.py       Téléchargement et validation des images
collector/text_utils.py   Normalisation et filtrage des mots-clés
collector/storage.py      Persistance MongoDB et GridFS
collector/pipeline.py     Orchestration de la collecte
check_mongo.py            Smoke test MongoDB réel
tests/                    Tests hors ligne
```

## Auteur

`louaybannani002`
