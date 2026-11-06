import pytest

from collector.graph_client import GraphAPIError, GraphClient, GraphRateLimitError


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload, self.status_code = payload, status_code

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append((url, params, headers))
        return self._responses.pop(0)


def test_paginate_follows_next_links_and_sends_token_in_header():
    session = FakeSession(
        [
            FakeResponse({"data": [{"id": "1"}, {"id": "2"}], "paging": {"next": "https://graph.facebook.com/v23.0/next"}}),
            FakeResponse({"data": [{"id": "3"}]}),
        ]
    )
    client = GraphClient("TOKEN", session=session)
    items = list(client.paginate("page/posts"))
    assert [i["id"] for i in items] == ["1", "2", "3"]
    assert session.calls[0][2]["Authorization"] == "Bearer TOKEN"
    assert "TOKEN" not in session.calls[0][0]


def test_paginate_respects_max_items():
    session = FakeSession([FakeResponse({"data": [{"id": str(i)} for i in range(10)]})])
    client = GraphClient("T", session=session)
    assert len(list(client.paginate("x", max_items=3))) == 3


def test_paginate_with_zero_items_does_not_make_a_request():
    session = FakeSession([])

    assert list(GraphClient("T", session=session).paginate("x", max_items=0)) == []
    assert session.calls == []


def test_paginate_rejects_next_url_on_another_host():
    session = FakeSession(
        [FakeResponse({"data": [], "paging": {"next": "https://example.com/steal-token"}})]
    )

    with pytest.raises(GraphAPIError, match="Invalid pagination URL"):
        list(GraphClient("T", session=session).paginate("x"))
    assert len(session.calls) == 1


def test_api_error_is_raised():
    session = FakeSession([FakeResponse({"error": {"message": "bad", "code": 100}}, 400)])
    with pytest.raises(GraphAPIError) as info:
        GraphClient("T", session=session).get("x")
    assert info.value.code == 100


def test_rate_limit_error_is_distinguished():
    session = FakeSession([FakeResponse({"error": {"message": "limit", "code": 4}}, 400)])
    with pytest.raises(GraphRateLimitError):
        GraphClient("T", session=session).get("x")
