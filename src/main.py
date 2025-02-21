import os
import yaml
from chat_cli import ChatCLI


def load_config(config_file="config.yaml"):
    with open(config_file, "r") as f:
        return yaml.safe_load(f)


def main():
    config = load_config("config.yaml")
    if not os.path.exists(config["database_file"]):
        print("Database not found, initializing new database...")
    cli = ChatCLI(config)
    cli.run()


if __name__ == "__main__":
    main()
