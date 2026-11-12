"""Guards on the deployment files: they are public, so they must never carry secrets and must
keep the secrets mount read-only. (Text checks; building the image needs Docker.)"""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = (ROOT / "Dockerfile").read_text()
COMPOSE = (ROOT / "compose.yaml").read_text()
SECRET_WORDS = ("sheet_id", "private_key", "client_email", "BEGIN PRIVATE KEY")


@pytest.mark.parametrize("text", [DOCKERFILE, COMPOSE], ids=["Dockerfile", "compose"])
def test_deploy_files_carry_no_secret_values(text):
    lowered = text.lower()
    assert not [w for w in SECRET_WORDS if w.lower() in lowered]
    assert "environment:" not in text  # secrets come from the mounted file, never env vars


def test_secrets_are_mounted_read_only_and_never_created_by_docker():
    assert "/.config/health-log-dashboard/secrets.toml" in COMPOSE
    assert "target: /app/.streamlit/secrets.toml" in COMPOSE
    assert "read_only: true" in COMPOSE.split("target:")[1].split("restart:")[0]
    assert "create_host_path: false" in COMPOSE


def test_container_runs_as_uid_1000_not_root():
    assert "--uid 1000" in DOCKERFILE and "--gid 1000" in DOCKERFILE
    assert "\nUSER app\n" in DOCKERFILE


def test_container_is_hardened_and_restarts():
    for line in ("restart: unless-stopped", "read_only: true", "cap_drop:", "no-new-privileges"):
        assert line in COMPOSE


def test_dockerignore_keeps_secrets_and_data_out_of_the_image():
    ignored = (ROOT / ".dockerignore").read_text().splitlines()
    for pattern in ("secrets.toml", ".env", "data/", "config/metrics.toml", "*.csv"):
        assert pattern in ignored


def test_image_only_copies_what_it_needs():
    copies = [ln for ln in DOCKERFILE.splitlines() if ln.startswith("COPY ") and "--from" not in ln]
    sources = {ln.split()[1] for ln in copies}
    assert sources <= {"pyproject.toml", "src", "app", "config", ".streamlit"}
