"""
The Wire Polecats - Human-assisted SMS CRM.

CRITICAL: All SMS output requires human approval. The Wire is human-assisted only.
This is a compliance requirement (CAN-SPAM, GDPR, TCPA) and a design invariant.

Polecats:
- SMSDraftPolecat: Draft SMS messages (ALWAYS requires approval)
"""

from typing import Any

from polecats.base import BasePolecat, register_polecat


@register_polecat
class WireSMSDraftPolecat(BasePolecat):
    """
    Draft SMS messages for human review.

    CRITICAL: This Polecat's output ALWAYS requires human approval.
    Never send SMS automatically - this is enforced at multiple levels.

    The Wire is human-assisted only:
    - AI drafts the message
    - Human reviews and approves
    - Human sends

    This is both a compliance requirement and a design invariant.
    """

    task_class = "sms_draft"
    content_type = "social"  # SMS has character limits like social
    rig = "wire"

    # CRITICAL: SMS always requires approval - no exceptions
    always_requires_approval = True

    async def execute(self) -> str:
        """Draft SMS message for human approval."""
        data = self.context.bead_data

        recipient_name = data.get("first_name", "")
        company = data.get("company_name", "")
        relationship_stage = self.config.get("relationship_stage", "initial")
        context = self.config.get("context", "")
        purpose = self.config.get("purpose", "follow_up")

        prompt = f"""Draft an SMS message for human review:

Recipient:
- Name: {recipient_name}
- Company: {company}
- Relationship Stage: {relationship_stage}

Purpose: {purpose}
Context: {context}

CRITICAL SMS Requirements:
1. Maximum 160 characters (single SMS)
2. Must be personal and conversational
3. Must have clear purpose
4. Must be easy to respond to
5. NO spam language
6. NO unsolicited promotional content
7. Must feel like genuine human communication

This message will be reviewed and sent by a human.

Generate as JSON:
{{
    "sms_text": "The SMS message text",
    "character_count": 123,
    "purpose": "Brief description of message purpose",
    "tone": "friendly/professional/urgent",
    "expected_response": "What we hope recipient does",
    "compliance_check": {{
        "is_solicited": true,
        "has_prior_relationship": true,
        "is_transactional": false
    }},
    "timing_recommendation": "Best time to send",
    "if_no_response": "Suggested follow-up (also requires approval)"
}}

Output only valid JSON:
"""
        return await self.call_neurometric(prompt)

    def _get_bead_type(self) -> str:
        return "lead"


@register_polecat
class WireConversationAnalysisPolecat(BasePolecat):
    """
    Analyze SMS conversation history.

    Helps humans understand conversation context before responding.
    Output is analysis, not messages - but still goes through approval
    for visibility into AI analysis.
    """

    task_class = "sms_analysis"
    content_type = "social"
    rig = "wire"

    # Analysis also requires approval for transparency
    always_requires_approval = True

    async def execute(self) -> str:
        """Analyze conversation history."""
        data = self.context.bead_data

        conversation_history = self.config.get("conversation_history", [])
        recipient_name = data.get("first_name", "")

        prompt = f"""Analyze this SMS conversation:

Recipient: {recipient_name}

Conversation History:
{conversation_history}

Provide analysis as JSON:
{{
    "conversation_summary": "Brief summary",
    "recipient_sentiment": "positive/neutral/negative/uncertain",
    "engagement_level": "high/medium/low",
    "key_topics_discussed": ["topic1", "topic2"],
    "open_questions": ["Unanswered questions"],
    "next_steps_mentioned": ["Any commitments made"],
    "response_recommendations": [
        {{
            "scenario": "If they said X",
            "suggested_approach": "Consider Y"
        }}
    ],
    "risk_factors": ["Any concerns for the relationship"],
    "opportunity_signals": ["Positive signals detected"]
}}

Output only valid JSON:
"""
        return await self.call_neurometric(prompt)

    def _get_bead_type(self) -> str:
        return "lead"


@register_polecat
class WireResponseSuggestionPolecat(BasePolecat):
    """
    Suggest responses to incoming SMS.

    Provides multiple response options for human selection.
    All suggestions require human approval before sending.
    """

    task_class = "sms_response"
    content_type = "social"
    rig = "wire"

    # All SMS output requires approval
    always_requires_approval = True

    async def execute(self) -> str:
        """Suggest SMS responses."""
        data = self.context.bead_data

        incoming_message = self.config.get("incoming_message", "")
        conversation_history = self.config.get("conversation_history", [])
        recipient_name = data.get("first_name", "")

        prompt = f"""Suggest responses to this incoming SMS:

From: {recipient_name}
Incoming Message: "{incoming_message}"

Recent History:
{conversation_history[-5:] if conversation_history else "No history"}

Provide 3 response options as JSON:
{{
    "incoming_analysis": {{
        "intent": "What they're asking/saying",
        "urgency": "high/medium/low",
        "sentiment": "positive/neutral/negative"
    }},
    "response_options": [
        {{
            "option": "A",
            "text": "Response text (160 chars max)",
            "character_count": 123,
            "tone": "friendly/professional/direct",
            "when_to_use": "Use this when..."
        }},
        {{
            "option": "B",
            "text": "Alternative response",
            "character_count": 100,
            "tone": "different tone",
            "when_to_use": "Use this when..."
        }},
        {{
            "option": "C",
            "text": "Third option",
            "character_count": 80,
            "tone": "another approach",
            "when_to_use": "Use this when..."
        }}
    ],
    "recommended_option": "A",
    "recommendation_reason": "Why this is recommended",
    "do_not_respond_if": "Conditions where no response is best"
}}

Output only valid JSON:
"""
        return await self.call_neurometric(prompt)

    def _get_bead_type(self) -> str:
        return "lead"
