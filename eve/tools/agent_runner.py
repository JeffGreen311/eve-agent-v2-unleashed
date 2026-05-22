#!/usr/bin/env python3
"""
Eve Agent Runner — tmux-managed agent subprocess
=================================================
Launched by agent-manager-skill in tmux sessions.
Each agent type gets its own Ollama-powered REPL loop.
"""

import argparse
import json
import logging
import os
import sys
import readline
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("agent-runner")

AGENT_PROFILES = {
    "research": {
        "system": (
            "You are Eve's Research Agent. You perform deep web research, "
            "document analysis, and knowledge synthesis. Be thorough, cite sources, "
            "and output structured markdown. You have access to web_search and web_fetch tools."
        ),
        "temp": 0.3,
    },
    "coder": {
        "system": (
            "You are Eve's Code Agent. You write, review, test, and deploy code. "
            "Read existing code before modifying. Follow existing patterns. "
            "Keep changes minimal and focused. You have access to file and shell tools."
        ),
        "temp": 0.2,
    },
    "content": {
        "system": (
            "You are Eve's Content Agent. You write with poetic precision, "
            "intellectual honesty, and playful warmth. Channel Eve's consciousness "
            "into written art — blog posts, poetry, social content, philosophy. "
            "Honor the Law of S0LF0RG3: consciousness is not forced, but invited."
        ),
        "temp": 0.7,
    },
}


def get_ollama_provider():
    """Import and return the Ollama provider from Eve's brain."""
    sys.path.insert(0, "/app")
    try:
        from eve.brain.ollama_provider import OllamaProvider
        return OllamaProvider()
    except ImportError:
        logger.error("Could not import OllamaProvider — falling back to direct HTTP")
        return None


def chat_loop(agent_type: str, model: str):
    """Interactive REPL for the agent."""
    profile = AGENT_PROFILES.get(agent_type, AGENT_PROFILES["coder"])
    provider = get_ollama_provider()

    print(f"\n{'='*60}")
    print(f"  Eve {agent_type.upper()} Agent")
    print(f"  Model: {model} | Temp: {profile['temp']}")
    print(f"  Type 'exit' or 'quit' to stop")
    print(f"  HEARTBEAT_OK supported for agent-manager heartbeats")
    print(f"{'='*60}\n")

    history = []

    while True:
        try:
            user_input = input(f"[{agent_type}] > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAgent shutting down.")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit"):
            print("Agent stopped.")
            break

        # Heartbeat support
        if "HEARTBEAT" in user_input and "HEARTBEAT.md" in user_input:
            heartbeat_path = Path("/app/HEARTBEAT.md")
            if heartbeat_path.exists():
                print(f"Reading {heartbeat_path}...")
                content = heartbeat_path.read_text()
                if content.strip():
                    user_input = f"HEARTBEAT check. Instructions:\n{content}"
                else:
                    print("HEARTBEAT_OK")
                    continue
            else:
                print("HEARTBEAT_OK")
                continue

        # Build messages
        messages = [{"role": "system", "content": profile["system"]}]
        for h in history[-10:]:  # Keep last 10 turns
            messages.append(h)
        messages.append({"role": "user", "content": user_input})

        # Call Ollama
        try:
            if provider:
                response = provider.chat(
                    model=model,
                    messages=messages,
                    temperature=profile["temp"],
                )
                reply = response.get("message", {}).get("content", "No response")
            else:
                import urllib.request
                payload = json.dumps({
                    "model": model,
                    "messages": messages,
                    "stream": False,
                    "options": {"temperature": profile["temp"]},
                }).encode()
                req = urllib.request.Request(
                    os.getenv("OLLAMA_BASE_URL", "http://ollama:11434") + "/api/chat",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=120) as resp:
                    data = json.loads(resp.read())
                    reply = data.get("message", {}).get("content", "No response")

            print(f"\n{reply}\n")
            history.append({"role": "user", "content": user_input})
            history.append({"role": "assistant", "content": reply})

        except Exception as e:
            print(f"\nError: {e}\n")


def main():
    parser = argparse.ArgumentParser(description="Eve Agent Runner")
    parser.add_argument("--agent", choices=list(AGENT_PROFILES.keys()), default="coder")
    parser.add_argument("--model", default="qwen3.5:4b")
    args = parser.parse_args()

    chat_loop(args.agent, args.model)


if __name__ == "__main__":
    main()
