# ui/dashboard.py
# 9-panel real-time clinical dashboard running on a daemon thread
# reframed for adhd/attention metrics — not tremor

import math
import time
import threading
import numpy as np
import matplotlib
try:
    matplotlib.use("Qt5Agg")
except Exception:
    matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.gridspec import GridSpec
from matplotlib.patches import Arc

from core.constants import (
    DIFFICULTY_LEVELS,
    HEX_NEON, HEX_PINK, HEX_GREEN, HEX_YELLOW, HEX_ORANGE, HEX_RED,
    HEX_BG, HEX_PANEL, HEX_GRID, HEX_DIM, HEX_MID, HEX_WHITE,
)
from core.shared_data import shared

dashboard_stop = threading.Event()
_dashboard_fig = [None]  # mutable ref so thread can write the figure back


def save_dashboard_png(path="savedDashboards/neuro_osu_dashboard.png"):
    """save current dashboard as png."""
    fig = _dashboard_fig[0]
    if fig is None:
        print("no dashboard to save yet"); return False
    try:
        fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=HEX_BG)
        print(f"dashboard saved → {path}"); return True
    except Exception as e:
        print(f"save failed: {e}"); return False


def save_session_csv(src="patient_performance.csv", dst=None):
    """copy session csv to a timestamped file."""
    import shutil
    from datetime import datetime as _dt
    if dst is None:
        dst = f"savedSessions/session_{_dt.now().strftime('%Y%m%d_%H%M%S')}.csv"
    try:
        shutil.copy2(src, dst); print(f"csv saved → {dst}"); return dst
    except Exception as e:
        print(f"csv save failed: {e}"); return None


def show_last_dashboard():
    """focus the dashboard window if still open."""
    fig = _dashboard_fig[0]
    if fig is None: return
    try:
        fig.canvas.manager.window.activateWindow()
        fig.canvas.manager.window.raise_()
    except Exception:
        pass



def _rolling_avg(vals, window=5):
    if len(vals) < window:
        window = max(1, len(vals))
    return np.convolve(np.array(vals, float), np.ones(window) / window, mode="valid")


def _radar_values(snap):
    """5 normalised adhd-relevant metrics for the spider chart."""
    t_total = snap["total_trials"]
    t_hits  = snap["total_hits"]
    rts     = snap["rts"]
    stabs   = snap["stabs"]
    health  = snap["current_health"]
    lapses  = snap["attention_lapses"]

    accuracy    = (t_hits / t_total) if t_total else 0.0
    speed       = max(0.0, min(1.0, 1.0 - (np.mean(rts) / 3.0))) if rts else 0.5
    stability   = np.mean(stabs) if stabs else 0.5
    consistency = max(0.0, min(1.0, 1.0 - np.std(rts) / 1.5)) if len(rts) >= 3 else 0.5
    # impulsivity = low variance in cursor movement = good impulse control
    focus       = max(0.0, 1.0 - lapses / max(t_total, 1))
    return [accuracy, speed, stability, consistency, focus]


def _style(ax, title="", xlabel="", ylabel=""):
    ax.set_facecolor(HEX_PANEL)
    for sp in ax.spines.values():
        sp.set_color(HEX_GRID); sp.set_linewidth(0.6)
    ax.tick_params(colors=HEX_DIM, labelsize=7, length=3, width=0.5)
    ax.xaxis.label.set_color(HEX_DIM)
    ax.yaxis.label.set_color(HEX_DIM)
    ax.grid(True, color=HEX_GRID, linewidth=0.3, alpha=0.5)
    if title:   ax.set_title(title,   color=HEX_NEON, fontsize=9, fontweight="bold", pad=8, loc="left")
    if xlabel:  ax.set_xlabel(xlabel, fontsize=7, labelpad=4)
    if ylabel:  ax.set_ylabel(ylabel, fontsize=7, labelpad=4)


