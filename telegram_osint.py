import asyncio
import json
import csv
import sqlite3
import argparse
import os
from datetime import datetime
from pathlib import Path
import logging

from telethon import TelegramClient
from telethon.errors import FloodWaitError
from rich.console import Console
from rich.progress import Progress
from rich.table import Table

console = Console()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class TelegramOSINT:
    def __init__(self, api_id, api_hash, session_name='osint_session'):
        self.client = TelegramClient(session_name, api_id, api_hash)
        self.db_path = 'telegram_osint.db'
        self.init_db()

    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS messages (
            id INTEGER, chat_id INTEGER, sender_id INTEGER, date TEXT, 
            text TEXT, media_path TEXT, PRIMARY KEY (id, chat_id))''')
        conn.commit()
        conn.close()

    async def start(self):
        await self.client.start()
        console.print("[green]Client connected successfully![/]")

    async def get_entity(self, identifier):
        try:
            return await self.client.get_entity(identifier)
        except Exception as e:
            console.print(f"[red]Error resolving {identifier}: {e}[/]")
            return None

    async def search_messages(self, chat, query, limit=100, since=None, until=None):
        entity = await self.get_entity(chat)
        if not entity:
            return []
        results = []
        async for msg in self.client.iter_messages(entity, search=query, limit=limit):
            if since and msg.date < since:
                continue
            if until and msg.date > until:
                continue
            results.append({
                'id': msg.id,
                'date': msg.date.isoformat() if msg.date else None,
                'sender_id': msg.sender_id,
                'sender': getattr(msg.sender, 'username', None) if msg.sender else None,
                'text': msg.text,
            })
        return results

    async def export_chat(self, chat, limit=0, export_format='json', download_media=False):
        entity = await self.get_entity(chat)
        if not entity:
            return
        messages = []
        media_dir = Path(f"media_{entity.id}")
        media_dir.mkdir(exist_ok=True)

        with Progress() as progress:
            task = progress.add_task(f"[cyan]Exporting {getattr(entity, 'title', entity.username or entity.id)}...", total=limit or None)
            async for msg in self.client.iter_messages(entity, limit=limit or None):
                msg_data = {
                    'id': msg.id,
                    'date': msg.date.isoformat() if msg.date else None,
                    'sender_id': msg.sender_id,
                    'text': msg.text,
                    'forwarded_from': str(msg.fwd_from) if getattr(msg, 'fwd_from', None) else None,
                }
                if download_media and msg.media:
                    try:
                        path = await msg.download_media(file=media_dir / f"{msg.id}")
                        msg_data['media_path'] = str(path)
                    except:
                        pass
                messages.append(msg_data)
                self.save_to_db(entity.id, msg)
                progress.update(task, advance=1)
                await asyncio.sleep(0.3)  # Rate limit

        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"{entity.id}_export_{timestamp}"
        if export_format == 'json':
            with open(f"{filename}.json", 'w', encoding='utf-8') as f:
                json.dump(messages, f, indent=2, ensure_ascii=False)
        elif export_format == 'csv':
            keys = messages[0].keys() if messages else []
            with open(f"{filename}.csv", 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=keys)
                writer.writeheader()
                writer.writerows(messages)
        console.print(f"[green]Exported {len(messages)} messages to {filename}! [/]")

    def save_to_db(self, chat_id, msg):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO messages VALUES (?, ?, ?, ?, ?, ?)",
                  (msg.id, chat_id, msg.sender_id, msg.date.isoformat() if msg.date else None, msg.text, None))
        conn.commit()
        conn.close()

    async def get_members(self, chat, limit=200):
        entity = await self.get_entity(chat)
        if not entity:
            return
        participants = await self.client.get_participants(entity, limit=limit)
        table = Table(title=f"Members of {getattr(entity, 'title', entity.username)}")
        table.add_column("ID", style="cyan")
        table.add_column("Username")
        table.add_column("Name")
        for p in participants[:limit]:
            table.add_row(str(p.id), p.username or "N/A", f"{p.first_name or ''} {p.last_name or ''}".strip())
        console.print(table)
        return participants

    async def profile_user(self, user):
        entity = await self.get_entity(user)
        if entity:
            console.print(f"[bold]Profile for {user}:[/]")
            console.print(f"ID: {entity.id}")
            console.print(f"Username: @{entity.username}")
            console.print(f"Name: {entity.first_name} {entity.last_name or ''}")
            console.print(f"Bio: {getattr(entity, 'about', 'N/A')}")

async def main():
    parser = argparse.ArgumentParser(description="High-end Telegram OSINT Tool for Intelligence Gathering")
    parser.add_argument('--api-id', type=int, help='Telegram API ID')
    parser.add_argument('--api-hash', help='Telegram API Hash')
    subparsers = parser.add_subparsers(dest='command', required=True)

    # Search
    s = subparsers.add_parser('search', help='Keyword search in chat')
    s.add_argument('chat', help='Chat username, ID or link')
    s.add_argument('query', help='Search query')
    s.add_argument('--limit', type=int, default=100)
    s.add_argument('--since', help='Start date YYYY-MM-DD')
    s.add_argument('--until', help='End date YYYY-MM-DD')

    # Export
    e = subparsers.add_parser('export', help='Export chat history')
    e.add_argument('chat', help='Chat')
    e.add_argument('--limit', type=int, default=500)
    e.add_argument('--format', choices=['json', 'csv'], default='json')
    e.add_argument('--media', action='store_true', help='Download media')

    # Members
    m = subparsers.add_parser('members', help='Enumerate group members')
    m.add_argument('chat', help='Chat')
    m.add_argument('--limit', type=int, default=200)

    # Profile
    p = subparsers.add_parser('profile', help='User profile')
    p.add_argument('user', help='Username or ID')

    args = parser.parse_args()

    api_id = args.api_id or int(os.getenv('TG_API_ID'))
    api_hash = args.api_hash or os.getenv('TG_API_HASH')
    if not api_id or not api_hash:
        console.print("[red]Provide API credentials via args or env vars TG_API_ID / TG_API_HASH[/]")
        return

    tool = TelegramOSINT(api_id, api_hash)
    await tool.start()

    if args.command == 'search':
        since = datetime.fromisoformat(args.since) if args.since else None
        until = datetime.fromisoformat(args.until) if args.until else None
        results = await tool.search_messages(args.chat, args.query, args.limit, since, until)
        for r in results:
            console.print(f"{r['date']} | @{r['sender']} ({r['sender_id']}): {r['text'][:300] if r['text'] else ''}")
    elif args.command == 'export':
        await tool.export_chat(args.chat, args.limit, args.format, args.media)
    elif args.command == 'members':
        await tool.get_members(args.chat, args.limit)
    elif args.command == 'profile':
        await tool.profile_user(args.user)

if __name__ == "__main__":
    asyncio.run(main())
