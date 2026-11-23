"""Load local VLM connection settings without storing authentication in source."""

from dataclasses import dataclass, field
import json
import os
from pathlib import Path, PureWindowsPath
from urllib.parse import urlsplit
import urllib.request


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LOCAL_CONFIG = PROJECT_ROOT / "code" / "configs" / "vlm.local.json"
DEFAULT_MODEL_NAME = "gemini-3.1-flash-lite"


class VLMConfigurationError(ValueError):
    """The service connection was not configured correctly."""


def get_dataset_root(project_root=None, environ=None):
    """Locate an existing or future dataset without changing any files."""
    env = os.environ if environ is None else environ
    root = PROJECT_ROOT if project_root is None else Path(project_root)
    configured = env.get("YECID_DATASET_DIR", "").strip()
    dataset_root = Path(configured).expanduser() if configured else root / "dataset"
    if not dataset_root.is_absolute():
        dataset_root = root / dataset_root
    return dataset_root.resolve()


def resolve_dataset_image(item, dataset_root=None, environ=None):
    """Resolve a materialized standard image, never the raw source_path.

    Explicit dataset relocation takes precedence over a legacy local_dest.
    Without relocation, keep legacy inputs compatible. New relative mappings
    must point to an existing file within the selected dataset root.
    """
    env = os.environ if environ is None else environ
    relocated = dataset_root is not None or bool(env.get("YECID_DATASET_DIR", "").strip())
    legacy = item.get("local_dest")
    if legacy and not relocated:
        return Path(legacy)

    relative = item.get("path")
    if not isinstance(relative, str) or not relative.strip():
        raise ValueError("Dataset mapping requires a relative standardized-image path")
    relative_path = Path(relative)
    windows_path = PureWindowsPath(relative)
    if relative_path.is_absolute() or windows_path.drive or windows_path.root:
        raise ValueError("Dataset image path must be relative to the dataset root")
    root = (Path(dataset_root) if dataset_root is not None else get_dataset_root(environ=env)).resolve()
    image_path = (root / relative_path).resolve()
    if not image_path.is_relative_to(root):
        raise ValueError("Dataset image path escapes the dataset root")
    if not image_path.is_file():
        raise FileNotFoundError("Standardized dataset image has not been materialized")
    return image_path


@dataclass(frozen=True)
class VLMSettings:
    api_url: str
    model: str
    api_key: str = field(default="", repr=False)

    def request_headers(self):
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = "Bearer " + self.api_key
        return headers


def load_vlm_settings(environ=None, project_root=None):
    """Read environment overrides and an optional, git-ignored JSON file.

    An empty YECID_VLM_CONFIG disables the local file. No endpoint or token is
    assumed: a real request requires an explicit URL. Values are never logged.
    """
    env = os.environ if environ is None else environ
    root = PROJECT_ROOT if project_root is None else Path(project_root)
    explicit_config = env.get("YECID_VLM_CONFIG")
    if explicit_config is None:
        config_path = root / "code" / "configs" / "vlm.local.json"
        required_file = False
    elif not explicit_config.strip():
        config_path = None
        required_file = False
    else:
        config_path = Path(explicit_config).expanduser()
        if not config_path.is_absolute():
            config_path = root / config_path
        required_file = True

    local = {}
    if config_path is not None:
        if not config_path.exists():
            if required_file:
                raise VLMConfigurationError("YECID_VLM_CONFIG file does not exist")
        else:
            try:
                local = json.loads(config_path.read_text(encoding="utf-8-sig"))
            except (OSError, ValueError) as exc:
                raise VLMConfigurationError("Cannot read local VLM JSON configuration") from exc
            if not isinstance(local, dict):
                raise VLMConfigurationError("Local VLM configuration must be a JSON object")
            if set(local) - {"api_url", "model", "api_key"}:
                raise VLMConfigurationError("Local VLM configuration contains unsupported fields")

    def text_value(env_name, file_name, default=""):
        value = env[env_name] if env_name in env else local.get(file_name, default)
        if not isinstance(value, str):
            raise VLMConfigurationError(env_name + " must be a string")
        return value.strip()

    api_url = text_value("YECID_VLM_API_URL", "api_url")
    model = text_value("YECID_VLM_MODEL", "model", DEFAULT_MODEL_NAME)
    api_key = text_value("YECID_VLM_API_KEY", "api_key")
    if not api_url:
        raise VLMConfigurationError(
            "Set YECID_VLM_API_URL or api_url in code/configs/vlm.local.json; "
            "see code/CONFIGURATION.md"
        )
    try:
        parsed = urlsplit(api_url)
        valid_url = parsed.scheme in {"http", "https"} and bool(parsed.hostname)
        parsed.port  # Validate a supplied port without logging the URL.
    except ValueError:
        valid_url = False
    if not valid_url:
        raise VLMConfigurationError("YECID_VLM_API_URL must be an HTTP(S) URL with a hostname")
    if not model:
        raise VLMConfigurationError("YECID_VLM_MODEL must not be empty")
    if "\r" in api_key or "\n" in api_key:
        raise VLMConfigurationError("YECID_VLM_API_KEY must not contain line breaks")
    return VLMSettings(api_url=api_url, model=model, api_key=api_key)


def build_vlm_request(payload):
    """Build a request using the configured service; do not perform network I/O."""
    settings = load_vlm_settings()
    configured_payload = dict(payload)
    configured_payload["model"] = settings.model
    return urllib.request.Request(
        settings.api_url,
        data=json.dumps(configured_payload).encode("utf-8"),
        headers=settings.request_headers(),
    )
