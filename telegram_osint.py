import asyncio
import json
import csv
import sqlite3
import argparse
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
import logging
from typing import List, Optional

from telethon import TelegramClient
from telethon.errors import FloodWaitError, SessionPasswordNeededError
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TimeElapsedColumn
from rich.table import Table
from rich import print as rprint

console = Console()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TelegramOSINT:
    def __init__(self, api_id: int, api_hash: str, session_name: str = 'osint_session', proxy: Optional[dict] = None):
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
            rprint("[green]✅ Client connected successfully![/]")
        except SessionPasswordNeededError:
            rprint("[red]2FA password required. Please handle it manually.[/]")
            sys.exit(1)

    async def get_entity(self, identifier):
        try:
            return await self.client.get_entity(identifier)
        except Exception as e:
            rprint(f"[red]Failed to resolve {identifier}: {e}[/]")
            return None

    async def safe_iter_messages(self, entity, **kwargs):
        """Wrapper with flood wait handling"""
        while True:
            try:
                async for msg in self.client.iter_messages(entity, **kwargs):
                    yield msg
                break
            except FloodWaitError as e:
                rprint(f"[yellow]Flood wait: Sleeping for {e.seconds} seconds...[/]")
                await asyncio.sleep(e.seconds + 2)
            except Exception as e:
                rprint(f"[red]Error iterating messages: {e}[/]")
                break

    async def search_messages(self, chat, query: str, limit: int = 100, since: Optional[datetime] = None, until: Optional[datetime] = None, save_to_db: bool = True):
        entity = await self.get_entity(chat)
        if not entity:
            return []
        
        results = []
        with Progress() as progress:
            task = progress.add_task(f"[cyan]Searching in {chat}...", total=limit or None)
            
            async for msg in self.safe_iter_messages(entity, search=query, limit=limit):
                if since and msg.date < since:
                    continue
                if until and msg.date > until:
                    continue
                
                msg_data = {
                    'id': msg.id,
                    'date': msg.date.isoformat() if msg.date else None,
                    'sender_id': msg.sender_id,
                    'sender': getattr(msg.sender, 'username', None) if msg.sender else None,
                    'text': msg.text,
                    'chat': str(chat)
                }
                results.append(msg_data)
                
                if save_to_db:
                    self.save_to_db(entity.id, msg, query)
                
                progress.update(task, advance=1)
                await asyncio.sleep(0.2)  # Gentle rate limit

        return results

    async def bulk_search(self, chats: List[str], query: str, limit: int = 50, since=None, until=None, output="bulk_results.json"):
        all_results = {}
        for chat in chats:
            rprint(f"[bold cyan]→ Searching in: {chat}[/]")
            results = await self.search_messages(chat, query, limit, since, until)
            if results:
                all_results[chat] = results
            await asyncio.sleep(2)  # Delay between chats

        with open(output, 'w', encoding='utf-8') as f:
            json.dump(all_results, f, indent=2, ensure_ascii=False)
        
        rprint(f"[green]✅ Bulk search completed! Results saved to {output}[/]")
        return all_results

    async def export_chat(self, chat, limit=0, export_format='json', download_media=False):
        # (Your original export logic improved with safe_iter_messages)
        entity = await self.get_entity(chat)
        if not entity:
            return
        messages = []
        media_dir = Path(f"media_{entity.id}")
        media_dir.mkdir(exist_ok=True)

        with Progress() as progress:
            task = progress.add_task(f"[cyan]Exporting {getattr(entity, 'title', entity.username or entity.id)}...", total=limit or None)
            async for msg in self.safe_iter_messages(entity, limit=limit or None):
                # ... same as your original
                msg_data = { ... }  # Keep your original msg_data logic
                if download_media and msg.media:
                    try:
                        path = await msg.download_media(file=media_dir / f"{msg.id}")
                        msg_data['media_path'] = str(path)
                    except Exception as e:
                        logger.warning(f"Media download failed: {e}")
                messages.append(msg_data)
                self.save_to_db(entity.id, msg)
                progress.update(task, advance=1)
                await asyncio.sleep(0.3)

        # Save logic remains same
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"{entity.id}_export_{timestamp}"
        # ... save json/csv
        rprint(f"[green]✅ Exported {len(messages)} messages![/]")

    def save_to_db(self, chat_id, msg, query: str = None):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO messages VALUES (?,?,?,?,?,?,?)",
                  (msg.id, chat_id, msg.sender_id, msg.date.isoformat() if msg.date else None,
                   msg.text, None, query))
        conn.commit()
        conn.close()

    # Keep your get_members and profile_user methods (they are good)

async def main():
    parser = argparse.ArgumentParser(description="Advanced Telegram OSINT Toolkit")
    parser.add_argument('--api-id', type=int)
    parser.add_argument('--api-hash')
    parser.add_argument('--proxy', help='Proxy URL e.g. socks5://127.0.0.1:9050')

    subparsers = parser.add_subparsers(dest='command', required=True)

    # Bulk Search (New & Powerful)
    bs = subparsers.add_parser('bulk-search', help='Bulk search across multiple chats')
    bs.add_argument('chats_file', help='channels.txt or channels.json')
    bs.add_argument('query')
    bs.add_argument('--limit', type=int, default=50)
    bs.add_argument('--since')
    bs.add_argument('--until')
    bs.add_argument('--output', default='bulk_results.json')

    # ... keep other parsers (search, export, members, profile)

    args = parser.parse_args()

    # Proxy support
    proxy = None
    if args.proxy:
        if args.proxy.startswith('socks5'):
            proxy = args.proxy  # Telethon supports string proxy in newer versions

    api_id = args.api_id or int(os.getenv('TG_API_ID', 0))
    api_hash = args.api_hash or os.getenv('TG_API_HASH')

    if not api_id or not api_hash:
        rprint("[red]API credentials missing! Use --api-id / --api-hash or set environment variables.[/]")
        return

    tool = TelegramOSINT(api_id, api_hash, proxy=proxy)
    await tool.start()

    if args.command == 'bulk-search':
        # Load chats and run bulk search
        # ... implementation
        pass
    # ... other commands

if __name__ == "__main__":
    asyncio.run(main())
