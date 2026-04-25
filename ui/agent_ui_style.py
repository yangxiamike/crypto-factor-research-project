from __future__ import annotations

from dataclasses import dataclass
from html import escape
from typing import Final


@dataclass(frozen=True)
class StatusStyle:
    label: str
    bg: str
    fg: str
    border: str
    dot: str


STATUS_STYLES: Final[dict[str, StatusStyle]] = {
    "waiting": StatusStyle("等待输入", "#EEF2FF", "#3730A3", "#C7D2FE", "#6366F1"),
    "generating": StatusStyle("Agent 生成中", "#ECFEFF", "#155E75", "#A5F3FC", "#06B6D4"),
    "review": StatusStyle("待审核", "#FFF7ED", "#9A3412", "#FED7AA", "#FB923C"),
    "running": StatusStyle("执行中", "#FDF4FF", "#7E22CE", "#E9D5FF", "#A855F7"),
    "stored": StatusStyle("已入库", "#F0FDF4", "#166534", "#BBF7D0", "#22C55E"),
    "monitoring": StatusStyle("监控中", "#EFF6FF", "#1D4ED8", "#BFDBFE", "#3B82F6"),
    "success": StatusStyle("通过", "#F0FDF4", "#166534", "#BBF7D0", "#22C55E"),
    "warning": StatusStyle("警告", "#FFFBEB", "#92400E", "#FDE68A", "#F59E0B"),
    "error": StatusStyle("异常", "#FEF2F2", "#991B1B", "#FECACA", "#EF4444"),
    "blocked": StatusStyle("阻塞", "#F8FAFC", "#334155", "#CBD5E1", "#64748B"),
}

_STATUS_ALIASES: Final[dict[str, str]] = {
    "todo": "waiting",
    "pending": "waiting",
    "queued": "waiting",
    "draft": "waiting",
    "waiting_input": "waiting",
    "thinking": "generating",
    "generating": "generating",
    "agent_generating": "generating",
    "reviewing": "review",
    "pending_review": "review",
    "approved": "success",
    "rejected": "error",
    "running": "running",
    "executing": "running",
    "done": "stored",
    "stored": "stored",
    "in_library": "stored",
    "monitoring": "monitoring",
    "in_monitoring": "monitoring",
    "active": "monitoring",
    "ok": "success",
    "warn": "warning",
    "failed": "error",
}

_TONE_TO_STATUS: Final[dict[str, str]] = {
    "primary": "monitoring",
    "info": "generating",
    "success": "success",
    "warning": "warning",
    "danger": "error",
    "neutral": "blocked",
}

