"""
Intelligence Station Polecats - Competitor monitoring.

Polecats:
- CompetitorWebChangePolecat: Monitor competitor website changes
- CompetitorJobsPolecat: Analyze competitor job postings
- CompetitorSocialPolecat: Monitor competitor social activity
- CompetitorReviewPolecat: Analyze competitor reviews
- CompetitorPRPolecat: Monitor competitor PR/news
"""

from typing import Any

from polecats.base import BasePolecat, register_polecat


@register_polecat
class CompetitorWebChangePolecat(BasePolecat):
    """Monitor and analyze competitor website changes."""

    task_class = "competitor_analysis"
    content_type = "blog"  # Analysis content
    rig = "intelligence_station"

    async def execute(self) -> str:
        """Analyze competitor website changes."""
        data = self.context.bead_data

        current_snapshot = self.config.get("current_snapshot", "")
        previous_snapshot = self.config.get("previous_snapshot", "")

        prompt = f"""Analyze changes to competitor website:

Competitor: {data.get('name', 'Unknown')}
Domain: {data.get('domain', 'Unknown')}

Previous Snapshot:
{previous_snapshot[:2000]}

Current Snapshot:
{current_snapshot[:2000]}

Analyze changes as JSON:
{{
    "significant_changes": [
        {{
            "type": "messaging/pricing/feature/design",
            "description": "What changed",
            "strategic_implication": "What this might mean"
        }}
    ],
    "new_messaging": ["New tagline or positioning"],
    "new_features": ["New features mentioned"],
    "pricing_changes": {{
        "detected": true/false,
        "details": "Description"
    }},
    "urgency": "high/medium/low",
    "recommended_actions": ["action1", "action2"],
    "mayor_alert": true/false
}}

Output only valid JSON:
"""
        return await self.call_neurometric(prompt)

    def _get_bead_type(self) -> str:
        return "competitor"


@register_polecat
class CompetitorJobsPolecat(BasePolecat):
    """Analyze competitor job postings for intelligence."""

    task_class = "competitor_analysis"
    content_type = "blog"
    rig = "intelligence_station"

    async def execute(self) -> str:
        """Analyze competitor job postings."""
        data = self.context.bead_data
        job_postings = self.config.get("job_postings", [])

        prompt = f"""Analyze competitor job postings:

Competitor: {data.get('name', 'Unknown')}

Recent Job Postings:
{job_postings}

Extract intelligence as JSON:
{{
    "hiring_trends": {{
        "departments_growing": ["Engineering", "Sales"],
        "new_roles": ["Role not seen before"],
        "volume_change": "increasing/stable/decreasing"
    }},
    "tech_stack_signals": ["Technology mentioned in job posts"],
    "product_hints": [
        {{
            "signal": "What the job post reveals",
            "interpretation": "What this might mean for their product"
        }}
    ],
    "expansion_signals": {{
        "new_markets": ["Market1"],
        "new_segments": ["Segment1"]
    }},
    "strategic_implications": "Summary of what this means",
    "recommended_actions": ["action1"]
}}

Output only valid JSON:
"""
        return await self.call_neurometric(prompt)

    def _get_bead_type(self) -> str:
        return "competitor"


@register_polecat
class CompetitorSocialPolecat(BasePolecat):
    """Monitor competitor social media activity."""

    task_class = "competitor_analysis"
    content_type = "social"
    rig = "intelligence_station"

    async def execute(self) -> str:
        """Analyze competitor social activity."""
        data = self.context.bead_data
        social_posts = self.config.get("recent_posts", [])

        prompt = f"""Analyze competitor social media activity:

Competitor: {data.get('name', 'Unknown')}

Recent Posts:
{social_posts}

Analyze as JSON:
{{
    "posting_frequency": "X posts per week",
    "content_themes": ["theme1", "theme2"],
    "engagement_trends": "increasing/stable/decreasing",
    "top_performing_content": [
        {{"type": "Type", "topic": "Topic", "engagement": "High/Medium"}}
    ],
    "messaging_changes": ["Notable shifts in messaging"],
    "campaign_detection": {{
        "active_campaign": true/false,
        "campaign_theme": "Description",
        "campaign_channels": ["Twitter", "LinkedIn"]
    }},
    "competitive_mentions": ["Mentions of us or other competitors"],
    "actionable_insights": ["insight1", "insight2"]
}}

Output only valid JSON:
"""
        return await self.call_neurometric(prompt)

    def _get_bead_type(self) -> str:
        return "competitor"


@register_polecat
class CompetitorReviewPolecat(BasePolecat):
    """Analyze competitor reviews (G2, Capterra, etc.)."""

    task_class = "competitor_analysis"
    content_type = "blog"
    rig = "intelligence_station"

    async def execute(self) -> str:
        """Analyze competitor reviews."""
        data = self.context.bead_data
        reviews = self.config.get("reviews", [])
        platform = self.config.get("platform", "G2")

        prompt = f"""Analyze competitor reviews:

Competitor: {data.get('name', 'Unknown')}
Review Platform: {platform}

Recent Reviews:
{reviews}

Analyze as JSON:
{{
    "overall_sentiment": "positive/mixed/negative",
    "rating_trend": "improving/stable/declining",
    "strengths_mentioned": [
        {{"strength": "Feature/aspect", "frequency": "common/occasional"}}
    ],
    "weaknesses_mentioned": [
        {{"weakness": "Issue", "frequency": "common/occasional", "opportunity": "How we can capitalize"}}
    ],
    "feature_requests": ["Features customers want"],
    "comparison_mentions": [
        {{"vs_competitor": "Name", "sentiment": "favorable/unfavorable"}}
    ],
    "sales_opportunities": ["How to use this in sales"],
    "product_opportunities": ["Gaps we could fill"],
    "marketing_angles": ["Messaging opportunities"]
}}

Output only valid JSON:
"""
        return await self.call_neurometric(prompt)

    def _get_bead_type(self) -> str:
        return "competitor"


@register_polecat
class CompetitorPRPolecat(BasePolecat):
    """Monitor competitor PR and news mentions."""

    task_class = "competitor_analysis"
    content_type = "pr_pitch"
    rig = "intelligence_station"

    async def execute(self) -> str:
        """Analyze competitor PR/news."""
        data = self.context.bead_data
        news_items = self.config.get("news_items", [])

        prompt = f"""Analyze competitor news and PR:

Competitor: {data.get('name', 'Unknown')}

Recent News:
{news_items}

Analyze as JSON:
{{
    "announcements": [
        {{
            "type": "funding/product/partnership/hire/other",
            "summary": "Brief summary",
            "significance": "high/medium/low",
            "our_response": "How we should respond"
        }}
    ],
    "funding_news": {{
        "detected": true/false,
        "amount": "Amount if known",
        "investors": ["Investor names"],
        "implications": "What this means"
    }},
    "product_launches": ["Products announced"],
    "partnerships": ["Partnerships announced"],
    "exec_changes": ["Executive changes"],
    "pr_strategy_insights": "What their PR strategy seems to be",
    "counter_narrative_opportunities": ["Where we can insert ourselves"],
    "urgent_response_needed": true/false
}}

Output only valid JSON:
"""
        return await self.call_neurometric(prompt)

    def _get_bead_type(self) -> str:
        return "competitor"
