"""
Press Room Polecats - PR and journalist outreach.

Polecats:
- JournalistResearchPolecat: Research journalists for pitching
- PitchDraftPolecat: Draft PR pitches (ALWAYS requires approval)
- PRWireDraftPolecat: Draft press releases
- HAROWatcherPolecat: Monitor and respond to HARO queries
- EmbargoPolecat: Manage embargo communications
"""

from typing import Any
from uuid import UUID

from polecats.base import BasePolecat, register_polecat


@register_polecat
class JournalistResearchPolecat(BasePolecat):
    """
    Research journalists for PR outreach.

    Input: Topic/angle to pitch
    Output: JournalistBead with research data
    """

    task_class = "journalist_research"
    content_type = "pr_pitch"
    rig = "press_room"

    async def execute(self) -> str:
        """Research journalist."""
        data = self.context.bead_data

        prompt = f"""Research this journalist for a PR pitch:

Journalist:
- Name: {data.get('name', 'Unknown')}
- Publication: {data.get('publication', 'Unknown')}
- Beats: {data.get('beats', [])}
- Twitter: {data.get('twitter_handle', 'Not provided')}

Analyze and provide as JSON:
{{
    "writing_style": "Description of their typical style",
    "recent_topics": ["topic1", "topic2", "topic3"],
    "preferred_pitch_style": "direct/story-based/data-driven",
    "best_angles": [
        {{
            "angle": "Angle description",
            "why_relevant": "Why this would interest them"
        }}
    ],
    "avoid": ["Things to avoid in pitch"],
    "timing_notes": "Best times/days to pitch",
    "relationship_tips": "How to build rapport"
}}

Output only valid JSON:
"""

        result = await self.call_neurometric(prompt)
        return result

    def _get_bead_type(self) -> str:
        return "journalist"


@register_polecat
class PitchDraftPolecat(BasePolecat):
    """
    Draft PR pitch for a journalist.

    IMPORTANT: PR pitches ALWAYS require human approval - no exceptions.

    Input: JournalistBead + story angle
    Output: Pitch draft for review
    """

    task_class = "pr_pitch_draft"
    content_type = "pr_pitch"
    rig = "press_room"

    # PR pitches always require approval
    always_requires_approval = True

    async def execute(self) -> str:
        """Draft PR pitch."""
        data = self.context.bead_data

        story_angle = self.config.get("story_angle", "")
        key_data = self.config.get("key_data_points", [])
        embargo_date = self.config.get("embargo_date", None)

        prompt = f"""Draft a PR pitch email for this journalist:

Journalist:
- Name: {data.get('name', 'Unknown')}
- Publication: {data.get('publication', 'Unknown')}
- Beats: {data.get('beats', [])}

Story Angle: {story_angle}
Key Data Points: {key_data}
{"Embargo Date: " + embargo_date if embargo_date else "No embargo"}

Requirements:
1. Follow AP Style
2. Lead with the news hook
3. Include one compelling data point
4. Keep to 150 words or less
5. Clear call-to-action (interview, exclusive, etc.)
6. Professional but personalized tone
7. No hallucinated quotes or statistics

Generate as JSON:
{{
    "subject_line": "Pitch subject",
    "pitch_body": "Full pitch text",
    "key_hook": "The main hook",
    "data_cited": ["Data point 1"],
    "cta": "What you're asking for",
    "follow_up_plan": "When/how to follow up"
}}

Output only valid JSON:
"""

        result = await self.call_neurometric(prompt)
        return result

    def _get_bead_type(self) -> str:
        return "journalist"


@register_polecat
class PRWireDraftPolecat(BasePolecat):
    """
    Draft a press release for wire distribution.

    Input: News/announcement details
    Output: Press release draft
    """

    task_class = "pr_wire_draft"
    content_type = "pr_pitch"
    rig = "press_room"

    async def execute(self) -> str:
        """Draft press release."""
        data = self.context.bead_data

        announcement = self.config.get("announcement", "")
        key_quotes = self.config.get("quotes", [])
        boilerplate = self.config.get("company_boilerplate", "")

        prompt = f"""Write a press release:

Announcement: {announcement}

Campaign Context:
- Name: {data.get('name', '')}
- Goal: {data.get('goal', '')}

Key Quotes to Include: {key_quotes}
Company Boilerplate: {boilerplate}

Follow standard press release format:
1. Dateline and headline
2. Subheadline
3. Opening paragraph with who/what/when/where/why
4. Supporting details and quotes
5. Boilerplate
6. Media contact

Output the full press release text:
"""

        result = await self.call_neurometric(prompt)
        return result

    def _get_bead_type(self) -> str:
        return "campaign"


@register_polecat
class HAROWatcherPolecat(BasePolecat):
    """
    Analyze HARO (Help A Reporter Out) queries for relevance.

    Input: HARO query content
    Output: Relevance analysis and response draft
    """

    task_class = "haro_analysis"
    content_type = "pr_pitch"
    rig = "press_room"

    async def execute(self) -> str:
        """Analyze HARO query."""
        query = self.config.get("haro_query", "")
        expertise = self.config.get("company_expertise", [])
        spokespeople = self.config.get("spokespeople", [])

        prompt = f"""Analyze this HARO query for response opportunity:

HARO Query:
{query}

Our Expertise Areas: {expertise}
Available Spokespeople: {spokespeople}

Analyze as JSON:
{{
    "relevant": true/false,
    "relevance_score": 0-100,
    "matching_expertise": ["area1", "area2"],
    "recommended_spokesperson": "Name and title",
    "angle_suggestion": "How to angle our response",
    "response_priority": "high/medium/low",
    "deadline_urgency": "Description",
    "draft_response": "If relevant, draft response (200 words max)"
}}

Output only valid JSON:
"""

        result = await self.call_neurometric(prompt)
        return result

    def _get_bead_type(self) -> str:
        return "asset"


@register_polecat
class EmbargoPolecat(BasePolecat):
    """
    Manage embargo communications.

    Input: Embargo details and journalist list
    Output: Embargo communication plan
    """

    task_class = "embargo_management"
    content_type = "pr_pitch"
    rig = "press_room"

    # Embargo comms require careful handling
    always_requires_approval = True

    async def execute(self) -> str:
        """Create embargo communications."""
        data = self.context.bead_data

        embargo_date = self.config.get("embargo_date", "")
        announcement = self.config.get("announcement", "")

        prompt = f"""Create embargo communication plan:

Embargo Lift Date: {embargo_date}
Announcement: {announcement}

Journalist:
- Name: {data.get('name', 'Unknown')}
- Publication: {data.get('publication', 'Unknown')}
- Tier: {data.get('publication_tier', 'tier2')}

Generate as JSON:
{{
    "embargo_email": {{
        "subject": "Embargo subject line",
        "body": "Embargo briefing email",
        "embargo_terms": "Clear embargo terms"
    }},
    "pre_briefing_script": "Talking points for call",
    "follow_up_schedule": [
        {{"days_before_lift": 3, "action": "Action to take"}},
        {{"days_before_lift": 1, "action": "Action to take"}}
    ],
    "lift_day_plan": "What to do on lift day",
    "breach_response": "What to do if embargo is broken"
}}

Output only valid JSON:
"""

        result = await self.call_neurometric(prompt)
        return result

    def _get_bead_type(self) -> str:
        return "journalist"
