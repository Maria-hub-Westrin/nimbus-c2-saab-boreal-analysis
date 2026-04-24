# SPDX-FileCopyrightText: 2026 Maria Westrin
# SPDX-License-Identifier: MIT
"""Unit + integration tests for the Boreal Passage scenario pack.

Test layers:

    CSV parsing        â€” round-trip every row, check counts and types.
    Geography          â€” coordinate flip is correct; named lookups work.
    Scenario payloads  â€” API schema validity, geographic sanity.
    Pipeline integration â€” each scenario lands in its expected
                          autonomy mode, deterministically.

Intentional non-tests
    - No *threshold* is tested here beyond "mode X is reached".
      Calibration of the assurance thresholds themselves is covered by
      ``tests/test_pipeline.py`` against the engine's own demo
      scenarios.
    - No cross-solver parity test â€” that is owned by
      ``tests/test_milp_parity.py`` and should not be duplicated per
      scenario pack.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nimbus_c2.models import Base, Threat  # noqa: E402
from nimbus_c2.pipeline import evaluate  # noqa: E402
from nimbus_saab_ext.scenarios import (  # noqa: E402
    BOREAL_EFFECTORS,
    BOREAL_SCENARIOS,
    X_EXTENT_KM,
    Y_EXTENT_KM,
    BorealGeography,
    boreal_scenario_as_engine_inputs,
    build_boreal_scenario,
    load_boreal_geography,
)


# --------------------------------------------------------------------------- #
# Geography parsing                                                           #
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def geo() -> BorealGeography:
    """Module-scoped geography â€” parsed once, reused by all tests."""
    return load_boreal_geography()


class TestGeographyParsing:
    """The CSV must round-trip into a well-formed geography object."""

    def test_total_feature_count(self, geo: BorealGeography) -> None:
        # 12 locations (3 air bases + 1 capital + 2 cities per side Ã— 2) + 8 terrain.
        assert len(geo.features) == 20

    def test_location_count(self, geo: BorealGeography) -> None:
        assert len(geo.locations) == 12

    def test_terrain_polygon_count(self, geo: BorealGeography) -> None:
        assert len(geo.terrain) == 8

    def test_each_side_has_one_capital(self, geo: BorealGeography) -> None:
        # Property accessor raises if count != 1.
        assert geo.north_capital.feature_name == "Arktholm (Capital X)"
        assert geo.south_capital.feature_name == "Meridia (Capital Y)"

    def test_each_side_has_three_air_bases(self, geo: BorealGeography) -> None:
        assert len(geo.north_air_bases) == 3
        assert len(geo.south_air_bases) == 3

    def test_named_lookup_raises_on_unknown(self, geo: BorealGeography) -> None:
        with pytest.raises(KeyError):
            geo.find("Does Not Exist")


class TestCoordinateFlip:
    """CSV uses +y=south; engine uses +y=north. Loader must flip."""

    def test_arktholm_is_in_northern_half(self, geo: BorealGeography) -> None:
        # After flip, Arktholm (CSV y=95) becomes y=1205 â€” well north of midline.
        assert geo.north_capital.y_km > Y_EXTENT_KM / 2

    def test_meridia_is_in_southern_half(self, geo: BorealGeography) -> None:
        # After flip, Meridia (CSV y=1208) becomes y=91.7 â€” well south of midline.
        assert geo.south_capital.y_km < Y_EXTENT_KM / 2

    def test_all_north_features_north_of_all_south_features(
        self, geo: BorealGeography
    ) -> None:
        north_ys = [f.y_km for f in geo.locations if f.side == "north"]
        south_ys = [f.y_km for f in geo.locations if f.side == "south"]
        # Strict separation: the northernmost southern feature is still
        # south of the southernmost northern feature.
        assert max(south_ys) < min(north_ys), (
            f"side separation violated: south max y = {max(south_ys)}, "
            f"north min y = {min(north_ys)}"
        )

    def test_polygon_vertices_are_flipped_consistently(
        self, geo: BorealGeography
    ) -> None:
        """The two mainland polygons should sit on opposite halves of the canvas."""
        north_main = [t for t in geo.terrain if t.feature_id == "north_mainland"][0]
        south_main = [t for t in geo.terrain if t.feature_id == "south_mainland"][0]
        north_vy = [vy for (_, vy) in north_main.polygon_km]
        south_vy = [vy for (_, vy) in south_main.polygon_km]
        # After flip: north mainland occupies high y, south occupies low y.
        assert min(north_vy) > max(south_vy)

    def test_x_axis_is_unchanged(self, geo: BorealGeography) -> None:
        """X coordinate must NOT be flipped â€” only y."""
        # Arktholm CSV x=418.3; after load, still 418.3.
        assert geo.north_capital.x_km == pytest.approx(418.3, rel=1e-6)


# --------------------------------------------------------------------------- #
# Scenario payload shape                                                      #
# --------------------------------------------------------------------------- #

class TestScenarioPayloads:

    @pytest.mark.parametrize("scenario_id", list(BOREAL_SCENARIOS.keys()))
    def test_payload_has_all_required_keys(self, scenario_id: str) -> None:
        payload = build_boreal_scenario(scenario_id)
        assert set(payload.keys()) >= {
            "bases", "effectors", "threats", "intent", "blind_spots"
        }

    @pytest.mark.parametrize("scenario_id", list(BOREAL_SCENARIOS.keys()))
    def test_defender_has_capital(self, scenario_id: str) -> None:
        payload = build_boreal_scenario(scenario_id)
        capitals = [b for b in payload["bases"] if b.get("is_capital")]
        assert len(capitals) == 1
        assert capitals[0]["name"] == "Arktholm (Capital X)"

    @pytest.mark.parametrize("scenario_id", list(BOREAL_SCENARIOS.keys()))
    def test_defender_has_four_bases(self, scenario_id: str) -> None:
        payload = build_boreal_scenario(scenario_id)
        assert len(payload["bases"]) == 4

    @pytest.mark.parametrize("scenario_id", list(BOREAL_SCENARIOS.keys()))
    def test_all_threats_have_unique_ids(self, scenario_id: str) -> None:
        payload = build_boreal_scenario(scenario_id)
        ids = [t["id"] for t in payload["threats"]]
        assert len(ids) == len(set(ids))

    @pytest.mark.parametrize("scenario_id", list(BOREAL_SCENARIOS.keys()))
    def test_threat_types_are_in_pk_matrix(self, scenario_id: str) -> None:
        """Every threat must have at least one effector that knows how to
        engage its type â€” otherwise the MILP has no feasible pairs."""
        payload = build_boreal_scenario(scenario_id)
        effector_types: set[str] = set()
        for e in payload["effectors"].values():
            effector_types |= set(e["pk_matrix"].keys())
        for t in payload["threats"]:
            assert t["estimated_type"] in effector_types, (
                f"threat {t['id']} has type {t['estimated_type']!r} "
                f"which no effector's pk_matrix contains"
            )

    @pytest.mark.parametrize("scenario_id", list(BOREAL_SCENARIOS.keys()))
    def test_threats_seeded_south_of_forward_defender(
        self, scenario_id: str, geo: BorealGeography
    ) -> None:
        """Narrative invariant: Country Y attacks Country X. Every
        threat must be seeded south of the southernmost Country X
        base (the forward FOB â€” Boreal Watch Post). Threshold is
        derived from the loaded geography rather than hardcoded so it
        survives canvas edits."""
        payload = build_boreal_scenario(scenario_id)
        forward_defender_y = min(
            b.y_km for b in (*geo.north_air_bases, geo.north_capital)
        )
        for t in payload["threats"]:
            assert t["y"] < forward_defender_y, (
                f"{scenario_id}/{t['id']} seeded at y={t['y']:.1f} â€” "
                f"expected y < {forward_defender_y:.1f} "
                "(south of the forward-most Country X base)"
            )

    def test_unknown_scenario_raises_keyerror(self) -> None:
        with pytest.raises(KeyError):
            build_boreal_scenario("no_such_scenario")


# --------------------------------------------------------------------------- #
# Engine-dataclass materialisation                                            #
# --------------------------------------------------------------------------- #

class TestEngineInputsMaterialisation:

    @pytest.mark.parametrize("scenario_id", list(BOREAL_SCENARIOS.keys()))
    def test_materialises_to_typed_dataclasses(self, scenario_id: str) -> None:
        bases, effectors, threats, intent, blind_spots = (
            boreal_scenario_as_engine_inputs(scenario_id)
        )
        assert all(isinstance(b, Base) for b in bases)
        assert all(isinstance(t, Threat) for t in threats)
        assert all(e.name for e in effectors.values())
        assert intent.min_pk_for_engage > 0
        # blind_spots is a list of (x, y) pairs.
        for bs in blind_spots:
            assert isinstance(bs, tuple) and len(bs) == 2


# --------------------------------------------------------------------------- #
# Pipeline integration â€” mode correctness                                     #
# --------------------------------------------------------------------------- #

EXPECTED_MODES = {sid: spec.expected_mode for sid, spec in BOREAL_SCENARIOS.items()}


class TestPipelineIntegration:

    @pytest.mark.parametrize("scenario_id", list(BOREAL_SCENARIOS.keys()))
    def test_scenario_lands_in_expected_autonomy_mode(
        self, scenario_id: str
    ) -> None:
        bases, effectors, threats, intent, blind_spots = (
            boreal_scenario_as_engine_inputs(scenario_id)
        )
        result = evaluate(bases, effectors, threats, intent, blind_spots=blind_spots)
        assert result.assurance.autonomy_mode.value == EXPECTED_MODES[scenario_id], (
            f"{scenario_id}: expected {EXPECTED_MODES[scenario_id]}, "
            f"got {result.assurance.autonomy_mode.value} "
            f"(SA={result.assurance.sa_health:.1f}, "
            f"complexity={result.assurance.situation_complexity:.2f}, "
            f"stakes={result.assurance.stakes:.2f})"
        )

    @pytest.mark.parametrize("scenario_id", list(BOREAL_SCENARIOS.keys()))
    def test_pipeline_returns_three_coas(self, scenario_id: str) -> None:
        bases, effectors, threats, intent, blind_spots = (
            boreal_scenario_as_engine_inputs(scenario_id)
        )
        result = evaluate(bases, effectors, threats, intent, blind_spots=blind_spots)
        assert len(result.coas) == 3

    def test_jammed_surfaces_at_least_one_alert(self) -> None:
        """The jammed scenario has degraded sensor_agreement + stale
        tracks + a blind spot â€” the alert surface must fire."""
        bases, effectors, threats, intent, blind_spots = (
            boreal_scenario_as_engine_inputs("boreal_jammed")
        )
        result = evaluate(bases, effectors, threats, intent, blind_spots=blind_spots)
        assert len(result.assurance.alerts) >= 1


# --------------------------------------------------------------------------- #
# Determinism                                                                 #
# --------------------------------------------------------------------------- #

class TestDeterminism:
    """The engine's determinism contract must hold through the adapter."""

    @pytest.mark.parametrize("scenario_id", list(BOREAL_SCENARIOS.keys()))
    def test_identical_inputs_yield_identical_json(
        self, scenario_id: str
    ) -> None:
        bases, effectors, threats, intent, blind_spots = (
            boreal_scenario_as_engine_inputs(scenario_id)
        )
        outputs = set()
        for _ in range(50):
            result = evaluate(bases, effectors, threats, intent, blind_spots=blind_spots)
            outputs.add(json.dumps(result.as_dict(), sort_keys=True))
        assert len(outputs) == 1, (
            f"{scenario_id} produced {len(outputs)} distinct outputs "
            "across 50 runs â€” determinism contract violated"
        )


