import importlib.util
import json
import re
from pathlib import Path
from types import ModuleType
from typing import Any


class ModeLoadError(Exception):
    """Raised when a game mode cannot be discovered or loaded."""


def _read_manifest(manifest_path: Path) -> dict[str, Any]:
    try:
        with manifest_path.open("r", encoding="utf-8") as file:
            manifest = json.load(file)
    except json.JSONDecodeError as exc:
        raise ModeLoadError(
            f"Invalid JSON in {manifest_path}: "
            f"line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc
    except OSError as exc:
        raise ModeLoadError(
            f"Cannot read manifest {manifest_path}: {exc}"
        ) from exc

    if not isinstance(manifest, dict):
        raise ModeLoadError(
            f"Manifest root must be an object: {manifest_path}"
        )

    return manifest


def _validate_manifest(
    manifest: dict[str, Any],
    directory: Path
) -> None:
    required_fields = ("id", "name", "version", "entry_point", "validator")

    for field in required_fields:
        value = manifest.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ModeLoadError(
                f"Invalid or missing '{field}' in {directory / 'manifest.json'}"
            )

    mode_id = manifest["id"]

    if not re.fullmatch(r"[a-zA-Z0-9_-]+", mode_id):
        raise ModeLoadError(f"Invalid mode ID: {mode_id!r}")

    if mode_id != directory.name:
        raise ModeLoadError(
            f"Mode ID mismatch: directory is {directory.name!r}, "
            f"manifest declares {mode_id!r}"
        )

    for field in ("entry_point", "validator"):
        filename = manifest[field]

        if Path(filename).name != filename or not filename.endswith(".py"):
            raise ModeLoadError(
                f"'{field}' must be a Python filename in the mode directory."
            )

        if not (directory / filename).is_file():
            raise ModeLoadError(
                f"Missing '{field}' file: {directory / filename}"
            )

    player_count = manifest.get("player_count")

    if not isinstance(player_count, dict):
        raise ModeLoadError("'player_count' must be an object.")

    minimum = player_count.get("minimum")
    maximum = player_count.get("maximum")

    for field, value in (("minimum", minimum), ("maximum", maximum)):
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ModeLoadError(
                f"'player_count.{field}' must be a positive integer."
            )

    if minimum > maximum:
        raise ModeLoadError(
            "'player_count.minimum' cannot exceed 'player_count.maximum'."
        )

    landlord_modes = manifest.get("landlord_modes")

    if (
        not isinstance(landlord_modes, list)
        or not landlord_modes
        or any(not isinstance(item, str) or not item for item in landlord_modes)
        or len(set(landlord_modes)) != len(landlord_modes)
    ):
        raise ModeLoadError(
            "'landlord_modes' must be a non-empty list of unique strings."
        )


def discover_modes(modes_directory: Path) -> dict[str, Path]:
    """Discover game mode directories by scanning the modes directory."""
    if not modes_directory.is_dir():
        raise ModeLoadError(
            f"Modes directory does not exist: {modes_directory}"
        )

    discovered = {}

    for directory in sorted(modes_directory.iterdir()):
        if not directory.is_dir():
            continue

        manifest_path = directory / "manifest.json"

        # Directories without manifests are not registered as game modes.
        if not manifest_path.is_file():
            continue

        manifest = _read_manifest(manifest_path)
        _validate_manifest(manifest, directory)

        discovered[manifest["id"]] = directory

    return discovered


def load_mode(modes_directory: Path, mode_id: str) -> dict[str, Any]:
    """Discover and dynamically load the selected game mode."""
    discovered = discover_modes(modes_directory)

    if mode_id not in discovered:
        raise ModeLoadError(
            f"Game mode {mode_id!r} was not found or is incomplete."
        )

    directory = discovered[mode_id]
    manifest = _read_manifest(directory / "manifest.json")

    validator_path = directory / manifest["validator"]
    module_name = f"_game_mode_{mode_id}_validator"

    try:
        spec = importlib.util.spec_from_file_location(
            module_name, validator_path
        )

        if spec is None or spec.loader is None:
            raise ModeLoadError(
                f"Cannot create import specification for {validator_path}"
            )

        validator_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(validator_module)

    except ModeLoadError:
        raise
    except Exception as exc:
        raise ModeLoadError(
            f"Failed to load validator for mode {mode_id!r}: {exc}"
        ) from exc

    validate_function = getattr(validator_module, "validate", None)

    if not callable(validate_function):
        raise ModeLoadError(
            f"Validator {validator_path} must define "
            "a callable 'validate(config, manifest)' function."
        )

    return {
        "id": mode_id,
        "directory": directory,
        "manifest": manifest,
        "validator": validator_module,
        "game_entry": directory / manifest["entry_point"],
    }
