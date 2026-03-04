# rlm/tools/telegram.py - Telegram Tool for RLMClaw

import logging
from typing import Dict, Any, Optional
# For actual Telegram integration, you would use a library like python-telegram-bot
# For now, we'll simulate the interaction or use basic HTTP requests.
import requests

logger = logging.getLogger(__name__)

class TelegramTool:
    """
    A tool for RLMClaw to interact with Telegram, enabling sending messages,
    reactions, and potentially managing group chats.
    """
    def __init__(self, config: Dict[str, Any]):
        self.bot_token = config.get("token")
        self.api_base_url = f"https://api.telegram.org/bot{self.bot_token}"
        self.allowed_chat_ids = config.get("allow_from", []) # List of allowed user/chat IDs

        if not self.bot_token:
            logger.warning("Telegram tool initialized without a bot token. Sending messages will fail.")
        else:
            logger.info("Telegram tool initialized.")

    def _send_request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Helper to send requests to the Telegram Bot API."""
        url = f"{self.api_base_url}/{method}"
        try:
            response = requests.post(url, json=params, timeout=5)
            response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
            return response.json()
        except requests.exceptions.Timeout:
            logger.error(f"Telegram API request timed out for method {method}")
            return {"ok": False, "description": "Request timed out"}
        except requests.exceptions.RequestException as e:
            logger.error(f"Telegram API request failed for method {method}: {e}")
            return {"ok": False, "description": str(e)}
        except json.JSONDecodeError:
            logger.error(f"Telegram API response was not valid JSON for method {method}: {response.text}")
            return {"ok": False, "description": "Invalid JSON response"}

    def send_message(self, chat_id: str, text: str, reply_to_message_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Sends a text message to a specified chat ID.
        Args:
            chat_id: The recipient's chat ID.
            text: The text of the message to be sent.
            reply_to_message_id: Optional message ID to reply to.
        Returns:
            A dictionary with the API response.
        """
        if not self.bot_token:
            return {"ok": False, "description": "Telegram bot token not configured."}
        if self.allowed_chat_ids and str(chat_id) not in [str(x) for x in self.allowed_chat_ids]:
            logger.warning(f"Attempted to send message to unauthorized chat ID: {chat_id}")
            return {"ok": False, "description": "Unauthorized chat ID."}

        params = {
            "chat_id": chat_id,
            "text": text
        }
        if reply_to_message_id:
            params["reply_to_message_id"] = reply_to_message_id

        logger.info(f"Sending message to {chat_id}")
        return self._send_request("sendMessage", params)

    def send_reaction(self, chat_id: str, message_id: int, emoji: str) -> Dict[str, Any]:
        """
        Sends a reaction to a specified message.
        Args:
            chat_id: The chat ID of the message.
            message_id: The ID of the message to react to.
            emoji: The emoji to use as a reaction (e.g., "👍", "👎", "🔥").
        Returns:
            A dictionary with the API response.
        """
        if not self.bot_token:
            return {"ok": False, "description": "Telegram bot token not configured."}
        if self.allowed_chat_ids and str(chat_id) not in [str(x) for x in self.allowed_chat_ids]:
            logger.warning(f"Attempted to react in unauthorized chat ID: {chat_id}")
            return {"ok": False, "description": "Unauthorized chat ID."}

        params = {
            "chat_id": chat_id,
            "message_id": message_id,
            "emoji": emoji,
            "is_big": False # Smaller reaction
        }
        logger.info(f"Sending reaction {emoji} to message {message_id} in chat {chat_id}")
        return self._send_request("setMessageReaction", params)

    def get_updates(self, offset: Optional[int] = None, limit: int = 100, timeout: int = 20) -> Dict[str, Any]:
        """
        Receives incoming updates using long polling.
        Args:
            offset: Identifier of the first update to be returned.
            limit: Limits the number of updates to be retrieved.
            timeout: Timeout in seconds for long polling.
        Returns:
            A dictionary with the API response.
        """
        if not self.bot_token:
            return {"ok": False, "description": "Telegram bot token not configured."}

        params = {
            "limit": limit,
            "timeout": timeout
        }
        if offset:
            params["offset"] = offset

        logger.info(f"Getting Telegram updates with offset {offset}, limit {limit}, timeout {timeout}")
        return self._send_request("getUpdates", params)

# Example Usage (for testing purposes)
if __name__ == "__main__":
    # In a real scenario, this would be loaded from config.json
    dummy_telegram_config = {
        "token": os.getenv("TELEGRAM_BOT_TOKEN"), # Ensure this env var is set for testing
        "allow_from": [os.getenv("TELEGRAM_USER_ID")] # User ID to allow messages from
    }

    if not dummy_telegram_config["token"]:
        print("Please set TELEGRAM_BOT_TOKEN environment variable for TelegramTool example.")
    if not dummy_telegram_config["allow_from"][0]:
        print("Please set TELEGRAM_USER_ID environment variable for TelegramTool example.")

    if dummy_telegram_config["token"] and dummy_telegram_config["allow_from"][0]:
        tool = TelegramTool(dummy_telegram_config)
        chat_id = dummy_telegram_config["allow_from"][0]

        # Test sending a message
        print("\n--- Testing send_message ---")
        send_result = tool.send_message(chat_id, "Hello from RLMClaw's Telegram tool!")
        print(f"Send Message Result: {send_result}")

        # Test sending a reaction (requires a message_id, which we don't have dynamically here)
        # For a real test, you'd need to send a message, then parse its ID from the response.
        # Placeholder for now:
        # if send_result.get("ok") and send_result.get("result"):
        #     message_id = send_result["result"]["message_id"]
        #     print("\n--- Testing send_reaction ---")
        #     react_result = tool.send_reaction(chat_id, message_id, "👍")
        #     print(f"Send Reaction Result: {react_result}")

        # Test getting updates (might not return anything if no new messages)
        print("\n--- Testing get_updates ---")
        updates_result = tool.get_updates()
        print(f"Get Updates Result: {updates_result}")
    else:
        print("TelegramTool example skipped due to missing configuration.")
