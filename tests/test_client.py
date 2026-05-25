import pytest
import time
from src.core.client import GroqClient


@pytest.fixture(scope="session")
def client() -> GroqClient:
    return GroqClient()


# ── singleton ─────────────────────────────────────────────────────────────────

def test_singleton(client: GroqClient) -> None:
    assert client is GroqClient()

# ── temperature variations and timing ────────────────────────────────────────────────────

@pytest.mark.parametrize("temperature", [0.0, 0.5, 1.0, 1.5, 2.0])
async def test_temperature(client: GroqClient, temperature: float) -> None:
    start = time.perf_counter()
    reply = await client.generate("Name one color.", temperature=temperature, max_tokens=20)
    elapsed = time.perf_counter() - start

    print(f"temp={temperature:.1f}  time={elapsed:.3f}s  response={reply}")

    assert isinstance(reply, str) and len(reply) > 0