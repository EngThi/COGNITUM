# agent.py — OpenAI Agents SDK + Composio with Dynamic LLM Support (Kimi / Gemini / OpenAI)
import os
import asyncio
from dotenv import load_dotenv

# Load environment configuration
load_dotenv()

# Import OpenAI client and agents SDK
from openai import AsyncOpenAI
from agents import Agent, Runner, OpenAIChatCompletionsModel, set_tracing_disabled
from composio import Composio
from composio_openai_agents import OpenAIAgentsProvider

# Disable tracing by default to keep logs clean unless configured otherwise
set_tracing_disabled(disabled=True)

def configure_mimo_cli():
    """
    Renders an interactive CLI menu to choose model, enable/disable thinking, and web search.
    """
    import os
    model = "mimo-v2.5-pro"
    thinking = True
    search = True
    use_composio = True
    
    models_list = ["mimo-v2.5-pro", "mimo-v2.5", "mimo-v2-pro", "mimo-v2-omni"]
    
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print("=========================================")
        print("      COGNITUM AGENT CONFIGURATION       ")
        print("=========================================")
        print(f"1. Model: {model}")
        print(f"2. Thinking: {'Enabled' if thinking else 'Disabled'}")
        print(f"3. Web Search: {'Enabled' if search else 'Disabled'}")
        print(f"4. Composio Tools: {'Enabled' if use_composio else 'Disabled'}")
        print("-----------------------------------------")
        print("Select option to toggle/change:")
        print("  [1] Change Model")
        print("  [2] Toggle Thinking")
        print("  [3] Toggle Web Search")
        print("  [4] Toggle Composio Tools")
        print("  [S] Start Chat Session")
        print("  [Q] Quit")
        print("-----------------------------------------")
        
        choice = input("Option: ").strip().lower()
        if choice == '1':
            print("\nAvailable Models:")
            for idx, m in enumerate(models_list):
                print(f"  [{idx + 1}] {m}")
            print(f"  [{len(models_list) + 1}] Custom Model...")
            m_choice = input("Select model: ").strip()
            if m_choice.isdigit():
                m_idx = int(m_choice) - 1
                if 0 <= m_idx < len(models_list):
                    model = models_list[m_idx]
                elif m_idx == len(models_list):
                    custom_m = input("Enter custom model name: ").strip()
                    if custom_m:
                        model = custom_m
        elif choice == '2':
            thinking = not thinking
        elif choice == '3':
            search = not search
        elif choice == '4':
            use_composio = not use_composio
        elif choice == 's':
            final_model = model
            if not thinking:
                final_model += "-no-thinking"
            if not search:
                final_model += "-no-search"
            return final_model, use_composio
        elif choice == 'q':
            return None, None

def setup_model():
    """
    Sets up and returns an OpenAIChatCompletionsModel configured dynamically 
    based on the available environment variables.
    """
    import httpx

    # 1. Check for Kimi Proxy
    kimi_url = os.getenv("KIMI_PROXY_URL")
    if kimi_url:
        kimi_active = False
        try:
            # Quick check if Kimi Proxy is online
            response = httpx.get(f"{kimi_url.rstrip('/')}/v1/models", headers={"Authorization": "Bearer your_secret_api_key"}, timeout=2.0)
            if response.status_code == 200:
                kimi_active = True
        except Exception:
            pass

        if kimi_active:
            kimi_api_key = os.getenv("KIMI_API_KEY", "your_secret_api_key")
            base_url = f"{kimi_url.rstrip('/')}/v1"
            
            # Renders the interactive configuration menu
            model_name, use_composio = configure_mimo_cli()
            if model_name is None:
                raise SystemExit("Quit selected by user.")
                
            print(f"\n🔌 Configuring Agent with Kimi Proxy at: {base_url}")
            print(f"🤖 Selected Model Configuration: {model_name}\n")
            
            client = AsyncOpenAI(
                api_key=kimi_api_key,
                base_url=base_url
            )
            return OpenAIChatCompletionsModel(
                model=model_name,
                openai_client=client
            ), use_composio
        else:
            print("⚠️ Kimi Proxy is configured but unreachable. Checking Gemini...")

    # 2. Check for Gemini (via OpenAI compatibility endpoint)
    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key:
        # Get GEMINI_MODEL or default to gemini-2.5-flash
        model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        print(f"✨ Configuring Agent with Google Gemini (OpenAI Compatibility Mode): {model_name}")
        
        client = AsyncOpenAI(
            api_key=gemini_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
        )
        return OpenAIChatCompletionsModel(
            model=model_name,
            openai_client=client
        ), True

    # 3. Fallback to standard OpenAI if key is present
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        print("🤖 Configuring Agent with standard OpenAI API")
        client = AsyncOpenAI(api_key=openai_key)
        return OpenAIChatCompletionsModel(
            model="gpt-4o",
            openai_client=client
        ), True

    raise ValueError(
        "No LLM provider configuration found. Please set either KIMI_PROXY_URL, "
        "GEMINI_API_KEY, or OPENAI_API_KEY in your environment."
    )

