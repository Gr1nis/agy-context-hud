import json
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional
import time


def estimate_tokens(text: str) -> int:
    """Calibrated token estimator for Gemini models across Code, English, and Cyrillic."""
    if not text:
        return 0
    ascii_chars = sum(1 for c in text if ord(c) < 128)
    non_ascii_chars = len(text) - ascii_chars
    # Code/ASCII averages ~3.5 chars/token; Cyrillic averages ~2.1 chars/token
    return int((ascii_chars / 3.5) + (non_ascii_chars / 2.1))


@dataclass
class ChatContextStats:
    conv_id: str
    title: str
    last_modified: float
    step_count: int = 0
    system_tokens: int = 0
    messages_tokens: int = 0
    tools_tokens: int = 0
    thinking_tokens: int = 0
    largest_tool_step: str = ""

    @property
    def total_tokens(self) -> int:
        return (
            self.system_tokens
            + self.messages_tokens
            + self.tools_tokens
            + self.thinking_tokens
        )

    @property
    def smart_limit(self) -> int:
        # Practical threshold where agents start losing focus / hitting stream timeouts
        return 150_000

    @property
    def usage_percent(self) -> float:
        return min(100.0, (self.total_tokens / self.smart_limit) * 100.0)

    @property
    def free_smart_tokens(self) -> int:
        return max(0, self.smart_limit - self.total_tokens)

    @property
    def status_zone(self) -> Dict[str, str]:
        pct = self.usage_percent
        if pct < 50:
            return {
                "level": "OPTIMAL",
                "color": "#81c995",
                "badge": "Свежий контекст",
            }
        elif pct < 82:
            return {
                "level": "WARNING",
                "color": "#fdd663",
                "badge": "Нагрузка растёт",
            }
        else:
            return {
                "level": "DANGER",
                "color": "#f28b82",
                "badge": "Риск потери контекста",
            }


class AntigravityContextAnalyzer:
    def __init__(self):
        self.home = Path.home()
        self.gemini_dir = self.home / ".gemini"
        self.brain_dir = self.gemini_dir / "antigravity" / "brain"
        self._cached_system_tokens: Optional[int] = None

    def get_system_overhead_tokens(self) -> int:
        if self._cached_system_tokens is not None:
            return self._cached_system_tokens

        # Base Antigravity tool schemas + system identity prompt (~9,200 tokens)
        tokens = 9200

        # Global & scratch GEMINI.md rules
        for rule_path in [
            self.gemini_dir / "config" / "GEMINI.md",
            self.gemini_dir / "antigravity" / "scratch" / "GEMINI.md",
        ]:
            if rule_path.exists():
                try:
                    tokens += estimate_tokens(rule_path.read_text(encoding="utf-8", errors="ignore"))
                except Exception:
                    pass

        # Installed skill metadata / frontmatter overhead (~150 tokens per skill)
        skills_dir = self.gemini_dir / "config" / "skills"
        if skills_dir.exists():
            skill_count = sum(1 for d in skills_dir.iterdir() if d.is_dir())
            tokens += skill_count * 180

        self._cached_system_tokens = tokens
        return tokens

    def _parse_annotation(self, conv_id: str) -> tuple[str, float]:
        ann_file = self.gemini_dir / "antigravity" / "annotations" / f"{conv_id}.pbtxt"
        if not ann_file.exists():
            return "", 0.0
        try:
            import re
            txt = ann_file.read_text(encoding="utf-8", errors="ignore")
            title = ""
            m_title = re.search(r'title:\s*"([^"]+)"', txt)
            if m_title:
                title = m_title.group(1).strip()
            sec = 0.0
            m_sec = re.search(r"last_user_view_time:\s*\{\s*seconds:\s*(\d+)(?:\s*nanos:\s*(\d+))?", txt)
            if m_sec:
                sec = float(m_sec.group(1)) + (float(m_sec.group(2) or 0) / 1e9)
            return title, max(sec, ann_file.stat().st_mtime)
        except Exception:
            return "", 0.0

    def get_active_chat(self) -> Optional[ChatContextStats]:
        if not self.brain_dir.exists():
            return None

        best_score = -1.0
        best_conv = None
        best_log = None
        best_title = ""

        for conv_dir in self.brain_dir.iterdir():
            if not conv_dir.is_dir():
                continue
            log_dir = conv_dir / ".system_generated" / "logs"
            log_file = log_dir / "transcript_full.jsonl"
            if not log_file.exists():
                log_file = log_dir / "transcript.jsonl"
            if not log_file.exists():
                continue
            try:
                log_mtime = log_file.stat().st_mtime
                pb_title, view_time = self._parse_annotation(conv_dir.name)
                activity_time = max(log_mtime, view_time)
                if activity_time > best_score:
                    best_score = activity_time
                    best_conv = conv_dir.name
                    best_log = log_file
                    best_title = pb_title
            except OSError:
                continue

        if best_conv and best_log:
            stats = self.analyze_transcript(best_conv, best_log, best_score)
            if best_title:
                stats.title = best_title
            return stats
        return None

    def analyze_transcript(self, conv_id: str, log_file: Path, mtime: float) -> ChatContextStats:
        stats = ChatContextStats(
            conv_id=conv_id,
            title=f"Chat {conv_id[:8]}...",
            last_modified=mtime,
            system_tokens=self.get_system_overhead_tokens(),
        )
        max_tool_tok = 0
        try:
            raw_text = log_file.read_text(encoding="utf-8", errors="ignore")
            lines = raw_text.splitlines()
            stats.step_count = len(lines)

            for line in lines:
                if not line.strip():
                    continue
                try:
                    step = json.loads(line)
                except json.JSONDecodeError:
                    continue

                step_type = step.get("type", "")
                content = step.get("content", "") or ""
                thinking = step.get("thinking", "") or ""
                tool_calls = step.get("tool_calls", []) or []

                if step_type == "USER_INPUT":
                    if stats.title.startswith("Chat ") and content.strip():
                        clean = content.replace("<USER_REQUEST>", "").replace("</USER_REQUEST>", "").strip()
                        first_line = next((l.strip() for l in clean.splitlines() if l.strip()), "")
                        if first_line:
                            stats.title = (first_line[:42] + "…") if len(first_line) > 42 else first_line
                    stats.messages_tokens += estimate_tokens(content)

                elif step_type == "PLANNER_RESPONSE":
                    stats.messages_tokens += estimate_tokens(content)
                    stats.thinking_tokens += estimate_tokens(thinking)
                    if tool_calls:
                        tc_str = json.dumps(tool_calls, ensure_ascii=False)
                        stats.tools_tokens += estimate_tokens(tc_str)

                else:
                    # GENERIC / Tool outputs / File views / Command outputs
                    t_tok = estimate_tokens(content)
                    stats.tools_tokens += t_tok
                    if t_tok > max_tool_tok:
                        max_tool_tok = t_tok
                        stats.largest_tool_step = f"Шаг #{step.get('step_index', '?')} ({t_tok:,} ток.)"
        except Exception:
            pass

        return stats
