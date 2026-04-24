# SPDX-FileCopyrightText: 2026 Maria Westrin
# SPDX-License-Identifier: MIT
"""Boreal Passage â€” hackathon scenario pack adapter.

This module loads the Boreal Passage tactical canvas
(``data/boreal/Boreal_passage_coordinates.csv``) into the engine's
existing ``Base`` / ``Threat`` / ``CommandersIntent`` dataclasses and
exposes four concrete scenarios that exercise the full
``evaluate()`` pipeline end-to-end.

The canvas
----------

The Boreal Passage is a fictitious 1667 km Ã— 1300 km strait with two
opposing countries:

    Country X (north, blue side) â€” defender
        Arktholm          (capital, high-value asset)
        Highridge Command (inland air base)
        Northern Vanguard Base (western coastal air base)
        Boreal Watch Post (forward operating base, on island)
        Valbrek, Nordvik  (major cities â€” tracked, not defended here)

    Country Y (south, red side) â€” threat origin
        Meridia           (capital)
        Firewatch Station (eastern coastal air base)
        Southern Redoubt  (inland air base)
        Spear Point Base  (forward strike base, on island)
        Callhaven, Solano (major cities â€” tracked, not used here)

The pack defends *Country X*. Threats in every scenario originate
from Country Y installations and cross the Passage northbound.

Coordinate convention
---------------------

The source CSV uses +y = south (map-image convention: Arktholm at
yâ‰ˆ95, Meridia at yâ‰ˆ1208). The Nimbus-C2 engine uses +y = north and
``heading_deg`` as compass bearing from north (see
``models.Threat``). The loader therefore **flips y on ingest**:

    y_nimbus = Y_EXTENT_KM - y_csv        (Y_EXTENT_KM = 1300)

After the flip, Arktholm is at yâ‰ˆ1205 (north, high y) and Meridia is
at yâ‰ˆ91.7 (south, low y). Threats attacking northbound have
``heading_deg=0`` (due north, +y direction), which is how
``heading_deg`` is defined everywhere else in the engine.

Maturity statement
------------------

This pack adds **geographic grounding**, not new algorithmic
capability. It does not modify the solver, assurance layer, COA
generator, or SITREP. Autonomy-mode outcomes on the Boreal scenarios
are a consequence of the *existing*, already-tested pipeline
applied to a richer operational picture. See
``docs/BOREAL_PASSAGE.md`` for the full scoping statement.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any, Iterable

from nimbus_c2.models import (
    Base,
    CommandersIntent,
    Effector,
    ROETier,
    Threat,
)

# --------------------------------------------------------------------------- #
# Canvas extent (matches the published SVG viewBox and the CSV range)         #
# --------------------------------------------------------------------------- #

X_EXTENT_KM: float = 1666.7
Y_EXTENT_KM: float = 1300.0


# --------------------------------------------------------------------------- #
# Parsed geography                                                            #
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class BorealFeature:
    """One row from the Boreal Passage CSV in the engine's coordinate system.

    Coordinates are in Nimbus-C2 convention: +y = north, km from the
    south-west corner. Features with ``geometry_type == "polygon"``
    have their vertex list in ``polygon_km`` (also y-flipped); points
    have an empty list.
    """
    record_type: str                  # "location" | "terrain"
    feature_id: str                   # stable id (may be empty for locations)
    feature_name: str                 # human-readable name
    side: str                         # "north" | "south"
    subtype: str                      # air_base | capital | major_city | mainland | island | peninsula
    location_context: str             # mainland | island (only for locations)
    geometry_type: str                # "point" | "polygon"
    x_km: float
    y_km: float
    polygon_km: tuple[tuple[float, float], ...] = ()
    notes: str = ""


@dataclass(frozen=True)
class BorealGeography:
    """Fully parsed Boreal Passage canvas.

    Exposes the feature lists the scenario builder needs:

        north_air_bases, north_capital, north_cities,
        south_air_bases, south_capital, south_cities,
        terrain
    """
    features: tuple[BorealFeature, ...]

    # Derived views -- computed once in __post_init__-style properties.
    @property
    def locations(self) -> tuple[BorealFeature, ...]:
        return tuple(f for f in self.features if f.record_type == "location")

    @property
    def terrain(self) -> tuple[BorealFeature, ...]:
        return tuple(f for f in self.features if f.record_type == "terrain")

    def _by(self, side: str, subtype: str) -> tuple[BorealFeature, ...]:
        return tuple(
            f for f in self.locations
            if f.side == side and f.subtype == subtype
        )

    @property
    def north_air_bases(self) -> tuple[BorealFeature, ...]:
        return self._by("north", "air_base")

    @property
    def north_capital(self) -> BorealFeature:
        capitals = self._by("north", "capital")
        if len(capitals) != 1:
            raise ValueError(
                f"expected exactly one north capital, found {len(capitals)}"
            )
        return capitals[0]

    @property
    def north_cities(self) -> tuple[BorealFeature, ...]:
        return self._by("north", "major_city")

    @property
    def south_air_bases(self) -> tuple[BorealFeature, ...]:
        return self._by("south", "air_base")

    @property
    def south_capital(self) -> BorealFeature:
        capitals = self._by("south", "capital")
        if len(capitals) != 1:
            raise ValueError(
                f"expected exactly one south capital, found {len(capitals)}"
            )
        return capitals[0]

    @property
    def south_cities(self) -> tuple[BorealFeature, ...]:
        return self._by("south", "major_city")

    def find(self, name: str) -> BorealFeature:
        """Look up a feature by its human name. Raises KeyError if not found."""
        for f in self.features:
            if f.feature_name == name:
                return f
        raise KeyError(f"no Boreal feature named {name!r}")


# --------------------------------------------------------------------------- #
# CSV loader                                                                  #
# --------------------------------------------------------------------------- #

def _flip_y(y: float) -> float:
    """CSV convention (+y=south) â†’ Nimbus convention (+y=north)."""
    return Y_EXTENT_KM - y


def _parse_polygon(raw: str) -> tuple[tuple[float, float], ...]:
    """Parse a CSV-embedded polygon literal.

    Input format, as produced by the scenario authors:

        "[[x0, y0], [x1, y1], ...]"

    The literal is already valid Python / JSON after unwrapping the
    outer quotes (which the csv module strips for us). We use
    ``ast.literal_eval`` rather than ``json.loads`` because Python
    list literals are a strict superset of JSON arrays of numbers â€”
    this is the smallest parser that handles both.
    """
    if not raw.strip():
        return ()
    import ast
    verts = ast.literal_eval(raw)
    return tuple((float(vx), _flip_y(float(vy))) for (vx, vy) in verts)


def load_boreal_geography(
    csv_path: str | Path | None = None,
) -> BorealGeography:
    """Load the Boreal Passage canvas from CSV.

    Parameters
    ----------
    csv_path :
        Path to the Boreal coordinates CSV. If ``None``, resolves to
        the bundled copy at
        ``nimbus_c2/scenarios/data/Boreal_passage_coordinates.csv``
        (installed alongside this module).

    Returns
    -------
    BorealGeography
        All features with y-axis flipped into Nimbus convention.
    """
    if csv_path is None:
        # Bundled data â€” uses importlib.resources so it works from both
        # source checkout and installed wheel.
        try:
            ref = resources.files("nimbus_saab_ext") / "data" / "Boreal_passage_coordinates.csv"
            csv_text = ref.read_text(encoding="utf-8")
        except (FileNotFoundError, ModuleNotFoundError):
            # Fallback: development checkout where data/boreal lives at repo root.
            repo_root = Path(__file__).resolve().parents[3]
            csv_path = repo_root / "data" / "boreal" / "Boreal_passage_coordinates.csv"
            csv_text = Path(csv_path).read_text(encoding="utf-8")
    else:
        csv_text = Path(csv_path).read_text(encoding="utf-8")

    features: list[BorealFeature] = []
    reader = csv.DictReader(csv_text.splitlines())
    for row in reader:
        poly_raw = row.get("coordinates_km", "") or ""
        features.append(BorealFeature(
            record_type=row["record_type"],
            feature_id=row.get("feature_id", "") or "",
            feature_name=row["feature_name"],
            side=row["side"],
            subtype=row["subtype"],
            location_context=row.get("location_context", "") or "",
            geometry_type=row["geometry_type"],
            x_km=float(row["x_km"]),
            y_km=_flip_y(float(row["y_km"])),
            polygon_km=_parse_polygon(poly_raw),
            notes=row.get("notes", "") or "",
        ))
    return BorealGeography(features=tuple(features))


# --------------------------------------------------------------------------- #
# Country-X defensive posture (bases + effectors)                             #
# --------------------------------------------------------------------------- #

# Effector registry for the Boreal theatre. Same shape as the canonical
# engine demo, but ranges are calibrated against Boreal geography:
# Arktholm is ~470 km from Spear Point Base (nearest Country Y forward
# launcher) in Nimbus coords â€” a 400 km SAM covers the approach from
# Spear Point to Arktholm, but not from deep Country Y territory.
BOREAL_EFFECTORS: dict[str, dict[str, Any]] = {
    "sam": {
        "name": "sam",
        "speed_kmh": 3000,
        "cost_weight": 80,
        "pk_matrix": {
            "bomber": 0.95, "drone": 0.9, "fast-mover": 0.7,
            "hypersonic": 0.5, "ghost": 0.8,
        },
        "range_km": 400,
        "min_engage_km": 5,
        "response_time_sec": 10,
    },
    "fighter": {
        "name": "fighter",
        "speed_kmh": 2000,
        "cost_weight": 50,
        "pk_matrix": {
            "bomber": 0.9, "drone": 0.7, "fast-mover": 0.8,
            "hypersonic": 0.3, "ghost": 0.6,
        },
        "range_km": 1200,
        "min_engage_km": 20,
        "response_time_sec": 60,
    },
    "drone": {
        "name": "drone",
        "speed_kmh": 400,
        "cost_weight": 10,
        "pk_matrix": {
            "bomber": 0.4, "drone": 0.8, "fast-mover": 0.1,
            "hypersonic": 0.05, "ghost": 0.3,
        },
        "range_km": 300,
        "min_engage_km": 0,
        "response_time_sec": 30,
    },
}


def _country_x_bases(geo: BorealGeography) -> list[dict[str, Any]]:
    """Build the defender's base list from the geography.

    Arktholm (capital) is the high-value protected asset. Each air
    base gets a realistic SAM/fighter/drone inventory appropriate to
    its role (capital > main coastal > forward FOB).
    """
    arktholm = geo.north_capital
    nvb = geo.find("Northern Vanguard Base")
    highridge = geo.find("Highridge Command")
    bwp = geo.find("Boreal Watch Post")

    return [
        # Capital: strongest inventory, reserves held for later waves.
        {
            "name": arktholm.feature_name,
            "x": arktholm.x_km, "y": arktholm.y_km,
            "inventory": {"sam": 12, "fighter": 4, "drone": 8},
            "is_capital": True,
            "reserve_floor": {"sam": 4},
            "launchers_per_cycle": {"sam": 2, "fighter": 1, "drone": 1},
        },
        # Western coastal: covers Nordvik corridor.
        {
            "name": nvb.feature_name,
            "x": nvb.x_km, "y": nvb.y_km,
            "inventory": {"sam": 6, "fighter": 3, "drone": 10},
            "launchers_per_cycle": {"sam": 1, "fighter": 1, "drone": 2},
        },
        # Inland: depth, fighter dominance.
        {
            "name": highridge.feature_name,
            "x": highridge.x_km, "y": highridge.y_km,
            "inventory": {"sam": 8, "fighter": 6, "drone": 6},
            "launchers_per_cycle": {"sam": 1, "fighter": 2, "drone": 1},
        },
        # Forward FOB on northern island: eyes, not teeth.
        {
            "name": bwp.feature_name,
            "x": bwp.x_km, "y": bwp.y_km,
            "inventory": {"sam": 4, "fighter": 2, "drone": 6},
            "launchers_per_cycle": {"sam": 1, "fighter": 1, "drone": 1},
        },
    ]


# Canonical commander's intent for every Boreal scenario. Stage-1
# parity-friendly: one effector per threat, strict feasibility floors.
_INTENT_DEFAULT = {
    "roe_tier": "standard",
    "min_pk_for_engage": 0.55,
    "min_safety_margin_sec": 5.0,
    "max_effectors_per_threat": 1,
}


# --------------------------------------------------------------------------- #
# Threat factories â€” one per scenario                                         #
# --------------------------------------------------------------------------- #

def _threats_clean(geo: BorealGeography) -> list[dict[str, Any]]:
    """Scenario 1 â€” CLEAN. Three bombers launched from Spear Point Base,
    fanning out toward Arktholm. Clean sensor picture, high track
    quality. Exercises AUTONOMOUS mode."""
    origin = geo.find("Spear Point Base")
    # Heading north (~0Â°) with small lateral spread. Tracks seeded
    # ~40 km off the launch base so TTA is non-trivial but tractable.
    return [
        {"id": "B01",
         "x": origin.x_km - 30, "y": origin.y_km + 40,
         "speed_kmh": 700, "heading_deg": 350,
         "estimated_type": "bomber", "threat_value": 85.0,
         "class_confidence": 0.95, "kinematic_consistency": 0.92,
         "sensor_agreement": 1.0, "age_sec": 3.0},
        {"id": "B02",
         "x": origin.x_km + 10, "y": origin.y_km + 40,
         "speed_kmh": 650, "heading_deg": 0,
         "estimated_type": "bomber", "threat_value": 80.0,
         "class_confidence": 0.93, "kinematic_consistency": 0.90,
         "sensor_agreement": 0.98, "age_sec": 4.5},
        {"id": "B03",
         "x": origin.x_km + 50, "y": origin.y_km + 40,
         "speed_kmh": 600, "heading_deg": 10,
         "estimated_type": "bomber", "threat_value": 82.0,
         "class_confidence": 0.94, "kinematic_consistency": 0.91,
         "sensor_agreement": 1.0, "age_sec": 3.2},
    ]


def _threats_swarm(geo: BorealGeography) -> list[dict[str, Any]]:
    """Scenario 2 â€” SWARM. 12-drone swarm from Southern Redoubt corridor
    plus two fast-movers from Firewatch Station plus one ghost over
    the Passage. Exercises ADVISE mode (elevated complexity, mixed
    track quality)."""
    sr = geo.find("Southern Redoubt")
    fw = geo.find("Firewatch Station")

    threats: list[dict[str, Any]] = []
    # 12 drones in a 4-wide x 3-deep lattice 80 km north of Southern Redoubt.
    for i in range(12):
        col = i % 4
        row = i // 4
        threats.append({
            "id": f"D{i:02d}",
            "x": sr.x_km + (col - 1.5) * 25,
            "y": sr.y_km + 80 + row * 20,
            "speed_kmh": 400,
            "heading_deg": 0,
            "estimated_type": "drone",
            "threat_value": 15.0,
            "class_confidence": 0.75,
            "kinematic_consistency": 0.8,
            "sensor_agreement": 0.9,
            "age_sec": 8.0,
        })
    # 2 fast-movers from Firewatch (eastern coastal) heading NNW.
    threats.extend([
        {"id": "F01",
         "x": fw.x_km - 20, "y": fw.y_km + 60,
         "speed_kmh": 1500, "heading_deg": 330,
         "estimated_type": "fast-mover", "threat_value": 95.0,
         "class_confidence": 0.88, "kinematic_consistency": 0.9,
         "sensor_agreement": 0.95, "age_sec": 4.0},
        {"id": "F02",
         "x": fw.x_km - 50, "y": fw.y_km + 80,
         "speed_kmh": 1400, "heading_deg": 325,
         "estimated_type": "fast-mover", "threat_value": 92.0,
         "class_confidence": 0.85, "kinematic_consistency": 0.88,
         "sensor_agreement": 0.93, "age_sec": 5.0},
    ])
    # 1 ghost near the Passage midline (yâ‰ˆ650) â€” ambiguous classification.
    threats.append({
        "id": "G01",
        "x": 700.0, "y": 700.0,
        "speed_kmh": 900, "heading_deg": 20,
        "estimated_type": "ghost", "threat_value": 70.0,
        "class_confidence": 0.55, "kinematic_consistency": 0.6,
        "sensor_agreement": 0.7, "age_sec": 15.0,
    })
    return threats


def _threats_jammed(geo: BorealGeography) -> list[dict[str, Any]]:
    """Scenario 3 â€” JAMMED. Hypersonic launch from Meridia + multiple
    ghosts over Spear Point island + fast-mover from Firewatch, all
    under degraded sensor agreement with a blind spot near the
    forward FOB. Exercises DEFER mode."""
    meridia = geo.find("Meridia (Capital Y)")
    spear = geo.find("Spear Point Base")
    fw = geo.find("Firewatch Station")
    return [
        {"id": "H01",
         "x": meridia.x_km - 40, "y": meridia.y_km + 80,
         "speed_kmh": 4000, "heading_deg": 340,
         "estimated_type": "hypersonic", "threat_value": 200.0,
         "class_confidence": 0.45, "kinematic_consistency": 0.5,
         "sensor_agreement": 0.45, "age_sec": 18.0},
        {"id": "G02",
         "x": spear.x_km - 30, "y": spear.y_km + 20,
         "speed_kmh": 700, "heading_deg": 355,
         "estimated_type": "ghost", "threat_value": 95.0,
         "class_confidence": 0.4, "kinematic_consistency": 0.55,
         "sensor_agreement": 0.4, "age_sec": 25.0},
        {"id": "G03",
         "x": spear.x_km + 30, "y": spear.y_km + 20,
         "speed_kmh": 800, "heading_deg": 5,
         "estimated_type": "ghost", "threat_value": 90.0,
         "class_confidence": 0.45, "kinematic_consistency": 0.5,
         "sensor_agreement": 0.45, "age_sec": 22.0},
        {"id": "F03",
         "x": fw.x_km - 30, "y": fw.y_km + 40,
         "speed_kmh": 1600, "heading_deg": 325,
         "estimated_type": "fast-mover", "threat_value": 100.0,
         "class_confidence": 0.6, "kinematic_consistency": 0.7,
         "sensor_agreement": 0.55, "age_sec": 12.0},
    ]


def _blind_spots_jammed(geo: BorealGeography) -> list[tuple[float, float]]:
    """A coverage gap centred on Spear Point island â€” the forward
    contested airspace in the Passage. Matches the JAMMED scenario
    narrative ('blind spot over the primary track')."""
    spear = geo.find("Spear Point Base")
    return [(spear.x_km, spear.y_km + 20)]


def _threats_strait(geo: BorealGeography) -> list[dict[str, Any]]:
    """Scenario 4 â€” STRAIT CROSSING (new). A doctrine-realistic first
    wave: 2 bombers from Spear Point + 1 fast-mover from Firewatch
    + 1 ambiguous track near the midline. Moderate complexity,
    elevated stakes (threats close to Arktholm), mixed track
    quality. Designed to land in ADVISE â€” the system proposes three
    COAs, operator confirms."""
    spear = geo.find("Spear Point Base")
    fw = geo.find("Firewatch Station")
    arktholm = geo.north_capital

    # Midline ambiguous track between Arktholm and Spear Point.
    mid_x = (arktholm.x_km + spear.x_km) / 2
    mid_y = (arktholm.y_km + spear.y_km) / 2

    return [
        {"id": "B11",
         "x": spear.x_km - 20, "y": spear.y_km + 30,
         "speed_kmh": 720, "heading_deg": 355,
         "estimated_type": "bomber", "threat_value": 90.0,
         "class_confidence": 0.91, "kinematic_consistency": 0.90,
         "sensor_agreement": 0.95, "age_sec": 4.0},
        {"id": "B12",
         "x": spear.x_km + 25, "y": spear.y_km + 30,
         "speed_kmh": 700, "heading_deg": 5,
         "estimated_type": "bomber", "threat_value": 88.0,
         "class_confidence": 0.90, "kinematic_consistency": 0.88,
         "sensor_agreement": 0.95, "age_sec": 4.5},
        {"id": "F11",
         "x": fw.x_km - 40, "y": fw.y_km + 60,
         "speed_kmh": 1500, "heading_deg": 320,
         "estimated_type": "fast-mover", "threat_value": 95.0,
         "class_confidence": 0.85, "kinematic_consistency": 0.88,
         "sensor_agreement": 0.9, "age_sec": 6.0},
        {"id": "G11",
         "x": mid_x, "y": mid_y,
         "speed_kmh": 850, "heading_deg": 10,
         "estimated_type": "ghost", "threat_value": 75.0,
         "class_confidence": 0.58, "kinematic_consistency": 0.62,
         "sensor_agreement": 0.7, "age_sec": 14.0},
    ]


# --------------------------------------------------------------------------- #
# Scenario descriptor registry                                                #
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class BorealScenarioSpec:
    """One Boreal scenario: metadata + threat/blindspot factories.

    The factories are invoked at build time (with the loaded
    geography) to produce the concrete threat list. Keeping the
    factories as functions-of-geography rather than baked-in
    constants keeps the module rebuildable against a different
    canvas without code changes.
    """
    id: str
    name: str
    description: str
    expected_mode: str                # "autonomous" | "advise" | "defer"
    threats_fn: Any
    blind_spots_fn: Any = None


BOREAL_SCENARIOS: dict[str, BorealScenarioSpec] = {
    "boreal_clean": BorealScenarioSpec(
        id="boreal_clean",
        name="Boreal â€” clean picture (three bombers from Spear Point)",
        description=(
            "Three bombers launched from Spear Point Base fan north "
            "toward Arktholm under high-quality tracking. Country X "
            "defence: Arktholm + NVB + Highridge + Boreal Watch Post. "
            "Expected autonomy mode: AUTONOMOUS."
        ),
        expected_mode="autonomous",
        threats_fn=_threats_clean,
    ),
    "boreal_swarm": BorealScenarioSpec(
        id="boreal_swarm",
        name="Boreal â€” drone swarm + fast-mover breakthrough",
        description=(
            "12-drone swarm from the Southern Redoubt corridor plus "
            "two fast-movers from Firewatch Station plus one ghost "
            "over the Passage. Elevated complexity, mixed track "
            "quality. Expected autonomy mode: ADVISE."
        ),
        expected_mode="advise",
        threats_fn=_threats_swarm,
    ),
    "boreal_jammed": BorealScenarioSpec(
        id="boreal_jammed",
        name="Boreal â€” jammed sensors + hypersonic from Meridia",
        description=(
            "Hypersonic launch from Meridia, two ghosts over Spear "
            "Point island, fast-mover from Firewatch â€” all under "
            "degraded cross-sensor agreement with a blind spot over "
            "the forward FOB. Expected autonomy mode: DEFER."
        ),
        expected_mode="defer",
        threats_fn=_threats_jammed,
        blind_spots_fn=_blind_spots_jammed,
    ),
    "boreal_strait": BorealScenarioSpec(
        id="boreal_strait",
        name="Boreal â€” strait crossing (four-track first wave)",
        description=(
            "A doctrine-realistic first wave: two bombers from Spear "
            "Point, one fast-mover from Firewatch, and one "
            "ambiguous ghost at the Passage midline. Moderate "
            "complexity, elevated stakes, mixed track quality. "
            "Expected autonomy mode: ADVISE."
        ),
        expected_mode="advise",
        threats_fn=_threats_strait,
    ),
}


# --------------------------------------------------------------------------- #
# Scenario builder                                                            #
# --------------------------------------------------------------------------- #

def build_boreal_scenario(
    scenario_id: str,
    geo: BorealGeography | None = None,
) -> dict[str, Any]:
    """Build a ready-to-POST EvaluateRequest payload.

    Parameters
    ----------
    scenario_id :
        One of ``BOREAL_SCENARIOS.keys()``.
    geo :
        A pre-loaded ``BorealGeography``. If ``None``, loads from the
        bundled CSV.

    Returns
    -------
    dict
        Shape matches ``nimbus_c2.api.app.EvaluateRequest`` exactly.
    """
    if scenario_id not in BOREAL_SCENARIOS:
        raise KeyError(
            f"unknown Boreal scenario {scenario_id!r}; "
            f"known: {sorted(BOREAL_SCENARIOS.keys())}"
        )
    if geo is None:
        geo = load_boreal_geography()

    spec = BOREAL_SCENARIOS[scenario_id]
    bases = _country_x_bases(geo)
    threats = spec.threats_fn(geo)
    blind_spots = spec.blind_spots_fn(geo) if spec.blind_spots_fn else []

    return {
        "bases": bases,
        "effectors": BOREAL_EFFECTORS,
        "threats": threats,
        "intent": dict(_INTENT_DEFAULT),
        "blind_spots": blind_spots,
    }


# --------------------------------------------------------------------------- #
# Convenience: build engine dataclasses directly (skip JSON round-trip)       #
# --------------------------------------------------------------------------- #

def boreal_scenario_as_engine_inputs(
    scenario_id: str,
    geo: BorealGeography | None = None,
) -> tuple[
    list[Base],
    dict[str, Effector],
    list[Threat],
    CommandersIntent,
    list[tuple[float, float]],
]:
    """Same as ``build_boreal_scenario`` but materialised into engine
    dataclasses. Useful for tests that bypass the API layer."""
    payload = build_boreal_scenario(scenario_id, geo)

    bases = [
        Base(
            name=b["name"], x=b["x"], y=b["y"],
            inventory=dict(b["inventory"]),
            is_capital=b.get("is_capital", False),
            reserve_floor=dict(b.get("reserve_floor", {})),
            launchers_per_cycle=dict(b.get("launchers_per_cycle", {})),
        )
        for b in payload["bases"]
    ]
    effectors = {
        k: Effector(
            name=e["name"],
            speed_kmh=e["speed_kmh"],
            cost_weight=e["cost_weight"],
            pk_matrix=dict(e["pk_matrix"]),
            range_km=e["range_km"],
            min_engage_km=e.get("min_engage_km", 0.0),
            response_time_sec=e["response_time_sec"],
        )
        for k, e in payload["effectors"].items()
    }
    threats = [
        Threat(
            id=t["id"], x=t["x"], y=t["y"],
            speed_kmh=t["speed_kmh"], heading_deg=t["heading_deg"],
            estimated_type=t["estimated_type"],
            threat_value=t["threat_value"],
            class_confidence=t.get("class_confidence", 0.85),
            kinematic_consistency=t.get("kinematic_consistency", 0.9),
            sensor_agreement=t.get("sensor_agreement", 1.0),
            age_sec=t.get("age_sec", 10.0),
        )
        for t in payload["threats"]
    ]
    intent = CommandersIntent(
        roe_tier=ROETier(payload["intent"]["roe_tier"]),
        min_pk_for_engage=payload["intent"]["min_pk_for_engage"],
        min_safety_margin_sec=payload["intent"]["min_safety_margin_sec"],
        max_effectors_per_threat=payload["intent"]["max_effectors_per_threat"],
    )
    blind_spots: list[tuple[float, float]] = [
        (float(x), float(y)) for (x, y) in payload["blind_spots"]
    ]
    return bases, effectors, threats, intent, blind_spots


__all__ = [
    "BOREAL_EFFECTORS",
    "BOREAL_SCENARIOS",
    "BorealFeature",
    "BorealGeography",
    "BorealScenarioSpec",
    "X_EXTENT_KM",
    "Y_EXTENT_KM",
    "boreal_scenario_as_engine_inputs",
    "build_boreal_scenario",
    "load_boreal_geography",
]