async def main():
    # Initialize dynamic model configuration
    try:
        model, use_composio = setup_model()
    except Exception as e:
        print(f"❌ Configuration Error: {e}")
        return

    # Initialize Composio with the OpenAI Agents provider
    tools = []
    if use_composio:
        composio_api_key = os.getenv("COMPOSIO_API_KEY")
        if not composio_api_key:
            print("⚠️ Warning: COMPOSIO_API_KEY is not set. Some tool calls may fail.")

        # Initialize Composio
        try:
            print("📦 Initializing Composio tools...")
            composio = Composio(provider=OpenAIAgentsProvider())
            user_id = "user_cognitum_agent"
            session = composio.create(user_id=user_id)
            # Load the meta tools (for managing connections, search, workbench, etc.)
            meta_tools = session.tools()
            
            # Load specific app tools natively so the LLM can call them directly
            app_tools = composio.tools.get(
                user_id=user_id,
                toolkits=["COMPOSIO_SEARCH", "GITLAB", "FIRECRAWL", "ELEVENLABS", "DISCORDBOT"]
            )
            
            tools = meta_tools + app_tools
            print(f"✅ Successfully loaded {len(tools)} tools natively from Composio (including Search, GitLab, Firecrawl, ElevenLabs, Discord)")
        except Exception as e:
            print(f"⚠️ Could not load tools from Composio: {e}. Running with empty tool set.")
    else:
        print("🚫 Composio tools disabled by user configuration. Running with empty tool set.")

    # Create agent with the dynamic model and loaded tools
    agent = Agent(
        name="COGNITUM Assistant",
        instructions=(
            "You are COGNITUM Assistant, a powerful system agent.\n"
            "CRITICAL: You do NOT have any built-in internet search features. If the user asks you to "
            "search the web, get news, or read/crawl a webpage, you MUST search for and use your "
            "Composio tools. For searching the web, use 'COMPOSIO_SEARCH_DUCK_DUCK_GO' or 'COMPOSIO_SEARCH_EXA_ANSWER'. "
            "For fetching webpage contents, use 'COMPOSIO_SEARCH_FETCH_URL_CONTENT'. "
            "Do NOT try to call 'COMPOSIO_SEARCH_WEB' (use the DuckDuckGo or Exa tools instead). "
            "Never tell the user that search is disabled or ask them to click an 'Online' (联网) button."
        ),
        model=model,
        tools=tools,
    )

    print("\n💬 COGNITUM Agent Interactive Chat started!")
    print("Type 'sair' or 'exit' to quit.\n")
    
    history = None
    
    while True:
        try:
            # Prompt the user for input
            user_input = input("👤 Você: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["sair", "exit", "quit"]:
                print("👋 Bye!")
                break
                
            print("🤖 COGNITUM está pensando...")
            
            # Prepare input: first turn uses string, subsequent turns use input list history
            if history is None:
                chat_input = user_input
            else:
                chat_input = history
                chat_input.append({"role": "user", "content": user_input})
                
            result = await Runner.run(
                starting_agent=agent,
                input=chat_input,
            )
            
            # Update the conversation history with the result
            history = result.to_input_list()
            
            print("\n🏆 Resposta do Agent:")
            print(result.final_output)
            print("-" * 50 + "\n")
            
        except KeyboardInterrupt:
            print("\n👋 Bye!")
            break
        except Exception as e:
            print(f"❌ Erro na execução: {e}\n")

if __name__ == "__main__":
    asyncio.run(main())
