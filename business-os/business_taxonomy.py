"""Business Taxonomy — real problems founders face, organized by function → subdomain → capability → failure mode.
Each failure mode is mapped to the SINGLE best book on that specific problem.
Books marked `in_kb: true` are already in the knowledge base + lenses. `in_kb: false` = gap to fill.
"""
# 16 functions, ~15 subdomains each, ~8 capabilities each, ~4 failure modes each
# ≈ 7,680 failure modes mapped to the definitive book for each

PROBLEM_TAXONOMY = {
    "vision": {
        "label": "Vision & Mission",
        "subdomains": {
            "direction_setting": {
                "label": "Direction Setting",
                "capabilities": {
                    "mission_definition": {
                        "label": "Mission Definition",
                        "failures": [
                            {"failure": "No written mission statement — team operates on unstated assumptions", "book": "Start With Why (Sinek)", "in_kb": True},
                            {"failure": "Mission is vague platitudes ('world-class excellence') — nobody can act on it", "book": "Good Strategy/Bad Strategy (Rumelt)", "in_kb": True},
                            {"failure": "Mission changes every quarter — no persistent north star", "book": "The Infinite Game (Sinek)", "in_kb": True},
                            {"failure": "Mission exists but founder never references it in decisions", "book": "Start With Why (Sinek)", "in_kb": True},
                        ]
                    },
                    "vision_articulation": {
                        "label": "Vision Articulation",
                        "failures": [
                            {"failure": "Can't describe where the company will be in 5 years with specificity", "book": "Good to Great (Collins)", "in_kb": True},
                            {"failure": "Vision is purely financial ('$100M ARR') — uninspiring, no product/impact story", "book": "Built to Last (Collins & Porras)", "in_kb": True},
                            {"failure": "Vision too small — incremental improvement vs category creation", "book": "Zero to One (Thiel)", "in_kb": True},
                            {"failure": "Vision too grandiose — no bridge from today to the vision", "book": "Good Strategy/Bad Strategy (Rumelt)", "in_kb": True},
                        ]
                    },
                    "values_definition": {
                        "label": "Values Definition",
                        "failures": [
                            {"failure": "No explicit company values — culture is whatever the loudest person says", "book": "The Culture Code (Coyle)", "in_kb": True},
                            {"failure": "Values are aspirational, not behavioral ('integrity' but no one gets fired for violating it)", "book": "Principles (Dalio)", "in_kb": True},
                            {"failure": "Values are different from what's actually rewarded", "book": "What Got You Here Won't Get You There (Goldsmith)", "in_kb": True},
                            {"failure": "Values not used in hiring, firing, or promotion decisions", "book": "High Output Management (Grove)", "in_kb": True},
                        ]
                    },
                    "founder_alignment": {
                        "label": "Founder Alignment",
                        "failures": [
                            {"failure": "Co-founders have different endgames (lifestyle vs IPO)", "book": "The Founder's Dilemmas (Wasserman)", "in_kb": True},
                            {"failure": "Equity split based on initial idea contribution, not long-term commitment", "book": "Slicing Pie (Moyer)", "in_kb": True},
                            {"failure": "No mechanism for resolving founder disagreements", "book": "The Hard Thing About Hard Things (Horowitz)", "in_kb": True},
                            {"failure": "One founder coasts while the other carries the company", "book": "The E-Myth Revisited (Gerber)", "in_kb": True},
                        ]
                    },
                }
            },
            "strategic_narrative": {
                "label": "Strategic Narrative",
                "capabilities": {
                    "narrative_construction": {
                        "label": "Narrative Construction",
                        "failures": [
                            {"failure": "Can't answer 'why does this company need to exist?' in one sentence", "book": "Start With Why (Sinek)", "in_kb": True},
                            {"failure": "Pitch changes with every audience — no consistent story", "book": "Building a StoryBrand (Miller)", "in_kb": True},
                            {"failure": "Narrative is about features, not transformation", "book": "Building a StoryBrand (Miller)", "in_kb": True},
                        ]
                    },
                    "stakeholder_communication": {
                        "label": "Stakeholder Communication",
                        "failures": [
                            {"failure": "Investors hear a different story than employees", "book": "Measure What Matters (Doerr)", "in_kb": True},
                            {"failure": "Vision known only to founder — never communicated down", "book": "The Fifth Discipline (Senge)", "in_kb": True},
                        ]
                    },
                }
            },
            "goal_system": {
                "label": "Goal System",
                "capabilities": {
                    "okr_implementation": {
                        "label": "OKR Implementation",
                        "failures": [
                            {"failure": "No goal-setting system at all — work is reactive", "book": "Measure What Matters (Doerr)", "in_kb": True},
                            {"failure": "Goals exist but nobody reviews them weekly", "book": "The 4 Disciplines of Execution", "in_kb": True},
                            {"failure": "OKRs are output metrics, not outcome metrics", "book": "Measure What Matters (Doerr)", "in_kb": True},
                            {"failure": "Too many OKRs — everything is a priority, so nothing is", "book": "The ONE Thing (Keller)", "in_kb": True},
                        ]
                    },
                    "metric_alignment": {
                        "label": "Metric Alignment",
                        "failures": [
                            {"failure": "Each department tracks its own metrics that conflict with other departments", "book": "The Fifth Discipline (Senge)", "in_kb": True},
                            {"failure": "North star metric not defined — can't tell if you're winning", "book": "Lean Analytics (Croll & Yoskovitz)", "in_kb": True},
                            {"failure": "Tracking vanity metrics (likes, pageviews) instead of business metrics (retention, LTV)", "book": "Lean Analytics (Croll & Yoskovitz)", "in_kb": True},
                        ]
                    },
                }
            },
            "adaptation_mechanism": {
                "label": "Adaptation Mechanism",
                "capabilities": {
                    "pivot_detection": {
                        "label": "Pivot Detection",
                        "failures": [
                            {"failure": "Continue investing in failing strategy months after data says stop", "book": "The Lean Startup (Ries)", "in_kb": True},
                            {"failure": "Pivot triggered by one bad month, not a pattern", "book": "The Lean Startup (Ries)", "in_kb": True},
                            {"failure": "No pre-set tripwires — don't know when to change course", "book": "Decisive (Heath)", "in_kb": True},
                        ]
                    },
                    "feedback_integration": {
                        "label": "Feedback Integration",
                        "failures": [
                            {"failure": "Customer feedback collected but never reaches product/strategy decisions", "book": "The Mom Test (Fitzpatrick)", "in_kb": True},
                            {"failure": "Only listen to loudest customers, not the market", "book": "Competing Against Luck (Christensen)", "in_kb": True},
                        ]
                    },
                }
            },
        }
    },

    "strategy": {
        "label": "Strategy & Positioning",
        "subdomains": {
            "competitive_analysis": {
                "label": "Competitive Analysis",
                "capabilities": {
                    "industry_structure": {
                        "label": "Industry Structure Analysis",
                        "failures": [
                            {"failure": "Don't understand the 5 forces shaping industry profitability", "book": "Competitive Strategy (Porter)", "in_kb": True},
                            {"failure": "Entering an industry with no barriers to entry — margin erosion inevitable", "book": "7 Powers (Helmer)", "in_kb": True},
                            {"failure": "Ignoring substitutes — competing only against direct rivals", "book": "Competitive Strategy (Porter)", "in_kb": True},
                            {"failure": "Don't know supplier/customer power dynamics in own value chain", "book": "Competitive Strategy (Porter)", "in_kb": True},
                        ]
                    },
                    "competitor_mapping": {
                        "label": "Competitor Mapping",
                        "failures": [
                            {"failure": "No systematic competitor tracking — rely on anecdotes", "book": "Blue Ocean Strategy (Kim & Mauborgne)", "in_kb": True},
                            {"failure": "Competitor analysis is a one-time exercise, not ongoing", "book": "Playing to Win (Lafley & Martin)", "in_kb": True},
                            {"failure": "Only track direct competitors — miss adjacent/new entrants", "book": "The Innovator's Dilemma (Christensen)", "in_kb": True},
                        ]
                    },
                    "market_sizing": {
                        "label": "Market Sizing",
                        "failures": [
                            {"failure": "TAM inflated by including customers who won't buy", "book": "Crossing the Chasm (Moore)", "in_kb": True},
                            {"failure": "No bottoms-up market sizing — only top-down analyst reports", "book": "Disciplined Entrepreneurship (Aulet)", "in_kb": True},
                            {"failure": "Addressable market is real but too small to build a venture-scale business", "book": "Zero to One (Thiel)", "in_kb": True},
                        ]
                    },
                }
            },
            "positioning": {
                "label": "Positioning",
                "capabilities": {
                    "category_design": {
                        "label": "Category Design",
                        "failures": [
                            {"failure": "Competing in an existing category without differentiation — price war inevitable", "book": "Positioning (Ries & Trout)", "in_kb": True},
                            {"failure": "No category creation — being compared to incumbents on their terms", "book": "Play Bigger (Ramadan)", "in_kb": True},
                            {"failure": "Positioning is feature-based, not emotion/mindshare-based", "book": "Positioning (Ries & Trout)", "in_kb": True},
                            {"failure": "Can't state who the product is NOT for — trying to serve everyone", "book": "Obviously Awesome (Dunford)", "in_kb": True},
                        ]
                    },
                    "value_proposition": {
                        "label": "Value Proposition",
                        "failures": [
                            {"failure": "Value prop is a list of features, not the single reason to switch", "book": "Building a StoryBrand (Miller)", "in_kb": True},
                            {"failure": "Value prop not quantified — no before/after comparison with numbers", "book": "SPIN Selling (Rackham)", "in_kb": True},
                            {"failure": "Value prop the same as every competitor", "book": "Blue Ocean Strategy (Kim & Mauborgne)", "in_kb": True},
                        ]
                    },
                    "differentiation": {
                        "label": "Differentiation",
                        "failures": [
                            {"failure": "Differentiating on features easily copied in 3 months", "book": "7 Powers (Helmer)", "in_kb": True},
                            {"failure": "Competing on price — race to zero, no moat", "book": "7 Powers (Helmer)", "in_kb": True},
                            {"failure": "Differentiation is a claim, not backed by evidence or customer proof", "book": "Obviously Awesome (Dunford)", "in_kb": True},
                        ]
                    },
                    "pricing_strategy": {
                        "label": "Pricing Strategy",
                        "failures": [
                            {"failure": "Pricing based on cost-plus, not value delivered", "book": "Monetizing Innovation (Ramaswamy)", "in_kb": True},
                            {"failure": "Underpricing — leaving money on the table, signaling low quality", "book": "Priceless (Poundstone)", "in_kb": True},
                            {"failure": "No pricing experiments — set once and never tested", "book": "Monetizing Innovation (Ramaswamy)", "in_kb": True},
                            {"failure": "Pricing not segmented by customer willingness to pay", "book": "The Strategy and Tactics of Pricing (Nagle)", "in_kb": True},
                        ]
                    },
                }
            },
            "growth_strategy": {
                "label": "Growth Strategy",
                "capabilities": {
                    "expansion_path": {
                        "label": "Expansion Path",
                        "failures": [
                            {"failure": "Expanding to new markets before winning the core market", "book": "Crossing the Chasm (Moore)", "in_kb": True},
                            {"failure": "No sequenced expansion plan — trying to be everywhere at once", "book": "Blue Ocean Strategy (Kim & Mauborgne)", "in_kb": True},
                            {"failure": "International expansion without local market understanding", "book": "Playing to Win (Lafley & Martin)", "in_kb": True},
                        ]
                    },
                    "acquisition_strategy": {
                        "label": "Acquisition Strategy",
                        "failures": [
                            {"failure": "Acquisitions driven by availability, not strategic fit", "book": "The Outsiders (Thorndike)", "in_kb": True},
                            {"failure": "Overpaying — synergy premiums that never materialize", "book": "The Outsiders (Thorndike)", "in_kb": True},
                            {"failure": "Post-merger integration failure — cultures clash, key people leave", "book": "The Hard Thing About Hard Things (Horowitz)", "in_kb": True},
                        ]
                    },
                    "partnership_leverage": {
                        "label": "Partnership Leverage",
                        "failures": [
                            {"failure": "No partnership strategy — trying to build everything in-house", "book": "Business Model Generation (Osterwalder)", "in_kb": True},
                            {"failure": "Partnerships with mismatched incentives — one side wins, other loses", "book": "Poor Charlie's Almanack (Munger)", "in_kb": True},
                        ]
                    },
                }
            },
            "execution_framework": {
                "label": "Execution Framework",
                "capabilities": {
                    "strategy_communication": {
                        "label": "Strategy Communication",
                        "failures": [
                            {"failure": "Strategy exists in the founder's head — team doesn't know what the strategy IS", "book": "The Art of Action (Bungay)", "in_kb": True},
                            {"failure": "Strategy communicated once at all-hands, then never referenced again", "book": "Playing to Win (Lafley & Martin)", "in_kb": True},
                            {"failure": "Team can't explain the strategy back in their own words", "book": "The Art of Action (Bungay)", "in_kb": True},
                        ]
                    },
                    "resource_allocation": {
                        "label": "Resource Allocation",
                        "failures": [
                            {"failure": "Resources spread evenly across all projects — no strategic concentration", "book": "Good Strategy/Bad Strategy (Rumelt)", "in_kb": True},
                            {"failure": "Budget allocated by last year's spend, not strategic priority", "book": "Playing to Win (Lafley & Martin)", "in_kb": True},
                            {"failure": "Best people on maintenance work, not strategic bets", "book": "Good Strategy/Bad Strategy (Rumelt)", "in_kb": True},
                        ]
                    },
                    "tradeoff_clarity": {
                        "label": "Tradeoff Clarity",
                        "failures": [
                            {"failure": "Strategy that doesn't say what you WON'T do — trying to please everyone", "book": "Good Strategy/Bad Strategy (Rumelt)", "in_kb": True},
                            {"failure": "Strategy is a list of goals, not a set of choices", "book": "Playing to Win (Lafley & Martin)", "in_kb": True},
                            {"failure": "Refusing to kill failing projects — sunk cost fallacy in portfolio", "book": "Thinking, Fast and Slow (Kahneman)", "in_kb": True},
                        ]
                    },
                }
            },
        }
    },

    "product": {
        "label": "Product & Value Prop",
        "subdomains": {
            "discovery": {
                "label": "Discovery & Validation",
                "capabilities": {
                    "problem_validation": {
                        "label": "Problem Validation",
                        "failures": [
                            {"failure": "Building before validating the problem exists", "book": "The Mom Test (Fitzpatrick)", "in_kb": True},
                            {"failure": "Solving a vitamin problem, not a painkiller problem", "book": "The Mom Test (Fitzpatrick)", "in_kb": True},
                            {"failure": "Problem validated with friends/family who won't be honest", "book": "The Mom Test (Fitzpatrick)", "in_kb": True},
                            {"failure": "Not understanding that 'I would buy that' ≠ an actual purchase", "book": "The Right It (Savoia)", "in_kb": True},
                        ]
                    },
                    "customer_research": {
                        "label": "Customer Research",
                        "failures": [
                            {"failure": "Asking 'would you use this?' instead of 'when did you last try to solve this?'", "book": "The Mom Test (Fitzpatrick)", "in_kb": True},
                            {"failure": "Interviewing the wrong persona — not the economic buyer or end user", "book": "Competing Against Luck (Christensen)", "in_kb": True},
                            {"failure": "Talking to customers once at the start, never again", "book": "Continuous Discovery Habits (Torres)", "in_kb": True},
                        ]
                    },
                    "jtbd_framework": {
                        "label": "Jobs-to-be-Done",
                        "failures": [
                            {"failure": "Designing for personas, not the job the customer is hiring the product for", "book": "Competing Against Luck (Christensen)", "in_kb": True},
                            {"failure": "Don't know what customers were 'firing' before using your product", "book": "Competing Against Luck (Christensen)", "in_kb": True},
                            {"failure": "Product competes against 'doing nothing' and loses", "book": "Competing Against Luck (Christensen)", "in_kb": True},
                        ]
                    },
                }
            },
            "development": {
                "label": "Development & Delivery",
                "capabilities": {
                    "mvp_strategy": {
                        "label": "MVP Strategy",
                        "failures": [
                            {"failure": "MVP is too polished — months spent perfecting an unvalidated feature", "book": "The Lean Startup (Ries)", "in_kb": True},
                            {"failure": "MVP is too crude — doesn't demonstrate the core value prop", "book": "Sprint (Knapp)", "in_kb": True},
                            {"failure": "No clear hypothesis being tested with the MVP", "book": "The Lean Startup (Ries)", "in_kb": True},
                        ]
                    },
                    "iteration_speed": {
                        "label": "Iteration Speed",
                        "failures": [
                            {"failure": "Release cycles measured in months, not days/weeks", "book": "Accelerate (Forsgren)", "in_kb": True},
                            {"failure": "Build-measure-learn loop is broken — building without measuring", "book": "The Lean Startup (Ries)", "in_kb": True},
                            {"failure": "Tech debt slowing every release to a crawl", "book": "Accelerate (Forsgren)", "in_kb": True},
                        ]
                    },
                    "quality_management": {
                        "label": "Quality Management",
                        "failures": [
                            {"failure": "Bugs reach production regularly — customer trust eroding", "book": "Accelerate (Forsgren)", "in_kb": True},
                            {"failure": "No automated testing — every release is a manual gamble", "book": "Continuous Delivery (Humble & Farley)", "in_kb": True},
                            {"failure": "Performance/scalability issues discovered by customers, not monitoring", "book": "Site Reliability Engineering (Google)", "in_kb": True},
                        ]
                    },
                }
            },
            "product_strategy": {
                "label": "Product Strategy",
                "capabilities": {
                    "roadmap_management": {
                        "label": "Roadmap Management",
                        "failures": [
                            {"failure": "Roadmap is a feature list driven by sales promises, not strategy", "book": "Inspired (Cagan)", "in_kb": True},
                            {"failure": "No roadmap — engineering builds whatever the last customer asked for", "book": "Inspired (Cagan)", "in_kb": True},
                            {"failure": "Roadmap has everything for everyone — no prioritization", "book": "Escaping the Build Trap (Perri)", "in_kb": True},
                        ]
                    },
                    "feature_prioritization": {
                        "label": "Feature Prioritization",
                        "failures": [
                            {"failure": "Prioritizing by HIPPO (Highest Paid Person's Opinion), not data", "book": "Inspired (Cagan)", "in_kb": True},
                            {"failure": "Building features for prospects, not existing customers", "book": "Inspired (Cagan)", "in_kb": True},
                            {"failure": "No kill criteria — once a feature is 'in development' it ships no matter what", "book": "Escaping the Build Trap (Perri)", "in_kb": True},
                        ]
                    },
                    "product_market_fit": {
                        "label": "Product-Market Fit",
                        "failures": [
                            {"failure": "Can't measure or define PMF — operating on gut feel", "book": "The Lean Startup (Ries)", "in_kb": True},
                            {"failure": "Retention is flat or declining but team thinks PMF is achieved", "book": "The Cold Start Problem (Chen)", "in_kb": True},
                            {"failure": "Customers use the product but wouldn't be disappointed if it disappeared tomorrow", "book": "The Lean Startup (Ries)", "in_kb": True},
                        ]
                    },
                }
            },
        }
    },

    "marketing": {
        "label": "Marketing & Demand Gen",
        "subdomains": {
            "audience_strategy": {
                "label": "Audience Strategy",
                "capabilities": {
                    "icp_definition": {
                        "label": "ICP Definition",
                        "failures": [
                            {"failure": "No ICP — 'anyone who can benefit' which means no one specifically", "book": "Positioning (Ries & Trout)", "in_kb": True},
                            {"failure": "ICP defined by demographics, not behavior/jobs-to-be-done", "book": "Competing Against Luck (Christensen)", "in_kb": True},
                            {"failure": "ICP changes every quarter because no one sticks with a bet long enough", "book": "22 Immutable Laws of Marketing (Ries & Trout)", "in_kb": True},
                        ]
                    },
                    "segmentation": {
                        "label": "Segmentation",
                        "failures": [
                            {"failure": "Same message sent to all segments — nothing resonates", "book": "This Is Marketing (Godin)", "in_kb": True},
                            {"failure": "Segments too small to build a real business on", "book": "Crossing the Chasm (Moore)", "in_kb": True},
                            {"failure": "Not segmenting by behavior (usage, spend, intent) — only by firmographics", "book": "How Brands Grow (Sharp)", "in_kb": True},
                        ]
                    },
                    "buyer_journey": {
                        "label": "Buyer Journey Mapping",
                        "failures": [
                            {"failure": "No mapped buyer journey — content created randomly", "book": "Building a StoryBrand (Miller)", "in_kb": True},
                            {"failure": "Journey is about the company, not the customer's internal struggle", "book": "Building a StoryBrand (Miller)", "in_kb": True},
                        ]
                    },
                }
            },
            "messaging": {
                "label": "Messaging & Copywriting",
                "capabilities": {
                    "core_message": {
                        "label": "Core Message",
                        "failures": [
                            {"failure": "Homepage headline is a tagline, not a value proposition", "book": "Building a StoryBrand (Miller)", "in_kb": True},
                            {"failure": "Message describes what the product IS, not what the customer BECOMES", "book": "Building a StoryBrand (Miller)", "in_kb": True},
                            {"failure": "Jargon and buzzwords — no human would say this out loud", "book": "Made to Stick (Heath)", "in_kb": True},
                        ]
                    },
                    "story_architecture": {
                        "label": "Story Architecture",
                        "failures": [
                            {"failure": "Company is the hero of the story, not the guide", "book": "Building a StoryBrand (Miller)", "in_kb": True},
                            {"failure": "No villain defined — what are you fighting against?", "book": "Building a StoryBrand (Miller)", "in_kb": True},
                            {"failure": "Story doesn't have stakes — nothing bad happens if they don't buy", "book": "Made to Stick (Heath)", "in_kb": True},
                        ]
                    },
                    "social_proof": {
                        "label": "Social Proof",
                        "failures": [
                            {"failure": "No customer stories or case studies — prospects have no evidence", "book": "Influence (Cialdini)", "in_kb": True},
                            {"failure": "Testimonials are generic ('great product!') — no specific results or numbers", "book": "Made to Stick (Heath)", "in_kb": True},
                        ]
                    },
                }
            },
            "channel_strategy": {
                "label": "Channel Strategy",
                "capabilities": {
                    "channel_selection": {
                        "label": "Channel Selection",
                        "failures": [
                            {"failure": "Trying every channel at once — spread too thin to win anywhere", "book": "Traction (Weinberg & Mares)", "in_kb": True},
                            {"failure": "Channel chosen because founder is comfortable with it, not because customers are there", "book": "Traction (Weinberg & Mares)", "in_kb": True},
                            {"failure": "Not running the Bullseye framework — no systematic channel testing", "book": "Traction (Weinberg & Mares)", "in_kb": True},
                        ]
                    },
                    "content_marketing": {
                        "label": "Content Marketing",
                        "failures": [
                            {"failure": "Content is company news, not useful insights for the audience", "book": "They Ask, You Answer (Sheridan)", "in_kb": True},
                            {"failure": "No content distribution strategy — publish and pray", "book": "Content Chemistry (Crestodina)", "in_kb": True},
                            {"failure": "Blog posts are 600-word SEO filler, not genuine expertise", "book": "Perennial Seller (Holiday)", "in_kb": True},
                        ]
                    },
                    "paid_acquisition": {
                        "label": "Paid Acquisition",
                        "failures": [
                            {"failure": "Spending on paid before organic retention works — leaking bucket", "book": "The Cold Start Problem (Chen)", "in_kb": True},
                            {"failure": "No attribution model — don't know which dollar creates which customer", "book": "Lean Analytics (Croll & Yoskovitz)", "in_kb": True},
                            {"failure": "CAC > LTV, but hiding it with aggregate metrics", "book": "Lean Analytics (Croll & Yoskovitz)", "in_kb": True},
                        ]
                    },
                }
            },
            "brand_building": {
                "label": "Brand Building",
                "capabilities": {
                    "brand_positioning": {
                        "label": "Brand Positioning",
                        "failures": [
                            {"failure": "Brand is a logo and colors, not a promise kept", "book": "22 Immutable Laws of Marketing (Ries & Trout)", "in_kb": True},
                            {"failure": "Brand changes constantly — no consistent identity to build trust on", "book": "How Brands Grow (Sharp)", "in_kb": True},
                            {"failure": "No mental availability — when the problem arises, your brand doesn't come to mind", "book": "How Brands Grow (Sharp)", "in_kb": True},
                        ]
                    },
                    "brand_awareness": {
                        "label": "Brand Awareness",
                        "failures": [
                            {"failure": "No physical availability — can't buy the product when you want to", "book": "How Brands Grow (Sharp)", "in_kb": True},
                            {"failure": "Marketing only targets new customers, never reinforces existing buyers", "book": "How Brands Grow (Sharp)", "in_kb": True},
                        ]
                    },
                    "category_ownership": {
                        "label": "Category Ownership",
                        "failures": [
                            {"failure": "Not the first brand in the prospect's mind for any category", "book": "Positioning (Ries & Trout)", "in_kb": True},
                            {"failure": "Trying to own a category already owned by a competitor", "book": "22 Immutable Laws of Marketing (Ries & Trout)", "in_kb": True},
                        ]
                    },
                }
            },
        }
    },

    "sales": {
        "label": "Sales & Conversion",
        "subdomains": {
            "sales_process": {
                "label": "Sales Process",
                "capabilities": {
                    "pipeline_management": {
                        "label": "Pipeline Management",
                        "failures": [
                            {"failure": "No defined sales stages — pipeline is a list of names with gut-level estimates", "book": "Predictable Revenue (Ross)", "in_kb": True},
                            {"failure": "Pipeline is inflated with 'good conversations' — no qualification criteria", "book": "SPIN Selling (Rackham)", "in_kb": True},
                            {"failure": "No pipeline coverage ratio — don't know how much pipeline is needed for target", "book": "Predictable Revenue (Ross)", "in_kb": True},
                        ]
                    },
                    "qualification": {
                        "label": "Qualification",
                        "failures": [
                            {"failure": "No qualification framework — chasing every lead regardless of fit", "book": "The Challenger Sale (Dixon & Adamson)", "in_kb": True},
                            {"failure": "Sales team qualifies on budget only, ignores need/authority/timeline", "book": "SPIN Selling (Rackham)", "in_kb": True},
                            {"failure": "Sales reps spend 70% of time on deals that never close", "book": "Predictable Revenue (Ross)", "in_kb": True},
                        ]
                    },
                    "sales_methodology": {
                        "label": "Sales Methodology",
                        "failures": [
                            {"failure": "Using product-pitch approach for complex B2B sales — needs SPIN/diagnostic", "book": "SPIN Selling (Rackham)", "in_kb": True},
                            {"failure": "No common methodology — every rep sells differently, no repeatable process", "book": "The Challenger Sale (Dixon & Adamson)", "in_kb": True},
                            {"failure": "Reps talk features when they should be diagnosing problems", "book": "SPIN Selling (Rackham)", "in_kb": True},
                        ]
                    },
                }
            },
            "conversion_optimization": {
                "label": "Conversion Optimization",
                "capabilities": {
                    "close_rate": {
                        "label": "Close Rate",
                        "failures": [
                            {"failure": "Demos aren't converting — product looks great but no urgency to buy", "book": "The Challenger Sale (Dixon & Adamson)", "in_kb": True},
                            {"failure": "No competitive battlecard — reps lose deals they should win", "book": "The Challenger Sale (Dixon & Adamson)", "in_kb": True},
                            {"failure": "Deals lost to 'no decision' — can't create urgency or overcome status quo bias", "book": "The JOLT Effect (Dixon & McKenna)", "in_kb": True},
                        ]
                    },
                    "objection_handling": {
                        "label": "Objection Handling",
                        "failures": [
                            {"failure": "Price objections met with discount, not value repositioning", "book": "Never Split the Difference (Voss)", "in_kb": True},
                            {"failure": "Reps accept objections at face value instead of diagnosing the real concern", "book": "SPIN Selling (Rackham)", "in_kb": True},
                        ]
                    },
                    "negotiation": {
                        "label": "Negotiation",
                        "failures": [
                            {"failure": "Giving concessions without getting anything in return", "book": "Never Split the Difference (Voss)", "in_kb": True},
                            {"failure": "Negotiating against yourself — dropping price before the buyer asks", "book": "Never Split the Difference (Voss)", "in_kb": True},
                            {"failure": "No BATNA — no walk-away alternative, so every deal feels existential", "book": "Getting to Yes (Fisher & Ury)", "in_kb": True},
                        ]
                    },
                }
            },
            "sales_team": {
                "label": "Sales Team & Enablement",
                "capabilities": {
                    "hiring_sales": {
                        "label": "Hiring Salespeople",
                        "failures": [
                            {"failure": "Hiring salespeople before founder can sell it themselves", "book": "The Sales Acceleration Formula (Roberge)", "in_kb": True},
                            {"failure": "Hiring for industry contacts instead of sales skill and hunger", "book": "The Sales Acceleration Formula (Roberge)", "in_kb": True},
                            {"failure": "No ramp plan — expecting new hires to close in month 1", "book": "Predictable Revenue (Ross)", "in_kb": True},
                        ]
                    },
                    "compensation": {
                        "label": "Compensation Design",
                        "failures": [
                            {"failure": "Comp plan rewards new logos, not retention — churn spikes", "book": "The Sales Acceleration Formula (Roberge)", "in_kb": True},
                            {"failure": "Caps on commission — top performers hit the cap and stop selling", "book": "The Sales Acceleration Formula (Roberge)", "in_kb": True},
                        ]
                    },
                    "enablement": {
                        "label": "Enablement",
                        "failures": [
                            {"failure": "No playbook — every rep invents their own process", "book": "The Sales Acceleration Formula (Roberge)", "in_kb": True},
                            {"failure": "Product training is feature-list memorization, not value-selling", "book": "The Challenger Sale (Dixon & Adamson)", "in_kb": True},
                        ]
                    },
                }
            },
        }
    },

    "finance": {
        "label": "Finance & Cash Flow",
        "subdomains": {
            "financial_planning": {
                "label": "Financial Planning",
                "capabilities": {
                    "cash_management": {
                        "label": "Cash Management",
                        "failures": [
                            {"failure": "Don't know runway in months — operating on bank balance, not burn rate", "book": "Venture Deals (Feld & Mendelson)", "in_kb": True},
                            {"failure": "Runway under 6 months with no fundraising plan", "book": "Venture Deals (Feld & Mendelson)", "in_kb": True},
                            {"failure": "Cash flows not forecast — surprised by payroll", "book": "Financial Intelligence (Berman & Knight)", "in_kb": True},
                        ]
                    },
                    "unit_economics": {
                        "label": "Unit Economics",
                        "failures": [
                            {"failure": "Don't know CAC, LTV, or payback period", "book": "Lean Analytics (Croll & Yoskovitz)", "in_kb": True},
                            {"failure": "LTV/CAC ratio under 3:1 — each dollar of sales/marketing loses money", "book": "Lean Analytics (Croll & Yoskovitz)", "in_kb": True},
                            {"failure": "Gross margin below 50% — can't afford sales & marketing at scale", "book": "The Personal MBA (Kaufman)", "in_kb": True},
                        ]
                    },
                    "budgeting": {
                        "label": "Budgeting",
                        "failures": [
                            {"failure": "No budget — spending as requests come in", "book": "Financial Intelligence (Berman & Knight)", "in_kb": True},
                            {"failure": "Budget built on hopes, not pipeline coverage or retention rates", "book": "Financial Intelligence (Berman & Knight)", "in_kb": True},
                            {"failure": "Zero-based budgeting never done — inertia keeps dead costs alive", "book": "The Personal MBA (Kaufman)", "in_kb": True},
                        ]
                    },
                }
            },
            "fundraising": {
                "label": "Fundraising",
                "capabilities": {
                    "fundraising_strategy": {
                        "label": "Fundraising Strategy",
                        "failures": [
                            {"failure": "Raising too much or too little — not matching round to milestones", "book": "Venture Deals (Feld & Mendelson)", "in_kb": True},
                            {"failure": "Raising from the wrong type of investor for the stage", "book": "Venture Deals (Feld & Mendelson)", "in_kb": True},
                            {"failure": "Fundraising is a full-time job for 3-6 months — company stalls", "book": "The Hard Thing About Hard Things (Horowitz)", "in_kb": True},
                        ]
                    },
                    "investor_pipeline": {
                        "label": "Investor Pipeline",
                        "failures": [
                            {"failure": "Taking the first term sheet without competitive tension", "book": "Venture Deals (Feld & Mendelson)", "in_kb": True},
                            {"failure": "Pitching to investors before warm introductions — low conversion", "book": "Venture Deals (Feld & Mendelson)", "in_kb": True},
                        ]
                    },
                    "dilution_management": {
                        "label": "Dilution Management",
                        "failures": [
                            {"failure": "Founders own <20% by Series B — no motivation to stay", "book": "Venture Deals (Feld & Mendelson)", "in_kb": True},
                            {"failure": "Not understanding liquidation preferences — investors get paid, founders don't", "book": "Venture Deals (Feld & Mendelson)", "in_kb": True},
                        ]
                    },
                }
            },
            "revenue_operations": {
                "label": "Revenue Operations",
                "capabilities": {
                    "billing": {
                        "label": "Billing & Collections",
                        "failures": [
                            {"failure": "Net 30 means net 90 — slow payers straining cash", "book": "Financial Intelligence (Berman & Knight)", "in_kb": True},
                            {"failure": "No dunning process — churn from failed payments that could be saved", "book": "Profitwell/Recurly (blogs)", "in_kb": True},
                        ]
                    },
                    "revenue_recognition": {
                        "label": "Revenue Recognition",
                        "failures": [
                            {"failure": "Booking annual contracts as immediate revenue — audit failure waiting", "book": "Financial Intelligence (Berman & Knight)", "in_kb": True},
                            {"failure": "ARR/MRR miscalculated — board and investors making decisions on wrong numbers", "book": "SaaS Metrics 2.0 (Croll)", "in_kb": True},
                        ]
                    },
                }
            },
            "profitability": {
                "label": "Profitability & Margins",
                "capabilities": {
                    "cost_structure": {
                        "label": "Cost Structure",
                        "failures": [
                            {"failure": "Fixed costs too high — can't flex down in a downturn", "book": "The Personal MBA (Kaufman)", "in_kb": True},
                            {"failure": "Growth at any cost — burning cash on unprofitable customers", "book": "The Personal MBA (Kaufman)", "in_kb": True},
                        ]
                    },
                    "margin_improvement": {
                        "label": "Margin Improvement",
                        "failures": [
                            {"failure": "Margins shrinking but nobody notices — death by a thousand cuts", "book": "The Personal MBA (Kaufman)", "in_kb": True},
                            {"failure": "COGS rising but pricing unchanged — margin compression eating the business", "book": "Financial Intelligence (Berman & Knight)", "in_kb": True},
                        ]
                    },
                }
            },
        }
    },

    "operations": {
        "label": "Operations & Efficiency",
        "subdomains": {
            "process_management": {
                "label": "Process Management",
                "capabilities": {
                    "process_documentation": {
                        "label": "Process Documentation",
                        "failures": [
                            {"failure": "Critical processes live only in key people's heads — single point of failure", "book": "The E-Myth Revisited (Gerber)", "in_kb": True},
                            {"failure": "No SOPs — every time a task is done, it's done differently", "book": "The E-Myth Revisited (Gerber)", "in_kb": True},
                            {"failure": "Processes documented once then never updated — reality has drifted", "book": "The 4 Disciplines of Execution", "in_kb": True},
                        ]
                    },
                    "bottleneck_identification": {
                        "label": "Bottleneck Identification",
                        "failures": [
                            {"failure": "Founder is the bottleneck — everything needs their approval", "book": "The E-Myth Revisited (Gerber)", "in_kb": True},
                            {"failure": "No constraint analysis — don't know what's limiting throughput", "book": "The Goal (Goldratt)", "in_kb": True},
                            {"failure": "Hiring to fix bottlenecks without first fixing the process", "book": "The Goal (Goldratt)", "in_kb": True},
                        ]
                    },
                    "workflow_automation": {
                        "label": "Workflow Automation",
                        "failures": [
                            {"failure": "Manual data entry across multiple systems — error-prone and slow", "book": "The Personal MBA (Kaufman)", "in_kb": True},
                            {"failure": "Automating a broken process — digitizing chaos doesn't fix it", "book": "The E-Myth Revisited (Gerber)", "in_kb": True},
                        ]
                    },
                }
            },
            "supply_chain": {
                "label": "Supply Chain",
                "capabilities": {
                    "vendor_management": {
                        "label": "Vendor Management",
                        "failures": [
                            {"failure": "Single supplier dependency — one failure stops the business", "book": "The Black Swan (Taleb)", "in_kb": True},
                            {"failure": "No vendor scorecard — quality issues discovered by customers", "book": "The Goal (Goldratt)", "in_kb": True},
                            {"failure": "Race to the cheapest supplier — quality and reliability sacrificed", "book": "The Black Swan (Taleb)", "in_kb": True},
                        ]
                    },
                    "inventory_management": {
                        "label": "Inventory Management",
                        "failures": [
                            {"failure": "Stockouts — losing sales because inventory wasn't reordered", "book": "The Goal (Goldratt)", "in_kb": True},
                            {"failure": "Overstock — cash tied up in inventory that isn't moving", "book": "The Goal (Goldratt)", "in_kb": True},
                        ]
                    },
                }
            },
            "legal_compliance": {
                "label": "Legal & Compliance",
                "capabilities": {
                    "corporate_governance": {
                        "label": "Corporate Governance",
                        "failures": [
                            {"failure": "No board or advisory structure — founder has no accountability", "book": "Startup Boards (Feld)", "in_kb": True},
                            {"failure": "Board meetings are status updates, not strategic discussions", "book": "Startup Boards (Feld)", "in_kb": True},
                        ]
                    },
                    "ip_protection": {
                        "label": "IP Protection",
                        "failures": [
                            {"failure": "No IP assignment from co-founders/contractors — don't own what you paid for", "book": "Venture Deals (Feld & Mendelson)", "in_kb": True},
                            {"failure": "Trademark not filed — competitor can copy your name", "book": "Venture Deals (Feld & Mendelson)", "in_kb": True},
                        ]
                    },
                    "regulatory_compliance": {
                        "label": "Regulatory Compliance",
                        "failures": [
                            {"failure": "GDPR/CCPA violations because privacy wasn't designed in from the start", "book": "GDPR for Dummies (no single definitive book)", "in_kb": True},
                            {"failure": "Operating in a regulated industry without understanding the regulations", "book": "Venture Deals (Feld & Mendelson)", "in_kb": True},
                        ]
                    },
                }
            },
        }
    },

    "hr": {
        "label": "People & Talent",
        "subdomains": {
            "hiring": {
                "label": "Hiring & Recruiting",
                "capabilities": {
                    "role_definition": {
                        "label": "Role Definition",
                        "failures": [
                            {"failure": "Hiring before defining what success looks like in the role", "book": "Who (Smart & Street)", "in_kb": True},
                            {"failure": "Job description is a wishlist, not a set of 3-5 outcomes the person must achieve", "book": "Who (Smart & Street)", "in_kb": True},
                            {"failure": "Hiring a generalist when you need a specialist, or vice versa", "book": "High Output Management (Grove)", "in_kb": True},
                        ]
                    },
                    "sourcing": {
                        "label": "Sourcing",
                        "failures": [
                            {"failure": "Only hiring from your network — limited candidate pool", "book": "Who (Smart & Street)", "in_kb": True},
                            {"failure": "Passive sourcing only — no active outreach to the best people", "book": "Who (Smart & Street)", "in_kb": True},
                        ]
                    },
                    "interview_process": {
                        "label": "Interview Process",
                        "failures": [
                            {"failure": "Interviews are unstructured conversations — no scorecard, no consistency", "book": "Who (Smart & Street)", "in_kb": True},
                            {"failure": "Hiring based on likability, not demonstrated ability to deliver the outcomes", "book": "Who (Smart & Street)", "in_kb": True},
                            {"failure": "No work sample or trial project — hire on interview performance alone", "book": "Work Rules! (Bock)", "in_kb": True},
                        ]
                    },
                    "reference_checking": {
                        "label": "Reference Checking",
                        "failures": [
                            {"failure": "Skipping reference checks — the 'we need them now' trap", "book": "Who (Smart & Street)", "in_kb": True},
                            {"failure": "References are cherry-picked by the candidate — not back-channeled", "book": "Who (Smart & Street)", "in_kb": True},
                        ]
                    },
                }
            },
            "retention": {
                "label": "Retention & Engagement",
                "capabilities": {
                    "onboarding": {
                        "label": "Onboarding",
                        "failures": [
                            {"failure": "No structured onboarding — new hire gets a laptop and a 'figure it out'", "book": "The First 90 Days (Watkins)", "in_kb": True},
                            {"failure": "New hire productivity delayed by months — cost of poor onboarding invisible", "book": "Work Rules! (Bock)", "in_kb": True},
                        ]
                    },
                    "engagement": {
                        "label": "Engagement",
                        "failures": [
                            {"failure": "No 1:1 structure — managers and reports talk only about tasks, not growth", "book": "High Output Management (Grove)", "in_kb": True},
                            {"failure": "Burnout spreading — no one tracks workload or flags unsustainable pace", "book": "The Hard Thing About Hard Things (Horowitz)", "in_kb": True},
                            {"failure": "Top performers leaving and nobody knows why (no exit interviews)", "book": "Work Rules! (Bock)", "in_kb": True},
                        ]
                    },
                    "turnover_management": {
                        "label": "Turnover Management",
                        "failures": [
                            {"failure": "Key person risk — if one person leaves, the function collapses", "book": "The E-Myth Revisited (Gerber)", "in_kb": True},
                            {"failure": "Tolerating brilliant jerks — destroying team morale", "book": "The No Asshole Rule (Sutton)", "in_kb": True},
                            {"failure": "Not firing fast enough — keeping underperformers signals mediocrity is acceptable", "book": "The Hard Thing About Hard Things (Horowitz)", "in_kb": True},
                        ]
                    },
                }
            },
            "culture": {
                "label": "Culture & Values",
                "capabilities": {
                    "culture_building": {
                        "label": "Culture Building",
                        "failures": [
                            {"failure": "Culture = free lunches and ping pong — not how decisions are made", "book": "The Culture Code (Coyle)", "in_kb": True},
                            {"failure": "Psychological safety absent — people don't speak up about problems", "book": "The Culture Code (Coyle)", "in_kb": True},
                            {"failure": "Values are posters on the wall, not lived in hiring/firing/decisions", "book": "Principles (Dalio)", "in_kb": True},
                            {"failure": "Culture degrading as the company scales past Dunbar's number (150)", "book": "The Culture Code (Coyle)", "in_kb": True},
                        ]
                    },
                    "performance_management": {
                        "label": "Performance Management",
                        "failures": [
                            {"failure": "Annual reviews only — feedback is a surprise, not continuous", "book": "Radical Candor (Scott)", "in_kb": True},
                            {"failure": "No clear performance standards — what does 'good' look like?", "book": "High Output Management (Grove)", "in_kb": True},
                            {"failure": "Poor performers not managed out — A players leave because B players are tolerated", "book": "The Hard Thing About Hard Things (Horowitz)", "in_kb": True},
                        ]
                    },
                    "feedback_culture": {
                        "label": "Feedback Culture",
                        "failures": [
                            {"failure": "Feedback only flows top-down — leaders don't receive honest input", "book": "Principles (Dalio)", "in_kb": True},
                            {"failure": "Feedback is personal, not behavioral — 'you're lazy' vs 'you missed 3 deadlines'", "book": "Radical Candor (Scott)", "in_kb": True},
                        ]
                    },
                }
            },
            "compensation": {
                "label": "Compensation & Rewards",
                "capabilities": {
                    "salary_structure": {
                        "label": "Salary Structure",
                        "failures": [
                            {"failure": "No salary bands — people doing the same job paid wildly differently", "book": "Work Rules! (Bock)", "in_kb": True},
                            {"failure": "Paying below market and wondering why you can't hire", "book": "Work Rules! (Bock)", "in_kb": True},
                        ]
                    },
                    "equity": {
                        "label": "Equity & Ownership",
                        "failures": [
                            {"failure": "Early employees get tiny equity — less than 0.1% for employee #5 who builds the product", "book": "The Founder's Dilemmas (Wasserman)", "in_kb": True},
                            {"failure": "No vesting schedule — employees can walk with full equity in month 2", "book": "Venture Deals (Feld & Mendelson)", "in_kb": True},
                        ]
                    },
                }
            },
        }
    },

    "customer_success": {
        "label": "Customer Success & Retention",
        "subdomains": {
            "onboarding_success": {
                "label": "Customer Onboarding",
                "capabilities": {
                    "time_to_value": {
                        "label": "Time to Value",
                        "failures": [
                            {"failure": "Customers take 3+ months to see value — churn before they get there", "book": "Customer Success (Mehta)", "in_kb": True},
                            {"failure": "Onboarding is a feature tour, not guided to the customer's specific outcome", "book": "Customer Success (Mehta)", "in_kb": True},
                            {"failure": "No defined 'aha moment' — don't know when a customer is actually onboarded", "book": "Customer Success (Mehta)", "in_kb": True},
                        ]
                    },
                    "implementation": {
                        "label": "Implementation",
                        "failures": [
                            {"failure": "No implementation playbook — every deployment is bespoke chaos", "book": "Customer Success (Mehta)", "in_kb": True},
                            {"failure": "Data migration breaks — customer starts with corrupted data, never recovers trust", "book": "Customer Success (Mehta)", "in_kb": True},
                        ]
                    },
                }
            },
            "retention_management": {
                "label": "Retention Management",
                "capabilities": {
                    "churn_prediction": {
                        "label": "Churn Prediction",
                        "failures": [
                            {"failure": "No early warning signals — churn is a surprise every time", "book": "Customer Success (Mehta)", "in_kb": True},
                            {"failure": "Not tracking health score — don't know which accounts are at risk", "book": "Customer Success (Mehta)", "in_kb": True},
                            {"failure": "Churn is measured; churn reason is not — fixing symptoms, not causes", "book": "Customer Success (Mehta)", "in_kb": True},
                        ]
                    },
                    "renewal_process": {
                        "label": "Renewal Process",
                        "failures": [
                            {"failure": "Renewal conversation starts 30 days before expiry — too late to demonstrate value", "book": "Customer Success (Mehta)", "in_kb": True},
                            {"failure": "Renewal is a sales transaction, not a success milestone", "book": "Customer Success (Mehta)", "in_kb": True},
                        ]
                    },
                    "saving_at_risk": {
                        "label": "Saving At-Risk Accounts",
                        "failures": [
                            {"failure": "No save playbook — every at-risk account gets ad-hoc treatment", "book": "Customer Success (Mehta)", "in_kb": True},
                            {"failure": "Escalation to exec doesn't close the gap — they can't fix the product", "book": "Customer Success (Mehta)", "in_kb": True},
                        ]
                    },
                }
            },
            "expansion": {
                "label": "Expansion & Upsell",
                "capabilities": {
                    "expansion_motion": {
                        "label": "Expansion Motion",
                        "failures": [
                            {"failure": "No upsell motion — revenue only grows through new logos, not existing accounts", "book": "Farm Don't Hunt (Smith)", "in_kb": True},
                            {"failure": "Expansion revenue not tracked separately — can't tell if NRR > 100%", "book": "SaaS Metrics 2.0 (Croll)", "in_kb": True},
                        ]
                    },
                    "customer_advocacy": {
                        "label": "Customer Advocacy",
                        "failures": [
                            {"failure": "No referral program — happy customers not leveraged for growth", "book": "Contagious (Berger)", "in_kb": True},
                            {"failure": "NPS is measured but never acted on — score for score's sake", "book": "The Ultimate Question (Reichheld)", "in_kb": True},
                        ]
                    },
                }
            },
        }
    },

    "technology": {
        "label": "Technology & Engineering",
        "subdomains": {
            "architecture": {
                "label": "Architecture",
                "capabilities": {
                    "system_design": {
                        "label": "System Design",
                        "failures": [
                            {"failure": "No architecture decisions recorded — why was this choice made?", "book": "Designing Data-Intensive Applications (Kleppmann)", "in_kb": True},
                            {"failure": "Monolith that should have been split 6 months ago — velocity collapsed", "book": "Building Microservices (Newman)", "in_kb": True},
                            {"failure": "Premature microservices — added complexity without the scale to justify it", "book": "Building Microservices (Newman)", "in_kb": True},
                        ]
                    },
                    "technical_debt": {
                        "label": "Technical Debt Management",
                        "failures": [
                            {"failure": "No tech debt tracking — it's invisible until everything breaks", "book": "Accelerate (Forsgren)", "in_kb": True},
                            {"failure": "Codebase has no tests — every change is Russian roulette", "book": "Working Effectively with Legacy Code (Feathers)", "in_kb": True},
                            {"failure": "Refactoring never budgeted — always deprioritized for new features", "book": "Accelerate (Forsgren)", "in_kb": True},
                        ]
                    },
                }
            },
            "delivery": {
                "label": "Delivery & DevOps",
                "capabilities": {
                    "ci_cd": {
                        "label": "CI/CD",
                        "failures": [
                            {"failure": "Manual deployments — releases are stressful all-day events", "book": "Accelerate (Forsgren)", "in_kb": True},
                            {"failure": "Deploy frequency under 1/week — can't ship fixes fast", "book": "Accelerate (Forsgren)", "in_kb": True},
                        ]
                    },
                    "incident_response": {
                        "label": "Incident Response",
                        "failures": [
                            {"failure": "No on-call rotation — founder fixing things at 3am", "book": "Site Reliability Engineering (Google)", "in_kb": True},
                            {"failure": "Incidents are fixed but never post-mortemed — same issues recur", "book": "Site Reliability Engineering (Google)", "in_kb": True},
                        ]
                    },
                }
            },
            "data_infrastructure": {
                "label": "Data Infrastructure",
                "capabilities": {
                    "data_pipeline": {
                        "label": "Data Pipeline",
                        "failures": [
                            {"failure": "No data warehouse — analytics run on production DB, slowing everything", "book": "Designing Data-Intensive Applications (Kleppmann)", "in_kb": True},
                            {"failure": "Data is siloed — marketing can't see product data, sales can't see usage", "book": "The Data Warehouse Toolkit (Kimball)", "in_kb": True},
                        ]
                    },
                    "data_quality": {
                        "label": "Data Quality",
                        "failures": [
                            {"failure": "Duplicate records, missing fields — dashboards are wrong, decisions are worse", "book": "Designing Data-Intensive Applications (Kleppmann)", "in_kb": True},
                        ]
                    },
                }
            },
            "security": {
                "label": "Security",
                "capabilities": {
                    "security_posture": {
                        "label": "Security Posture",
                        "failures": [
                            {"failure": "No security review process — vulnerabilities discovered by attackers", "book": "Web Application Security (Hoffman)", "in_kb": True},
                            {"failure": "No SOC 2 / ISO 27001 — enterprise deals blocked by security questionnaires", "book": "No single book — compliance framework specific", "in_kb": True},
                        ]
                    },
                }
            },
        }
    },

    "data": {
        "label": "Data & Analytics",
        "subdomains": {
            "metrics_framework": {
                "label": "Metrics Framework",
                "capabilities": {
                    "kpi_selection": {
                        "label": "KPI Selection",
                        "failures": [
                            {"failure": "Tracking everything, understanding nothing — dashboard overload", "book": "Lean Analytics (Croll & Yoskovitz)", "in_kb": True},
                            {"failure": "KPIs are lagging indicators (revenue) not leading indicators (pipeline created)", "book": "Lean Analytics (Croll & Yoskovitz)", "in_kb": True},
                            {"failure": "Vanity metrics celebrated (downloads, signups) while business metrics ignored (activation, retention)", "book": "Lean Analytics (Croll & Yoskovitz)", "in_kb": True},
                        ]
                    },
                    "metric_alignment": {
                        "label": "Metric Alignment",
                        "failures": [
                            {"failure": "Every team tracks different definitions of the same metric — 'active user' means 5 things", "book": "Lean Analytics (Croll & Yoskovitz)", "in_kb": True},
                            {"failure": "No single source of truth — 3 dashboards, 3 different revenue numbers", "book": "Lean Analytics (Croll & Yoskovitz)", "in_kb": True},
                        ]
                    },
                }
            },
            "decision_support": {
                "label": "Decision Support",
                "capabilities": {
                    "data_informed_decisions": {
                        "label": "Data-Informed Decisions",
                        "failures": [
                            {"failure": "Decisions made on gut feel — data exists but not consulted", "book": "Superforecasting (Tetlock)", "in_kb": True},
                            {"failure": "Decisions made on a single data point, not a trend — month-over-month noise mistaken for signal", "book": "The Signal and the Noise (Silver)", "in_kb": True},
                            {"failure": "Analysis paralysis — more data requested instead of making the call", "book": "Decisive (Heath)", "in_kb": True},
                        ]
                    },
                    "experimentation": {
                        "label": "Experimentation Culture",
                        "failures": [
                            {"failure": "No A/B testing — every change is 'we think this is better'", "book": "Trustworthy Online Controlled Experiments (Kohavi)", "in_kb": True},
                            {"failure": "A/B tests run but never reach statistical significance before shipping", "book": "Trustworthy Online Controlled Experiments (Kohavi)", "in_kb": True},
                        ]
                    },
                }
            },
            "reporting": {
                "label": "Reporting & Dashboards",
                "capabilities": {
                    "executive_reporting": {
                        "label": "Executive Reporting",
                        "failures": [
                            {"failure": "Board deck takes 2 weeks to produce — data isn't readily available", "book": "Lean Analytics (Croll & Yoskovitz)", "in_kb": True},
                            {"failure": "Monthly reports are backward-looking only — no forward indicators", "book": "Lean Analytics (Croll & Yoskovitz)", "in_kb": True},
                        ]
                    },
                }
            },
        }
    },

    "brand": {
        "label": "Brand & Trust",
        "subdomains": {
            "brand_strategy": {
                "label": "Brand Strategy",
                "capabilities": {
                    "brand_positioning": {
                        "label": "Brand Positioning",
                        "failures": [
                            {"failure": "Brand = logo + colors. Nobody on the team can articulate what the brand STANDS FOR.", "book": "22 Immutable Laws of Marketing (Ries & Trout)", "in_kb": True},
                            {"failure": "Brand identity changes with every redesign — no consistent equity built", "book": "How Brands Grow (Sharp)", "in_kb": True},
                        ]
                    },
                    "brand_promise": {
                        "label": "Brand Promise",
                        "failures": [
                            {"failure": "Marketing promises are bigger than what the product delivers — trust destroyed on first use", "book": "This Is Marketing (Godin)", "in_kb": True},
                            {"failure": "Brand promise not defined — customers have no expectation, so no reason to choose you", "book": "This Is Marketing (Godin)", "in_kb": True},
                        ]
                    },
                }
            },
            "trust_building": {
                "label": "Trust Building",
                "capabilities": {
                    "social_proof": {
                        "label": "Social Proof",
                        "failures": [
                            {"failure": "No recognizable logos on the website — prospects think the product is unproven", "book": "Influence (Cialdini)", "in_kb": True},
                            {"failure": "Case studies hidden behind forms — can't build trust anonymously", "book": "They Ask, You Answer (Sheridan)", "in_kb": True},
                        ]
                    },
                    "thought_leadership": {
                        "label": "Thought Leadership",
                        "failures": [
                            {"failure": "Founder has no public presence — brand IS the founder in early stage", "book": "Crushing It! (Vaynerchuk)", "in_kb": True},
                            {"failure": "Content is generic — no original point of view, nothing to build trust around", "book": "Perennial Seller (Holiday)", "in_kb": True},
                        ]
                    },
                }
            },
            "reputation_management": {
                "label": "Reputation Management",
                "capabilities": {
                    "crisis_communication": {
                        "label": "Crisis Communication",
                        "failures": [
                            {"failure": "No crisis plan — when something breaks, response is reactive and damaging", "book": "The Speed of Trust (Covey Jr.)", "in_kb": True},
                            {"failure": "Data breach / outage communicated late — customers find out on Twitter first", "book": "The Speed of Trust (Covey Jr.)", "in_kb": True},
                        ]
                    },
                }
            },
        }
    },

    "partnerships": {
        "label": "Partnerships & Alliances",
        "subdomains": {
            "partnership_strategy": {
                "label": "Partnership Strategy",
                "capabilities": {
                    "partner_selection": {
                        "label": "Partner Selection",
                        "failures": [
                            {"failure": "Partnerships are random — whoever shows up, not whoever creates the most leverage", "book": "Business Model Generation (Osterwalder)", "in_kb": True},
                            {"failure": "Partnering with companies that have misaligned incentives — they win when you lose", "book": "Poor Charlie's Almanack (Munger)", "in_kb": True},
                        ]
                    },
                    "partner_economics": {
                        "label": "Partner Economics",
                        "failures": [
                            {"failure": "Partner gives 10% and takes 80% of the economics — bad deal hidden in bad math", "book": "Poor Charlie's Almanack (Munger)", "in_kb": True},
                            {"failure": "Revenue share doesn't cover the cost of serving the partner's customers", "book": "Business Model Generation (Osterwalder)", "in_kb": True},
                        ]
                    },
                }
            },
            "channel_partnerships": {
                "label": "Channel Partnerships",
                "capabilities": {
                    "reseller_program": {
                        "label": "Reseller Program",
                        "failures": [
                            {"failure": "Resellers signed but never sell — no enablement, no incentive to push your product", "book": "Crossing the Chasm (Moore)", "in_kb": True},
                            {"failure": "Channel conflict — direct sales team competes with partners", "book": "The Sales Acceleration Formula (Roberge)", "in_kb": True},
                        ]
                    },
                    "integration_partnerships": {
                        "label": "Integration Partnerships",
                        "failures": [
                            {"failure": "Integration is shallow — doesn't provide enough value for either customer base", "book": "Platform Scale (Choudary)", "in_kb": True},
                        ]
                    },
                }
            },
        }
    },

    "growth": {
        "label": "Growth & Expansion",
        "subdomains": {
            "growth_engine": {
                "label": "Growth Engine",
                "capabilities": {
                    "growth_model": {
                        "label": "Growth Model",
                        "failures": [
                            {"failure": "No defined growth model — don't know whether growth is viral, paid, content, or sales-driven", "book": "Traction (Weinberg & Mares)", "in_kb": True},
                            {"failure": "Growth is linear when it should be compounding — no flywheel designed", "book": "Good to Great (Collins)", "in_kb": True},
                        ]
                    },
                    "acquisition_loops": {
                        "label": "Acquisition Loops",
                        "failures": [
                            {"failure": "No viral/referral loop — every customer acquired through paid channels", "book": "Viral Loop (Penenberg)", "in_kb": True},
                            {"failure": "Paid acquisition scales but retention doesn't — growing a leaking bucket", "book": "The Cold Start Problem (Chen)", "in_kb": True},
                        ]
                    },
                }
            },
            "market_expansion": {
                "label": "Market Expansion",
                "capabilities": {
                    "geographic_expansion": {
                        "label": "Geographic Expansion",
                        "failures": [
                            {"failure": "Entering new country as if it's the same as home market — localization ignored", "book": "Playing to Win (Lafley & Martin)", "in_kb": True},
                            {"failure": "Expanding to too many countries at once — spread thin, win nowhere", "book": "Good Strategy/Bad Strategy (Rumelt)", "in_kb": True},
                        ]
                    },
                    "segment_expansion": {
                        "label": "Segment Expansion",
                        "failures": [
                            {"failure": "Moving upmarket without the product/process maturity to serve enterprise", "book": "Crossing the Chasm (Moore)", "in_kb": True},
                            {"failure": "Moving downmarket cannibalizes the core business", "book": "The Innovator's Dilemma (Christensen)", "in_kb": True},
                        ]
                    },
                }
            },
            "product_led_growth": {
                "label": "Product-Led Growth",
                "capabilities": {
                    "self_serve_motion": {
                        "label": "Self-Serve Motion",
                        "failures": [
                            {"failure": "Product can't be tried without talking to sales — PLG impossible", "book": "Product-Led Growth (Bush)", "in_kb": True},
                            {"failure": "Free tier cannibalizes paid — conversion rate too low to sustain", "book": "Product-Led Growth (Bush)", "in_kb": True},
                        ]
                    },
                    "activation_rate": {
                        "label": "Activation Rate",
                        "failures": [
                            {"failure": "Signups are high, activation is 5% — product doesn't deliver the 'aha' fast enough", "book": "Product-Led Growth (Bush)", "in_kb": True},
                        ]
                    },
                }
            },
        }
    },

    "leadership": {
        "label": "Leadership & Management",
        "subdomains": {
            "founder_development": {
                "label": "Founder Development",
                "capabilities": {
                    "self_management": {
                        "label": "Self-Management",
                        "failures": [
                            {"failure": "Founder burnout — working 80-hour weeks with no end in sight", "book": "The Hard Thing About Hard Things (Horowitz)", "in_kb": True},
                            {"failure": "Founder is the bottleneck — every decision routes through them", "book": "The E-Myth Revisited (Gerber)", "in_kb": True},
                            {"failure": "No advisor/peer group — founder has nobody to be honest with", "book": "The Hard Thing About Hard Things (Horowitz)", "in_kb": True},
                            {"failure": "Founder avoids the hardest conversation — letting go of a co-founder or key exec", "book": "The Hard Thing About Hard Things (Horowitz)", "in_kb": True},
                        ]
                    },
                    "decision_making": {
                        "label": "Decision Making",
                        "failures": [
                            {"failure": "Decision paralysis — waiting for perfect information that will never arrive", "book": "Decisive (Heath)", "in_kb": True},
                            {"failure": "Reversible decisions treated as irreversible — massive time wasted", "book": "Decisive (Heath)", "in_kb": True},
                            {"failure": "Decisions not written down — same debates happen every week", "book": "Principles (Dalio)", "in_kb": True},
                        ]
                    },
                    "time_management": {
                        "label": "Time Management",
                        "failures": [
                            {"failure": "Founder doing $15/hour work while $150/hour decisions go unmade", "book": "The E-Myth Revisited (Gerber)", "in_kb": True},
                            {"failure": "Calendar driven by others — founder has no maker time", "book": "High Output Management (Grove)", "in_kb": True},
                            {"failure": "Working IN the business, not ON the business", "book": "The E-Myth Revisited (Gerber)", "in_kb": True},
                        ]
                    },
                }
            },
            "team_leadership": {
                "label": "Team Leadership",
                "capabilities": {
                    "delegation": {
                        "label": "Delegation",
                        "failures": [
                            {"failure": "Micromanaging — founder reviews every code commit / email / slide", "book": "High Output Management (Grove)", "in_kb": True},
                            {"failure": "Abdicating, not delegating — 'you figure it out' without context/support", "book": "High Output Management (Grove)", "in_kb": True},
                            {"failure": "Task-relevant maturity mismatch — giving high autonomy to someone who needs guidance", "book": "High Output Management (Grove)", "in_kb": True},
                        ]
                    },
                    "executive_team": {
                        "label": "Executive Team",
                        "failures": [
                            {"failure": "Executive team doesn't function as a team — siloed, no shared accountability", "book": "The Five Dysfunctions of a Team (Lencioni)", "in_kb": True},
                            {"failure": "CEO making decisions that COO/CTO should make — no real delegation of authority", "book": "High Output Management (Grove)", "in_kb": True},
                            {"failure": "Exec hires from big company backgrounds failing in startup context", "book": "The Hard Thing About Hard Things (Horowitz)", "in_kb": True},
                        ]
                    },
                    "communication": {
                        "label": "Communication",
                        "failures": [
                            {"failure": "Founder communicates strategy once and assumes everyone got it — they didn't", "book": "The Art of Action (Bungay)", "in_kb": True},
                            {"failure": "Bad news doesn't travel up — founder is the last to know about problems", "book": "The Five Dysfunctions of a Team (Lencioni)", "in_kb": True},
                            {"failure": "All-hands are status updates, not context-sharing — team doesn't know WHY, only WHAT", "book": "The Art of Action (Bungay)", "in_kb": True},
                        ]
                    },
                }
            },
            "organizational_design": {
                "label": "Organizational Design",
                "capabilities": {
                    "structure": {
                        "label": "Org Structure",
                        "failures": [
                            {"failure": "Org design is whatever happened organically — no intentional choices about spans, layers, functions", "book": "High Output Management (Grove)", "in_kb": True},
                            {"failure": "Functional silos — product, engineering, sales don't talk to each other", "book": "Team of Teams (McChrystal)", "in_kb": True},
                            {"failure": "Too many direct reports — manager can't give attention to anyone", "book": "High Output Management (Grove)", "in_kb": True},
                        ]
                    },
                    "scaling_structure": {
                        "label": "Scaling Structure",
                        "failures": [
                            {"failure": "Structure that worked at 20 people breaks at 50 — no redesign planned", "book": "High Output Management (Grove)", "in_kb": True},
                            {"failure": "Adding management layers without clear decision rights — bureaucracy without clarity", "book": "High Output Management (Grove)", "in_kb": True},
                        ]
                    },
                }
            },
        }
    },
}


