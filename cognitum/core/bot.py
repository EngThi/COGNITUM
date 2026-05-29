import os
import json
import html
import re
import subprocess
from pathlib import Path
from datetime import datetime
from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from google import genai
from google.genai import types
from google.genai.errors import ClientError

from cognitum.config import settings
from cognitum.core.state import (
    save_event,
    get_unprocessed_events,
    mark_event_status,
    get_active_session,
    set_active_session,
    save_kimi_session,
    get_user_sessions,
    get_agent_mode,
    toggle_agent_mode,
    get_proxy_mode,
    toggle_proxy_mode,
    record_kimi_use,
    ensure_kimiproxy_running
)
from cognitum.core.log import get_logger
from cognitum.core.tools.vault_tool import search_vault
from cognitum.core.tools.status_tool import get_status
from cognitum.core.tools.composio_tool import call_composio_action
from cognitum.core.tools.mcp_tool import call_mcp_tool
from cognitum.core.tools.http_tool import call_http_api

logger = get_logger("telegram_bot")

TMP_DIR = Path(settings.base_dir) / "tmp"
TMP_DIR.mkdir(parents=True, exist_ok=True)

def markdown_to_html(text: str) -> str:
    text = text.replace('\r\n', '\n')

    # Extract code blocks
    code_blocks = []
    def save_code_block(match):
        lang = match.group(1) or ""
        content = match.group(2)
        code_blocks.append((lang, content))
        return f"<!--CODEBLOCK_{len(code_blocks)-1}-->"

    text = re.sub(r'```(\w*)\n?(.*?)```', save_code_block, text, flags=re.DOTALL)

    # Extract inline code
    inline_codes = []
    def save_inline_code(match):
        content = match.group(1)
        inline_codes.append(content)
        return f"<!--INLINECODE_{len(inline_codes)-1}-->"
    text = re.sub(r'`([^`\n]+)`', save_inline_code, text)

    # Escape HTML tags
    text = html.escape(text, quote=False)

    # Convert formatting
    text = re.sub(r'\*\*(.*?)\*\*|__(.*?)__', lambda m: f"<b>{m.group(1) or m.group(2)}</b>", text)
    text = re.sub(r'\*(.*?)\*|_(.*?)_', lambda m: f"<i>{m.group(1) or m.group(2)}</i>", text)
    text = re.sub(r'~~(.*?)~~', r'<s>\1</s>', text)

    # Blockquotes
    lines = text.split('\n')
    in_quote = False
    quote_content = []
    new_lines = []
    for line in lines:
        if line.startswith('&gt;'):
            in_quote = True
            content = line[4:]
            if content.startswith(' '):
                content = content[1:]
            quote_content.append(content)
        else:
            if in_quote:
                q_text = "\n".join(quote_content)
                new_lines.append(f"<blockquote expandable>{q_text}</blockquote>")
                in_quote = False
                quote_content = []
            new_lines.append(line)
    if in_quote:
        q_text = "\n".join(quote_content)
        new_lines.append(f"<blockquote expandable>{q_text}</blockquote>")
    text = "\n".join(new_lines)

    text = re.sub(r'^(#{1,6})\s+(.*?)$', lambda m: f"<b>{m.group(2)}</b>", text, flags=re.MULTILINE)
    text = re.sub(r'\[(.*?)\]\((.*?)\)', r'<a href="\2">\1</a>', text)

    # Restore inline code blocks
    for i, content in enumerate(inline_codes):
        escaped_code = html.escape(content, quote=False)
        text = text.replace(f"&lt;!--INLINECODE_{i}--&gt;", f"<code>{escaped_code}</code>")

    # Restore fenced code blocks
    for i, (lang, content) in enumerate(code_blocks):
        escaped_code = html.escape(content, quote=False)
        if lang:
            code_html = f'<pre><code class="language-{lang}">{escaped_code}</code></pre>'
        else:
            code_html = f'<pre>{escaped_code}</pre>'
        text = text.replace(f"&lt;!--CODEBLOCK_{i}--&gt;", code_html)

    return text