# --------------------------------------------------------------------------- #
# API surface (only runs if FastAPI is installed)                             #
# --------------------------------------------------------------------------- #

@pytest.mark.skipif(
    pytest.importorskip("fastapi", reason="fastapi not installed") is None,
    reason="fastapi not installed",
)
class TestBorealApiSurface:
    """Optional: when the Boreal scenarios are wired into the FastAPI
    app (see MIGRATION snippet in docs/BOREAL_PASSAGE.md), these
    tests cover the external surface."""

    def test_boreal_scenarios_registered_in_api(self) -> None:
        """Fails until the migration snippet is applied. Kept here so
        that, once applied, the integration is verified end-to-end."""
        try:
            from nimbus_c2.api.demo_data import DEMO_SCENARIOS
        except ImportError:
            pytest.skip("demo_data not importable in this environment")
        registered = set(DEMO_SCENARIOS.keys())
        boreal = set(BOREAL_SCENARIOS.keys())
        # If the migration has been applied, all four Boreal ids appear
        # alongside the originals. If not, this xfails rather than blocking.
        if not boreal.issubset(registered):
            pytest.xfail(
                "Boreal scenarios not yet registered in DEMO_SCENARIOS â€” "
                "apply the migration snippet in docs/BOREAL_PASSAGE.md."
            )
