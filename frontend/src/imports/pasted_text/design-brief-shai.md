## DESIGN BRIEF: Self-Healing Workflow AI — Mission Control Dashboard

### PROJECT OVERVIEW
Design a complete, production-grade UI for an autonomous AI system that monitors
Apache Airflow pipelines, detects failures, and auto-applies configuration patches.
Users are DevOps engineers and SREs who need to monitor, approve, and audit AI-driven
infrastructure repairs in real time.

### DESIGN IDENTITY: "Industrial Terminal"
This is mission-critical infrastructure software — not a SaaS product.
The design must feel like a NASA mission control room, not a startup dashboard.
Every visual decision must be justified by function. No decoration for decoration's sake.

Aesthetic keywords: industrial · monochrome-first · data-dense · high-contrast · authoritative
Mood reference: Bloomberg Terminal meets GitHub Dark meets Grafana
What makes it unforgettable: The color only appears when something HAPPENS.
Static state is all dark grays. A failure turns red. A repair in progress glows amber.
A successful patch snaps to teal-green. The UI itself communicates system state
without the user reading a single word.

### LOADING SCREEN (Design This First — It's the First Impression)
This is a Docker-based system. On startup it must: boot containers → load ML model
→ connect FAISS index → verify LLM API → declare ready.

Design a full-screen loading experience with:
Background: #0a0c0f with a subtle animated grid (very low opacity lines, slowly drifting)
Center logo: Text "SH-AI" in JetBrains Mono bold, 72px, color #00d4aa.
              Below it: "SELF-HEALING WORKFLOW AI" in 10px, letter-spacing 0.4em,
              color #4a5a6a
Progress system (4 sequential stages, each with its own row):
  Stage 1 — "INITIALIZING DOCKER SERVICES"     → shows: containers spinning up
  Stage 2 — "LOADING ML CLASSIFIER"            → shows: model file size, accuracy metric
  Stage 3 — "BUILDING FAISS INDEX"             → shows: index size, vector count
  Stage 4 — "CONNECTING LLM API"               → shows: provider name (Groq), latency ping
Each stage row has:
  - A mono label (stage name, left-aligned)
  - A thin amber progress bar that fills left-to-right
  - A status indicator: spinning dots while loading, green checkmark when done
  - A small detail line: "pipeline.pkl — 2.3 MB" / "playbook.faiss — 847 vectors"
When all 4 complete: the progress rows fade out, the logo scales up slightly,
and a green "SYSTEM READY" text fades in below. Then the dashboard cross-fades in.

### COLOR SYSTEM (Non-Negotiable — Must Match These Exactly)
CSS Variables to use:
  --bg:        #0a0c0f   ← Page background (only color used)
  --surface:   #111418   ← Card / panel fill
  --surface2:  #161b22   ← Secondary panel, table header
  --border:    #1e2530   ← Default border
  --border-lit:#2a3540   ← Hover/active border
  --text:      #d0d8e4   ← Primary text
  --muted:     #4a5a6a   ← Labels, metadata, timestamps
  --teal:      #00d4aa   ← Primary action, success, system-ready (the hero accent)
  --failure:   #ef4444   ← Error states, rejection, critical failure
  --active:    #f59e0b   ← Processing, pending, in-progress
  --data:      #3b82f6   ← Informational, neutral data, missing_file class
  --ai:        #8b5cf6   ← AI / LLM outputs, ML scores, repair plans
  --healthy:   #10b981   ← Applied/passed/approved states
Failure class color mapping (use exactly):
  timeout → #f59e0b (amber)    http_error → #ef4444 (red)
  missing_file → #3b82f6 (blue)  missing_column → #8b5cf6 (purple)
  missing_db → #f97316 (orange)

### TYPOGRAPHY SYSTEM
Primary font:  JetBrains Mono — ALL text in the app (monospace = technical authority)
Heading font:  Syne (700, 800 weight) — page titles and section labels ONLY
Font sizes:    9px labels · 11px body · 13px values · 15px subheads · 20–28px headings
Letter spacing:0.2–0.3em on uppercase labels (creates the terminal feel)
NO Inter, Roboto, or system fonts anywhere.

### LAYOUT RULES
- Left sidebar: 220px fixed width, dark #0d1014 background
- Content area: fluid, min 800px, 24px padding
- Max card width: 100% of content area
- Border radius: 0–2px ONLY. No rounded corners. Sharp edges throughout.
- 1px borders on all panels. No drop shadows except 0 0 0 1px glow on active elements.
- Grid: 12-column, 16px gutters

