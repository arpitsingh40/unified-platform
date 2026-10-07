import pytest
from cognition import classify_decision, identity_block, cognition_block


# Decision category classifier tests
class TestClassifyDecision:
    # Deal negotiation phrases map correctly
    def test_deal_negotiation(self):
        assert classify_decision("Should I take this distributor deal?") == "deal_negotiation"
        assert classify_decision("Negotiating terms with a vendor") == "deal_negotiation"

    # Hiring and firing phrases map to people_team
    def test_people_team(self):
        assert classify_decision("Should I hire a CTO?") == "people_team"
        assert classify_decision("Firing an underperforming employee") == "people_team"

    # Customer acquisition phrases map to growth_marketing
    def test_growth_marketing(self):
        assert classify_decision("How do I get more customers?") == "growth_marketing"
        assert classify_decision("Instagram ads ROI dropped") == "growth_marketing"

    # Pricing phrase maps to pricing_offer
    def test_pricing_offer(self):
        assert classify_decision("Should I raise my prices?") == "pricing_offer"

    # Feature build phrase maps to product_validation
    def test_product_validation(self):
        assert classify_decision("Should I build this new feature?") == "product_validation"

    # Runway and cash phrases map to crisis_survival
    def test_crisis_survival(self):
        assert classify_decision("We have 3 months of runway left") == "crisis_survival"
        assert classify_decision("Cash crisis, can't pay salaries") == "crisis_survival"

    # Pivot phrase maps to strategy_direction
    def test_strategy_direction(self):
        assert classify_decision("Should we pivot to a new market?") == "strategy_direction"

    # Investment phrase maps to money_allocation
    def test_money_allocation(self):
        assert classify_decision("Where should I invest our profit?") == "money_allocation"

    # Bottleneck phrase maps to ops_execution
    def test_ops_execution(self):
        assert classify_decision("Bottleneck in our delivery process") == "ops_execution"

    # Unrelated input returns no category
    def test_generic_returns_none(self):
        assert classify_decision("What do you think about life?") is None


# Identity prompt block tests
class TestIdentityBlock:
    # Empty user produces empty block
    def test_empty_user(self):
        assert identity_block({}) == ""

    # Falls back to the user's name when questionnaire missing
    def test_user_without_questionnaire(self, sample_user):
        result = identity_block(sample_user)
        assert "Test Founder" in result

    # Name-only user still renders
    def test_user_with_name_only(self):
        user = {"id": "test", "name": "Alice"}
        result = identity_block(user)
        assert "Alice" in result


# Cognition prompt block tests
class TestCognitionBlock:
    # No inputs produce empty block
    def test_empty_user_and_text(self):
        result = cognition_block({}, "")
        assert result == ""
