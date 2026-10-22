"""Mechanistic invariants of the treatment ODE."""

import numpy as np
import pandas as pd

from pdxmodel.model import Cohort, bliss_effect, combo_a_effect, solve_cohort, treatment_effects


def fixture_cohort() -> Cohort:
    """A tiny equal-baseline quartet for exact arm comparisons."""
    rows = [
        ("PDX-1", "BRCA", arm, day, 200.0)
        for arm in ("control", "A", "B", "A+B")
        for day in (0, 4, 8, 12, 16, 20)
    ]
    return Cohort.from_frame(
        pd.DataFrame(rows, columns=["pdx_id", "cancer_type", "treatment", "day", "volume_mm3"])
    )


def test_solutions_are_positive_and_zero_dose_matches_control() -> None:
    """No drug effect must reproduce untreated growth from the same baseline."""
    cohort = fixture_cohort()
    prediction = solve_cohort(np.asarray([0.04, 3.0, 0.0, 0.4, 0.0]), cohort, "logistic")
    assert (prediction > 0).all()
    assert np.allclose(prediction[:6], prediction[6:12], rtol=1e-9)
    assert np.allclose(prediction[12:18], prediction[18:24], rtol=1e-9)


def test_zero_interaction_is_bliss_independence() -> None:
    """At ψ=0 the pair effect equals the stated Bliss expression."""
    assert bliss_effect(0.2, 0.4, 0.0) == 0.2 + 0.4 - 0.2 * 0.4
    assert combo_a_effect(0.2) < 0.2
    assert treatment_effects(0.2, 0.4, 0.0)[-1] == bliss_effect(combo_a_effect(0.2), 0.4, 0.0)
