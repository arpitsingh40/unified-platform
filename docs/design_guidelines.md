{
  "brand": {
    "name": "SmartDecigen",
    "attributes": [
      "calm instrument",
      "premium minimal",
      "goal-anchored accountability",
      "text-first",
      "not-a-chatbot",
      "quietly directive"
    ],
    "north_star": "User leaves doing the one next action they already knew they needed to do."
  },
  "critical_product_rules": {
    "no_scrolling_chat_primary": true,
    "primary_ui": "Single-pane Situation Pane with 4 living fields + composer",
    "history": "Hidden behind 'Show history' expander (collapsed by default)",
    "no_chat_bubbles": true,
    "next_action_is_hero": true
  },
  "design_personality": {
    "style_fusion": [
      "Superhuman-like typographic crispness",
      "Linear-like restraint + spacing",
      "Notion-like calm surfaces",
      "Luxury editorial micro-contrast (hairlines, subtle shadows)"
    ],
    "layout_principle": "Single dominant surface per screen; progressive disclosure for everything else.",
    "density": "Low density; 2–3x more whitespace than comfortable.",
    "anti_patterns": [
      "chat transcript as main UI",
      "message bubbles",
      "gamified progress",
      "loud gradients",
      "emoji icons"
    ]
  },
  "typography": {
    "font_pairing": {
      "display": {
        "name": "Gloock",
        "usage": "H1 / key moments (Next Action label, auth headline)",
        "google_fonts": "https://fonts.google.com/specimen/Gloock"
      },
      "sans": {
        "name": "IBM Plex Sans",
        "usage": "UI body, labels, inputs, dashboard",
        "google_fonts": "https://fonts.google.com/specimen/IBM+Plex+Sans"
      },
      "mono_optional": {
        "name": "IBM Plex Mono",
        "usage": "timestamps in history, credits microtext",
        "google_fonts": "https://fonts.google.com/specimen/IBM+Plex+Mono"
      }
    },
    "tailwind_notes": {
      "implementation": "Add fonts via index.html <link> or @import in index.css; set body font-family to IBM Plex Sans; use Gloock via utility class on headings.",
      "classes": {
        "display": "font-[\"Gloock\",serif]",
        "sans": "font-[\"IBM Plex Sans\",system-ui,sans-serif]",
        "mono": "font-mono"
      }
    },
    "type_scale": {
      "h1": "text-4xl sm:text-5xl lg:text-6xl",
      "h2": "text-base md:text-lg",
      "body": "text-sm md:text-base",
      "small": "text-xs text-muted-foreground",
      "line_heights": {
        "display": "leading-[1.05]",
        "body": "leading-6",
        "compact": "leading-5"
      },
      "letter_spacing": {
        "display": "tracking-[-0.02em]",
        "ui": "tracking-[-0.01em]"
      }
    }
  },
  "color_system": {
    "notes": "Ultra-minimal, premium, mostly neutral. Accent is a muted ocean-teal used sparingly for focus rings, selected states, and pace indicators. No purple.",
    "tokens_css_variables": {
      "root": {
        "--background": "36 33% 98%",
        "--foreground": "222 22% 12%",
        "--card": "0 0% 100%",
        "--card-foreground": "222 22% 12%",
        "--popover": "0 0% 100%",
        "--popover-foreground": "222 22% 12%",
        "--primary": "222 22% 12%",
        "--primary-foreground": "0 0% 98%",
        "--secondary": "36 20% 95%",
        "--secondary-foreground": "222 22% 12%",
        "--muted": "36 18% 94%",
        "--muted-foreground": "222 10% 42%",
        "--accent": "186 42% 92%",
        "--accent-foreground": "222 22% 12%",
        "--border": "30 12% 88%",
        "--input": "30 12% 88%",
        "--ring": "186 55% 38%",
        "--destructive": "0 72% 52%",
        "--destructive-foreground": "0 0% 98%",
        "--radius": "0.75rem"
      },
      "semantic_additions": {
        "--success": "162 45% 34%",
        "--warning": "38 92% 45%",
        "--info": "186 55% 38%",
        "--surface": "36 33% 98%",
        "--surface-2": "36 20% 95%",
        "--hairline": "30 12% 88%"
      }
    },
    "palette_hex_reference": {
      "paper": "#FBFAF7",
      "ink": "#1A1F2A",
      "muted_ink": "#5B6472",
      "hairline": "#E6E0D6",
      "teal_focus": "#2F8F8A",
      "teal_wash": "#DDF1EF",
      "success": "#2F7D63",
      "warning": "#D08A00",
      "danger": "#D64545"
    },
    "gradients": {
      "allowed_usage": "Decorative section backgrounds only (<=20% viewport). Never on text-heavy panes/cards.",
      "hero_background": "radial-gradient(1200px 600px at 20% 0%, rgba(47,143,138,0.10), transparent 55%), radial-gradient(900px 500px at 90% 10%, rgba(208,138,0,0.08), transparent 60%)",
      "restriction": "No saturated/dark gradients; no purple/pink combos; no gradients on small UI elements (<100px)."
    }
  },
  "spacing_grid": {
    "container": {
      "max_width": "max-w-5xl",
      "page_padding": "px-4 sm:px-6 lg:px-8",
      "vertical_rhythm": "py-8 sm:py-10"
    },
    "grid": {
      "dashboard": "grid grid-cols-1 md:grid-cols-2 gap-4 lg:gap-6",
      "situation_pane": "single column; internal sections separated by hairline separators and spacing (space-y-6)"
    },
    "radius_shadow": {
      "radius": "rounded-xl (cards), rounded-2xl (hero surface)",
      "shadow": "shadow-[0_1px_0_rgba(17,24,39,0.06),0_12px_30px_rgba(17,24,39,0.06)] (premium lift)",
      "hairline": "border border-border/70"
    }
  },
  "components": {
    "component_path": {
      "shadcn_primary": "/app/frontend/src/components/ui",
      "use_components": [
        {
          "name": "Button",
          "path": "src/components/ui/button.jsx"
        },
        {
          "name": "Card",
          "path": "src/components/ui/card.jsx"
        },
        {
          "name": "Input",
          "path": "src/components/ui/input.jsx"
        },
        {
          "name": "Textarea",
          "path": "src/components/ui/textarea.jsx"
        },
        {
          "name": "Badge",
          "path": "src/components/ui/badge.jsx"
        },
        {
          "name": "Separator",
          "path": "src/components/ui/separator.jsx"
        },
        {
          "name": "Collapsible",
          "path": "src/components/ui/collapsible.jsx"
        },
        {
          "name": "ScrollArea",
          "path": "src/components/ui/scroll-area.jsx"
        },
        {
          "name": "DropdownMenu",
          "path": "src/components/ui/dropdown-menu.jsx"
        },
        {
          "name": "Skeleton",
          "path": "src/components/ui/skeleton.jsx"
        },
        {
          "name": "Sonner Toast",
          "path": "src/components/ui/sonner.jsx"
        },
        {
          "name": "Dialog",
          "path": "src/components/ui/dialog.jsx"
        }
      ]
    },
    "button_system": {
      "tokens": {
        "--btn-radius": "12px",
        "--btn-shadow": "0 1px 0 rgba(17,24,39,0.06)",
        "--btn-press-scale": "0.98"
      },
      "variants": {
        "primary": {
          "intent": "Commit / Send / Start goal",
          "tailwind": "rounded-xl bg-primary text-primary-foreground shadow-[0_1px_0_rgba(17,24,39,0.06)] hover:bg-primary/92 focus-visible:ring-2 focus-visible:ring-[hsl(var(--ring))] focus-visible:ring-offset-2 active:scale-[0.98] transition-colors",
          "data_testid_examples": [
            "auth-submit-button",
            "new-goal-create-button",
            "composer-send-button"
          ]
        },
        "secondary": {
          "intent": "Show history / Cancel",
          "tailwind": "rounded-xl bg-secondary text-secondary-foreground hover:bg-secondary/70 border border-border/70 active:scale-[0.98] transition-colors",
          "data_testid_examples": [
            "history-toggle-button",
            "new-goal-cancel-button"
          ]
        },
        "ghost": {
          "intent": "Account menu / subtle actions",
          "tailwind": "rounded-xl hover:bg-muted/70 active:scale-[0.98] transition-colors",
          "data_testid_examples": [
            "account-menu-button"
          ]
        }
      }
    },
    "badges": {
      "status_badge": {
        "active": "bg-[hsl(var(--accent))] text-foreground border border-border/70",
        "paused": "bg-muted text-muted-foreground border border-border/70",
        "graduated": "bg-secondary text-foreground border border-border/70",
        "released": "bg-transparent text-muted-foreground border border-border/70"
      },
      "pace_indicator": {
        "ahead": "text-[hsl(var(--success))] bg-transparent",
        "on_track": "text-[hsl(var(--info))] bg-transparent",
        "behind": "text-[hsl(var(--warning))] bg-transparent",
        "pattern": "Use Badge with variant='outline' and only change text color; avoid filled gamified chips."
      }
    }
  },
  "page_layouts": {
    "auth": {
      "goal": "Premium first impression; calm commitment.",
      "layout": "Split minimal: left is brand + 1 sentence promise; right is a single Card form. On mobile: single column.",
      "background": "Use paper tone with subtle noise overlay; no big gradients.",
      "components": ["Card", "Input", "Button", "Label"],
      "data_testids": [
        "login-email-input",
        "login-password-input",
        "login-submit-button",
        "signup-email-input",
        "signup-password-input",
        "signup-submit-button"
      ]
    },
    "goals_dashboard": {
      "layout": "Top bar (title left, credits + account menu right). Below: grid of goal cards.",
      "goal_card": {
        "structure": "Title (1 line), status badge + pace indicator row, next action preview (muted), CTA 'Open'.",
        "components": ["Card", "Badge", "Button", "Separator"],
        "data_testids": [
          "goals-new-goal-button",
          "goal-card-open-button",
          "credits-balance"
        ]
      }
    },
    "new_goal_flow": {
      "tone": "Commitment ceremony, not a form.",
      "layout": "Centered narrow column (max-w-xl) but NOT text-centered; left-aligned text. Use a single Card with generous padding.",
      "fields": [
        "What is the goal? (short)",
        "Why now? (textarea)"
      ],
      "microcopy": "Use calm, directive prompts. Example: 'Name it plainly.' / 'Why does this matter this week?'",
      "data_testids": [
        "new-goal-title-input",
        "new-goal-why-textarea",
        "new-goal-create-button"
      ]
    },
    "goal_thread_situation_pane": {
      "core_screen": true,
      "layout": {
        "top_bar": "Goal title left; credits + account menu right. Optional breadcrumb back to dashboard.",
        "pane": "One large Card-like surface (rounded-2xl) containing the 4 living fields + composer.",
        "history": "Collapsible at bottom; when expanded, show ScrollArea with raw log."
      },
      "situation_fields": {
        "re_engagement_line": {
          "placement": "Top of pane, above Current State",
          "style": "text-sm text-muted-foreground border-l-2 border-[hsl(var(--ring))]/40 pl-3",
          "data_testid": "reengagement-line"
        },
        "current_state": {
          "label": "Current state",
          "content": "Clamp to 3 lines; show subtle 'last updated' microtext.",
          "style": "text-sm md:text-base leading-6",
          "data_testid": "situation-current-state"
        },
        "easiest_path": {
          "label": "Easiest path",
          "content": "1–2 lines; should read like a gentle instruction.",
          "style": "text-sm md:text-base text-foreground",
          "data_testid": "situation-easiest-path"
        },
        "next_action": {
          "label": "Next action (24–48h)",
          "content": "1 line; the hero element.",
          "style": "mt-2 rounded-xl bg-[hsl(var(--accent))]/60 border border-border/70 px-4 py-3 text-base md:text-lg font-[\"Gloock\",serif] tracking-[-0.02em]",
          "data_testid": "situation-next-action"
        },
        "open_question": {
          "label": "Open question",
          "content": "1 line pinned directly above composer.",
          "style": "text-sm text-muted-foreground",
          "data_testid": "situation-open-question"
        }
      },
      "composer": {
        "pattern": "Single textarea + send button; no chat bubbles. Enter sends, Shift+Enter newline.",
        "components": ["Textarea", "Button"],
        "style": "Textarea: min-h-[96px] rounded-xl bg-white border border-border/70 focus-visible:ring-2 focus-visible:ring-[hsl(var(--ring))]",
        "data_testids": [
          "composer-textarea",
          "composer-send-button"
        ]
      },
      "history_expander": {
        "components": ["Collapsible", "ScrollArea", "Separator"],
        "style": "Collapsed shows a hairline + 'Show history' button. Expanded reveals log with timestamps in mono.",
        "data_testids": [
          "history-toggle-button",
          "history-scroll-area"
        ]
      }
    }
  },
  "motion_microinteractions": {
    "principles": [
      "Motion communicates state changes (thinking, refreshed fields), never decoration.",
      "Prefer opacity + translateY(2-4px) + blur(2px) for refresh moments.",
      "Respect prefers-reduced-motion."
    ],
    "field_refresh_transition": {
      "intent": "When engine responds, the 4 fields update in place with a subtle 'situation evolved' moment.",
      "implementation_hint": {
        "approach": "Wrap each field in a div that toggles data-state='updating' for 250–400ms; animate opacity and slight translate.",
        "css_snippet": "[data-refresh='true']{opacity:0; transform:translateY(4px); filter:blur(2px);} [data-refresh='false']{opacity:1; transform:translateY(0); filter:blur(0); transition:opacity 260ms ease, transform 260ms ease, filter 260ms ease;}"
      }
    },
    "thinking_state": {
      "tone": "Calm processing, no spinner spam.",
      "pattern": "Inline 'Processing…' microtext + subtle skeleton shimmer on the 4 fields (not full-page).",
      "components": ["Skeleton"],
      "duration": "5–9s typical",
      "data_testid": "engine-thinking-state"
    },
    "hover_focus": {
      "buttons": "hover:bg change only; active scale 0.98; focus ring teal.",
      "cards": "hover:shadow slightly stronger; border darkens by 5–8%",
      "avoid": "transition: all"
    }
  },
  "accessibility": {
    "contrast": "All text must meet WCAG AA; muted text still readable on paper background.",
    "keyboard": [
      "Composer textarea focus visible ring",
      "Enter to send; Shift+Enter newline",
      "History expander togglable via keyboard",
      "Dropdown menu navigable"
    ],
    "aria": {
      "history": "Collapsible trigger must have aria-expanded",
      "thinking": "Use aria-live='polite' for processing status"
    }
  },
  "libraries": {
    "recommended": [
      {
        "name": "framer-motion",
        "why": "Elegant field refresh transitions + reduced-motion handling",
        "install": "npm i framer-motion",
        "usage": "Use <AnimatePresence> and motion.div for field refresh; keep durations 0.26–0.4s; avoid springy playful motion."
      },
      {
        "name": "lucide-react",
        "why": "Minimal icons for account menu, chevrons, history",
        "install": "npm i lucide-react",
        "usage": "Use icons at 16–18px, strokeWidth=1.75; never emojis."
      }
    ]
  },
  "image_urls": {
    "background_texture": [
      {
        "url": "https://images.unsplash.com/photo-1601662528567-526cd06f6582?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NTYxODh8MHwxfHNlYXJjaHwxfHxtaW5pbWFsJTIwcHJlbWl1bSUyMGFic3RyYWN0JTIwcGFwZXIlMjB0ZXh0dXJlJTIwbGlnaHR8ZW58MHx8fHdoaXRlfDE3ODExMzU1MDN8MA&ixlib=rb-4.1.0&q=85",
        "category": "global background",
        "description": "Subtle paper texture for auth + dashboard background overlay (very low opacity)."
      },
      {
        "url": "https://images.unsplash.com/photo-1604147706283-d7119b5b822c?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NTYxODh8MHwxfHNlYXJjaHwyfHxtaW5pbWFsJTIwcHJlbWl1bSUyMGFic3RyYWN0JTIwcGFwZXIlMjB0ZXh0dXJlJTIwbGlnaHR8ZW58MHx8fHdoaXRlfDE3ODExMzU1MDN8MA&ixlib=rb-4.1.0&q=85",
        "category": "global background",
        "description": "Alternative plaster texture; use for subtle noise-like depth behind the Situation Pane."
      }
    ]
  },
  "instructions_to_main_agent": {
    "global_css_updates": [
      "Replace CRA default App.css styles; remove centered App-header patterns.",
      "In index.css :root, update HSL tokens to the provided palette; keep shadcn structure.",
      "Add a subtle noise/paper texture via ::before overlay on body or main layout wrapper (opacity 0.06–0.10).",
      "Do NOT use gradients beyond the allowed hero background and keep it under 20% viewport."
    ],
    "situation_pane_build": [
      "Implement Situation Pane as a single Card surface with internal sections separated by Separator and spacing.",
      "Render the 4 living fields as structured blocks (label + content), not messages.",
      "When engine responds, update fields in place and trigger refresh animation (framer-motion or CSS data attribute).",
      "Keep history collapsed by default using Collapsible; history content inside ScrollArea.",
      "Next Action block must be visually dominant (accent wash background + display font)."
    ],
    "testing_requirements": [
      "Add data-testid to every interactive element (buttons, inputs, textarea, menu triggers) and key informational elements (credits balance, next action, thinking state, re-engagement line).",
      "Use kebab-case test ids describing role (not appearance)."
    ],
    "js_files_note": "All components/pages are .js/.jsx; do not write .tsx guidance. Use named exports for components and default exports for pages."
  },
  "general_ui_ux_design_guidelines": "- You must **not** apply universal transition. Eg: `transition: all`. This results in breaking transforms. Always add transitions for specific interactive elements like button, input excluding transforms\n- You must **not** center align the app container, ie do not add `.App { text-align: center; }` in the css file. This disrupts the human natural reading flow of text\n- NEVER: use AI assistant Emoji characters like`🤖🧠💭💡🔮🎯📚🎭🎬🎪🎉🎊🎁🎀🎂🍰🎈🎨🎰💰💵💳🏦💎🪙💸🤑📊📈📉💹🔢🏆🥇 etc for icons. Always use **FontAwesome cdn** or **lucid-react** library already installed in the package.json\n\n **GRADIENT RESTRICTION RULE**\nNEVER use dark/saturated gradient combos (e.g., purple/pink) on any UI element.  Prohibited gradients: blue-500 to purple 600, purple 500 to pink-500, green-500 to blue-500, red to pink etc\nNEVER use dark gradients for logo, testimonial, footer etc\nNEVER let gradients cover more than 20% of the viewport.\nNEVER apply gradients to text-heavy content or reading areas.\nNEVER use gradients on small UI elements (<100px width).\nNEVER stack multiple gradient layers in the same viewport.\n\n**ENFORCEMENT RULE:**\n    • Id gradient area exceeds 20% of viewport OR affects readability, **THEN** use solid colors\n\n**How and where to use:**\n   • Section backgrounds (not content backgrounds)\n   • Hero section header content. Eg: dark to light to dark color\n   • Decorative overlays and accent elements only\n   • Hero section with 2-3 mild color\n   • Gradients creation can be done for any angle say horizontal, vertical or diagonal\n\n- For AI chat, voice application, **do not use purple color. Use color like light green, ocean blue, peach orange etc**\n\n</Font Guidelines>\n\n- Every interaction needs micro-animations - hover states, transitions, parallax effects, and entrance animations. Static = dead. \n   \n- Use 2-3x more spacing than feels comfortable. Cramped designs look cheap.\n\n- Subtle grain textures, noise overlays, custom cursors, selection states, and loading animations: separates good from extraordinary.\n   \n- Before generating UI, infer the visual style from the problem statement (palette, contrast, mood, motion) and immediately instantiate it by setting global design tokens (primary, secondary/accent, background, foreground, ring, state colors), rather than relying on any library defaults. Don't make the background dark as a default step, always understand problem first and define colors accordingly\n    Eg: - if it implies playful/energetic, choose a colorful scheme\n           - if it implies monochrome/minimal, choose a black–white/neutral scheme\n\n**Component Reuse:**\n\t- Prioritize using pre-existing components from src/components/ui when applicable\n\t- Create new components that match the style and conventions of existing components when needed\n\t- Examine existing components to understand the project's component patterns before creating new ones\n\n**IMPORTANT**: Do not use HTML based component like dropdown, calendar, toast etc. You **MUST** always use `/app/frontend/src/components/ui/ ` only as a primary components as these are modern and stylish component\n\n**Best Practices:**\n\t- Use Shadcn/UI as the primary component library for consistency and accessibility\n\t- Import path: ./components/[component-name]\n\n**Export Conventions:**\n\t- Components MUST use named exports (export const ComponentName = ...)\n\t- Pages MUST use default exports (export default function PageName() {...})\n\n**Toasts:**\n  - Use `sonner` for toasts\"\n  - Sonner component are located in `/app/src/components/ui/sonner.tsx`\n\nUse 2–4 color gradients, subtle textures/noise overlays, or CSS-based noise to avoid flat visuals."
}