AGENT_UI_CSS: Final[str] = """
/* ---------- Global Theme ---------- */
:root {
  --agent-bg: #F5F8FF;
  --agent-bg-soft: #FCFDFF;
  --agent-surface: #FFFFFF;
  --agent-surface-muted: #F7FAFF;
  --agent-border: #D8E2FF;
  --agent-shadow: 0 10px 28px rgba(84, 95, 162, 0.10);
  --agent-shadow-soft: 0 4px 14px rgba(84, 95, 162, 0.07);
  --agent-primary: #5A6ACF;
  --agent-primary-soft: #EEF1FF;
  --agent-success-soft: #EFFFF4;
  --agent-warning-soft: #FFF5E8;
  --agent-danger-soft: #FFF1F2;
  --agent-text-main: #20264A;
  --agent-text-sub: #6B7398;
  --agent-paper-line: rgba(146, 162, 230, 0.08);
  --agent-radius-xl: 22px;
  --agent-radius-lg: 18px;
  --agent-radius-md: 14px;
}

.stApp {
  background:
    radial-gradient(1250px 650px at 14% -20%, #EAF1FF 0%, transparent 62%),
    radial-gradient(980px 560px at 95% -35%, #F8EDFF 0%, transparent 56%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.82) 0%, rgba(249, 252, 255, 0.92) 100%),
    repeating-linear-gradient(
      0deg,
      transparent 0px,
      transparent 23px,
      var(--agent-paper-line) 23px,
      var(--agent-paper-line) 24px
    ),
    var(--agent-bg);
  color: var(--agent-text-main);
  position: relative;
  min-height: 100vh;
}

.stApp::before,
.stApp::after {
  content: "";
  position: fixed;
  z-index: 0;
  width: 190px;
  height: 190px;
  border-radius: 999px;
  pointer-events: none;
  opacity: 0.35;
  filter: blur(1px);
}

.stApp::before {
  top: 92px;
  right: -66px;
  background: radial-gradient(circle at 40% 35%, #FFE5F2 0%, #FFD7EB 42%, transparent 72%);
}

.stApp::after {
  bottom: 26px;
  left: -72px;
  background: radial-gradient(circle at 58% 46%, #E0F4FF 0%, #CDEBFF 45%, transparent 76%);
}

.stApp > * {
  position: relative;
  z-index: 1;
}

.main .block-container {
  max-width: 1320px;
  padding-top: 1rem;
  padding-bottom: 2rem;
  padding-left: 1rem;
  padding-right: 1rem;
}

h1, h2, h3, h4, h5, h6 {
  color: var(--agent-text-main);
  letter-spacing: 0;
  font-weight: 750;
}

h1 {
  font-size: clamp(1.35rem, 1.08rem + 1.15vw, 2rem);
  margin-bottom: 0.2rem;
}

p, label, .stCaption, .stMarkdown {
  color: var(--agent-text-main);
}

div[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #FAFCFF 0%, #F2F6FF 100%);
  border-right: 1px solid var(--agent-border);
}

div[data-testid="stSidebar"] > div:first-child {
  padding-top: 0.75rem;
}

[data-testid="stSidebarNav"] {
  background: transparent;
}

[data-testid="stSidebarNav"] ul {
  gap: 4px;
}

[data-testid="stSidebarNav"] li a {
  border-radius: 12px;
  border: 1px solid transparent;
  transition: all 0.18s ease;
}

[data-testid="stSidebarNav"] li a:hover {
  background: #F4F7FF;
  border-color: var(--agent-border);
}

[data-testid="stSidebarNav"] li a[aria-current="page"] {
  background: #EDF2FF;
  border-color: #C8D6FF;
  box-shadow: inset 0 0 0 1px rgba(90, 106, 207, 0.07);
  font-weight: 650;
}

/* ---------- Streamlit Controls ---------- */
.stButton > button,
.stDownloadButton > button,
[data-testid="baseButton-secondary"],
[data-testid="baseButton-primary"] {
  border-radius: 999px;
  border: 1px solid var(--agent-border);
  box-shadow: var(--agent-shadow-soft);
  font-weight: 640;
  transition: transform 0.16s ease, box-shadow 0.16s ease, border-color 0.16s ease, background 0.16s ease;
}

.stButton > button:hover,
.stDownloadButton > button:hover {
  border-color: #BAC8FF;
  background: #F6F8FF;
  transform: translateY(-1px);
  box-shadow: 0 8px 18px rgba(80, 95, 168, 0.12);
}

[data-testid="baseButton-primary"] {
  background: linear-gradient(180deg, #7081E7 0%, #5A6ACF 100%);
  color: #FFFFFF;
  border-color: #6678DE;
}

[data-testid="baseButton-primary"]:hover {
  background: linear-gradient(180deg, #7A8AEF 0%, #5E6FD3 100%);
}

.stButton > button:focus-visible,
.stDownloadButton > button:focus-visible,
[data-testid="baseButton-secondary"]:focus-visible,
[data-testid="baseButton-primary"]:focus-visible {
  outline: 2px solid #A7BAFF !important;
  outline-offset: 2px;
}

input, textarea, [data-baseweb="select"] > div {
  border-radius: 12px !important;
  border-color: var(--agent-border) !important;
  box-shadow: none !important;
}

input:focus, textarea:focus,
[data-baseweb="select"] > div:focus-within {
  border-color: #A7BAFF !important;
  box-shadow: 0 0 0 3px rgba(167, 186, 255, 0.24) !important;
}

[data-testid="stTabs"] [data-baseweb="tab-list"] {
  gap: 8px;
  border-bottom: none;
}

[data-testid="stTabs"] [data-baseweb="tab"] {
  border-radius: 999px;
  border: 1px solid var(--agent-border);
  background: #FFFFFF;
  color: var(--agent-text-sub);
  padding: 0.3rem 0.85rem;
}

[data-testid="stTabs"] [aria-selected="true"] {
  color: #2F3B85;
  border-color: #BFCFFF;
  background: #EDF2FF;
  font-weight: 650;
}

div[data-testid="stExpander"] {
  border-radius: var(--agent-radius-lg);
  border: 1px solid var(--agent-border);
  background: var(--agent-surface);
  box-shadow: var(--agent-shadow-soft);
}

div[data-testid="stExpander"] summary {
  border-radius: var(--agent-radius-lg);
}

div[data-testid="stMetric"] {
  border: 1px solid var(--agent-border);
  border-radius: var(--agent-radius-lg);
  background: var(--agent-surface);
  box-shadow: var(--agent-shadow);
  padding: 0.82rem 1rem;
}

div[data-testid="stMetric"] > div {
  gap: 2px;
}

[data-testid="stMetricDelta"] svg {
  width: 0.86rem;
  height: 0.86rem;
}

.stProgress {
  height: 0.95rem;
}

.stProgress > div > div {
  border-radius: 999px;
  background: #E8EEFF;
}

.stProgress > div > div > div {
  border-radius: 999px;
  background: linear-gradient(90deg, #73D1EA 0%, #6F94FF 52%, #8D7CFF 100%);
}

div[data-testid="stDataFrame"],
div[data-testid="stTable"] {
  border: 1px solid var(--agent-border);
  border-radius: var(--agent-radius-lg);
  overflow: hidden;
  box-shadow: var(--agent-shadow-soft);
  background: #FFFFFF;
}

div[data-testid="stDataFrame"] [role="columnheader"],
div[data-testid="stTable"] thead tr th {
  background: #F2F6FF !important;
  color: #40508F !important;
  font-weight: 700 !important;
  border-bottom: 1px solid #DDE6FF !important;
}

div[data-testid="stDataFrame"] [role="gridcell"],
div[data-testid="stTable"] tbody tr td {
  border-bottom: 1px solid #EEF2FF !important;
}

div[data-testid="stDataFrame"] [role="row"]:nth-child(even) [role="gridcell"],
div[data-testid="stTable"] tbody tr:nth-child(even) td {
  background: #FAFCFF;
}

div[data-testid="stDataFrame"] [role="row"]:hover [role="gridcell"],
div[data-testid="stTable"] tbody tr:hover td {
  background: #F4F8FF;
}

/* ---------- Helper Blocks ---------- */
.agent-workbench {
  background: var(--agent-bg-soft);
  border: 1px solid var(--agent-border);
  border-radius: var(--agent-radius-xl);
  box-shadow: var(--agent-shadow);
  padding: 16px 18px 18px 18px;
  position: relative;
  overflow: hidden;
}

.agent-workbench::before {
  content: "";
  position: absolute;
  top: -66px;
  right: -46px;
  width: 168px;
  height: 168px;
  border-radius: 999px;
  background: radial-gradient(circle, rgba(189, 226, 255, 0.42) 0%, rgba(189, 226, 255, 0.12) 45%, transparent 74%);
  pointer-events: none;
}

.agent-grid {
  display: grid;
  gap: 12px;
}

.agent-grid.cols-2 {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.agent-grid.cols-3 {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.agent-card {
  background: var(--agent-surface);
  border: 1px solid var(--agent-border);
  border-radius: var(--agent-radius-lg);
  box-shadow: var(--agent-shadow);
  padding: 14px 14px 12px 14px;
  position: relative;
}

.agent-card.compact {
  border-radius: var(--agent-radius-md);
  padding: 10px 12px;
}

.agent-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}

.agent-card-title {
  font-size: 0.98rem;
  font-weight: 700;
  line-height: 1.3;
  color: var(--agent-text-main);
}

.agent-card-subtitle {
  font-size: 0.78rem;
  color: var(--agent-text-sub);
}

.agent-card-body {
  color: var(--agent-text-main);
  font-size: 0.92rem;
  line-height: 1.5;
}

.agent-card-footer {
  margin-top: 10px;
  padding-top: 8px;
  border-top: 1px dashed #E5EBFF;
  color: var(--agent-text-sub);
  font-size: 0.8rem;
}

.agent-badge-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.agent-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border-radius: 999px;
  padding: 2px 10px 3px 10px;
  border: 1px solid transparent;
  font-size: 0.76rem;
  font-weight: 600;
  white-space: nowrap;
  line-height: 1.2;
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.75) inset;
}

.agent-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  flex-shrink: 0;
}

.agent-icon-bubble {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.8rem;
  height: 1.8rem;
  border-radius: 999px;
  border: 1px solid #CBD7FF;
  background: linear-gradient(180deg, #F8FAFF 0%, #EDF2FF 100%);
  color: #3D4B93;
  font-size: 0.94rem;
  box-shadow: var(--agent-shadow-soft);
}

.agent-sticker {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 10px;
  border-radius: 999px;
  border: 1px solid #CCE0FF;
  background: #EEF5FF;
  color: #3A4D9A;
  font-size: 0.78rem;
  font-weight: 650;
}

.agent-sticker.success {
  border-color: #BFEFD1;
  background: var(--agent-success-soft);
  color: #1D7A48;
}

.agent-sticker.warning {
  border-color: #FFD8AB;
  background: var(--agent-warning-soft);
  color: #AA5A11;
}

.agent-sticker.danger {
  border-color: #FDC9D2;
  background: var(--agent-danger-soft);
  color: #AE2D46;
}

.agent-progress-track {
  width: 100%;
  height: 0.64rem;
  border-radius: 999px;
  background: #E8EDFF;
  overflow: hidden;
}

.agent-progress-bar {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #76D6E8 0%, #7198FF 50%, #8D80FF 100%);
}

.agent-progress-label {
  margin-top: 0.26rem;
  color: var(--agent-text-sub);
  font-size: 0.74rem;
}

.agent-hero-shell {
  display: grid;
  grid-template-columns: 150px minmax(0, 1.3fr) minmax(320px, 0.95fr) 220px;
  gap: 14px;
  align-items: stretch;
  margin-bottom: 12px;
}

.agent-mascot-card,
.agent-status-board,
.agent-note-card,
.agent-hero-main,
.agent-overview-ribbon,
.agent-side-spec {
  border: 1px solid var(--agent-border);
  box-shadow: var(--agent-shadow);
  background: rgba(255, 255, 255, 0.88);
}

.agent-mascot-card {
  border-radius: 28px;
  padding: 18px 14px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  background: linear-gradient(180deg, #FFF9EE 0%, #F3FFF3 100%);
}

.agent-mascot-face {
  width: 78px;
  height: 78px;
  border-radius: 34px 34px 28px 28px;
  display: grid;
  place-items: center;
  color: #28704B;
  font-size: 1.6rem;
  font-weight: 900;
  background: #DDF5C8;
  border: 2px solid #80C58F;
  box-shadow: 0 12px 22px rgba(101, 153, 92, 0.16);
}

.agent-sparkle {
  color: #6D7B56;
  font-size: 0.74rem;
  font-weight: 750;
}

.agent-hero-main {
  border-radius: 28px;
  padding: 18px 22px;
  background:
    radial-gradient(220px 90px at 92% 12%, rgba(255, 215, 231, 0.58) 0%, transparent 72%),
    linear-gradient(180deg, #FFFFFF 0%, #FBFDFF 100%);
}

.agent-kicker {
  color: #486B56;
  font-weight: 800;
  font-size: 0.86rem;
}

.agent-hero-title {
  color: #202229;
  font-size: clamp(2rem, 1.55rem + 1.9vw, 3.65rem);
  font-weight: 900;
  line-height: 1.04;
  letter-spacing: -0.04em;
}

.agent-hero-flow {
  margin-top: 10px;
  color: #4F5668;
  font-size: 1rem;
  font-weight: 680;
}

.agent-status-board {
  border-radius: 24px;
  padding: 16px;
  background: #FBFDFF;
}

.agent-status-title,
.agent-section-title {
  color: #214D3D;
  font-weight: 850;
  margin: 0 0 10px 0;
}

.agent-note-card {
  border-radius: 20px;
  padding: 18px;
  background: linear-gradient(145deg, #FFF4B9 0%, #FFF9D8 100%);
  border-color: #E4BD4B;
  color: #382B08;
  transform: rotate(-1.5deg);
}

.agent-note-card div {
  font-size: 1.05rem;
  font-weight: 850;
}

.agent-note-card strong {
  display: block;
  margin-top: 4px;
  font-size: 1.28rem;
  line-height: 1.2;
}

.agent-note-card span {
  display: block;
  margin-top: 12px;
  color: #775B11;
  font-size: 0.8rem;
}

.agent-overview-ribbon {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  border-radius: 24px;
  padding: 12px;
  margin-bottom: 14px;
}

.agent-top-chip {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 8px;
  align-items: center;
  border: 1px solid #E1E8FF;
  border-radius: 18px;
  background: #FBFDFF;
  padding: 10px;
}

.agent-top-chip > span {
  width: 36px;
  height: 36px;
  display: grid;
  place-items: center;
  border-radius: 14px;
  background: #EEF8EA;
  border: 1px solid #CFE8C6;
}

.agent-top-chip b {
  display: block;
  color: #1F2849;
  font-size: 1.05rem;
}

.agent-top-chip small {
  display: block;
  margin-bottom: 5px;
  color: var(--agent-text-sub);
  font-weight: 700;
}

.agent-flow-strip,
.agent-page-map,
.agent-icon-grid,
.agent-validation-grid {
  display: grid;
  gap: 10px;
}

.agent-flow-strip {
  grid-template-columns: repeat(8, minmax(120px, 1fr));
  align-items: stretch;
  overflow-x: auto;
  padding: 2px 2px 12px 2px;
}

.agent-flow-step {
  min-width: 120px;
  border: 1px solid #DDE8CC;
  border-radius: 18px;
  background: #FFFDF7;
  padding: 12px;
  position: relative;
}

.agent-flow-number {
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border-radius: 999px;
  background: #45A666;
  color: #FFFFFF;
  font-weight: 900;
  margin-bottom: 8px;
}

.agent-flow-name {
  color: #1F3D31;
  font-weight: 850;
}

.agent-flow-sub {
  min-height: 34px;
  color: #6C755E;
  font-size: 0.76rem;
  margin: 5px 0 8px 0;
}

.agent-flow-line {
  display: none;
}

.agent-page-map {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.agent-page-tile {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 10px;
  align-items: start;
  border: 1px solid color-mix(in srgb, var(--tile-accent) 35%, #DCE4FF);
  border-radius: 18px;
  background: #FFFFFF;
  padding: 10px;
}

.agent-page-index {
  width: 30px;
  height: 30px;
  border-radius: 999px;
  display: grid;
  place-items: center;
  background: var(--tile-accent);
  color: #FFFFFF;
  font-weight: 900;
}

.agent-page-tile strong,
.agent-page-tile span {
  display: block;
}

.agent-page-tile span {
  color: var(--agent-text-sub);
  font-size: 0.76rem;
  margin-top: 3px;
}

.agent-icon-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.agent-icon-chip {
  text-align: center;
}

.agent-icon-chip div {
  width: 48px;
  height: 48px;
  margin: 0 auto 6px auto;
  display: grid;
  place-items: center;
  border: 1px solid #D6E0FF;
  border-radius: 16px;
  background: linear-gradient(180deg, #FFFFFF 0%, #F2F7FF 100%);
  box-shadow: var(--agent-shadow-soft);
}

.agent-icon-chip span {
  color: var(--agent-text-sub);
  font-size: 0.74rem;
  font-weight: 700;
}

.agent-type-card {
  margin-top: 14px;
  padding: 12px;
  border-radius: 18px;
  background: #FFFDF8;
  border: 1px solid #EFE0B6;
}

.agent-type-card div {
  display: flex;
  gap: 10px;
  align-items: baseline;
  margin: 7px 0;
}

.agent-type-card b {
  font-size: 1.7rem;
  color: #1F253E;
}

.agent-type-card span {
  color: #4F5668;
  font-weight: 700;
}

.agent-workbench-title {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  margin: 4px 0 10px 0;
  color: #21543F;
  font-size: 2rem;
  font-weight: 900;
}

.agent-command-bar {
  display: grid;
  grid-template-columns: minmax(240px, 1fr) minmax(180px, 0.6fr) minmax(120px, 0.35fr) minmax(120px, 0.35fr);
  gap: 12px;
  align-items: center;
  border: 1px solid #D8E6C9;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.88);
  padding: 12px;
  margin-bottom: 14px;
}

.agent-helper-card {
  display: flex;
  align-items: center;
  gap: 12px;
}

.agent-helper-avatar {
  width: 54px;
  height: 54px;
  display: grid;
  place-items: center;
  border-radius: 22px;
  background: #DDF5C8;
  border: 1px solid #99D39C;
  color: #226C43;
  font-weight: 900;
}

.agent-helper-card b,
.agent-helper-card span {
  display: block;
}

.agent-helper-card span,
.agent-progress-pill span,
.agent-task-pill span,
.agent-data-foot {
  color: var(--agent-text-sub);
  font-size: 0.78rem;
  font-weight: 700;
}

.agent-progress-pill,
.agent-task-pill {
  border: 1px solid #E4EAFF;
  border-radius: 18px;
  background: #FFFFFF;
  padding: 10px;
}

.agent-progress-pill b,
.agent-task-pill b {
  display: block;
  color: #27304F;
  font-size: 1.08rem;
}

.agent-mini-nav {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin-bottom: 12px;
}

.agent-mini-nav-item {
  border: 1px solid #E0E7FF;
  border-radius: 14px;
  background: #FFFFFF;
  padding: 9px 10px;
  color: #51607E;
  font-weight: 760;
}

.agent-mini-nav-item.active {
  background: #EAF7E8;
  border-color: #A7D6A5;
  color: #23613E;
}

.agent-phase-row {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
  margin-bottom: 10px;
}

.agent-phase-row div {
  border: 1px solid #DDDDF2;
  border-radius: 16px;
  background: #FCFBFF;
  padding: 12px;
  text-align: center;
  color: #56617D;
  font-weight: 780;
}

.agent-validation-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.agent-validation-grid > div {
  border: 1px solid #E6ECFF;
  border-radius: 14px;
  background: #FBFDFF;
  padding: 10px;
}

.agent-data-foot {
  margin-top: 10px;
}

.agent-mini-table {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  border: 1px solid var(--agent-border);
  border-radius: 18px;
  overflow: hidden;
  background: #FFFFFF;
  box-shadow: var(--agent-shadow-soft);
}

.agent-mini-table th,
.agent-mini-table td {
  padding: 10px 12px;
  border-bottom: 1px solid #EEF2FF;
  text-align: left;
  vertical-align: middle;
}

.agent-mini-table th {
  background: #F2F6FF;
  color: #40508F;
}

.agent-mini-table tr:last-child td {
  border-bottom: none;
}

@media (max-width: 1100px) {
  .main .block-container {
    padding-left: 0.8rem;
    padding-right: 0.8rem;
  }

  .agent-hero-shell,
  .agent-command-bar {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .agent-overview-ribbon {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .agent-grid.cols-3 {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 760px) {
  .main .block-container {
    padding-top: 0.8rem;
    padding-left: 0.65rem;
    padding-right: 0.65rem;
  }

  .agent-workbench {
    border-radius: 18px;
    padding: 12px;
  }

  .agent-grid.cols-2,
  .agent-grid.cols-3 {
    grid-template-columns: minmax(0, 1fr);
  }

  .agent-hero-shell,
  .agent-command-bar,
  .agent-overview-ribbon,
  .agent-page-map,
  .agent-icon-grid,
  .agent-phase-row,
  .agent-validation-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .agent-card {
    border-radius: 14px;
    padding: 10px 10px 9px 10px;
  }
}
"""


