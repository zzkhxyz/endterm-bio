"""Publication-ready diagnostic figures from fitted model output."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats

from pdxmodel.fit import FitResult
from pdxmodel.model import ARM_ORDER, Cohort, parameter_names

COLORS = {"control": "#8b95a5", "A": "#0071e3", "B": "#ff375f", "A+B": "#28a745"}


def _style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.edgecolor": "#c8cdd3",
            "axes.labelcolor": "#303846",
            "text.color": "#18202d",
            "xtick.color": "#657080",
            "ytick.color": "#657080",
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "savefig.facecolor": "white",
            "font.size": 10,
        }
    )


def _save(fig: plt.Figure, out_dir: Path, stem: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_dir / f"{stem}.png", dpi=180, bbox_inches="tight")
    svg_path = out_dir / f"{stem}.svg"
    fig.savefig(svg_path, bbox_inches="tight")
    svg_path.write_text(
        "\n".join(line.rstrip() for line in svg_path.read_text(encoding="utf-8").splitlines()) + "\n",
        encoding="utf-8",
    )
    plt.close(fig)


def plot_fit(fit: FitResult, cohort: Cohort, out_dir: Path) -> None:
    """Show measured points and fitted lines for every PDX and treatment."""
    _style()
    fig, axes = plt.subplots(5, 2, figsize=(13, 18), sharex=False)
    frame = cohort.frame.reset_index(drop=True)
    for ax, line in zip(axes.flat, cohort.lines, strict=True):
        for arm in ARM_ORDER:
            mask = (frame.pdx_id == line) & (frame.treatment == arm)
            days = cohort.days[mask]
            observed = cohort.observed[mask]
            predicted = fit.predicted[mask]
            ax.scatter(days, observed, color=COLORS[arm], s=16, alpha=0.8)
            ax.plot(days, predicted, color=COLORS[arm], lw=1.8, label=arm)
        ax.set_title(str(line), loc="left", weight="bold")
        ax.set_xlabel("Days after first treatment")
        ax.set_ylabel("Tumor volume (mm³)")
        ax.grid(alpha=0.12)
    handles, labels = axes.flat[0].get_legend_handles_labels()
    fig.suptitle("Model versus observed PDX tumor volumes", y=0.998, size=17, weight="bold")
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 0.982), ncol=4, frameon=False)
    fig.tight_layout(rect=(0, 0, 1, 0.955))
    _save(fig, out_dir, "model_vs_data")


def plot_residuals(fit: FitResult, cohort: Cohort, out_dir: Path) -> None:
    """Inspect residuals versus time/fitted value and a normal QQ plot."""
    _style()
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.4))
    residual = fit.residuals
    axes[0].scatter(cohort.days, residual, alpha=0.45, s=14, color="#0071e3")
    axes[0].set(xlabel="Day", ylabel="Weighted log residual", title="Residual versus time")
    axes[1].scatter(np.log(fit.predicted), residual, alpha=0.45, s=14, color="#ff375f")
    axes[1].set(xlabel="Log fitted volume", ylabel="Weighted log residual", title="Residual versus fit")
    stats.probplot(residual, dist="norm", plot=axes[2])
    axes[2].set_title("Normal QQ plot")
    for ax in axes[:2]:
        ax.axhline(0, color="#8b95a5", lw=1)
        ax.grid(alpha=0.12)
    fig.tight_layout()
    _save(fig, out_dir, "residuals")


def plot_correlation(correlation: list[list[float]], cohort: Cohort, out_dir: Path) -> None:
    """Heatmap of the Jacobian covariance correlation matrix."""
    _style()
    names = parameter_names(cohort.lines)
    fig, ax = plt.subplots(figsize=(10, 9))
    image = ax.imshow(correlation, cmap="coolwarm", vmin=-1, vmax=1)
    ax.set_xticks(range(len(names)), names, rotation=90, fontsize=7)
    ax.set_yticks(range(len(names)), names, fontsize=7)
    ax.set_title("Approximate parameter correlations", weight="bold")
    fig.colorbar(image, ax=ax, label="Pearson correlation")
    fig.tight_layout()
    _save(fig, out_dir, "parameter_correlation")


def plot_sensitivity(sensitivity: list[dict[str, float | str]], out_dir: Path) -> None:
    """Tornado chart for final A+B volume sensitivity."""
    _style()
    ordered = sorted(sensitivity, key=lambda row: abs(float(row["normalized_terminal_sensitivity"])))
    names = [str(row["parameter"]) for row in ordered]
    values = [float(row["normalized_terminal_sensitivity"]) for row in ordered]
    fig, ax = plt.subplots(figsize=(9, 8))
    ax.barh(names, values, color=["#0071e3" if v > 0 else "#ff375f" for v in values])
    ax.axvline(0, color="#8b95a5", lw=1)
    ax.set_xlabel("Normalized sensitivity of mean final A+B volume")
    ax.set_title("±10% local parameter sensitivity", weight="bold")
    fig.tight_layout()
    _save(fig, out_dir, "sensitivity_tornado")


def plot_profiles(profiles: dict[str, object], out_dir: Path) -> None:
    """Refitted likelihood-ratio curves for the three shared effects."""
    _style()
    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    for ax, (name, record) in zip(axes, profiles.items(), strict=True):
        if not isinstance(record, dict):
            continue
        ax.plot(record["fixed_values"], record["likelihood_ratio"], color="#0071e3", marker="o")
        ax.axhline(record["threshold_chi2_95"], color="#ff375f", ls="--", label="95% cutoff")
        if name == "psi":
            ax.axvline(0, color="#8b95a5", ls=":", label="Bliss (ψ=0)")
        ax.set(xlabel=name, ylabel="Profile likelihood ratio", title=name)
        ax.grid(alpha=0.12)
    axes[-1].legend(frameon=False)
    fig.tight_layout()
    _save(fig, out_dir, "profile_likelihood")
