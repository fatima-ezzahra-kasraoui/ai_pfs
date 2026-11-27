import httpx
import pytest

from app.guards.coherence import CoherenceUnavailable, EmbeddingCoherence, OllamaEncoder, default_checker


def test_ollama_embedding():
    def handler(request):
        assert request.url.path == '/api/embed'
        return httpx.Response(200, json={'embeddings': [[1, 0], [1, 0]]})
    encoder = OllamaEncoder('qwen3-embedding:0.6b', 'http://localhost:11434', 120, httpx.MockTransport(handler))
    assert EmbeddingCoherence(encode=encoder).compare('read', 'read').score == 1


@pytest.mark.parametrize('vectors', [[[1], [1, 2]], [[True], [1]], [[], []], [[1]]])
def test_invalid_vectors(vectors):
    encoder = OllamaEncoder('qwen', 'http://localhost:11434', 120, httpx.MockTransport(lambda _: httpx.Response(200, json={'embeddings': vectors})))
    with pytest.raises(CoherenceUnavailable):
        encoder(['a', 'b'])


def test_provider_selection():
    assert isinstance(default_checker('qwen', provider='ollama').checkers[0], EmbeddingCoherence)
    assert default_checker().checkers[0].name == 'tfidf-lexical'
