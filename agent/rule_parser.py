import re

def fallback_regex_parser(message):
    message = message.strip().lower()

    # 🧑 Register user
    match = re.search(r'register me as ([\w\s]+) with email (\S+@\S+)', message)
    if match:
        name = match.group(1).strip().title()
        email = match.group(2).strip()
        return (
            f"✅ Creating user profile for *{name}* with email *{email}*...",
            {"intent": "register_user", "params": {"name": name, "email": email}}
        )

    # 🐶 Add pet (stub)
    if "add a pet" in message or "create my pet" in message:
        return (
            "🦴 Adding a new pet... (logic TBD)",
            {"intent": "create_pet"}
        )

    # 🍖 Analyze food (stub)
    if "analyze" in message and "food" in message:
        return (
            "📸 Please upload the food label on the main page.",
            {"intent": "analyze_food"}
        )

    # 🤷 Fallback
    return (
        "🤔 I’m not sure what to do yet. Try something like: 'Register me as John Doe with email john@example.com'",
        {"intent": "unknown"}
    )