### SIDEBAR NAVIGATION
Design a left sidebar (220px) with:
Top: "SH-AI" wordmark in 14px JetBrains Mono bold, teal color
     Below: "SELF-HEALING v1.0" in 9px muted
Navigation items (icon + label, vertical list):
  ⬡ Dashboard      → /
  ⬡ Episodes       → /episodes
  ⬡ Repair Plans   → /plans
  ⬡ Review Queue   → /review     ← shows a red badge with pending count
  ⬡ Audit Trail    → /audit
  ⬡ Rollback       → /rollback
  ⬡ Intelligence   → /intelligence
  ⬡ Settings       → /settings
Bottom of sidebar: System status indicator showing:
  ● OPERATIONAL (green dot) or ● DEGRADED (red dot)
  "Last sync: 2 min ago"

### SCREEN 1: DASHBOARD (HOME)
Top row — 4 KPI cards (equal width):
  Card 1: Total Episodes      → large number, subtitle "last 24h"
  Card 2: Auto-Patch Rate     → percentage + trend arrow
  Card 3: MTTR               → "4.2 min" + subtitle "mean time to repair"
  Card 4: Pending Review      → count with amber warning if > 0
Each KPI card: surface2 background, 1px border, no radius, teal top-border 2px,
number in 36px Syne 800, label in 9px muted uppercase.

Middle section — 2 columns:
  Left (60%): Failure Class Distribution — horizontal bar chart, one bar per class,
              colored with class colors above, bars are thin (8px height),
              percentage label right-aligned, count left-aligned.
  Right (40%): Recent Activity Feed — scrollable list of events.
               Each event: timestamp (muted mono) + icon + one-line description.
               Event types: 🔴 failure detected / 🟡 plan generated / 🟢 patch applied /
               ⚪ human approved / 🔵 rollback executed

Bottom row — Safety Threshold Status:
  3 horizontal gauge bars labeled: "Confidence Threshold (0.50)" / "Auto-patch rate (80%)" /
  "Human approval required (< 0.50 confidence)"
  Each gauge: thin track, filled portion in teal, threshold marker line

### SCREEN 2: EPISODES LIST
Full-width sortable table. Columns:
  Episode ID (mono, muted) · DAG · Task · Failure Class (colored pill) ·
  Confidence (mini bar + number) · ML∩Regex (checkmark or X) · Status · Actions
Table rows: 40px height, hover state lights the border-left 2px in teal.
Above table: Filter bar with dropdowns for failure_class, dag_id, status, and a search input.
Pagination: bottom-right, "Showing 1–20 of 60" style.
Clicking a row opens a slide-in detail panel from the right (400px, overlay on content).

