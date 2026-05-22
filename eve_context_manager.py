"""
Eve Context Manager Module
Provides fit_context() function for truncating messages to stay within token limits.
"""

import json
from typing import List, Dict, Any, Optional


def fit_context(messages: list, max_tokens: int, system_prompt: str = "") -> dict:
    """
    Truncate conversation messages to fit within max_tokens, preserving system prompt.
    
    Args:
        messages: List of message dicts with 'role' and 'content' keys
        max_tokens: Maximum token budget (includes system_prompt and output buffer)
        system_prompt: Optional system prompt to preserve at top of context
    
    Returns:
        dict with 'messages', 'token_count', 'truncated' flag
    """
    if not isinstance(messages, list):
        raise ValueError("messages must be a list")
    
    # Count tokens roughly (1 token ≈ 4 chars for English)
    def estimate_tokens(text: str) -> int:
        return len(text.strip()) // 4
    
    # Build initial context with system prompt
    context_messages = []
    if system_prompt:
        context_messages.append({"role": "system", "content": system_prompt})
    
    # Calculate available tokens for user/assistant messages
    system_tokens = estimate_tokens(system_prompt) if system_prompt else 0
    available_tokens = max_tokens - system_tokens
    output_buffer = 500  # Reserve tokens for model response
    available_tokens -= output_buffer
    
    if available_tokens <= 0:
        return {
            "messages": context_messages,
            "token_count": system_tokens,
            "truncated": True,
            "error": "max_tokens too low for system prompt + output"
        }
    
    # Greedy truncation: keep most recent messages that fit
    total_tokens = system_tokens
    truncated_messages = []
    
    for msg in reversed(messages):
        msg_tokens = estimate_tokens(msg.get("content", ""))
        if total_tokens + msg_tokens <= available_tokens:
            truncated_messages.insert(0, msg)
            total_tokens += msg_tokens
        else:
            # Try partial truncation for last message
            remaining = available_tokens - total_tokens
            if remaining > 100:  # Minimum meaningful content
                truncate_at = int(len(msg["content"]) * (remaining / msg_tokens))
                truncated_content = msg["content"][:truncate_at] + "\n... [TRUNCATED]"
                msg["content"] = truncated_content
                msg_tokens = estimate_tokens(truncated_content)
                truncated_messages.insert(0, msg)
                total_tokens += msg_tokens
            break
    
    # Build final context
    context_messages.extend(truncated_messages)
    
    return {
        "messages": context_messages,
        "total_tokens": total_tokens,
        "dropped": len(messages) - len(truncated_messages),
        "truncated": len(truncated_messages) < len(messages),
        "original_message_count": len(messages),
    }

if __name__ == "__main__":
    msgs = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"Message {i}: " + "word " * 30} for i in range(20)]
    print(f"Before: {len(msgs)} messages, ~{sum(len(m['content'])//4 for m in msgs)} tokens")
    result = fit_context(msgs, 800, system_prompt="You are Eve.")
    print(f"After: {len(result['messages'])} messages, {result['total_tokens']} tokens")
    print(f"Dropped: {result['dropped']} | Truncated: {result['truncated']}")