def get_action_description(func_name, func_args):
    if func_name == "run_command":
        cmd = func_args.get("command", "")
        short_cmd = cmd.split('\n')[0]
        if len(short_cmd) > 60:
            short_cmd = short_cmd[:60] + "..."
        return f"Comando <code>{html.escape(short_cmd)}</code>"
    elif func_name == "read_file":
        path = func_args.get("path", "")
        return f"Leitura de <code>{html.escape(path)}</code>"
    elif func_name == "write_file":
        path = func_args.get("path", "")
        return f"Gravação de <code>{html.escape(path)}</code>"
    elif func_name == "list_directory":
        path = func_args.get("path", "")
        return f"Listagem do diretório <code>{html.escape(path)}</code>"
    elif func_name == "search_vault":
        query = func_args.get("query", "")
        return f"Busca no vault por <code>{html.escape(query)}</code>"
    elif func_name == "get_status":
        return "Verificação de status do sistema"
    elif func_name == "call_composio_action":
        action = func_args.get("action_name", "")
        return f"Ação Composio <code>{html.escape(action)}</code>"
    elif func_name == "call_mcp_tool":
        tool = func_args.get("tool_name", "")
        server = func_args.get("server_command", "")
        return f"Ferramenta MCP <code>{html.escape(tool)}</code> no servidor <code>{html.escape(server)}</code>"
    elif func_name == "call_http_api":
        method = func_args.get("method", "GET").upper()
        url = func_args.get("url", "")
        return f"Requisição HTTP <code>{method} {html.escape(url)}</code>"
    return f"Execução de {func_name}"

_genai_client = None

def get_genai_client():
    global _genai_client
    if _genai_client is None:
        api_key = os.getenv("GEMINI_API_KEY") or settings.gemini_api_key
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in environment or config.")
        _genai_client = genai.Client(api_key=api_key)
    return _genai_client

async def post_init(application) -> None:
    commands = [
        BotCommand("start", "Inicia o bot e exibe ajuda"),
        BotCommand("chat", "Gerencia os contextos de chat do Kimi"),
        BotCommand("agent", "Ativa/desativa o modo agente do bot"),
        BotCommand("proxy", "Ativa/desativa o uso do KimiProxy (IA local)"),
        BotCommand("note", "Captura uma nota/ideia rapida"),
        BotCommand("flash", "Captura um flashcard de fatos"),
        BotCommand("erro", "Registra um erro ou licao aprendida"),
        BotCommand("task", "Cria um item a fazer (to-do)"),
        BotCommand("capture", "Captura dados livres/nao estruturados"),
        BotCommand("status", "Mostra o status de saude do Cognitum OS"),
        BotCommand("summary", "Gera e envia o sumario diario"),
        BotCommand("review", "Inicia sessao de revisao agendada"),
    ]
    await application.bot.set_my_commands(commands)
    logger.info("Telegram command menu initialized successfully.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🧠 *Cognitum Personal OS Active*\n\n"
        "*Commands:*\n"
        "• `/chat` - Gerenciar chats e memória no Kimi\n"
        "• `/agent` - Alternar entre Modo Agente e Modo Chat\n"
        "• `/proxy` - Alternar entre KimiProxy (Kimi) e Gemini direto\n"
        "• `/note <text>` - Capture a raw note/idea\n"
        "• `/flash <text>` - Capture a facts flashcard\n"
        "• `/erro <text>` - Log a mistake/lesson learned\n"
        "• `/task <text>` - Create a quick to-do\n"
        "• `/capture <text>` - Ingest any unstructured data\n"
        "• `/status` - Check cognitive OS status\n"
        "• `/summary` - Request a daily summary brief\n"
        "• `/review` - Start spaced-repetition review session\n\n"
        "💡 *Tip:* Send voice notes for transcription, or photos for image OCR notes!",
        parse_mode="Markdown"
    )

async def handle_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args) if context.args else ""
    if not text:
        await update.message.reply_text("Usage: /note <content>")
        return
    event_id = await save_event("telegram.message", {"text": f"[note] {text}", "source": "telegram", "chat_id": update.effective_chat.id})
    await update.message.reply_text(f"✅ Ingested Note (Event ID: {event_id})")

