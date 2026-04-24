# SPDX-FileCopyrightText: 2026 Maria Westrin, Ulrika Wennberg
# SPDX-License-Identifier: MIT
"""Nimbus-C2 Saab Extension — Boreal Passage scenario analysis package.

This is an analysis-only extension for the Nimbus-C2 decision engine.
It imports nimbus-c2 as an unmodified dependency and provides adapters
that load the Saab-supplied Boreal Passage canvas into the engine's
existing dataclasses.

The engine itself is not modified by this package.
"""
from __future__ import annotations

from .scenarios import (
    BOREAL_SCENARIOS,
    BorealGeography,
    build_boreal_scenario,
    load_boreal_geography,
)

__all__ = [
    "BOREAL_SCENARIOS",
    "BorealGeography",
    "build_boreal_scenario",
    "load_boreal_geography",
]
