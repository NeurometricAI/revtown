"""
SDR Hive Polecats - Outbound sales development.

Polecats:
- ScoutPolecat: Find and qualify leads
- EnrichPolecat: Enrich lead data
- PersonalizePolecat: Personalize outreach
- SequencePolecat: Create email sequences
- SMSPolecat: Draft SMS messages (requires human approval)
"""

from typing import Any
from uuid import UUID

from polecats.base import BasePolecat, register_polecat


@register_polecat
class ScoutPolecat(BasePolecat):
    """
    Scout and qualify leads based on ICP.

    Input: ICPBead with qualification criteria
    Output: Qualified LeadBeads
    """

    task_class = "lead_scout"
    content_type = "email"  # Not really content, but closest match
    rig = "sdr_hive"

    async def execute(self) -> str:
        """Analyze and qualify leads."""
        data = self.context.bead_data

        # Get ICP criteria from config or related Beads
        icp = self.config.get("icp", {})

        prompt = f"""Analyze this lead against our ICP criteria:

Lead Information:
- Name: {data.get('first_name', '')} {data.get('last_name', '')}
- Title: {data.get('title', 'Unknown')}
- Company: {data.get('company_name', 'Unknown')}
- Industry: {data.get('industry', 'Unknown')}
- Company Size: {data.get('company_size', 'Unknown')}

ICP Criteria:
- Target Industries: {icp.get('industries', ['Not specified'])}
- Target Company Sizes: {icp.get('company_sizes', ['Not specified'])}
- Target Job Titles: {icp.get('job_titles', ['Not specified'])}
- Target Seniority: {icp.get('seniority_levels', ['Not specified'])}

Analyze and output as JSON:
{{
    "qualified": true/false,
    "icp_match_score": 0-100,
    "matching_criteria": ["criterion1", "criterion2"],
    "gaps": ["gap1", "gap2"],
    "recommended_approach": "Description of recommended outreach approach",
    "priority": "high/medium/low"
}}

Output only valid JSON:
"""

        result = await self.call_neurometric(prompt)
        return result

    def _get_bead_type(self) -> str:
        return "lead"


@register_polecat
class EnrichPolecat(BasePolecat):
    """
    Enrich lead data with additional information.

    Input: LeadBead with basic info
    Output: Updated LeadBead with enrichment_data
    """

    task_class = "lead_enrich"
    content_type = "email"
    rig = "sdr_hive"

    async def execute(self) -> str:
        """Enrich lead data."""
        data = self.context.bead_data

        prompt = f"""Based on this lead information, suggest enrichment data and talking points:

Lead:
- Name: {data.get('first_name', '')} {data.get('last_name', '')}
- Title: {data.get('title', 'Unknown')}
- Company: {data.get('company_name', 'Unknown')}
- LinkedIn: {data.get('linkedin_url', 'Not provided')}
- Industry: {data.get('industry', 'Unknown')}

Generate enrichment insights as JSON:
{{
    "company_insights": {{
        "likely_challenges": ["challenge1", "challenge2"],
        "recent_news_topics": ["topic1", "topic2"],
        "tech_stack_hints": ["tech1", "tech2"]
    }},
    "person_insights": {{
        "likely_responsibilities": ["resp1", "resp2"],
        "career_progression_hints": "Description",
        "communication_style_hints": "formal/casual/technical"
    }},
    "outreach_angles": [
        {{
            "angle": "Description of angle",
            "hook": "Opening line suggestion",
            "relevance": "Why this matters to them"
        }}
    ],
    "questions_to_research": ["question1", "question2"]
}}

Output only valid JSON:
"""

        result = await self.call_neurometric(prompt)
        return result

    def _get_bead_type(self) -> str:
        return "lead"