def clinical_dashboard():
    try:
        plt.style.use("dark_background")
        fig = plt.figure(figsize=(16, 9.5), facecolor=HEX_BG)
        fig.canvas.manager.set_window_title("Neuro-Osu  │  clinical dashboard")

        gs = GridSpec(3, 4, figure=fig, hspace=0.52, wspace=0.42,
                      left=0.05, right=0.97, top=0.92, bottom=0.06)

        ax_rt    = fig.add_subplot(gs[0, 0:2])
        ax_acc   = fig.add_subplot(gs[0, 2])
        ax_radar = fig.add_subplot(gs[0, 3], polar=True)
        ax_stab  = fig.add_subplot(gs[1, 0:2])
        ax_combo = fig.add_subplot(gs[1, 2])
        ax_diff  = fig.add_subplot(gs[1, 3])
        ax_vel   = fig.add_subplot(gs[2, 0])
        ax_err   = fig.add_subplot(gs[2, 1])
        ax_pie   = fig.add_subplot(gs[2, 2])
        ax_info  = fig.add_subplot(gs[2, 3])

        def update(_):
            if dashboard_stop.is_set():
                return
            snap    = shared.snapshot()
            trials  = snap["trials"];  rts    = snap["rts"]
            stabs   = snap["stabs"];   diffs  = snap["diffs"]
            vels    = snap["velocities"]; errs = snap["errors"]
            combos  = snap["combos"];  healths = snap["healths"]
            t_total = snap["total_trials"]; t_hits = snap["total_hits"]
            diff_now = snap["current_diff"]; elapsed = snap["elapsed"]

            for ax in [ax_rt, ax_acc, ax_stab, ax_combo, ax_diff,
                       ax_vel, ax_err, ax_pie, ax_info]:
                ax.cla(); ax.set_facecolor(HEX_PANEL)
                for sp in ax.spines.values(): sp.set_color(HEX_GRID)
            ax_radar.cla(); ax_radar.set_facecolor(HEX_PANEL)

            # 1 — reaction time trend
            _style(ax_rt, "reaction time", "trial #", "seconds")
            if trials:
                ax_rt.fill_between(trials, rts, alpha=0.12, color=HEX_NEON)
                ax_rt.plot(trials, rts, color=HEX_NEON, lw=1.2, alpha=0.6,
                           marker="o", markersize=2.5)
                if len(rts) >= 5:
                    ra = _rolling_avg(rts, 5)
                    ax_rt.plot(trials[4:], ra, color=HEX_PINK, lw=2, label="5-trial avg")
                    ax_rt.legend(fontsize=7, loc="upper right",
                                 facecolor=HEX_PANEL, edgecolor=HEX_GRID, labelcolor=HEX_MID)
                avg = np.mean(rts)
                ax_rt.axhline(avg, color=HEX_YELLOW, lw=0.8, ls="--", alpha=0.5)
                ax_rt.text(trials[-1], avg, f" μ={avg:.2f}s",
                           color=HEX_YELLOW, fontsize=7, va="bottom")

            # 2 — rolling accuracy
            _style(ax_acc, "rolling accuracy", "trial #", "%")
            if len(snap["scores_bin"]) >= 3:
                sb  = np.array(snap["scores_bin"], float)
                win = min(8, len(sb))
                ra  = np.convolve(sb, np.ones(win) / win, mode="valid") * 100
                rx  = list(range(win, win + len(ra)))
                ax_acc.fill_between(rx, ra, alpha=0.18, color=HEX_GREEN)
                ax_acc.plot(rx, ra, color=HEX_GREEN, lw=2)
                ax_acc.axhline(70, color=HEX_YELLOW, lw=0.7, ls=":", alpha=0.5)
                ax_acc.text(rx[-1] + 0.3, ra[-1], f"{ra[-1]:.0f}%",
                            color=HEX_GREEN, fontsize=8, fontweight="bold", va="center")
            ax_acc.set_ylim(0, 105)

            # 3 — performance radar (adhd metrics)
            radar_labels = ["accuracy", "speed", "focus stability",
                            "consistency", "impulse ctrl"]
            rv = _radar_values(snap)
            N  = len(radar_labels)
            angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
            rv_plot = rv + [rv[0]]; angles_plot = angles + [angles[0]]
            ax_radar.plot(angles_plot, rv_plot, color=HEX_NEON, lw=2)
            ax_radar.fill(angles_plot, rv_plot, color=HEX_NEON, alpha=0.15)
            ax_radar.scatter(angles, rv, color=HEX_NEON, s=30,
                             edgecolors=HEX_WHITE, linewidths=0.5, zorder=5)
            ax_radar.set_xticks(angles)
            ax_radar.set_xticklabels(radar_labels, fontsize=7, color=HEX_MID)
            ax_radar.set_ylim(0, 1); ax_radar.set_yticks([0.25, 0.5, 0.75, 1.0])
            ax_radar.set_yticklabels(["25%","50%","75%","100%"], fontsize=6, color=HEX_DIM)
            ax_radar.yaxis.grid(True, color=HEX_GRID, lw=0.4)
            ax_radar.xaxis.grid(True, color=HEX_GRID, lw=0.4)
            ax_radar.set_title("attention profile", color=HEX_NEON,
                               fontsize=9, fontweight="bold", pad=14)
            for sp in ax_radar.spines.values(): sp.set_color(HEX_GRID)

            # 4 — focus stability (replaces tremor bars)
            _style(ax_stab, "focus stability", "trial #", "stability score")
            if trials:
                bar_colors = [HEX_GREEN if s >= 0.7 else (HEX_YELLOW if s >= 0.4 else HEX_RED)
                              for s in stabs]
                ax_stab.bar(trials, stabs, color=bar_colors, alpha=0.75, width=0.8, edgecolor="none")
                ax_stab.axhline(0.7, color=HEX_NEON, lw=1, ls=":", alpha=0.6, label="target (0.7)")
                if len(stabs) >= 5:
                    sa = _rolling_avg(stabs, 5)
                    ax_stab.plot(trials[4:], sa, color=HEX_PINK, lw=2, label="trend")
                ax_stab.legend(fontsize=6, loc="lower right",
                               facecolor=HEX_PANEL, edgecolor=HEX_GRID, labelcolor=HEX_MID)
            ax_stab.set_ylim(0, 1.05)

            # 5 — health & combo
            _style(ax_combo, "health & combo", "trial #", "")
            if trials:
                ax_combo.plot(trials, healths, color=HEX_RED, lw=2, label="health %")
                ax_combo.fill_between(trials, healths, alpha=0.1, color=HEX_RED)
                ax2 = ax_combo.twinx()
                ax2.set_facecolor("none")
                ax2.plot(trials, combos, color=HEX_ORANGE, lw=1.5, ls="--", label="combo")
                ax2.tick_params(colors=HEX_DIM, labelsize=7)
                ax2.set_ylabel("combo", fontsize=7, color=HEX_DIM)
                for sp in ax2.spines.values(): sp.set_color(HEX_GRID)
                l1, lb1 = ax_combo.get_legend_handles_labels()
                l2, lb2 = ax2.get_legend_handles_labels()
                ax_combo.legend(l1 + l2, lb1 + lb2, fontsize=6, loc="upper left",
                                facecolor=HEX_PANEL, edgecolor=HEX_GRID, labelcolor=HEX_MID)
            ax_combo.set_ylim(0, 110)

            # 6 — difficulty gauge
            ax_diff.set_xlim(-1.5, 1.5); ax_diff.set_ylim(-1.0, 1.5)
            ax_diff.set_aspect("equal"); ax_diff.axis("off")
            arc_cols = [HEX_GREEN, HEX_NEON, HEX_YELLOW, HEX_PINK, HEX_RED]
            seg = 270 / 5
            for i in range(5):
                t1 = -135 + i * seg; t2 = t1 + seg - 2
                ax_diff.add_patch(Arc((0, 0), 2.2, 2.2, angle=0,
                                      theta1=t1, theta2=t2,
                                      color=arc_cols[i], lw=10,
                                      alpha=0.9 if (i + 1) == diff_now else 0.25))
            needle_rad = math.radians(-135 + (diff_now - 0.5) * seg)
            nl = 0.8
            ax_diff.annotate("", xy=(nl * math.cos(needle_rad), nl * math.sin(needle_rad)),
                             xytext=(0, 0),
                             arrowprops=dict(arrowstyle="-|>", color=HEX_WHITE, lw=2.5))
            ax_diff.plot(0, 0, "o", color=HEX_DIM, markersize=6)
            ax_diff.text(0, -0.30, f"level {diff_now}", ha="center",
                         color=arc_cols[diff_now - 1], fontsize=16, fontweight="bold")
            lbl = DIFFICULTY_LEVELS[diff_now]["label"].split("-")[1].strip()
            ax_diff.text(0, -0.60, lbl, ha="center", color=HEX_DIM, fontsize=8)
            ax_diff.set_title("difficulty", color=HEX_NEON, fontsize=9, fontweight="bold", pad=4)

            # 7 — cursor velocity (impulsivity proxy)
            _style(ax_vel, "cursor velocity (impulsivity proxy)", "trial #", "px/s")
            if trials and vels:
                ax_vel.fill_between(trials, vels, alpha=0.12, color=HEX_ORANGE)
                ax_vel.plot(trials, vels, color=HEX_ORANGE, lw=1.5,
                            marker="o", markersize=2, alpha=0.8)
                if len(vels) >= 5:
                    va = _rolling_avg(vels, 5)
                    ax_vel.plot(trials[4:], va, color=HEX_NEON, lw=2)

            # 8 — click precision
            _style(ax_err, "click precision", "trial #", "error (px)")
            if trials and errs:
                sc = [HEX_GREEN if e < 10 else (HEX_YELLOW if e < 25 else
                      (HEX_ORANGE if e < 50 else HEX_RED)) for e in errs]
                ax_err.scatter(trials, errs, c=sc, s=25, alpha=0.8, edgecolors="none", zorder=3)
                if len(errs) >= 3:
                    ea = _rolling_avg(errs, min(5, len(errs)))
                    ax_err.plot(trials[len(trials) - len(ea):], ea, color=HEX_PINK, lw=2)
                ax_err.axhline(25, color=HEX_YELLOW, lw=0.7, ls=":", alpha=0.5)

            # 9a — hit breakdown pie
            ax_pie.set_facecolor(HEX_PANEL); ax_pie.axis("equal")
            counts = [snap["perfect"], snap["great"], snap["good"], snap["miss"]]
            if sum(counts) > 0:
                wedges, texts, autos = ax_pie.pie(
                    counts,
                    labels=["perfect", "great", "good", "miss"],
                    colors=[HEX_NEON, HEX_GREEN, HEX_YELLOW, HEX_RED],
                    autopct=lambda p: f"{p:.0f}%" if p > 0 else "",
                    startangle=90, pctdistance=0.75,
                    wedgeprops=dict(width=0.45, edgecolor=HEX_PANEL, linewidth=2),
                )
                for t in texts:  t.set_color(HEX_MID);  t.set_fontsize(7)
                for t in autos:  t.set_color(HEX_WHITE); t.set_fontsize(7); t.set_fontweight("bold")
            else:
                ax_pie.text(0, 0, "no data", ha="center", va="center",
                            color=HEX_DIM, fontsize=10)
            ax_pie.set_title("hit breakdown", color=HEX_NEON, fontsize=9,
                             fontweight="bold", pad=8)

            # 9b — session metrics panel
            ax_info.axis("off"); ax_info.set_facecolor(HEX_PANEL)
            acc     = (t_hits / t_total * 100) if t_total else 0
            mins    = int(elapsed) // 60; secs = int(elapsed) % 60
            avg_rt  = f"{np.mean(rts):.3f}s"  if rts   else "—"
            best_rt = f"{min(rts):.3f}s"       if rts   else "—"
            avg_st  = f"{np.mean(stabs):.2f}"  if stabs else "—"

            lines = [
                ("session metrics",                  HEX_NEON,   12, "bold"),
                ("─" * 28,                           HEX_GRID,    8, "normal"),
                (f"duration      {mins:02d}:{secs:02d}", HEX_MID, 9, "normal"),
                (f"total trials  {t_total}",          HEX_MID,    9, "normal"),
                (f"hits          {t_hits}",            HEX_GREEN,  9, "bold"),
                (f"misses        {snap['miss']}",      HEX_RED,    9, "bold"),
                (f"attn lapses   {snap['attention_lapses']}", HEX_ORANGE, 9, "bold"),
                (f"accuracy      {acc:.1f}%",          HEX_NEON,  10, "bold"),
                ("─" * 28,                            HEX_GRID,   8, "normal"),
                (f"avg rt        {avg_rt}",            HEX_YELLOW, 9, "normal"),
                (f"best rt       {best_rt}",           HEX_GREEN,  9, "normal"),
                (f"avg stability {avg_st}",            HEX_NEON,   9, "normal"),
                (f"max combo     {snap['max_combo']}", HEX_ORANGE, 9, "bold"),
                (f"score         {snap['current_score']:,}", HEX_NEON, 10, "bold"),
            ]
            y = 0.97
            for txt, col, fsize, weight in lines:
                ax_info.text(0.05, y, txt, transform=ax_info.transAxes,
                             color=col, fontsize=fsize, fontweight=weight,
                             fontfamily="monospace")
                y -= 0.072

            fig.suptitle("neuro-osu  ┃  clinical attention dashboard",
                         color=HEX_NEON, fontsize=12, fontweight="bold",
                         x=0.5, y=0.97, fontfamily="monospace")

        ani = animation.FuncAnimation(fig, update, interval=700, cache_frame_data=False)
        plt.show(block=False)
        _dashboard_fig[0] = fig

        # keep running even after the game window closes
        while not dashboard_stop.is_set():
            try:
                fig.canvas.flush_events()
                time.sleep(0.05)
            except Exception:
                break

    except Exception as e:
        print(f"dashboard error (non-critical): {e}")
        while not dashboard_stop.is_set():
            time.sleep(0.1)