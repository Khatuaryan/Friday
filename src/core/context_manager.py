"""
Follow-Up Context Manager — Tracks conversational state and active interaction windows.

Determines whether ambient speech detected within a short post-response window (default 15s)
should be treated as a direct continuation command for Friday without requiring the wake word.
"""

from __future__ import annotations

import os
import time
from src.utils.logger import get_logger

logger = get_logger("friday.context_manager")


class FollowUpContextManager:
    """
    Tracks and validates follow-up conversation context.
    
    Checks if a query occurred within the dynamic post-response window (configurable)
    and validates if the transcript is directed to Friday or is ambient conversation.
    """

    def __init__(self, default_window_secs: float = 15.0) -> None:
        """
        Initialize the context manager.
        
        Args:
            default_window_secs: Fallback timeframe in seconds for follow-up detection.
        """
        self._default_window_secs = default_window_secs
        self.last_response_time: float = 0.0
        self.last_command: str = ""
        self.last_response: str = ""

        # Phrases indicating direct continuation
        self.CONTINUATION_PREFIXES = [
            "and", "also", "but", "what about", "how about", "so", "then",
            "what if", "why", "when", "ok", "alright", "tell me", "can you",
            "could you", "please", "actually", "who", "where", "show me",
            "do it", "yes", "no", "play", "stop", "pause", "open", "close"
        ]

        # Ambient conversation indicators (boss talking to someone else)
        self.AMBIENT_VERBS = ["tell", "ask", "call", "send", "say to", "talk to"]
        # Common proper names to filter out if addressed to a third person
        self.COMMON_NAMES = {
            "rohan", "rahul", "amit", "priya", "pooja", "john", "sarah", "david",
            "mike", "emily", "james", "lisa", "alex", "chris", "anna", "sam"
        }

    @property
    def window_secs(self) -> float:
        """Retrieve the follow-up window duration from the environment or default."""
        try:
            return float(os.getenv("FRIDAY_FOLLOWUP_WINDOW_SECS", str(self._default_window_secs)))
        except ValueError:
            return self._default_window_secs

    def record_response(self, command: str, response: str) -> None:
        """
        Record a successful response to establish the follow-up timestamp and context.

        Args:
            command: The transcribed command from the user.
            response: Friday's synthesized response text.
        """
        self.last_command = (command or "").strip()
        self.last_response = (response or "").strip()
        self.last_response_time = time.perf_counter()
        logger.debug(
            "Recorded response context. Command: '%s'. Time: %.2f",
            self.last_command,
            self.last_response_time
        )

    def is_followup_window_active(self) -> bool:
        """
        Check if the current time sits within the active follow-up window.

        Returns:
            True if within window_secs of last recorded response.
        """
        if self.last_response_time <= 0:
            return False
        elapsed = time.perf_counter() - self.last_response_time
        active = elapsed <= self.window_secs
        if active:
            logger.debug("Follow-up window is active (elapsed: %.2fs / %.2fs)", elapsed, self.window_secs)
        return active

    def is_followup_eligible(self, transcript: str) -> bool:
        """
        Applies heuristics to check if the transcript qualifies as a direct follow-up.

        Args:
            transcript: Transcribed speech to evaluate.

        Returns:
            True if the transcript represents an eligible follow-up query.
        """
        clean_text = (transcript or "").strip().lower()
        if not clean_text:
            return False

        # 1. Explicit wake words or helper address are always eligible
        for ww in ["hey mycroft", "hey friday", "friday", "mycroft"]:
            if clean_text.startswith(ww):
                logger.info("Direct wake word/address found in follow-up candidate.")
                return True

        # 2. Heuristic check: is the boss speaking to someone else?
        # e.g., "tell Rohan...", "ask Rohan..."
        words = clean_text.split()
        if len(words) >= 2 and words[0] in self.AMBIENT_VERBS:
            target = words[1]
            if target in self.COMMON_NAMES:
                logger.info(
                    "Ambient speech detected: Boss addressed third person '%s' using verb '%s'",
                    target,
                    words[0]
                )
                return False

        # If the first word itself is a third-person name and not followed by a known instruction
        if len(words) >= 1 and words[0] in self.COMMON_NAMES:
            logger.info("Ambient speech detected: Transcript starts with third-person name '%s'", words[0])
            return False

        # 3. Check for explicit continuation prefixes
        for prefix in self.CONTINUATION_PREFIXES:
            if clean_text.startswith(prefix + " ") or clean_text == prefix:
                logger.info("Follow-up eligible: matched continuation prefix '%s'", prefix)
                return True

        # 4. Check for semantic topic overlap (Jaccard similarity)
        similarity = self._jaccard_similarity(clean_text, self.last_command)
        if similarity >= 0.15:
            logger.info("Follow-up eligible: topic similarity (Jaccard: %.2f >= 0.15)", similarity)
            return True

        # 5. Default to True if it does not match ambient filters, is short, and contains a verb/question
        # e.g., "what time is it?", "what is that?", etc.
        question_words = {"what", "how", "why", "when", "who", "where", "which", "can", "could", "is", "are", "do", "does"}
        if any(qw in words for qw in question_words):
            logger.info("Follow-up eligible: detected interrogative query pattern.")
            return True

        # Otherwise, if we had a strong prior conversation and similarity is non-zero, let it pass
        if similarity > 0:
            logger.info("Follow-up eligible: mild topic similarity (%.2f)", similarity)
            return True

        logger.debug("Transcript '%s' did not satisfy follow-up heuristics.", clean_text)
        return False

    def _jaccard_similarity(self, s1: str, s2: str) -> float:
        """Calculate word-level Jaccard similarity, filtering common English stopwords."""
        w1 = set(s1.split())
        w2 = set(s2.split())
        if not w1 or not w2:
            return 0.0

        stopwords = {
            "is", "the", "a", "an", "to", "of", "in", "on", "at", "for", "with",
            "about", "what", "how", "why", "when", "my", "your", "you", "me",
            "hey", "friday", "mycroft"
        }
        w1_filtered = w1 - stopwords
        w2_filtered = w2 - stopwords

        if not w1_filtered or not w2_filtered:
            intersection = w1.intersection(w2)
            union = w1.union(w2)
        else:
            intersection = w1_filtered.intersection(w2_filtered)
            union = w1_filtered.union(w2_filtered)

        return len(intersection) / len(union) if union else 0.0