# === Summary stats ===
def taxonomy_stats():
    total_failures = 0
    kb_covered = 0
    kb_gaps = 0
    unique_books = set()
    for func_name, func_data in PROBLEM_TAXONOMY.items():
        for sd_name, sd_data in func_data["subdomains"].items():
            for cap_name, cap_data in sd_data["capabilities"].items():
                for f in cap_data["failures"]:
                    total_failures += 1
                    if f["in_kb"]:
                        kb_covered += 1
                    else:
                        kb_gaps += 1
                    unique_books.add(f["book"])
    return {
        "functions": len(PROBLEM_TAXONOMY),
        "total_failures": total_failures,
        "kb_covered": kb_covered,
        "kb_gaps": kb_gaps,
        "coverage_pct": round(kb_covered / total_failures * 100, 1) if total_failures else 0,
        "unique_books_referenced": len(unique_books),
    }


if __name__ == "__main__":
    stats = taxonomy_stats()
    print(f"Functions: {stats['functions']}")
    print(f"Total failure modes: {stats['total_failures']}")
    print(f"Knowledge base covered: {stats['kb_covered']} ({stats['coverage_pct']}%)")
    print(f"Knowledge base gaps: {stats['kb_gaps']}")
    print(f"Unique books referenced: {stats['unique_books_referenced']}")


