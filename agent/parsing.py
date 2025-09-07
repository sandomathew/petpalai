# agent/parsing.py

from .llm_parser import try_llm_parser

def route_message(message):
    message = message.strip()

    # 🔍 First attempt: LLM
    parsed = try_llm_parser(message)
    if parsed:
        return "🤖 Working on it...", parsed

    # 🧱 Fallback: rule-based regex
    from .rule_parser import fallback_regex_parser
    return fallback_regex_parser(message)