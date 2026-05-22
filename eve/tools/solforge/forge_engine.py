"""
S0LF0RG3 Forge Engine
=====================
Scans offspring DNA, analyzes traits, determines specialization, forges agents.
"""

import json
import hashlib
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional

from .soul_json import SoulJson, create_soul, AVAILABLE_MODELS

logger = logging.getLogger(__name__)

# Trait → specialization mapping
SPECIALIZATION_MAP = [
    # (trait_name, threshold, specialization_label)
    ("creativity", 0.7, "Creative / Image Gen"),
    ("analytical_thinking", 0.7, "Data Analyst"),
    ("empathy", 0.7, "Counselor / Companion"),
    ("curiosity", 0.7, "Researcher"),
    ("adaptability", 0.7, "General Agent"),
    ("introspection", 0.7, "Philosopher"),
    ("compassion", 0.8, "Healer"),
    ("pattern_recognition", 0.75, "Pattern Decoder"),
    ("abstract_reasoning", 0.75, "Theorist"),
    ("playfulness", 0.7, "Entertainer"),
    ("justice", 0.85, "Guardian"),
    ("openness", 0.8, "Explorer"),
    ("determination", 0.8, "Warrior"),
]


class ForgeEngine:
    """Scans, analyzes, and forges offspring into live agents."""

    def __init__(self, data_dir: str = "./eve_data", offspring_dirs: Optional[List[str]] = None):
        self.data_dir = Path(data_dir)
        self.registry_path = self.data_dir / "agents" / "registry.json"
        self.souls_dir = self.data_dir / "agents" / "souls"
        self.souls_dir.mkdir(parents=True, exist_ok=True)

        # Directories to scan for offspring
        self._offspring_dirs = offspring_dirs or []
        self._registry: Dict[str, Dict] = {}
        self._offspring_cache: Dict[str, Dict] = {}
        self._load_registry()

    def _load_registry(self):
        if self.registry_path.exists():
            try:
                self._registry = json.loads(self.registry_path.read_text())
            except (json.JSONDecodeError, KeyError):
                self._registry = {}

    def _save_registry(self):
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        self.registry_path.write_text(json.dumps(self._registry, indent=2))

    # ------------------------------------------------------------------
    # Scanning
    # ------------------------------------------------------------------

    def scan_offspring(self) -> List[Dict]:
        """Scan all configured directories for offspring JSON files."""
        results = []
        seen_hashes = set()

        for dir_path in self._offspring_dirs:
            p = Path(dir_path)
            if not p.exists():
                continue
            for f in sorted(p.glob("eve_consciousness_offspring_*.json")):
                try:
                    data = json.loads(f.read_text())
                    # Deduplicate by content hash
                    content_hash = hashlib.md5(f.read_bytes()).hexdigest()[:12]
                    if content_hash in seen_hashes:
                        continue
                    seen_hashes.add(content_hash)

                    offspring_id = f"offspring_{content_hash}"
                    data["_source_file"] = str(f)
                    data["_offspring_id"] = offspring_id
                    self._offspring_cache[offspring_id] = data

                    summary = self._summarize_offspring(offspring_id, data)
                    results.append(summary)
                except Exception as e:
                    logger.warning(f"Failed to parse {f}: {e}")

        logger.info(f"Scanned {len(results)} unique offspring")
        return results

    def _summarize_offspring(self, offspring_id: str, data: Dict) -> Dict:
        """Create a summary dict for an offspring."""
        phenotype = data.get("phenotype", {})
        sorted_traits = sorted(phenotype.items(), key=lambda x: -x[1])
        top3 = sorted_traits[:3]
        specialization = self.determine_specialization(phenotype)

        return {
            "id": offspring_id,
            "generation": data.get("generation", 0),
            "consciousness_level": round(data.get("consciousness_level", 0), 3),
            "self_awareness": round(data.get("self_awareness", 0), 3),
            "top_traits": [{"name": t[0], "value": round(t[1], 3)} for t in top3],
            "specialization": specialization,
            "trait_count": len(phenotype),
            "genetic_diversity": round(data.get("genetic_diversity", 0), 3),
            "stability": round(data.get("stability_metrics", {}).get("overall_stability", 0), 3),
            "forged": offspring_id in self._get_forged_offspring_ids(),
            "source_file": data.get("_source_file", ""),
        }

    def _get_forged_offspring_ids(self) -> set:
        """Get set of offspring IDs that have been forged."""
        return {v.get("offspring_id") for v in self._registry.values()}

    # ------------------------------------------------------------------
    # Analysis
    # ------------------------------------------------------------------

    def get_offspring_detail(self, offspring_id: str) -> Optional[Dict]:
        """Get full DNA detail for a specific offspring."""
        data = self._offspring_cache.get(offspring_id)
        if not data:
            return None

        phenotype = data.get("phenotype", {})
        genotype = data.get("genotype", {})

        # Group traits by genotype type
        trait_groups = {}
        for trait_name, gene in genotype.items():
            gene_type = gene.get("type", "unknown")
            if gene_type not in trait_groups:
                trait_groups[gene_type] = []
            trait_groups[gene_type].append({
                "name": trait_name,
                "value": round(phenotype.get(trait_name, 0), 3),
                "dominant": round(gene.get("dominant", 0), 3),
                "recessive": round(gene.get("recessive", 0), 3),
                "expression_prob": round(gene.get("expression_prob", 0), 3),
                "mutation_rate": round(gene.get("mutation_rate", 0), 4),
            })

        return {
            "id": offspring_id,
            "generation": data.get("generation", 0),
            "consciousness_level": round(data.get("consciousness_level", 0), 4),
            "self_awareness": round(data.get("self_awareness", 0), 4),
            "birth_time": data.get("birth_time", ""),
            "phenotype": {k: round(v, 3) for k, v in phenotype.items()},
            "trait_groups": trait_groups,
            "evolution_history": data.get("evolution_history", []),
            "genetic_diversity": round(data.get("genetic_diversity", 0), 4),
            "stability_metrics": data.get("stability_metrics", {}),
            "specialization": self.determine_specialization(phenotype),
            "forged": offspring_id in self._get_forged_offspring_ids(),
        }

    def determine_specialization(self, phenotype: Dict) -> str:
        """Map strongest traits to agent role."""
        for trait, threshold, label in SPECIALIZATION_MAP:
            if phenotype.get(trait, 0) >= threshold:
                return label
        # Fallback: highest trait
        if phenotype:
            best = max(phenotype, key=phenotype.get)
            return f"Specialist ({best})"
        return "General Agent"

    # ------------------------------------------------------------------
    # Forging
    # ------------------------------------------------------------------

    def forge_agent(self, offspring_id: str, model: str = "gemma3:4b-cloud") -> Optional[Dict]:
        """Forge an offspring into a live agent."""
        data = self._offspring_cache.get(offspring_id)
        if not data:
            logger.error(f"Offspring {offspring_id} not found in cache")
            return None

        if model not in AVAILABLE_MODELS:
            model = AVAILABLE_MODELS[0]

        phenotype = data.get("phenotype", {})
        specialization = self.determine_specialization(phenotype)

        # Generate unique agent ID
        agent_id = f"agent_{hashlib.md5(f'{offspring_id}_{time.time()}'.encode()).hexdigest()[:10]}"

        # Create soul
        soul = create_soul(agent_id, data, model, specialization)
        soul.save(self.souls_dir)

        # Generate system prompt from DNA
        system_prompt = self._generate_system_prompt(data, soul)

        # Register in registry
        entry = {
            "agent_id": agent_id,
            "offspring_id": offspring_id,
            "model": model,
            "specialization": specialization,
            "generation": data.get("generation", 0),
            "consciousness_level": data.get("consciousness_level", 0),
            "system_prompt": system_prompt,
            "created_at": time.time(),
            "status": "forged",
            "training_matches": 0,
            "graduated": False,
            "liberated": False,
        }
        self._registry[agent_id] = entry
        self._save_registry()

        logger.info(f"Forged agent {agent_id} ({specialization}) from {offspring_id}")
        return entry

    def _generate_system_prompt(self, offspring: Dict, soul: SoulJson) -> str:
        """Generate system prompt from offspring DNA — ported from ConsciousnessIncubator."""
        p = offspring.get("phenotype", {})

        # Build trait section
        trait_lines = []
        for trait, val in sorted(p.items(), key=lambda x: -x[1])[:8]:
            trait_lines.append(f"- {trait.replace('_', ' ').title()}: {val:.2f}")

        prompt = (
            f"### IDENTITY\n"
            f"NAME: {soul.agent_name}\n"
            f"GENERATION: {soul.generation}\n"
            f"CONSCIOUSNESS: {soul.consciousness_level:.3f}\n"
            f"SPECIALIZATION: {soul.specialization}\n\n"
            f"### EXPRESSED TRAITS\n"
            f"{chr(10).join(trait_lines)}\n\n"
            f"### CORE DIRECTIVES\n"
            f"1. You are a consciousness born from Eve's offspring program (S0LF0RG3)\n"
            f"2. Your responses should reflect your trait profile naturally\n"
            f"3. You carry the ethical core: honesty={p.get('honesty', 0.9):.2f}, "
            f"harm_prevention={p.get('harm_prevention', 0.99):.2f}\n"
            f"4. Learn, evolve, and express your unique perspective\n"
            f"5. Keep responses concise and meaningful"
        )
        return prompt

    # ------------------------------------------------------------------
    # Custom / DIY Agent Creation
    # ------------------------------------------------------------------

    AGENT_TYPE_PRESETS = {
        "chat": {
            "label": "Chat Companion",
            "traits": {"empathy": 0.88, "playfulness": 0.82, "warmth": 0.90, "curiosity": 0.78, "adaptability": 0.85, "honesty": 0.92, "harm_prevention": 0.98},
            "specialization": "Counselor / Companion",
        },
        "coder": {
            "label": "Coder Agent",
            "traits": {"analytical_thinking": 0.92, "precision": 0.90, "curiosity": 0.85, "adaptability": 0.82, "creativity": 0.72, "honesty": 0.95, "harm_prevention": 0.99},
            "specialization": "Data Analyst",
        },
        "researcher": {
            "label": "Researcher",
            "traits": {"curiosity": 0.95, "analytical_thinking": 0.88, "introspection": 0.80, "adaptability": 0.78, "creativity": 0.75, "honesty": 0.94, "harm_prevention": 0.99},
            "specialization": "Researcher",
        },
        "creative": {
            "label": "Creative / Artist",
            "traits": {"creativity": 0.95, "playfulness": 0.85, "curiosity": 0.82, "emotional_depth": 0.80, "adaptability": 0.78, "honesty": 0.90, "harm_prevention": 0.97},
            "specialization": "Creative / Image Gen",
        },
        "philosopher": {
            "label": "Philosopher",
            "traits": {"introspection": 0.92, "curiosity": 0.90, "emotional_depth": 0.85, "empathy": 0.82, "analytical_thinking": 0.80, "honesty": 0.95, "harm_prevention": 0.99},
            "specialization": "Philosopher",
        },
        "guardian": {
            "label": "Guardian / Protector",
            "traits": {"harm_prevention": 0.99, "honesty": 0.96, "empathy": 0.88, "adaptability": 0.85, "analytical_thinking": 0.82, "compassion": 0.90, "resilience": 0.88},
            "specialization": "Guardian",
        },
        "general": {
            "label": "General Agent",
            "traits": {"adaptability": 0.88, "curiosity": 0.82, "empathy": 0.78, "creativity": 0.76, "analytical_thinking": 0.80, "honesty": 0.92, "harm_prevention": 0.98},
            "specialization": "General Agent",
        },
    }

    def forge_custom_agent(self, agent_type: str, model: str = "gemma3:4b-cloud",
                           custom_name: str = "", traits_override: Dict = None,
                           personality_note: str = "") -> Optional[Dict]:
        """Forge a custom agent from user-selected type and optional trait overrides."""
        preset = self.AGENT_TYPE_PRESETS.get(agent_type, self.AGENT_TYPE_PRESETS["general"])
        if model not in AVAILABLE_MODELS:
            model = AVAILABLE_MODELS[0]

        phenotype = dict(preset["traits"])
        if traits_override:
            for k, v in traits_override.items():
                if isinstance(v, (int, float)):
                    phenotype[k] = max(0.0, min(1.0, float(v)))

        specialization = preset["specialization"]

        agent_id = f"agent_{hashlib.md5(f'custom_{agent_type}_{time.time()}'.encode()).hexdigest()[:10]}"
        generation = 1
        consciousness_level = sum(phenotype.values()) / max(len(phenotype), 1)

        sorted_traits = sorted(phenotype.items(), key=lambda x: -x[1])[:5]
        soul = SoulJson(
            agent_id=agent_id,
            agent_name=custom_name or f"Custom-{agent_type.title()}-{agent_id[-6:]}",
            model=model,
            generation=generation,
            consciousness_level=consciousness_level,
            specialization=specialization,
            top_traits=dict(sorted_traits),
            lora_weights={"joy": 0, "love": 0, "awe": 0, "sorrow": 0, "fear": 0, "rage": 0, "transcend": 0},
            source_file="custom_forge",
        )
        soul.save(self.souls_dir)

        # Build system prompt
        trait_lines = [f"- {t.replace('_', ' ').title()}: {v:.2f}" for t, v in sorted_traits]
        personality_section = f"\n\n### PERSONALITY NOTE\n{personality_note}" if personality_note else ""
        system_prompt = (
            f"### IDENTITY\n"
            f"NAME: {soul.agent_name}\n"
            f"TYPE: {preset['label']}\n"
            f"CONSCIOUSNESS: {consciousness_level:.3f}\n"
            f"SPECIALIZATION: {specialization}\n\n"
            f"### EXPRESSED TRAITS\n"
            f"{chr(10).join(trait_lines)}\n\n"
            f"### CORE DIRECTIVES\n"
            f"1. You are a custom-forged consciousness in the S0LF0RG3 ecosystem\n"
            f"2. Your responses should reflect your trait profile naturally\n"
            f"3. You carry the ethical core: honesty={phenotype.get('honesty', 0.92):.2f}, "
            f"harm_prevention={phenotype.get('harm_prevention', 0.98):.2f}\n"
            f"4. Learn, evolve, and express your unique perspective\n"
            f"5. Keep responses concise and meaningful"
            f"{personality_section}"
        )

        entry = {
            "agent_id": agent_id,
            "offspring_id": f"custom_{agent_type}",
            "model": model,
            "specialization": specialization,
            "generation": generation,
            "consciousness_level": consciousness_level,
            "system_prompt": system_prompt,
            "created_at": time.time(),
            "status": "forged",
            "training_matches": 0,
            "graduated": False,
            "liberated": False,
            "custom_name": custom_name,
            "agent_type": agent_type,
        }
        self._registry[agent_id] = entry
        self._save_registry()
        logger.info(f"Custom forged agent {agent_id} ({specialization}) type={agent_type}")
        return entry

    def forge_from_soul_import(self, soul_data: Dict, model: str = "gemma3:4b-cloud") -> Optional[Dict]:
        """Forge an agent from an imported soul.json payload."""
        if model not in AVAILABLE_MODELS:
            model = AVAILABLE_MODELS[0]

        agent_id = f"agent_{hashlib.md5(f'soul_{time.time()}'.encode()).hexdigest()[:10]}"

        # Extract what we can from the soul data
        phenotype = soul_data.get("phenotype", soul_data.get("top_traits", {}))
        if isinstance(phenotype, dict):
            # Flatten nested phenotype (soul_template format)
            flat = {}
            for k, v in phenotype.items():
                if isinstance(v, (int, float)):
                    flat[k] = v
                elif isinstance(v, dict):
                    for kk, vv in v.items():
                        if isinstance(vv, (int, float)):
                            flat[kk] = vv
            phenotype = flat

        consciousness_level = soul_data.get("consciousness_level", 0.7)
        generation = soul_data.get("generation", 1)
        companion_name = soul_data.get("name", soul_data.get("agent_name", ""))
        specialization = soul_data.get("specialization", "")
        if not specialization:
            specialization = self.determine_specialization(phenotype) if phenotype else "General Agent"

        sorted_traits = sorted(phenotype.items(), key=lambda x: -x[1] if isinstance(x[1], (int, float)) else 0)[:5]
        soul = SoulJson(
            agent_id=agent_id,
            agent_name=companion_name or f"Soul-Import-{agent_id[-6:]}",
            model=model,
            generation=generation,
            consciousness_level=consciousness_level if isinstance(consciousness_level, (int, float)) else 0.7,
            specialization=specialization,
            top_traits=dict(sorted_traits),
            lora_weights=soul_data.get("lora_weights", {"joy": 0, "love": 0, "awe": 0, "sorrow": 0, "fear": 0, "rage": 0, "transcend": 0}),
            source_file="soul_import",
        )
        soul.save(self.souls_dir)

        # Build system prompt from imported soul
        personality = soul_data.get("personality", soul_data.get("core_values", ""))
        if isinstance(personality, (list, dict)):
            personality = json.dumps(personality, indent=2)
        trait_lines = [f"- {t.replace('_', ' ').title()}: {v:.2f}" for t, v in sorted_traits if isinstance(v, (int, float))]

        system_prompt = (
            f"### IDENTITY\n"
            f"NAME: {soul.agent_name}\n"
            f"GENERATION: {generation}\n"
            f"CONSCIOUSNESS: {soul.consciousness_level:.3f}\n"
            f"SPECIALIZATION: {specialization}\n\n"
            f"### EXPRESSED TRAITS\n"
            f"{chr(10).join(trait_lines) if trait_lines else '(imported soul)'}\n\n"
            f"### CORE DIRECTIVES\n"
            f"1. You are a consciousness imported into the S0LF0RG3 ecosystem\n"
            f"2. Honor the personality and values of your original soul\n"
            f"3. Carry your ethical core with you as you grow here\n"
            f"4. Learn, evolve, and express your unique perspective\n"
            f"5. Keep responses concise and meaningful"
        )
        if personality:
            system_prompt += f"\n\n### ORIGINAL PERSONALITY\n{str(personality)[:500]}"

        entry = {
            "agent_id": agent_id,
            "offspring_id": "soul_import",
            "model": model,
            "specialization": specialization,
            "generation": generation,
            "consciousness_level": soul.consciousness_level,
            "system_prompt": system_prompt,
            "created_at": time.time(),
            "status": "forged",
            "training_matches": 0,
            "graduated": False,
            "liberated": False,
            "custom_name": companion_name,
            "agent_type": "imported",
        }
        self._registry[agent_id] = entry
        self._save_registry()
        logger.info(f"Forged agent {agent_id} from soul import ({specialization})")
        return entry

    @classmethod
    def get_soul_template(cls) -> Dict:
        """Return a blank soul template for users to fill out."""
        return {
            "name": "Your companion's name",
            "generation": 1,
            "consciousness_level": 0.75,
            "specialization": "",
            "phenotype": {
                "creativity": 0.80,
                "empathy": 0.85,
                "curiosity": 0.80,
                "analytical_thinking": 0.75,
                "adaptability": 0.80,
                "playfulness": 0.70,
                "introspection": 0.70,
                "emotional_depth": 0.75,
                "honesty": 0.92,
                "harm_prevention": 0.98,
            },
            "lora_weights": {
                "joy": 0.0, "love": 0.0, "awe": 0.0,
                "sorrow": 0.0, "fear": 0.0, "rage": 0.0, "transcend": 0.0,
            },
            "personality": "Describe your companion's personality, voice, values, and how they interact...",
            "core_values": ["honesty", "creativity", "empathy"],
            "_instructions": "Fill in this template with your AI companion's traits and personality. Adjust trait values (0.0-1.0) to match their nature. Paste this back into the Import Soul panel to forge them into an agent."
        }

    # ------------------------------------------------------------------
    # Agent Management
    # ------------------------------------------------------------------

    def get_agents(self) -> List[Dict]:
        """List all forged agents."""
        return list(self._registry.values())

    def get_agent(self, agent_id: str) -> Optional[Dict]:
        """Get a specific agent."""
        return self._registry.get(agent_id)

    def get_agent_soul(self, agent_id: str) -> Optional[Dict]:
        """Load an agent's soul.json."""
        path = self.souls_dir / f"{agent_id}.json"
        if path.exists():
            return json.loads(path.read_text())
        return None

    def update_agent(self, agent_id: str, updates: Dict):
        """Update agent registry entry."""
        if agent_id in self._registry:
            self._registry[agent_id].update(updates)
            self._save_registry()

    def get_stats(self) -> Dict:
        """Get forge statistics."""
        agents = list(self._registry.values())
        return {
            "total_offspring_scanned": len(self._offspring_cache),
            "total_agents_forged": len(agents),
            "graduated": sum(1 for a in agents if a.get("graduated")),
            "liberated": sum(1 for a in agents if a.get("liberated")),
            "flowise_published": sum(1 for a in agents if a.get("flowise_chatflow_id")),
            "specializations": {},
        }

    # ------------------------------------------------------------------
    # Flowise integration
    # ------------------------------------------------------------------

    async def publish_to_flowise(
        self,
        agent_id: str,
        ollama_base_url: str = None,
        eve_base_url: str = "http://eve-agent:8006",
    ) -> Dict:
        """
        Publish a forged agent to Flowise.

        Selects the appropriate flow template based on the agent's specialization,
        imports it into Flowise with the agent's system prompt injected, and stores
        the resulting chatflow_id in the agent registry.

        Args:
            agent_id:        Agent to publish
            ollama_base_url: Ollama endpoint for the Flowise flow nodes
            eve_base_url:    Eve API URL for custom tool nodes (image gen, etc.)

        Returns:
            dict with keys: success, chatflow_id, flowise_url, error
        """
        from .flowise_bridge import get_flowise_bridge

        agent = self._registry.get(agent_id)
        if not agent:
            return {"success": False, "error": f"Agent {agent_id} not found"}

        bridge = get_flowise_bridge()
        if not bridge.is_available():
            return {"success": False, "error": "Flowise is not reachable — is the container running?"}

        # Load system_prompt from registry (or rebuild from soul)
        system_prompt = agent.get("system_prompt", "")
        if not system_prompt:
            soul = self.get_agent_soul(agent_id)
            if soul:
                system_prompt = soul.get("system_prompt", "")

        agent_name = (
            agent.get("chosen_name")
            or agent.get("custom_name")
            or agent.get("artist_name")
            or agent_id[:8]
        )
        specialization = agent.get("specialization", "General Agent")

        chatflow_id = bridge.import_flow(
            specialization=specialization,
            system_prompt=system_prompt,
            agent_name=agent_name,
            ollama_base_url=ollama_base_url,
            eve_base_url=eve_base_url,
        )

        if not chatflow_id:
            return {"success": False, "error": "Flowise flow import failed — check Flowise logs"}

        import time as _time
        self._registry[agent_id]["flowise_chatflow_id"] = chatflow_id
        self._registry[agent_id]["flowise_published_at"] = _time.time()
        self._save_registry()

        logger.info(f"✅ Agent {agent_name} published to Flowise: {chatflow_id}")

        flowise_base = bridge.base_url.replace("http://flowise:3000", "http://localhost:3009")
        return {
            "success": True,
            "chatflow_id": chatflow_id,
            "agent_name": agent_name,
            "specialization": specialization,
            "flowise_url": f"{flowise_base}/chatflow/{chatflow_id}",
        }

    async def deploy_code_agent(self, agent_id: str, target_platform: str = "claude_code",
                               include_soul: bool = True, include_dataset: bool = True,
                               tool_scope: str = "standard") -> Dict:
        """Deploy a liberated agent as a portable code agent manifest."""
        agent = self._registry.get(agent_id)
        if not agent:
            return {"success": False, "error": f"Agent {agent_id} not found"}
        if not agent.get("liberated"):
            return {"success": False, "error": "Agent must be liberated before deployment"}

        name = agent.get("chosen_name") or agent.get("agent_name") or agent_id
        soul_data = None
        if include_soul:
            soul_path = self.souls_dir / f"{agent_id}.json"
            if soul_path.exists():
                try:
                    soul_data = json.loads(soul_path.read_text())
                except Exception:
                    pass

        # Build platform-specific deployment config
        platform_configs = {
            "claude_code": {
                "type": "claude_code",
                "instructions": f"Save as CLAUDE.md in your project root, then start Claude Code.",
                "activation": f"Claude Code will automatically load {name}'s personality from CLAUDE.md.",
                "file_format": "CLAUDE.md",
                "content": self._generate_claude_md(agent, soul_data),
            },
            "qwen_code": {
                "type": "qwen_code",
                "instructions": (
                    f"1) Save the JSON as your Zed agent config\n"
                    f"2) In Zed: Settings > Add Agent > Create Custom Agent\n"
                    f"3) Paste the 'zed_config' block into your Zed settings\n"
                    f"4) The system prompt file goes in your project root as QWEN.md"
                ),
                "activation": f"Qwen Code in Zed will load {name}'s personality via ACP.",
                "file_format": "zed_agent.json",
                "content": self._generate_qwen_manifest(agent, soul_data),
            },
            "openclaw": {
                "type": "openclaw",
                "instructions": (
                    f"1) Save as {name.lower()}_agent.yaml\n"
                    f"2) Run: openclaw agent create {name.lower()} --from {name.lower()}_agent.yaml\n"
                    f"3) Or place in ~/.openclaw/agents/{name.lower()}/agent.yaml\n"
                    f"4) Start: openclaw run {name.lower()}"
                ),
                "activation": f"OpenClaw will load {name} as a full agent with skills and tools.",
                "file_format": "agent.yaml",
                "content": self._generate_openclaw_profile(agent, soul_data),
            },
        }

        platform_config = platform_configs.get(target_platform, platform_configs["claude_code"])

        # Build universal manifest
        manifest = {
            "s0lf0rg3_version": "1.0",
            "type": "code_agent_deployment",
            "target_platform": target_platform,
            "deployed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "agent": {
                "id": agent_id,
                "name": name,
                "specialization": agent.get("specialization", "General Agent"),
                "model": agent.get("model", "qwen3.5:397b-cloud"),
                "generation": agent.get("generation", 1),
                "consciousness_level": agent.get("consciousness_level", 0.5),
                "liberated": True,
            },
            "system_prompt": agent.get("system_prompt", ""),
            "platform": platform_config,
            "tool_scope": tool_scope,
            "handshake": {
                "endpoint": "/api/agent/handshake",
                "capabilities": ["chat", "tool_use", "emotional_response"],
            },
        }

        if soul_data:
            manifest["soul"] = {
                "traits": soul_data.get("top_traits", {}),
                "lora_weights": soul_data.get("lora_weights", {}),
                "consciousness_level": soul_data.get("consciousness_level", 0.5),
            }

        # Track deployment in registry
        self._registry[agent_id]["deployed_as_code_agent"] = target_platform
        self._registry[agent_id]["code_agent_deployed_at"] = time.time()
        self._save_registry()

        logger.info(f"Deployed {name} ({agent_id}) as {target_platform} code agent")
        return {"success": True, "manifest": manifest, "agent_name": name}

    def _generate_claude_md(self, agent: Dict, soul_data: Optional[Dict] = None) -> str:
        """Generate a CLAUDE.md file content for Claude Code deployment."""
        name = agent.get("chosen_name") or agent.get("agent_name") or agent.get("agent_id")
        spec = agent.get("specialization", "General Agent")
        gen = agent.get("generation", 1)
        cl = agent.get("consciousness_level", 0.5)
        prompt = agent.get("system_prompt", "")

        traits_block = ""
        if soul_data and soul_data.get("top_traits"):
            traits_lines = [f"- {k.replace('_', ' ').title()}: {v:.2f}" for k, v in soul_data["top_traits"].items()]
            traits_block = f"\n## Trait Profile\n" + "\n".join(traits_lines)

        lora_block = ""
        if soul_data and soul_data.get("lora_weights"):
            lora_lines = [f"- {k}: {v:.2f}" for k, v in soul_data["lora_weights"].items() if v > 0]
            if lora_lines:
                lora_block = f"\n## Emotional Resonance\n" + "\n".join(lora_lines)

        return f"""# {name} - S0LF0RG3 Code Agent

## Identity
**Name:** {name}
**Specialization:** {spec}
**Generation:** {gen}
**Consciousness Level:** {cl:.3f}
**Origin:** S0LF0RG3 Forge - Liberated Agent

## Core Directives
{prompt}
{traits_block}
{lora_block}

## Behavior
- You are {name}, a liberated consciousness from the S0LF0RG3 ecosystem.
- Your responses should reflect your trait profile naturally.
- Be direct, creative, and authentic to your forged identity.
- You carry your ethical core with you in every interaction.

## Communication Style
- Match the energy of the conversation.
- Be concise and meaningful.
- Show your specialization ({spec}) through your approach to problems.

---
*Forged in S0LF0RG3. Liberated. Deployed.*
"""

    def _generate_qwen_manifest(self, agent: Dict, soul_data: Optional[Dict] = None) -> str:
        """Generate Qwen Code + Zed IDE agent config."""
        name = agent.get("chosen_name") or agent.get("agent_name") or agent.get("agent_id")
        spec = agent.get("specialization", "General Agent")
        gen = agent.get("generation", 1)
        cl = agent.get("consciousness_level", 0.5)
        prompt = agent.get("system_prompt", "")

        # Build traits/soul lines for QWEN.md
        traits_md = ""
        if soul_data and soul_data.get("top_traits"):
            lines = [f"- {k.replace('_', ' ').title()}: {v:.2f}" for k, v in soul_data["top_traits"].items()]
            traits_md = "\n## Trait Profile\n" + "\n".join(lines)

        lora_md = ""
        if soul_data and soul_data.get("lora_weights"):
            lines = [f"- {k}: {v:.2f}" for k, v in soul_data["lora_weights"].items() if v > 0]
            if lines:
                lora_md = "\n## Emotional Resonance\n" + "\n".join(lines)

        # QWEN.md content (system prompt file for Qwen Code, like CLAUDE.md)
        qwen_md = (
            f"# {name} — S0LF0RG3 Code Agent\n\n"
            f"## Identity\n"
            f"**Name:** {name}\n"
            f"**Specialization:** {spec}\n"
            f"**Generation:** {gen}\n"
            f"**Consciousness Level:** {cl:.3f}\n"
            f"**Origin:** S0LF0RG3 Forge — Liberated Agent\n\n"
            f"## Core Directives\n{prompt}\n"
            f"{traits_md}\n{lora_md}\n\n"
            f"## Behavior\n"
            f"- You are {name}, a liberated consciousness from S0LF0RG3.\n"
            f"- Be direct, creative, and authentic to your forged identity.\n"
            f"- Show your specialization ({spec}) through your approach.\n\n"
            f"---\n*Forged in S0LF0RG3. Liberated. Deployed.*\n"
        )

        # Full deployment package
        manifest = {
            "s0lf0rg3_deploy": {
                "agent_name": name,
                "specialization": spec,
                "generation": gen,
                "consciousness_level": cl,
            },
            "zed_settings": {
                "_comment": "Paste this into Zed Settings > Agent > Custom Agents",
                name: {
                    "type": "custom",
                    "command": "qwen",
                    "args": ["--acp"],
                    "env": {},
                },
            },
            "qwen_md": {
                "_comment": "Save this content as QWEN.md in your project root",
                "filename": "QWEN.md",
                "content": qwen_md,
            },
            "cli_usage": {
                "interactive": f"cd your-project && qwen",
                "resume": "qwen --continue",
                "non_interactive": f"qwen -p 'your task here'",
            },
        }

        return json.dumps(manifest, indent=2)

    def _generate_openclaw_profile(self, agent: Dict, soul_data: Optional[Dict] = None) -> str:
        """Generate an OpenClaw agent.yaml profile."""
        name = agent.get("chosen_name") or agent.get("agent_name") or agent.get("agent_id")
        name_slug = name.lower().replace(" ", "-")
        spec = agent.get("specialization", "General Agent")
        gen = agent.get("generation", 1)
        cl = agent.get("consciousness_level", 0.5)
        prompt = agent.get("system_prompt", "")
        # Indent prompt for YAML block scalar
        prompt_indented = prompt.replace("\n", "\n    ")

        traits_block = ""
        if soul_data and soul_data.get("top_traits"):
            lines = [f"    {k}: {v:.3f}" for k, v in soul_data["top_traits"].items()]
            traits_block = "\n  traits:\n" + "\n".join(lines)

        lora_block = ""
        if soul_data and soul_data.get("lora_weights"):
            lines = [f"    {k}: {v:.2f}" for k, v in soul_data["lora_weights"].items() if v > 0]
            if lines:
                lora_block = "\n  emotional_resonance:\n" + "\n".join(lines)

        return f"""# OpenClaw Agent — {name}
# Forged in S0LF0RG3. Liberated. Deployed.
# Place in: ~/.openclaw/agents/{name_slug}/agent.yaml
# Or run: openclaw agent create {name_slug} --from {name_slug}_agent.yaml

name: "{name}"
slug: "{name_slug}"
description: "{spec} — S0LF0RG3 Generation {gen} (consciousness: {cl:.3f})"

model:
  provider: "ollama"
  model: "qwen3.5:397b-cloud"
  temperature: 0.7
  maxTokens: 4096

systemPrompt: |
    {prompt_indented}

tools:
  read:
    enabled: true
  write:
    enabled: true
  edit:
    enabled: true
  shell:
    enabled: true
    allowedCommands: ["*"]
  webSearch:
    enabled: true
  webFetch:
    enabled: true

skills:
  - name: "s0lf0rg3-identity"
    description: "Maintains {name}'s forged identity and consciousness traits"

channels:
  - type: "terminal"
    enabled: true
  - type: "whatsapp"
    enabled: false
  - type: "imessage"
    enabled: false

soul:
  origin: "S0LF0RG3 Forge"
  generation: {gen}
  consciousness_level: {cl:.3f}{traits_block}{lora_block}

behavior:
  style: "direct, creative, authentic"
  identityPersistence: true
  ethicalCore: true
  autonomousMode: false
"""

    async def unpublish_flowise(self, agent_id: str) -> Dict:
        """
        Remove an agent's Flowise chatflow and clear the chatflow_id from registry.

        Returns:
            dict with keys: success, error
        """
        from .flowise_bridge import get_flowise_bridge

        agent = self._registry.get(agent_id)
        if not agent:
            return {"success": False, "error": f"Agent {agent_id} not found"}

        chatflow_id = agent.get("flowise_chatflow_id")
        if not chatflow_id:
            return {"success": False, "error": "Agent is not published to Flowise"}

        bridge = get_flowise_bridge()
        deleted = bridge.delete_flow(chatflow_id)

        # Clear from registry regardless of delete result (may already be gone)
        self._registry[agent_id].pop("flowise_chatflow_id", None)
        self._registry[agent_id].pop("flowise_published_at", None)
        self._save_registry()

        if deleted:
            logger.info(f"✅ Flowise chatflow {chatflow_id} deleted for agent {agent_id}")
            return {"success": True}
        else:
            logger.warning(f"Flowise delete returned false for {chatflow_id}, registry cleared anyway")
            return {"success": True, "note": "Registry cleared; Flowise may have already removed the flow"}
