import os

# import readline
import atexit
import yaml
from datetime import datetime
from typing import List, Dict, Optional
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from openai import OpenAI
from database import DatabaseManager, ChatMessage, ChatSession


class ChatCLI:
    def __init__(self, config: dict):
        self.config = config
        self.db = DatabaseManager(config["database_file"])
        self.api_key = config["api_key"]
        self.base_url = config["base_url"]
        self.current_model = config["default_model"]
        self.history_file = os.path.expanduser(config["history_file"])
        self.current_session_id = None
        self.console = Console()
        self.load_history()
        self.load_models_from_yaml("models.yaml")

    def load_history(self):
        if os.path.exists(self.history_file):
            pass
        #     readline.read_history_file(self.history_file)
        # atexit.register(readline.write_history_file, self.history_file)

    def load_models_from_yaml(self, models_file: str):
        if os.path.exists(models_file):
            with open(models_file, "r") as f:
                data = yaml.safe_load(f)
                for model in data.get("models", []):
                    self.db.insert_model(model["name"], model.get("description", ""))

    def display_welcome(self):
        welcome_text = """
# AI Chat CLI

Available commands:
- /exit - Exit the application
- /list_models - Show available models
- /switch_model <model_name> - Switch to a different model
- /new_session - Create a new chat session
- /list_sessions - Show all chat sessions
- /change_session <id> - Switch to a different session
- /rename_session <new_title> - Rename the current session
- /delete_session <id> - Delete a session entirely
- /help - Show this help message
"""
        self.console.print(Markdown(welcome_text))

    def display_models(self):
        table = Table(title="Available Models")
        table.add_column("Model Name")
        table.add_column("Description")
        for model, desc in self.db.get_all_models():
            table.add_row(model, desc)
        self.console.print(table)

    def display_sessions(self):
        table = Table(title="Chat Sessions")
        table.add_column("ID")
        table.add_column("Start Time")
        table.add_column("Current Model")
        table.add_column("Title")
        sessions = self.db.get_all_sessions()
        for session_id, start_time, model, title in sessions:
            table.add_row(
                str(session_id),
                start_time.strftime("%Y-%m-%d %H:%M:%S"),
                model,
                title or "Untitled",
            )
        self.console.print(table)

    def display_chat_history(self, session: ChatSession):
        for msg in session.messages:
            role_color = "green" if msg.role == "assistant" else "blue"
            self.console.print(
                Panel(
                    Markdown(msg.content),
                    title=f"[{role_color}]{msg.role.capitalize()}[/] ({msg.model})",
                    subtitle=f"[dim]{msg.timestamp.strftime('%Y-%m-%d %H:%M:%S')}[/]",
                )
            )

    def call_ai_api(self, messages: List[Dict]) -> Optional[str]:
        client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        try:
            response = client.chat.completions.create(
                model=self.current_model, messages=messages
            )
            return response.choices[0].message.content
        except Exception as e:
            self.console.print(f"[red]Error calling AI API: {e}[/]")
            return None

    def process_command(self, command: str) -> bool:
        if command == "/exit":
            return False
        elif command == "/list_models":
            self.display_models()
        elif command.startswith("/switch_model "):
            model = command.split(" ", 1)[1]
            models = [m[0] for m in self.db.get_all_models()]
            if model in models:
                self.current_model = model
                if self.current_session_id:
                    self.db.update_session_model(self.current_session_id, model)
                self.console.print(f"[green]Switched to model: {model}[/]")
            else:
                self.console.print(f"[red]Invalid model: {model}[/]")
        elif command == "/new_session":
            title = Prompt.ask("Enter session title (optional)")
            self.current_session_id = self.db.create_session(
                self.current_model, title=title
            )
            self.console.print(
                f"[green]Created new session: {self.current_session_id}[/]"
            )
        elif command == "/list_sessions":
            self.display_sessions()
        elif command.startswith("/change_session "):
            try:
                session_id = int(command.split(" ", 1)[1])
                session = self.db.get_session(session_id)
                if session:
                    self.current_session_id = session_id
                    self.current_model = session.current_model
                    self.console.print(f"[green]Switched to session: {session_id}[/]")
                    self.display_chat_history(session)
                else:
                    self.console.print(f"[red]Session not found: {session_id}[/]")
            except ValueError:
                self.console.print("[red]Invalid session ID[/]")
        elif command.startswith("/rename_session "):
            new_title = command.split(" ", 1)[1].strip()
            if new_title and self.current_session_id:
                self.db.update_session_title(self.current_session_id, new_title)
                self.console.print(f"[green]Session renamed to: {new_title}[/]")
            else:
                self.console.print(
                    "[red]Provide a valid title and ensure a session is active.[/]"
                )
        elif command.startswith("/delete_session "):
            try:
                session_id = int(command.split(" ", 1)[1])
                confirm = Prompt.ask(
                    f"Are you sure you want to delete session {session_id}? (yes/no)"
                )
                if confirm.lower() == "yes" or "y":
                    self.db.delete_session(session_id)
                    self.console.print(
                        f"[green]Session {session_id} deleted successfully.[/]"
                    )
                    if self.current_session_id == session_id:
                        self.current_session_id = self.db.create_session(
                            self.current_model, "New Session"
                        )
                        self.console.print(
                            f"[green]Switched to new session: {self.current_session_id}[/]"
                        )
                else:
                    self.console.print("[yellow]Delete canceled[/]")
            except ValueError:
                self.console.print("[red]Invalid session ID[/]")
        elif command == "/help":
            self.display_welcome()
        else:
            self.console.print(
                "[red]Unknown command. Type /help for available commands.[/]"
            )
        return True

    def run(self):
        self.display_welcome()
        if not self.current_session_id:
            self.current_session_id = self.db.create_session(
                self.current_model, "New Session"
            )
        running = True
        while running:
            try:
                user_input = Prompt.ask("\n[blue]You[/]").strip()
                if not user_input:
                    continue
                if user_input.startswith("/"):
                    running = self.process_command(user_input)
                    continue
                user_msg = ChatMessage(
                    role="user",
                    content=user_input,
                    timestamp=datetime.now(),
                    model=self.current_model,
                )
                self.db.add_message(self.current_session_id, user_msg)
                session = self.db.get_session(self.current_session_id)
                messages = [
                    {"role": msg.role, "content": msg.content}
                    for msg in session.messages
                ]
                with self.console.status("[bold green]AI is thinking..."):
                    response = self.call_ai_api(messages)
                if response:
                    ai_msg = ChatMessage(
                        role="assistant",
                        content=response,
                        timestamp=datetime.now(),
                        model=self.current_model,
                    )
                    self.db.add_message(self.current_session_id, ai_msg)
                    self.console.print(
                        Panel(
                            Markdown(response),
                            title=f"[green]AI ({self.current_model})[/]",
                            subtitle=f"[dim]{ai_msg.timestamp.strftime('%Y-%m-%d %H:%M:%S')}[/]",
                        )
                    )
                else:
                    self.console.print("[red]Failed to get AI response[/]")
            except KeyboardInterrupt:
                self.console.print("\n[yellow]Use /exit to quit[/]")
            except Exception as e:
                self.console.print(f"[red]Error: {e}[/]")
