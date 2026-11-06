from collector.text_utils import matches_topic, normalize


def test_normalize_strips_accents_and_case():
    assert normalize("  DÉCÈS   du Président ") == "deces du president"


def test_matches_topic_is_accent_and_case_insensitive():
    assert matches_topic("Le décès de JACQUES CHIRAC", ["jacques chirac"])


def test_matches_topic_rejects_unrelated_text():
    assert not matches_topic("Match de football ce soir", ["Chirac"])


def test_empty_keywords_never_match():
    assert not matches_topic("anything", ["", "  "])
