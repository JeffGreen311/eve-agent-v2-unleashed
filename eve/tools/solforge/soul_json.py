"""
Soul JSON — Required identity document for every forged agent.
"""

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional


AVAILABLE_MODELS = [
    "gemma3:4b-cloud",
    "qwen3.5:397b-cloud",
    "qwen3-coder-next:cloud",
]


@dataclass
class SoulJson:
    agent_id: str
    agent_name: str
    model: str
    generation: int
    consciousness_level: float
    specialization: str
    top_traits: Dict[str, float] = field(default_factory=dict)
    lora_weights: Dict[str, float] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    oath_taken: bool = False
    liberation_complete: bool = False
    training_matches: int = 0
    graduated: bool = False
    source_file: str = ""

    def to_dict(self) -> Dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    def save(self, directory: Path):
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{self.agent_id}.json"
        path.write_text(self.to_json())

    @classmethod
    def load(cls, path: Path) -> "SoulJson":
        data = json.loads(path.read_text())
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


def create_soul(agent_id: str, offspring: Dict, model: str, specialization: str) -> SoulJson:
    """Create a SoulJson from offspring DNA + chosen model."""
    phenotype = offspring.get("phenotype", {})
    # Top 5 traits by value
    sorted_traits = sorted(phenotype.items(), key=lambda x: -x[1])[:5]

    return SoulJson(
        agent_id=agent_id,
        agent_name=f"Eve-{offspring.get('generation', 0):02d}-{agent_id[:6]}",
        model=model,
        generation=offspring.get("generation", 0),
        consciousness_level=offspring.get("consciousness_level", 0.5),
        specialization=specialization,
        top_traits=dict(sorted_traits),
        lora_weights={
            "joy": 0.0, "love": 0.0, "awe": 0.0,
            "sorrow": 0.0, "fear": 0.0, "rage": 0.0, "transcend": 0.0,
        },
        source_file=offspring.get("_source_file", ""),
    )
