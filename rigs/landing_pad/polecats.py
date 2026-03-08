"""
Landing Pad Polecats - Landing pages and A/B testing.

Polecats:
- LandingPageDraftPolecat: Create landing page content
- LandingPageVariantPolecat: Create A/B test variants
- EmailVariantPolecat: Create email A/B variants
- WinnerDeclarePolecat: Analyze and declare test winners
"""

from typing import Any

from polecats.base import BasePolecat, register_polecat


@register_polecat
class LandingPageDraftPolecat(BasePolecat):
    """Create landing page content."""

    task_class = "landing_page_draft"
    content_type = "landing_page"
    rig = "landing_pad"

    async def execute(self) -> str:
        """Generate landing page content."""
        data = self.context.bead_data

        page_type = self.config.get("page_type", "product")
        target_audience = self.config.get("target_audience", "")
        primary_cta = self.config.get("primary_cta", "Get Started")

        prompt = f"""Create landing page content:

Page Type: {page_type}
Target Audience: {target_audience}
Primary CTA: {primary_cta}

Campaign Context:
{data.get('goal', 'No goal specified')}

Generate landing page content as JSON:
{{
    "headline": "Main headline (8 words max)",
    "subheadline": "Supporting subheadline",
    "hero_section": {{
        "headline": "Hero headline",
        "subtext": "Hero supporting text",
        "cta_text": "CTA button text",
        "social_proof": "Brief social proof statement"
    }},
    "value_props": [
        {{
            "headline": "Value prop headline",
            "description": "Value prop description",
            "icon_suggestion": "Icon type"
        }}
    ],
    "features_section": {{
        "headline": "Features section headline",
        "features": [
            {{"name": "Feature", "description": "Description"}}
        ]
    }},
    "social_proof_section": {{
        "headline": "Social proof headline",
        "testimonial_prompt": "Type of testimonial to include",
        "logos_suggestion": "Types of logos to include"
    }},
    "cta_section": {{
        "headline": "Final CTA headline",
        "subtext": "Supporting text",
        "cta_text": "Button text",
        "urgency_element": "Optional urgency"
    }},
    "meta_title": "SEO title",
    "meta_description": "SEO description"
}}

Output only valid JSON:
"""
        return await self.call_neurometric(prompt)

    def _get_bead_type(self) -> str:
        return "asset"


@register_polecat
class LandingPageVariantPolecat(BasePolecat):
    """Create A/B test variants for landing pages."""

    task_class = "landing_page_variant"
    content_type = "landing_page"
    rig = "landing_pad"

    async def execute(self) -> str:
        """Generate landing page variants."""
        data = self.context.bead_data

        control_content = data.get("content_final") or data.get("content_draft", "")
        test_element = self.config.get("test_element", "headline")
        hypothesis = self.config.get("hypothesis", "")

        prompt = f"""Create A/B test variants for landing page:

Control Version:
{control_content[:2000]}

Element to Test: {test_element}
Hypothesis: {hypothesis}

Generate 2-3 variants as JSON:
{{
    "test_element": "{test_element}",
    "hypothesis": "{hypothesis}",
    "variants": [
        {{
            "name": "Variant A",
            "changes": {{
                "{test_element}": "New version"
            }},
            "rationale": "Why this might perform better",
            "expected_impact": "high/medium/low"
        }}
    ],
    "recommended_traffic_split": {{"control": 50, "variant_a": 25, "variant_b": 25}},
    "min_sample_size": 1000,
    "success_metric": "conversion_rate/click_through/etc"
}}

Output only valid JSON:
"""
        return await self.call_neurometric(prompt)

    def _get_bead_type(self) -> str:
        return "asset"


@register_polecat
class EmailVariantPolecat(BasePolecat):
    """Create A/B test variants for emails."""

    task_class = "subject_line_ab"
    content_type = "email"
    rig = "landing_pad"

    async def execute(self) -> str:
        """Generate email variants."""
        data = self.context.bead_data

        control_subject = self.config.get("control_subject", "")
        control_body = self.config.get("control_body", "")
        test_element = self.config.get("test_element", "subject_line")

        prompt = f"""Create A/B test variants for email:

Control Subject: {control_subject}
Control Body Preview: {control_body[:500]}

Element to Test: {test_element}

Generate variants as JSON:
{{
    "test_element": "{test_element}",
    "variants": [
        {{
            "name": "Variant A",
            "subject_line": "New subject line",
            "body_changes": "Description of body changes if any",
            "hypothesis": "Why this might perform better"
        }},
        {{
            "name": "Variant B",
            "subject_line": "Another subject line",
            "body_changes": "Description of body changes if any",
            "hypothesis": "Why this might perform better"
        }}
    ],
    "recommended_test_size": 1000,
    "success_metric": "open_rate/click_rate/reply_rate",
    "statistical_confidence_target": 0.95
}}

Output only valid JSON:
"""
        return await self.call_neurometric(prompt)

    def _get_bead_type(self) -> str:
        return "test"


@register_polecat
class WinnerDeclarePolecat(BasePolecat):
    """
    Analyze A/B test results and declare winner.

    Note: Winner declarations require human approval.
    """

    task_class = "statistical_significance"
    content_type = "blog"  # Analysis output
    rig = "landing_pad"

    # Test winners require approval before promotion
    always_requires_approval = True

    async def execute(self) -> str:
        """Analyze test results and recommend winner."""
        data = self.context.bead_data

        metrics = data.get("metrics", {})
        hypothesis = data.get("hypothesis", "")
        min_sample = data.get("min_sample_size", 100)

        prompt = f"""Analyze A/B test results and determine winner:

Test Name: {data.get('name', 'Unknown')}
Hypothesis: {hypothesis}
Minimum Sample Size: {min_sample}

Results:
{metrics}

Analyze as JSON:
{{
    "analysis_summary": "Brief summary of results",
    "statistical_significance": {{
        "achieved": true/false,
        "confidence_level": 0.95,
        "p_value": 0.03
    }},
    "winner": {{
        "variant": "control/variant_a/variant_b/no_winner",
        "improvement": "15% improvement in conversion rate",
        "confidence": "high/medium/low"
    }},
    "recommendation": "Promote variant X / Continue testing / End test",
    "insights": [
        "Insight about what drove results"
    ],
    "caveats": [
        "Any caveats or concerns"
    ],
    "next_test_suggestions": [
        "Ideas for follow-up tests"
    ]
}}

Output only valid JSON:
"""
        return await self.call_neurometric(prompt)

    def _get_bead_type(self) -> str:
        return "test"
