"""
Content Factory Polecats - Inbound content creation.

Polecats:
- BlogDraftPolecat: Create blog post drafts
- SEOMetaPolecat: Generate SEO metadata
- SocialSnippetPolecat: Create social media snippets from content
- ContentCalendarPolecat: Plan content calendar
- ImageBriefPolecat: Create image/visual briefs
"""

from typing import Any
from uuid import UUID

from polecats.base import BasePolecat, register_polecat


@register_polecat
class BlogDraftPolecat(BasePolecat):
    """
    Create a blog post draft.

    Input: AssetBead with topic, keywords, and target audience
    Output: Updated AssetBead with content_draft
    """

    task_class = "blog_draft"
    content_type = "blog"
    rig = "content_factory"

    async def execute(self) -> str:
        """Generate a blog post draft."""
        data = self.context.bead_data

        topic = data.get("title") or data.get("topic", "")
        keywords = data.get("keywords", [])
        target_audience = self.config.get("target_audience", "business professionals")
        word_count = self.config.get("word_count", 1200)

        prompt = f"""Write a blog post on the following topic:

Topic: {topic}

Target Audience: {target_audience}
Target Word Count: {word_count}
Keywords to include: {', '.join(keywords) if keywords else 'None specified'}

Requirements:
1. Start with a compelling hook
2. Use clear, scannable formatting with headers
3. Include practical, actionable insights
4. End with a clear call-to-action
5. Maintain a professional but approachable tone

Write the complete blog post:
"""

        content = await self.call_neurometric(prompt)
        return content

    def _get_bead_type(self) -> str:
        return "asset"


@register_polecat
class SEOMetaPolecat(BasePolecat):
    """
    Generate SEO metadata for content.

    Input: AssetBead with content
    Output: Updated AssetBead with meta_title, meta_description, keywords
    """

    task_class = "seo_meta"
    content_type = "blog"
    rig = "content_factory"

    async def execute(self) -> str:
        """Generate SEO metadata."""
        data = self.context.bead_data

        content = data.get("content_draft") or data.get("content_final", "")
        title = data.get("title", "")

        prompt = f"""Analyze this content and generate SEO metadata:

Title: {title}

Content:
{content[:3000]}

Generate the following as JSON:
{{
    "meta_title": "SEO-optimized title (50-60 chars)",
    "meta_description": "Compelling description (150-160 chars)",
    "keywords": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"],
    "h1_suggestion": "Primary heading suggestion"
}}

Output only valid JSON:
"""

        result = await self.call_neurometric(prompt)
        return result

    def _get_bead_type(self) -> str:
        return "asset"


@register_polecat
class SocialSnippetPolecat(BasePolecat):
    """
    Create social media snippets from blog content.

    Input: AssetBead with blog content
    Output: Multiple social post variants
    """

    task_class = "social_snippet"
    content_type = "social"
    rig = "content_factory"

    async def execute(self) -> str:
        """Generate social media snippets."""
        data = self.context.bead_data

        content = data.get("content_draft") or data.get("content_final", "")
        title = data.get("title", "")

        prompt = f"""Create social media posts to promote this blog content:

Blog Title: {title}

Blog Content (excerpt):
{content[:2000]}

Generate posts for each platform as JSON:
{{
    "twitter": [
        {{"text": "Tweet 1 (280 chars max)", "hashtags": ["tag1", "tag2"]}},
        {{"text": "Tweet 2 (280 chars max)", "hashtags": ["tag1", "tag2"]}}
    ],
    "linkedin": {{
        "text": "LinkedIn post (1000-1500 chars)",
        "hashtags": ["tag1", "tag2", "tag3"]
    }},
    "threads": {{
        "text": "Threads post (500 chars max)"
    }}
}}

Make each post engaging and platform-appropriate. Output only valid JSON:
"""

        result = await self.call_neurometric(prompt)
        return result

    def _get_bead_type(self) -> str:
        return "asset"


@register_polecat
class ContentCalendarPolecat(BasePolecat):
    """
    Plan a content calendar based on campaign goals.

    Input: CampaignBead with goals and timeline
    Output: Structured content calendar
    """

    task_class = "content_calendar"
    content_type = "blog"
    rig = "content_factory"

    async def execute(self) -> str:
        """Generate a content calendar."""
        data = self.context.bead_data

        goal = data.get("goal", "")
        horizon_days = data.get("horizon_days", 30)
        keywords = self.config.get("focus_keywords", [])

        prompt = f"""Create a content calendar for the following campaign:

Campaign Goal: {goal}
Duration: {horizon_days} days
Focus Keywords: {', '.join(keywords) if keywords else 'Not specified'}

Generate a content calendar as JSON:
{{
    "content_pillars": ["pillar1", "pillar2", "pillar3"],
    "weekly_schedule": [
        {{
            "week": 1,
            "posts": [
                {{
                    "day": "Monday",
                    "type": "blog",
                    "topic": "Topic title",
                    "pillar": "pillar1",
                    "keywords": ["kw1", "kw2"]
                }}
            ]
        }}
    ],
    "total_pieces": 10,
    "cadence_notes": "Explanation of posting rhythm"
}}

Output only valid JSON:
"""

        result = await self.call_neurometric(prompt)
        return result

    def _get_bead_type(self) -> str:
        return "campaign"


@register_polecat
class ImageBriefPolecat(BasePolecat):
    """
    Create image/visual briefs for content.

    Input: AssetBead with content
    Output: Visual brief for designers or AI image generation
    """

    task_class = "image_brief"
    content_type = "blog"
    rig = "content_factory"

    async def execute(self) -> str:
        """Generate image briefs."""
        data = self.context.bead_data

        content = data.get("content_draft") or data.get("content_final", "")
        title = data.get("title", "")

        prompt = f"""Create image briefs for this blog content:

Title: {title}

Content:
{content[:2000]}

Generate image briefs as JSON:
{{
    "hero_image": {{
        "description": "Detailed description for hero image",
        "mood": "professional/playful/serious/etc",
        "colors": ["primary", "secondary"],
        "style": "photography/illustration/abstract",
        "dimensions": "1200x630"
    }},
    "inline_images": [
        {{
            "placement": "After section X",
            "description": "Image description",
            "type": "diagram/photo/illustration"
        }}
    ],
    "social_images": {{
        "twitter": "Description for Twitter card image",
        "linkedin": "Description for LinkedIn post image"
    }}
}}

Output only valid JSON:
"""

        result = await self.call_neurometric(prompt)
        return result

    def _get_bead_type(self) -> str:
        return "asset"