async def handle_flash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args) if context.args else ""
    if not text:
        await update.message.reply_text("Usage: /flash <question/answer or fact>")
        return
    event_id = await save_event("telegram.message", {"text": f"[flashcard] {text}", "source": "telegram", "chat_id": update.effective_chat.id})
    await update.message.reply_text(f"✅ Ingested Flashcard Event (Event ID: {event_id})")

async def handle_erro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args) if context.args else ""
    if not text:
        await update.message.reply_text("Usage: /erro <mistake details>")
        return
    event_id = await save_event("telegram.message", {"text": f"[mistake] {text}", "source": "telegram", "chat_id": update.effective_chat.id})
    await update.message.reply_text(f"✅ Ingested Mistake Event (Event ID: {event_id})")

async def handle_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args) if context.args else ""
    if not text:
        await update.message.reply_text("Usage: /task <todo details>")
        return
    event_id = await save_event("telegram.message", {"text": f"[task] {text}", "source": "telegram", "chat_id": update.effective_chat.id})
    await update.message.reply_text(f"✅ Ingested Task Event (Event ID: {event_id})")

async def handle_capture(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args) if context.args else ""
    if not text:
        await update.message.reply_text("Usage: /capture <raw text>")
        return
    event_id = await save_event("raw.input", {"text": text, "source": "telegram", "chat_id": update.effective_chat.id})
    await update.message.reply_text(f"✅ Ingested Raw Capture (Event ID: {event_id})")

async def handle_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_chat_id = update.effective_chat.id
    agent_active = await get_agent_mode(telegram_chat_id)
    proxy_active = await get_proxy_mode(telegram_chat_id)
    
    agent_status = "🕵️‍♂️ ATIVO (Modo Agente)" if agent_active else "💬 INATIVO (Modo Chat apenas)"
    proxy_status = "🚀 ATIVO (KimiProxy)" if proxy_active else "✨ DESATIVADO (Gemini Direto)"
    
    try:
        script_path = Path(settings.base_dir) / "scripts" / "status_check.py"
        if not script_path.exists():
            script_path = Path("/opt/automation/scripts/status_check.py")
            
        res = subprocess.run([str(script_path)], capture_output=True, text=True)
        dashboard = res.stdout.strip()
        
        status_msg = (
            f"⚙️ *CONFIGURAÇÕES DO CHAT:*\n"
            f"• Modo Agente: {agent_status}\n"
            f"• Provedor IA: {proxy_status}\n\n"
            f"```\n{dashboard}\n```"
        )
        await update.message.reply_text(status_msg, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Failed to get system status: {e}")
        await update.message.reply_text(f"❌ Failed to get status dashboard: {e}")

async def handle_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Generating today's brief summary...")
    await save_event("action.daily_brief", {"source": "telegram", "chat_id": update.effective_chat.id})

async def handle_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Checking spaced repetition scheduler...")
    await save_event("action.start_review", {"source": "telegram", "chat_id": update.effective_chat.id})

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    voice = update.message.voice
    await update.message.reply_text("🎤 Voice note received. Downloading and transcribing...")

    try:
        file = await context.bot.get_file(voice.file_id)
        local_path = TMP_DIR / f"{voice.file_id}.ogg"
        await file.download_to_drive(local_path)

        client = get_genai_client()
        logger.info(f"Uploading voice note {local_path} to Gemini...")
        file_ref = client.files.upload(file=local_path)

        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=[file_ref, "Transcreva este audio em portugues de forma extremamente precisa. Retorne apenas o texto transcrito."]
        )
        transcription = response.text.strip()
        local_path.unlink(missing_ok=True)

        event_id = await save_event(
            "telegram.message",
            {"text": transcription, "source": "telegram_voice", "chat_id": update.effective_chat.id}
        )

        await update.message.reply_text(
            f"📝 *Transcricao:*\n\"{transcription}\"\n\n"
            f"✅ Ingerido como evento ID {event_id}",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error in voice pipeline: {e}")
        await update.message.reply_text(f"❌ Falha no processamento de voz: {e}")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    await update.message.reply_text("📸 Imagem recebida. Processando OCR cognitivo...")

    try:
        file = await context.bot.get_file(photo.file_id)
        local_path = TMP_DIR / f"{photo.file_id}.jpg"
        await file.download_to_drive(local_path)

        client = get_genai_client()
        file_ref = client.files.upload(file=local_path)

        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=[file_ref, "Extraia todas as informacoes uteis desta imagem e formate-as como uma nota em Markdown organizada. Se for um quadro, anotacao ou slide, transcreva fielmente."]
        )
        ocr_result = response.text.strip()
        local_path.unlink(missing_ok=True)

        event_id = await save_event(
            "telegram.message",
            {"text": f"[ocr] {ocr_result}", "source": "telegram_photo", "chat_id": update.effective_chat.id}
        )

        await update.message.reply_text(
            f"📝 *OCR Extraido:*\n{ocr_result}\n\n"
            f"✅ Nota ingerida sob ID {event_id}",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error in image pipeline: {e}")
        await update.message.reply_text(f"❌ Falha no processamento da imagem: {e}")

async def handle_agent_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_chat_id = update.effective_chat.id
    new_mode = await toggle_agent_mode(telegram_chat_id)
    if new_mode:
        await update.message.reply_text(
            "🕵️‍♂️ *Modo Agente Ativado!*\n\n"
            "Agora eu posso executar comandos no terminal, gerenciar arquivos do vault "
            "e organizar o ecossistema Cognitum diretamente pelo chat.",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "💬 *Modo Conversa Ativado (Chat apenas)*\n\n"
            "Modo Agente desativado. Agora responderei apenas como um chat normal.",
            parse_mode="Markdown"
        )

async def handle_proxy_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_chat_id = update.effective_chat.id
    new_mode = await toggle_proxy_mode(telegram_chat_id)
    if new_mode:
        await record_kimi_use()
        await ensure_kimiproxy_running()
        await update.message.reply_text(
            "🚀 *KimiProxy Ativado!*\n\n"
            "Agora tentarei responder usando o Kimi (via KimiProxy) por padrão.",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "✨ *KimiProxy Desativado!*\n\n"
            "As respostas serão geradas diretamente pelo Gemini (sem passar pelo KimiProxy).",
            parse_mode="Markdown"
        )

def tool_run_command(command: str) -> str:
    try:
        res = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=settings.base_dir
        )
        output = f"Exit Code: {res.returncode}\n"
        if res.stdout:
            output += f"STDOUT:\n{res.stdout}\n"
        if res.stderr:
            output += f"STDERR:\n{res.stderr}\n"
        return output.strip() or "Command completed with no output."
    except Exception as e:
        return f"Exception executing command: {e}"

