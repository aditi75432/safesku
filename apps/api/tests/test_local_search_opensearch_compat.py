from apps.api.app.local_search import LocalOpenSearch, INDEX_NAME


class _FakeIndices:
    def __init__(self):
        self.exists_calls = []
        self.create_calls = []
        self.refresh_calls = []

    def exists(self, **kwargs):
        self.exists_calls.append(kwargs)
        return False

    def create(self, **kwargs):
        self.create_calls.append(kwargs)
        return {"acknowledged": True}

    def refresh(self, **kwargs):
        self.refresh_calls.append(kwargs)


class _FakeClient:
    def __init__(self):
        self.indices = _FakeIndices()


def test_ensure_index_uses_keyword_only_opensearch3_api():
    adapter = LocalOpenSearch.__new__(LocalOpenSearch)
    adapter.client = _FakeClient()

    adapter.ensure_index()

    assert adapter.client.indices.exists_calls == [{"index": INDEX_NAME}]
    assert len(adapter.client.indices.create_calls) == 1
    assert adapter.client.indices.create_calls[0]["index"] == INDEX_NAME
