"""Core data structures for faceless video projects."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(slots=True)
class VideoProject:
    """The metadata needed to start planning one video."""

    project_id: str
    title: str
    topic: str = ""
    audience: str = ""
    video_format: str = "explainer"
    duration_minutes: float | None = None
    notes: str = ""
    status: str = "idea"
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.project_id.strip():
            raise ValueError("project_id cannot be empty")
        if not self.title.strip():
            raise ValueError("title cannot be empty")
        if self.duration_minutes is not None and self.duration_minutes <= 0:
            raise ValueError("duration_minutes must be greater than zero")
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation of the project."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VideoProject":
        """Build a project from data previously saved as JSON."""
        return cls(**data)


@dataclass(slots=True)
class ScriptSection:
    """An editable part of a video script."""

    name: str
    narration: str = ""
    visual_notes: str = ""
    estimated_duration_seconds: float | None = None
    estimated_word_count: int | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("script section name cannot be empty")
        if self.estimated_duration_seconds is not None and self.estimated_duration_seconds < 0:
            raise ValueError("estimated duration cannot be negative")
        if self.estimated_word_count is not None and self.estimated_word_count < 0:
            raise ValueError("estimated word count cannot be negative")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScriptSection":
        return cls(**data)


@dataclass(slots=True)
class VideoScript:
    """A structured, editable script associated with one project and plan."""

    project_id: str
    title: str
    target_duration_minutes: float
    sections: list[ScriptSection]
    pacing: str = "standard"

    def __post_init__(self) -> None:
        if not self.project_id.strip():
            raise ValueError("project_id cannot be empty")
        if not self.title.strip():
            raise ValueError("title cannot be empty")
        if self.target_duration_minutes <= 0:
            raise ValueError("target_duration_minutes must be greater than zero")

    @property
    def estimated_word_count(self) -> int:
        return sum(section.estimated_word_count or 0 for section in self.sections)

    @property
    def estimated_duration_seconds(self) -> float:
        return sum(section.estimated_duration_seconds or 0 for section in self.sections)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "title": self.title,
            "target_duration_minutes": self.target_duration_minutes,
            "pacing": self.pacing,
            "sections": [section.to_dict() for section in self.sections],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VideoScript":
        return cls(
            project_id=data["project_id"],
            title=data["title"],
            target_duration_minutes=data["target_duration_minutes"],
            pacing=data.get("pacing", "standard"),
            sections=[ScriptSection.from_dict(item) for item in data.get("sections", [])],
        )


PRODUCTION_ASSET_TYPES = (
    "image",
    "video",
    "screen_recording",
    "graphic",
    "text_card",
    "archive",
    "other",
)


@dataclass(slots=True)
class ProductionScene:
    """One editable scene in a production shot list."""

    scene_number: int
    script_section_index: int
    narration_reference: str
    estimated_duration_seconds: float
    visual_direction: str
    on_screen_text: str = ""
    asset_type: str = "video"
    notes: str = ""

    def __post_init__(self) -> None:
        if self.scene_number <= 0:
            raise ValueError("scene_number must be greater than zero")
        if self.script_section_index <= 0:
            raise ValueError("script_section_index must be greater than zero")
        if self.estimated_duration_seconds < 0:
            raise ValueError("estimated duration cannot be negative")
        if self.asset_type not in PRODUCTION_ASSET_TYPES:
            raise ValueError(f"unsupported production asset type: {self.asset_type}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProductionScene":
        return cls(**data)


@dataclass(slots=True)
class ProductionPlan:
    """An editable shot list that references an authoritative VideoScript."""

    project_id: str
    title: str
    target_duration_minutes: float
    source_script: str
    scenes: list[ProductionScene]

    def __post_init__(self) -> None:
        if not self.project_id.strip():
            raise ValueError("project_id cannot be empty")
        if not self.title.strip():
            raise ValueError("title cannot be empty")
        if self.target_duration_minutes <= 0:
            raise ValueError("target_duration_minutes must be greater than zero")
        if not self.source_script.strip():
            raise ValueError("source_script cannot be empty")

    @property
    def estimated_duration_seconds(self) -> float:
        return sum(scene.estimated_duration_seconds for scene in self.scenes)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "title": self.title,
            "target_duration_minutes": self.target_duration_minutes,
            "source_script": self.source_script,
            "scenes": [scene.to_dict() for scene in self.scenes],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProductionPlan":
        return cls(
            project_id=data["project_id"],
            title=data["title"],
            target_duration_minutes=data["target_duration_minutes"],
            source_script=data["source_script"],
            scenes=[ProductionScene.from_dict(item) for item in data.get("scenes", [])],
        )


ASSET_MANIFEST_TYPES = (
    "image",
    "video",
    "graphic",
    "screenshot",
    "screen_recording",
    "text_card",
    "archive",
    "other",
)
ASSET_STATUSES = ("needed", "sourced", "downloaded", "ready", "rejected")


@dataclass(slots=True)
class AssetManifestEntry:
    """Metadata for one asset requirement; it does not inspect or fetch assets."""

    asset_id: str
    scene_number: int
    scene_reference: str
    asset_type: str
    description: str
    source_url: str = ""
    source_name: str = ""
    local_path: str = ""
    status: str = "needed"
    rights_note: str = ""
    attribution: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.asset_id.strip():
            raise ValueError("asset_id cannot be empty")
        if self.scene_number <= 0:
            raise ValueError("scene_number must be greater than zero")
        if not self.scene_reference.strip():
            raise ValueError("scene_reference cannot be empty")
        if self.asset_type not in ASSET_MANIFEST_TYPES:
            raise ValueError(f"unsupported asset type: {self.asset_type}")
        if not self.description.strip():
            raise ValueError("asset description cannot be empty")
        if self.status not in ASSET_STATUSES:
            raise ValueError(f"unsupported asset status: {self.status}")
        if self.status == "sourced" and not (self.source_url.strip() or self.source_name.strip()):
            raise ValueError("sourced assets need a source URL or source name")
        if self.status in ("downloaded", "ready") and not self.local_path.strip():
            raise ValueError(f"{self.status} assets need a local path")
        if self.status == "rejected" and not self.notes.strip():
            raise ValueError("rejected assets need notes explaining the rejection")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AssetManifestEntry":
        return cls(**data)


@dataclass(slots=True)
class AssetManifest:
    """An offline asset inventory linked to an authoritative ProductionPlan."""

    project_id: str
    title: str
    source_production_plan: str
    assets: list[AssetManifestEntry]

    def __post_init__(self) -> None:
        if not self.project_id.strip():
            raise ValueError("project_id cannot be empty")
        if not self.title.strip():
            raise ValueError("title cannot be empty")
        if not self.source_production_plan.strip():
            raise ValueError("source_production_plan cannot be empty")
        asset_ids = [asset.asset_id for asset in self.assets]
        if len(asset_ids) != len(set(asset_ids)):
            raise ValueError("asset IDs must be unique")

    @property
    def status_counts(self) -> dict[str, int]:
        return {status: sum(asset.status == status for asset in self.assets) for status in ASSET_STATUSES}

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "title": self.title,
            "source_production_plan": self.source_production_plan,
            "assets": [asset.to_dict() for asset in self.assets],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AssetManifest":
        return cls(
            project_id=data["project_id"],
            title=data["title"],
            source_production_plan=data["source_production_plan"],
            assets=[AssetManifestEntry.from_dict(item) for item in data.get("assets", [])],
        )


ASSET_SOURCE_KINDS = ("manual", "public_domain", "creative_commons", "local_catalog")
ASSET_CANDIDATE_RELATIONSHIPS = ("candidate", "shortlisted", "selected", "rejected")


@dataclass(slots=True)
class AssetSource:
    """Metadata describing a possible asset source; it is never contacted here."""

    source_id: str
    name: str
    source_url: str = ""
    license_policy_url: str = ""
    source_kind: str = "manual"
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.source_id.strip():
            raise ValueError("source_id cannot be empty")
        if not self.name.strip():
            raise ValueError("source name cannot be empty")
        if self.source_kind not in ASSET_SOURCE_KINDS:
            raise ValueError(f"unsupported asset source kind: {self.source_kind}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AssetSource":
        return cls(**data)


@dataclass(slots=True)
class AssetCandidate:
    """Recorded candidate metadata, with no implied rights clearance."""

    candidate_id: str
    asset_id: str
    source_id: str
    source_name: str
    url: str
    title: str
    creator: str = ""
    license_name: str = ""
    license_url: str = ""
    usage_information: str = ""
    preview_url: str = ""
    attribution: str = ""
    rights_note: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        for field_name, value in (("candidate_id", self.candidate_id), ("asset_id", self.asset_id), ("source_id", self.source_id), ("source_name", self.source_name), ("url", self.url), ("title", self.title)):
            if not value.strip():
                raise ValueError(f"{field_name} cannot be empty")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AssetCandidate":
        return cls(**data)


@dataclass(slots=True)
class AssetCandidateMatch:
    """An editorial relationship between a manifest requirement and candidate."""

    asset_id: str
    candidate_id: str
    relationship: str = "candidate"
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.asset_id.strip():
            raise ValueError("asset_id cannot be empty")
        if not self.candidate_id.strip():
            raise ValueError("candidate_id cannot be empty")
        if self.relationship not in ASSET_CANDIDATE_RELATIONSHIPS:
            raise ValueError(f"unsupported candidate relationship: {self.relationship}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AssetCandidateMatch":
        return cls(**data)


@dataclass(slots=True)
class AssetSourcingPlan:
    """Candidate metadata kept separate from authoritative asset requirements."""

    project_id: str
    title: str
    source_asset_manifest: str
    sources: list[AssetSource]
    candidates: list[AssetCandidate]
    matches: list[AssetCandidateMatch]

    def __post_init__(self) -> None:
        if not self.project_id.strip():
            raise ValueError("project_id cannot be empty")
        if not self.title.strip():
            raise ValueError("title cannot be empty")
        if not self.source_asset_manifest.strip():
            raise ValueError("source_asset_manifest cannot be empty")
        source_ids = [source.source_id for source in self.sources]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("source IDs must be unique")
        candidate_ids = [candidate.candidate_id for candidate in self.candidates]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("candidate IDs must be unique")
        known_sources = set(source_ids)
        if any(candidate.source_id not in known_sources for candidate in self.candidates):
            raise ValueError("candidate references an unknown source")
        known_candidates = set(candidate_ids)
        if any(match.candidate_id not in known_candidates for match in self.matches):
            raise ValueError("match references an unknown candidate")
        match_keys = [(match.asset_id, match.candidate_id) for match in self.matches]
        if len(match_keys) != len(set(match_keys)):
            raise ValueError("candidate matches must be unique")

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "title": self.title,
            "source_asset_manifest": self.source_asset_manifest,
            "sources": [source.to_dict() for source in self.sources],
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "matches": [match.to_dict() for match in self.matches],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AssetSourcingPlan":
        return cls(
            project_id=data["project_id"],
            title=data["title"],
            source_asset_manifest=data["source_asset_manifest"],
            sources=[AssetSource.from_dict(item) for item in data.get("sources", [])],
            candidates=[AssetCandidate.from_dict(item) for item in data.get("candidates", [])],
            matches=[AssetCandidateMatch.from_dict(item) for item in data.get("matches", [])],
        )


@dataclass(slots=True)
class ResearchSource:
    """A manually recorded source and the facts taken from it."""

    url: str
    title: str
    notes: str = ""
    key_facts: list[str] | None = None
    citation: str = ""

    def __post_init__(self) -> None:
        if not self.url.strip():
            raise ValueError("source url cannot be empty")
        if not self.title.strip():
            raise ValueError("source title cannot be empty")
        if self.key_facts is None:
            self.key_facts = []

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ResearchSource":
        return cls(**data)
