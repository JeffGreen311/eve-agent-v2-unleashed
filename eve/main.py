"""Entry point for running Eve Agent as a module."""

import sys


def main():
    """Main entry point for eve-agent CLI."""
    from eve.connectors.cli_connector import CLIConnector
    from eve.config import Settings

    settings = Settings()
    connector = CLIConnector(settings)

    try:
        connector.run()
    except KeyboardInterrupt:
        print("\nEve signing off. Until next time.")
        sys.exit(0)


if __name__ == "__main__":
    main()
