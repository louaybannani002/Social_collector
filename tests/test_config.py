from collector.config import mongo_uri_from_env


def test_mongo_uri_supports_existing_mongodb_uri_name(monkeypatch):
    monkeypatch.delenv("MONGO_URI", raising=False)
    monkeypatch.setenv("MONGODB_URI", "mongodb+srv://user:secret@example.mongodb.net/db")

    assert mongo_uri_from_env() == "mongodb+srv://user:secret@example.mongodb.net/db"


def test_mongo_uri_prefers_documented_name_when_both_are_set(monkeypatch):
    monkeypatch.setenv("MONGO_URI", "mongodb://preferred/db")
    monkeypatch.setenv("MONGODB_URI", "mongodb://legacy/db")

    assert mongo_uri_from_env() == "mongodb://preferred/db"