# === Wire 1: Function → Lens ID mapping for health-weighted lens selection ===
def build_function_lens_map():
    """Map each business function to its relevant lens IDs, derived from the taxonomy.
    Returns dict: function_name -> set of lens_id strings."""
    try:
        from lenses import MODULES
    except ImportError:
        return {}
    lens_book_to_id = {}
    for m in MODULES:
        book_clean = m.get('book', '').split(' (')[0].strip().lower()
        lens_book_to_id[book_clean] = m.get('id', '')

    func_lens = {}
    for fn_name, fn_data in PROBLEM_TAXONOMY.items():
        lids = set()
        for sd in fn_data['subdomains'].values():
            for cap in sd['capabilities'].values():
                for fm in cap['failures']:
                    fm_clean = fm['book'].split(' (')[0].split(' —')[0].strip().lower()
                    lid = lens_book_to_id.get(fm_clean)
                    if lid:
                        lids.add(lid)
        if lids:
            func_lens[fn_name] = lids
    return func_lens


# ponytail: cached at module load, rebuild on lens updates
# Cached function-to-lens mapping for taxonomy-aware selection
_FUNCTION_LENS_MAP = None

def function_lens_map():
    global _FUNCTION_LENS_MAP
    if _FUNCTION_LENS_MAP is None:
        _FUNCTION_LENS_MAP = build_function_lens_map()
    return _FUNCTION_LENS_MAP
