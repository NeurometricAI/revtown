"""
Repo Watch Polecats - GitHub monitoring and developer content.

Polecats:
- RepoStargazerPolecat: Analyze stargazer trends
- IssueTrendPolecat: Analyze issue trends
- PRMentionPolecat: Find mentions in PRs
- ReadmeOptimizePolecat: Optimize README
- DevRelContentPolecat: Create developer content
- ChangelogPolecat: Generate changelog entries
"""

from typing import Any

from polecats.base import BasePolecat, register_polecat


@register_polecat
class RepoStargazerPolecat(BasePolecat):
    """Analyze GitHub stargazer trends and profiles."""

    task_class = "repo_stargazer"
    content_type = "blog"
    rig = "repo_watch"

    async def execute(self) -> str:
        """Analyze stargazer data."""
        data = self.context.bead_data

        stargazers = self.config.get("stargazers", [])
        time_period = self.config.get("time_period", "30 days")

        prompt = f"""Analyze GitHub stargazer data:

Repository: {self.config.get('repo_name', 'Unknown')}
Time Period: {time_period}

Recent Stargazers Sample:
{stargazers[:20]}

Analyze as JSON:
{{
    "growth_trend": "accelerating/stable/declining",
    "growth_rate": "X new stars per week",
    "notable_stargazers": [
        {{
            "username": "username",
            "significance": "Why notable (company, following, etc.)",
            "potential_action": "Reach out / monitor / etc."
        }}
    ],
    "geographic_distribution": ["Country1", "Country2"],
    "company_distribution": ["Company1", "Company2"],
    "developer_types": ["Type1", "Type2"],
    "correlation_events": "Any events that correlated with star spikes",
    "outreach_opportunities": [
        {{
            "target": "Who to reach out to",
            "reason": "Why",
            "suggested_approach": "How"
        }}
    ]
}}

Output only valid JSON:
"""
        return await self.call_neurometric(prompt)

    def _get_bead_type(self) -> str:
        return "asset"


@register_polecat
class IssueTrendPolecat(BasePolecat):
    """Analyze GitHub issue trends."""

    task_class = "issue_trend"
    content_type = "blog"
    rig = "repo_watch"

    async def execute(self) -> str:
        """Analyze issue trends."""
        issues = self.config.get("issues", [])
        repo_name = self.config.get("repo_name", "Unknown")

        prompt = f"""Analyze GitHub issue trends:

Repository: {repo_name}

Recent Issues:
{issues}

Analyze as JSON:
{{
    "volume_trend": "increasing/stable/decreasing",
    "response_time_trend": "improving/stable/worsening",
    "top_categories": [
        {{"category": "Category", "count": 10, "trend": "up/down"}}
    ],
    "feature_requests": [
        {{"feature": "Feature name", "demand_level": "high/medium", "occurrences": 5}}
    ],
    "pain_points": [
        {{"issue": "Issue description", "severity": "high/medium", "frequency": "common"}}
    ],
    "community_health_indicators": {{
        "contributor_engagement": "high/medium/low",
        "issue_resolution_rate": "good/fair/poor",
        "community_sentiment": "positive/mixed/negative"
    }},
    "product_insights": ["Insight for product team"],
    "content_opportunities": ["Content ideas based on issues"]
}}

Output only valid JSON:
"""
        return await self.call_neurometric(prompt)

    def _get_bead_type(self) -> str:
        return "asset"


@register_polecat
class PRMentionPolecat(BasePolecat):
    """Find and analyze PR mentions of the project."""

    task_class = "pr_mention"
    content_type = "blog"
    rig = "repo_watch"

    async def execute(self) -> str:
        """Find PR mentions."""
        mentions = self.config.get("mentions", [])
        project_name = self.config.get("project_name", "Unknown")

        prompt = f"""Analyze PR mentions of our project:

Project: {project_name}

Mentions Found:
{mentions}

Analyze as JSON:
{{
    "total_mentions": 42,
    "mention_trend": "increasing/stable/decreasing",
    "notable_repos": [
        {{
            "repo": "owner/repo",
            "stars": 1000,
            "context": "How they're using us",
            "opportunity": "Potential action"
        }}
    ],
    "integration_patterns": ["How people are integrating"],
    "common_use_cases": ["Use case 1", "Use case 2"],
    "ecosystem_position": "Where we sit in the ecosystem",
    "partnership_opportunities": [
        {{"project": "Project name", "reason": "Why partner"}}
    ],
    "content_opportunities": [
        {{"type": "blog/tutorial/case_study", "topic": "Topic idea"}}
    ]
}}

Output only valid JSON:
"""
        return await self.call_neurometric(prompt)

    def _get_bead_type(self) -> str:
        return "asset"