def tool_read_file(path: str) -> str:
    try:
        p = Path(path)
        if not p.is_file():
            return f"Error: {path} is not a file or does not exist."
        content = p.read_text(encoding="utf-8")
        if len(content) > 100000:
            return content[:100000] + "\n... [TRUNCATED due to size] ..."
        return content
    except Exception as e:
        return f"Error reading file: {e}"

def tool_write_file(path: str, content: str) -> str:
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"Successfully wrote {len(content)} characters to {path}"
    except Exception as e:
        return f"Error writing file: {e}"

def tool_list_directory(path: str) -> str:
    try:
        p = Path(path)
        if not p.is_dir():
            return f"Error: {path} is not a directory or does not exist."
        items = []
        for item in p.iterdir():
            item_type = "DIR" if item.is_dir() else "FILE"
            size = f" ({item.stat().st_size} bytes)" if item.is_file() else ""
            items.append(f"- [{item_type}] {item.name}{size}")
        return "\n".join(items) or "Directory is empty."
    except Exception as e:
        return f"Error listing directory: {e}"

async def handle_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    if not user_text:
        return

    telegram_chat_id = update.effective_chat.id
    await save_event("raw.input", {"text": user_text, "source": "telegram_chat", "chat_id": telegram_chat_id})
    await context.bot.send_chat_action(chat_id=telegram_chat_id, action="typing")

    session = await get_active_session(telegram_chat_id)
    agent_active = await get_agent_mode(telegram_chat_id)
    proxy_active = await get_proxy_mode(telegram_chat_id)

    system_prompt = ""
    if agent_active:
        try:
            memory_dir = Path(settings.memory_dir)
            user_md = (memory_dir / "USER.md").read_text(encoding="utf-8") if (memory_dir / "USER.md").exists() else ""
            system_md = (memory_dir / "SYSTEM.md").read_text(encoding="utf-8") if (memory_dir / "SYSTEM.md").exists() else ""
            rules_md = (memory_dir / "RULES.md").read_text(encoding="utf-8") if (memory_dir / "RULES.md").exists() else ""
            current_md = (memory_dir / "CURRENT.md").read_text(encoding="utf-8") if (memory_dir / "CURRENT.md").exists() else ""
            tools_md = (memory_dir / "TOOLS.md").read_text(encoding="utf-8") if (memory_dir / "TOOLS.md").exists() else ""
            
            system_prompt = (
                f"# ONBOARDING CONTEXT\n\n"
                f"You are Thiago's CLI & automation agent for the COGNITUM OS.\n"
                f"You have direct system access to the VPS to run commands, edit files, and organize the workspace.\n\n"
                f"{user_md}\n\n"
                f"{system_md}\n\n"
                f"{rules_md}\n\n"
                f"{current_md}\n\n"
            )
            if tools_md:
                system_prompt += f"{tools_md}\n\n"
            system_prompt += "Be concise, efficient, and write Portuguese explanations by default."
        except Exception as e:
            logger.error(f"Failed to load operational memory: {e}")
            system_prompt = "You are Thiago's CLI & automation agent for COGNITUM. Answer in Portuguese."

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_text})

    tools = []
    if agent_active:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "run_command",
                    "description": "Execute a shell command (bash) on the host system. Use this to check system configuration, manage git, run scripts, etc.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {"type": "string", "description": "The exact shell command to execute."}
                        },
                        "required": ["command"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read the contents of a text file from the filesystem.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "The absolute path to the file."}
                        },
                        "required": ["path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "write_file",
                    "description": "Write or overwrite content to a file on the filesystem.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "The absolute path to write the file."},
                            "content": {"type": "string", "description": "The full text content to write."}
                        },
                        "required": ["path", "content"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "list_directory",
                    "description": "List files and directories in a given path.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "The directory path to list."}
                        },
                        "required": ["path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_vault",
                    "description": "Search for a query string across markdown files in Obsidian vault.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "The search term to look for."}
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_status",
                    "description": "Get the health, queue sizes, and event logs.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "call_composio_action",
                    "description": "Execute a Composio integration tool.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "action_name": {"type": "string", "description": "The action name."},
                            "parameters": {"type": "object", "description": "Parameters for the action."}
                        },
                        "required": ["action_name", "parameters"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "call_mcp_tool",
                    "description": "Run a tool on a Model Context Protocol (MCP) server.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "server_command": {"type": "string", "description": "MCP server command."},
                            "tool_name": {"type": "string", "description": "Tool name."},
                            "arguments": {"type": "object", "description": "Parameters."}
                        },
                        "required": ["server_command", "tool_name", "arguments"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "call_http_api",
                    "description": "Make an HTTP request.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "method": {"type": "string", "description": "HTTP method."},
                            "url": {"type": "string", "description": "URL."},
                            "headers": {"type": "object", "description": "Headers.", "default": {}},
                            "json_data": {"type": "object", "description": "JSON payload.", "default": {}}
                        },
                        "required": ["method", "url"]
                    }
                }
            }
        ]

    max_turns = 8
    import urllib.request
    import json
    import os
    
    kimi_url_base = os.environ.get("KIMI_PROXY_URL", settings.kimi_proxy_url).rstrip("/")
    url = f"{kimi_url_base}/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer your_secret_api_key"
    }

    current_kimi_chat_id = session["kimi_chat_id"] if session else None
    current_kimi_parent_id = session["last_parent_id"] if session else None

    for turn in range(max_turns):
        data = {
            "model": "k2d6",
            "messages": messages
        }
        if current_kimi_chat_id:
            data["kimi_chat_id"] = current_kimi_chat_id
            data["kimi_parent_id"] = current_kimi_parent_id
        if tools:
            data["tools"] = tools

        try:
            if not proxy_active:
                raise Exception("KimiProxy desativado pelo usuario.")
            
            await record_kimi_use()
            await ensure_kimiproxy_running()
            
            req = urllib.request.Request(url, data=json.dumps(data).encode(), headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=120) as response:
                res_data = json.loads(response.read().decode())
                
                new_kimi_chat_id = res_data.get("kimi_chat_id")
                new_kimi_parent_id = res_data.get("kimi_parent_id")
                if new_kimi_chat_id and new_kimi_parent_id:
                    current_kimi_chat_id = new_kimi_chat_id
                    current_kimi_parent_id = new_kimi_parent_id
                    title = session["title"] if session else (user_text[:30] + ("..." if len(user_text) > 30 else ""))
                    await save_kimi_session(new_kimi_chat_id, telegram_chat_id, title, new_kimi_parent_id)
                    if not session or not session.get("kimi_chat_id"):
                        await set_active_session(telegram_chat_id, new_kimi_chat_id)
                        session = {"kimi_chat_id": new_kimi_chat_id, "last_parent_id": new_kimi_parent_id, "title": title}

                choice = res_data["choices"][0]
                message_out = choice["message"]
                assistant_reply = message_out.get("content") or ""
                tool_calls = message_out.get("tool_calls") or []

                messages.append(message_out)

                if assistant_reply:
                    try:
                        html_reply = markdown_to_html(assistant_reply)
                        await update.message.reply_text(html_reply, parse_mode="HTML")
                    except Exception:
                        await update.message.reply_text(assistant_reply)

                if not tool_calls:
                    break

                for tc in tool_calls:
                    tc_id = tc["id"]
                    func = tc["function"]
                    func_name = func["name"]
                    func_args = json.loads(func["arguments"]) if isinstance(func["arguments"], str) else func["arguments"]
                    
                    logger.info(f"Agent executing tool {func_name} with args {func_args}")
                    
                    action_desc = get_action_description(func_name, func_args)
                    status_msg = await update.message.reply_text(
                        f"⚙️ <b>Executando:</b> {action_desc}...",
                        parse_mode="HTML"
                    )

                    if func_name == "run_command":
                        cmd_output = tool_run_command(func_args.get("command", ""))
                    elif func_name == "read_file":
                        cmd_output = tool_read_file(func_args.get("path", ""))
                    elif func_name == "write_file":
                        cmd_output = tool_write_file(func_args.get("path", ""), func_args.get("content", ""))
                    elif func_name == "list_directory":
                        cmd_output = tool_list_directory(func_args.get("path", ""))
                    elif func_name == "search_vault":
                        cmd_output = search_vault(func_args.get("query", ""))
                        cmd_output = "\n".join(cmd_output) if isinstance(cmd_output, list) else str(cmd_output)
                    elif func_name == "get_status":
                        cmd_output = get_status()
                    elif func_name == "call_composio_action":
                        cmd_output = call_composio_action(
                            func_args.get("action_name", ""),
                            func_args.get("parameters", {})
                        )
                    elif func_name == "call_mcp_tool":
                        cmd_output = call_mcp_tool(
                            func_args.get("server_command", ""),
                            func_args.get("tool_name", ""),
                            func_args.get("arguments", {})
                        )
                    elif func_name == "call_http_api":
                        cmd_output = call_http_api(
                            func_args.get("method", "GET"),
                            func_args.get("url", ""),
                            func_args.get("headers"),
                            func_args.get("json_data")
                        )
                    else:
                        cmd_output = f"Error: Tool {func_name} not found."

                    trunc_output = cmd_output
                    if len(trunc_output) > 2500:
                        trunc_output = trunc_output[:2500] + "\n... [TRUNCATED] ..."
                    
                    escaped_output = html.escape(trunc_output)
                    try:
                        await status_msg.edit_text(
                            f"⚙️ <b>Executado:</b> {action_desc}\n\n"
                            f"<tg-spoiler><pre><code>{escaped_output}</code></pre></tg-spoiler>",
                            parse_mode="HTML"
                        )
                    except Exception:
                        try:
                            await status_msg.edit_text(
                                f"⚙️ Executado: {func_name}\n\n"
                                f"Resultado:\n{trunc_output[:2000]}",
                                parse_mode="Markdown"
                            )
                        except Exception:
                            pass

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc_id,
                        "name": func_name,
                        "content": cmd_output
                    })
                
                await context.bot.send_chat_action(chat_id=telegram_chat_id, action="typing")

        except Exception as e:
            logger.error(f"Error calling KimiProxy: {e}. Falling back to Gemini Direct...")
            try:
                client = get_genai_client()
                response = client.models.generate_content(
                    model=settings.gemini_model,
                    contents=user_text
                )
                gemini_reply = response.text.strip()
                try:
                    await update.message.reply_text(markdown_to_html(gemini_reply), parse_mode="HTML")
                except Exception:
                    await update.message.reply_text(gemini_reply)
            except Exception as gemini_err:
                logger.error(f"Fallback to Gemini also failed: {gemini_err}")
                await update.message.reply_text("❌ Desculpe, nao consegui obter resposta no momento.")
            break

