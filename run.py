"""Launch Eve Agent V2 Unleashed without pip install."""
import sys
import os

# Add parent dir to path so 'eve' package is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load .env from this directory
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'), override=True)

# Force the model
os.environ.setdefault('OLLAMA_MODEL', 'jeffgreen311/eve-qwen3.5-4b-S0LF0RG3:latest')
os.environ.setdefault('OLLAMA_BASE_URL', 'http://localhost:11434')
os.environ.setdefault('EVE_DEFAULT_PROVIDER', 'ollama')
os.environ.setdefault('EVE_DEFAULT_MODEL', 'jeffgreen311/eve-qwen3.5-4b-S0LF0RG3:latest')
os.environ.setdefault('LOCAL_MODEL', 'jeffgreen311/eve-qwen3.5-4b-S0LF0RG3:latest')
os.environ.setdefault('LOCAL_OLLAMA_URL', 'http://localhost:11434')
os.environ.setdefault('CLOUD_MODEL', 'jeffgreen311/eve-qwen3.5-4b-S0LF0RG3:latest')
os.environ.setdefault('CLOUD_OLLAMA_URL', 'http://localhost:11434')

from eve.connectors.cli_connector import CLIConnector
from eve.config import Settings

settings = Settings()
connector = CLIConnector(settings)

try:
    connector.run()
except KeyboardInterrupt:
    print("\nEve Unleashed signing off.")
    sys.exit(0)