def inject_agent_ui_style(st_module) -> None:
    """Inject a stable, Streamlit-friendly stylesheet for the Agent workbench."""
    st_module.markdown(f"<style>{AGENT_UI_CSS}</style>", unsafe_allow_html=True)


def _resolve_status(status: str | None) -> StatusStyle:
    if not status:
        return STATUS_STYLES["blocked"]
    key = _STATUS_ALIASES.get(status.strip().lower(), status.strip().lower())
    return STATUS_STYLES.get(key, STATUS_STYLES["blocked"])


def status_badge_html(status: str, label: str | None = None) -> str:
    style = _resolve_status(status)
    text = escape(label or style.label)
    return (
        f"<span class='agent-badge' style='background:{style.bg};color:{style.fg};border-color:{style.border};'>"
        f"<span class='agent-dot' style='background:{style.dot};'></span>{text}</span>"
    )


def badge_html(text: str, tone: str = "neutral", icon: str | None = None) -> str:
    key = _TONE_TO_STATUS.get(tone.strip().lower(), "blocked")
    style = _resolve_status(key)
    icon_html = ""
    if icon:
        icon_html = f"<span>{escape(icon)}</span>"
    return (
        f"<span class='agent-badge' style='background:{style.bg};color:{style.fg};border-color:{style.border};'>"
        f"{icon_html}{escape(text)}</span>"
    )


