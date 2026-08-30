from typing import Any
from apps.backend.observability.emit import emit

def usage_from_response(response: Any) -> dict:
    """Extracts {'prompt_tokens', 'response_tokens', 'total_tokens'} from a
    google.genai GenerateContentResponse. Returns zeros if unavailable."""
    usage = {
        "prompt_tokens": 0,
        "response_tokens": 0,
        "total_tokens": 0
    }
    
    try:
        usage_meta = getattr(response, "usage_metadata", None)
        if usage_meta:
            usage["prompt_tokens"] = getattr(usage_meta, "prompt_token_count", 0) or 0
            usage["response_tokens"] = getattr(usage_meta, "candidates_token_count", 0) or 0
            usage["total_tokens"] = getattr(usage_meta, "total_token_count", 0) or 0
    except Exception:
        pass
        
    return usage

def record_llm_call(*, model: str, usage: dict, duration_ms: int,
                    cached: bool = False, retries: int = 0,
                    error: str | None = None) -> None:
    """Emits one `llm` event."""
    
    prompt = usage.get("prompt_tokens", 0)
    resp = usage.get("response_tokens", 0)
    
    msg = f"{model}: {prompt} prompt + {resp} response tokens"
    if cached:
        msg = f"{model}: cached hit"
    if error:
        msg = f"{model}: error - {error}"
        
    emit(
        level="error" if error else "info",
        source="agent",
        category="llm",
        message=msg,
        duration_ms=duration_ms,
        data={
            "model": model,
            "prompt_tokens": prompt,
            "response_tokens": resp,
            "total_tokens": usage.get("total_tokens", 0),
            "cached": cached,
            "retries": retries,
            "error": error
        }
    )