@register_polecat
class PersonalizePolecat(BasePolecat):
    """
    Personalize outreach email for a specific lead.

    Input: LeadBead with enrichment data
    Output: Personalized email content
    """

    task_class = "email_personalization"
    content_type = "email"
    rig = "sdr_hive"

    async def execute(self) -> str:
        """Generate personalized email."""
        data = self.context.bead_data
        enrichment = data.get("enrichment_data", {})

        template = self.config.get("email_template", "")
        value_prop = self.config.get("value_proposition", "")

        prompt = f"""Write a personalized cold email for this lead:

Lead:
- Name: {data.get('first_name', '')} {data.get('last_name', '')}
- Title: {data.get('title', 'Unknown')}
- Company: {data.get('company_name', 'Unknown')}
- Industry: {data.get('industry', 'Unknown')}

Enrichment Data:
{enrichment}

Value Proposition: {value_prop}

{"Base Template: " + template if template else ""}

Requirements:
1. Personalize the opening based on their role/company
2. Keep it under 150 words
3. One clear call-to-action
4. Professional but conversational tone
5. No spam trigger words

Generate as JSON:
{{
    "subject_line": "Personalized subject",
    "email_body": "Full email text",
    "personalization_notes": "What was personalized and why"
}}

Output only valid JSON:
"""

        result = await self.call_neurometric(prompt)
        return result

    def _get_bead_type(self) -> str:
        return "lead"


@register_polecat
class SequencePolecat(BasePolecat):
    """
    Create a multi-touch email sequence.

    Input: Campaign parameters and ICP
    Output: Full email sequence with multiple touchpoints
    """

    task_class = "email_sequence"
    content_type = "email"
    rig = "sdr_hive"

    async def execute(self) -> str:
        """Generate email sequence."""
        data = self.context.bead_data

        touchpoints = self.config.get("touchpoints", 5)
        cadence = self.config.get("cadence", "2-3-4-5 days")
        goal = data.get("goal", "book a meeting")

        prompt = f"""Create a {touchpoints}-touch cold email sequence:

Campaign Goal: {goal}
Sequence Cadence: {cadence}

Target:
- Industry: {self.config.get('target_industry', 'B2B SaaS')}
- Titles: {self.config.get('target_titles', ['VP', 'Director'])}

Generate sequence as JSON:
{{
    "sequence_name": "Name",
    "total_touchpoints": {touchpoints},
    "emails": [
        {{
            "touchpoint": 1,
            "days_after_previous": 0,
            "subject_line": "Subject",
            "body": "Email body",
            "purpose": "Initial outreach",
            "cta": "Call to action"
        }}
    ],
    "exit_criteria": "When to stop sequence",
    "reply_handling": "How to handle different reply types"
}}

Output only valid JSON:
"""

        result = await self.call_neurometric(prompt)
        return result

    def _get_bead_type(self) -> str:
        return "campaign"


@register_polecat
class SMSPolecat(BasePolecat):
    """
    Draft SMS messages for The Wire.

    IMPORTANT: All SMS output ALWAYS requires human approval.
    Never send SMS automatically.

    Input: LeadBead with context
    Output: SMS draft for human review
    """

    task_class = "sms_draft"
    content_type = "social"  # SMS is similar to social in character limits
    rig = "sdr_hive"

    # SMS always requires approval
    always_requires_approval = True

    async def execute(self) -> str:
        """Draft SMS message."""
        data = self.context.bead_data

        context = self.config.get("context", "")
        relationship = self.config.get("relationship_stage", "initial")

        prompt = f"""Draft an SMS message for this lead:

Lead:
- Name: {data.get('first_name', '')}
- Company: {data.get('company_name', '')}
- Relationship Stage: {relationship}
- Context: {context}

Requirements:
1. Maximum 160 characters
2. Personal but professional
3. Clear purpose
4. Easy to respond to
5. No spam language

Generate as JSON:
{{
    "sms_text": "The SMS message",
    "character_count": 123,
    "purpose": "Why this message",
    "expected_response": "What we hope they'll do",
    "follow_up_if_no_response": "Next step"
}}

Output only valid JSON:
"""

        result = await self.call_neurometric(prompt)
        return result

    def _get_bead_type(self) -> str:
        return "lead"