@register_polecat
class ReadmeOptimizePolecat(BasePolecat):
    """Optimize README for better engagement."""

    task_class = "readme_optimize"
    content_type = "blog"
    rig = "repo_watch"

    async def execute(self) -> str:
        """Optimize README."""
        current_readme = self.config.get("current_readme", "")
        project_type = self.config.get("project_type", "library")

        prompt = f"""Optimize this README:

Current README:
{current_readme[:3000]}

Project Type: {project_type}

Provide optimization suggestions as JSON:
{{
    "overall_score": 75,
    "sections_analysis": [
        {{
            "section": "Section name",
            "current_score": 70,
            "issues": ["Issue 1"],
            "suggestions": ["Suggestion 1"]
        }}
    ],
    "missing_sections": ["Section that should be added"],
    "badge_recommendations": ["Badges to add"],
    "quick_wins": ["Easy improvements"],
    "rewritten_sections": {{
        "hero": "Suggested hero section rewrite",
        "installation": "Suggested installation section"
    }},
    "seo_keywords": ["Keywords to include"],
    "comparison_to_top_repos": "How this compares to similar repos"
}}

Output only valid JSON:
"""
        return await self.call_neurometric(prompt)

    def _get_bead_type(self) -> str:
        return "asset"


@register_polecat
class DevRelContentPolecat(BasePolecat):
    """Create developer-focused content."""

    task_class = "devrel_content"
    content_type = "blog"
    rig = "repo_watch"

    async def execute(self) -> str:
        """Create developer content."""
        content_type = self.config.get("content_type", "tutorial")
        topic = self.config.get("topic", "")
        target_skill_level = self.config.get("skill_level", "intermediate")

        prompt = f"""Create developer content:

Content Type: {content_type}
Topic: {topic}
Target Skill Level: {target_skill_level}

Generate as JSON:
{{
    "title": "Content title",
    "type": "{content_type}",
    "estimated_read_time": "10 min",
    "outline": [
        {{"section": "Section name", "content_notes": "What to cover"}}
    ],
    "code_examples": [
        {{"language": "python", "description": "What this shows", "code": "Code snippet"}}
    ],
    "key_takeaways": ["Takeaway 1", "Takeaway 2"],
    "prerequisites": ["Prereq 1"],
    "next_steps": ["What to learn next"],
    "seo_keywords": ["keyword1", "keyword2"],
    "social_snippets": {{
        "twitter": "Tweet to promote",
        "linkedin": "LinkedIn post to promote"
    }}
}}

Output only valid JSON:
"""
        return await self.call_neurometric(prompt)

    def _get_bead_type(self) -> str:
        return "asset"


@register_polecat
class ChangelogPolecat(BasePolecat):
    """Generate changelog entries."""

    task_class = "changelog"
    content_type = "blog"
    rig = "repo_watch"

    async def execute(self) -> str:
        """Generate changelog."""
        commits = self.config.get("commits", [])
        version = self.config.get("version", "")
        previous_version = self.config.get("previous_version", "")

        prompt = f"""Generate changelog entry:

Version: {version}
Previous Version: {previous_version}

Commits:
{commits}

Generate changelog as JSON:
{{
    "version": "{version}",
    "release_date": "YYYY-MM-DD",
    "highlights": ["Major highlight 1", "Major highlight 2"],
    "sections": {{
        "added": ["New feature 1"],
        "changed": ["Change 1"],
        "deprecated": ["Deprecated feature"],
        "removed": ["Removed feature"],
        "fixed": ["Bug fix 1"],
        "security": ["Security fix"]
    }},
    "breaking_changes": [
        {{
            "change": "Description",
            "migration": "How to migrate"
        }}
    ],
    "contributors": ["@username1", "@username2"],
    "full_changelog_link": "Link format",
    "marketing_summary": "One paragraph for announcement"
}}

Output only valid JSON:
"""
        return await self.call_neurometric(prompt)

    def _get_bead_type(self) -> str:
        return "asset"
