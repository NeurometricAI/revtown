"""
Refinery - Automated quality gate for all outputs.

Every output that touches the real world must pass through Refinery.
Checks include: brand voice, spam score, SEO grade, legal flags, hallucination likelihood.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Protocol
from uuid import UUID

import structlog

logger = structlog.get_logger()


class CheckResult(str, Enum):
    """Result of a Refinery check."""

    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


@dataclass
class RefineryScore:
    """Score from a single Refinery check."""

    check_name: str
    result: CheckResult
    score: float  # 0.0 to 1.0
    details: str | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass
class RefineryResult:
    """Aggregated result from all Refinery checks."""

    passed: bool
    overall_score: float  # 0.0 to 1.0
    scores: list[RefineryScore]
    warnings: list[str]
    blocking_issues: list[str]
    checked_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def should_force_approval(self) -> bool:
        """Whether this content should be forced to approval queue."""
        return not self.passed or self.overall_score < 0.8


class RefineryCheck(Protocol):
    """Protocol for Refinery check functions."""

    async def __call__(self, content: str, context: dict[str, Any]) -> RefineryScore:
        """Run the check and return a score."""
        ...


# =============================================================================
# Universal Checks (apply to all content)
# =============================================================================


async def check_brand_voice(content: str, context: dict[str, Any]) -> RefineryScore:
    """
    Check content against brand voice guidelines.

    Uses the organization's brand voice settings to evaluate tone,
    vocabulary, and style consistency.
    """
    # TODO: Implement via Neurometric call to analyze brand voice
    # For now, return placeholder

    return RefineryScore(
        check_name="brand_voice",
        result=CheckResult.PASS,
        score=0.85,
        details="Brand voice analysis placeholder",
    )


async def check_hallucination(content: str, context: dict[str, Any]) -> RefineryScore:
    """
    Check for potential hallucinations or fabricated information.

    Flags:
    - Statistics without sources
    - Quotes without attribution
    - Specific claims that can't be verified
    """
    warnings = []

    # Check for unverified statistics
    import re

    stat_patterns = [
        r"\d+%",  # Percentages
        r"\$\d+",  # Dollar amounts
        r"\d+x",  # Multipliers
    ]

    for pattern in stat_patterns:
        matches = re.findall(pattern, content)
        if matches and "source" not in content.lower():
            warnings.append(f"Statistics found without source citation: {matches[:3]}")

    # Check for quoted text without attribution
    quote_pattern = r'"[^"]{20,}"'
    quotes = re.findall(quote_pattern, content)
    if quotes:
        warnings.append("Quoted text found - verify attribution")

    result = CheckResult.PASS if not warnings else CheckResult.WARN
    score = 1.0 - (len(warnings) * 0.15)

    return RefineryScore(
        check_name="hallucination",
        result=result,
        score=max(score, 0.0),
        details="Hallucination likelihood check",
        warnings=warnings,
    )


async def check_legal_flags(content: str, context: dict[str, Any]) -> RefineryScore:
    """
    Check for potential legal issues.

    Flags:
    - Trademark usage
    - Copyright concerns
    - Defamation risks
    - Compliance issues (GDPR, CAN-SPAM, TCPA)
    """
    warnings = []

    # Check for competitor mentions that might be problematic
    if "competitor" in context:
        competitor_name = context["competitor"]
        if competitor_name.lower() in content.lower():
            warnings.append(f"Competitor '{competitor_name}' mentioned - verify claims")

    # Check for absolutes that could be problematic
    absolute_terms = ["guarantee", "always", "never", "100%", "best in class", "industry leading"]
    for term in absolute_terms:
        if term.lower() in content.lower():
            warnings.append(f"Absolute claim found: '{term}' - verify accuracy")

    result = CheckResult.PASS if not warnings else CheckResult.WARN
    score = 1.0 - (len(warnings) * 0.1)

    return RefineryScore(
        check_name="legal_flags",
        result=result,
        score=max(score, 0.0),
        details="Legal compliance check",
        warnings=warnings,
    )


# =============================================================================
# Content-Type Specific Checks
# =============================================================================


async def check_spam_score(content: str, context: dict[str, Any]) -> RefineryScore:
    """
    Check spam likelihood for email/outreach content.

    Standard: spam_score < 3
    """
    warnings = []
    spam_score = 0

    # Check for spam trigger words
    spam_triggers = [
        "act now", "limited time", "free", "winner", "congratulations",
        "urgent", "don't miss", "exclusive offer", "click here",
    ]

    content_lower = content.lower()
    for trigger in spam_triggers:
        if trigger in content_lower:
            spam_score += 1
            warnings.append(f"Spam trigger word: '{trigger}'")

    # Check for excessive caps
    caps_ratio = sum(1 for c in content if c.isupper()) / max(len(content), 1)
    if caps_ratio > 0.3:
        spam_score += 2
        warnings.append("Excessive capitalization")

    # Check for excessive punctuation
    if content.count("!") > 3:
        spam_score += 1
        warnings.append("Excessive exclamation marks")

    # Standard: spam_score < 3
    passed = spam_score < 3
    result = CheckResult.PASS if passed else CheckResult.FAIL
    score = max(0, 1.0 - (spam_score / 5))

    return RefineryScore(
        check_name="spam_score",
        result=result,
        score=score,
        details=f"Spam score: {spam_score}",
        warnings=warnings,
    )


async def check_personalization_depth(content: str, context: dict[str, Any]) -> RefineryScore:
    """
    Check personalization depth for outreach content.

    Standard: personalization_depth > 70%
    """
    # Look for personalization markers
    personalization_markers = [
        "{{first_name}}", "{{company}}", "{{title}}",  # Template vars
    ]

    # Check if lead context was used
    lead = context.get("lead", {})
    lead_fields_used = 0
    lead_fields_total = 0

    for field in ["first_name", "company_name", "title", "industry"]:
        if lead.get(field):
            lead_fields_total += 1
            if str(lead[field]).lower() in content.lower():
                lead_fields_used += 1

    if lead_fields_total > 0:
        depth = lead_fields_used / lead_fields_total
    else:
        depth = 0.5  # Default if no lead context

    # Standard: > 70%
    passed = depth > 0.7
    result = CheckResult.PASS if passed else CheckResult.WARN

    return RefineryScore(
        check_name="personalization_depth",
        result=result,
        score=depth,
        details=f"Personalization depth: {depth:.0%}",
        warnings=[] if passed else ["Personalization depth below 70% threshold"],
    )


async def check_seo_grade(content: str, context: dict[str, Any]) -> RefineryScore:
    """
    Check SEO quality for blog/landing page content.
    """
    warnings = []
    score = 1.0

    # Check title length
    title = context.get("title", "")
    if len(title) < 30 or len(title) > 60:
        warnings.append(f"Title length ({len(title)} chars) - optimal is 30-60")
        score -= 0.1

    # Check meta description
    meta_desc = context.get("meta_description", "")
    if len(meta_desc) < 120 or len(meta_desc) > 160:
        warnings.append(f"Meta description length ({len(meta_desc)} chars) - optimal is 120-160")
        score -= 0.1

    # Check keyword density
    keywords = context.get("keywords", [])
    if keywords:
        content_lower = content.lower()
        for kw in keywords[:3]:  # Check top 3 keywords
            count = content_lower.count(kw.lower())
            word_count = len(content.split())
            density = (count / max(word_count, 1)) * 100
            if density < 0.5 or density > 3:
                warnings.append(f"Keyword '{kw}' density ({density:.1f}%) - optimal is 0.5-3%")
                score -= 0.05

    result = CheckResult.PASS if score > 0.7 else CheckResult.WARN

    return RefineryScore(
        check_name="seo_grade",
        result=result,
        score=max(score, 0),
        details="SEO quality check",
        warnings=warnings,
    )


async def check_readability(content: str, context: dict[str, Any]) -> RefineryScore:
    """
    Check readability using Flesch Reading Ease score.
    """
    # Simple Flesch Reading Ease approximation
    words = content.split()
    sentences = content.count(".") + content.count("!") + content.count("?")
    syllables = sum(count_syllables(word) for word in words)

    if sentences == 0:
        sentences = 1
    if len(words) == 0:
        return RefineryScore(
            check_name="readability",
            result=CheckResult.WARN,
            score=0.5,
            details="No content to analyze",
        )

    # Flesch Reading Ease formula
    fre = 206.835 - 1.015 * (len(words) / sentences) - 84.6 * (syllables / len(words))
    fre = max(0, min(100, fre))

    # Score mapping (FRE 60-70 is ideal for general audience)
    if fre >= 60:
        result = CheckResult.PASS
        score = min(fre / 100, 1.0)
    elif fre >= 30:
        result = CheckResult.WARN
        score = fre / 100
    else:
        result = CheckResult.FAIL
        score = fre / 100

    return RefineryScore(
        check_name="readability",
        result=result,
        score=score,
        details=f"Flesch Reading Ease: {fre:.0f}",
        warnings=[] if fre >= 60 else [f"Readability score {fre:.0f} is below recommended 60"],
    )


def count_syllables(word: str) -> int:
    """Estimate syllable count for a word."""
    word = word.lower()
    vowels = "aeiouy"
    count = 0
    prev_is_vowel = False

    for char in word:
        is_vowel = char in vowels
        if is_vowel and not prev_is_vowel:
            count += 1
        prev_is_vowel = is_vowel

    # Handle silent 'e'
    if word.endswith("e"):
        count -= 1

    return max(1, count)


async def check_ap_style(content: str, context: dict[str, Any]) -> RefineryScore:
    """
    Check AP Style compliance for PR content.
    """
    warnings = []

    # Common AP Style issues
    ap_issues = [
        (r"\b(\d) percent\b", "Use % symbol: '$1%'"),
        (r"\bpercent\b", "Use % symbol instead of 'percent'"),
        (r"\bover \d", "Use 'more than' for numerical comparisons"),
        (r"\bunder \d", "Use 'fewer than' or 'less than' for numerical comparisons"),
        (r"\be-mail\b", "Use 'email' (no hyphen)"),
        (r"\bweb site\b", "Use 'website' (one word)"),
    ]

    import re

    for pattern, message in ap_issues:
        if re.search(pattern, content, re.IGNORECASE):
            warnings.append(f"AP Style: {message}")

    score = 1.0 - (len(warnings) * 0.1)
    result = CheckResult.PASS if not warnings else CheckResult.WARN

    return RefineryScore(
        check_name="ap_style",
        result=result,
        score=max(score, 0),
        details="AP Style compliance check",
        warnings=warnings,
    )


# =============================================================================
# Refinery Engine
# =============================================================================


class Refinery:
    """
    The Refinery quality gate engine.

    Runs configurable checks on content before it can reach the real world.
    """

    # Default checks by content type
    DEFAULT_CHECKS: dict[str, list[Callable]] = {
        "email": [
            check_brand_voice,
            check_spam_score,
            check_personalization_depth,
            check_hallucination,
            check_legal_flags,
        ],
        "blog": [
            check_brand_voice,
            check_seo_grade,
            check_readability,
            check_hallucination,
            check_legal_flags,
        ],
        "pr_pitch": [
            check_brand_voice,
            check_ap_style,
            check_hallucination,
            check_legal_flags,
        ],
        "social": [
            check_brand_voice,
            check_hallucination,
            check_legal_flags,
        ],
        "landing_page": [
            check_brand_voice,
            check_seo_grade,
            check_readability,
            check_legal_flags,
        ],
    }

    def __init__(self, organization_id: UUID | None = None):
        self.organization_id = organization_id
        self.logger = logger.bind(
            service="refinery",
            organization_id=str(organization_id) if organization_id else None,
        )
        self._custom_checks: dict[str, list[Callable]] = {}

    def register_check(self, content_type: str, check: Callable):
        """Register a custom check for a content type."""
        if content_type not in self._custom_checks:
            self._custom_checks[content_type] = []
        self._custom_checks[content_type].append(check)

    async def check(
        self,
        content: str,
        content_type: str,
        context: dict[str, Any] | None = None,
        additional_checks: list[Callable] | None = None,
    ) -> RefineryResult:
        """
        Run all applicable checks on content.

        Args:
            content: The content to check
            content_type: Type of content (email, blog, pr_pitch, social, landing_page)
            context: Additional context for checks
            additional_checks: Extra checks to run

        Returns:
            RefineryResult with aggregated scores and pass/fail status
        """
        context = context or {}
        self.logger.info(
            "Running Refinery checks",
            content_type=content_type,
            content_length=len(content),
        )

        # Get checks for this content type
        checks = list(self.DEFAULT_CHECKS.get(content_type, []))
        checks.extend(self._custom_checks.get(content_type, []))
        if additional_checks:
            checks.extend(additional_checks)

        # Run all checks
        scores: list[RefineryScore] = []
        for check in checks:
            try:
                score = await check(content, context)
                scores.append(score)
            except Exception as e:
                self.logger.error(
                    "Refinery check failed",
                    check=check.__name__,
                    error=str(e),
                )
                scores.append(RefineryScore(
                    check_name=check.__name__,
                    result=CheckResult.WARN,
                    score=0.5,
                    details=f"Check error: {e}",
                ))

        # Aggregate results
        all_warnings = []
        blocking_issues = []

        for score in scores:
            all_warnings.extend(score.warnings)
            if score.result == CheckResult.FAIL:
                blocking_issues.append(f"{score.check_name}: {score.details}")

        overall_score = sum(s.score for s in scores) / max(len(scores), 1)
        passed = not blocking_issues

        result = RefineryResult(
            passed=passed,
            overall_score=overall_score,
            scores=scores,
            warnings=all_warnings,
            blocking_issues=blocking_issues,
        )

        self.logger.info(
            "Refinery check completed",
            passed=passed,
            overall_score=overall_score,
            check_count=len(scores),
            warning_count=len(all_warnings),
            blocking_count=len(blocking_issues),
        )

        return result


# =============================================================================
# Singleton Instance
# =============================================================================


def get_refinery(organization_id: UUID | None = None) -> Refinery:
    """Get a Refinery instance."""
    return Refinery(organization_id)
