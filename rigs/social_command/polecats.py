"""
Social Command Polecats - Social media management.

Polecats:
- DraftTweetPolecat: Draft Twitter/X posts
- DraftLinkedInPolecat: Draft LinkedIn posts
- DraftThreadsPolecat: Draft Threads posts
- EngagementPolecat: Draft engagement responses
- HashtagResearchPolecat: Research relevant hashtags
- CrossPostAdaptPolecat: Adapt content across platforms
"""

from typing import Any

from polecats.base import BasePolecat, register_polecat


@register_polecat
class DraftTweetPolecat(BasePolecat):
    """Draft Twitter/X posts."""

    task_class = "draft_tweet"
    content_type = "social"
    rig = "social_command"

    async def execute(self) -> str:
        """Generate tweet drafts."""
        data = self.context.bead_data
        topic = self.config.get("topic", data.get("title", ""))
        tone = self.config.get("tone", "professional")
        include_cta = self.config.get("include_cta", True)

        prompt = f"""Write tweet variations for:

Topic: {topic}
Tone: {tone}
Include CTA: {include_cta}

Content Context:
{data.get('content_draft', '')[:1000] if data.get('content_draft') else 'No context provided'}

Generate 3 tweet variations as JSON:
{{
    "tweets": [
        {{
            "text": "Tweet text (280 chars max)",
            "character_count": 123,
            "hashtags": ["tag1", "tag2"],
            "hook_type": "question/statement/statistic/etc",
            "best_time": "morning/afternoon/evening"
        }}
    ],
    "thread_suggestion": {{
        "recommended": true/false,
        "thread_outline": ["Tweet 1 idea", "Tweet 2 idea"]
    }}
}}

Output only valid JSON:
"""
        return await self.call_neurometric(prompt)

    def _get_bead_type(self) -> str:
        return "asset"


@register_polecat
class DraftLinkedInPolecat(BasePolecat):
    """Draft LinkedIn posts."""

    task_class = "draft_linkedin"
    content_type = "social"
    rig = "social_command"

    async def execute(self) -> str:
        """Generate LinkedIn post."""
        data = self.context.bead_data
        topic = self.config.get("topic", data.get("title", ""))
        post_type = self.config.get("post_type", "thought_leadership")

        prompt = f"""Write a LinkedIn post:

Topic: {topic}
Post Type: {post_type}

Content Context:
{data.get('content_draft', '')[:1500] if data.get('content_draft') else 'No context'}

LinkedIn best practices:
- Hook in first line (before "see more")
- Use line breaks for readability
- 1000-1500 characters ideal
- End with engagement prompt

Generate as JSON:
{{
    "post_text": "Full LinkedIn post",
    "character_count": 1234,
    "hashtags": ["tag1", "tag2", "tag3"],
    "hook": "The first line/hook",
    "engagement_question": "Question to drive comments",
    "best_day": "Tuesday/Wednesday/Thursday"
}}

Output only valid JSON:
"""
        return await self.call_neurometric(prompt)

    def _get_bead_type(self) -> str:
        return "asset"


@register_polecat
class DraftThreadsPolecat(BasePolecat):
    """Draft Threads posts."""

    task_class = "draft_threads"
    content_type = "social"
    rig = "social_command"

    async def execute(self) -> str:
        """Generate Threads post."""
        data = self.context.bead_data
        topic = self.config.get("topic", data.get("title", ""))

        prompt = f"""Write a Threads post:

Topic: {topic}
Content: {data.get('content_draft', '')[:1000] if data.get('content_draft') else 'No context'}

Threads characteristics:
- Max 500 characters
- More conversational than Twitter
- Can be longer-form than tweets
- Less formal hashtag usage

Generate as JSON:
{{
    "post_text": "Threads post text",
    "character_count": 234,
    "tone": "conversational/informative/humorous",
    "engagement_potential": "high/medium/low"
}}

Output only valid JSON:
"""
        return await self.call_neurometric(prompt)

    def _get_bead_type(self) -> str:
        return "asset"


@register_polecat
class EngagementPolecat(BasePolecat):
    """Draft responses for social engagement."""

    task_class = "engagement_response"
    content_type = "social"
    rig = "social_command"

    async def execute(self) -> str:
        """Generate engagement responses."""
        original_post = self.config.get("original_post", "")
        engagement_type = self.config.get("type", "comment")
        platform = self.config.get("platform", "linkedin")

        prompt = f"""Draft a {engagement_type} response:

Original Post:
{original_post}

Platform: {platform}
Engagement Type: {engagement_type}

Guidelines:
- Be helpful and add value
- Don't be promotional
- Be conversational
- Keep it concise

Generate as JSON:
{{
    "response_text": "Your response",
    "character_count": 123,
    "adds_value": true/false,
    "follow_up_opportunity": "Description of potential follow-up"
}}

Output only valid JSON:
"""
        return await self.call_neurometric(prompt)

    def _get_bead_type(self) -> str:
        return "asset"


@register_polecat
class HashtagResearchPolecat(BasePolecat):
    """Research relevant hashtags for content."""

    task_class = "hashtag_research"
    content_type = "social"
    rig = "social_command"

    async def execute(self) -> str:
        """Research hashtags."""
        data = self.context.bead_data
        topic = self.config.get("topic", data.get("title", ""))
        platform = self.config.get("platform", "all")

        prompt = f"""Research hashtags for:

Topic: {topic}
Primary Platform: {platform}

Provide hashtag recommendations as JSON:
{{
    "primary_hashtags": [
        {{"tag": "#hashtag", "reach": "high/medium/low", "competition": "high/medium/low"}}
    ],
    "niche_hashtags": [
        {{"tag": "#hashtag", "relevance": "high/medium"}}
    ],
    "trending_relevant": [
        {{"tag": "#hashtag", "trend_status": "rising/stable"}}
    ],
    "avoid": ["#hashtagstoavoid"],
    "platform_specific": {{
        "twitter": ["tag1", "tag2"],
        "linkedin": ["tag1", "tag2"],
        "instagram": ["tag1", "tag2"]
    }},
    "optimal_count": {{
        "twitter": 2,
        "linkedin": 3,
        "instagram": 8
    }}
}}

Output only valid JSON:
"""
        return await self.call_neurometric(prompt)

    def _get_bead_type(self) -> str:
        return "asset"


@register_polecat
class CrossPostAdaptPolecat(BasePolecat):
    """Adapt content for cross-platform posting."""

    task_class = "cross_post_adapt"
    content_type = "social"
    rig = "social_command"

    async def execute(self) -> str:
        """Adapt content across platforms."""
        data = self.context.bead_data
        source_content = data.get("content_draft") or data.get("content_final", "")
        source_platform = self.config.get("source_platform", "blog")

        prompt = f"""Adapt this content for all social platforms:

Source Platform: {source_platform}
Source Content:
{source_content[:2000]}

Generate platform-specific versions as JSON:
{{
    "twitter": {{
        "posts": [
            {{"text": "Tweet 1", "hashtags": ["tag1"]}}
        ],
        "thread": {{"needed": true/false, "tweets": ["t1", "t2"]}}
    }},
    "linkedin": {{
        "post": "LinkedIn version",
        "hashtags": ["tag1", "tag2"]
    }},
    "threads": {{
        "post": "Threads version"
    }},
    "adaptation_notes": "Key changes made for each platform"
}}

Output only valid JSON:
"""
        return await self.call_neurometric(prompt)

    def _get_bead_type(self) -> str:
        return "asset"