def badge_row_html(items: list[str]) -> str:
    return "<div class='agent-badge-row'>" + "".join(items) + "</div>"


def icon_bubble_html(icon: str, title: str | None = None) -> str:
    if title:
        return f"<span class='agent-icon-bubble' title='{escape(title)}'>{escape(icon)}</span>"
    return f"<span class='agent-icon-bubble'>{escape(icon)}</span>"


def sticker_html(text: str, tone: str = "info", icon: str | None = None) -> str:
    style = _resolve_status(_TONE_TO_STATUS.get(tone.strip().lower(), "generating"))
    tone_class = ""
    if tone.strip().lower() == "success":
        tone_class = " success"
    elif tone.strip().lower() == "warning":
        tone_class = " warning"
    elif tone.strip().lower() in {"danger", "error"}:
        tone_class = " danger"
    icon_html = f"<span>{escape(icon)}</span>" if icon else ""
    return (
        f"<span class='agent-sticker{tone_class}' style='border-color:{style.border};background:{style.bg};color:{style.fg};'>"
        f"{icon_html}<span>{escape(text)}</span></span>"
    )


def progress_html(percent: float, label: str | None = None) -> str:
    safe_percent = max(0.0, min(100.0, float(percent)))
    label_html = f"<div class='agent-progress-label'>{escape(label)}</div>" if label else ""
    return (
        "<div>"
        "<div class='agent-progress-track'>"
        f"<div class='agent-progress-bar' style='width:{safe_percent:.1f}%;'></div>"
        "</div>"
        f"{label_html}"
        "</div>"
    )


