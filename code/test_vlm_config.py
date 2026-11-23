"""Offline configuration tests; never contact a service or use real credentials."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from vlm_config import (
    DEFAULT_MODEL_NAME,
    VLMConfigurationError,
    build_vlm_request,
    get_dataset_root,
    load_vlm_settings,
    resolve_dataset_image,
)


class TestVLMConfiguration(unittest.TestCase):
    def test_no_implicit_request_destination(self):
        with self.assertRaisesRegex(VLMConfigurationError, "YECID_VLM_API_URL"):
            load_vlm_settings({"YECID_VLM_CONFIG": ""})

    def test_environment_overrides_local_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "code/configs/vlm.local.json"
            config.parent.mkdir(parents=True)
            config.write_text(json.dumps({
                "api_url": "http://local.invalid/v1/chat/completions",
                "model": "local-model",
                "api_key": "dummy-local-test-value",
            }), encoding="utf-8")
            settings = load_vlm_settings({
                "YECID_VLM_API_URL": "https://environment.invalid/v1/chat/completions",
                "YECID_VLM_MODEL": "environment-model",
                "YECID_VLM_API_KEY": "",
            }, project_root=root)
            self.assertEqual(settings.api_url, "https://environment.invalid/v1/chat/completions")
            self.assertEqual(settings.model, "environment-model")
            self.assertNotIn("Authorization", settings.request_headers())

    def test_explicit_relative_config_and_private_repr(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "private.local.json"
            synthetic_token = "dummy-configuration-test-token"
            config.write_text(json.dumps({
                "api_url": "http://service.invalid/v1/chat/completions",
                "api_key": synthetic_token,
            }), encoding="utf-8")
            settings = load_vlm_settings({"YECID_VLM_CONFIG": config.name}, project_root=root)
            self.assertEqual(settings.model, DEFAULT_MODEL_NAME)
            self.assertEqual(settings.request_headers()["Authorization"], "Bearer " + synthetic_token)
            self.assertNotIn(synthetic_token, repr(settings))

    def test_empty_config_variable_disables_local_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "code/configs/vlm.local.json"
            config.parent.mkdir(parents=True)
            config.write_text("not JSON", encoding="utf-8")
            settings = load_vlm_settings({
                "YECID_VLM_CONFIG": "",
                "YECID_VLM_API_URL": "http://offline.invalid/v1/chat/completions",
            }, project_root=root)
            self.assertEqual(settings.api_key, "")

    def test_invalid_local_configuration_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(VLMConfigurationError, "does not exist"):
                load_vlm_settings({"YECID_VLM_CONFIG": "missing.local.json"}, project_root=root)
            config = root / "invalid.local.json"
            config.write_text("[]", encoding="utf-8")
            with self.assertRaisesRegex(VLMConfigurationError, "JSON object"):
                load_vlm_settings({"YECID_VLM_CONFIG": config.name}, project_root=root)

    def test_invalid_endpoint_is_rejected_without_echoing_values(self):
        for value in ["https://", "file:///tmp/not-a-service", "http://host.invalid:bad-port"]:
            with self.subTest(url_type=value.split(":", 1)[0]):
                with self.assertRaises(VLMConfigurationError) as caught:
                    load_vlm_settings({"YECID_VLM_CONFIG": "", "YECID_VLM_API_URL": value})
                self.assertNotIn(value, str(caught.exception))

    def test_request_builder_uses_configured_model_and_preserves_messages(self):
        payload = {"model": "old-placeholder", "messages": [{"role": "user", "content": "offline fixture"}], "temperature": 0.1}
        with patch.dict("os.environ", {
            "YECID_VLM_CONFIG": "",
            "YECID_VLM_API_URL": "http://offline.invalid/v1/chat/completions",
            "YECID_VLM_MODEL": "configured-model",
            "YECID_VLM_API_KEY": "",
        }):
            request = build_vlm_request(payload)
        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(body["model"], "configured-model")
        self.assertEqual(body["messages"], payload["messages"])
        self.assertEqual(body["temperature"], payload["temperature"])
        self.assertEqual(payload["model"], "old-placeholder")
        self.assertNotIn("Authorization", request.headers)


class TestDatasetImagePaths(unittest.TestCase):
    def test_dataset_root_defaults_and_relative_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(get_dataset_root(root, {}), (root / "dataset").resolve())
            self.assertEqual(
                get_dataset_root(root, {"YECID_DATASET_DIR": "new-dataset"}),
                (root / "new-dataset").resolve(),
            )

    def test_legacy_destination_remains_compatible_without_relocation(self):
        self.assertEqual(
            resolve_dataset_image({"local_dest": "fixture"}, environ={}),
            Path("fixture"),
        )

    def test_relative_mapping_uses_materialized_image_not_raw_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = root / "images/train/0001.jpg"
            image.parent.mkdir(parents=True)
            image.write_bytes(b"synthetic standardized-image fixture")
            item = {"path": "images/train/0001.jpg", "source_path": "must-never-be-read.jpg"}
            self.assertEqual(resolve_dataset_image(item, root, {}), image.resolve())

    def test_explicit_root_overrides_stale_absolute_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = root / "images/train/0001.jpg"
            image.parent.mkdir(parents=True)
            image.write_bytes(b"synthetic relocated-image fixture")
            item = {"path": "images/train/0001.jpg", "local_dest": "C:/old-computer/dataset/0001.jpg"}
            self.assertEqual(resolve_dataset_image(item, environ={"YECID_DATASET_DIR": str(root)}), image.resolve())
            self.assertEqual(resolve_dataset_image(item, dataset_root=root, environ={}), image.resolve())

    def test_invalid_paths_and_unmaterialized_source_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw = root / "raw.jpg"
            raw.write_bytes(b"raw source is not a standard image")
            for value in ["../raw.jpg", str(raw.resolve()), "C:/old-computer/image.jpg", "\\\\server\\share\\image.jpg"]:
                with self.subTest(path_kind=value.split("/", 1)[0]):
                    with self.assertRaises(ValueError):
                        resolve_dataset_image({"path": value}, root, {})
            with self.assertRaises(FileNotFoundError):
                resolve_dataset_image({"path": "images/train/missing.jpg", "source_path": str(raw)}, root, {})
            with self.assertRaises(ValueError):
                resolve_dataset_image({"source_path": str(raw)}, root, {})


if __name__ == "__main__":
    unittest.main()
