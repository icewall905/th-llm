import re
import random
import logging
import httpx
from config import settings

logger = logging.getLogger(__name__)

_model_cache: str = ""


def reset_model_cache():
    global _model_cache
    _model_cache = ""


async def _resolve_model() -> str:
    global _model_cache
    if _model_cache:
        return _model_cache
    if settings.llm_model:
        _model_cache = settings.llm_model
        return _model_cache
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(
                f"{settings.llm_base_url}/models",
                headers={"Authorization": f"Bearer {settings.llm_api_key}"},
            )
            resp.raise_for_status()
            data = resp.json()
            models = data.get("data", [])
            if models:
                _model_cache = models[0]["id"]
                logger.info(f"Auto-selected LLM model: {_model_cache}")
                return _model_cache
    except Exception as e:
        logger.warning(f"Could not auto-detect model: {e}")
    _model_cache = "default"
    return _model_cache


def _extract_text(msg: dict) -> str:
    """Return the model's final output, falling back to reasoning_content if content is empty."""
    return msg.get("content", "").strip() or msg.get("reasoning_content", "").strip()


def _parse_action(text: str) -> tuple[str, int]:
    """Parse poker action from model output, searching from the end."""
    lines = [l.strip() for l in text.strip().split('\n') if l.strip()]
    for line in reversed(lines):
        lu = line.upper().lstrip('* ->#•')
        m = re.match(r'RAISE\s+(\d+)', lu)
        if m:
            return "raise", int(m.group(1))
        if re.match(r'FOLD\b', lu):
            return "fold", 0
        if re.match(r'CHECK\b', lu):
            return "check", 0
        if re.match(r'CALL\b', lu):
            return "call", 0

    text_upper = text.upper()
    m = re.search(r'RAISE\s+(\d+)', text_upper)
    if m:
        return "raise", int(m.group(1))
    for action in ('CALL', 'CHECK', 'FOLD'):
        if re.search(rf'\b{action}\b', text_upper):
            return action.lower(), 0
    return "call", 0


def _parse_name(text: str) -> str:
    """Extract a clean name from the last non-empty line of model output."""
    for line in reversed(text.splitlines()):
        line = line.strip().strip('"\'*#-•>').strip()
        if line and len(line) <= 24:
            return line[:16]
    return text.strip()[:16] or "Maverick"


async def get_llm_name(existing_names: list[str]) -> str:
    """Ask the LLM to invent a short poker player nickname for itself."""
    model = await _resolve_model()
    taken = ", ".join(existing_names) if existing_names else "none"
    themes = [
        "wild west outlaw", "cyberpunk hacker", "1920s gangster", "ocean pirate",
        "ancient mythology", "space explorer", "ninja assassin", "arctic hunter",
        "jungle mercenary", "underground boxer", "desert nomad", "neon casino shark",
        "medieval knight", "voodoo mystic", "cold war spy", "rockabilly rebel",
    ]
    theme = random.choice(themes)
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": (
                    f"Pick a short, memorable poker player nickname inspired by a {theme} (1-2 words, max 12 chars). "
                    f"These names are already taken: {taken}. "
                    f"Reply with ONLY the name, nothing else."
                ),
            }
        ],
        "max_tokens": 20,
        "temperature": 1.0,
        "stream": False,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{settings.llm_base_url}/chat/completions",
                headers={"Authorization": f"Bearer {settings.llm_api_key}",
                         "Content-Type": "application/json"},
                json=payload,
            )
            resp.raise_for_status()
            msg = resp.json()["choices"][0]["message"]
            text = _extract_text(msg)
            name = _parse_name(text)
            logger.info(f"LLM chose name: {name!r}")
            return name
    except Exception as e:
        logger.warning(f"LLM name generation failed: {e}")
        return "Maverick"


async def get_llm_action(prompt: str, personality: str = "") -> tuple[str, int]:
    model = await _resolve_model()
    style = f" {personality}" if personality else " Play skillfully."
    system = (
        "You are a Texas Hold'em poker player." + style +
        " Think carefully about the situation, then respond with exactly "
        "one line after your reasoning: FOLD, CHECK, CALL, or RAISE <amount>."
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 8192,
        "temperature": 0.7,
        "stream": False,
    }

    try:
        async with httpx.AsyncClient(timeout=300) as client:
            resp = await client.post(
                f"{settings.llm_base_url}/chat/completions",
                headers={"Authorization": f"Bearer {settings.llm_api_key}",
                         "Content-Type": "application/json"},
                json=payload,
            )
            resp.raise_for_status()
            msg = resp.json()["choices"][0]["message"]
            content = msg.get("content", "").strip()
            reasoning = msg.get("reasoning_content", "")
            logger.info(f"LLM reasoning ({len(reasoning)} chars), content: {content!r}")
            text = content if content else reasoning
            return _parse_action(text)
    except Exception as e:
        logger.error(f"LLM request failed: {e}")
        return "call", 0
