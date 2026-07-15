import asyncio
import json
import csv
import sqlite3
import argparse
import os
import sys
from datetime import datetime
from pathlib import Path
import logging
from typing import List, Optional

from telethon import TelegramClient
from telethon.errors import FloodWaitError, SessionPasswordNeededError
from rich.console import Console
from rich.progress import Progress
from rich.table import Table

console = Console()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TelegramOSINT:
    def __init__(self, api_id: int, api_hash: str, session_name: str = 'osint_session', proxy: Optional[str] = None):
        self.client = TelegramClient(session_name, api_id, api_hash, proxy=proxy)
        self.db_path = 'telegram_osint.db'
        self.init_db()

    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS messages (
            id INTEGER, chat_id INTEGER, sender_id INTEGER, date TEXT,
            text TEXT, media_path TEXT, query TEXT, PRIMARY KEY (id, chat_id))''')
        conn.commit()
        conn.close()

    async def start(self):
        try:
            await self.client.start()
            console.print("[green]✅ Client connected successfully![/]")
        except SessionPasswordNeededError:
            console.print("[red]2FA password required. Handle it in Telegram app.[/]")
            sys.exit(1)
        except Exception as e:
            console.print(f"[red]Login failed: {e}[/]")
            sys.exit(1)

    async def get_entity(self, identifier):
        try:
            return await self.client.get_entity(identifier)
        except Exception as e:
            console.print(f"[red]Could not resolve {identifier}: {e}[/]")
            return None

    async def safe_iter_messages(self, entity, **kwargs):
        """Safe iterator with flood control"""
        retries = 3
        for _ in range(retries):
            try:
                async for msg in self.client.iter_messages(entity, **kwargs):
                    yield msg
                return
            except FloodWaitError as e:
                wait = e.seconds + 3
                console.print(f"[yellow]⚠️ FloodWait: Sleeping {wait} seconds...[/]")
                await asyncio.sleep(wait)
            except Exception as e:
                console.print(f"[red]Error in iteration: {e}[/]")
                await asyncio.sleep(5)
                break

    async def search_messages(self, chat, query: str, limit: int = 100, since: Optional[datetime] = None, until: Optional[datetime] = None):
        entity = await self.get_entity(chat)
        if not entity:
            return []
        
        results = []
        with Progress() as progress:
            task = progress.add_task(f"[cyan]Searching {chat}...", total=limit or None)
            
            async for msg in self.safe_iter_messages(entity, search=query, limit=limit):
                if (since and msg.date < since) or (until and msg.date > until):
                    continue
                
                msg_data = {
                    'id': msg.id,
                    'date': msg.date.isoformat() if msg.date else None,
                    'sender_id': msg.sender_id,
                    'sender': getattr(msg.sender, 'username', None) if msg.sender else None,
                    'text': msg.text or "",
                    'chat': str(chat)
                }
                results.append(msg_data)
                self.save_to_db(entity.id, msg, query)
                progress.update(task, advance=1)
                await asyncio.sleep(0.25)  # Efficient rate limit

        return results

    async def bulk_search(self, chats: List[str], query: str, limit: int = 50, since=None, until=None, output="bulk_results.json"):
        all_results = {}
        for i, chat in enumerate(chats, 1):
            console.print(f"[bold cyan][{i}/{len(chats)}] Searching → {chat}[/]")
            results = await self.search_messages(chat, query, limit, since, until)
            if results:
                all_results[chat] = results
            await asyncio.sleep(2)  # Cooldown between chats

        with open(output, 'w', encoding='utf-8') as f:
            json.dump(all_results, f, indent=2, ensure_ascii=False)
        
        console.print(f"[green]✅ Bulk search completed! Saved {len(all_results)} chats to {output}[/]")
        return all_results

    async def export_chat(self, chat, limit=500, export_format='json', download_media=False):
        entity = await self.get_entity(chat)
        if not entity:
            return
        
        messages = []
        media_dir = Path(f"media_{entity.id}")
        media_dir.mkdir(exist_ok=True)

        with Progress() as progress:
            task = progress.add_task(f"[cyan]Exporting {getattr(entity, 'title', entity.username)}...", total=limit or None)
            
            async for msg in self.safe_iter_messages(entity, limit=limit or None):
                msg_data = {
                    'id': msg.id,
                    'date': msg.date.isoformat() if msg.date else None,
                    'sender_id': msg.sender_id,
                    'text': msg.text,
                    'forwarded_from': str(getattr(msg, 'fwd_from', None)),
                }
                if download_media and msg.media:
                    try:
                        path = await msg.download_media(file=media_dir / f"{msg.id}")
                        msg_data['media_path'] = str(path)
                    except Exception as e:
                        logger.warning(f"Media failed: {e}")
                messages.append(msg_data)
                self.save_to_db(entity.id, msg)
                progress.update(task, advance=1)
                await asyncio.sleep(0.3)

        ts = datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"{entity.id}_export_{ts}"
        
        if export_format == 'json':
            with open(f"{filename}.json", 'w', encoding='utf-8') as f:
                json.dump(messages, f, indent=2, ensure_ascii=False)
        elif export_format == 'csv':
            with open(f"{filename}.csv", 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=messages[0].keys() if messages else [])
                writer.writeheader()
                writer.writerows(messages)

        console.print(f"[green]✅ Exported {len(messages)} messages to {filename}![/]")

    def save_to_db(self, chat_id, msg, query: str = None):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO messages VALUES (?,?,?,?,?,?,?)",
                  (msg.id, chat_id, msg.sender_id,
                   msg.date.isoformat() if msg.date else None,
                   msg.text, None, query))
        conn.commit()
        conn.close()

    async def get_members(self, chat, limit=200):
        entity = await self.get_entity(chat)
        if not entity:
            return
        participants = await self.client.get_participants(entity, limit=limit)
        table = Table(title=f"Members — {getattr(entity, 'title', entity.username)}")
        table.add_column("ID", style="cyan")
        table.add_column("Username")
        table.add_column("Name")
        for p in participants[:limit]:
            table.add_row(str(p.id), p.username or "N/A", f"{p.first_name or ''} {p.last_name or ''}".strip())
        console.print(table)

    async def profile_user(self, user):
        entity = await self.get_entity(user)
        if entity:
            console.print(f"[bold]Profile — {user}[/]")
            console.print(f"ID: {entity.id}")
            console.print(f"Username: @{entity.username}")
            console.print(f"Name: {entity.first_name} {entity.last_name or ''}")
            console.print(f"Bio: {getattr(entity, 'about', 'N/A')}")

    async def load_chats_list(self, file_path: str) -> List[str]:
        path = Path(file_path)
        if not path.exists():
            console.print(f"[red]File not found: {file_path}[/]")
            return []
        if path.suffix == '.json':
            with open(path) as f:
                data = json.load(f)
                return data if isinstance(data, list) else [data]
        else:
            with open(path) as f:
                return [line.strip() for line in f if line.strip() and not line.startswith('#')]

async def main():
    parser = argparse.ArgumentParser(description="🚀 Advanced Telegram OSINT Toolkit")
    parser.add_argument('--api-id', type=int, help='Telegram API ID')
    parser.add_argument('--api-hash', help='Telegram API Hash')
    parser.add_argument('--proxy', help='Proxy (e.g. socks5://127.0.0.1:9050)')

    subparsers = parser.add_subparsers(dest='command', required=True)

    # Bulk Search
    bs = subparsers.add_parser('bulk-search', help='Bulk search across multiple chats')
    bs.add_argument('chats_file', help='channels.txt or channels.json')
    bs.add_argument('query', help='Search keyword/phrase')
    bs.add_argument('--limit', type=int, default=50)
    bs.add_argument('--since', help='Start date (YYYY-MM-DD)')
    bs.add_argument('--until', help='End date (YYYY-MM-DD)')
    bs.add_argument('--output', default='bulk_results.json')

    # Single Search
    s = subparsers.add_parser('search', help='Search in single chat')
    s.add_argument('chat', help='Chat username/ID/link')
    s.add_argument('query', help='Search query')
    s.add_argument('--limit', type=int, default=100)
    s.add_argument('--since', help='YYYY-MM-DD')
    s.add_argument('--until', help='YYYY-MM-DD')

    # Export
    e = subparsers.add_parser('export', help='Export chat history')
    e.add_argument('chat', help='Chat')
    e.add_argument('--limit', type=int, default=500)
    e.add_argument('--format', choices=['json', 'csv'], default='json')
    e.add_argument('--media', action='store_true')

    # Members
    m = subparsers.add_parser('members', help='Get group members')
    m.add_argument('chat')
    m.add_argument('--limit', type=int, default=200)

    # Profile
    p = subparsers.add_parser('profile', help='Get user profile')
    p.add_argument('user')

    args = parser.parse_args()

    api_id = args.api_id or int(os.getenv('TG_API_ID', 0))
    api_hash = args.api_hash or os.getenv('TG_API_HASH')

    if not api_id or not api_hash:
        console.print("[red]❌ Missing API credentials! Use flags or .env file.[/]")
        return

    tool = TelegramOSINT(api_id, api_hash, proxy=args.proxy)
    await tool.start()

    if args.command == 'bulk-search':
        chats = await tool.load_chats_list(args.chats_file)
        since = datetime.fromisoformat(args.since) if args.since else None
        until = datetime.fromisoformat(args.until) if args.until else None
        await tool.bulk_search(chats, args.query, args.limit, since, until, args.output)

    elif args.command == 'search':
        since = datetime.fromisoformat(args.since) if args.since else None
        until = datetime.fromisoformat(args.until) if args.until else None
        results = await tool.search_messages(args.chat, args.query, args.limit, since, until)
        for r in results:
            console.print(f"{r['date']} | @{r['sender']} ({r['sender_id']}): {r['text'][:250]}")

    elif args.command == 'export':
        await tool.export_chat(args.chat, args.limit, args.format, args.media)

    elif args.command == 'members':
        await tool.get_members(args.chat, args.limit)

    elif args.command == 'profile':
        await tool.profile_user(args.user)

if __name__ == "__main__":
    asyncio.run(main())