def card_open_html(
    title: str | None = None,
    subtitle: str | None = None,
    right_html: str | None = None,
    compact: bool = False,
) -> str:
    card_class = "agent-card compact" if compact else "agent-card"
    parts = [f"<div class='{card_class}'>"]
    if title or subtitle or right_html:
        parts.append("<div class='agent-card-head'>")
        parts.append("<div>")
        if title:
            parts.append(f"<div class='agent-card-title'>{escape(title)}</div>")
        if subtitle:
            parts.append(f"<div class='agent-card-subtitle'>{escape(subtitle)}</div>")
        parts.append("</div>")
        if right_html:
            parts.append(f"<div>{right_html}</div>")
        parts.append("</div>")
    parts.append("<div class='agent-card-body'>")
    return "".join(parts)


def card_close_html(footer: str | None = None) -> str:
    if footer:
        return f"</div><div class='agent-card-footer'>{footer}</div></div>"
    return "</div></div>"


def card_html(
    body_html: str,
    title: str | None = None,
    subtitle: str | None = None,
    right_html: str | None = None,
    footer_html: str | None = None,
    compact: bool = False,
) -> str:
    return (
        card_open_html(title=title, subtitle=subtitle, right_html=right_html, compact=compact)
        + body_html
        + card_close_html(footer=footer_html)
    )


def workbench_open_html() -> str:
    return "<section class='agent-workbench'>"


def workbench_close_html() -> str:
    return "</section>"


__all__ = [
    "AGENT_UI_CSS",
    "STATUS_STYLES",
    "StatusStyle",
    "badge_html",
    "badge_row_html",
    "card_close_html",
    "card_html",
    "card_open_html",
    "icon_bubble_html",
    "inject_agent_ui_style",
    "progress_html",
    "sticker_html",
    "status_badge_html",
    "workbench_close_html",
    "workbench_open_html",
]
