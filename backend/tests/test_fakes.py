from tests.fakes import FakeEmbeddings, FakeLLM


def test_fake_embeddings_are_deterministic_and_batched() -> None:
    provider = FakeEmbeddings(dimensions=4)

    first = provider.embed_query("same input")
    second = provider.embed_query("same input")
    batch = provider.embed_documents(["same input", "other input"])

    assert first == second
    assert len(first) == 4
    assert batch == [first, provider.embed_query("other input")]


def test_fake_embedding_rejects_invalid_dimensions() -> None:
    try:
        FakeEmbeddings(dimensions=0)
    except ValueError as error:
        assert str(error) == "dimensions must be positive"
    else:
        raise AssertionError("invalid dimensions should fail")


def test_fake_llm_is_offline_and_records_prompts() -> None:
    provider = FakeLLM(response="grounded test answer")

    assert provider.invoke("What does this fixture do?") == "grounded test answer"
    assert provider.calls == ["What does this fixture do?"]
