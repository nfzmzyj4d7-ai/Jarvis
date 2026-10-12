import socket
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))

from fake_ollama import FakeOllama  # noqa: E402


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def fake_ollama():
    with FakeOllama() as f:
        yield f


@pytest.fixture
def make_config(tmp_path):
    """Kopie van de echte config.yaml, met database/logs in een tijdelijke map en de nep-Ollama als host."""
    def _make(llm_host: str = "http://127.0.0.1:9", server: bool = False, port: int | None = None):
        data = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
        data["paths"] = {"database": str(tmp_path / "jarvis.db"), "log_dir": str(tmp_path / "logs")}
        data["llm"]["host"] = llm_host
        data["server"] = {"enabled": server, "host": "127.0.0.1", "port": port or free_port()}
        # modellen blijven in de projectmap
        for section in ("wakeword", "vad"):
            for k, v in data[section].items():
                if isinstance(v, str) and v.startswith("models/"):
                    data[section][k] = str(ROOT / v)
        data["tts"]["voices"] = {k: str(ROOT / v) for k, v in data["tts"]["voices"].items()}
        path = tmp_path / "config.yaml"
        path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
        return path
    return _make