### SCREEN 3: EPISODE DETAIL (SLIDE-IN PANEL OR FULL PAGE)
Two-column layout:
  Left: Log Viewer — dark terminal panel (#080b0e) with the raw log_excerpt.
        Syntax highlight: error class names in red, file paths in blue,
        timeout values in amber, numbers in orange.
        Above log: Drain template extraction box (surface2 bg, purple border-left)
                   showing: template string with <*> wildcards highlighted.
  Right: Classification Result
        - Failure class pill (large, colored)
        - Confidence circular gauge (SVG, 0-100%)
        - "Regex Classifier: ✓ timeout" badge
        - "ML Classifier: ✓ timeout (0.97)" badge
        - Agreement status: "✓ BOTH CLASSIFIERS AGREE" in teal
        Below: Top-3 FAISS playbook entries (similarity score + entry text)

### SCREEN 4: REPAIR PLAN LIST
Card-based grid (2 columns). Each plan card:
  Header: plan_id in mono + failure_class pill
  Body: confidence gauge (mini, horizontal bar) + reasoning (2 lines, truncated)
  Footer: action count "3 actions" + requires_human badge (amber warning if true)
  Right edge: status badge (pending / applied / rejected / dry_run)

### SCREEN 5: PLAN DETAIL + DIFF VIEWER
This is the most important screen. Three-zone layout:
Zone A (top): Plan header
  - plan_id + failure_class + timestamp
  - Large circular confidence gauge (SVG, 120px, colored by threshold)
  - Reasoning text block (surface2 bg, left border in --ai color)
  - requires_human_approval: red warning banner if true

Zone B (middle): Repair Actions list
  Each action shown as a row:
  [OPERATOR BADGE] → param name → "=" → new value → justification (italic, muted)
  Operator badge colors: set_env=blue / set_retry=amber / set_timeout=amber /
                         replace_path=data-blue / add_precheck=purple

Zone C (bottom): File Diff Viewer — GitHub style, side by side
  Left panel (removed lines): dark red tint background (#1a0808), lines prefixed "−" in red
  Right panel (added lines): dark green tint background (#081a0e), lines prefixed "+" in teal
  File name shown in header bar of the diff panel
  Unchanged context lines: muted color

Below the diff: Action bar
  [✓ APPROVE]  button: teal fill, white text, full width or prominent
  [✗ REJECT]   button: outlined, red border, text input appears below for reason
  [DRY RUN]    button: outlined, muted, shows diff without committing
  After approve: 5-second toast with "UNDO" option in top-right corner

### SCREEN 6: REVIEW QUEUE
Only shows plans where requires_human_approval = true AND status = pending.
Empty state: "✓ NO PENDING REVIEWS" — large teal checkmark, short message, minimal.
Populated: same plan cards as Screen 4 but with prominent approve/reject buttons on card.
Top: bulk action bar "Select All → Approve All / Reject All" (requires confirmation modal)

### SCREEN 7: AUDIT TRAIL
Vertical timeline. Each event is a row:
  Left: colored dot (red=failure / amber=plan / teal=applied / blue=rollback)
        + vertical connecting line between events
  Center: event description + entity ID (mono, clickable link to episode/plan)
  Right: timestamp in muted mono + git commit hash if applicable (6 chars, monospace)
Filter bar above: DAG dropdown · Status dropdown · Date range picker
Bottom: "EXPORT MARKDOWN REPORT" button → downloads audit_report.md

### SCREEN 8: ROLLBACK MANAGER
Table of all applied patches: patch_id · file modified · applied_at · git_commit_hash
Each row has: [DRY RUN] and [ROLLBACK] buttons
Click Rollback → modal appears showing:
  - "You are about to revert: plan_ep_039"
  - Affected files list
  - Git command preview: "git revert {hash}"
  - [CONFIRM ROLLBACK] and [CANCEL] buttons

### SCREEN 9: SETTINGS
Three sections separated by horizontal rules:
1. Safety Thresholds — sliders (0.0 to 1.0) for:
   confidence_threshold / high_confidence_auto_apply / require_human_threshold
2. API Configuration — masked text inputs for GROQ_API_KEY / OPENAI_API_KEY
   Show last 4 chars only. "Reveal" eye button. "Test Connection" button.
3. System Controls — toggle switches:
   AUTO_PATCH_ENABLED · DRY_RUN_MODE · AUDIT_LOGGING

### SCREEN 10: INTELLIGENCE (Model Dashboard)
Row 1: 4 metric cards — Test Accuracy · Train Accuracy · Total Episodes · Model File
Row 2: Two image panels: confusion_matrix.png | accuracy_plot.png (loaded from backend)
Row 3: SVG donut chart — failure class distribution (5 slices, class colors)
Row 4: Classifier agreement rate — "Regex + ML agreed on 58/60 episodes (96.7%)"

### COMPONENT SPECIFICATIONS
StatusBadge: 8px text, 0.15em letter-spacing, 4px 10px padding, 1px border, 2px radius.
              Colors: pending=amber / applied=healthy / rejected=failure / dry_run=data
ConfidenceGauge (circular): SVG circle, stroke-dasharray animated on mount.
              < 0.3 → red, 0.3–0.5 → amber, ≥ 0.5 → teal/green
DataTable rows: 40px, 1px bottom border, hover: background #161b22
Toast notification: bottom-right, dark surface, colored left border, auto-dismiss 4s
Modal: centered, dark backdrop (rgba 0,0,0,0.7), surface2 background, sharp corners
Button variants: Primary=teal fill · Destructive=red fill · Ghost=transparent+border · Icon=32px square

### DELIVERABLES REQUESTED FROM FIGMA
1. Loading screen (full resolution)
2. All 9 screens at 1440px desktop width
3. Component library frame: all badges, buttons, gauges, toasts, modals
4. Sidebar navigation states: default + active + hover
5. Table row states: default + hover + selected
6. Mobile responsive variants for Dashboard and Review Queue (375px)

CRITICAL DESIGN RULES:
- Zero purple-on-white gradients. Zero rounded hero images. Zero stock-photo backgrounds.
- Every color must be from the defined palette — no improvisation.
- Data must look like data. Terminals must look like terminals.
- The user should feel like they're watching a real system think, not browsing a website.