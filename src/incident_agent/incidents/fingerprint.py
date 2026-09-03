"""Stable Alertmanager alert fingerprinting."""

import hashlib
import json
from collections.abc import Mapping


def normalize_labels(labels: Mapping[str, str]) -> dict[str, str]:
    """Return labels with whitespace normalized and keys sorted by serialization."""

    return {str(key).strip(): str(value).strip() for key, value in labels.items()}


def compute_fingerprint(labels: Mapping[str, str]) -> str:
    """Hash only stable alert identity labels, excluding dynamic timestamps."""

    normalized = normalize_labels(labels)
    payload = {
        key: normalized[key]
        for key in sorted(normalized)
        if key not in {"startsAt", "endsAt", "annotations"}
    }
    encoded = json.dumps(
        payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