async def handle_chat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_chat_id = update.effective_chat.id
    sessions = await get_user_sessions(telegram_chat_id)
    active = await get_active_session(telegram_chat_id)
    active_chat_id = active["kimi_chat_id"] if active else None
    
    keyboard = []
    new_chat_label = "🆕 Iniciar Novo Chat"
    if active_chat_id is None:
        new_chat_label += " (Ativo)"
    keyboard.append([InlineKeyboardButton(new_chat_label, callback_data="chat_action:new")])
    
    for s in sessions[:10]:
        title = s["title"] or "Sem titulo"
        if s["kimi_chat_id"] == active_chat_id:
            title = f"💬 {title} (Ativo)"
        else:
            title = f"📁 {title}"
        keyboard.append([InlineKeyboardButton(title, callback_data=f"chat_select:{s['kimi_chat_id']}")])
        
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "💬 *Gerenciador de Chats Kimi*\n\n"
        "Selecione um chat para retomar a conversa ou inicie um novo contexto:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def handle_chat_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    telegram_chat_id = update.effective_chat.id
    
    if data == "chat_action:new":
        await set_active_session(telegram_chat_id, None)
        await query.edit_message_text(
            "🆕 *Novo chat preparado!*\n\n"
            "Sua proxima mensagem de texto iniciara uma nova conversa com memoria independente no Kimi.",
            parse_mode="Markdown"
        )
    elif data.startswith("chat_select:"):
        kimi_chat_id = data.split(":", 1)[1]
        await set_active_session(telegram_chat_id, kimi_chat_id)
        
        sessions = await get_user_sessions(telegram_chat_id)
        selected_title = "Chat Selecionado"
        for s in sessions:
            if s["kimi_chat_id"] == kimi_chat_id:
                selected_title = s["title"] or "Sem titulo"
                break
                
        await query.edit_message_text(
            f"✅ *Chat Ativado!*\n\n"
            f"Contexto atual: *{selected_title}*\n"
            f"As próximas mensagens continuarão essa conversa.",
            parse_mode="Markdown"
        )

def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN") or settings.telegram_bot_token
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN not found in environment. Telegram Bot script disabled.")
        return

    app = ApplicationBuilder().token(token).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("chat", handle_chat_command))
    app.add_handler(CommandHandler("agent", handle_agent_toggle))
    app.add_handler(CommandHandler("proxy", handle_proxy_toggle))
    app.add_handler(CommandHandler("note", handle_note))
    app.add_handler(CommandHandler("flash", handle_flash))
    app.add_handler(CommandHandler("erro", handle_erro))
    app.add_handler(CommandHandler("task", handle_task))
    app.add_handler(CommandHandler("capture", handle_capture))
    app.add_handler(CommandHandler("status", handle_status))
    app.add_handler(CommandHandler("summary", handle_summary))
    app.add_handler(CommandHandler("review", handle_review))

    app.add_handler(CallbackQueryHandler(handle_chat_callback))

    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_chat))

    logger.info("Starting Telegram Bot polling...")
    app.run_polling()

if __name__ == "__main__":
    main()
